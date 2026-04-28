#include "ti_msp_dl_config.h"
#include "laser_pwm_control.h"

/*
 * IOMUX indices and function codes for the two bridge pins.
 *
 *   PA8  PINCM19  GPIO fn = 0x1  TIMA0_CCP0      fn = 0x5
 *   PA22 PINCM47  GPIO fn = 0x1  TIMA0_CCP0_CMPL fn = 0x7
 */
#define PA8_PINCM       BRIDGE_DUMMY_DUMMY_IOMUX   /* IOMUX_PINCM19 */
#define PA22_PINCM      BRIDGE_LASER_LASER_IOMUX   /* IOMUX_PINCM47 */

#define PA8_GPIO_FUNC   IOMUX_PINCM19_PF_GPIOA_DIO08
#define PA22_GPIO_FUNC  IOMUX_PINCM47_PF_GPIOA_DIO22
#define PA8_PWM_FUNC    IOMUX_PINCM19_PF_TIMA0_CCP0
#define PA22_PWM_FUNC   IOMUX_PINCM47_PF_TIMA0_CCP0_CMPL

/*
 * Configure TIMA0 for 100 kHz edge-aligned complementary PWM.
 *
 * Hardware: BUSCLK = 32 MHz, prescale = 0 (divide-by-1) -> 32 MHz timer clock.
 * Period register = 319 -> period = 320 counts -> 100 kHz.
 * CC0 shadow register loaded at zero event.
 * Initial ccValue = 319 -> laser duty ~ 1/320 (effectively off; GPIO mode
 * is used for true off, but a low initial value is a safe default).
 *
 * No pin is assigned here — PA8/PA22 are switched to TIMA0 at runtime by
 * laser_pins_to_pwm().
 */
void laser_pwm_init(void)
{
    DL_TimerA_reset(TIMA0);
    DL_TimerA_enablePower(TIMA0);
    delay_cycles(16);

    static const DL_TimerA_ClockConfig clkCfg = {
        .clockSel    = DL_TIMER_CLOCK_BUSCLK,
        .divideRatio = DL_TIMER_CLOCK_DIVIDE_1,
        .prescale    = 0U,
    };
    DL_TimerA_setClockConfig(TIMA0, (DL_TimerA_ClockConfig *)&clkCfg);

    static const DL_TimerA_PWMConfig pwmCfg = {
        .pwmMode           = DL_TIMER_PWM_MODE_EDGE_ALIGN,
        .period            = 319,
        .isTimerWithFourCC = true,
        .startTimer        = DL_TIMER_STOP,
    };
    DL_TimerA_initPWMMode(TIMA0, (DL_TimerA_PWMConfig *)&pwmCfg);

    DL_TimerA_setCounterControl(TIMA0,
        DL_TIMER_CZC_CCCTL0_ZCOND,
        DL_TIMER_CAC_CCCTL0_ACOND,
        DL_TIMER_CLC_CCCTL0_LCOND);

    DL_TimerA_setCaptureCompareOutCtl(TIMA0,
        DL_TIMER_CC_OCTL_INIT_VAL_LOW,
        DL_TIMER_CC_OCTL_INV_OUT_DISABLED,
        DL_TIMER_CC_OCTL_SRC_FUNCVAL,
        DL_TIMERA_CAPTURE_COMPARE_0_INDEX);

    DL_TimerA_setCaptCompUpdateMethod(TIMA0,
        DL_TIMER_CC_UPDATE_METHOD_ZERO_EVT,
        DL_TIMERA_CAPTURE_COMPARE_0_INDEX);
    DL_TimerA_setCaptureCompareValue(TIMA0, 319, DL_TIMER_CC_0_INDEX);

    DL_TimerA_enableClock(TIMA0);

    DL_TimerA_setCCPDirection(TIMA0, DL_TIMER_CC0_OUTPUT);
    DL_TimerA_enableShadowFeatures(TIMA0);
}

/*
 * Switch bridge pins to GPIO and lock them to safe output values.
 *
 * Sequence:
 *   1. Write DOUT before touching IOMUX so the moment the pin switches
 *      to GPIO it immediately drives the correct level.
 *   2. Switch PA8 first: dummy path goes GPIO-HIGH while laser is still
 *      PWM-controlled, ensuring current always has somewhere to flow.
 *   3. Switch PA22: laser path goes GPIO-LOW, laser off.
 */
void laser_pins_to_gpio_safe(void)
{
    DL_GPIO_setPins(GPIOA, BRIDGE_DUMMY_DUMMY_PIN);    /* PA8  = 1 */
    DL_GPIO_clearPins(GPIOA, BRIDGE_LASER_LASER_PIN);  /* PA22 = 0 */

    IOMUX->SECCFG.PINCM[PA8_PINCM]  = IOMUX_PINCM_PC_CONNECTED | PA8_GPIO_FUNC;
    IOMUX->SECCFG.PINCM[PA22_PINCM] = IOMUX_PINCM_PC_CONNECTED | PA22_GPIO_FUNC;
}

/*
 * Switch bridge pins to TIMA0 peripheral function.
 *
 * Sequence:
 *   1. Switch PA22 first: laser pin gets PWM control while dummy is still
 *      GPIO-HIGH, so current path is maintained.
 *   2. Switch PA8: dummy path handed to TIMA0_CCP0.  CCP0 is the complement
 *      of CCP0_CMPL, so exactly one of the two transistors is on at any time.
 */
void laser_pins_to_pwm(void)
{
    IOMUX->SECCFG.PINCM[PA22_PINCM] = IOMUX_PINCM_PC_CONNECTED | PA22_PWM_FUNC;
    IOMUX->SECCFG.PINCM[PA8_PINCM]  = IOMUX_PINCM_PC_CONNECTED | PA8_PWM_FUNC;
}
