#include "laser_pwm_control.h"
#include "board.h"
#include <ti/devices/msp/msp.h>

/*
 * Runtime IOMUX switching between GPIO-safe and TIMA0_CCP0 / CCP0_CMPL
 * on the bridge pins.  Timer init lives in laser_timera.c; this file
 * only owns the per-pulse mux flips.
 */

/*
 * Switch bridge pins to GPIO and lock them to safe output values.
 * (CRITICAL — SAFE OUTPUT IS LASER OFF.)
 *
 * Sequence:
 *   1. Pre-load DOUT before touching IOMUX so each pin drives the right
 *      level the instant it switches to GPIO.
 *   2. Switch PA21 (laser, CCP0) to GPIO first so the laser path is
 *      defined LOW while PA22 is still PWM-complemented.
 *   3. Switch PA22 (dummy, CCP0_CMPL) to GPIO HIGH last.
 */
void laser_pins_to_gpio_safe(void)
{
    BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_PWM_LASER_PIN;   /* PA21 = 0 */
    BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_PWM_DUMMY_PIN;   /* PA22 = 1 */

    IOMUX->SECCFG.PINCM[BOARD_PWM_LASER_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | BOARD_PWM_LASER_GPIO_FUNC;
    IOMUX->SECCFG.PINCM[BOARD_PWM_DUMMY_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | BOARD_PWM_DUMMY_GPIO_FUNC;
}

/*
 * Switch bridge pins to TIMA0 peripheral function.
 *
 * Sequence:
 *   1. Switch PA22 (dummy, CCP0_CMPL) first — complement output drives
 *      while the laser pin is still GPIO-HIGH, maintaining current path.
 *   2. Switch PA21 (laser, CCP0) second — laser now follows PWM.
 */
void laser_pins_to_pwm(void)
{
    IOMUX->SECCFG.PINCM[BOARD_PWM_DUMMY_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | BOARD_PWM_DUMMY_PWM_FUNC;
    IOMUX->SECCFG.PINCM[BOARD_PWM_LASER_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | BOARD_PWM_LASER_PWM_FUNC;
}
