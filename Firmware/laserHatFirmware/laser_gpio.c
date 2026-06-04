#include "laser_gpio.h"
#include "board.h"
#include "mcu.h"

/*
 * PINCM indices for every pin not otherwise claimed by the application.
 * SysConfig generates the equivalent list; mirrored here so the unused
 * pins still get put into a defined output-low state instead of
 * floating inputs.
 */
static const uint8_t kUnusedPincm[] = {
    IOMUX_PINCM1,  IOMUX_PINCM2,  IOMUX_PINCM7,  IOMUX_PINCM14,
    IOMUX_PINCM19, IOMUX_PINCM20, IOMUX_PINCM34,
    IOMUX_PINCM38, IOMUX_PINCM39, IOMUX_PINCM40, IOMUX_PINCM54,
    IOMUX_PINCM55, IOMUX_PINCM59, IOMUX_PINCM60,
};

/* Matching pin bit masks for the DOUT and DOE registers.
 * PA4..PA6 (BUTTON2..4) and PA14 (BNC trigger) are now used. */
#define UNUSED_PIN_MASK \
    ((1u << 0)  | (1u << 1)  | (1u << 2)  | (1u << 7)  | \
     (1u << 8)  | (1u << 9)  | (1u << 12) | \
     (1u << 16) | (1u << 17) | (1u << 18) | (1u << 24) | \
     (1u << 25) | (1u << 26) | (1u << 27))

/* IOMUX function code 1 is "GPIO" on every PINCM. */
#define PINCM_FUNC_GPIO         ((uint32_t) 0x00000001u)

void laser_gpio_enable_power_and_reset(void)
{
    /* RSTCTL: pulse the peripheral reset bit, then release. */
    GPIOA->GPRCM.RSTCTL =
        (GPIO_RSTCTL_KEY_UNLOCK_W | GPIO_RSTCTL_RESETSTKYCLR_CLR |
         GPIO_RSTCTL_RESETASSERT_ASSERT);

    /* Enable the GPIOA peripheral bus clock. */
    GPIOA->GPRCM.PWREN =
        (GPIO_PWREN_KEY_UNLOCK_W | GPIO_PWREN_ENABLE_ENABLE);
}

void laser_gpio_init(void)
{
    /* ----- Unused pins: driven LOW outputs ----- */
    for (unsigned i = 0; i < sizeof(kUnusedPincm) / sizeof(kUnusedPincm[0]); i++) {
        IOMUX->SECCFG.PINCM[kUnusedPincm[i]] =
            IOMUX_PINCM_PC_CONNECTED | PINCM_FUNC_GPIO;
    }
    BOARD_GPIO_PORT->DOUTCLR31_0 = UNUSED_PIN_MASK;
    BOARD_GPIO_PORT->DOESET31_0  = UNUSED_PIN_MASK;

    /* ----- UART0 TX/RX peripheral functions ----- */
    IOMUX->SECCFG.PINCM[BOARD_UART_TX_PINCM] =
        BOARD_UART_TX_FUNC | IOMUX_PINCM_PC_CONNECTED;
    IOMUX->SECCFG.PINCM[BOARD_UART_RX_PINCM] =
        BOARD_UART_RX_FUNC | IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_INENA_ENABLE;

    /* ----- Bridge pins (digital outputs; PWM mux switched at runtime) ----- */
    IOMUX->SECCFG.PINCM[BOARD_PWM_LASER_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | PINCM_FUNC_GPIO;
    IOMUX->SECCFG.PINCM[BOARD_PWM_DUMMY_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | PINCM_FUNC_GPIO;

    /* ----- BUTTON1..4: digital inputs with internal pull-down ----- */
    const uint32_t button_pincm_cfg =
        IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_INENA_ENABLE |
        IOMUX_PINCM_PIPD_ENABLE  | PINCM_FUNC_GPIO;
    IOMUX->SECCFG.PINCM[BOARD_BUTTON1_PINCM] = button_pincm_cfg;
    IOMUX->SECCFG.PINCM[BOARD_BUTTON2_PINCM] = button_pincm_cfg;
    IOMUX->SECCFG.PINCM[BOARD_BUTTON3_PINCM] = button_pincm_cfg;
    IOMUX->SECCFG.PINCM[BOARD_BUTTON4_PINCM] = button_pincm_cfg;

    /* ----- STIM_MIRROR LED: digital output ----- */
    IOMUX->SECCFG.PINCM[BOARD_STIM_MIRROR_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | PINCM_FUNC_GPIO;

    /* ----- BNC trigger: digital input, rising-edge interrupt ----- */
    /* Enable the internal pull-DOWN so a released/unterminated line idles
     * LOW instead of floating; otherwise noise on an open BNC can look
     * like a rising edge and fire the laser.  Active-high, matching the
     * Pi-trigger input (PA19) armed in laser_gpio_arm_pi_trigger(). */
    IOMUX->SECCFG.PINCM[BOARD_BNC_TRIGGER_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_INENA_ENABLE |
        IOMUX_PINCM_PIPD_ENABLE  | PINCM_FUNC_GPIO;
    /* POLARITY15_0: each DIO gets a 2-bit field (RISE=01).  PA14 → bits 28-29. */
    BOARD_GPIO_PORT->POLARITY15_0 =
        (BOARD_GPIO_PORT->POLARITY15_0 & ~(0x3u << 28)) | (0x1u << 28);
    /* Clear any latched interrupt, then unmask PA14 at the GPIOA peripheral.
     * The Pi-trigger input (PA19) gets added to IMASK later by
     * laser_gpio_arm_pi_trigger() once boot is past the SWD-needed window. */
    BOARD_GPIO_PORT->CPU_INT.ICLR  = BOARD_BNC_TRIGGER_PIN;
    BOARD_GPIO_PORT->CPU_INT.IMASK = BOARD_BNC_TRIGGER_PIN;

    /* Pre-load DOUT before enabling output direction so each pin drives
     * the right level on the same cycle the output enable lands.
     *   PA21 = 0   (laser path OFF, critical safety default)
     *   PA22 = 1   (dummy current path conducting)
     *   PA13 = 1   (STIM_MIRROR LED on for boot-blink phase)
     */
    BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_PWM_LASER_PIN;
    BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_PWM_DUMMY_PIN | BOARD_STIM_MIRROR_PIN;
    BOARD_GPIO_PORT->DOESET31_0  =
        BOARD_PWM_LASER_PIN | BOARD_PWM_DUMMY_PIN | BOARD_STIM_MIRROR_PIN;
}

void laser_gpio_arm_pi_trigger(void)
{
    /* Switch PA19's PINCM from boot-default SWDIO to plain GPIO input.
     * Function code 1 = GPIO.  Enable INENA so we can read the level,
     * and enable the internal pull-DOWN so the line idles LOW when the
     * Pi releases GPIO 24 (e.g. at Python process exit).  Without this,
     * gpiozero closing the line lets it float and the input transition
     * looks like a rising edge to our ISR -> spurious pulse fires. */
    IOMUX->SECCFG.PINCM[BOARD_PI_TRIGGER_PINCM] =
        IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_INENA_ENABLE |
        IOMUX_PINCM_PIPD_ENABLE  | BOARD_PI_TRIGGER_GPIO_FUNC;

    /* POLARITY31_16: each DIO again gets a 2-bit field (RISE=01).
     * PA19 sits at index 19, so within the upper-half register that's
     * (19-16) * 2 = bits 6-7. */
    BOARD_GPIO_PORT->POLARITY31_16 =
        (BOARD_GPIO_PORT->POLARITY31_16 & ~(0x3u << 6)) | (0x1u << 6);

    /* Clear any latched edge, then OR PA19 into the existing IMASK so
     * the BNC trigger's mask isn't disturbed. */
    BOARD_GPIO_PORT->CPU_INT.ICLR  = BOARD_PI_TRIGGER_PIN;
    BOARD_GPIO_PORT->CPU_INT.IMASK |= BOARD_PI_TRIGGER_PIN;
}
