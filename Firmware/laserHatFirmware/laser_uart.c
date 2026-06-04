#include "laser_uart.h"
#include "mcu.h"
#include <stdbool.h>

/* ------------------------------------------------------------------
 * RX ring buffer — single-producer (UART ISR), single-consumer (main).
 * Power-of-two size lets us use a simple mask instead of modulo.
 * ------------------------------------------------------------------ */
#define RX_BUF_SIZE   256u
#define RX_BUF_MASK   (RX_BUF_SIZE - 1u)

static volatile uint8_t  rx_buf[RX_BUF_SIZE];
static volatile uint32_t rx_head;   /* written by ISR */
static volatile uint32_t rx_tail;   /* written by main */

static inline void rx_push(uint8_t byte)
{
    uint32_t next = (rx_head + 1u) & RX_BUF_MASK;
    if (next != rx_tail) {           /* drop on overflow */
        rx_buf[rx_head] = byte;
        rx_head = next;
    }
}

bool laser_uart_rx_pop(uint8_t *out)
{
    if (rx_tail == rx_head) {
        return false;
    }
    *out = rx_buf[rx_tail];
    rx_tail = (rx_tail + 1u) & RX_BUF_MASK;
    return true;
}

/* ------------------------------------------------------------------
 * Blocking TX
 * ------------------------------------------------------------------ */
void laser_uart_tx_byte(uint8_t byte)
{
    while ((UART0->STAT & UART_STAT_TXFF_MASK) != 0u) { /* wait */ }
    UART0->TXDATA = byte;
}

void laser_uart_tx_str(const char *s)
{
    while (*s) {
        laser_uart_tx_byte((uint8_t)*s++);
    }
}

void laser_uart_tx_u32(uint32_t value)
{
    /* Up to 10 digits for uint32_t (4294967295). */
    char buf[10];
    int  n = 0;

    if (value == 0u) {
        laser_uart_tx_byte('0');
        return;
    }
    while (value > 0u) {
        buf[n++] = (char)('0' + (value % 10u));
        value  /= 10u;
    }
    while (n-- > 0) {
        laser_uart_tx_byte((uint8_t)buf[n]);
    }
}

/* ------------------------------------------------------------------
 * RX ISR — push bytes into the ring; no protocol logic here.
 * ------------------------------------------------------------------ */
void UART0_IRQHandler(void)
{
    if (UART0->CPU_INT.IIDX == UART_CPU_INT_IIDX_STAT_RXIFG) {
        rx_push((uint8_t)(UART0->RXDATA & UART_RXDATA_DATA_MASK));
    }
}

/*
 * 115200 baud at 32 MHz BUSCLK with 16x oversampling:
 *   divisor = 32e6 / (16 * 115200) = 17.361...
 *   IBRD = 17, FBRD = round(0.361 * 64) = 23
 * Actual ≈ 115210 baud, well within UART tolerance.
 */
#define UART_IBRD        17u
#define UART_FBRD        23u

static inline void update_reg(volatile uint32_t *reg, uint32_t value, uint32_t mask)
{
    *reg = (*reg & ~mask) | (value & mask);
}

void laser_uart_init(void)
{
    /* Reset + power on UART0. */
    UART0->GPRCM.RSTCTL =
        (UART_RSTCTL_KEY_UNLOCK_W | UART_RSTCTL_RESETSTKYCLR_CLR |
         UART_RSTCTL_RESETASSERT_ASSERT);
    UART0->GPRCM.PWREN =
        (UART_PWREN_KEY_UNLOCK_W | UART_PWREN_ENABLE_ENABLE);
    for (volatile int i = 0; i < 16; i++) { /* settle */ }

    /* Disable before configuring (driverlib does the same in DL_UART_init). */
    UART0->CTL0 &= ~UART_CTL0_ENABLE_ENABLE;

    /* Clock = BUSCLK, divide by 1. */
    UART0->CLKSEL = UART_CLKSEL_BUSCLK_SEL_ENABLE;
    UART0->CLKDIV = UART_CLKDIV_RATIO_DIV_BY_1;

    /* CTL0: normal mode, TX+RX enabled, no flow control.  Also clear
     * FEN (FIFO enable bit lives here too) so each received byte raises
     * an RX interrupt immediately, instead of waiting for the FIFO
     * threshold — the line parser wants every byte as it arrives. */
    update_reg(&UART0->CTL0,
        UART_CTL0_MODE_UART | UART_CTL0_RXE_ENABLE | UART_CTL0_TXE_ENABLE |
        UART_CTL0_RTSEN_DISABLE | UART_CTL0_CTSEN_DISABLE,
        UART_CTL0_RXE_MASK | UART_CTL0_TXE_MASK | UART_CTL0_MODE_MASK |
        UART_CTL0_RTSEN_MASK | UART_CTL0_CTSEN_MASK | UART_CTL0_FEN_MASK);

    /* LCRH: 8N1, parity disabled. */
    update_reg(&UART0->LCRH,
        UART_LCRH_PEN_DISABLE | UART_LCRH_WLEN_DATABIT8 | UART_LCRH_STP2_DISABLE,
        UART_LCRH_PEN_ENABLE | UART_LCRH_EPS_MASK | UART_LCRH_SPS_MASK |
        UART_LCRH_WLEN_MASK | UART_LCRH_STP2_MASK);

    /* 16x oversampling. */
    update_reg(&UART0->CTL0, UART_CTL0_HSE_OVS16, UART_CTL0_HSE_MASK);

    /* Baud rate divisor: 115200 @ 32 MHz BUSCLK / 16. */
    update_reg(&UART0->IBRD, UART_IBRD, UART_IBRD_DIVINT_MASK);
    update_reg(&UART0->FBRD, UART_FBRD, UART_FBRD_DIVFRAC_MASK);
    /* Per TRM: any LCRH write latches IBRD/FBRD.  Re-trigger by rewriting
     * the same LCRH value. */
    UART0->LCRH = UART0->LCRH;

    /* Enable RX interrupt at the peripheral (NVIC enable still done in main). */
    UART0->CPU_INT.IMASK |= UART_CPU_INT_IMASK_RXINT_SET;

    /* Enable UART. */
    UART0->CTL0 |= UART_CTL0_ENABLE_ENABLE;
}
