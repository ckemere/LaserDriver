#ifndef UART_H
#define UART_H

#include <stdint.h>
#include <stdbool.h>
#include "mcu.h"

/*
 * Register-level UART driver for the two ports of the Rev 2 HAT:
 *
 *   UART1 (PA8/PA9)   -> the Pi's UART (GPIO14/15)      `g_uart_pi`
 *   UART0 (PA10/PA11) -> CH340N on the USB-C socket J5  `g_uart_usb`
 *                        (also the ROM bootloader's port)
 *
 * Both run 115200 8N1 from BUSCLK = 32 MHz (IBRD=17, FBRD=23, 16x
 * oversampling -> 115210 actual) and speak the same binary protocol; the
 * main loop runs one frame decoder per port.
 *
 * RX: the port's IRQ pushes bytes into a 256-byte ring; the main loop
 * drains it with uart_rx_pop().  TX: blocking polled writes (a frame is
 * < 32 bytes, < 3 ms).  Pin mux is done in gpio.c.
 */

#define UART_RX_BUF_SIZE   256u

typedef struct {
    UART_Regs         *regs;
    volatile uint8_t   rx_buf[UART_RX_BUF_SIZE];
    volatile uint32_t  rx_head;   /* written by the ISR */
    volatile uint32_t  rx_tail;   /* written by main */
} UartPort;

extern UartPort g_uart_pi;    /* UART1 */
extern UartPort g_uart_usb;   /* UART0 */

/* Bind `p` to `regs`, then reset, clock and configure it (115200 8N1, RX
 * interrupt unmasked at the peripheral; NVIC enable is the caller's). */
void uart_init(UartPort *p, UART_Regs *regs);

/* Pop one byte from the port's RX ring.  false when empty. */
bool uart_rx_pop(UartPort *p, uint8_t *out);

/* Blocking TX. */
void uart_tx_byte(UartPort *p, uint8_t byte);
void uart_tx_buf(UartPort *p, const uint8_t *buf, uint32_t len);

#endif /* UART_H */
