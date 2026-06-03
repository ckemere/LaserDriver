
#include "ti_msp_dl_config.h"
#include "laser_pwm_control.h"
#include "laser_sysctl.h"
#include "laser_gpio.h"
#include "laser_timera.h"
#include "laser_timerg.h"
#include "laser_dac.h"
#include <stdbool.h>
#include <stdint.h>

/*
 * DAC setpoint applied once at boot before pulses begin.
 * 500 out of 4095 on a 2.5 V reference ≈ 305 mV.
 */
#define DAC_SETPOINT            500

/*
 * TIMA0 runs at 100 kHz (32 MHz BUSCLK / 320 counts), UP-counting mode.
 * Period register = 319 (counts 0..319), so one full cycle = 320 counts.
 *
 * Laser duty = CC0 / 320  (UP mode: output HIGH from 0 to CC0, LOW after).
 *   CC0 = 0:   compare fires at count 0 -> laser ~0%  (GPIO mode used for true off)
 *   CC0 = 320: compare never fires      -> laser 100%
 */
#define PWM_PERIOD_COUNTS       320u

/*
 * Trapezoidal pulse profile.
 * State machine is clocked by TIMG0 at 100 kHz (one tick = 10 µs).
 *
 *   Rise  : 2 s = 200 000 ticks, RAMP_STEPS steps
 *   High  : 1 s = 100 000 ticks
 *   Fall  : 2 s = 200 000 ticks
 *   Low   : 1 s = 100 000 ticks
 */
#define RAMP_STEPS              320u
// #define TICKS_PER_RAMP_STEP     625u    /* 200 000 / 320 */
// #define HOLD_TICKS              100000u
#define TICKS_PER_RAMP_STEP     25u    /* 200 000 / 320 */
#define HOLD_TICKS              10000u

/*
 * Button debounce: require the pin to be stable for this many ticks before
 * accepting a state change.  At 100 kHz, 1000 ticks = 10 ms.
 */
#define DEBOUNCE_TICKS          1000u

/*
 * Boot-phase indicator: blink STIM_MIRROR LED for ~4 s at power-on before
 * accepting button triggers.  At 100 kHz, 4 s = 400 000 ticks; toggling
 * every 10 000 ticks gives a 5 Hz blink.
 */
#define BOOT_BLINK_TICKS        400000u
#define BOOT_BLINK_HALF_PERIOD  10000u

/* -----------------------------------------------------------------------
 * State machine types
 * ----------------------------------------------------------------------- */

/* Top-level: boot blink, waiting for a trigger, or running a laser pulse? */
typedef enum {
    OVERALL_BOOT,
    OVERALL_WAITING,
    OVERALL_TRIGGERED,
} OverallPhase;

/* Button debounce sub-state.  Buttons are wired to +3V3 on press,
 * configured PULL_DOWN in syscfg, so a pressed pin reads HIGH. */
typedef enum {
    BUTTON_IDLE,        /* pin is LOW (not pressed) */
    BUTTON_PRESSED,     /* confirmed press, waiting for release */
    BUTTON_RELEASED,    /* release confirmed — triggers laser on this tick */
} ButtonPhase;

/* Laser waveform sub-state. */
typedef enum {
    LASER_IDLE,
    LASER_RAMP_UP,
    LASER_HOLD_HIGH,
    LASER_RAMP_DOWN,
    LASER_HOLD_LOW,
} LaserPhase;

/*
 * Full machine state.  get_next_state() and set_output() together with this
 * struct completely describe the system — no other mutable global state is
 * needed for the control loop.
 */
typedef struct {
    OverallPhase overall;
    LaserPhase   laser;
    ButtonPhase  button;
    uint32_t     ramp_step;      /* current PWM duty step (0..RAMP_STEPS) */
    uint32_t     tick_count;     /* ticks elapsed within current laser phase */
    uint32_t     debounce_ticks; /* consecutive ticks confirming button state */
} MachineState;

/* -----------------------------------------------------------------------
 * Hardware helpers
 * ----------------------------------------------------------------------- */

/* Incremented only in TIMG0 ISR; read in get_next_state(). */
static volatile uint32_t isr_ticks = 0;

/*
 * Write the laser PWM duty step.  Call only while pins are in PWM mode.
 * UP mode: CC0 = step -> duty = step / 320.
 */
static inline void set_laser_step(uint32_t step)
{
    DL_TimerA_setCaptureCompareValue(TIMA0, step, DL_TIMER_CC_0_INDEX);
}

/*
 * Configure TIMG0 as a 100 kHz periodic tick source for the state machine.
 * TIMA0 (PWM) runs independently and has no interrupt.
 */
static void tick_timer_init(void)
{
    DL_TimerG_reset(TIMG0);
    DL_TimerG_enablePower(TIMG0);
    delay_cycles(16);

    static const DL_TimerG_ClockConfig clkCfg = {
        .clockSel    = DL_TIMER_CLOCK_BUSCLK,
        .divideRatio = DL_TIMER_CLOCK_DIVIDE_1,
        .prescale    = 0U,
    };
    DL_TimerG_setClockConfig(TIMG0, (DL_TimerG_ClockConfig *)&clkCfg);

    static const DL_TimerG_TimerConfig tmrCfg = {
        .timerMode    = DL_TIMER_TIMER_MODE_PERIODIC,
        .period       = 319,   /* 320 counts at 32 MHz = 100 kHz */
        .startTimer   = DL_TIMER_STOP,
        .genIntermInt = DL_TIMER_INTERM_INT_DISABLED,
        .counterVal   = 0U,
    };
    DL_TimerG_initTimerMode(TIMG0, (DL_TimerG_TimerConfig *)&tmrCfg);

    DL_TimerG_enableClock(TIMG0);
}

/* -----------------------------------------------------------------------
 * State machine
 * ----------------------------------------------------------------------- */

/*
 * Advance state by one tick.  Returns state unchanged if no new TIMG0 tick
 * has fired (guards against spurious WFI wakeups from other sources).
 *
 * Button is polled by reading PA3 directly; active-high (pin connects to
 * +3V3 on press), pull-down configured by SysConfig.  A BUTTON_RELEASED
 * event (set for exactly one tick after confirmed release) is consumed
 * by the overall phase logic to start a laser pulse cycle.
 */
static MachineState get_next_state(MachineState s)
{
    static uint32_t last_tick = 0;
    if (isr_ticks == last_tick)
        return s;
    last_tick++;

    /* --- Button debounce (active-high) --- */
    bool pin_pressed = (DL_GPIO_readPins(BUTTON_PORT, BUTTON_TRIGGER_PIN) != 0);
    bool trigger = false;

    switch (s.button) {
        case BUTTON_IDLE:
            if (pin_pressed) {
                s.debounce_ticks++;
                if (s.debounce_ticks >= DEBOUNCE_TICKS) {
                    s.button = BUTTON_PRESSED;
                    s.debounce_ticks = 0;
                }
            } else {
                s.debounce_ticks = 0;
            }
            break;

        case BUTTON_PRESSED:
            if (!pin_pressed) {
                s.debounce_ticks++;
                if (s.debounce_ticks >= DEBOUNCE_TICKS) {
                    s.button = BUTTON_RELEASED;
                    s.debounce_ticks = 0;
                }
            } else {
                s.debounce_ticks = 0;
            }
            break;

        case BUTTON_RELEASED:
            /* One-tick signal consumed here; pass trigger to overall logic. */
            trigger = true;
            s.button = BUTTON_IDLE;
            break;
    }

    /* --- Overall and laser phases --- */
    switch (s.overall) {
        case OVERALL_BOOT:
            s.tick_count++;
            if (s.tick_count >= BOOT_BLINK_TICKS) {
                s.tick_count = 0;
                s.overall    = OVERALL_WAITING;
                /* Drop any button press observed during the boot window. */
                s.button     = BUTTON_IDLE;
                s.debounce_ticks = 0;
            }
            break;

        case OVERALL_WAITING:
            /* Ignore button presses that arrive while a cycle is in progress. */
            if (trigger) {
                s.overall    = OVERALL_TRIGGERED;
                s.laser      = LASER_RAMP_UP;
                s.ramp_step  = 0;
                s.tick_count = 0;
            }
            break;

        case OVERALL_TRIGGERED:
            s.tick_count++;
            switch (s.laser) {
                case LASER_RAMP_UP:
                    if (s.tick_count >= TICKS_PER_RAMP_STEP) {
                        s.tick_count = 0;
                        s.ramp_step++;
                        if (s.ramp_step >= RAMP_STEPS) {
                            s.tick_count = 0;
                            s.laser      = LASER_HOLD_HIGH;
                        }
                    }
                    break;

                case LASER_HOLD_HIGH:
                    if (s.tick_count >= HOLD_TICKS) {
                        s.tick_count = 0;
                        s.ramp_step  = RAMP_STEPS;
                        s.laser      = LASER_RAMP_DOWN;
                    }
                    break;

                case LASER_RAMP_DOWN:
                    if (s.tick_count >= TICKS_PER_RAMP_STEP) {
                        s.tick_count = 0;
                        s.ramp_step--;
                        if (s.ramp_step == 0) {
                            s.tick_count = 0;
                            s.laser      = LASER_HOLD_LOW;
                        }
                    }
                    break;

                case LASER_HOLD_LOW:
                    if (s.tick_count >= HOLD_TICKS) {
                        s.tick_count = 0;
                        s.ramp_step  = 0;
                        s.laser      = LASER_IDLE;
                        s.overall    = OVERALL_WAITING;
                    }
                    break;

                default:
                    break;
            }
            break;
    }

    return s;
}

/*
 * Drive hardware to match the current state.
 * - Boot: laser off, STIM_MIRROR blinks from tick_count.
 * - Waiting: laser off, STIM_MIRROR off.
 * - Triggered: PWM follows the waveform; STIM_MIRROR mirrors laser-on.
 */
static void set_output(MachineState s)
{
    if (s.overall == OVERALL_BOOT) {
        laser_pins_to_gpio_safe();
        if ((s.tick_count / BOOT_BLINK_HALF_PERIOD) & 1u) {
            DL_GPIO_setPins(GPIO_LEDS_PORT, GPIO_LEDS_USER_LED_1_PIN);
        } else {
            DL_GPIO_clearPins(GPIO_LEDS_PORT, GPIO_LEDS_USER_LED_1_PIN);
        }
        return;
    }

    if (s.overall == OVERALL_WAITING) {
        laser_pins_to_gpio_safe();
        DL_GPIO_clearPins(GPIO_LEDS_PORT, GPIO_LEDS_USER_LED_1_PIN);
        return;
    }

    switch (s.laser) {
        case LASER_IDLE:
        case LASER_HOLD_LOW:
            laser_pins_to_gpio_safe();
            DL_GPIO_clearPins(GPIO_LEDS_PORT, GPIO_LEDS_USER_LED_1_PIN);

            break;

        case LASER_RAMP_UP:
        case LASER_RAMP_DOWN:
            if (s.ramp_step == 0) {
                laser_pins_to_gpio_safe();
            } else {
                laser_pins_to_pwm();
                set_laser_step(s.ramp_step);
            }
            DL_GPIO_setPins(GPIO_LEDS_PORT, GPIO_LEDS_USER_LED_1_PIN);

            break;

        case LASER_HOLD_HIGH:
            laser_pins_to_pwm();
            set_laser_step(RAMP_STEPS);
            
            DL_GPIO_setPins(GPIO_LEDS_PORT, GPIO_LEDS_USER_LED_1_PIN);
            break;

        default:
            break;
    }
}

/* -----------------------------------------------------------------------
 * Entry point
 * ----------------------------------------------------------------------- */

volatile uint8_t gEchoData = 0;

int main(void)
{
    SYSCFG_DL_init();
    /* PA21 = 0 (laser path LOW), PA22 = 1 (dummy HIGH), PA3 pull-down
     * enabled — all set by GPIO init in SYSCFG_DL_init().
     */

    /* Hand-rolled SYSCTL + GPIO config running in parallel with SysConfig's.
     * Same registers, same values; behavior unchanged.  Once every
     * peripheral has a register-level replacement these calls take over
     * and SYSCFG_DL_init() goes away. */
    laser_sysctl_init();
    laser_gpio_enable_power_and_reset();
    laser_gpio_init();
    laser_timera_init();
    laser_timerg_init();
    laser_dac_init();
    laser_dac_write12(DAC_SETPOINT);
    laser_dac_enable();

    DL_DAC12_output12(DAC0, DAC_SETPOINT);
    DL_DAC12_enable(DAC0);

    laser_pwm_init();
    laser_pins_to_gpio_safe();
    DL_TimerA_startCounter(TIMA0);

    tick_timer_init();
    DL_TimerG_enableInterrupt(TIMG0, DL_TIMERG_INTERRUPT_ZERO_EVENT);
    NVIC_SetPriority(TIMG0_INT_IRQn, 0);
    NVIC_EnableIRQ(TIMG0_INT_IRQn);
    DL_TimerG_startCounter(TIMG0);

    MachineState state = { OVERALL_BOOT, LASER_IDLE, BUTTON_IDLE, 0, 0, 0 };

    NVIC_ClearPendingIRQ(UART_0_INST_INT_IRQN);
    NVIC_EnableIRQ(UART_0_INST_INT_IRQN);

    while (1) {
        state = get_next_state(state);
        set_output(state);
        __WFI();
    }
}

void TIMG0_IRQHandler(void)
{
    switch (DL_TimerG_getPendingInterrupt(TIMG0)) {
        case DL_TIMERG_IIDX_ZERO:
            isr_ticks++;
            break;
        default:
            break;
    }
}

void UART_0_INST_IRQHandler(void)
{
    switch (DL_UART_Main_getPendingInterrupt(UART_0_INST)) {
        case DL_UART_MAIN_IIDX_RX:
            gEchoData = DL_UART_Main_receiveData(UART_0_INST);
            DL_UART_Main_transmitData(UART_0_INST, gEchoData);
            break;
        default:
            break;
    }
}



/*
 * Copyright (c) 2021, Texas Instruments Incorporated
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * *  Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 * *  Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * *  Neither the name of Texas Instruments Incorporated nor the names of
 *    its contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
 * EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
