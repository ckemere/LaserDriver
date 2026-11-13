#include "tick_timers.h"
#include "mcu.h"

#define TICK_PERIOD_COUNTS         320u    /* 32 MHz / 320 = 100 kHz   */
#define HOUSEKEEPING_PERIOD_COUNTS 32000u  /* 32 MHz / 32000 = 1 kHz   */

static inline void update_reg(volatile uint32_t *reg, uint32_t value, uint32_t mask)
{
    *reg = (*reg & ~mask) | (value & mask);
}

/* Shared init for a periodic-down-counting GPTimer with zero-event IRQ.
 *
 *   tim:    peripheral pointer (TIMG0, TIMG6, ...)
 *   period: counter LOAD value; tick rate = BUSCLK / period
 *           (with the BUSCLK/1, prescale 0 config used below).
 */
static void init_periodic(GPTIMER_Regs *tim, uint32_t period)
{
    /* Reset + power on. */
    tim->GPRCM.RSTCTL =
        (GPTIMER_RSTCTL_KEY_UNLOCK_W | GPTIMER_RSTCTL_RESETSTKYCLR_CLR |
         GPTIMER_RSTCTL_RESETASSERT_ASSERT);
    tim->GPRCM.PWREN =
        (GPTIMER_PWREN_KEY_UNLOCK_W | GPTIMER_PWREN_ENABLE_ENABLE);
    for (volatile int i = 0; i < 16; i++) { /* settle */ }

    /* Clock: BUSCLK, /1, prescale 0. */
    tim->CLKSEL          = GPTIMER_CLKSEL_BUSCLK_SEL_ENABLE;
    tim->CLKDIV          = GPTIMER_CLKDIV_RATIO_DIV_BY_1;
    tim->COMMONREGS.CPS  = 0u;

    /* Periodic DOWN-counting at LOAD = (period - 1). */
    tim->COUNTERREGS.LOAD = period - 1u;

    /* Reload from LOAD when enabled. */
    update_reg(&tim->COUNTERREGS.CTRCTL,
        GPTIMER_CTRCTL_CVAE_LDVAL, GPTIMER_CTRCTL_CVAE_MASK);

    /* CC0 default; compare disabled, ACOND = TIMCLK. */
    tim->COUNTERREGS.CC_01[0] = 0u;
    update_reg(&tim->COUNTERREGS.CCCTL_01[0],
        GPTIMER_CCCTL_01_COC_CAPTURE | GPTIMER_CCCTL_01_ACOND_TIMCLK,
        GPTIMER_CCCTL_01_COC_MASK   | GPTIMER_CCCTL_01_ZCOND_MASK |
        GPTIMER_CCCTL_01_LCOND_MASK | GPTIMER_CCCTL_01_ACOND_MASK |
        GPTIMER_CCCTL_01_CCOND_MASK);

    /* CTRCTL: drive zero/advance/load conds off CCCTL0. */
    update_reg(&tim->COUNTERREGS.CTRCTL,
        GPTIMER_CTRCTL_CZC_CCCTL0_ZCOND | GPTIMER_CTRCTL_CAC_CCCTL0_ACOND |
        GPTIMER_CTRCTL_CLC_CCCTL0_LCOND,
        GPTIMER_CTRCTL_CZC_MASK | GPTIMER_CTRCTL_CAC_MASK |
        GPTIMER_CTRCTL_CLC_MASK);

    /* Periodic DOWN, repeat, disabled until start(). */
    update_reg(&tim->COUNTERREGS.CTRCTL,
        GPTIMER_CTRCTL_CM_DOWN | GPTIMER_CTRCTL_REPEAT_REPEAT_1 |
        GPTIMER_CTRCTL_EN_DISABLED,
        GPTIMER_CTRCTL_REPEAT_MASK | GPTIMER_CTRCTL_EN_MASK |
        GPTIMER_CTRCTL_CM_MASK);

    /* Counter clock. */
    tim->COMMONREGS.CCLKCTL = GPTIMER_CCLKCTL_CLKEN_ENABLED;

    /* Unmask zero-event interrupt at the peripheral. */
    tim->CPU_INT.IMASK = GPTIMER_CPU_INT_IMASK_Z_SET;
}

void laser_timerg_init_tick(void)
{
    init_periodic(TIMG0, TICK_PERIOD_COUNTS);
}

void laser_timerg_start_tick(void)
{
    TIMG0->COUNTERREGS.CTRCTL |= GPTIMER_CTRCTL_EN_ENABLED;
}

void laser_timerg_init_housekeeping(void)
{
    init_periodic(TIMG6, HOUSEKEEPING_PERIOD_COUNTS);
}

void laser_timerg_start_housekeeping(void)
{
    TIMG6->COUNTERREGS.CTRCTL |= GPTIMER_CTRCTL_EN_ENABLED;
}
