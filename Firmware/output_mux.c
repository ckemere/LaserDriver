#include "output_mux.h"
#include "board.h"
#include "mcu.h"
#include <stdbool.h>

/* Idle level of PWM_B: HIGH for the laser module (dummy switch on), LOW
 * for the e-stim module (CATH = anodic, nothing flows while EN is low). */
static volatile bool g_b_idle_high = true;

void laser_pins_set_b_idle_high(bool high)
{
    g_b_idle_high = high;
}

/*
 * Switch the module PWM pins to GPIO and lock them to safe levels.
 * (CRITICAL — SAFE OUTPUT IS LASER OFF.)
 *
 *   1. Pre-load DOUT so each pin drives the right level the instant it
 *      becomes a GPIO.
 *   2. Switch PA7 (A, CCP1) to GPIO first so the laser path is defined
 *      LOW while PA12 is still the PWM complement.
 *   3. Switch PA12 (B, CCP3) to GPIO (HIGH in laser mode) last.
 */
void laser_pins_to_gpio_safe(void)
{
    BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_PWM_A_PIN;   /* PA7  = 0 */
    if (g_b_idle_high) {
        BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_PWM_B_PIN;   /* PA12 = 1 */
    } else {
        BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_PWM_B_PIN;   /* PA12 = 0 */
    }

    IOMUX->SECCFG.PINCM[BOARD_PWM_A_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_PF_GPIO;
    IOMUX->SECCFG.PINCM[BOARD_PWM_B_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_PF_GPIO;
}

/*
 * Switch the module PWM pins to TIMA0: B (complement) first so a current
 * path exists while A is still GPIO-LOW, then A follows the PWM.
 */
void laser_pins_to_pwm(void)
{
    IOMUX->SECCFG.PINCM[BOARD_PWM_B_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | BOARD_PWM_B_PWM_FUNC;
    IOMUX->SECCFG.PINCM[BOARD_PWM_A_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | BOARD_PWM_A_PWM_FUNC;
}
