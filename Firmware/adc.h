#ifndef ADC_H
#define ADC_H

#include <stdbool.h>
#include <stdint.h>
#include "board.h"

/*
 * ADC register-level driver — the laser's two readbacks.  The instance and
 * channels come from the board header (BOARD_HAS_LASER boards only):
 *
 *   board  | instance | photodiode (pd)        | LASER_V divider (comp)
 *   -------+----------+------------------------+-------------------------
 *   rev2   | ADC1     | ch 2 = PA17 (J9.4)     | ch 8 (PA22 = J9.5 is really
 *          |          |                        | A0_7: see board_rev2.h)
 *   laser  | ADC0     | ch 1 = PA26 (DB_ADC_A) | ch 0 = PA27 (DB_ADC_B)
 *
 * comp = LASER_V through 100 k / 33 k: 12 V -> 2.98 V, 5 V -> 1.24 V.
 *
 * 12-bit, VDDA reference, software-triggered two-channel sequence
 * (MEMCTL0 = pd channel, MEMCTL1 = comp channel), SYSOSC / 8 = 4 MHz
 * sample clock.  Both pins stay at their IOMUX reset default (no digital
 * function) so the analog path is connected; on Rev 2 in e-stim mode they
 * are I2C GPIOs and the ADC must not be started (module.c owns the pins).
 *
 * Usage from the 1 kHz housekeeping loop: laser_adc_start() one tick,
 * laser_adc_read() the next (a conversion pair takes ~30 µs).
 */

#if BOARD_HAS_LASER
void laser_adc_init(void);
void laser_adc_start(void);
/* true and *pd / *comp filled when the last sequence has completed. */
bool laser_adc_read(uint16_t *pd, uint16_t *comp);
#endif /* BOARD_HAS_LASER */

#endif /* ADC_H */
