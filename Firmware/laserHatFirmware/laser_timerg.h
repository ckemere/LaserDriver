#ifndef LASER_TIMERG_H
#define LASER_TIMERG_H

#include <stdint.h>
#include "mcu.h"

/*
 * TIMG0 register-level driver — 100 kHz state-machine tick.
 *
 * Counter is configured DOWN-counting periodic: BUSCLK / 1 / (320 counts)
 * = 100 kHz. Zero-event interrupt fires once per tick.
 *
 * Caller is responsible for NVIC enable.  laser_timerg_start() turns the
 * counter on; the interrupt is enabled at peripheral level inside init.
 */

void laser_timerg_init(void);
void laser_timerg_start(void);

/* Inline IRQ-acknowledge helper.  Reading IIDX clears the highest-
 * priority pending source; returns the source code so callers can
 * dispatch.  GPTIMER_CPU_INT_IIDX_STAT_Z = zero-event. */
static inline uint32_t laser_timerg_ack(void)
{
    return TIMG0->CPU_INT.IIDX;
}

#endif /* LASER_TIMERG_H */
