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
 * Pulse configuration
 *
 *   intensity   peak PWM duty (1..PWM_PERIOD_COUNTS); sets the
 *               number of ramp steps and the held duty at the peak.
 *   ramp_ticks  total duration of the ramp-up phase (and ramp-down).
 *               Each step takes ramp_ticks / intensity ticks
 *               (rounded down, minimum 1 tick).
 *   hold_ticks  duration of the peak hold (also the dead time at the
 *               trailing edge before returning to WAITING).
 *
 * One TIMG0 tick = 10 µs at 100 kHz.
 *
 * Two copies of the struct are kept: g_config_live is what the UART
 * protocol mutates; g_config_active is what the state machine reads.
 * The live copy is snapshotted into active on every WAITING -> TRIGGERED
 * transition, so a config change mid-pulse cannot glitch a running
 * waveform.
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

static PulseConfig g_config_live = {
    .ramp_ticks = RAMP_TICKS_DEFAULT,
    .hold_ticks = HOLD_TICKS_DEFAULT,
    .intensity  = INTENSITY_DEFAULT,
};
static PulseConfig g_config_active;
static uint32_t    g_active_ticks_per_step;   /* derived at latch time */

/*
 * Boot-side init: applied once at the analog current limit and never
 * touched again at runtime.
 */
#define DAC_SETPOINT            500u

/*
 * Button debounce: require the pin to be stable for this many ticks
 * before accepting a state change.  At 100 kHz, 1000 ticks = 10 ms.
 */
#define DEBOUNCE_TICKS          1000u
#define NUM_BUTTONS                4u

/*
 * Power-on boot blink: 20 toggles of STIM_MIRROR at ~5 Hz before the
 * state machine starts.  Pure busy-wait, no timer dependence.
 *   100 ms at 32 MHz BUSCLK ≈ 3.2 M cycles.
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
    BTN_IDLE,       /* pin LOW (released) */
    BTN_PRESSED,    /* confirmed pressed */
} BtnPhase;

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
    BtnPhase     btn_phase[NUM_BUTTONS];
    uint16_t     btn_debounce[NUM_BUTTONS];
    uint8_t      btn_mask;    /* debounced; bit n = button n+1 pressed */
} MachineState;

/* -----------------------------------------------------------------------
 * Hardware helpers
 * ----------------------------------------------------------------------- */

/* Incremented only in TIMG0 ISR; read in get_next_state(). */
static volatile uint32_t isr_ticks = 0;

/* Set true by the parser when a 't' command is received; consumed
 * (and cleared) by get_next_state().  Bool reads/writes are atomic
 * on Cortex-M0+ so no further protection needed. */
static volatile bool g_uart_trigger_request = false;

/* True while a pulse initiated by a 't' command is running; gates the
 * "OK pulse start/end" ACK emission. */
static bool g_pulse_via_uart = false;
static uint32_t g_pulse_start_tick = 0;

/* Busy-wait roughly `cycles` BUSCLK cycles.  Used only for the boot
 * blink.  ~3 cycles per loop iteration on Cortex-M0+. */
static void delay_cycles(uint32_t cycles)
{
    volatile uint32_t i = cycles / 3u;
    while (i--) { /* nop */ }
}

/* -----------------------------------------------------------------------
 * State machine
 * ----------------------------------------------------------------------- */

static void latch_config(void)
{
    g_config_active = g_config_live;
    g_active_ticks_per_step =
        g_config_active.ramp_ticks / g_config_active.intensity;
    if (g_active_ticks_per_step == 0u) {
        g_active_ticks_per_step = 1u;
    }
}

/*
 * Advance state by one tick.  Returns state unchanged if no new TIMG0
 * tick has fired (guards against spurious WFI wakeups from other
 * sources like UART RX).
 */
static MachineState get_next_state(MachineState s)
{
    static uint32_t last_tick = 0;
    if (isr_ticks == last_tick)
        return s;
    last_tick++;

    /* --- Per-button debounce (active-high, all 4 buttons) --- */
    uint8_t raw_mask = laser_gpio_read_buttons_raw();
    bool    btn1_released_edge = false;

    for (unsigned n = 0; n < NUM_BUTTONS; n++) {
        bool raw_pressed = (raw_mask >> n) & 1u;
        bool now_pressed = (s.btn_phase[n] == BTN_PRESSED);

        if (raw_pressed != now_pressed) {
            s.btn_debounce[n]++;
            if (s.btn_debounce[n] >= DEBOUNCE_TICKS) {
                s.btn_phase[n] = raw_pressed ? BTN_PRESSED : BTN_IDLE;
                s.btn_debounce[n] = 0;
                if (n == 0u && !raw_pressed) {
                    /* BUTTON1 release fires a trigger. */
                    btn1_released_edge = true;
                }
                /* Update mask bit. */
                if (raw_pressed) {
                    s.btn_mask |= (uint8_t)(1u << n);
                } else {
                    s.btn_mask &= (uint8_t)~(1u << n);
                }
            }
        } else {
            s.btn_debounce[n] = 0;
        }
    }

    /* --- Combine trigger sources --- */
    bool trigger_from_uart = g_uart_trigger_request;
    g_uart_trigger_request = false;
    bool trigger = btn1_released_edge || trigger_from_uart;

    /* --- Overall and laser phases --- */
    switch (s.overall) {
        case OVERALL_WAITING:
            if (trigger) {
                latch_config();
                s.overall    = OVERALL_TRIGGERED;
                s.laser      = LASER_RAMP_UP;
                s.ramp_step  = 0;
                s.tick_count = 0;
                if (trigger_from_uart) {
                    g_pulse_via_uart   = true;
                    g_pulse_start_tick = last_tick;
                }
            }
            break;

        case OVERALL_TRIGGERED:
            s.tick_count++;
            switch (s.laser) {
                case LASER_RAMP_UP:
                    if (s.tick_count >= g_active_ticks_per_step) {
                        s.tick_count = 0;
                        s.ramp_step++;
                        if (s.ramp_step >= g_config_active.intensity) {
                            s.tick_count = 0;
                            s.laser      = LASER_HOLD_HIGH;
                        }
                    }
                    break;

                case LASER_HOLD_HIGH:
                    if (s.tick_count >= g_config_active.hold_ticks) {
                        s.tick_count = 0;
                        s.ramp_step  = g_config_active.intensity;
                        s.laser      = LASER_RAMP_DOWN;
                    }
                    break;

                case LASER_RAMP_DOWN:
                    if (s.tick_count >= g_active_ticks_per_step) {
                        s.tick_count = 0;
                        s.ramp_step--;
                        if (s.ramp_step == 0) {
                            s.tick_count = 0;
                            s.laser      = LASER_HOLD_LOW;
                        }
                    }
                    break;

                case LASER_HOLD_LOW:
                    if (s.tick_count >= g_config_active.hold_ticks) {
                        s.tick_count = 0;
                        s.ramp_step  = 0;
                        s.laser      = LASER_IDLE;
                        s.overall    = OVERALL_WAITING;
                    }
                    break;

                default:
                    break;
            }
            break;
    }

    return s;
}

/*
 * Drive hardware to match the current state.
 * - Waiting:   laser off, STIM_MIRROR off.
 * - Triggered: PWM follows the waveform; STIM_MIRROR mirrors laser-on.
 */
static void set_output(MachineState s)
{
    if (s.overall == OVERALL_WAITING) {
        laser_pins_to_gpio_safe();
        laser_gpio_stim_mirror_clear();
        return;
    }

    switch (s.laser) {
        case LASER_IDLE:
        case LASER_HOLD_LOW:
            laser_pins_to_gpio_safe();
            laser_gpio_stim_mirror_clear();
            break;

        case LASER_RAMP_UP:
        case LASER_RAMP_DOWN:
            if (s.ramp_step == 0) {
                laser_pins_to_gpio_safe();
            } else {
                laser_pins_to_pwm();
                laser_timera_set_duty(s.ramp_step);
            }
            laser_gpio_stim_mirror_set();
            break;

        case LASER_HOLD_HIGH:
            laser_pins_to_pwm();
            laser_timera_set_duty(g_config_active.intensity);
            laser_gpio_stim_mirror_set();
            break;

        default:
            break;
    }
}

/* -----------------------------------------------------------------------
 * UART protocol
 *
 *   i N    set intensity (1..320, peak PWM duty)
 *   r N    set ramp-up ticks
 *   h N    set hold ticks
 *   t      trigger one pulse; ACK is "OK pulse start=..." + "OK pulse end=..."
 *   ?      query state — one line:
 *          OK i=N r=N h=N b=BBBB phase=W|T tick=TTT
 *
 * Lines are \n-terminated.  Whitespace tolerated between verb and arg.
 * Unknown verbs or out-of-range args -> ERR <reason>.
 * ----------------------------------------------------------------------- */

#define LINE_BUF_SIZE   64u

static char  line_buf[LINE_BUF_SIZE];
static uint8_t line_len = 0;
static bool   line_overflowed = false;

static bool parse_decimal(const char *s, uint32_t *out)
{
    uint32_t v = 0;
    bool got_digit = false;
    while (*s == ' ' || *s == '\t') s++;
    if (*s == '\0' || *s == '\r') return false;
    while (*s >= '0' && *s <= '9') {
        v = v * 10u + (uint32_t)(*s - '0');
        got_digit = true;
        s++;
    }
    while (*s == ' ' || *s == '\t' || *s == '\r') s++;
    if (*s != '\0') return false;          /* trailing garbage */
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

static void emit_status(const MachineState *s)
{
    laser_uart_tx_str("OK i=");
    laser_uart_tx_u32(g_config_live.intensity);
    laser_uart_tx_str(" r=");
    laser_uart_tx_u32(g_config_live.ramp_ticks);
    laser_uart_tx_str(" h=");
    laser_uart_tx_u32(g_config_live.hold_ticks);
    laser_uart_tx_str(" b=");
    laser_uart_tx_u32(s->btn_mask);
    laser_uart_tx_str(" phase=");
    laser_uart_tx_byte(s->overall == OVERALL_WAITING ? 'W' : 'T');
    laser_uart_tx_str(" tick=");
    laser_uart_tx_u32(isr_ticks);
    laser_uart_tx_byte('\n');
}

static void process_line(const MachineState *s)
{
    /* Strip leading whitespace. */
    const char *p = line_buf;
    while (*p == ' ' || *p == '\t') p++;
    if (*p == '\0' || *p == '\r') return;     /* blank line */

    char verb = *p++;
    uint32_t arg = 0;

    switch (verb) {
        case 'i':
            if (!parse_decimal(p, &arg)) { emit_err("bad_arg"); return; }
            if (arg < INTENSITY_MIN || arg > INTENSITY_MAX) {
                emit_err("range"); return;
            }
            g_config_live.intensity = (uint16_t)arg;
            emit_ok_kv('i', arg);
            break;

        case 'r':
            if (!parse_decimal(p, &arg)) { emit_err("bad_arg"); return; }
            if (arg < RAMP_TICKS_MIN || arg > RAMP_TICKS_MAX) {
                emit_err("range"); return;
            }
            g_config_live.ramp_ticks = arg;
            emit_ok_kv('r', arg);
            break;

        case 'h':
            if (!parse_decimal(p, &arg)) { emit_err("bad_arg"); return; }
            if (arg < HOLD_TICKS_MIN || arg > HOLD_TICKS_MAX) {
                emit_err("range"); return;
            }
            g_config_live.hold_ticks = arg;
            emit_ok_kv('h', arg);
            break;

        case 't':
            if (s->overall != OVERALL_WAITING) {
                emit_err("busy");
                return;
            }
            g_uart_trigger_request = true;
            /* No immediate ACK — "OK pulse start=..." follows when the
             * state machine actually transitions. */
            break;

        case '?':
            emit_status(s);
            break;

        default:
            emit_err("unknown");
            break;
    }
}

static void drain_uart(const MachineState *s)
{
    uint8_t b;
    while (laser_uart_rx_pop(&b)) {
        if (b == '\n') {
            if (line_overflowed) {
                emit_err("overflow");
                line_overflowed = false;
            } else {
                line_buf[line_len] = '\0';
                process_line(s);
            }
            line_len = 0;
        } else if (line_len + 1u >= LINE_BUF_SIZE) {
            line_overflowed = true;
        } else {
            line_buf[line_len++] = (char)b;
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

    /* Power-on boot indicator.  Pure delay loop before any timer fires. */
    for (uint32_t n = 0; n < BOOT_BLINK_FLASHES; n++) {
        laser_gpio_stim_mirror_set();
        delay_cycles(BOOT_BLINK_HALF_CYCLES);
        laser_gpio_stim_mirror_clear();
        delay_cycles(BOOT_BLINK_HALF_CYCLES);
    }

    laser_timera_init();
    laser_timerg_init();
    laser_dac_init();
    laser_dac_write12(DAC_SETPOINT);
    laser_dac_enable();
    laser_uart_init();

    laser_pins_to_gpio_safe();
    laser_timera_start();

    NVIC_SetPriority(TIMG0_INT_IRQn, 0);
    NVIC_EnableIRQ(TIMG0_INT_IRQn);
    laser_timerg_start();

    NVIC_ClearPendingIRQ(UART0_INT_IRQn);
    NVIC_EnableIRQ(UART0_INT_IRQn);

    MachineState state = { 0 };
    state.overall = OVERALL_WAITING;

    OverallPhase prev_overall = state.overall;

    while (1) {
        /* Service UART input first — short and bounded. */
        drain_uart(&state);

        state = get_next_state(state);
        set_output(state);

        /* Emit pulse-event ACKs on overall-phase transitions, but only
         * if the running pulse was initiated by a 't' command. */
        if (prev_overall == OVERALL_WAITING && state.overall == OVERALL_TRIGGERED) {
            if (g_pulse_via_uart) {
                emit_pulse_event("start", g_pulse_start_tick);
            }
        } else if (prev_overall == OVERALL_TRIGGERED && state.overall == OVERALL_WAITING) {
            if (g_pulse_via_uart) {
                emit_pulse_event("end", isr_ticks);
                g_pulse_via_uart = false;
            }
        }
        prev_overall = state.overall;

        __WFI();
    }
}

void TIMG0_IRQHandler(void)
{
    if (laser_timerg_ack() == GPTIMER_CPU_INT_IIDX_STAT_Z) {
        isr_ticks++;
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
