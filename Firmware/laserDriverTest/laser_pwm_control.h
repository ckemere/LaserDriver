#ifndef LASER_PWM_CONTROL_H
#define LASER_PWM_CONTROL_H

/*
 * Bridge-pin mux switching between GPIO safe-state and TIMA0 PWM.
 *
 * PA8  (PINCM19) -> Q2b dummy path:  GPIO HIGH keeps a current path when laser is off.
 * PA22 (PINCM47) -> Q2a laser path:  GPIO LOW  guarantees laser off at any time.
 *
 * Call laser_pins_to_gpio_safe() whenever the laser should be off.
 * Call laser_pins_to_pwm()       just before driving set_laser_step().
 * Both functions are safe to call on every state-machine tick (idempotent).
 */

void laser_pins_to_gpio_safe(void);
void laser_pins_to_pwm(void);

#endif /* LASER_PWM_CONTROL_H */
