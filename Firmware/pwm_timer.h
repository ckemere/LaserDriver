#ifndef PWM_TIMER_H
#define PWM_TIMER_H

#include <stdint.h>
#include "mcu.h"

/*
 * TIMA0 register-level driver — module PWM on J8 (Rev 2).
 *
 * 100 kHz edge-aligned UP-counting PWM, BUSCLK = 32 MHz, period = 320:
 *
 *   CCP1 (PA7,  PWM_A): HIGH at counter zero, LOW at counter == CC1
 *                       -> duty = CC1 / 320 (CC1 = 320 -> 100 %)
 *   CCP3 (PA12, PWM_B): LOW at zero, HIGH at counter == CC3, with
 *                       CC3 == CC1 -> the complement of CCP1 (no deadband),
 *                       i.e. the dummy switch conducts while the laser
 *                       switch is off.
 *
 * CC writes latch at the next counter-zero event, so a duty update never
 * glitches mid-period.  Pin-mux switching between GPIO-safe and PWM is in
 * output_mux.c; this module only configures the timer.
 *
 * The e-stim module uses the same two pins as independent EN / CATH
 * edges (spec §7); that mode is not part of the bring-up build.
 */

void laser_timera_init(void);
void laser_timera_start(void);

/* Hot-path duty update (called from the tick ISR). */
static inline void laser_timera_set_duty(uint32_t step)
{
    TIMA0->COUNTERREGS.CC_01[1] = step;   /* CC1: PWM_A duty */
    TIMA0->COUNTERREGS.CC_23[1] = step;   /* CC3: PWM_B complement */
}

#endif /* PWM_TIMER_H */
