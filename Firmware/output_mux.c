#include "output_mux.h"
#include "board.h"
#include "mcu.h"
#include <stdbool.h>

/* Idle level of PWM_B: HIGH for the laser (dummy switch on), LOW for
 * e-stim (CATH = anodic, nothing flows while EN is low).  Starts at the
 * level gpio init set; enter_mode() sets it for the mode. */
static volatile bool g_b_idle_high = (BOARD_PWM_B_BOOT_HIGH != 0);

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
 *   2. Switch A (CCP1) to GPIO first so the laser path is defined LOW
 *      while B is still the PWM complement.
 *   3. Switch B (CCP3) to GPIO (HIGH in laser mode) last.
 * On the StimHAT both lines are always GPIO (EN_H / CATH_H, no pulls:
 * PC_CONNECTED | GPIO only, the 10k pull-downs on the board stay in charge
 * whenever the pins are not driven).
 */
void laser_pins_to_gpio_safe(void)
{
    BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_PWM_A_PIN;       /* A = 0 */
    if (g_b_idle_high) {
        BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_PWM_B_PIN;   /* B = 1 */
    } else {
        BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_PWM_B_PIN;   /* B = 0 */
    }

    IOMUX->SECCFG.PINCM[BOARD_PWM_A_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_PF_GPIO;
    IOMUX->SECCFG.PINCM[BOARD_PWM_B_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_PF_GPIO;
}

#if BOARD_HAS_LASER
/*
 * Switch the PWM pins to TIMA0: B (complement) first so a current path
 * exists while A is still GPIO-LOW, then A follows the PWM.
 */
void laser_pins_to_pwm(void)
{
    IOMUX->SECCFG.PINCM[BOARD_PWM_B_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | BOARD_PWM_B_PWM_FUNC;
    IOMUX->SECCFG.PINCM[BOARD_PWM_A_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | BOARD_PWM_A_PWM_FUNC;
}
#endif
