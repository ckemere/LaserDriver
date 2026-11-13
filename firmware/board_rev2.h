#ifndef BOARD_REV2_H
#define BOARD_REV2_H

/*
 * LaserHAT **Rev 2** pin map for the MSPM0G3507SRHBR (U7, VQFN-32): the HAT
 * with the plug-in laser / e-stim modules on J8 / J9.  Build: BOARD=rev2
 * (-DBOARD_REV2).  Include board.h, not this file.
 *
 * Source of truth: docs/history/REV2_NOTES.md ("Rev 2 MCU pin map" appendix) and the HAT
 * schematic netlist.  The Rev 1 map is git tag `firmware-rev1`.
 *
 * Pins the firmware deliberately leaves at their reset default
 * (PINCM PC = unconnected, high-impedance):
 *   PA0/PA1   I2C0 SDA/SCL: the Pi's I2C bus (OLED bonnet).
 *   PA2       ROSC (analog, sysctl.c).
 *   PA19/PA20 SWDIO/SWCLK.
 *
 * The three J9 module lines change role with the mode (module.c):
 *   PA15      DB_DAC (J9.3):   LASER = DAC0_OUT setpoint (analog, PINCM at
 *             reset default); ESTIM = RELEASE, push-pull GPIO output.
 *   PA17/PA22 DB_ADC_A/B (J9.4/J9.5): LASER = ADC1 ch 2 photodiode / "ADC1
 *             ch 8" compliance divider (analog); ESTIM = bit-banged I2C SDA /
 *             SCL, open-drain GPIO (pull-ups on the module).
 *             KNOWN ISSUE, kept so the Rev 2 build behaves exactly as before:
 *             PA22 is A0_7 (ADC0 channel 7, datasheet SLASEW9E table 6-3),
 *             not an ADC1 input, so adc_comp on the Rev 2 HAT does not read
 *             J9.5.  A fix needs a second ADC instance (PA17 is ADC1 only).
 */

#include <stdint.h>
#include "mcu.h"
#include "protocol.h"

/* ----- Identity and feature set ----- */
#define BOARD_TYPE                  BOARD_TYPE_REV2
#define BOARD_NAME                  "rev2"
#define BOARD_HAS_LASER             1   /* LASER mode: TIMA0 PWM, DAC0, ADC */
#define BOARD_HAS_ESTIM             1   /* ESTIM mode: EN/CATH/RELEASE GPIOs, bit-banged I2C */
#define BOARD_HAS_FAULT_PIN         1   /* FAULT_n GPIO IRQ */
#define BOARD_HAS_BUTTON6           0
#define BOARD_DEFAULT_MODE          MODE_LASER

/* All used pins are on GPIOA. */
#define BOARD_GPIO_PORT             GPIOA

/* ----- Laser PWM timer: TIMA0, CC1 = PWM_A, CC3 = PWM_B (pwm_timer.h).
 * Plain literals: they are token-pasted into register / bit names. ----- */
#define BOARD_PWM_TIMER             TIMA0
#define BOARD_PWM_TIMER_BASE        TIMA0_BASE
#define BOARD_PWM_A_CC              1       /* CC1 -> CC_01[1], CCACT_01[1], ... */
#define BOARD_PWM_A_CC_PAIR         01
#define BOARD_PWM_B_CC              3       /* CC3 -> CC_23[1], CCACT_23[1], ... */
#define BOARD_PWM_B_CC_PAIR         23

/* ----- Module header J8: PWM_A (PA7) = laser switch / e-stim EN, TIMA0_CCP1 ----- */
#define BOARD_PWM_A_PIN             (1u << 7)
#define BOARD_PWM_A_PINCM           IOMUX_PINCM14
#define BOARD_PWM_A_PWM_FUNC        IOMUX_PINCM14_PF_TIMA0_CCP1

/* ----- Module header J8: PWM_B (PA12) = dummy switch / e-stim CATH, TIMA0_CCP3 ----- */
#define BOARD_PWM_B_PIN             (1u << 12)
#define BOARD_PWM_B_PINCM           IOMUX_PINCM34
#define BOARD_PWM_B_PWM_FUNC        IOMUX_PINCM34_PF_TIMA0_CCP3
/* Level of PWM_B from gpio init until enter_mode(): HIGH = dummy switch on
 * (the boot mode is LASER). */
#define BOARD_PWM_B_BOOT_HIGH       1

/* ----- Module header J8.3: DB_GPIO (PA6) = FAULT_n, active low -----
 * Input with pull-up: the laser module leaves it open, the e-stim module
 * drives it (low = fault / isolated side not ready, spec §7).  Falling edge
 * = GROUP1 GPIO interrupt (main.c).  Bit 6 -> polarity in POLARITY15_0. */
#define BOARD_FAULT_N_BIT           6u
#define BOARD_FAULT_N_PIN           (1u << BOARD_FAULT_N_BIT)
#define BOARD_FAULT_N_PINCM         IOMUX_PINCM11
#define BOARD_FAULT_N_PULLUP        1

/* ----- LASER: module header J9: DB_DAC (PA15), DB_ADC_A (PA17), DB_ADC_B (PA22) ----- */
#define BOARD_DAC_PIN               (1u << 15)
#define BOARD_DAC_PINCM             IOMUX_PINCM37    /* DAC0_OUT / e-stim RELEASE */
#define BOARD_ADC_A_PIN             (1u << 17)
#define BOARD_ADC_A_PINCM           IOMUX_PINCM39    /* A1_2 / e-stim SDA */
#define BOARD_ADC_B_PIN             (1u << 22)
#define BOARD_ADC_B_PINCM           IOMUX_PINCM47    /* A0_7 (see KNOWN ISSUE) / e-stim SCL */
#define BOARD_ADC_INST              ADC1
#define BOARD_ADC_PD_CHANNEL        2u               /* ADC1 channel 2 = PA17 */
#define BOARD_ADC_COMP_CHANNEL      8u               /* see KNOWN ISSUE above */

/* ----- ESTIM: the same pins under their spec §7 names ----- */
#define BOARD_ESTIM_EN_PIN          BOARD_PWM_A_PIN  /* J8.5 EN   = PA7  */
#define BOARD_ESTIM_CATH_PIN        BOARD_PWM_B_PIN  /* J8.4 CATH = PA12 */
#define BOARD_ESTIM_RELEASE_PIN     BOARD_DAC_PIN    /* J9.3 RELEASE = PA15 */
#define BOARD_ESTIM_RELEASE_PINCM   BOARD_DAC_PINCM
#define BOARD_ESTIM_SDA_PIN         BOARD_ADC_A_PIN  /* J9.4 SDA = PA17 */
#define BOARD_ESTIM_SDA_PINCM       BOARD_ADC_A_PINCM
#define BOARD_ESTIM_SCL_PIN         BOARD_ADC_B_PIN  /* J9.5 SCL = PA22 */
#define BOARD_ESTIM_SCL_PINCM       BOARD_ADC_B_PINCM
/* Internal pull-ups on SDA/SCL in ESTIM mode (on top of the module's). */
#define BOARD_ESTIM_I2C_PULLUP      1

/* ----- Buttons: active LOW (commons on GND), internal pull-ups -----
 * Bit order in the button mask (EVT_BUTTON / RSP_STATUS, see protocol.h):
 *   bit 0  BUTTON1  PA21  SW8  BACK  (south edge)
 *   bit 1  BUTTON2  PA14  SW7  wheel push = SELECT
 *   bit 2  BUTTON3  PA16  SW7  wheel roll (contact D)
 *   bit 3  BUTTON4  PA13  SW7  wheel roll (contact B)
 *   bit 4  BUTTON5  PA23  SW9  FIRE  (east edge)
 *   bit 5  BSL      PA18  SW6  active HIGH (ROM BSL invoke; read-only here)
 *   bit 6  -        no BUTTON6 on this board: always 0
 */
#define BOARD_BUTTON1_PIN           (1u << 21)
#define BOARD_BUTTON1_PINCM         IOMUX_PINCM46
#define BOARD_BUTTON2_PIN           (1u << 14)
#define BOARD_BUTTON2_PINCM         IOMUX_PINCM36
#define BOARD_BUTTON3_PIN           (1u << 16)
#define BOARD_BUTTON3_PINCM         IOMUX_PINCM38
#define BOARD_BUTTON4_PIN           (1u << 13)
#define BOARD_BUTTON4_PINCM         IOMUX_PINCM35
#define BOARD_BUTTON5_PIN           (1u << 23)
#define BOARD_BUTTON5_PINCM         IOMUX_PINCM53
#define BOARD_BUTTON_MASK           (BOARD_BUTTON1_PIN | BOARD_BUTTON2_PIN | \
                                     BOARD_BUTTON3_PIN | BOARD_BUTTON4_PIN | \
                                     BOARD_BUTTON5_PIN)

#define BOARD_BSL_PIN               (1u << 18)
#define BOARD_BSL_PINCM             IOMUX_PINCM40

/* ----- Status LED D7 (PA24), anode on the pin: HIGH = on ----- */
#define BOARD_LED_PIN               (1u << 24)
#define BOARD_LED_PINCM             IOMUX_PINCM54

/* ----- MCU_STIM_OUT (PA25) -> U8 Schmitt buffer -> J7 "STIM OUT" BNC + D9 ----- */
#define BOARD_STIM_OUT_PIN          (1u << 25)
#define BOARD_STIM_OUT_PINCM        IOMUX_PINCM55

/* ----- MCU_STIM_IN (PA26) <- U8 <- J6 "TRIG IN" BNC, rising edge ----- */
#define BOARD_STIM_IN_BIT           26u
#define BOARD_STIM_IN_PIN           (1u << BOARD_STIM_IN_BIT)
#define BOARD_STIM_IN_PINCM         IOMUX_PINCM59

/* ----- PI_TRIGGER (PA27) <- Pi GPIO26 (J1.37), rising edge ----- */
#define BOARD_PI_TRIGGER_BIT        27u
#define BOARD_PI_TRIGGER_PIN        (1u << BOARD_PI_TRIGGER_BIT)
#define BOARD_PI_TRIGGER_PINCM      IOMUX_PINCM60

/* ----- UART1 <-> Pi: PA8 TX -> GPIO15 (RXD), PA9 RX <- GPIO14 (TXD) ----- */
#define BOARD_PI_UART_TX_PINCM      IOMUX_PINCM19
#define BOARD_PI_UART_TX_FUNC       IOMUX_PINCM19_PF_UART1_TX
#define BOARD_PI_UART_RX_PINCM      IOMUX_PINCM20
#define BOARD_PI_UART_RX_FUNC       IOMUX_PINCM20_PF_UART1_RX

/* ----- UART0 <-> CH340N (USB-C J5): PA10 TX, PA11 RX; also the ROM BSL port ----- */
#define BOARD_USB_UART_TX_PINCM     IOMUX_PINCM21
#define BOARD_USB_UART_TX_FUNC      IOMUX_PINCM21_PF_UART0_TX
#define BOARD_USB_UART_RX_PINCM     IOMUX_PINCM22
#define BOARD_USB_UART_RX_FUNC      IOMUX_PINCM22_PF_UART0_RX

/* ----- Spare pins (no copper): driven low.  Mask and PINCM list must agree. ----- */
#define BOARD_SPARE_PINS            ((1u << 3) | (1u << 4) | (1u << 5))
#define BOARD_SPARE_PINCMS          IOMUX_PINCM8, IOMUX_PINCM9, IOMUX_PINCM10   /* PA3..PA5 */

#endif /* BOARD_REV2_H */
