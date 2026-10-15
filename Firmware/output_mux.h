#ifndef OUTPUT_MUX_H
#define OUTPUT_MUX_H

/*
 * Runtime IOMUX flips between GPIO-safe and TIMA0 PWM on the module
 * header's PWM pins (J8):
 *
 *   PA7  PWM_A (J8.5, TIMA0_CCP1) -> laser module: laser switch gate / EN.
 *                                   GPIO LOW guarantees "off" at any time.
 *   PA12 PWM_B (J8.4, TIMA0_CCP3) -> laser module: dummy switch gate / CATH.
 *                                   GPIO HIGH keeps the dummy path on.
 *
 * TIMA0 init lives in pwm_timer.c.  Both functions are idempotent and are
 * called on every state-machine tick.
 */

void laser_pins_to_gpio_safe(void);
void laser_pins_to_pwm(void);

#endif /* OUTPUT_MUX_H */
