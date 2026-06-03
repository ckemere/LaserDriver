#include "laser_uart.h"
#include <ti/devices/msp/msp.h>

/*
 * 9600 baud at 32 MHz BUSCLK with 16x oversampling:
 *   divisor = 32e6 / (16 * 9600) = 208.333...
 *   IBRD = 208, FBRD = round(0.333 * 64) = 21
 * SysConfig generates the same pair.
 */
#define UART_IBRD_9600   208u
#define UART_FBRD_9600   21u

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
     * FEN (FIFO enable bit lives here too) so we get one-byte RX
     * interrupts to match the existing echo placeholder. */
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

    /* Baud rate divisor: 9600 @ 32 MHz BUSCLK / 16. */
    update_reg(&UART0->IBRD, UART_IBRD_9600, UART_IBRD_DIVINT_MASK);
    update_reg(&UART0->FBRD, UART_FBRD_9600, UART_FBRD_DIVFRAC_MASK);
    /* Per TRM: any LCRH write latches IBRD/FBRD.  Re-trigger by rewriting
     * the same LCRH value. */
    UART0->LCRH = UART0->LCRH;

    /* Enable RX interrupt at the peripheral (NVIC enable still done in main). */
    UART0->CPU_INT.IMASK |= UART_CPU_INT_IMASK_RXINT_SET;

    /* Enable UART. */
    UART0->CTL0 |= UART_CTL0_ENABLE_ENABLE;
}
