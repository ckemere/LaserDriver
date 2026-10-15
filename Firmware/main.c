#include "mcu.h"
#include "output_mux.h"
#include "sysctl.h"
#include "gpio.h"
#include "pwm_timer.h"
#include "tick_timers.h"
#include "uart.h"
#include "protocol.h"
#include "framing.h"
#include <stdbool.h>
#include <stdint.h>

/* -----------------------------------------------------------------------
 * LaserHAT Rev 2 bring-up firmware
 *
 * Scope: the HAT alone (no laser / e-stim module plugged in).  It brings
 * up everything on the HAT the Pi and the user can see:
 *
 *   - the five edge buttons (SW7 thumbwheel roll/roll/push, SW8 BACK,
 *     SW9 FIRE), debounced, reported as EVT_BUTTON; FIRE fires a pulse;
 *   - the status LED D7 (boot blink, 1 Hz heartbeat when idle, solid on
 *     during a pulse);
 *   - the module PWM lines on J8 (TIMA0 CCP1/CCP3, visible on a scope);
 *   - STIM OUT (J7 BNC + D9) mirrors the pulse envelope, TRIG IN (J6)
 *     and the Pi's GPIO26 fire a pulse;
 *   - the binary protocol on *both* UARTs: UART1 to the Pi (GPIO14/15)
 *     and UART0 to the USB-C CH340N, so the smoke test also runs from a
 *     laptop with no Pi.
 *
 * Architecture (unchanged from Rev 1)
 *
 * TIMG0_IRQHandler (100 kHz) is the *only* place pulse timing lives.  It
 * advances the state machine and drives the PWM / GPIO outputs.  Nothing
 * else - main loop, UART parsers, GPIO edge ISR - touches the pulse state.
 *
 * Triggers are mediated through three volatile flags consumed (and
 * cleared) by the tick ISR at the start of each tick:
 *
 *   g_uart_trigger_pending      set by a CMD_TRIGGER on either port
 *   g_button_trigger_pending    set by main loop on a FIRE press
 *   g_hw_trigger_pending        set by the BNC / Pi-GPIO edge ISR
 *                               (GROUP1_IRQHandler)
 *
 * Pulse events (EVT_PULSE_START / EVT_PULSE_END) are emitted from the
 * main loop on PulseEvent records the ISR fills at the WAITING<->TRIGGERED
 * edges, so the blocking UART writes stay out of interrupt context.
 * Events go to both ports; a command's RSP_STATUS goes back to the port
 * it came from.
 *
 * Config edits arrive in main (parser) and are read by the ISR at latch
 * time.  Each parser command writes a single g_config_live field with one
 * aligned store (atomic on M0+), and the ISR copies the struct
 * field-by-field at latch time, so no field is ever torn.
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

typedef struct {
    uint32_t pulse_dur_ticks;
    uint32_t ipi_ticks;
} EstimConfig;

static volatile EstimConfig g_estim_config_live = {
    .pulse_dur_ticks = ESTIM_DUR_DEFAULT,
    .ipi_ticks       = ESTIM_IPI_DEFAULT,
};
static EstimConfig g_estim_config_active;   /* ISR-only */

static volatile uint8_t g_mode = MODE_LASER;
static          uint8_t g_mode_active;      /* ISR-only, latched at trigger */

/*
 * Button debounce: the pin must be stable for this many 1 kHz polls
 * before a state change is accepted (10 polls = 10 ms).
 */
#define DEBOUNCE_TICKS            10u
#define NUM_BUTTONS                6u   /* 5 edge buttons + the BSL switch */
#define BUTTON_FIRE_BIT            4u   /* BUTTON5 = SW9 FIRE */

/* Idle heartbeat on D7: 50 ms on every second (in 10 us ticks). */
#define HEARTBEAT_PERIOD_TICKS 100000u
#define HEARTBEAT_ON_TICKS       5000u

/*
 * Power-on boot blink: 20 flashes of D7 at ~2.5 Hz before any timer
 * starts (~4 s).  Pure busy-wait; this is also the window in which
 * `make flash` halts the core.  ~100 ms at 32 MHz ≈ 3.2 M cycles.
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
 * at full for the hold window, then switch off. */
typedef enum {
    LASER_IDLE,
    LASER_RAMP_UP,
    LASER_HOLD_HIGH,
} LaserPhase;

/* EStim pulse pair (bring-up: only mirrored on D7 / STIM OUT; the J8
 * lines stay safe until the module firmware per spec §7 lands). */
typedef enum {
    ESTIM_IDLE,
    ESTIM_PULSE1,
    ESTIM_INTERPULSE,
    ESTIM_PULSE2,
} EstimPhase;

typedef struct {
    OverallPhase overall;
    LaserPhase   laser;
    EstimPhase   estim;
    uint32_t     ramp_step;
    uint32_t     tick_count;
} MachineState;

typedef enum {
    BTN_IDLE,       /* released */
    BTN_PRESSED,    /* confirmed pressed */
} BtnPhase;

/* -----------------------------------------------------------------------
 * Cross-context globals
 * ----------------------------------------------------------------------- */

static volatile MachineState g_state = {
    .overall = OVERALL_WAITING,
    .laser   = LASER_IDLE,
    .estim   = ESTIM_IDLE,
};
static volatile uint32_t     g_isr_ticks = 0u;

static volatile bool g_uart_trigger_pending   = false;
static volatile bool g_button_trigger_pending = false;
static volatile bool g_hw_trigger_pending     = false;

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

typedef struct {
    uint8_t mask;
    uint8_t edges;
    bool    pending;
} ButtonEvent;
static ButtonEvent g_btn_event = { 0u, 0u, false };

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
    g_config_active.ramp_ticks = g_config_live.ramp_ticks;
    g_config_active.hold_ticks = g_config_live.hold_ticks;
    g_config_active.intensity  = g_config_live.intensity;

    g_active_ticks_per_step = g_config_active.ramp_ticks / g_config_active.intensity;
    if (g_active_ticks_per_step == 0u) {
        g_active_ticks_per_step = 1u;
    }

    g_estim_config_active.pulse_dur_ticks = g_estim_config_live.pulse_dur_ticks;
    g_estim_config_active.ipi_ticks       = g_estim_config_live.ipi_ticks;
    g_mode_active = g_mode;
}

static inline void state_machine_tick(void)
{
    bool trigger = g_uart_trigger_pending || g_button_trigger_pending
                   || g_hw_trigger_pending;
    g_uart_trigger_pending   = false;
    g_button_trigger_pending = false;
    g_hw_trigger_pending     = false;

    switch (g_state.overall) {
        case OVERALL_WAITING:
            if (trigger) {
                latch_config_from_live();
                g_state.overall    = OVERALL_TRIGGERED;
                g_state.tick_count = 0u;
                if (g_mode_active == MODE_ESTIM) {
                    g_state.estim = ESTIM_PULSE1;
                } else {
                    g_state.laser     = LASER_RAMP_UP;
                    g_state.ramp_step = 0u;
                }
                g_pulse_start_evt.tick    = g_isr_ticks;
                g_pulse_start_evt.pending = true;
            }
            break;

        case OVERALL_TRIGGERED:
            g_state.tick_count++;
            if (g_mode_active == MODE_ESTIM) {
                switch (g_state.estim) {
                    case ESTIM_PULSE1:
                        if (g_state.tick_count >= g_estim_config_active.pulse_dur_ticks) {
                            g_state.tick_count = 0u;
                            g_state.estim      = ESTIM_INTERPULSE;
                        }
                        break;

                    case ESTIM_INTERPULSE:
                        if (g_state.tick_count >= g_estim_config_active.ipi_ticks) {
                            g_state.tick_count = 0u;
                            g_state.estim      = ESTIM_PULSE2;
                        }
                        break;

                    case ESTIM_PULSE2:
                        if (g_state.tick_count >= g_estim_config_active.pulse_dur_ticks) {
                            g_state.estim   = ESTIM_IDLE;
                            g_state.overall = OVERALL_WAITING;
                            g_pulse_end_evt.tick    = g_isr_ticks;
                            g_pulse_end_evt.pending = true;
                        }
                        break;

                    default:
                        break;
                }
            } else {
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
            }
            break;
    }
}

static inline void set_output_from_state(void)
{
    static uint32_t heartbeat = 0u;      /* ISR-only */

    bool     pwm    = false;   /* true = PWM mux, false = GPIO-safe */
    uint16_t duty   = 0u;      /* only meaningful when pwm */
    bool     active = false;   /* pulse envelope: D7 + STIM OUT */

    if (g_state.overall == OVERALL_WAITING) {
        /* gpio-safe, outputs off */
    } else if (g_mode_active == MODE_ESTIM) {
        active = (g_state.estim == ESTIM_PULSE1 || g_state.estim == ESTIM_PULSE2);
    } else {
        switch (g_state.laser) {
            case LASER_IDLE:
                break;

            case LASER_RAMP_UP:
                if (g_state.ramp_step != 0u) {
                    pwm  = true;
                    duty = (uint16_t)g_state.ramp_step;
                }
                active = true;
                break;

            case LASER_HOLD_HIGH:
                pwm    = true;
                duty   = g_config_active.intensity;
                active = true;
                break;

            default:
                return;   /* unreachable; leave outputs untouched */
        }
    }

    /* Idle heartbeat so the user can see the MCU is alive. */
    if (++heartbeat >= HEARTBEAT_PERIOD_TICKS) {
        heartbeat = 0u;
    }
    bool led = active || (g_state.overall == OVERALL_WAITING &&
                          heartbeat < HEARTBEAT_ON_TICKS);

    /* Apply unconditionally every tick: plain register stores, so the
     * safe module-pin state is self-healing within 10 us. */
    if (pwm) {
        laser_pins_to_pwm();
        laser_timera_set_duty(duty);
    } else {
        laser_pins_to_gpio_safe();
    }

    if (active) {
        laser_gpio_stim_out_set();
    } else {
        laser_gpio_stim_out_clear();
    }
    if (led) {
        laser_gpio_led_set();
    } else {
        laser_gpio_led_clear();
    }
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
                    if (n == BUTTON_FIRE_BIT) {
                        /* FIRE press fires a pulse. */
                        g_button_trigger_pending = true;
                    }
                } else {
                    g_btn_mask &= (uint8_t)~(1u << n);
                }
            }
        } else {
            g_btn_debounce[n] = 0u;
        }
    }

    if (g_btn_mask != old_mask) {
        g_btn_event.mask    = g_btn_mask;
        g_btn_event.edges   = (uint8_t)(g_btn_mask & (uint8_t)~old_mask);
        g_btn_event.pending = true;
    }
}

/* -----------------------------------------------------------------------
 * UART protocol — magic-word framed binary (SYNC | TYPE | payload), one
 * decoder per port.  See protocol.h and Pi/protocol.py.
 *
 *   CMD_CONFIG  i,r,h  -> RSP_STATUS    (status-as-ack)
 *   CMD_TRIGGER        -> RSP_STATUS, then EVT_PULSE_START/_END
 *   CMD_QUERY          -> RSP_STATUS
 *   (async)            -> EVT_BUTTON on any debounced button change
 * ----------------------------------------------------------------------- */

static FrameDecoder g_rx_pi;
static FrameDecoder g_rx_usb;

static void tx_frame(UartPort *port, uint8_t type, const uint8_t *payload, size_t len)
{
    uint8_t wire[3u + PROTO_MAX_PAYLOAD];
    size_t  n = frame_encode(type, payload, len, wire, sizeof wire);
    if (n != 0u) {
        uart_tx_buf(port, wire, (uint32_t)n);
    }
}

static void tx_frame_all(uint8_t type, const uint8_t *payload, size_t len)
{
    tx_frame(&g_uart_pi,  type, payload, len);
    tx_frame(&g_uart_usb, type, payload, len);
}

static void emit_status(UartPort *port)
{
    StatusPayload s = {
        .intensity        = g_config_live.intensity,
        .ramp_ticks       = g_config_live.ramp_ticks,
        .hold_ticks       = g_config_live.hold_ticks,
        .button_mask      = g_btn_mask,
        .phase = (g_state.overall == OVERALL_WAITING) ? PHASE_WAITING
                                                      : PHASE_TRIGGERED,
        .tick             = g_isr_ticks,
        .mode             = g_mode,
        .estim_dur_ticks  = g_estim_config_live.pulse_dur_ticks,
        .estim_ipi_ticks  = g_estim_config_live.ipi_ticks,
    };
    tx_frame(port, RSP_STATUS, (const uint8_t *)&s, sizeof s);
}

static void apply_estim_config(const uint8_t *payload)
{
    const EstimConfigPayload *c = (const EstimConfigPayload *)payload;
    if (c->pulse_dur_ticks < ESTIM_DUR_MIN || c->pulse_dur_ticks > ESTIM_DUR_MAX ||
        c->ipi_ticks < ESTIM_IPI_MIN || c->ipi_ticks > ESTIM_IPI_MAX) {
        return;
    }
    g_estim_config_live.pulse_dur_ticks = c->pulse_dur_ticks;
    g_estim_config_live.ipi_ticks       = c->ipi_ticks;
}

static void apply_config(const uint8_t *payload)
{
    const ConfigPayload *c = (const ConfigPayload *)payload;
    if (c->intensity < INTENSITY_MIN || c->intensity > INTENSITY_MAX ||
        c->ramp_ticks < RAMP_TICKS_MIN || c->ramp_ticks > RAMP_TICKS_MAX ||
        c->hold_ticks < HOLD_TICKS_MIN || c->hold_ticks > HOLD_TICKS_MAX) {
        return;   /* out of range: unchanged; the STATUS echo shows it */
    }
    g_config_live.intensity  = c->intensity;
    g_config_live.ramp_ticks = c->ramp_ticks;
    g_config_live.hold_ticks = c->hold_ticks;
}

static void process_frame(UartPort *port, uint8_t type,
                          const uint8_t *payload, size_t len)
{
    switch (type) {
        case CMD_CONFIG:
            if (len == CMD_CONFIG_LEN) {
                apply_config(payload);
            }
            emit_status(port);
            break;

        case CMD_TRIGGER:
            if (g_state.overall == OVERALL_WAITING) {
                g_uart_trigger_pending = true;
            }
            emit_status(port);
            break;

        case CMD_QUERY:
            emit_status(port);
            break;

        case CMD_SET_MODE:
            if (len == CMD_SET_MODE_LEN) {
                uint8_t m = payload[0];
                if (m == MODE_LASER || m == MODE_ESTIM) {
                    g_mode = m;
                    laser_pins_to_gpio_safe();
                }
            }
            emit_status(port);
            break;

        case CMD_ESTIM_CONFIG:
            if (len == CMD_ESTIM_CONFIG_LEN) {
                apply_estim_config(payload);
            }
            emit_status(port);
            break;

        default:
            break;
    }
}

static void drain_uart(UartPort *port, FrameDecoder *dec)
{
    uint8_t b;
    while (uart_rx_pop(port, &b)) {
        uint8_t type;
        uint8_t payload[PROTO_MAX_PAYLOAD];
        size_t  len;
        if (frame_decoder_push(dec, b, &type, payload, sizeof payload, &len)) {
            process_frame(port, type, payload, len);
        }
    }
}

static void emit_pending_events(void)
{
    if (g_pulse_start_evt.pending) {
        uint32_t tick = g_pulse_start_evt.tick;
        g_pulse_start_evt.pending = false;
        tx_frame_all(EVT_PULSE_START, (const uint8_t *)&tick, sizeof tick);
    }
    if (g_pulse_end_evt.pending) {
        uint32_t tick = g_pulse_end_evt.tick;
        g_pulse_end_evt.pending = false;
        tx_frame_all(EVT_PULSE_END, (const uint8_t *)&tick, sizeof tick);
    }
    if (g_btn_event.pending) {
        uint8_t p[2] = { g_btn_event.mask, g_btn_event.edges };
        g_btn_event.pending = false;
        tx_frame_all(EVT_BUTTON, p, sizeof p);
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

    /* Boot indicator on D7 before any timer runs — also the window in
     * which `make flash` halts the core over SWD. */
    for (uint32_t n = 0u; n < BOOT_BLINK_FLASHES; n++) {
        laser_gpio_led_set();
        delay_cycles(BOOT_BLINK_HALF_CYCLES);
        laser_gpio_led_clear();
        delay_cycles(BOOT_BLINK_HALF_CYCLES);
    }

    laser_timera_init();
    laser_timerg_init_tick();
    laser_timerg_init_housekeeping();
    uart_init(&g_uart_pi,  UART1);
    uart_init(&g_uart_usb, UART0);
    frame_decoder_init(&g_rx_pi);
    frame_decoder_init(&g_rx_usb);

    laser_pins_to_gpio_safe();
    laser_timera_start();

    /* TIMG0 runs the state machine at the highest priority; TIMG6
     * housekeeping lower so it can never delay a pulse tick. */
    NVIC_SetPriority(TIMG0_INT_IRQn, 0);
    NVIC_SetPriority(TIMG6_INT_IRQn, 3);
    NVIC_EnableIRQ(TIMG0_INT_IRQn);
    NVIC_EnableIRQ(TIMG6_INT_IRQn);
    laser_timerg_start_tick();
    laser_timerg_start_housekeeping();

    NVIC_ClearPendingIRQ(UART1_INT_IRQn);
    NVIC_EnableIRQ(UART1_INT_IRQn);
    NVIC_ClearPendingIRQ(UART0_INT_IRQn);
    NVIC_EnableIRQ(UART0_INT_IRQn);

    /* GPIOA IRQ (shared GROUP1 vector) for the BNC and Pi trigger edges. */
    NVIC_SetPriority(GPIOA_INT_IRQn, 1);
    NVIC_ClearPendingIRQ(GPIOA_INT_IRQn);
    NVIC_EnableIRQ(GPIOA_INT_IRQn);

    while (1) {
        if (g_housekeeping_due) {
            g_housekeeping_due = false;
            drain_uart(&g_uart_pi,  &g_rx_pi);
            drain_uart(&g_uart_usb, &g_rx_usb);
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

/* GPIOA shares the INT_GROUP1 vector; we're the only GROUP1 source. */
void GROUP1_IRQHandler(void)
{
    uint32_t mis = GPIOA->CPU_INT.MIS;
    uint32_t fired_mask = mis & (BOARD_STIM_IN_PIN | BOARD_PI_TRIGGER_PIN);
    if (fired_mask) {
        GPIOA->CPU_INT.ICLR = fired_mask;
        g_hw_trigger_pending = true;
    }
}
