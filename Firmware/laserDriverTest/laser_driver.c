
#include "ti_msp_dl_config.h"
#include "laser_pwm_control.h"
#include <stdbool.h>
#include <stdint.h>

/*
 * DAC setpoint applied once at boot before pulses begin.
 * 100 out of 4095 on a 2.5 V reference ≈ 61 mV.
 */
#define DAC_SETPOINT            100

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
#define TICKS_PER_RAMP_STEP     625u    /* 200 000 / 320 */
#define HOLD_TICKS              100000u

typedef enum {
    STATE_IDLE,
    STATE_RAMP_UP,
    STATE_HOLD_HIGH,
    STATE_RAMP_DOWN,
    STATE_HOLD_LOW,
} PulseState;

/* Incremented only in TIMG0 ISR; read in main loop. */
static volatile uint32_t isr_ticks = 0;

/*
 * Set to true to start the repeating trapezoidal pulse sequence.
 * A future button ISR should set this flag instead of the auto-start below.
 */
volatile bool pulse_active = false;

/*
 * Write the laser PWM duty step.  Call only while pins are in PWM mode.
 * UP mode: CC0 = step -> duty = step / 320.
 *   step = 0          -> ~0%   laser
 *   step = RAMP_STEPS -> 100%  laser
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
        .timerMode    = DL_TIMER_TIMER_MODE_PERIODIC,   /* down-counting, repeating */
        .period       = 319,                             /* 320 counts at 32 MHz = 100 kHz */
        .startTimer   = DL_TIMER_STOP,
        .genIntermInt = DL_TIMER_INTERM_INT_DISABLED,
        .counterVal   = 0U,
    };
    DL_TimerG_initTimerMode(TIMG0, (DL_TimerG_TimerConfig *)&tmrCfg);

    DL_TimerG_enableClock(TIMG0);
}

int main(void)
{
    SYSCFG_DL_init();
    /* PA8 = 1 (laser path HIGH), PA22 = 0 (dummy LOW) — set by GPIO init. */

    DL_DAC12_output12(DAC0, DAC_SETPOINT);
    DL_DAC12_enable(DAC0);

    laser_pwm_init();
    DL_TimerA_startCounter(TIMA0);

    tick_timer_init();
    DL_TimerG_enableInterrupt(TIMG0, DL_TIMERG_INTERRUPT_ZERO_EVENT);
    NVIC_SetPriority(TIMG0_INT_IRQn, 0);
    NVIC_EnableIRQ(TIMG0_INT_IRQn);
    DL_TimerG_startCounter(TIMG0);

    /* Auto-start on boot; replace with a button-press handler to set this flag. */
    pulse_active = true;

    PulseState state     = STATE_IDLE;
    uint32_t   tick_cnt  = 0;
    uint32_t   ramp_step = 0;
    uint32_t   last_tick = 0;

    while (1) {
        if (isr_ticks == last_tick) {
            __WFI();
            continue;
        }
        last_tick++;
        tick_cnt++;

        switch (state) {
            case STATE_IDLE:
                if (pulse_active) {
                    ramp_step = 0;
                    tick_cnt  = 0;
                    state     = STATE_RAMP_UP;
                }
                laser_pins_to_gpio_safe();
                break;

            case STATE_RAMP_UP:
                if (tick_cnt >= TICKS_PER_RAMP_STEP) {
                    tick_cnt = 0;
                    ramp_step++;
                    if (ramp_step >= RAMP_STEPS) {
                        state = STATE_HOLD_HIGH;
                    }
                }
                if (ramp_step == 0) {
                    laser_pins_to_gpio_safe();
                } else {
                    laser_pins_to_pwm();
                    set_laser_step(ramp_step);
                }
                break;

            case STATE_HOLD_HIGH:
                if (tick_cnt >= HOLD_TICKS) {
                    tick_cnt  = 0;
                    ramp_step = RAMP_STEPS;
                    state     = STATE_RAMP_DOWN;
                }
                laser_pins_to_pwm();
                set_laser_step(RAMP_STEPS);
                break;

            case STATE_RAMP_DOWN:
                if (tick_cnt >= TICKS_PER_RAMP_STEP) {
                    tick_cnt = 0;
                    ramp_step--;
                    if (ramp_step == 0) {
                        state = STATE_HOLD_LOW;
                    }
                }
                if (ramp_step == 0) {
                    laser_pins_to_gpio_safe();
                } else {
                    laser_pins_to_pwm();
                    set_laser_step(ramp_step);
                }
                break;

            case STATE_HOLD_LOW:
                if (tick_cnt >= HOLD_TICKS) {
                    tick_cnt  = 0;
                    ramp_step = 0;
                    state     = STATE_RAMP_UP;
                }
                laser_pins_to_gpio_safe();
                break;

            default:
                break;
        }
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
