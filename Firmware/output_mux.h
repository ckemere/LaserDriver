#ifndef OUTPUT_MUX_H
#define OUTPUT_MUX_H

#include <stdbool.h>
#include "board.h"

/*
 * The two switch lines A / B (board.h BOARD_PWM_A/B_*):
 *
 *   A  laser board: laser switch gate, TIMA0_CCP1 (Rev 2 PA7 = J8.5,
 *      LaserDriverHAT PA22); e-stim: EN (Rev 2 PA7, StimHAT EN_H PA24).
 *      GPIO LOW guarantees "off" at any time.
 *   B  laser board: dummy switch gate, TIMA0_CCP3 (Rev 2 PA12 = J8.4,
 *      LaserDriverHAT PA23), GPIO HIGH keeps the dummy path on; e-stim:
 *      CATH (Rev 2 PA12, StimHAT CATH_H PA23), idles LOW (spec §7).
 *
 * laser_pins_to_gpio_safe() puts both in their GPIO mux at the safe
 * levels; laser_pins_to_pwm() (laser boards only) hands them to TIMA0.
 * TIMA0 init lives in pwm_timer.c.  Both are idempotent and called on
 * every state-machine tick.  laser_pins_set_b_idle_high() picks the idle
 * level of B for the current mode (true = laser).
 */

void laser_pins_set_b_idle_high(bool high);
void laser_pins_to_gpio_safe(void);
#if BOARD_HAS_LASER
void laser_pins_to_pwm(void);
#endif

#endif /* OUTPUT_MUX_H */
