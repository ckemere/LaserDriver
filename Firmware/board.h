#ifndef BOARD_H
#define BOARD_H

/*
 * LaserHAT board pin map for MSPM0G3507SRHBR (U7, VQFN-32).
 *
 * Centralizes the pin assignments so peripheral modules can be written
 * without depending on the SysConfig-generated ti_msp_dl_config.h.
 *
 * Pin masks use the bare bit-position convention (1U << n).  PINCM
 * indices are the IOMUX register indices used to configure the pin.
 * Function codes come from the device header (mspm0g350x.h) and select
 * the alternate peripheral function on that PINCM.
 */

#include <stdint.h>
#include "mcu.h"

/* All used pins are on GPIOA on this board. */
#define BOARD_GPIO_PORT             GPIOA

/* ----- PWM bridge: laser side (PA21) ----- */
#define BOARD_PWM_LASER_PIN         (1u << 21)
#define BOARD_PWM_LASER_PINCM       IOMUX_PINCM46
#define BOARD_PWM_LASER_GPIO_FUNC   IOMUX_PINCM46_PF_GPIOA_DIO21
#define BOARD_PWM_LASER_PWM_FUNC    IOMUX_PINCM46_PF_TIMA0_CCP0

/* ----- PWM bridge: dummy side (PA22) ----- */
#define BOARD_PWM_DUMMY_PIN         (1u << 22)
#define BOARD_PWM_DUMMY_PINCM       IOMUX_PINCM47
#define BOARD_PWM_DUMMY_GPIO_FUNC   IOMUX_PINCM47_PF_GPIOA_DIO22
#define BOARD_PWM_DUMMY_PWM_FUNC    IOMUX_PINCM47_PF_TIMA0_CCP0_CMPL

/* ----- BUTTON1..4 (PA3..PA6) — pressed: pin -> +3V3, PULL_DOWN ----- */
#define BOARD_BUTTON1_PIN           (1u << 3)
#define BOARD_BUTTON1_PINCM         IOMUX_PINCM8

#define BOARD_BUTTON2_PIN           (1u << 4)
#define BOARD_BUTTON2_PINCM         IOMUX_PINCM9

#define BOARD_BUTTON3_PIN           (1u << 5)
#define BOARD_BUTTON3_PINCM         IOMUX_PINCM10

#define BOARD_BUTTON4_PIN           (1u << 6)
#define BOARD_BUTTON4_PINCM         IOMUX_PINCM11

#define BOARD_BUTTON_MASK           (BOARD_BUTTON1_PIN | BOARD_BUTTON2_PIN | \
                                     BOARD_BUTTON3_PIN | BOARD_BUTTON4_PIN)

/* ----- BNC trigger input (PA14) — external TTL pulse, rising edge ----- */
#define BOARD_BNC_TRIGGER_PIN       (1u << 14)
#define BOARD_BNC_TRIGGER_PINCM     IOMUX_PINCM36

/* ----- Pi trigger input (PA19, ex-SWDIO) — Pi GPIO 24 drives it ----- */
/* Boots as SWDIO; firmware reclaims as a GPIO input after the boot
 * blink so SWD reflashing still works (NRST restores the default mux).
 * Mux function 1 = plain GPIO; the GPIOA peripheral name is DIO19. */
#define BOARD_PI_TRIGGER_PIN        (1u << 19)
#define BOARD_PI_TRIGGER_PINCM      IOMUX_PINCM41
#define BOARD_PI_TRIGGER_GPIO_FUNC  ((uint32_t)0x00000001u)

/* ----- STIM_MIRROR LED (PA13) ----- */
#define BOARD_STIM_MIRROR_PIN       (1u << 13)
#define BOARD_STIM_MIRROR_PINCM     IOMUX_PINCM35
#define BOARD_STIM_MIRROR_GPIO_FUNC IOMUX_PINCM35_PF_GPIOA_DIO13

/* ----- DAC OUT (PA15) — output disconnected at IOMUX; DAC drives pin via VREF mux ----- */
#define BOARD_DAC_OUT_PIN           (1u << 15)
#define BOARD_DAC_OUT_PINCM         IOMUX_PINCM37

/* ----- UART0 TX (PA10) / RX (PA11) ----- */
#define BOARD_UART_TX_PIN           (1u << 10)
#define BOARD_UART_TX_PINCM         IOMUX_PINCM21
#define BOARD_UART_TX_FUNC          IOMUX_PINCM21_PF_UART0_TX

#define BOARD_UART_RX_PIN           (1u << 11)
#define BOARD_UART_RX_PINCM         IOMUX_PINCM22
#define BOARD_UART_RX_FUNC          IOMUX_PINCM22_PF_UART0_RX

/* ----- VREF+ (PA23) ----- */
#define BOARD_VREF_POS_PINCM        IOMUX_PINCM48

#endif /* BOARD_H */
