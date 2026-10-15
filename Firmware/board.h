#ifndef BOARD_H
#define BOARD_H

/*
 * LaserHAT **Rev 2** pin map for the MSPM0G3507SRHBR (U7, VQFN-32).
 *
 * Source of truth: LaserHAT/CLAUDE.md ("Rev 2 MCU pin map") and the HAT
 * schematic netlist.  The Rev 1 map (buttons on PA3..PA6, PWM on
 * PA21/PA22, trigger on PA19) is gone; git tag `firmware-rev1` has it.
 *
 * Pin masks use the bare bit-position convention (1U << n).  PINCM
 * indices and function codes are in mcu.h.
 *
 * Pins the firmware deliberately leaves at their reset default
 * (PINCM PC = unconnected, high-impedance):
 *   PA0/PA1   I2C0 SDA/SCL — shared with the Pi's I2C bus (OLED bonnet,
 *             R19/R20 pull-ups to the Pi's 3V3).  Driving them would
 *             break the Pi's bus.
 *   PA2       ROSC — 100 k 0.1 % to GND for the SYSOSC frequency
 *             correction loop (analog function, enabled in sysctl.c).
 *   PA15      DB_DAC (J9.3) — module setpoint / RELEASE; no module yet.
 *   PA17/PA22 DB_ADC_A/B (J9.4/J9.5) — module analog / I2C; no module yet.
 *   PA19/PA20 SWDIO/SWCLK — dedicated debug pins in Rev 2 (Pi GPIO25/24).
 */

#include <stdint.h>
#include "mcu.h"

/* All used pins are on GPIOA on this board. */
#define BOARD_GPIO_PORT             GPIOA

/* ----- Module header J8: PWM_A (PA7) = EN / laser switch, TIMA0_CCP1 ----- */
#define BOARD_PWM_A_PIN             (1u << 7)
#define BOARD_PWM_A_PINCM           IOMUX_PINCM14
#define BOARD_PWM_A_PWM_FUNC        IOMUX_PINCM14_PF_TIMA0_CCP1

/* ----- Module header J8: PWM_B (PA12) = CATH / dummy switch, TIMA0_CCP3 ----- */
#define BOARD_PWM_B_PIN             (1u << 12)
#define BOARD_PWM_B_PINCM           IOMUX_PINCM34
#define BOARD_PWM_B_PWM_FUNC        IOMUX_PINCM34_PF_TIMA0_CCP3

/* ----- Module header J8.3: DB_GPIO (PA6) = FAULT_n, active low ----- */
/* Input with pull-up: the laser module leaves it open, the e-stim module
 * drives it.  TIMA0_FAULT0 (PF 4) is not armed in the bring-up build. */
#define BOARD_FAULT_N_PIN           (1u << 6)
#define BOARD_FAULT_N_PINCM         IOMUX_PINCM11

/* ----- Buttons: active LOW (commons on GND), internal pull-ups -----
 * Bit order in the firmware's button mask (and EVT_BUTTON / RSP_STATUS):
 *   bit 0  BUTTON1  PA21  SW8  BACK  (south edge)
 *   bit 1  BUTTON2  PA14  SW7  wheel push = SELECT
 *   bit 2  BUTTON3  PA16  SW7  wheel roll (contact D)
 *   bit 3  BUTTON4  PA13  SW7  wheel roll (contact B)
 *   bit 4  BUTTON5  PA23  SW9  FIRE  (east edge)
 *   bit 5  BSL      PA18  SW6  active HIGH (ROM BSL invoke; read-only here)
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

/* ----- MCU_STIM_IN (PA26) <- U8 <- J6 "TRIG IN" BNC (1 k series, 100 k pull-down) ----- */
#define BOARD_STIM_IN_PIN           (1u << 26)
#define BOARD_STIM_IN_PINCM         IOMUX_PINCM59

/* ----- PI_TRIGGER (PA27) <- Pi GPIO26 (J1.37), rising edge ----- */
#define BOARD_PI_TRIGGER_PIN        (1u << 27)
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

/* ----- Spare pins (no copper): driven low ----- */
#define BOARD_SPARE_PINS            ((1u << 3) | (1u << 4) | (1u << 5))

#endif /* BOARD_H */
