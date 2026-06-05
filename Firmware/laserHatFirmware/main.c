#include "mcu.h"
#include "output_mux.h"
#include "sysctl.h"
#include "gpio.h"
#include "pwm_timer.h"
#include "tick_timers.h"
#include "dac.h"
#include "uart.h"
#include "protocol.h"
#include "framing.h"
#include "cobs.h"
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
 * Pulse events (EVT_PULSE_START / EVT_PULSE_END) are emitted from the
 * main loop on PulseEvent records the ISR fills at the WAITING<->TRIGGERED
 * edges, so the blocking UART frame writes stay out of interrupt context.
 * Events are emitted for *every* pulse regardless of trigger source: the
 * host is a broker that reads all typed frames and routes them by type, so
 * there's no per-source ACK gating to get wrong.
 *
 * Wire protocol is binary framed (COBS + CRC16); see protocol.h / framing.h
 * and the host mirror Pi/protocol.py.  The UART RX ISR still just pushes
 * bytes into a ring; the main loop feeds them to a frame decoder.
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

/* Pulse shape: ramp the duty up to `intensity` over the ramp window, hold
 * at full for the hold window, then switch off.  There is no ramp-down or
 * trailing-low phase — the laser turns off at the end of HOLD_HIGH. */
typedef enum {
    LASER_IDLE,
    LASER_RAMP_UP,
    LASER_HOLD_HIGH,
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
 * Write the payload (tick) *before* setting .pending, so a reader that
 * observes .pending is guaranteed to also see the matching tick. */
typedef struct {
    uint32_t tick;
    bool     pending;
} PulseEvent;

static volatile PulseEvent g_pulse_start_evt = { 0u, false };
static volatile PulseEvent g_pulse_end_evt   = { 0u, false };

/* Button state — owned by main loop. */
static BtnPhase g_btn_phase[NUM_BUTTONS];
static uint16_t g_btn_debounce[NUM_BUTTONS];
static uint8_t  g_btn_mask = 0u;   /* bit n = button (n+1) debounced-pressed */

/* Button-change event, produced by poll_buttons and drained by the main
 * loop's frame TX (both run in the 1 kHz housekeeping block, so no
 * cross-context volatility is needed).  .edges is the just-pressed
 * (rising) bits; .mask is the full debounced state. */
typedef struct {
    uint8_t mask;
    uint8_t edges;
    bool    pending;
} ButtonEvent;
static ButtonEvent g_btn_event = { 0u, 0u, false };

/* PA19 (SWDIO) stays in its boot-default SWDIO function until the host
 * sends `g\n` over UART, at which point the firmware reclaims it as a
 * GPIO-input trigger line.  This guarantees SWD reflashing always
 * works on a freshly-booted MCU; clients enable the GPIO-trigger path
 * explicitly when they want it.
 * Canonical rationale: board.h (PA19 block) and README.md (UART protocol). */
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
    bool trigger = g_uart_trigger_pending || g_button_trigger_pending
                   || g_hw_trigger_pending;
    g_uart_trigger_pending   = false;
    g_button_trigger_pending = false;
    g_hw_trigger_pending     = false;

    /* --- Overall + laser phases --- */
    switch (g_state.overall) {
        case OVERALL_WAITING:
            if (trigger) {
                latch_config_from_live();
                g_state.overall    = OVERALL_TRIGGERED;
                g_state.laser      = LASER_RAMP_UP;
                g_state.ramp_step  = 0u;
                g_state.tick_count = 0u;
                g_pulse_start_evt.tick    = g_isr_ticks;
                g_pulse_start_evt.pending = true;
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
                        /* End of hold: switch off and return to waiting.
                         * No ramp-down / trailing-low phase. */
                        g_state.tick_count = 0u;
                        g_state.ramp_step  = 0u;
                        g_state.laser      = LASER_IDLE;
                        g_state.overall    = OVERALL_WAITING;
                        g_pulse_end_evt.tick    = g_isr_ticks;
                        g_pulse_end_evt.pending = true;
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
                /* gpio-safe, mirror off */
                break;

            case LASER_RAMP_UP:
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
    uint8_t old_mask = g_btn_mask;
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

    /* Report any change in the debounced mask so clients can react to
     * presses without polling.  edges = bits that just went pressed. */
    if (g_btn_mask != old_mask) {
        g_btn_event.mask    = g_btn_mask;
        g_btn_event.edges   = (uint8_t)(g_btn_mask & (uint8_t)~old_mask);
        g_btn_event.pending = true;
    }
}

/* -----------------------------------------------------------------------
 * UART protocol — binary framed (COBS + CRC16)
 *
 * Command frames (host -> MCU) are decoded here; response/event frames
 * (MCU -> host) are encoded and sent.  See protocol.h for the type/field
 * map and Pi/protocol.py for the host mirror.  The RX ISR pushes bytes
 * into a ring; this code feeds them to the frame decoder.
 *
 *   CMD_SET_INTENSITY u16   -> RSP_ACK
 *   CMD_SET_RAMP/HOLD u32   -> RSP_ACK
 *   CMD_TRIGGER             -> RSP_ACK, then EVT_PULSE_START/_END
 *   CMD_ARM                 -> RSP_ACK   (reclaim PA19 from SWDIO)
 *   CMD_QUERY               -> RSP_STATUS
 *   (async)                 -> EVT_BUTTON on any debounced button change
 * ----------------------------------------------------------------------- */

static FrameDecoder g_rx_decoder;

/* Encode one frame and push it out the UART (blocking). */
static void tx_frame(uint8_t type, const uint8_t *payload, size_t len)
{
    uint8_t wire[COBS_ENCODE_MAX(FRAME_MAX_BODY) + 1u];
    size_t  n = frame_encode(type, payload, len, wire, sizeof wire);
    if (n != 0u) {
        laser_uart_tx_buf(wire, (uint32_t)n);
    }
}

static inline void put_u16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)(v >> 8);
}

static inline void put_u32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8)  & 0xFFu);
    p[2] = (uint8_t)((v >> 16) & 0xFFu);
    p[3] = (uint8_t)((v >> 24) & 0xFFu);
}

static void emit_ack(uint8_t cmd_type, uint8_t status)
{
    uint8_t payload[2] = { cmd_type, status };
    tx_frame(RSP_ACK, payload, sizeof payload);
}

static void emit_status(void)
{
    /* Field layout matches PROTO_STATUS_FIELD_LEN / Python "<HIIBBBI".
     * Written byte-by-byte (little-endian) to avoid any struct padding. */
    uint8_t p[PROTO_STATUS_FIELD_LEN];
    put_u16(&p[0],  g_config_live.intensity);
    put_u32(&p[2],  g_config_live.ramp_ticks);
    put_u32(&p[6],  g_config_live.hold_ticks);
    p[10] = g_btn_mask;
    p[11] = g_pi_trigger_armed ? 1u : 0u;
    p[12] = (g_state.overall == OVERALL_WAITING) ? PHASE_WAITING
                                                 : PHASE_TRIGGERED;
    put_u32(&p[13], g_isr_ticks);
    tx_frame(RSP_STATUS, p, sizeof p);
}

static void emit_pulse_event(uint8_t type, uint32_t tick)
{
    uint8_t p[4];
    put_u32(p, tick);
    tx_frame(type, p, sizeof p);
}

/* Decode a fixed-width little-endian field of the expected length. */
static bool payload_u16(const uint8_t *p, size_t len, uint32_t *out)
{
    if (len != 2u) return false;
    *out = (uint32_t)p[0] | ((uint32_t)p[1] << 8);
    return true;
}

static bool payload_u32(const uint8_t *p, size_t len, uint32_t *out)
{
    if (len != 4u) return false;
    *out = (uint32_t)p[0] | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
    return true;
}

static void process_frame(uint8_t type, const uint8_t *payload, size_t len)
{
    uint32_t arg = 0u;

    switch (type) {
        case CMD_SET_INTENSITY:
            if (!payload_u16(payload, len, &arg) ||
                arg < INTENSITY_MIN || arg > INTENSITY_MAX) {
                emit_ack(type, ACK_RANGE); return;
            }
            /* Single aligned store; atomic on Cortex-M0+.  The ISR snapshots
             * config atomically at latch time, so no IRQ bracketing here. */
            g_config_live.intensity = (uint16_t)arg;
            emit_ack(type, ACK_OK);
            break;

        case CMD_SET_RAMP:
            if (!payload_u32(payload, len, &arg) ||
                arg < RAMP_TICKS_MIN || arg > RAMP_TICKS_MAX) {
                emit_ack(type, ACK_RANGE); return;
            }
            g_config_live.ramp_ticks = arg;   /* single aligned store (see above) */
            emit_ack(type, ACK_OK);
            break;

        case CMD_SET_HOLD:
            if (!payload_u32(payload, len, &arg) ||
                arg < HOLD_TICKS_MIN || arg > HOLD_TICKS_MAX) {
                emit_ack(type, ACK_RANGE); return;
            }
            g_config_live.hold_ticks = arg;   /* single aligned store (see above) */
            emit_ack(type, ACK_OK);
            break;

        case CMD_TRIGGER:
            if (g_state.overall != OVERALL_WAITING) {
                emit_ack(type, ACK_BUSY);
                return;
            }
            g_uart_trigger_pending = true;
            emit_ack(type, ACK_OK);
            /* EVT_PULSE_START / _END follow from the main loop. */
            break;

        case CMD_ARM:
            /* Arm the Pi-GPIO (PA19) trigger.  No disarm — to put PA19 back
             * as SWDIO, reset the MCU.  Idempotent: re-arming just re-runs
             * the IOMUX write.
             * Canonical rationale: board.h (PA19) / README.md. */
            laser_gpio_arm_pi_trigger();
            g_pi_trigger_armed = true;
            emit_ack(type, ACK_OK);
            break;

        case CMD_QUERY:
            emit_status();
            break;

        default:
            emit_ack(type, ACK_UNKNOWN);
            break;
    }
}

static void drain_uart(void)
{
    uint8_t b;
    while (laser_uart_rx_pop(&b)) {
        uint8_t type;
        uint8_t payload[FRAME_MAX_BODY];
        size_t  len;
        if (frame_decoder_push(&g_rx_decoder, b, &type,
                               payload, sizeof payload, &len)) {
            process_frame(type, payload, len);
        }
    }
}

static void emit_pending_events(void)
{
    /* The ISR fills each pulse record's tick before setting .pending, so
     * reading .pending first guarantees the matching tick is visible.
     * Pulse events are emitted for every trigger source. */
    if (g_pulse_start_evt.pending) {
        uint32_t tick = g_pulse_start_evt.tick;
        g_pulse_start_evt.pending = false;
        emit_pulse_event(EVT_PULSE_START, tick);
    }
    if (g_pulse_end_evt.pending) {
        uint32_t tick = g_pulse_end_evt.tick;
        g_pulse_end_evt.pending = false;
        emit_pulse_event(EVT_PULSE_END, tick);
    }
    if (g_btn_event.pending) {
        uint8_t p[2] = { g_btn_event.mask, g_btn_event.edges };
        g_btn_event.pending = false;
        tx_frame(EVT_BUTTON, p, sizeof p);
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
    frame_decoder_init(&g_rx_decoder);

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
            emit_pending_events();
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
