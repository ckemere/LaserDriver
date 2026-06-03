#include "laser_sysctl.h"
#include "mcu.h"

/*
 * Register-level SYSCTL init.  Mirrors SYSCFG_DL_SYSCTL_init() but without
 * driverlib.  Bit definitions come from the device header (mspm0g350x.h).
 */
void laser_sysctl_init(void)
{
    /* BOR threshold = level 0 (BORMIN = reset below ~1.62 V). */
    SYSCTL->SOCLOCK.BORTHRESHOLD = SYSCTL_BORTHRESHOLD_LEVEL_BORMIN;

    /* SYSOSC = base 32 MHz (clears FREQ field; SYSOSCBASE encoded as 0). */
    SYSCTL->SOCLOCK.SYSOSCCFG =
        (SYSCTL->SOCLOCK.SYSOSCCFG & ~SYSCTL_SYSOSCCFG_FREQ_MASK) |
        SYSCTL_SYSOSCCFG_FREQ_SYSOSCBASE;

    /* Disable HFXT and SYSPLL (boot defaults; set explicitly). */
    SYSCTL->SOCLOCK.HSCLKEN &= ~SYSCTL_HSCLKEN_HFXTEN_MASK;
    SYSCTL->SOCLOCK.HSCLKEN &= ~SYSCTL_HSCLKEN_SYSPLLEN_MASK;

    /* Enable MFPCLK (4 MHz precision clock, required for DAC). */
    SYSCTL->SOCLOCK.GENCLKEN |= SYSCTL_GENCLKEN_MFPCLKEN_ENABLE;

    /* Source MFPCLK from SYSOSC (encoded as 0; clear MFPCLKSRC bit). */
    SYSCTL->SOCLOCK.GENCLKCFG =
        (SYSCTL->SOCLOCK.GENCLKCFG & ~SYSCTL_GENCLKCFG_MFPCLKSRC_MASK) |
        SYSCTL_GENCLKCFG_MFPCLKSRC_SYSOSC;
}
