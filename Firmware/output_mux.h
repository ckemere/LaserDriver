#ifndef OUTPUT_MUX_H
#define OUTPUT_MUX_H

#include <stdbool.h>

/*
 * Runtime IOMUX flips between GPIO-safe and TIMA0 PWM on the module
 * header's PWM pins (J8):
 *
 *   PA7  PWM_A (J8.5, TIMA0_CCP1) -> laser module: laser switch gate / EN.
 *                                   GPIO LOW guarantees "off" at any time.
 *   PA12 PWM_B (J8.4, TIMA0_CCP3) -> laser module: dummy switch gate, GPIO
 *                                   HIGH keeps the dummy path on; e-stim
 *                                   module: CATH, idles LOW (spec §7).
 *
 * TIMA0 init lives in pwm_timer.c.  Both functions are idempotent and are
 * called on every state-machine tick.  laser_pins_set_b_idle_high() picks
 * the idle level of PWM_B for the current mode (true = laser module).
 */

void laser_pins_set_b_idle_high(bool high);
void laser_pins_to_gpio_safe(void);
void laser_pins_to_pwm(void);

#endif /* OUTPUT_MUX_H */
