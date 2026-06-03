#include "laser_timera.h"
#include "mcu.h"

/*
 * Mirrors the driverlib-driven init that was in laser_pwm_init() — same
 * sequence, just spelled out as register writes against the device
 * header (mspm0g350x.h via msp.h).  Constants like
 * GPTIMER_CTRCTL_CM_UP are the bare-metal aliases that DL_TIMER_PWM_*
 * resolved to inside driverlib.
 */

#define TIMA_PERIOD_COUNTS  320u

/* Common register-update helper: read-modify-write on a single field. */
static inline void update_reg(volatile uint32_t *reg, uint32_t value, uint32_t mask)
{
    *reg = (*reg & ~mask) | (value & mask);
}

void laser_timera_init(void)
{
    /* --- Reset + power-enable TIMA0 (timed reset assert + release) --- */
    TIMA0->GPRCM.RSTCTL =
        (GPTIMER_RSTCTL_KEY_UNLOCK_W | GPTIMER_RSTCTL_RESETSTKYCLR_CLR |
         GPTIMER_RSTCTL_RESETASSERT_ASSERT);
    TIMA0->GPRCM.PWREN =
        (GPTIMER_PWREN_KEY_UNLOCK_W | GPTIMER_PWREN_ENABLE_ENABLE);
    /* Driverlib calls delay_cycles(16) after enablePower — give the
     * peripheral 16 BUSCLK cycles to come up before the first register
     * write. */
    for (volatile int i = 0; i < 16; i++) { /* nop */ }

    /* --- Clock config: BUSCLK, /1, prescale 0 --- */
    TIMA0->CLKSEL          = GPTIMER_CLKSEL_BUSCLK_SEL_ENABLE;
    TIMA0->CLKDIV          = GPTIMER_CLKDIV_RATIO_DIV_BY_1;
    TIMA0->COMMONREGS.CPS  = 0u;

    /* --- PWM init (edge-aligned, up-counting, four-CC capable) ---
     * setLoadValue(period - 1):
     */
    TIMA0->COUNTERREGS.LOAD = TIMA_PERIOD_COUNTS - 1u;

    /* CC0 + CC1 action: at counter zero -> HIGH, at counter-up match -> LOW. */
    const uint32_t cc_action_up =
        GPTIMER_CCACT_01_ZACT_CCP_HIGH | GPTIMER_CCACT_01_CUACT_CCP_LOW;
    const uint32_t cc_action_mask =
        GPTIMER_CCACT_01_SWFRCACT_CMPL_MASK | GPTIMER_CCACT_01_SWFRCACT_MASK |
        GPTIMER_CCACT_01_FEXACT_MASK        | GPTIMER_CCACT_01_FENACT_MASK   |
        GPTIMER_CCACT_01_CC2UACT_MASK       | GPTIMER_CCACT_01_CC2DACT_MASK  |
        GPTIMER_CCACT_01_CUACT_MASK         | GPTIMER_CCACT_01_CDACT_MASK    |
        GPTIMER_CCACT_01_LACT_MASK          | GPTIMER_CCACT_01_ZACT_MASK;
    update_reg(&TIMA0->COUNTERREGS.CCACT_01[0], cc_action_up, cc_action_mask);
    update_reg(&TIMA0->COUNTERREGS.CCACT_01[1], cc_action_up, cc_action_mask);

    /* Set counter value to ZERO when timer enabled (EDGE_ALIGN_UP). */
    update_reg(&TIMA0->COUNTERREGS.CTRCTL,
        GPTIMER_CTRCTL_CVAE_ZEROVAL, GPTIMER_CTRCTL_CVAE_MASK);

    /* CC0 + CC1 control: COMPARE mode, no extra COND bits. */
    const uint32_t ccctl_mask =
        GPTIMER_CCCTL_01_COC_MASK   | GPTIMER_CCCTL_01_ZCOND_MASK |
        GPTIMER_CCCTL_01_LCOND_MASK | GPTIMER_CCCTL_01_ACOND_MASK |
        GPTIMER_CCCTL_01_CCOND_MASK;
    update_reg(&TIMA0->COUNTERREGS.CCCTL_01[0],
        GPTIMER_CCCTL_01_COC_COMPARE, ccctl_mask);
    update_reg(&TIMA0->COUNTERREGS.CCCTL_01[1],
        GPTIMER_CCCTL_01_COC_COMPARE, ccctl_mask);

    /* CC0 + CC1 output control: start LOW; will be raised to INIT_VAL_HIGH
     * for CC0 below.  Functional value source (not pre-/post-fault). */
    TIMA0->COUNTERREGS.OCTL_01[0] =
        GPTIMER_OCTL_01_CCPIV_LOW | GPTIMER_OCTL_01_CCPOINV_NOINV |
        GPTIMER_OCTL_01_CCPO_FUNCVAL;
    TIMA0->COUNTERREGS.OCTL_01[1] =
        GPTIMER_OCTL_01_CCPIV_LOW | GPTIMER_OCTL_01_CCPOINV_NOINV |
        GPTIMER_OCTL_01_CCPO_FUNCVAL;

    /* CC0 + CC1 input function: no inversion, source = CCPX. */
    update_reg(&TIMA0->COUNTERREGS.IFCTL_01[0],
        GPTIMER_IFCTL_01_INV_NOINVERT | GPTIMER_IFCTL_01_ISEL_CCPX_INPUT,
        GPTIMER_IFCTL_01_INV_MASK | GPTIMER_IFCTL_01_ISEL_MASK);
    update_reg(&TIMA0->COUNTERREGS.IFCTL_01[1],
        GPTIMER_IFCTL_01_INV_NOINVERT | GPTIMER_IFCTL_01_ISEL_CCPX_INPUT,
        GPTIMER_IFCTL_01_INV_MASK | GPTIMER_IFCTL_01_ISEL_MASK);

    /* Counter mode UP, REPEAT, timer stopped for now. */
    update_reg(&TIMA0->COUNTERREGS.CTRCTL,
        GPTIMER_CTRCTL_REPEAT_REPEAT_1 | GPTIMER_CTRCTL_CM_UP |
        GPTIMER_CTRCTL_EN_DISABLED,
        GPTIMER_CTRCTL_CZC_MASK    | GPTIMER_CTRCTL_CAC_MASK    |
        GPTIMER_CTRCTL_CLC_MASK    | GPTIMER_CTRCTL_CVAE_MASK   |
        GPTIMER_CTRCTL_CM_MASK     | GPTIMER_CTRCTL_REPEAT_MASK |
        GPTIMER_CTRCTL_EN_MASK);

    /* --- setCounterControl: drive CTRCTL zero/advance/load condition
     *     fields off CCCTL0 (matches the original sequence). --- */
    update_reg(&TIMA0->COUNTERREGS.CTRCTL,
        GPTIMER_CTRCTL_CZC_CCCTL0_ZCOND | GPTIMER_CTRCTL_CAC_CCCTL0_ACOND |
        GPTIMER_CTRCTL_CLC_CCCTL0_LCOND,
        GPTIMER_CTRCTL_CZC_MASK | GPTIMER_CTRCTL_CAC_MASK |
        GPTIMER_CTRCTL_CLC_MASK);

    /* --- CC0 output: start HIGH at zero (overrides the initial LOW set
     *     during the four-CC PWM init). --- */
    TIMA0->COUNTERREGS.OCTL_01[0] =
        GPTIMER_OCTL_01_CCPIV_HIGH | GPTIMER_OCTL_01_CCPOINV_NOINV |
        GPTIMER_OCTL_01_CCPO_FUNCVAL;

    /* --- CC0 update method: latch new compare values at counter zero. --- */
    update_reg(&TIMA0->COUNTERREGS.CCCTL_01[0],
        GPTIMER_CCCTL_01_CCUPD_ZERO_EVT, GPTIMER_CCCTL_01_CCUPD_MASK);

    /* --- CC0 initial value = 0 (laser off until set_duty changes it). --- */
    TIMA0->COUNTERREGS.CC_01[0] = 0u;

    /* --- Enable peripheral clock and shadow update; declare CC0 output --- */
    TIMA0->COMMONREGS.CCLKCTL = GPTIMER_CCLKCTL_CLKEN_ENABLED;
    TIMA0->COMMONREGS.CCPD    = GPTIMER_CCPD_C0CCP0_OUTPUT;
    TIMA0->COMMONREGS.GCTL   |= GPTIMER_GCTL_SHDWLDEN_ENABLE;
}

void laser_timera_start(void)
{
    TIMA0->COUNTERREGS.CTRCTL |= GPTIMER_CTRCTL_EN_ENABLED;
}
