#include "laser_timerg.h"
#include "mcu.h"

#define TICK_PERIOD_COUNTS  320u  /* 32 MHz / 320 = 100 kHz */

static inline void update_reg(volatile uint32_t *reg, uint32_t value, uint32_t mask)
{
    *reg = (*reg & ~mask) | (value & mask);
}

void laser_timerg_init(void)
{
    /* Reset + power on TIMG0. */
    TIMG0->GPRCM.RSTCTL =
        (GPTIMER_RSTCTL_KEY_UNLOCK_W | GPTIMER_RSTCTL_RESETSTKYCLR_CLR |
         GPTIMER_RSTCTL_RESETASSERT_ASSERT);
    TIMG0->GPRCM.PWREN =
        (GPTIMER_PWREN_KEY_UNLOCK_W | GPTIMER_PWREN_ENABLE_ENABLE);
    for (volatile int i = 0; i < 16; i++) { /* settle */ }

    /* Clock: BUSCLK, /1, prescale 0. */
    TIMG0->CLKSEL          = GPTIMER_CLKSEL_BUSCLK_SEL_ENABLE;
    TIMG0->CLKDIV          = GPTIMER_CLKDIV_RATIO_DIV_BY_1;
    TIMG0->COMMONREGS.CPS  = 0u;

    /* Periodic DOWN-counting mode at the given period.  initTimerMode
     * writes LOAD = period (no -1 adjustment, unlike PWM's UP mode). */
    TIMG0->COUNTERREGS.LOAD = TICK_PERIOD_COUNTS - 1u;

    /* After enable, counter starts from LOAD value (periodic DOWN). */
    update_reg(&TIMG0->COUNTERREGS.CTRCTL,
        GPTIMER_CTRCTL_CVAE_LDVAL, GPTIMER_CTRCTL_CVAE_MASK);

    /* Initial CC0 value 0 (timer mode doesn't really use CC0, but
     * matches the driverlib sequence). */
    TIMG0->COUNTERREGS.CC_01[0] = 0u;

    /* Capture-compare control: COC = capture (i.e., compare events
     * disabled), ACOND = TIMCLK.  Matches DL_TIMER_INTERM_INT_DISABLED. */
    update_reg(&TIMG0->COUNTERREGS.CCCTL_01[0],
        GPTIMER_CCCTL_01_COC_CAPTURE | GPTIMER_CCCTL_01_ACOND_TIMCLK,
        GPTIMER_CCCTL_01_COC_MASK   | GPTIMER_CCCTL_01_ZCOND_MASK |
        GPTIMER_CCCTL_01_LCOND_MASK | GPTIMER_CCCTL_01_ACOND_MASK |
        GPTIMER_CCCTL_01_CCOND_MASK);

    /* Counter control: drive zero/advance/load condition fields off CCCTL0. */
    update_reg(&TIMG0->COUNTERREGS.CTRCTL,
        GPTIMER_CTRCTL_CZC_CCCTL0_ZCOND | GPTIMER_CTRCTL_CAC_CCCTL0_ACOND |
        GPTIMER_CTRCTL_CLC_CCCTL0_LCOND,
        GPTIMER_CTRCTL_CZC_MASK | GPTIMER_CTRCTL_CAC_MASK |
        GPTIMER_CTRCTL_CLC_MASK);

    /* Mode = periodic DOWN counting, repeat enabled, timer disabled until start. */
    update_reg(&TIMG0->COUNTERREGS.CTRCTL,
        GPTIMER_CTRCTL_CM_DOWN | GPTIMER_CTRCTL_REPEAT_REPEAT_1 |
        GPTIMER_CTRCTL_EN_DISABLED,
        GPTIMER_CTRCTL_REPEAT_MASK | GPTIMER_CTRCTL_EN_MASK |
        GPTIMER_CTRCTL_CM_MASK);

    /* Enable peripheral clock to the counter. */
    TIMG0->COMMONREGS.CCLKCTL = GPTIMER_CCLKCTL_CLKEN_ENABLED;

    /* Enable zero-event interrupt at the peripheral. */
    TIMG0->CPU_INT.IMASK = GPTIMER_CPU_INT_IMASK_Z_SET;
}

void laser_timerg_start(void)
{
    TIMG0->COUNTERREGS.CTRCTL |= GPTIMER_CTRCTL_EN_ENABLED;
}
