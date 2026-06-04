#ifndef LASER_GPIO_H
#define LASER_GPIO_H

#include <stdint.h>

/*
 * GPIO + IOMUX register-level init.  Replaces SYSCFG_DL_GPIO_init():
 *
 *   - Unused pins driven low (defined, low-power state)
 *   - UART0 TX/RX pins muxed to UART0 function
 *   - Bridge pins PA21/PA22 configured as digital outputs
 *     (PA21 cleared = laser off, PA22 set = dummy path active)
 *   - BUTTON1..4 (PA3..PA6) configured as inputs with internal pull-down
 *     (matches the schematic: SW pin 2 -> +3V3, so press = HIGH)
 *   - STIM_MIRROR LED (PA13) configured as digital output, initial HIGH
 *
 * laser_gpio_enable_power_and_reset() resets the GPIOA peripheral and
 * enables its bus clock — call before laser_gpio_init().  Both are
 * normally subsumed into the board boot sequence.
 */

void laser_gpio_enable_power_and_reset(void);
void laser_gpio_init(void);

/*
 * Reclaim PA19 from SWDIO to a plain GPIO input + rising-edge interrupt.
 * Called from main() AFTER the boot blink completes, so the SWD pin
 * stays live long enough to flash this very firmware.  NRST always
 * restores SWDIO at reset, so future re-flashes still work.
 */
void laser_gpio_arm_pi_trigger(void);

/* Tiny inlines so the hot-path button read in laser_driver.c doesn't
 * need driverlib either.  All return 0 or a bit mask. */
#include "mcu.h"
#include "board.h"

static inline uint32_t laser_gpio_read_button1(void)
{
    return BOARD_GPIO_PORT->DIN31_0 & BOARD_BUTTON1_PIN;
}

/* Returns a 4-bit raw mask: bit 0 = B1, bit 1 = B2, bit 2 = B3, bit 3 = B4.
 * Each bit is 1 if the corresponding button reads HIGH (pressed). */
static inline uint8_t laser_gpio_read_buttons_raw(void)
{
    uint32_t din = BOARD_GPIO_PORT->DIN31_0;
    return (uint8_t)(((din >> 3) & 0x0Fu));  /* PA3..PA6 -> bits 0..3 */
}

static inline void laser_gpio_stim_mirror_set(void)
{
    BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_STIM_MIRROR_PIN;
}

static inline void laser_gpio_stim_mirror_clear(void)
{
    BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_STIM_MIRROR_PIN;
}

#endif /* LASER_GPIO_H */
