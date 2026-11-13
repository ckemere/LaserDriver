#ifndef GPIO_H
#define GPIO_H

#include <stdint.h>
#include <stdbool.h>
#include "mcu.h"
#include "board.h"

/*
 * GPIO + IOMUX register-level init, pins from the selected board header
 * (board.h -> board_rev2.h / board_stim.h / board_laser.h):
 *
 *   - spare pins (BOARD_SPARE_PINCMS) driven low
 *   - UART1 (Pi) and UART0 (USB-C) pins muxed to their peripherals
 *   - switch lines A / B (laser + dummy switch, or e-stim EN + CATH) as
 *     GPIO outputs, A low, B at BOARD_PWM_B_BOOT_HIGH (dummy switch on for
 *     a laser board, CATH low on the StimHAT); on laser boards the PWM
 *     timer mux is flipped at runtime by output_mux.c
 *   - FAULT_n (BOARD_HAS_FAULT_PIN) input, falling-edge IRQ armed at
 *     runtime (laser_gpio_fault_irq_enable) once the line has been high
 *   - BUTTON1..5 (+ BUTTON6) inputs with pull-ups (active low); BSL (PA18)
 *     input with pull-down (active high)
 *   - LED output, on for the boot blink; STIM_OUT output low
 *   - STIM_IN and PI_TRIGGER inputs with rising-edge IRQ
 *
 * PA0/PA1 (Pi I2C), PA2 (ROSC) and PA19/PA20 (SWD) are deliberately left
 * at their reset default.  The module / e-stim lines (DAC, ADC, RELEASE,
 * SDA, SCL) are owned by module.c and start at their reset default too.
 *
 * laser_gpio_enable_power_and_reset() resets the GPIOA peripheral and
 * enables its bus clock — call before laser_gpio_init().
 */

void laser_gpio_enable_power_and_reset(void);
void laser_gpio_init(void);

/* Raw button mask, 1 = pressed (bit order: protocol.h EVT_BUTTON_BIT_*):
 *   bit 0 BUTTON1 BACK, bit 1 BUTTON2 SELECT, bit 2 BUTTON3, bit 3
 *   BUTTON4, bit 4 BUTTON5 FIRE, bit 5 BSL switch SW6 (active high, for
 *   bring-up only), bit 6 BUTTON6 (StimHAT / LaserDriverHAT only). */
static inline uint8_t laser_gpio_read_buttons_raw(void)
{
    uint32_t din = BOARD_GPIO_PORT->DIN31_0;
    uint8_t  m   = 0u;
    if (!(din & BOARD_BUTTON1_PIN)) { m |= 0x01u; }
    if (!(din & BOARD_BUTTON2_PIN)) { m |= 0x02u; }
    if (!(din & BOARD_BUTTON3_PIN)) { m |= 0x04u; }
    if (!(din & BOARD_BUTTON4_PIN)) { m |= 0x08u; }
    if (!(din & BOARD_BUTTON5_PIN)) { m |= 0x10u; }
    if (  din & BOARD_BSL_PIN     )  { m |= 0x20u; }
#if BOARD_HAS_BUTTON6
    if (!(din & BOARD_BUTTON6_PIN)) { m |= 0x40u; }
#endif
    return m;
}

#if BOARD_HAS_FAULT_PIN
/* FAULT_n level: true = no fault (or, Rev 2, module absent: pull-up). */
static inline bool laser_gpio_fault_n_high(void)
{
    return (BOARD_GPIO_PORT->DIN31_0 & BOARD_FAULT_N_PIN) != 0u;
}

/* FAULT_n falling-edge interrupt (shares the GROUP1 vector with the two
 * trigger inputs).  Enable only once FAULT_n has been high (module ready)
 * so an unpowered e-stim side at boot does not count as a fault. */
static inline void laser_gpio_fault_irq_enable(void)
{
    BOARD_GPIO_PORT->CPU_INT.ICLR   = BOARD_FAULT_N_PIN;
    BOARD_GPIO_PORT->CPU_INT.IMASK |= BOARD_FAULT_N_PIN;
}

static inline void laser_gpio_fault_irq_disable(void)
{
    BOARD_GPIO_PORT->CPU_INT.IMASK &= ~BOARD_FAULT_N_PIN;
    BOARD_GPIO_PORT->CPU_INT.ICLR   = BOARD_FAULT_N_PIN;
}
#else
/* No fault line on this board (LaserDriverHAT): never a fault, the
 * interrupt does not exist. */
static inline bool laser_gpio_fault_n_high(void)      { return true; }
static inline void laser_gpio_fault_irq_enable(void)  { }
static inline void laser_gpio_fault_irq_disable(void) { }
#endif

#if BOARD_HAS_ESTIM
/* E-stim EN / CATH as plain GPIO edges — valid only while the pins are in
 * their GPIO (not PWM timer) mux, which is always the case in ESTIM mode. */
static inline void laser_gpio_estim_en_set(void)    { BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_ESTIM_EN_PIN; }
static inline void laser_gpio_estim_en_clear(void)  { BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_ESTIM_EN_PIN; }
static inline void laser_gpio_estim_cath_set(void)  { BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_ESTIM_CATH_PIN; }
static inline void laser_gpio_estim_cath_clear(void){ BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_ESTIM_CATH_PIN; }
#endif

static inline void laser_gpio_led_set(void)
{
    BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_LED_PIN;
}

static inline void laser_gpio_led_clear(void)
{
    BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_LED_PIN;
}

static inline void laser_gpio_stim_out_set(void)
{
    BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_STIM_OUT_PIN;
}

static inline void laser_gpio_stim_out_clear(void)
{
    BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_STIM_OUT_PIN;
}

#endif /* GPIO_H */
