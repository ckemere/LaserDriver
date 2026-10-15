#include "uart.h"
#include "mcu.h"
#include <stdbool.h>

/* Zero-initialised (ring buffers in .bss); the peripheral pointer is set
 * by uart_init() before the matching NVIC line is enabled. */
UartPort g_uart_pi;    /* UART1 */
UartPort g_uart_usb;   /* UART0 */

#define RX_BUF_MASK   (UART_RX_BUF_SIZE - 1u)

static inline void rx_push(UartPort *p, uint8_t byte)
{
    uint32_t next = (p->rx_head + 1u) & RX_BUF_MASK;
    if (next != p->rx_tail) {           /* drop on overflow */
        p->rx_buf[p->rx_head] = byte;
        p->rx_head = next;
    }
}

bool uart_rx_pop(UartPort *p, uint8_t *out)
{
    if (p->rx_tail == p->rx_head) {
        return false;
    }
    *out = p->rx_buf[p->rx_tail];
    p->rx_tail = (p->rx_tail + 1u) & RX_BUF_MASK;
    return true;
}

void uart_tx_byte(UartPort *p, uint8_t byte)
{
    while ((p->regs->STAT & UART_STAT_TXFF_MASK) != 0u) { /* wait */ }
    p->regs->TXDATA = byte;
}

void uart_tx_buf(UartPort *p, const uint8_t *buf, uint32_t len)
{
    for (uint32_t i = 0u; i < len; i++) {
        uart_tx_byte(p, buf[i]);
    }
}

/* ------------------------------------------------------------------
 * RX ISRs — push bytes into the ring; no protocol logic here.
 * ------------------------------------------------------------------ */
static inline void rx_isr(UartPort *p)
{
    if (p->regs->CPU_INT.IIDX == UART_CPU_INT_IIDX_STAT_RXIFG) {
        rx_push(p, (uint8_t)(p->regs->RXDATA & UART_RXDATA_DATA_MASK));
    }
}

void UART1_IRQHandler(void) { rx_isr(&g_uart_pi);  }
void UART0_IRQHandler(void) { rx_isr(&g_uart_usb); }

/*
 * 115200 baud at 32 MHz BUSCLK with 16x oversampling:
 *   divisor = 32e6 / (16 * 115200) = 17.361...
 *   IBRD = 17, FBRD = round(0.361 * 64) = 23  -> 115210 baud
 */
#define UART_IBRD        17u
#define UART_FBRD        23u

static inline void update_reg(volatile uint32_t *reg, uint32_t value, uint32_t mask)
{
    *reg = (*reg & ~mask) | (value & mask);
}

void uart_init(UartPort *p, UART_Regs *regs)
{
    UART_Regs *u = regs;

    p->regs    = regs;
    p->rx_head = 0u;
    p->rx_tail = 0u;

    u->GPRCM.RSTCTL =
        (UART_RSTCTL_KEY_UNLOCK_W | UART_RSTCTL_RESETSTKYCLR_CLR |
         UART_RSTCTL_RESETASSERT_ASSERT);
    u->GPRCM.PWREN =
        (UART_PWREN_KEY_UNLOCK_W | UART_PWREN_ENABLE_ENABLE);
    for (volatile int i = 0; i < 16; i++) { /* settle */ }

    u->CTL0 &= ~UART_CTL0_ENABLE_ENABLE;

    u->CLKSEL = UART_CLKSEL_BUSCLK_SEL_ENABLE;
    u->CLKDIV = UART_CLKDIV_RATIO_DIV_BY_1;

    /* Normal mode, TX+RX, no flow control, FIFO off so every byte raises
     * an RX interrupt immediately. */
    update_reg(&u->CTL0,
        UART_CTL0_MODE_UART | UART_CTL0_RXE_ENABLE | UART_CTL0_TXE_ENABLE |
        UART_CTL0_RTSEN_DISABLE | UART_CTL0_CTSEN_DISABLE,
        UART_CTL0_RXE_MASK | UART_CTL0_TXE_MASK | UART_CTL0_MODE_MASK |
        UART_CTL0_RTSEN_MASK | UART_CTL0_CTSEN_MASK | UART_CTL0_FEN_MASK);

    /* 8N1. */
    update_reg(&u->LCRH,
        UART_LCRH_PEN_DISABLE | UART_LCRH_WLEN_DATABIT8 | UART_LCRH_STP2_DISABLE,
        UART_LCRH_PEN_ENABLE | UART_LCRH_EPS_MASK | UART_LCRH_SPS_MASK |
        UART_LCRH_WLEN_MASK | UART_LCRH_STP2_MASK);

    update_reg(&u->CTL0, UART_CTL0_HSE_OVS16, UART_CTL0_HSE_MASK);

    update_reg(&u->IBRD, UART_IBRD, UART_IBRD_DIVINT_MASK);
    update_reg(&u->FBRD, UART_FBRD, UART_FBRD_DIVFRAC_MASK);
    u->LCRH = u->LCRH;   /* any LCRH write latches IBRD/FBRD */

    u->CPU_INT.IMASK |= UART_CPU_INT_IMASK_RXINT_SET;

    u->CTL0 |= UART_CTL0_ENABLE_ENABLE;
}
