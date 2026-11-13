#ifndef BOARD_H
#define BOARD_H

/*
 * Board selection.  One source tree, three HATs with the same MSPM0 core
 * and different pin maps / function sets; exactly one of these must be
 * defined (the Makefiles pass it from BOARD=rev2|stim|laser):
 *
 *   -DBOARD_REV2   board_rev2.h   LaserHAT Rev 2, MSPM0G3507: plug-in laser
 *                                 and e-stim modules on J8/J9, both modes
 *   -DBOARD_STIM   board_stim.h   StimHAT, MSPM0G1507: isolated e-stim
 *                                 stimulator on the HAT, ESTIM mode only
 *   -DBOARD_LASER  board_laser.h  LaserDriverHAT, MSPM0G1507: laser driver
 *                                 on the HAT, LASER mode only
 *
 * Every board header defines the same macro set:
 *   identity     BOARD_TYPE (BOARD_TYPE_* of protocol.h, sent in
 *                RSP_VERSION.board), BOARD_NAME
 *   features     BOARD_HAS_LASER, BOARD_HAS_ESTIM, BOARD_HAS_FAULT_PIN,
 *                BOARD_HAS_BUTTON6 (all 0/1), BOARD_DEFAULT_MODE
 *   switch lines BOARD_PWM_A_PIN/_PINCM (laser switch / e-stim EN),
 *                BOARD_PWM_B_PIN/_PINCM (dummy switch / e-stim CATH),
 *                BOARD_PWM_B_BOOT_HIGH; with BOARD_HAS_LASER also
 *                BOARD_PWM_A/B_PWM_FUNC (IOMUX code of the timer output),
 *                BOARD_PWM_TIMER / _TIMER_BASE (TIMA0 / TIMG7),
 *                BOARD_PWM_A/B_CC (compare channel, plain literal) and
 *                BOARD_PWM_A/B_CC_PAIR (01 or 23: its register group);
 *                see pwm_timer.h
 *   fault        with BOARD_HAS_FAULT_PIN: BOARD_FAULT_N_BIT/_PIN/_PINCM,
 *                BOARD_FAULT_N_PULLUP
 *   laser        with BOARD_HAS_LASER: BOARD_DAC_PIN/_PINCM,
 *                BOARD_ADC_A/B_PIN/_PINCM, BOARD_ADC_INST (ADC0 / ADC1),
 *                BOARD_ADC_PD_CHANNEL, BOARD_ADC_COMP_CHANNEL
 *   e-stim       with BOARD_HAS_ESTIM: BOARD_ESTIM_EN/CATH_PIN,
 *                BOARD_ESTIM_RELEASE/SDA/SCL_PIN/_PINCM,
 *                BOARD_ESTIM_I2C_PULLUP
 *   buttons      BOARD_BUTTON1..5_PIN/_PINCM (+ BUTTON6 with
 *                BOARD_HAS_BUTTON6), BOARD_BUTTON_MASK, BOARD_BSL_PIN/_PINCM;
 *                bit order of the reported mask: protocol.h EVT_BUTTON
 *   misc I/O     BOARD_LED_*, BOARD_STIM_OUT_*, BOARD_STIM_IN_BIT/_PIN/_PINCM,
 *                BOARD_PI_TRIGGER_BIT/_PIN/_PINCM, the four UART PINCM/FUNC
 *                pairs, BOARD_SPARE_PINS + BOARD_SPARE_PINCMS
 *
 * Pin masks use the bit-position convention (1u << n) on GPIOA; PINCM
 * indices and IOMUX function codes come from mcu.h.  The _BIT macros exist
 * for the GPIO interrupt polarity registers, which split at bit 16
 * (POLARITY15_0 / POLARITY31_16, 2 bits per pin; gpio.c).
 */

#if (defined(BOARD_REV2) + defined(BOARD_STIM) + defined(BOARD_LASER)) != 1
#error "Select exactly one board: -DBOARD_REV2, -DBOARD_STIM or -DBOARD_LASER (make BOARD=rev2|stim|laser)"
#endif

#if defined(BOARD_REV2)
#include "board_rev2.h"
#elif defined(BOARD_STIM)
#include "board_stim.h"
#elif defined(BOARD_LASER)
#include "board_laser.h"
#endif

#if !BOARD_HAS_LASER && !BOARD_HAS_ESTIM
#error "board has neither LASER nor ESTIM"
#endif
#if (BOARD_DEFAULT_MODE == MODE_LASER && !BOARD_HAS_LASER) || \
    (BOARD_DEFAULT_MODE == MODE_ESTIM && !BOARD_HAS_ESTIM)
#error "BOARD_DEFAULT_MODE is a mode this board does not have"
#endif

#endif /* BOARD_H */
