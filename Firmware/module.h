#ifndef MODULE_H
#define MODULE_H

#include <stdbool.h>
#include <stdint.h>
#include "mcu.h"
#include "board.h"

/*
 * The laser / e-stim lines besides the two switch lines, per board:
 *
 *   Rev 2 (J9, the role follows the mode):
 *     mode  | PA15 (J9.3)       | PA17 (J9.4)          | PA22 (J9.5)
 *     ------+-------------------+----------------------+---------------------
 *     LASER | DAC0_OUT, IREF    | ADC1 ch 2 photodiode | compliance (see
 *           |                   |                      | board_rev2.h)
 *     ESTIM | RELEASE, push-pull| I2C SDA, open-drain  | I2C SCL, open-drain
 *
 *   StimHAT (ESTIM only, through U101 ISO7741 / U109 ISO1640):
 *     RELEASE_H PA25 push-pull, SDA_H PA26 / SCL_H PA27 open-drain with
 *     2.2k pull-ups on the HAT side (no internal pull-ups).
 *
 *   LaserDriverHAT (LASER only): DAC0_OUT PA15, ADC0 ch 1 PA26, ch 0 PA27,
 *     all analog (reset default).
 *
 * E-stim contract (estim_interface/ESTIM_MODULE_SPEC.md §7): the DAC60501
 * (I2C 0x48) behind the ISO1640 gets GAIN 0x04 = 0x0100 once after the
 * isolated side is up (FAULT_n high + 250 µs), then DAC 0x08 = code << 4
 * between trains.  The I2C is bit-banged here (none of the SDA/SCL pin
 * pairs muxes a matching I2C SDA/SCL) at ~200 kHz from the main loop; the
 * 100 kHz tick ISR may interrupt a bit, which only stretches it.  ACK and
 * the START bus check read SDA back, which works through the ISO1640 (its
 * side-1 low level is well below the MSPM0's VIL).
 *
 * module_laser_pins() / module_estim_pins() switch the IOMUX; the hot-path
 * RELEASE inlines are for the tick ISR.
 */

#if BOARD_HAS_LASER
void module_laser_pins(void);     /* DAC / ADC pins -> analog (reset default) */
#endif

#if BOARD_HAS_ESTIM
void module_estim_pins(void);     /* RELEASE GPIO out low, SDA/SCL open-drain released */

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
#endif /* BOARD_HAS_ESTIM */

#endif /* MODULE_H */
