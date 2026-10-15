#ifndef ADC_H
#define ADC_H

#include <stdbool.h>
#include <stdint.h>

/*
 * ADC1 register-level driver — the laser module's two readbacks on J9:
 *
 *   ADC1.2 (PA17, J9.4)  photodiode (PD load per the module's J4 jumper)
 *   ADC1.8 (PA22, J9.5)  compliance rail LASER_V through R1/R2 (100 k / 33 k):
 *                        12 V -> 2.98 V, 5 V -> 1.24 V
 *
 * 12-bit, VDDA reference, software-triggered two-channel sequence
 * (MEMCTL0 = channel 2, MEMCTL1 = channel 8), SYSOSC / 8 = 4 MHz sample
 * clock.  Both pins stay at their IOMUX reset default (no digital function)
 * so the analog path is connected; in e-stim mode they are I2C GPIOs and
 * the ADC must not be started (module.c owns the pins).
 *
 * Usage from the 1 kHz housekeeping loop: laser_adc_start() one tick,
 * laser_adc_read() the next (a conversion pair takes ~30 µs).
 */

void laser_adc_init(void);
void laser_adc_start(void);
/* true and *pd / *comp filled when the last sequence has completed. */
bool laser_adc_read(uint16_t *pd, uint16_t *comp);

#endif /* ADC_H */
