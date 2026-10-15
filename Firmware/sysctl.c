#include "sysctl.h"
#include "mcu.h"

/*
 * Register-level SYSCTL init (no driverlib).
 *
 * Rev 2 adds the SYSOSC frequency correction loop (FCL) with the external
 * 100 k 0.1 % ROSC resistor R4 on PA2: SYSOSC accuracy goes from ±2.5 %
 * (free-running) to well under 1 %, which is what the two UARTs run on.
 * PA2 stays in its reset state (PINCM unconnected = analog).  To fall
 * back to the free-running oscillator delete the SYSOSCFCLCTL write.
 */
void laser_sysctl_init(void)
{
    /* BOR threshold = level 0 (BORMIN = reset below ~1.62 V). */
    SYSCTL->SOCLOCK.BORTHRESHOLD = SYSCTL_BORTHRESHOLD_LEVEL_BORMIN;

    /* SYSOSC = base 32 MHz. */
    SYSCTL->SOCLOCK.SYSOSCCFG =
        (SYSCTL->SOCLOCK.SYSOSCCFG & ~SYSCTL_SYSOSCCFG_FREQ_MASK) |
        SYSCTL_SYSOSCCFG_FREQ_SYSOSCBASE;

    /* FCL with the external ROSC resistor (DL_SYSCTL_enableSYSOSCFCLExternalResistor). */
    SYSCTL->SOCLOCK.SYSOSCFCLCTL =
        SYSCTL_SYSOSCFCLCTL_KEY_VALUE | SYSCTL_SYSOSCFCLCTL_SETUSEFCL_TRUE |
        SYSCTL_SYSOSCFCLCTL_SETUSEEXRES_TRUE;

    /* Disable HFXT and SYSPLL (boot defaults; set explicitly). */
    SYSCTL->SOCLOCK.HSCLKEN &= ~SYSCTL_HSCLKEN_HFXTEN_MASK;
    SYSCTL->SOCLOCK.HSCLKEN &= ~SYSCTL_HSCLKEN_SYSPLLEN_MASK;

    /* Enable MFPCLK (4 MHz precision clock, required for the DAC). */
    SYSCTL->SOCLOCK.GENCLKEN |= SYSCTL_GENCLKEN_MFPCLKEN_ENABLE;
    SYSCTL->SOCLOCK.GENCLKCFG =
        (SYSCTL->SOCLOCK.GENCLKCFG & ~SYSCTL_GENCLKCFG_MFPCLKSRC_MASK) |
        SYSCTL_GENCLKCFG_MFPCLKSRC_SYSOSC;
}
