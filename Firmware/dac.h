#ifndef DAC_H
#define DAC_H

#include <stdint.h>
#include "mcu.h"

/*
 * DAC0 register-level driver — the laser module's current setpoint on
 * J9.3 (PA15, DAC0_OUT).
 *
 * Reference = VDDA (the MCU's 3.3 V rail), 12-bit binary, output buffer
 * on, FIFO and sample timer off: V_OUT = code / 4096 x 3.3 V.  The laser
 * module divides that by R3/R4 (39 k / 10 k) into IREF across the 2 ohm
 * sense resistor, so I = code x 0.0822 mA (REV2_NOTES "Laser module").
 * VDDA rather than the internal 2.5 V VREF so the full 300 mA design range
 * is reachable (2.5 V would stop at ~255 mA).
 *
 * laser_dac_init() once at boot; laser_dac_enable() / _disable() when the
 * mode changes (PA15 is the e-stim RELEASE GPIO in the other mode, see
 * module.c); laser_dac_write12() any time.
 */

void laser_dac_init(void);
void laser_dac_enable(void);
void laser_dac_disable(void);

static inline void laser_dac_write12(uint16_t code)
{
    /* DATA0 takes a 12-bit value masked at the peripheral. */
    DAC0->DATA0 = (uint32_t) code & DAC12_DATA0_DATA_VALUE_MASK;
}

#endif /* DAC_H */
