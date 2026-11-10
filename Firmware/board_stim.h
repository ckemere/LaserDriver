#ifndef BOARD_STIM_H
#define BOARD_STIM_H

/*
 * **StimHAT** pin map (LaserHAT/StimHAT, 2026-10-29) for the MSPM0G1507SRHBR
 * (U7, VQFN-32; same RHB pinout and peripherals used here as the G3507).
 * Build: BOARD=stim (-DBOARD_STIM).  Include board.h, not this file.
 *
 * Source of truth: LaserHAT/StimHAT/README.md, "MCU pin map (StimHAT,
 * 2026-10-29)".  The e-stim stimulator is on the HAT behind U101 ISO7741
 * (EN_H / CATH_H / RELEASE_H in, FAULT_H back) and U109 ISO1640 (SDA_H /
 * SCL_H to the DAC60501 at 0x48).  E-stim only: there is no laser, no PWM,
 * no DAC0 / ADC use; CMD_SET_MODE LASER is refused.
 *
 * EN_H / CATH_H / RELEASE_H are plain GPIO outputs driven from the tick ISR
 * exactly as the e-stim module's lines were (spec §7).  R101-R103 (10k
 * pull-downs) hold them low while the pins are Hi-Z (reset, boot); the
 * MCU's internal pull-ups must NEVER be enabled on PA23-PA25 (about 20k
 * against 10k would sit in the ISO7741's undefined input band).
 *
 * Pins left at their reset default: PA0/PA1 (Pi I2C bus), PA2 (ROSC),
 * PA19/PA20 (SWD).  NRST <- Pi GPIO9, MCU_PWR_EN <- Pi GPIO10.
 */

#include <stdint.h>
#include "mcu.h"
#include "protocol.h"

/* ----- Identity and feature set ----- */
#define BOARD_TYPE                  BOARD_TYPE_STIM
#define BOARD_NAME                  "stim"
#define BOARD_HAS_LASER             0
#define BOARD_HAS_ESTIM             1
#define BOARD_HAS_FAULT_PIN         1
#define BOARD_HAS_BUTTON6           1
#define BOARD_DEFAULT_MODE          MODE_ESTIM

/* All used pins are on GPIOA. */
#define BOARD_GPIO_PORT             GPIOA

/* ----- Switch line A = EN_H (PA24, U101.4): GPIO only (no PWM on this board) ----- */
#define BOARD_PWM_A_PIN             (1u << 24)
#define BOARD_PWM_A_PINCM           IOMUX_PINCM54
/* ----- Switch line B = CATH_H (PA23, U101.5): GPIO only, idles LOW ----- */
#define BOARD_PWM_B_PIN             (1u << 23)
#define BOARD_PWM_B_PINCM           IOMUX_PINCM53
#define BOARD_PWM_B_BOOT_HIGH       0   /* CATH low from the first instruction of gpio init */

/* ----- FAULT_H (PA22, U101.6), active low -----
 * Push-pull output of the ISO7741 (fail-safe low: also low while the
 * isolated side is unpowered).  No internal pull: the line is always
 * driven, and a pull-up could only make an undriven line read "no fault".
 * Falling edge = GROUP1 GPIO interrupt.  Bit 22 -> polarity in
 * POLARITY31_16 (field 22 - 16 = 6). */
#define BOARD_FAULT_N_BIT           22u
#define BOARD_FAULT_N_PIN           (1u << BOARD_FAULT_N_BIT)
#define BOARD_FAULT_N_PINCM         IOMUX_PINCM47
#define BOARD_FAULT_N_PULLUP        0

/* ----- E-stim lines (spec §7 names) ----- */
#define BOARD_ESTIM_EN_PIN          BOARD_PWM_A_PIN  /* EN_H   = PA24 */
#define BOARD_ESTIM_CATH_PIN        BOARD_PWM_B_PIN  /* CATH_H = PA23 */
#define BOARD_ESTIM_RELEASE_PIN     (1u << 25)       /* RELEASE_H = PA25 (U101.3) */
#define BOARD_ESTIM_RELEASE_PINCM   IOMUX_PINCM55
#define BOARD_ESTIM_SDA_PIN         (1u << 26)       /* SDA_H = PA26 -> U109 ISO1640 */
#define BOARD_ESTIM_SDA_PINCM       IOMUX_PINCM59
#define BOARD_ESTIM_SCL_PIN         (1u << 27)       /* SCL_H = PA27 -> U109 ISO1640 */
#define BOARD_ESTIM_SCL_PINCM       IOMUX_PINCM60
/* SDA_H / SCL_H have 2.2k pull-ups on the HAT side of the ISO1640 (R107 /
 * R108): no internal pull-ups.  Readback (ACK, START check) works through
 * the ISO1640: its side-1 low level is well under the MSPM0's VIL. */
#define BOARD_ESTIM_I2C_PULLUP      0

/* ----- Buttons: active LOW (commons on GND), internal pull-ups -----
 * SW7 = 5-way joystick (mounted at 135 deg), SW9 = FIRE.
 * Bit order in the button mask (EVT_BUTTON / RSP_STATUS, see protocol.h):
 *   bit 0  BUTTON1  PA12  joystick left   = BACK
 *   bit 1  BUTTON2  PA14  joystick centre = SELECT
 *   bit 2  BUTTON3  PA15  joystick down   (Rev 2's wheel roll D slot)
 *   bit 3  BUTTON4  PA7   joystick up     (Rev 2's wheel roll B slot)
 *   bit 4  BUTTON5  PA16  SW9 FIRE
 *   bit 5  BSL      PA18  SW6, active HIGH (read-only here)
 *   bit 6  BUTTON6  PA13  joystick right  (new on this board)
 */
#define BOARD_BUTTON1_PIN           (1u << 12)
#define BOARD_BUTTON1_PINCM         IOMUX_PINCM34
#define BOARD_BUTTON2_PIN           (1u << 14)
#define BOARD_BUTTON2_PINCM         IOMUX_PINCM36
#define BOARD_BUTTON3_PIN           (1u << 15)
#define BOARD_BUTTON3_PINCM         IOMUX_PINCM37
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

/* ----- MCU_STIM_OUT (PA17) -> U8B -> J7 "STIM OUT" BNC + D9 ----- */
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
#define BOARD_SPARE_PINS            ((1u << 3) | (1u << 6))
#define BOARD_SPARE_PINCMS          IOMUX_PINCM8, IOMUX_PINCM11   /* PA3, PA6 */

#endif /* BOARD_STIM_H */
