#include "pwm_timer.h"
#include "mcu.h"

#if BOARD_HAS_LASER   /* the whole file: no PWM on the StimHAT */

/* Timer and channels: BOARD_PWM_TIMER, BOARD_PWM_A/B_CC(_PAIR) (pwm_timer.h;
 * Rev 2 TIMA0 CC1 / CC3, LaserDriverHAT TIMG7 CC0 / CC1). */

#define TIMA_PERIOD_COUNTS  320u

/* TIMG7 (and TIMA0) count 16 bits: the LOAD value must fit. */
_Static_assert(TIMA_PERIOD_COUNTS - 1u <= 0xFFFFu, "PWM period exceeds a 16-bit counter");

static inline void update_reg(volatile uint32_t *reg, uint32_t value, uint32_t mask)
{
    *reg = (*reg & ~mask) | (value & mask);
}

void laser_timera_init(void)
{
    /* --- Reset + power-enable the PWM timer --- */
    PWM_TIM->GPRCM.RSTCTL =
        (GPTIMER_RSTCTL_KEY_UNLOCK_W | GPTIMER_RSTCTL_RESETSTKYCLR_CLR |
         GPTIMER_RSTCTL_RESETASSERT_ASSERT);
    PWM_TIM->GPRCM.PWREN =
        (GPTIMER_PWREN_KEY_UNLOCK_W | GPTIMER_PWREN_ENABLE_ENABLE);
    for (volatile int i = 0; i < 16; i++) { /* settle */ }

    /* --- Clock: BUSCLK, /1, prescale 0 --- */
    PWM_TIM->CLKSEL          = GPTIMER_CLKSEL_BUSCLK_SEL_ENABLE;
    PWM_TIM->CLKDIV          = GPTIMER_CLKDIV_RATIO_DIV_BY_1;
    PWM_TIM->COMMONREGS.CPS  = 0u;

    PWM_TIM->COUNTERREGS.LOAD = TIMA_PERIOD_COUNTS - 1u;

    /* PWM_A: HIGH at zero, LOW at compare-up. */
    const uint32_t ccact_a_mask =
        PWM_A_BITS(CCACT, SWFRCACT_CMPL_MASK) | PWM_A_BITS(CCACT, SWFRCACT_MASK) |
        PWM_A_BITS(CCACT, FEXACT_MASK)        | PWM_A_BITS(CCACT, FENACT_MASK)   |
        PWM_A_BITS(CCACT, CC2UACT_MASK)       | PWM_A_BITS(CCACT, CC2DACT_MASK)  |
        PWM_A_BITS(CCACT, CUACT_MASK)         | PWM_A_BITS(CCACT, CDACT_MASK)    |
        PWM_A_BITS(CCACT, LACT_MASK)          | PWM_A_BITS(CCACT, ZACT_MASK);
    update_reg(&PWM_A_REG(CCACT),
        PWM_A_BITS(CCACT, ZACT_CCP_HIGH) | PWM_A_BITS(CCACT, CUACT_CCP_LOW),
        ccact_a_mask);

    /* PWM_B: LOW at zero, HIGH at compare-up = complement of PWM_A. */
    const uint32_t ccact_b_mask =
        PWM_B_BITS(CCACT, SWFRCACT_CMPL_MASK) | PWM_B_BITS(CCACT, SWFRCACT_MASK) |
        PWM_B_BITS(CCACT, FEXACT_MASK)        | PWM_B_BITS(CCACT, FENACT_MASK)   |
        PWM_B_BITS(CCACT, CC2UACT_MASK)       | PWM_B_BITS(CCACT, CC2DACT_MASK)  |
        PWM_B_BITS(CCACT, CUACT_MASK)         | PWM_B_BITS(CCACT, CDACT_MASK)    |
        PWM_B_BITS(CCACT, LACT_MASK)          | PWM_B_BITS(CCACT, ZACT_MASK);
    update_reg(&PWM_B_REG(CCACT),
        PWM_B_BITS(CCACT, ZACT_CCP_LOW) | PWM_B_BITS(CCACT, CUACT_CCP_HIGH),
        ccact_b_mask);

    /* Counter set to zero when enabled (edge-aligned up). */
    update_reg(&PWM_TIM->COUNTERREGS.CTRCTL,
        GPTIMER_CTRCTL_CVAE_ZEROVAL, GPTIMER_CTRCTL_CVAE_MASK);

    /* Both channels: compare mode, update at the zero event. */
    update_reg(&PWM_A_REG(CCCTL),
        PWM_A_BITS(CCCTL, COC_COMPARE) | PWM_A_BITS(CCCTL, CCUPD_ZERO_EVT),
        PWM_A_BITS(CCCTL, COC_MASK)   | PWM_A_BITS(CCCTL, ZCOND_MASK) |
        PWM_A_BITS(CCCTL, LCOND_MASK) | PWM_A_BITS(CCCTL, ACOND_MASK) |
        PWM_A_BITS(CCCTL, CCOND_MASK) | PWM_A_BITS(CCCTL, CCUPD_MASK));
    update_reg(&PWM_B_REG(CCCTL),
        PWM_B_BITS(CCCTL, COC_COMPARE) | PWM_B_BITS(CCCTL, CCUPD_ZERO_EVT),
        PWM_B_BITS(CCCTL, COC_MASK)   | PWM_B_BITS(CCCTL, ZCOND_MASK) |
        PWM_B_BITS(CCCTL, LCOND_MASK) | PWM_B_BITS(CCCTL, ACOND_MASK) |
        PWM_B_BITS(CCCTL, CCOND_MASK) | PWM_B_BITS(CCCTL, CCUPD_MASK));

    /* Output control: PWM_A idles HIGH, PWM_B idles LOW; functional value,
     * no inversion. */
    PWM_A_REG(OCTL) =
        PWM_A_BITS(OCTL, CCPIV_HIGH) | PWM_A_BITS(OCTL, CCPOINV_NOINV) |
        PWM_A_BITS(OCTL, CCPO_FUNCVAL);
    PWM_B_REG(OCTL) =
        PWM_B_BITS(OCTL, CCPIV_LOW) | PWM_B_BITS(OCTL, CCPOINV_NOINV) |
        PWM_B_BITS(OCTL, CCPO_FUNCVAL);

    /* Input filter / source: not inverted, CCPx input (unused for outputs). */
    update_reg(&PWM_A_REG(IFCTL),
        PWM_A_BITS(IFCTL, INV_NOINVERT) | PWM_A_BITS(IFCTL, ISEL_CCPX_INPUT),
        PWM_A_BITS(IFCTL, INV_MASK) | PWM_A_BITS(IFCTL, ISEL_MASK));
    update_reg(&PWM_B_REG(IFCTL),
        PWM_B_BITS(IFCTL, INV_NOINVERT) | PWM_B_BITS(IFCTL, ISEL_CCPX_INPUT),
        PWM_B_BITS(IFCTL, INV_MASK) | PWM_B_BITS(IFCTL, ISEL_MASK));

    /* Counter mode UP, repeat, stopped for now; zero/advance/load
     * conditions off CCCTL0 (= none). */
    update_reg(&PWM_TIM->COUNTERREGS.CTRCTL,
        GPTIMER_CTRCTL_REPEAT_REPEAT_1 | GPTIMER_CTRCTL_CM_UP |
        GPTIMER_CTRCTL_EN_DISABLED |
        GPTIMER_CTRCTL_CZC_CCCTL0_ZCOND | GPTIMER_CTRCTL_CAC_CCCTL0_ACOND |
        GPTIMER_CTRCTL_CLC_CCCTL0_LCOND,
        GPTIMER_CTRCTL_CZC_MASK    | GPTIMER_CTRCTL_CAC_MASK    |
        GPTIMER_CTRCTL_CLC_MASK    | GPTIMER_CTRCTL_CM_MASK     |
        GPTIMER_CTRCTL_REPEAT_MASK | GPTIMER_CTRCTL_EN_MASK);

    /* Duty 0 until the state machine says otherwise. */
    PWM_A_REG(CC) = 0u;
    PWM_B_REG(CC) = 0u;

    /* Counter clock on, both CCPs declared outputs, shadow load enabled. */
    PWM_TIM->COMMONREGS.CCLKCTL = GPTIMER_CCLKCTL_CLKEN_ENABLED;
    PWM_TIM->COMMONREGS.CCPD    = PWM_A_CCPD_OUTPUT | PWM_B_CCPD_OUTPUT;
    PWM_TIM->COMMONREGS.GCTL   |= GPTIMER_GCTL_SHDWLDEN_ENABLE;
}

void laser_timera_start(void)
{
    PWM_TIM->COUNTERREGS.CTRCTL |= GPTIMER_CTRCTL_EN_ENABLED;
}

#endif /* BOARD_HAS_LASER */
