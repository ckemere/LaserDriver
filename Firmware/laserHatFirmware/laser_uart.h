#ifndef LASER_UART_H
#define LASER_UART_H

#include <stdint.h>
#include <ti/devices/msp/msp.h>

/*
 * UART0 register-level driver — placeholder echo path until a real
 * protocol lands.
 *
 * Configures UART0 for 9600 8N1 from BUSCLK = 32 MHz (IBRD=208,
 * FBRD=21, oversampling 16x → 9600.24 actual).  Enables the RX
 * interrupt at the peripheral.  Pin mux for PA10/PA11 is handled by
 * laser_gpio_init().
 *
 * Hot-path RX/TX helpers stay inline so the IRQ handler doesn't pay a
 * call.
 */

void laser_uart_init(void);

static inline uint32_t laser_uart_iidx(void)
{
    return UART0->CPU_INT.IIDX;
}

static inline uint8_t laser_uart_rx(void)
{
    return (uint8_t)(UART0->RXDATA & UART_RXDATA_DATA_MASK);
}

static inline void laser_uart_tx(uint8_t byte)
{
    UART0->TXDATA = byte;
}

#endif /* LASER_UART_H */
