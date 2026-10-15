#include "adc.h"
#include "board.h"
#include "mcu.h"

/* Sample time in sample-clock periods (4 MHz): 64 -> 16 µs, generous for the
 * 25 k source impedance of the compliance divider. */
#define ADC_SAMPLE_PERIODS   64u

void laser_adc_init(void)
{
    ADC1->ULLMEM.GPRCM.RSTCTL =
        (ADC12_RSTCTL_KEY_UNLOCK_W | ADC12_RSTCTL_RESETSTKYCLR_CLR |
         ADC12_RSTCTL_RESETASSERT_ASSERT);
    ADC1->ULLMEM.GPRCM.PWREN =
        (ADC12_PWREN_KEY_UNLOCK_W | ADC12_PWREN_ENABLE_ENABLE);
    for (volatile int i = 0; i < 16; i++) { /* settle */ }

    /* Sample clock from SYSOSC (32 MHz), told its range, divided by 8. */
    ADC1->ULLMEM.GPRCM.CLKCFG =
        ADC12_CLKCFG_KEY_UNLOCK_W | ADC12_CLKCFG_SAMPCLK_SYSOSC;
    ADC1->ULLMEM.CLKFREQ = ADC12_CLKFREQ_FRANGE_RANGE24TO32;
    ADC1->ULLMEM.CTL0 = ADC12_CTL0_SCLKDIV_DIV_BY_8 | ADC12_CTL0_PWRDN_MANUAL;

    /* Software-triggered single pass over the sequence, sample timer. */
    ADC1->ULLMEM.CTL1 = ADC12_CTL1_CONSEQ_SEQUENCE | ADC12_CTL1_SAMPMODE_AUTO |
                        ADC12_CTL1_TRIGSRC_SOFTWARE | ADC12_CTL1_AVGN_DISABLE |
                        ADC12_CTL1_AVGD_SHIFT0;

    /* 12-bit unsigned results, sequence MEMCTL0..MEMCTL1, no FIFO / DMA. */
    ADC1->ULLMEM.CTL2 = ADC12_CTL2_RES_BIT_12 | ADC12_CTL2_DF_UNSIGNED |
                        ADC12_CTL2_STARTADD_ADDR_00 | ADC12_CTL2_ENDADD_ADDR_01 |
                        ADC12_CTL2_FIFOEN_DISABLE | ADC12_CTL2_DMAEN_DISABLE;

    ADC1->ULLMEM.SCOMP0 = ADC_SAMPLE_PERIODS & ADC12_SCOMP0_VAL_MASK;

    const uint32_t common = ADC12_MEMCTL_VRSEL_VDDA_VSSA | ADC12_MEMCTL_STIME_SEL_SCOMP0 |
                            ADC12_MEMCTL_AVGEN_DISABLE | ADC12_MEMCTL_BCSEN_DISABLE |
                            ADC12_MEMCTL_TRIG_AUTO_NEXT | ADC12_MEMCTL_WINCOMP_DISABLE;
    ADC1->ULLMEM.MEMCTL[0] = common | (BOARD_ADC_PD_CHANNEL   & ADC12_MEMCTL_CHANSEL_MASK);
    ADC1->ULLMEM.MEMCTL[1] = common | (BOARD_ADC_COMP_CHANNEL & ADC12_MEMCTL_CHANSEL_MASK);

    ADC1->ULLMEM.CPU_INT.IMASK = 0u;   /* polled */
}

void laser_adc_start(void)
{
    ADC1->ULLMEM.CPU_INT.ICLR = ADC12_CPU_INT_ICLR_MEMRESIFG1_CLR;
    ADC1->ULLMEM.CTL0 |= ADC12_CTL0_ENC_ON;
    ADC1->ULLMEM.CTL1 |= ADC12_CTL1_SC_START;
}

bool laser_adc_read(uint16_t *pd, uint16_t *comp)
{
    if (!(ADC1->ULLMEM.CPU_INT.RIS & ADC12_CPU_INT_RIS_MEMRESIFG1_MASK)) {
        return false;                   /* sequence not finished (or never started) */
    }
    *pd   = (uint16_t)(ADC1->ULLMEM.MEMRES[0] & 0x0FFFu);
    *comp = (uint16_t)(ADC1->ULLMEM.MEMRES[1] & 0x0FFFu);
    ADC1->ULLMEM.CPU_INT.ICLR = ADC12_CPU_INT_ICLR_MEMRESIFG1_CLR;
    ADC1->ULLMEM.CTL0 &= ~ADC12_CTL0_ENC_MASK;
    return true;
}
