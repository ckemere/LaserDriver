#ifndef TICK_TIMERS_H
#define TICK_TIMERS_H

#include <stdint.h>
#include "mcu.h"

/*
 * Two TIMG-family periodic-tick timers:
 *
 *   TIMG0 — 100 kHz state-machine tick (BUSCLK / 1 / 320 counts).
 *           Zero-event interrupt drives TIMG0_IRQHandler in laser_driver.c,
 *           where the pulse state machine lives.
 *
 *   TIMG6 — 1 kHz housekeeping tick (BUSCLK / 1 / 32000 counts).
 *           Zero-event interrupt drives TIMG6_IRQHandler; the handler
 *           just sets a "housekeeping due" flag so the main loop knows
 *           it's time to drain UART, poll buttons, and emit events.
 *
 * Caller enables NVIC; the peripheral-level interrupt is enabled inside
 * each init(), and start() kicks the counter.
 */

void laser_timerg_init_tick(void);
void laser_timerg_start_tick(void);

void laser_timerg_init_housekeeping(void);
void laser_timerg_start_housekeeping(void);

/* Inline IRQ-acknowledge helpers.  Reading IIDX clears the highest-
 * priority pending source; returns the source code so callers can
 * dispatch.  GPTIMER_CPU_INT_IIDX_STAT_Z = zero-event. */
static inline uint32_t laser_timerg_tick_ack(void)
{
    return TIMG0->CPU_INT.IIDX;
}
static inline uint32_t laser_timerg_housekeeping_ack(void)
{
    return TIMG6->CPU_INT.IIDX;
}

#endif /* TICK_TIMERS_H */
