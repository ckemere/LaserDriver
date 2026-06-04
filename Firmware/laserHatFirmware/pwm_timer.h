#ifndef PWM_TIMER_H
#define PWM_TIMER_H

#include <stdint.h>

/*
 * TIMA0 register-level driver — laser bridge PWM.
 *
 * Configures TIMA0 for 100 kHz edge-aligned UP-counting PWM with
 * complementary CC0 / CC0_CMPL outputs:
 *
 *   BUSCLK = 32 MHz, prescale = 0, divide = 1, period = 320 counts
 *
 * UP mode (INIT_VAL_HIGH on CC0):
 *   - CCP0 goes HIGH at counter zero
 *   - CCP0 goes LOW at counter == CC0
 *   - Laser duty = CC0 / 320; CC0 = 0 -> ~0 %, CC0 = 320 -> 100 %
 *   - CCP0_CMPL (PA22) is the hardware complement
 *
 * Pin-mux switching between GPIO-safe and PWM still lives in
 * laser_pwm_control.c; this module only configures the timer itself.
 */

void laser_timera_init(void);
void laser_timera_start(void);

/* Hot-path duty update.  Inline so the state machine doesn't pay a
 * call overhead per tick. */
#include "mcu.h"
static inline void laser_timera_set_duty(uint32_t step)
{
    /* CC_01[0] = CC0 register; UP mode -> duty = step / period. */
    TIMA0->COUNTERREGS.CC_01[0] = step;
}

#endif /* PWM_TIMER_H */
