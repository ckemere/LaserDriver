#ifndef UART_H
#define UART_H

#include <stdint.h>
#include <stdbool.h>
#include "mcu.h"

/*
 * UART0 register-level driver.
 *
 * Configures UART0 for 115200 8N1 from BUSCLK = 32 MHz (IBRD=17,
 * FBRD=23, oversampling 16x → 115210 actual).  Enables the RX
 * interrupt at the peripheral.  Pin mux for PA10/PA11 is handled by
 * laser_gpio_init().
 *
 * RX side: the UART0 IRQ pushes received bytes into a small ring
 * buffer; main loop drains it byte-by-byte via laser_uart_rx_pop()
 * and feeds them to the binary frame decoder (see framing.h).
 *
 * TX side: simple blocking polled writes.  At 115200 each byte takes
 * ~87 µs; a frame is well under 32 bytes so a single polled write
 * fits in <3 ms.
 */

void laser_uart_init(void);

/* Pop one byte from the RX ring buffer.  Returns true if a byte was
 * available and stored in *out, false if the ring is empty. */
bool laser_uart_rx_pop(uint8_t *out);

/* Blocking TX of a single byte, or a byte buffer (used to push one
 * encoded wire frame). */
void laser_uart_tx_byte(uint8_t byte);
void laser_uart_tx_buf(const uint8_t *buf, uint32_t len);

/* Read the IRQ index register, clearing the pending source. */
static inline uint32_t laser_uart_iidx(void)
{
    return UART0->CPU_INT.IIDX;
}

#endif /* UART_H */
