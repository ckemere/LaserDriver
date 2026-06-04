#include "mcu.h"
#include "laser_pwm_control.h"
#include "laser_sysctl.h"
#include "laser_gpio.h"
#include "laser_timera.h"
#include "laser_timerg.h"
#include "laser_dac.h"
#include "laser_uart.h"
#include <stdbool.h>
#include <stdint.h>

/* -----------------------------------------------------------------------
 * Architecture
 *
 * TIMG0_IRQHandler (100 kHz) is the *only* place pulse timing lives.
 * It advances the state machine and drives the PWM / GPIO outputs.
 * Nothing else - main loop, UART parser, future GPIO edge ISRs - is
 * allowed to touch the pulse state.  This isolates pulse timing from
 * everything else: UART parsing can take as long as it likes without
 * shifting a single PWM-duty write.
 *
 * Triggers are mediated through three volatile flags consumed (and
 * cleared) by the tick ISR at the start of each tick:
 *
 *   g_uart_trigger_pending      set by the UART parser on 't'
 *   g_button_trigger_pending    set by main loop on BUTTON1 release
 *   g_hw_trigger_pending        set by the BNC / Pi-GPIO edge ISR
 *                               (GROUP1_IRQHandler)
 *
 * Pulse-event ACKs (OK pulse start/end) are emitted from the main
 * loop on PulseEvent records the ISR fills at the WAITING<->TRIGGERED
 * edges, so laser_uart_tx_*'s blocking writes stay out of interrupt
 * context.  Each record carries its own via_uart bit, so the ACK pair
 * for a UART-initiated pulse is gated independently of whatever source
 * triggers the next pulse.
 *
 * Config edits arrive in main (parser) and are read by the ISR at
 * latch time.  Each parser command writes a single g_config_live field
 * with one aligned store (atomic on M0+), and the ISR copies the struct
 * field-by-field at latch time, so no field is ever torn.  The latch is
 * the consistency point: a pulse uses whatever fields are live when it
 * triggers.
 * ----------------------------------------------------------------------- */

#define PWM_PERIOD_COUNTS       320u

#define INTENSITY_DEFAULT       320u    /* full duty */
#define RAMP_TICKS_DEFAULT     8000u    /* 80 ms */
#define HOLD_TICKS_DEFAULT    10000u    /* 100 ms */

#define INTENSITY_MIN             1u
#define INTENSITY_MAX           PWM_PERIOD_COUNTS
#define RAMP_TICKS_MIN            1u
#define RAMP_TICKS_MAX     10000000u    /* ~100 s */
#define HOLD_TICKS_MIN            1u
#define HOLD_TICKS_MAX     10000000u

typedef struct {
    uint32_t ramp_ticks;
    uint32_t hold_ticks;
    uint16_t intensity;
} PulseConfig;

static volatile PulseConfig g_config_live = {
    .ramp_ticks = RAMP_TICKS_DEFAULT,
    .hold_ticks = HOLD_TICKS_DEFAULT,
    .intensity  = INTENSITY_DEFAULT,
};
static PulseConfig g_config_active;          /* ISR-only */
static uint32_t    g_active_ticks_per_step;  /* derived at latch time */

/* Boot-side init: applied once at the analog current limit. */
#define DAC_SETPOINT            500u

/*
 * Button debounce: require the pin to be stable for this many polls
 * before accepting a state change.  Main loop polls at the
 * housekeeping rate (1 kHz), so 10 polls = 10 ms.
 */
#define DEBOUNCE_TICKS            10u
#define NUM_BUTTONS                4u

/*
 * Power-on boot blink: 20 toggles of STIM_MIRROR at ~5 Hz before any
 * timer starts.  Pure busy-wait.  ~100 ms at 32 MHz BUSCLK ≈ 3.2 M cycles.
 */
#define BOOT_BLINK_FLASHES      20u
#define BOOT_BLINK_HALF_CYCLES  3200000u

/* -----------------------------------------------------------------------
 * State machine types
 * ----------------------------------------------------------------------- */

typedef enum {
    OVERALL_WAITING,
    OVERALL_TRIGGERED,
} OverallPhase;

typedef enum {
    LASER_IDLE,
    LASER_RAMP_UP,
    LASER_HOLD_HIGH,
    LASER_RAMP_DOWN,
    LASER_HOLD_LOW,
} LaserPhase;

typedef struct {
    OverallPhase overall;
    LaserPhase   laser;
    uint32_t     ramp_step;
    uint32_t     tick_count;
} MachineState;

typedef enum {
    BTN_IDLE,       /* pin LOW (released) */
    BTN_PRESSED,    /* confirmed pressed */
} BtnPhase;

/* -----------------------------------------------------------------------
 * Cross-context globals
 * ----------------------------------------------------------------------- */

/* Pulse state — written only by TIMG0 ISR.  Main only reads .overall
 * (one word, atomic on M0+) for the ? response. */
static volatile MachineState g_state = { OVERALL_WAITING, LASER_IDLE, 0u, 0u };
static volatile uint32_t     g_isr_ticks = 0u;

/* Trigger-source flags.  All bool reads/writes are atomic on M0+. */
static volatile bool g_uart_trigger_pending   = false;
static volatile bool g_button_trigger_pending = false;
static volatile bool g_hw_trigger_pending     = false;

/* Per-pulse event record handed from the ISR (which fills it at a phase
 * transition) to the main loop's blocking UART TX path (which drains it).
 * Each event carries its own via_uart bit so a UART pulse's start/end ACK
 * gating cannot be stomped by a *different* trigger source starting the
 * next pulse before main has drained this one.  Write the payload
 * (tick, via_uart) *before* setting .pending, so a reader that observes
 * .pending is guaranteed to also see the matching payload. */
typedef struct {
    uint32_t tick;
    bool     via_uart;
    bool     pending;
} PulseEvent;

static volatile PulseEvent g_pulse_start_evt = { 0u, false, false };
static volatile PulseEvent g_pulse_end_evt   = { 0u, false, false };

/* ISR-only: tracks whether the in-flight pulse was UART-initiated.  Set
 * when the pulse starts and read when it ends (same pulse, before any
 * next pulse can begin) to stamp the end event's own via_uart copy. */
static bool g_pulse_via_uart = false;

/* Button state — owned by main loop. */
static BtnPhase g_btn_phase[NUM_BUTTONS];
static uint16_t g_btn_debounce[NUM_BUTTONS];
static uint8_t  g_btn_mask = 0u;   /* bit n = button (n+1) debounced-pressed */

/* PA19 (SWDIO) stays in its boot-default SWDIO function until the host
 * sends `g\n` over UART, at which point the firmware reclaims it as a
 * GPIO-input trigger line.  This guarantees SWD reflashing always
 * works on a freshly-booted MCU; clients enable the GPIO-trigger path
 * explicitly when they want it. */
static bool g_pi_trigger_armed = false;

/* Set by TIMG6_IRQHandler at 1 kHz; cleared by main when it actually
 * runs housekeeping work.  TIMG0 ticks also wake main from WFI, but
 * main sees no flag and re-WFIs immediately. */
static volatile bool g_housekeeping_due = false;

/* -----------------------------------------------------------------------
 * Boot blink delay
 * ----------------------------------------------------------------------- */

static void delay_cycles(uint32_t cycles)
{
    volatile uint32_t i = cycles / 3u;
    while (i--) { /* nop */ }
}

/* -----------------------------------------------------------------------
 * State machine — runs entirely inside TIMG0_IRQHandler
 * ----------------------------------------------------------------------- */

static inline void latch_config_from_live(void)
{
    /* Called from ISR.  Each live field is written by the parser with a
     * single aligned store (atomic on M0+), so copying them here can never
     * read a torn field. */
    g_config_active.ramp_ticks = g_config_live.ramp_ticks;
    g_config_active.hold_ticks = g_config_live.hold_ticks;
    g_config_active.intensity  = g_config_live.intensity;

    g_active_ticks_per_step = g_config_active.ramp_ticks / g_config_active.intensity;
    if (g_active_ticks_per_step == 0u) {
        g_active_ticks_per_step = 1u;
    }
}

static inline void state_machine_tick(void)
{
    /* --- Combine trigger sources --- */
    bool from_uart   = g_uart_trigger_pending;
    bool from_button = g_button_trigger_pending;
    bool from_hw     = g_hw_trigger_pending;
    g_uart_trigger_pending   = false;
    g_button_trigger_pending = false;
    g_hw_trigger_pending     = false;
    bool trigger = from_uart || from_button || from_hw;

    /* --- Overall + laser phases --- */
    switch (g_state.overall) {
        case OVERALL_WAITING:
            if (trigger) {
                latch_config_from_live();
                g_state.overall    = OVERALL_TRIGGERED;
                g_state.laser      = LASER_RAMP_UP;
                g_state.ramp_step  = 0u;
                g_state.tick_count = 0u;
                g_pulse_via_uart   = from_uart;
                g_pulse_start_evt.tick     = g_isr_ticks;
                g_pulse_start_evt.via_uart = from_uart;
                g_pulse_start_evt.pending  = true;
            }
            break;

        case OVERALL_TRIGGERED:
            g_state.tick_count++;
            switch (g_state.laser) {
                case LASER_RAMP_UP:
                    if (g_state.tick_count >= g_active_ticks_per_step) {
                        g_state.tick_count = 0u;
                        g_state.ramp_step++;
                        if (g_state.ramp_step >= g_config_active.intensity) {
                            g_state.tick_count = 0u;
                            g_state.laser      = LASER_HOLD_HIGH;
                        }
                    }
                    break;

                case LASER_HOLD_HIGH:
                    if (g_state.tick_count >= g_config_active.hold_ticks) {
                        g_state.tick_count = 0u;
                        g_state.ramp_step  = g_config_active.intensity;
                        g_state.laser      = LASER_RAMP_DOWN;
                    }
                    break;

                case LASER_RAMP_DOWN:
                    if (g_state.tick_count >= g_active_ticks_per_step) {
                        g_state.tick_count = 0u;
                        g_state.ramp_step--;
                        if (g_state.ramp_step == 0u) {
                            g_state.tick_count = 0u;
                            g_state.laser      = LASER_HOLD_LOW;
                        }
                    }
                    break;

                case LASER_HOLD_LOW:
                    if (g_state.tick_count >= g_config_active.hold_ticks) {
                        g_state.tick_count = 0u;
                        g_state.ramp_step  = 0u;
                        g_state.laser      = LASER_IDLE;
                        g_state.overall    = OVERALL_WAITING;
                        g_pulse_end_evt.tick     = g_isr_ticks;
                        g_pulse_end_evt.via_uart = g_pulse_via_uart;
                        g_pulse_end_evt.pending  = true;
                    }
                    break;

                default:
                    break;
            }
            break;
    }
}

static inline void set_output_from_state(void)
{
    /* Derive the desired output from the current state. */
    bool     pwm    = false;   /* true = PWM mux, false = GPIO-safe */
    uint16_t duty   = 0u;      /* only meaningful when pwm */
    bool     mirror = false;   /* STIM_MIRROR LED on */

    if (g_state.overall == OVERALL_WAITING) {
        /* defaults: gpio-safe, mirror off */
    } else {
        switch (g_state.laser) {
            case LASER_IDLE:
            case LASER_HOLD_LOW:
                /* gpio-safe, mirror off */
                break;

            case LASER_RAMP_UP:
            case LASER_RAMP_DOWN:
                if (g_state.ramp_step != 0u) {
                    pwm  = true;
                    duty = (uint16_t)g_state.ramp_step;
                }
                mirror = true;
                break;

            case LASER_HOLD_HIGH:
                pwm    = true;
                duty   = g_config_active.intensity;
                mirror = true;
                break;

            default:
                return;   /* unreachable; leave outputs untouched */
        }
    }

    /* RAM shadow of what was last applied.  Compare against it and skip
     * the (two IOMUX registers + duty) writes when nothing changed, so a
     * steady HOLD_HIGH doesn't re-mux the bridge every 10 us.  We never
     * read the IOMUX back — the shadow is the sole source of truth, so the
     * locked-GPIO-vs-PWM safety property and the idempotent-set design are
     * preserved (a forced first write establishes a known state). */
    static bool     applied_valid  = false;
    static bool     applied_pwm    = false;
    static uint16_t applied_duty   = 0u;
    static bool     applied_mirror = false;

    if (!applied_valid || pwm != applied_pwm) {
        if (pwm) {
            laser_pins_to_pwm();
            laser_timera_set_duty(duty);
        } else {
            laser_pins_to_gpio_safe();
        }
        applied_pwm  = pwm;
        applied_duty = duty;
    } else if (pwm && duty != applied_duty) {
        /* Same PWM mux, new duty (ramp step): update duty only. */
        laser_timera_set_duty(duty);
        applied_duty = duty;
    }

    if (!applied_valid || mirror != applied_mirror) {
        if (mirror) {
            laser_gpio_stim_mirror_set();
        } else {
            laser_gpio_stim_mirror_clear();
        }
        applied_mirror = mirror;
    }

    applied_valid = true;
}

void TIMG0_IRQHandler(void)
{
    if (laser_timerg_tick_ack() == GPTIMER_CPU_INT_IIDX_STAT_Z) {
        g_isr_ticks++;
        state_machine_tick();
        set_output_from_state();
    }
}

/* -----------------------------------------------------------------------
 * Main-loop button polling + debounce
 * ----------------------------------------------------------------------- */

static void poll_buttons(void)
{
    uint8_t raw_mask = laser_gpio_read_buttons_raw();

    for (unsigned n = 0; n < NUM_BUTTONS; n++) {
        bool raw_pressed = (raw_mask >> n) & 1u;
        bool now_pressed = (g_btn_phase[n] == BTN_PRESSED);

        if (raw_pressed != now_pressed) {
            g_btn_debounce[n]++;
            if (g_btn_debounce[n] >= DEBOUNCE_TICKS) {
                g_btn_phase[n]    = raw_pressed ? BTN_PRESSED : BTN_IDLE;
                g_btn_debounce[n] = 0u;
                if (raw_pressed) {
                    g_btn_mask |= (uint8_t)(1u << n);
                } else {
                    g_btn_mask &= (uint8_t)~(1u << n);
                    if (n == 0u) {
                        /* BUTTON1 release fires a pulse. */
                        g_button_trigger_pending = true;
                    }
                }
            }
        } else {
            g_btn_debounce[n] = 0u;
        }
    }
}

/* -----------------------------------------------------------------------
 * UART protocol  (unchanged wire format)
 *
 *   i N    set intensity (1..320, peak PWM duty)
 *   r N    set ramp-up ticks
 *   h N    set hold ticks
 *   t      trigger one pulse; ACK is "OK pulse start=..." + "OK pulse end=..."
 *   g      arm the PA19 (Pi-GPIO) trigger.  PA19 starts as SWDIO so SWD
 *          reflashing always works on a fresh boot; sending `g` switches
 *          PA19 to a GPIO input with rising-edge interrupt.  No disarm —
 *          reset the MCU to restore SWDIO.
 *   ?      query state — one line:
 *          OK i=N r=N h=N b=BBBB g=0|1 phase=W|T tick=TTT
 * ----------------------------------------------------------------------- */

#define LINE_BUF_SIZE   64u

static char  line_buf[LINE_BUF_SIZE];
static uint8_t line_len = 0u;
static bool   line_overflowed = false;

static bool parse_decimal(const char *s, uint32_t *out)
{
    uint32_t v = 0u;
    bool got_digit = false;
    while (*s == ' ' || *s == '\t') s++;
    if (*s == '\0' || *s == '\r') return false;
    while (*s >= '0' && *s <= '9') {
        uint32_t digit = (uint32_t)(*s - '0');
        /* Reject before the multiply/add can wrap past UINT32_MAX, so an
         * over-long value can't silently alias a small in-range one
         * (e.g. 4294967297 -> 1).  Callers still range-check the result. */
        if (v > (UINT32_MAX - digit) / 10u) {
            return false;
        }
        v = v * 10u + digit;
        got_digit = true;
        s++;
    }
    while (*s == ' ' || *s == '\t' || *s == '\r') s++;
    if (*s != '\0') return false;
    if (!got_digit) return false;
    *out = v;
    return true;
}

static void emit_ok_kv(char verb, uint32_t value)
{
    laser_uart_tx_str("OK ");
    laser_uart_tx_byte((uint8_t)verb);
    laser_uart_tx_byte('=');
    laser_uart_tx_u32(value);
    laser_uart_tx_byte('\n');
}

static void emit_err(const char *reason)
{
    laser_uart_tx_str("ERR ");
    laser_uart_tx_str(reason);
    laser_uart_tx_byte('\n');
}

static void emit_pulse_event(const char *kind, uint32_t tick)
{
    laser_uart_tx_str("OK pulse ");
    laser_uart_tx_str(kind);
    laser_uart_tx_byte('=');
    laser_uart_tx_u32(tick);
    laser_uart_tx_byte('\n');
}

static void emit_status(void)
{
    /* Snapshot the volatile fields the ISR owns once each; not strictly
     * necessary on M0+ but makes intent explicit. */
    OverallPhase phase = g_state.overall;
    uint32_t     tick  = g_isr_ticks;

    laser_uart_tx_str("OK i=");
    laser_uart_tx_u32(g_config_live.intensity);
    laser_uart_tx_str(" r=");
    laser_uart_tx_u32(g_config_live.ramp_ticks);
    laser_uart_tx_str(" h=");
    laser_uart_tx_u32(g_config_live.hold_ticks);
    laser_uart_tx_str(" b=");
    laser_uart_tx_u32(g_btn_mask);
    laser_uart_tx_str(" g=");
    laser_uart_tx_byte(g_pi_trigger_armed ? '1' : '0');
    laser_uart_tx_str(" phase=");
    laser_uart_tx_byte(phase == OVERALL_WAITING ? 'W' : 'T');
    laser_uart_tx_str(" tick=");
    laser_uart_tx_u32(tick);
    laser_uart_tx_byte('\n');
}

static void process_line(void)
{
    const char *p = line_buf;
    while (*p == ' ' || *p == '\t') p++;
    if (*p == '\0' || *p == '\r') return;     /* blank line */

    char verb = *p++;
    uint32_t arg = 0u;

    switch (verb) {
        case 'i':
            if (!parse_decimal(p, &arg)) { emit_err("bad_arg"); return; }
            if (arg < INTENSITY_MIN || arg > INTENSITY_MAX) {
                emit_err("range"); return;
            }
            /* Single aligned store; atomic on Cortex-M0+.  The ISR's
             * config snapshot is taken atomically at latch time, so no
             * IRQ bracketing is needed here. */
            g_config_live.intensity = (uint16_t)arg;
            emit_ok_kv('i', arg);
            break;

        case 'r':
            if (!parse_decimal(p, &arg)) { emit_err("bad_arg"); return; }
            if (arg < RAMP_TICKS_MIN || arg > RAMP_TICKS_MAX) {
                emit_err("range"); return;
            }
            /* Single aligned store; atomic on Cortex-M0+ (see 'i'). */
            g_config_live.ramp_ticks = arg;
            emit_ok_kv('r', arg);
            break;

        case 'h':
            if (!parse_decimal(p, &arg)) { emit_err("bad_arg"); return; }
            if (arg < HOLD_TICKS_MIN || arg > HOLD_TICKS_MAX) {
                emit_err("range"); return;
            }
            /* Single aligned store; atomic on Cortex-M0+ (see 'i'). */
            g_config_live.hold_ticks = arg;
            emit_ok_kv('h', arg);
            break;

        case 't':
            if (g_state.overall != OVERALL_WAITING) {
                emit_err("busy");
                return;
            }
            g_uart_trigger_pending = true;
            /* No immediate ACK — "OK pulse start=..." will follow from
             * the main loop when the ISR transitions to TRIGGERED. */
            break;

        case 'g':
            /* `g` arms the Pi-GPIO (PA19) trigger.  No disarm — to put
             * PA19 back as SWDIO, reset the MCU.  Idempotent: re-issuing
             * 'g' just re-runs the IOMUX write. */
            laser_gpio_arm_pi_trigger();
            g_pi_trigger_armed = true;
            emit_ok_kv('g', 1u);
            break;

        case '?':
            emit_status();
            break;

        default:
            emit_err("unknown");
            break;
    }
}

static void drain_uart(void)
{
    uint8_t b;
    while (laser_uart_rx_pop(&b)) {
        /* Accept LF, CR, or CRLF as a line terminator. */
        if (b == '\n' || b == '\r') {
            if (line_overflowed) {
                emit_err("overflow");
                line_overflowed = false;
                line_len = 0u;
            } else if (line_len > 0u) {
                line_buf[line_len] = '\0';
                process_line();
                line_len = 0u;
            }
        } else if (line_len + 1u >= LINE_BUF_SIZE) {
            line_overflowed = true;
        } else {
            line_buf[line_len++] = (char)b;
        }
    }
}

static void emit_pending_pulse_events(void)
{
    /* The ISR fills each record's payload (tick, via_uart) before setting
     * .pending, so reading .pending first guarantees the matching payload
     * is already visible. */
    if (g_pulse_start_evt.pending) {
        uint32_t tick     = g_pulse_start_evt.tick;
        bool     via_uart = g_pulse_start_evt.via_uart;
        g_pulse_start_evt.pending = false;
        if (via_uart) {
            emit_pulse_event("start", tick);
        }
    }
    if (g_pulse_end_evt.pending) {
        uint32_t tick     = g_pulse_end_evt.tick;
        bool     via_uart = g_pulse_end_evt.via_uart;
        g_pulse_end_evt.pending = false;
        if (via_uart) {
            emit_pulse_event("end", tick);
        }
    }
}

/* -----------------------------------------------------------------------
 * Entry point
 * ----------------------------------------------------------------------- */

int main(void)
{
    laser_sysctl_init();
    laser_gpio_enable_power_and_reset();
    laser_gpio_init();

    /* Boot indicator before any timer runs. */
    for (uint32_t n = 0u; n < BOOT_BLINK_FLASHES; n++) {
        laser_gpio_stim_mirror_set();
        delay_cycles(BOOT_BLINK_HALF_CYCLES);
        laser_gpio_stim_mirror_clear();
        delay_cycles(BOOT_BLINK_HALF_CYCLES);
    }

    /* PA19 (SWDIO) stays in its boot-default SWDIO function until the
     * host sends `g\n` over UART.  Keeps SWD reflashing reliable on a
     * freshly-booted MCU regardless of what the previous firmware did. */

    laser_timera_init();
    laser_timerg_init_tick();
    laser_timerg_init_housekeeping();
    laser_dac_init();
    laser_dac_write12(DAC_SETPOINT);
    laser_dac_enable();
    laser_uart_init();

    laser_pins_to_gpio_safe();
    laser_timera_start();

    /* TIMG0 ISR now runs the state machine; gets the highest NVIC
     * priority (numerically 0 on M0+).  TIMG6 housekeeping runs at a
     * lower priority so it can never delay a pulse tick. */
    NVIC_SetPriority(TIMG0_INT_IRQn, 0);
    NVIC_SetPriority(TIMG6_INT_IRQn, 3);
    NVIC_EnableIRQ(TIMG0_INT_IRQn);
    NVIC_EnableIRQ(TIMG6_INT_IRQn);
    laser_timerg_start_tick();
    laser_timerg_start_housekeeping();

    NVIC_ClearPendingIRQ(UART0_INT_IRQn);
    NVIC_EnableIRQ(UART0_INT_IRQn);

    /* GPIOA IRQ (shared GROUP1 vector) for the BNC trigger edge.
     * Higher priority than housekeeping so a trigger reaches the ISR
     * before the next 1 kHz housekeeping wake. */
    NVIC_SetPriority(GPIOA_INT_IRQn, 1);
    NVIC_ClearPendingIRQ(GPIOA_INT_IRQn);
    NVIC_EnableIRQ(GPIOA_INT_IRQn);

    while (1) {
        if (g_housekeeping_due) {
            g_housekeeping_due = false;
            drain_uart();
            poll_buttons();
            emit_pending_pulse_events();
        }
        __WFI();
    }
}

void TIMG6_IRQHandler(void)
{
    if (laser_timerg_housekeeping_ack() == GPTIMER_CPU_INT_IIDX_STAT_Z) {
        g_housekeeping_due = true;
    }
}

/* MSPM0G3507 routes GPIOA (and several other peripherals) through the
 * shared INT_GROUP1 vector; the startup file names the handler
 * GROUP1_IRQHandler.  We're the only GROUP1 source in use, so a single
 * MIS check is enough. */
void GROUP1_IRQHandler(void)
{
    uint32_t mis = GPIOA->CPU_INT.MIS;
    uint32_t fired_mask = mis & (BOARD_BNC_TRIGGER_PIN | BOARD_PI_TRIGGER_PIN);
    if (fired_mask) {
        GPIOA->CPU_INT.ICLR = fired_mask;
        g_hw_trigger_pending = true;
    }
}

/*
 * Copyright (c) 2021, Texas Instruments Incorporated
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * *  Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 * *  Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * *  Neither the name of Texas Instruments Incorporated nor the names of
 *    its contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
 * EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
