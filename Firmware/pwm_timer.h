#ifndef PWM_TIMER_H
#define PWM_TIMER_H

#include <stdint.h>
#include "mcu.h"
#include "board.h"

/*
 * GPTIMER register-level driver — laser PWM on the switch lines A / B
 * (BOARD_HAS_LASER boards only).  Not built for the StimHAT (no PWM).
 * The timer and its two compare channels come from the board header:
 *
 *   board  | BOARD_PWM_TIMER | PWM_A (laser switch)  | PWM_B (dummy switch)
 *   -------+-----------------+-----------------------+----------------------
 *   rev2   | TIMA0           | CC1 = CC_01[1], PA7   | CC3 = CC_23[1], PA12
 *   laser  | TIMG7           | CC0 = CC_01[0], PA26  | CC1 = CC_01[1], PA27
 *
 * BOARD_PWM_A/B_CC is the channel number, BOARD_PWM_A/B_CC_PAIR the
 * register group it lives in (01 or 23); the index in the group is
 * channel & 1.  Register and bit names are built by token pasting at
 * compile time, so the generated code is that of hand-written accesses.
 * The function names keep their historical "timera" spelling.
 *
 * Only features every GPTIMER instance used here has: compare channels,
 * shadow CC (CCUPD at zero) and shadow load (TIMA0 and TIMG7 both have
 * them, SLASEW9E table 8-16), a 16-bit LOAD, no dead band, fault input or
 * repeat counter.  TIMG instances have only CC0 / CC1 (no _23 registers);
 * checked below.  TIMA0 and TIMG7 are both in PD1, clocked from BUSCLK.
 *
 * 100 kHz edge-aligned UP-counting PWM, BUSCLK = 32 MHz, period = 320:
 *
 *   PWM_A (laser switch): HIGH at counter zero, LOW at counter == CC(A)
 *                       -> duty = CC / 320 (CC = 320 -> 100 %)
 *   PWM_B (dummy switch): LOW at zero, HIGH at counter == CC(B), with
 *                       CC(B) == CC(A) -> the complement of PWM_A (no
 *                       deadband), i.e. the dummy switch conducts while
 *                       the laser switch is off.
 *
 * CC writes latch at the next counter-zero event, so a duty update never
 * glitches mid-period.  Pin-mux switching between GPIO-safe and PWM is in
 * output_mux.c; this module only configures the timer.
 *
 * On Rev 2 the e-stim module uses the same two pins as independent EN /
 * CATH edges (spec §7); in ESTIM mode they stay in their GPIO mux and the
 * tick ISR drives them directly (10 µs grid), so this timer idles.
 */

#if BOARD_HAS_LASER

/* ----- Compile-time sanity of the board's channel description ----- */
#if !((BOARD_PWM_A_CC_PAIR == 1 && BOARD_PWM_A_CC <= 1) || \
      (BOARD_PWM_A_CC_PAIR == 23 && BOARD_PWM_A_CC >= 2 && BOARD_PWM_A_CC <= 3))
#error "BOARD_PWM_A_CC_PAIR must be 01 for CC0/CC1 and 23 for CC2/CC3"
#endif
#if !((BOARD_PWM_B_CC_PAIR == 1 && BOARD_PWM_B_CC <= 1) || \
      (BOARD_PWM_B_CC_PAIR == 23 && BOARD_PWM_B_CC >= 2 && BOARD_PWM_B_CC <= 3))
#error "BOARD_PWM_B_CC_PAIR must be 01 for CC0/CC1 and 23 for CC2/CC3"
#endif
#if BOARD_PWM_A_CC == BOARD_PWM_B_CC
#error "PWM_A and PWM_B need two different compare channels"
#endif
#if (BOARD_PWM_TIMER_BASE != TIMA0_BASE) && (BOARD_PWM_A_CC > 1 || BOARD_PWM_B_CC > 1)
#error "only TIMA0 has CC2/CC3 (_23 registers); TIMG / TIMA1 have CC0/CC1 only"
#endif

/* ----- Name builders (two levels so the board macros expand first) ----- */
#define PWM_PASTE3_(a, b, c)        a##b##c
#define PWM_PASTE3(a, b, c)         PWM_PASTE3_(a, b, c)
#define PWM_BITS_(reg, pair, f)     GPTIMER_##reg##_##pair##_##f
#define PWM_BITS(reg, pair, f)      PWM_BITS_(reg, pair, f)
#define PWM_CCPD_(cc)               GPTIMER_CCPD_C0CCP##cc##_OUTPUT
#define PWM_CCPD(cc)                PWM_CCPD_(cc)

/* The timer, and a channel's counter register (reg = CC, CCCTL, OCTL,
 * CCACT, IFCTL), e.g. PWM_A_REG(CC) = TIMG7->COUNTERREGS.CC_01[0]. */
#define PWM_TIM                     BOARD_PWM_TIMER
#define PWM_A_REG(reg) \
    (PWM_TIM->COUNTERREGS.PWM_PASTE3(reg, _, BOARD_PWM_A_CC_PAIR)[(BOARD_PWM_A_CC) & 1])
#define PWM_B_REG(reg) \
    (PWM_TIM->COUNTERREGS.PWM_PASTE3(reg, _, BOARD_PWM_B_CC_PAIR)[(BOARD_PWM_B_CC) & 1])
/* A bit-field value of that register group, e.g. PWM_A_BITS(CCACT,
 * ZACT_CCP_HIGH) = GPTIMER_CCACT_01_ZACT_CCP_HIGH. */
#define PWM_A_BITS(reg, f)          PWM_BITS(reg, BOARD_PWM_A_CC_PAIR, f)
#define PWM_B_BITS(reg, f)          PWM_BITS(reg, BOARD_PWM_B_CC_PAIR, f)
/* CCPD output-direction bits of the two channels (GPTIMER_CCPD_C0CCPn_OUTPUT). */
#define PWM_A_CCPD_OUTPUT           PWM_CCPD(BOARD_PWM_A_CC)
#define PWM_B_CCPD_OUTPUT           PWM_CCPD(BOARD_PWM_B_CC)

void laser_timera_init(void);
void laser_timera_start(void);

/* Hot-path duty update (called from the tick ISR). */
static inline void laser_timera_set_duty(uint32_t step)
{
    PWM_A_REG(CC) = step;   /* PWM_A duty */
    PWM_B_REG(CC) = step;   /* PWM_B complement */
}
#endif /* BOARD_HAS_LASER */

#endif /* PWM_TIMER_H */
