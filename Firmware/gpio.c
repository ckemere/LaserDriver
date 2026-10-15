#include "gpio.h"
#include "board.h"
#include "mcu.h"

/* Spare pins (no copper on the HAT): defined output-low state. */
static const uint8_t kSparePincm[] = {
    IOMUX_PINCM8, IOMUX_PINCM9, IOMUX_PINCM10,          /* PA3..PA5 */
};

#define PINCM_GPIO_OUT   (IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_PF_GPIO)
#define PINCM_GPIO_IN    (IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_INENA_ENABLE | \
                          IOMUX_PINCM_PF_GPIO)
#define PINCM_GPIO_IN_PU (PINCM_GPIO_IN | IOMUX_PINCM_PIPU_ENABLE)
#define PINCM_GPIO_IN_PD (PINCM_GPIO_IN | IOMUX_PINCM_PIPD_ENABLE)

/* GPIO interrupt polarity: 2 bits per DIO, 01 = rising edge. */
#define POL_RISE(dio_in_half)   (0x1u << (2u * (dio_in_half)))
#define POL_MASK(dio_in_half)   (0x3u << (2u * (dio_in_half)))

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

    /* ----- Module PWM pins: GPIO outputs (TIMA0 mux switched at runtime) ----- */
    IOMUX->SECCFG.PINCM[BOARD_PWM_A_PINCM] = PINCM_GPIO_OUT;
    IOMUX->SECCFG.PINCM[BOARD_PWM_B_PINCM] = PINCM_GPIO_OUT;

    /* ----- FAULT_n: input with pull-up (open on the laser module) ----- */
    IOMUX->SECCFG.PINCM[BOARD_FAULT_N_PINCM] = PINCM_GPIO_IN_PU;

    /* ----- BUTTON1..5: inputs with pull-up (pressed = LOW) ----- */
    IOMUX->SECCFG.PINCM[BOARD_BUTTON1_PINCM] = PINCM_GPIO_IN_PU;
    IOMUX->SECCFG.PINCM[BOARD_BUTTON2_PINCM] = PINCM_GPIO_IN_PU;
    IOMUX->SECCFG.PINCM[BOARD_BUTTON3_PINCM] = PINCM_GPIO_IN_PU;
    IOMUX->SECCFG.PINCM[BOARD_BUTTON4_PINCM] = PINCM_GPIO_IN_PU;
    IOMUX->SECCFG.PINCM[BOARD_BUTTON5_PINCM] = PINCM_GPIO_IN_PU;

    /* ----- BSL switch SW6 (PA18): input with pull-down (pressed = HIGH) ----- */
    IOMUX->SECCFG.PINCM[BOARD_BSL_PINCM] = PINCM_GPIO_IN_PD;

    /* ----- LED and STIM_OUT: outputs ----- */
    IOMUX->SECCFG.PINCM[BOARD_LED_PINCM]      = PINCM_GPIO_OUT;
    IOMUX->SECCFG.PINCM[BOARD_STIM_OUT_PINCM] = PINCM_GPIO_OUT;

    /* ----- STIM_IN (BNC via U8) and PI_TRIGGER (Pi GPIO26): inputs ----- */
    /* Pull-downs so an undriven line idles LOW: U8 normally drives PA26,
     * but PA27 floats whenever the Pi releases GPIO26 (e.g. at Python
     * process exit), and a float-to-high transition would look like a
     * trigger edge. */
    IOMUX->SECCFG.PINCM[BOARD_STIM_IN_PINCM]    = PINCM_GPIO_IN_PD;
    IOMUX->SECCFG.PINCM[BOARD_PI_TRIGGER_PINCM] = PINCM_GPIO_IN_PD;
    BOARD_GPIO_PORT->POLARITY31_16 =
        (BOARD_GPIO_PORT->POLARITY31_16 & ~(POL_MASK(26u - 16u) | POL_MASK(27u - 16u)))
        | POL_RISE(26u - 16u) | POL_RISE(27u - 16u);
    BOARD_GPIO_PORT->CPU_INT.ICLR  = BOARD_STIM_IN_PIN | BOARD_PI_TRIGGER_PIN;
    BOARD_GPIO_PORT->CPU_INT.IMASK = BOARD_STIM_IN_PIN | BOARD_PI_TRIGGER_PIN;

    /* Pre-load DOUT before enabling output direction so each pin drives
     * the right level on the same cycle the output enable lands.
     *   PA7  PWM_A = 0   (laser / EN switch OFF — safety default)
     *   PA12 PWM_B = 1   (dummy switch conducting)
     *   PA24 LED   = 1   (on for the boot blink)
     *   PA25 STIM_OUT = 0
     *   PA3..5 spare = 0
     */
    BOARD_GPIO_PORT->DOUTCLR31_0 =
        BOARD_PWM_A_PIN | BOARD_STIM_OUT_PIN | BOARD_SPARE_PINS;
    BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_PWM_B_PIN | BOARD_LED_PIN;
    BOARD_GPIO_PORT->DOESET31_0  =
        BOARD_PWM_A_PIN | BOARD_PWM_B_PIN | BOARD_LED_PIN |
        BOARD_STIM_OUT_PIN | BOARD_SPARE_PINS;
}
