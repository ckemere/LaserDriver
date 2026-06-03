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
 *   - BUTTON1 (PA3) configured as input with internal pull-down
 *     (matches the schematic: SW1 pin 2 -> +3V3, so press = HIGH)
 *   - STIM_MIRROR LED (PA13) configured as digital output, initial HIGH
 *
 * laser_gpio_enable_power_and_reset() resets the GPIOA peripheral and
 * enables its bus clock — call before laser_gpio_init().  Both are
 * normally subsumed into the board boot sequence.
 */

void laser_gpio_enable_power_and_reset(void);
void laser_gpio_init(void);

/* Tiny inlines so the hot-path button read in laser_driver.c doesn't
 * need driverlib either.  All return 0 or a bit mask. */
#include <ti/devices/msp/msp.h>
#include "board.h"

static inline uint32_t laser_gpio_read_button1(void)
{
    return BOARD_GPIO_PORT->DIN31_0 & BOARD_BUTTON1_PIN;
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
