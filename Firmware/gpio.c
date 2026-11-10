#include "gpio.h"
#include "board.h"
#include "mcu.h"

/* Spare pins (no copper on the HAT): defined output-low state. */
static const uint8_t kSparePincm[] = { BOARD_SPARE_PINCMS };

#define PINCM_GPIO_OUT   (IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_PF_GPIO)
#define PINCM_GPIO_IN    (IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_INENA_ENABLE | \
                          IOMUX_PINCM_PF_GPIO)
#define PINCM_GPIO_IN_PU (PINCM_GPIO_IN | IOMUX_PINCM_PIPU_ENABLE)
#define PINCM_GPIO_IN_PD (PINCM_GPIO_IN | IOMUX_PINCM_PIPD_ENABLE)

/* GPIO interrupt polarity: 2 bits per DIO, 01 = rising edge, 10 = falling,
 * split over two registers at bit 16: DIO0..15 in POLARITY15_0, DIO16..31
 * in POLARITY31_16 (field = bit - 16).  (The GPIO CPU_INT.IIDX would give
 * DIO + 1 of the highest-priority pending pin; GROUP1_IRQHandler reads MIS
 * instead, so it handles every pending pin in one pass.) */
#define POL_RISE                0x1u
#define POL_FALL                0x2u

static void gpio_set_polarity(uint32_t bit, uint32_t pol)
{
    if (bit < 16u) {
        uint32_t sh = 2u * bit;
        BOARD_GPIO_PORT->POLARITY15_0 =
            (BOARD_GPIO_PORT->POLARITY15_0 & ~(0x3u << sh)) | (pol << sh);
    } else {
        uint32_t sh = 2u * (bit - 16u);
        BOARD_GPIO_PORT->POLARITY31_16 =
            (BOARD_GPIO_PORT->POLARITY31_16 & ~(0x3u << sh)) | (pol << sh);
    }
}

void laser_gpio_enable_power_and_reset(void)
{
    GPIOA->GPRCM.RSTCTL =
        (GPIO_RSTCTL_KEY_UNLOCK_W | GPIO_RSTCTL_RESETSTKYCLR_CLR |
         GPIO_RSTCTL_RESETASSERT_ASSERT);
    GPIOA->GPRCM.PWREN =
        (GPIO_PWREN_KEY_UNLOCK_W | GPIO_PWREN_ENABLE_ENABLE);
}

void laser_gpio_init(void)
{
    /* ----- Spare pins: driven LOW outputs ----- */
    for (unsigned i = 0; i < sizeof(kSparePincm) / sizeof(kSparePincm[0]); i++) {
        IOMUX->SECCFG.PINCM[kSparePincm[i]] = PINCM_GPIO_OUT;
    }

    /* ----- UART1 (Pi) and UART0 (USB-C) peripheral functions ----- */
    IOMUX->SECCFG.PINCM[BOARD_PI_UART_TX_PINCM] =
        BOARD_PI_UART_TX_FUNC | IOMUX_PINCM_PC_CONNECTED;
    IOMUX->SECCFG.PINCM[BOARD_PI_UART_RX_PINCM] =
        BOARD_PI_UART_RX_FUNC | IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_INENA_ENABLE;
    IOMUX->SECCFG.PINCM[BOARD_USB_UART_TX_PINCM] =
        BOARD_USB_UART_TX_FUNC | IOMUX_PINCM_PC_CONNECTED;
    IOMUX->SECCFG.PINCM[BOARD_USB_UART_RX_PINCM] =
        BOARD_USB_UART_RX_FUNC | IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_INENA_ENABLE;

    /* ----- Switch lines A / B: GPIO outputs, no pulls (laser boards switch
     * them to TIMA0 at runtime; StimHAT EN_H / CATH_H stay GPIO) ----- */
    IOMUX->SECCFG.PINCM[BOARD_PWM_A_PINCM] = PINCM_GPIO_OUT;
    IOMUX->SECCFG.PINCM[BOARD_PWM_B_PINCM] = PINCM_GPIO_OUT;

#if BOARD_HAS_FAULT_PIN
    /* ----- FAULT_n: input (pull-up on Rev 2, where the laser module leaves
     * it open; none on the StimHAT, where the ISO7741 drives it), falling
     * edge selected now, interrupt masked until the line has been high ----- */
    IOMUX->SECCFG.PINCM[BOARD_FAULT_N_PINCM] =
        BOARD_FAULT_N_PULLUP ? PINCM_GPIO_IN_PU : PINCM_GPIO_IN;
    gpio_set_polarity(BOARD_FAULT_N_BIT, POL_FALL);
#endif

    /* ----- BUTTON1..5 (+6): inputs with pull-up (pressed = LOW) ----- */
    IOMUX->SECCFG.PINCM[BOARD_BUTTON1_PINCM] = PINCM_GPIO_IN_PU;
    IOMUX->SECCFG.PINCM[BOARD_BUTTON2_PINCM] = PINCM_GPIO_IN_PU;
    IOMUX->SECCFG.PINCM[BOARD_BUTTON3_PINCM] = PINCM_GPIO_IN_PU;
    IOMUX->SECCFG.PINCM[BOARD_BUTTON4_PINCM] = PINCM_GPIO_IN_PU;
    IOMUX->SECCFG.PINCM[BOARD_BUTTON5_PINCM] = PINCM_GPIO_IN_PU;
#if BOARD_HAS_BUTTON6
    IOMUX->SECCFG.PINCM[BOARD_BUTTON6_PINCM] = PINCM_GPIO_IN_PU;
#endif

    /* ----- BSL switch SW6 (PA18): input with pull-down (pressed = HIGH) ----- */
    IOMUX->SECCFG.PINCM[BOARD_BSL_PINCM] = PINCM_GPIO_IN_PD;

    /* ----- LED and STIM_OUT: outputs ----- */
    IOMUX->SECCFG.PINCM[BOARD_LED_PINCM]      = PINCM_GPIO_OUT;
    IOMUX->SECCFG.PINCM[BOARD_STIM_OUT_PINCM] = PINCM_GPIO_OUT;

    /* ----- STIM_IN (BNC via U8) and PI_TRIGGER (Pi GPIO): inputs ----- */
    /* Pull-downs so an undriven line idles LOW: U8 normally drives
     * STIM_IN, but PI_TRIGGER floats whenever the Pi releases its GPIO
     * (e.g. at Python process exit), and a float-to-high transition would
     * look like a trigger edge. */
    IOMUX->SECCFG.PINCM[BOARD_STIM_IN_PINCM]    = PINCM_GPIO_IN_PD;
    IOMUX->SECCFG.PINCM[BOARD_PI_TRIGGER_PINCM] = PINCM_GPIO_IN_PD;
    gpio_set_polarity(BOARD_STIM_IN_BIT,    POL_RISE);
    gpio_set_polarity(BOARD_PI_TRIGGER_BIT, POL_RISE);
    BOARD_GPIO_PORT->CPU_INT.ICLR  = BOARD_STIM_IN_PIN | BOARD_PI_TRIGGER_PIN;
    BOARD_GPIO_PORT->CPU_INT.IMASK = BOARD_STIM_IN_PIN | BOARD_PI_TRIGGER_PIN;

    /* Pre-load DOUT before enabling output direction so each pin drives
     * the right level on the same cycle the output enable lands.
     *   PWM_A    = 0   (laser switch / e-stim EN OFF — safety default)
     *   PWM_B    = BOARD_PWM_B_BOOT_HIGH (laser boards: 1, dummy switch
     *              conducting; StimHAT: 0, CATH low)
     *   LED      = 1   (on for the boot blink)
     *   STIM_OUT = 0
     *   spare    = 0
     */
#if BOARD_PWM_B_BOOT_HIGH
    BOARD_GPIO_PORT->DOUTCLR31_0 =
        BOARD_PWM_A_PIN | BOARD_STIM_OUT_PIN | BOARD_SPARE_PINS;
    BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_PWM_B_PIN | BOARD_LED_PIN;
#else
    BOARD_GPIO_PORT->DOUTCLR31_0 =
        BOARD_PWM_A_PIN | BOARD_PWM_B_PIN | BOARD_STIM_OUT_PIN | BOARD_SPARE_PINS;
    BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_LED_PIN;
#endif
    BOARD_GPIO_PORT->DOESET31_0  =
        BOARD_PWM_A_PIN | BOARD_PWM_B_PIN | BOARD_LED_PIN |
        BOARD_STIM_OUT_PIN | BOARD_SPARE_PINS;
}
