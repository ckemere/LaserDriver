
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
 * PWM runs at 100 kHz (32 MHz BUSCLK / 320 counts).
 * Period register = 319 (counts 0..319), so one full cycle = 320 counts.
 *
 * Laser duty = (PWM_PERIOD_COUNTS - ccValue) / PWM_PERIOD_COUNTS
 *   ccValue = 0:   compare fires at count 0 (same as zero event) -> laser 100%
 *   ccValue = 319: compare fires after 319 counts               -> laser 1/320
 *
 * "Laser off" is now handled by GPIO mode (laser_pins_to_gpio_safe), not by
 * a PWM ccValue — the hardware safely grounds PA22 regardless of timer state.
 */
#define PWM_PERIOD_COUNTS       320u

/*
 * Trapezoidal pulse profile (all times in PWM ticks at 100 kHz):
 *   Rise  : 2 s = 200 000 ticks, RAMP_STEPS steps
 *   High  : 1 s = 100 000 ticks
 *   Fall  : 2 s = 200 000 ticks
 *   Low   : 1 s = 100 000 ticks
 *
 * ramp_step 0 means laser off (GPIO mode).
 * ramp_step RAMP_STEPS means full on (ccValue = 0).
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

/* Written only in ISR; read in main loop. */
static volatile uint32_t isr_ticks = 0;

/*
 * Set to true to start the repeating trapezoidal pulse sequence.
 * A future button ISR should set this flag instead of the auto-start below.
 */
volatile bool pulse_active = false;

static inline void set_laser_step(uint32_t step)
{
    /* Only call this while pins are in PWM mode (laser_pins_to_pwm called first). */
    DL_TimerA_setCaptureCompareValue(
        TIMA0, PWM_PERIOD_COUNTS - step, DL_TIMER_CC_0_INDEX);
}

int main(void)
{
    SYSCFG_DL_init();
    /* PA8=1 (dummy ON), PA22=0 (laser OFF) — already set by generated GPIO init. */

    DL_DAC12_output12(DAC0, DAC_SETPOINT);
    DL_DAC12_enable(DAC0);

    laser_pwm_init();

    DL_TimerA_enableInterrupt(TIMA0, DL_TIMERA_INTERRUPT_ZERO_EVENT);
    NVIC_SetPriority(TIMA0_INT_IRQn, 0);
    NVIC_EnableIRQ(TIMA0_INT_IRQn);

    DL_TimerA_startCounter(TIMA0);

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

void TIMA0_IRQHandler(void)
{
    switch (DL_TimerA_getPendingInterrupt(TIMA0)) {
        case DL_TIMERA_IIDX_ZERO:
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
