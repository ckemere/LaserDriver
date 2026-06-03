#ifndef LASER_PWM_CONTROL_H
#define LASER_PWM_CONTROL_H

/*
 * Runtime IOMUX flips between GPIO-safe and TIMA0 PWM on the bridge
 * pins:
 *
 *   PA21 -> Q2a laser path: GPIO LOW guarantees laser off at any time.
 *   PA22 -> Q2b dummy path: GPIO HIGH keeps a current path when laser is off.
 *
 * TIMA0 peripheral init now lives in laser_timera.c.  Both pin-mux
 * functions are safe to call on every state-machine tick (idempotent).
 */

void laser_pins_to_gpio_safe(void);
void laser_pins_to_pwm(void);

#endif /* LASER_PWM_CONTROL_H */
