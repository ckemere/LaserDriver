#ifndef GPIO_H
#define GPIO_H

#include <stdint.h>
#include <stdbool.h>
#include "mcu.h"
#include "board.h"

/*
 * GPIO + IOMUX register-level init for the Rev 2 HAT (see board.h):
 *
 *   - spare pins PA3..PA5 driven low
 *   - UART1 (Pi) and UART0 (USB-C) pins muxed to their peripherals
 *   - module PWM pins PA7 (A) / PA12 (B) as GPIO outputs, A low / B high
 *     (laser switch off, dummy switch on); the TIMA0 mux is flipped at
 *     runtime by output_mux.c
 *   - FAULT_n (PA6) input with pull-up
 *   - BUTTON1..5 inputs with pull-ups (active low); BSL (PA18) input with
 *     pull-down (active high)
 *   - LED (PA24) output, on for the boot blink; STIM_OUT (PA25) output low
 *   - STIM_IN (PA26) and PI_TRIGGER (PA27) inputs with rising-edge IRQ
 *
 * PA0/PA1 (Pi I2C), PA2 (ROSC), PA15/PA17/PA22 (module analog lines) and
 * PA19/PA20 (SWD) are deliberately left at their reset default.
 *
 * laser_gpio_enable_power_and_reset() resets the GPIOA peripheral and
 * enables its bus clock — call before laser_gpio_init().
 */

void laser_gpio_enable_power_and_reset(void);
void laser_gpio_init(void);

/* Raw button mask, 1 = pressed:
 *   bit 0 BUTTON1 BACK, bit 1 BUTTON2 SELECT (wheel push), bit 2 BUTTON3
 *   (wheel roll D), bit 3 BUTTON4 (wheel roll B), bit 4 BUTTON5 FIRE,
 *   bit 5 BSL switch SW6 (active high, for bring-up only). */
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
    return m;
}

/* FAULT_n (J8.3) level: true = no fault / module absent (pull-up). */
static inline bool laser_gpio_fault_n_high(void)
{
    return (BOARD_GPIO_PORT->DIN31_0 & BOARD_FAULT_N_PIN) != 0u;
}

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
