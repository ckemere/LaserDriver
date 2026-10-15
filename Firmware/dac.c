#include "dac.h"
#include "mcu.h"

static inline void update_reg(volatile uint32_t *reg, uint32_t value, uint32_t mask)
{
    *reg = (*reg & ~mask) | (value & mask);
}

void laser_dac_init(void)
{
    /* Reset + power on DAC0. */
    DAC0->GPRCM.RSTCTL =
        (DAC12_RSTCTL_KEY_UNLOCK_W | DAC12_RSTCTL_RESETSTKYCLR_CLR |
         DAC12_RSTCTL_RESETASSERT_ASSERT);
    DAC0->GPRCM.PWREN =
        (DAC12_PWREN_KEY_UNLOCK_W | DAC12_PWREN_ENABLE_ENABLE);
    for (volatile int i = 0; i < 16; i++) { /* settle */ }

    /* CTL0: 12-bit binary data format (ENABLE stays clear until asked). */
    update_reg(&DAC0->CTL0,
        DAC12_CTL0_RES__12BITS | DAC12_CTL0_DFM_BINARY,
        DAC12_CTL0_RES_MASK | DAC12_CTL0_DFM_MASK);

    /* CTL1: output on OUT0 (PA15), reference VDDA / VSSA, output amp on. */
    update_reg(&DAC0->CTL1,
        DAC12_CTL1_OPS_OUT0 | DAC12_CTL1_REFSP_VDDA |
        DAC12_CTL1_REFSN_VSSA | DAC12_CTL1_AMPEN_ENABLE,
        DAC12_CTL1_OPS_MASK   | DAC12_CTL1_REFSP_MASK | DAC12_CTL1_REFSN_MASK |
        DAC12_CTL1_AMPEN_MASK | DAC12_CTL1_AMPHIZ_MASK);

    /* CTL2: FIFO disabled, DMA trigger disabled. */
    update_reg(&DAC0->CTL2,
        DAC12_CTL2_FIFOEN_CLR     | DAC12_CTL2_FIFOTRIGSEL_STIM |
        DAC12_CTL2_DMATRIGEN_CLR  | DAC12_CTL2_FIFOTH_LOW,
        DAC12_CTL2_DMATRIGEN_MASK | DAC12_CTL2_FIFOTH_MASK |
        DAC12_CTL2_FIFOEN_MASK    | DAC12_CTL2_FIFOTRIGSEL_MASK);

    /* CTL3: sample-time generator disabled. */
    update_reg(&DAC0->CTL3,
        DAC12_CTL3_STIMEN_CLR | DAC12_CTL3_STIMCONFIG__500SPS,
        DAC12_CTL3_STIMCONFIG_MASK | DAC12_CTL3_STIMEN_MASK);

    DAC0->DATA0 = 0u;
}

void laser_dac_enable(void)
{
    DAC0->CTL0 |= DAC12_CTL0_ENABLE_SET;
}

void laser_dac_disable(void)
{
    DAC0->CTL0 &= ~DAC12_CTL0_ENABLE_MASK;
}
