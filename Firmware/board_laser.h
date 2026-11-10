#ifndef BOARD_LASER_H
#define BOARD_LASER_H

/*
 * **LaserDriverHAT** pin map (LaserHAT/LaserDriverHAT) for the
 * MSPM0G1507SRHBR (U7, VQFN-32; same RHB pinout and peripherals used here
 * as the G3507).  Build: BOARD=laser (-DBOARD_LASER).  Include board.h,
 * not this file.
 *
 * Source of truth: LaserHAT/LaserDriverHAT/README.md, "MCU pin map".  The
 * StimHAT core with the LaserDaughter block on the HAT in place of the
 * stimulator.  Laser only: CMD_SET_MODE ESTIM is refused.
 *
 * No fault line: the laser module never had a FAULT output (its J8.3 was
 * unconnected), so BOARD_HAS_FAULT_PIN is 0 and the FAULT_n path is
 * compiled out (FAULT_n reads as "high" = no fault, the interrupt is never
 * armed, MODULE_FAULT_N_LOW / MODULE_FAULT_LATCHED never set).
 *
 * Pins left at their reset default: PA0/PA1 (Pi I2C bus), PA2 (ROSC),
 * PA19/PA20 (SWD), PA15/PA26/PA27 (analog: DAC0_OUT, A0_1, A0_0).
 * NRST <- Pi GPIO9, MCU_PWR_EN <- Pi GPIO10.
 */

#include <stdint.h>
#include "mcu.h"
#include "protocol.h"

/* ----- Identity and feature set ----- */
#define BOARD_TYPE                  BOARD_TYPE_LASER
#define BOARD_NAME                  "laser"
#define BOARD_HAS_LASER             1
#define BOARD_HAS_ESTIM             0
#define BOARD_HAS_FAULT_PIN         0
#define BOARD_HAS_BUTTON6           1
#define BOARD_DEFAULT_MODE          MODE_LASER

/* All used pins are on GPIOA. */
#define BOARD_GPIO_PORT             GPIOA

/* ----- DB_PWM_A (PA22) = laser switch (Q1 G1), TIMA0_CCP1 (PF 5) ----- */
#define BOARD_PWM_A_PIN             (1u << 22)
#define BOARD_PWM_A_PINCM           IOMUX_PINCM47
#define BOARD_PWM_A_PWM_FUNC        IOMUX_PINCM47_PF_TIMA0_CCP1

/* ----- DB_PWM_B (PA23) = dummy switch (Q1 G2), TIMA0_CCP3 (PF 4) ----- */
#define BOARD_PWM_B_PIN             (1u << 23)
#define BOARD_PWM_B_PINCM           IOMUX_PINCM53
#define BOARD_PWM_B_PWM_FUNC        IOMUX_PINCM53_PF_TIMA0_CCP3
#define BOARD_PWM_B_BOOT_HIGH       1   /* dummy switch conducting at boot */

/* ----- Laser block: DB_DAC (PA15), DB_ADC_A (PA26), DB_ADC_B (PA27) ----- */
#define BOARD_DAC_PIN               (1u << 15)
#define BOARD_DAC_PINCM             IOMUX_PINCM37    /* DAC0_OUT, IREF set-point */
#define BOARD_ADC_A_PIN             (1u << 26)
#define BOARD_ADC_A_PINCM           IOMUX_PINCM59    /* A0_1: photodiode */
#define BOARD_ADC_B_PIN             (1u << 27)
#define BOARD_ADC_B_PINCM           IOMUX_PINCM60    /* A0_0: LASER_V x 33k / 133k */
#define BOARD_ADC_INST              ADC0
#define BOARD_ADC_PD_CHANNEL        1u               /* ADC0 channel 1 = PA26 */
#define BOARD_ADC_COMP_CHANNEL      0u               /* ADC0 channel 0 = PA27 */

/* ----- Buttons: active LOW (commons on GND), internal pull-ups -----
 * As the StimHAT except BUTTON3, moved to PA6 (PA15 is DAC0_OUT).
 * Bit order in the button mask (EVT_BUTTON / RSP_STATUS, see protocol.h):
 *   bit 0  BUTTON1  PA12  joystick left   = BACK
 *   bit 1  BUTTON2  PA14  joystick centre = SELECT
 *   bit 2  BUTTON3  PA6   joystick down
 *   bit 3  BUTTON4  PA7   joystick up
 *   bit 4  BUTTON5  PA16  SW9 FIRE
 *   bit 5  BSL      PA18  SW6, active HIGH (read-only here)
 *   bit 6  BUTTON6  PA13  joystick right
 */
#define BOARD_BUTTON1_PIN           (1u << 12)
#define BOARD_BUTTON1_PINCM         IOMUX_PINCM34
#define BOARD_BUTTON2_PIN           (1u << 14)
#define BOARD_BUTTON2_PINCM         IOMUX_PINCM36
#define BOARD_BUTTON3_PIN           (1u << 6)
#define BOARD_BUTTON3_PINCM         IOMUX_PINCM11
#define BOARD_BUTTON4_PIN           (1u << 7)
#define BOARD_BUTTON4_PINCM         IOMUX_PINCM14
#define BOARD_BUTTON5_PIN           (1u << 16)
#define BOARD_BUTTON5_PINCM         IOMUX_PINCM38
#define BOARD_BUTTON6_PIN           (1u << 13)
#define BOARD_BUTTON6_PINCM         IOMUX_PINCM35
#define BOARD_BUTTON_MASK           (BOARD_BUTTON1_PIN | BOARD_BUTTON2_PIN | \
                                     BOARD_BUTTON3_PIN | BOARD_BUTTON4_PIN | \
                                     BOARD_BUTTON5_PIN | BOARD_BUTTON6_PIN)

#define BOARD_BSL_PIN               (1u << 18)
#define BOARD_BSL_PINCM             IOMUX_PINCM40

/* ----- Status LED D7 (PA5): HIGH = on ----- */
#define BOARD_LED_PIN               (1u << 5)
#define BOARD_LED_PINCM             IOMUX_PINCM10

/* ----- MCU_STIM_OUT (PA17) -> U8B -> J7 "SYNC OUT" BNC + D9 ----- */
#define BOARD_STIM_OUT_PIN          (1u << 17)
#define BOARD_STIM_OUT_PINCM        IOMUX_PINCM39

/* ----- MCU_STIM_IN (PA21) <- U8A <- J6 "TRIG IN" BNC, rising edge (GPIO IRQ) ----- */
#define BOARD_STIM_IN_BIT           21u
#define BOARD_STIM_IN_PIN           (1u << BOARD_STIM_IN_BIT)
#define BOARD_STIM_IN_PINCM         IOMUX_PINCM46

/* ----- PI_TRIGGER (PA4) <- Pi GPIO18 (J1.12), rising edge ----- */
#define BOARD_PI_TRIGGER_BIT        4u
#define BOARD_PI_TRIGGER_PIN        (1u << BOARD_PI_TRIGGER_BIT)
#define BOARD_PI_TRIGGER_PINCM      IOMUX_PINCM9

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
#define BOARD_SPARE_PINS            ((1u << 3) | (1u << 24) | (1u << 25))
#define BOARD_SPARE_PINCMS          IOMUX_PINCM8, IOMUX_PINCM54, IOMUX_PINCM55   /* PA3, PA24, PA25 */

#endif /* BOARD_LASER_H */
