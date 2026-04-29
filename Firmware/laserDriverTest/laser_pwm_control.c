#include "ti_msp_dl_config.h"
#include "laser_pwm_control.h"

/*
 * IOMUX indices and function codes for the two bridge pins.
 *
 *   PA8  PINCM19  GPIO fn = 0x1  TIMA0_CCP0      fn = 0x5  (laser, direct)
 *   PA22 PINCM47  GPIO fn = 0x1  TIMA0_CCP0_CMPL fn = 0x7  (dummy, complement)
 */
#define PA8_PINCM       BRIDGE_LASER_LASER_IOMUX   /* IOMUX_PINCM19 */
#define PA22_PINCM      BRIDGE_DUMMY_DUMMY_IOMUX   /* IOMUX_PINCM47 */

#define PA8_GPIO_FUNC   IOMUX_PINCM19_PF_GPIOA_DIO08
#define PA22_GPIO_FUNC  IOMUX_PINCM47_PF_GPIOA_DIO22
#define PA8_PWM_FUNC    IOMUX_PINCM19_PF_TIMA0_CCP0
#define PA22_PWM_FUNC   IOMUX_PINCM47_PF_TIMA0_CCP0_CMPL

/*
 * Configure TIMA0 for 100 kHz edge-aligned UP-counting complementary PWM.
 *
 * Clock: BUSCLK = 32 MHz, prescale = 0 (divide-by-1).
 * Period = 320 counts (register = 319) -> 100 kHz.
 *
 * UP mode output (INIT_VAL_HIGH):
 *   - At zero (timer reset): CCP0 goes HIGH.
 *   - At count == CC0: CCP0 goes LOW.
 *   - Laser duty = CC0 / 320.  CC0 = 0 -> ~0%, CC0 >= 320 -> 100%.
 *   - CCP0_CMPL (PA22, dummy) is always the hardware complement of CCP0.
 *
 * No pin is assigned here — PA8/PA22 are switched to TIMA0 at runtime by
 * laser_pins_to_pwm() and back by laser_pins_to_gpio_safe().
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
        .pwmMode           = DL_TIMER_PWM_MODE_EDGE_ALIGN_UP,
        .period            = 319,
        .isTimerWithFourCC = true,
        .startTimer        = DL_TIMER_STOP,
    };
    DL_TimerA_initPWMMode(TIMA0, (DL_TimerA_PWMConfig *)&pwmCfg);

    DL_TimerA_setCounterControl(TIMA0,
        DL_TIMER_CZC_CCCTL0_ZCOND,
        DL_TIMER_CAC_CCCTL0_ACOND,
        DL_TIMER_CLC_CCCTL0_LCOND);

    /* INIT_VAL_HIGH: output starts HIGH at zero, goes LOW at compare match. */
    DL_TimerA_setCaptureCompareOutCtl(TIMA0,
        DL_TIMER_CC_OCTL_INIT_VAL_HIGH,
        DL_TIMER_CC_OCTL_INV_OUT_DISABLED,
        DL_TIMER_CC_OCTL_SRC_FUNCVAL,
        DL_TIMERA_CAPTURE_COMPARE_0_INDEX);

    DL_TimerA_setCaptCompUpdateMethod(TIMA0,
        DL_TIMER_CC_UPDATE_METHOD_ZERO_EVT,
        DL_TIMERA_CAPTURE_COMPARE_0_INDEX);
    /* CC0 = 0: compare fires immediately -> laser off by default. */
    DL_TimerA_setCaptureCompareValue(TIMA0, 0, DL_TIMER_CC_0_INDEX);

    DL_TimerA_enableClock(TIMA0);

    DL_TimerA_setCCPDirection(TIMA0, DL_TIMER_CC0_OUTPUT);
    DL_TimerA_enableShadowFeatures(TIMA0);
}

/*
 * Switch bridge pins to GPIO and lock them to safe output values.
 *
 * Sequence:
 *   1. Pre-load DOUT registers before touching IOMUX so each pin drives
 *      the correct level the instant it switches to GPIO.
 *   2. Switch PA8 (laser, CCP0) to GPIO first so the laser path is
 *      defined (HIGH) while PA22 is still PWM-complemented.
 *   3. Switch PA22 (dummy, CCP0_CMPL) to GPIO LOW last.
 */
void laser_pins_to_gpio_safe(void)
{
    DL_GPIO_setPins(GPIOA, BRIDGE_LASER_LASER_PIN);    /* PA8  = 1 */
    DL_GPIO_clearPins(GPIOA, BRIDGE_DUMMY_DUMMY_PIN);  /* PA22 = 0 */

    IOMUX->SECCFG.PINCM[PA8_PINCM]  = IOMUX_PINCM_PC_CONNECTED | PA8_GPIO_FUNC;
    IOMUX->SECCFG.PINCM[PA22_PINCM] = IOMUX_PINCM_PC_CONNECTED | PA22_GPIO_FUNC;
}

/*
 * Switch bridge pins to TIMA0 peripheral function.
 *
 * Sequence:
 *   1. Switch PA22 (dummy, CCP0_CMPL) first: complement output is active
 *      while the laser pin is still GPIO-HIGH, maintaining the current path.
 *   2. Switch PA8 (laser, CCP0) second: laser now follows PWM.
 */
void laser_pins_to_pwm(void)
{
    IOMUX->SECCFG.PINCM[PA22_PINCM] = IOMUX_PINCM_PC_CONNECTED | PA22_PWM_FUNC;
    IOMUX->SECCFG.PINCM[PA8_PINCM]  = IOMUX_PINCM_PC_CONNECTED | PA8_PWM_FUNC;
}
