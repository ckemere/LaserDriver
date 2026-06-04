#include "dac.h"
#include "mcu.h"

/* SysConfig generates this; chip needs ~320 cycles for VREF to settle. */
#define VREF_SETTLE_CYCLES   320u

static inline void update_reg(volatile uint32_t *reg, uint32_t value, uint32_t mask)
{
    *reg = (*reg & ~mask) | (value & mask);
}

static void vref_init(void)
{
    /* Reset + power on VREF. */
    VREF->GPRCM.RSTCTL =
        (VREF_RSTCTL_KEY_UNLOCK_W | VREF_RSTCTL_RESETSTKYCLR_CLR |
         VREF_RSTCTL_RESETASSERT_ASSERT);
    VREF->GPRCM.PWREN =
        (VREF_PWREN_KEY_UNLOCK_W | VREF_PWREN_ENABLE_ENABLE);
    for (volatile int i = 0; i < 16; i++) { /* settle */ }

    /* Clock: LFCLK, divide /1. */
    VREF->CLKSEL = VREF_CLKSEL_LFCLK_SEL_MASK;
    VREF->CLKDIV = 0u;  /* DIVIDE_1 */

    /* CTL0: enable VREF, buffered 2.5 V output, sample-and-hold disabled. */
    VREF->CTL0 = VREF_CTL0_ENABLE_ENABLE |
                 VREF_CTL0_BUFCONFIG_OUTPUT2P5V |
                 VREF_CTL0_SHMODE_DISABLE;

    /* CTL2: sample/hold cycle counts minimum (0 / SHCYCLE_MINIMUM).
     * Both fields end up zero; written explicitly for clarity. */
    VREF->CTL2 =
        ((uint32_t) VREF_CTL2_SHCYCLE_MINIMUM << VREF_CTL2_SHCYCLE_OFS) |
        (0u << VREF_CTL2_HCYCLE_OFS);

    /* Give VREF time to settle before any client (DAC) samples it. */
    for (volatile uint32_t i = 0; i < VREF_SETTLE_CYCLES; i++) { /* nop */ }
}

void laser_dac_init(void)
{
    /* VREF must come up first; DAC sources VEREFP/VEREFN from it. */
    vref_init();

    /* Reset + power on DAC0. */
    DAC0->GPRCM.RSTCTL =
        (DAC12_RSTCTL_KEY_UNLOCK_W | DAC12_RSTCTL_RESETSTKYCLR_CLR |
         DAC12_RSTCTL_RESETASSERT_ASSERT);
    DAC0->GPRCM.PWREN =
        (DAC12_PWREN_KEY_UNLOCK_W | DAC12_PWREN_ENABLE_ENABLE);
    for (volatile int i = 0; i < 16; i++) { /* settle */ }

    /* CTL0: 12-bit binary data format. */
    update_reg(&DAC0->CTL0,
        DAC12_CTL0_RES__12BITS | DAC12_CTL0_DFM_BINARY,
        DAC12_CTL0_RES_MASK | DAC12_CTL0_DFM_MASK);

    /* CTL1: output enable, VREF source = VEREFP/VEREFN, output amp on. */
    update_reg(&DAC0->CTL1,
        DAC12_CTL1_OPS_OUT0 | DAC12_CTL1_REFSP_VEREFP |
        DAC12_CTL1_REFSN_VEREFN | DAC12_CTL1_AMPEN_ENABLE,
        DAC12_CTL1_OPS_MASK   | DAC12_CTL1_REFSP_MASK | DAC12_CTL1_REFSN_MASK |
        DAC12_CTL1_AMPEN_MASK | DAC12_CTL1_AMPHIZ_MASK);

    /* CTL2: FIFO disabled, DMA trigger disabled, threshold and trigger
     * source fields land in default safe values (FIFO is off). */
    update_reg(&DAC0->CTL2,
        DAC12_CTL2_FIFOEN_CLR     | DAC12_CTL2_FIFOTRIGSEL_STIM |
        DAC12_CTL2_DMATRIGEN_CLR  | DAC12_CTL2_FIFOTH_LOW,
        DAC12_CTL2_DMATRIGEN_MASK | DAC12_CTL2_FIFOTH_MASK |
        DAC12_CTL2_FIFOEN_MASK    | DAC12_CTL2_FIFOTRIGSEL_MASK);

    /* CTL3: sample-time generator disabled, sample rate field set to
     * 500 SPS (irrelevant while disabled). */
    update_reg(&DAC0->CTL3,
        DAC12_CTL3_STIMEN_CLR | DAC12_CTL3_STIMCONFIG__500SPS,
        DAC12_CTL3_STIMCONFIG_MASK | DAC12_CTL3_STIMEN_MASK);
}

void laser_dac_enable(void)
{
    DAC0->CTL0 |= DAC12_CTL0_ENABLE_SET;
}
