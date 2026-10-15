#ifndef MODULE_H
#define MODULE_H

#include <stdbool.h>
#include <stdint.h>
#include "mcu.h"
#include "board.h"

/*
 * Module-side handling of the J9 lines, whose role follows the mode:
 *
 *   mode  | PA15 (J9.3)           | PA17 (J9.4)          | PA22 (J9.5)
 *   ------+-----------------------+----------------------+---------------------
 *   LASER | DAC0_OUT, IREF        | ADC1.2 photodiode    | ADC1.8 compliance
 *   ESTIM | RELEASE, push-pull    | I2C SDA, open-drain  | I2C SCL, open-drain
 *
 * E-stim contract (estim_interface/ESTIM_MODULE_SPEC.md §7): the DAC60501
 * (I2C 0x48) behind the ISO1640 gets GAIN 0x04 = 0x0100 once after the
 * isolated side is up (FAULT_n high + 250 µs), then DAC 0x08 = code << 4
 * between trains.  The I2C is bit-banged here (PA17 only muxes I2C1_SCL,
 * PA22 has no I2C function) at ~200 kHz from the main loop; the 100 kHz
 * tick ISR may interrupt a bit, which only stretches it.
 *
 * module_laser_pins() / module_estim_pins() switch the IOMUX; the hot-path
 * RELEASE inlines are for the tick ISR.
 */

void module_laser_pins(void);     /* PA15/PA17/PA22 -> analog (reset default) */
void module_estim_pins(void);     /* PA15 GPIO out low, PA17/PA22 open-drain released */

static inline void module_release_set(void)
{
    BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_ESTIM_RELEASE_PIN;
}

static inline void module_release_clear(void)
{
    BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_ESTIM_RELEASE_PIN;
}

/* DAC60501 over the bit-banged bus.  Each returns true when every byte was
 * acknowledged.  Main-loop only, and only between trains. */
bool module_estim_dac_init(void);              /* GAIN register: REF-DIV 1, gain 1 */
bool module_estim_dac_write(uint16_t code12);  /* DAC register: code << 4 */

#endif /* MODULE_H */
