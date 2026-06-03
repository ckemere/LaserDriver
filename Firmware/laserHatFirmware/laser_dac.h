#ifndef LASER_DAC_H
#define LASER_DAC_H

#include <stdint.h>
#include <ti/devices/msp/msp.h>

/*
 * DAC0 + internal VREF register-level driver.
 *
 * VREF is configured to drive its 2.5 V buffered output, sourced from
 * LFCLK with no sample-and-hold. DAC0 references VEREFP/VEREFN, 12-bit
 * binary, output amplifier on, FIFO and sample-timer disabled.
 *
 * After laser_dac_init() the DAC output stage is ready; call
 * laser_dac_write12() with the desired code and then laser_dac_enable().
 */

void laser_dac_init(void);
void laser_dac_enable(void);

static inline void laser_dac_write12(uint16_t code)
{
    /* DATA0 takes a 12-bit value masked at the peripheral. */
    DAC0->DATA0 = (uint32_t) code & DAC12_DATA0_DATA_VALUE_MASK;
}

#endif /* LASER_DAC_H */
