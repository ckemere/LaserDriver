#include "mcu.h"
#include "output_mux.h"
#include "sysctl.h"
#include "gpio.h"
#include "pwm_timer.h"
#include "tick_timers.h"
#include "dac.h"
#include "adc.h"
#include "module.h"
#include "uart.h"
#include "protocol.h"
#include "framing.h"
#include "version.h"
#include <stdbool.h>
#include <stdint.h>

/* -----------------------------------------------------------------------
 * LaserHAT Rev 2 firmware — HAT + laser module + e-stim module
 *
 *   - the five edge buttons (SW7 thumbwheel roll/roll/push, SW8 BACK,
 *     SW9 FIRE), debounced, reported as EVT_BUTTON; FIRE fires a pulse;
 *   - the status LED D7 (boot blink, 1 Hz heartbeat when idle, solid
 *     during a pulse, 5 Hz blink while a module fault is latched);
 *   - LASER mode: TIMA0 PWM on J8 (CCP1 = laser switch, CCP3 = dummy
 *     switch complement), DAC0 on J9.3 sets the module's current (IREF)
 *     for the duration of a pulse and is zero between pulses (the module's
 *     cascode Q1 must not carry dummy current continuously, REV2_NOTES),
 *     ADC1 reads the photodiode (J9.4) and the compliance rail (J9.5);
 *   - ESTIM mode (spec §7): EN / CATH / RELEASE driven as GPIOs from the
 *     tick ISR (10 µs grid) — RELEASE + CATH, EN pulse, CATH low in the
 *     gap, EN pulse, RELEASE held ~200 µs then dropped for 200 µs;
 *     amplitude = DAC60501 on the module over bit-banged I2C (J9.4/J9.5)
 *     between trains; FAULT_n (J8.3) falling edge kills the outputs
 *     within a few µs and latches a fault until CMD_CLEAR_FAULT;
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
 * else - main loop, UART parsers, GPIO edge ISR - touches the pulse state;
 * the one exception is the FAULT_n edge in GROUP1_IRQHandler, which may
 * force the outputs off and set the fault latch (the tick then aborts).
 *
 * Triggers are mediated through three volatile flags consumed (and
 * cleared) by the tick ISR at the start of each tick:
 *
 *   g_uart_trigger_pending      set by a CMD_TRIGGER on either port
 *   g_button_trigger_pending    set by main loop on a FIRE press
 *   g_hw_trigger_pending        set by the BNC / Pi-GPIO edge ISR
 *                               (GROUP1_IRQHandler)
 *
 * Pulse events (EVT_PULSE_START / EVT_PULSE_END / EVT_FAULT) are emitted
 * from the main loop on records the ISRs fill, so the blocking UART
 * writes stay out of interrupt context.  Events go to both ports; a
 * command's RSP_STATUS goes back to the port it came from.
 *
 * Config edits arrive in main (parser) and are read by the ISR at latch
 * time.  Each parser command writes a single live field with one aligned
 * store (atomic on M0+), and the ISR copies the struct field-by-field at
 * latch time, so no field is ever torn.
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

/* E-stim sequencing around the pulse pair (spec §7), in 10 µs ticks. */
#define ESTIM_PRE_TICKS           1u    /* RELEASE + CATH lead EN by >= 1 µs */
#define ESTIM_POST_TICKS         20u    /* RELEASE stays high ~200 µs after the pair */
#define ESTIM_RESET_TICKS        20u    /* RELEASE low >= 200 µs (electrode reset) */

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

/* Module setpoints (main-owned; the laser one is written to DAC0 by the
 * tick ISR at pulse start and zeroed at pulse end, the e-stim one is
 * written to the module's DAC between trains). */
static volatile uint16_t g_laser_dac = LASER_DAC_DEFAULT;
static volatile uint16_t g_estim_dac = ESTIM_DAC_DEFAULT;
static volatile bool     g_estim_dac_pending = true;
static volatile bool     g_estim_ready = false;   /* DAC60501 GAIN init acked */
static volatile bool     g_i2c_error   = false;   /* last DAC write NACKed */

/* Fault handling.  The FAULT_n falling-edge interrupt is one-shot: armed
 * once FAULT_n has been high for 2 ms (module ready or absent), masked
 * again by its own handler when it fires, and re-armed only after
 * CMD_CLEAR_FAULT has cleared the latch *and* the line has been high for
 * another 2 ms.  A chattering line (e.g. an e-stim module whose converter
 * is folding back) therefore costs one interrupt per fault instead of
 * re-firing at top priority and starving the tick ISR and main.  The
 * latch is set by that handler or by the tick ISR seeing FAULT_n low
 * mid-train (the backstop that still works while the interrupt is masked),
 * and cleared only by CMD_CLEAR_FAULT. */
static volatile bool g_fault_armed   = false;
static volatile bool g_fault_latched = false;

/* Laser-mode readbacks (main-owned). */
static volatile uint16_t g_adc_pd   = 0u;
static volatile uint16_t g_adc_comp = 0u;

/*
 * Button debounce: the pin must be stable for this many 1 kHz polls
 * before a state change is accepted (10 polls = 10 ms).
 */
#define DEBOUNCE_TICKS            10u
#define NUM_BUTTONS                6u   /* 5 edge buttons + the BSL switch */
#define BUTTON_FIRE_BIT            4u   /* BUTTON5 = SW9 FIRE */

/* Idle heartbeat on D7: 50 ms on every second (in 10 us ticks); fault
 * indication: 5 Hz square wave. */
#define HEARTBEAT_PERIOD_TICKS 100000u
#define HEARTBEAT_ON_TICKS       5000u
#define FAULT_BLINK_HALF_TICKS  10000u

/*
 * Power-on boot blink: 10 flashes of D7 at ~2.5 Hz before any timer
 * starts (~2 s).  Pure busy-wait.  It is a "just (re)booted" indicator;
 * since Rev 2 keeps PA19/PA20 as dedicated SWD pins it is no longer the
 * only window in which `make flash` can attach (Rev 1 reclaimed SWDIO as
 * a GPIO after the blink).  It still gives OpenOCD, launched right after
 * the power-cycle, a busy-waiting core to halt rather than one in WFI.
 * ~100 ms at 32 MHz ≈ 3.2 M cycles per half period.
 */
#define BOOT_BLINK_FLASHES      10u
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

/* EStim pulse pair with the RELEASE envelope of spec §7. */
typedef enum {
    ESTIM_IDLE,
    ESTIM_PRE,          /* RELEASE high, CATH high; EN still low */
    ESTIM_PULSE1,       /* EN high (cathodic) */
    ESTIM_INTERPULSE,   /* EN low, CATH low */
    ESTIM_PULSE2,       /* EN high (anodic) */
    ESTIM_POST,         /* EN low, RELEASE still high */
    ESTIM_RESET,        /* RELEASE low: electrode shorted / amplifier re-centred */
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
} TickEvent;

static volatile TickEvent g_pulse_start_evt = { 0u, false };
static volatile TickEvent g_pulse_end_evt   = { 0u, false };
static volatile TickEvent g_fault_evt       = { 0u, false };

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
 * Fault kill — callable from any ISR: plain register stores only.
 * ----------------------------------------------------------------------- */

static inline void fault_kill_outputs(void)
{
    laser_pins_to_gpio_safe();      /* EN / PWM_A low, CATH / PWM_B idle */
    module_release_clear();         /* RELEASE low (no effect in laser mode) */
}

static inline void fault_latch(void)
{
    fault_kill_outputs();
    if (!g_fault_latched) {
        g_fault_latched     = true;
        g_fault_evt.tick    = g_isr_ticks;
        g_fault_evt.pending = true;
    }
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

static inline void abort_to_waiting(void)
{
    if (g_mode_active == MODE_LASER) {
        laser_dac_write12(0u);          /* no dummy current between pulses */
    }
    g_state.laser     = LASER_IDLE;
    g_state.estim     = ESTIM_IDLE;
    g_state.ramp_step = 0u;
    g_state.overall   = OVERALL_WAITING;
    g_pulse_end_evt.tick    = g_isr_ticks;
    g_pulse_end_evt.pending = true;
}

static inline void state_machine_tick(void)
{
    bool trigger = g_uart_trigger_pending || g_button_trigger_pending
                   || g_hw_trigger_pending;
    g_uart_trigger_pending   = false;
    g_button_trigger_pending = false;
    g_hw_trigger_pending     = false;

    /* Backstop for the FAULT_n edge interrupt: low mid-train = fault. */
    if (g_state.overall == OVERALL_TRIGGERED && g_fault_armed &&
        !laser_gpio_fault_n_high()) {
        fault_latch();
    }
    if (g_fault_latched && g_state.overall == OVERALL_TRIGGERED) {
        abort_to_waiting();
        return;
    }

    switch (g_state.overall) {
        case OVERALL_WAITING:
            /* E-stim trains need the module's isolated side up (FAULT_n
             * high; also high with no module at all, via the pull-up). */
            if (trigger && !g_fault_latched &&
                (g_mode != MODE_ESTIM || laser_gpio_fault_n_high())) {
                latch_config_from_live();
                g_state.overall    = OVERALL_TRIGGERED;
                g_state.tick_count = 0u;
                if (g_mode_active == MODE_ESTIM) {
                    g_state.estim = ESTIM_PRE;
                } else {
                    g_state.laser     = LASER_RAMP_UP;
                    g_state.ramp_step = 0u;
                    laser_dac_write12(g_laser_dac);   /* IREF up; the first
                                                         ramp step is dummy-only */
                }
                g_pulse_start_evt.tick    = g_isr_ticks;
                g_pulse_start_evt.pending = true;
            }
            break;

        case OVERALL_TRIGGERED:
            g_state.tick_count++;
            if (g_mode_active == MODE_ESTIM) {
                switch (g_state.estim) {
                    case ESTIM_PRE:
                        if (g_state.tick_count >= ESTIM_PRE_TICKS) {
                            g_state.tick_count = 0u;
                            g_state.estim      = ESTIM_PULSE1;
                        }
                        break;

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
                            g_state.tick_count = 0u;
                            g_state.estim      = ESTIM_POST;
                        }
                        break;

                    case ESTIM_POST:
                        if (g_state.tick_count >= ESTIM_POST_TICKS) {
                            g_state.tick_count = 0u;
                            g_state.estim      = ESTIM_RESET;
                        }
                        break;

                    case ESTIM_RESET:
                        if (g_state.tick_count >= ESTIM_RESET_TICKS) {
                            g_state.tick_count = 0u;
                            abort_to_waiting();     /* normal end of the pair */
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
                            abort_to_waiting();     /* normal end of the pulse */
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

    bool     pwm    = false;   /* true = PWM mux, false = GPIO-safe (laser) */
    uint16_t duty   = 0u;      /* only meaningful when pwm */
    bool     active = false;   /* stimulus on: D7 + STIM OUT */
    bool     en = false, cath = false, release = false;   /* e-stim lines */
    bool     estim_drive = false;   /* drive EN/CATH/RELEASE as GPIOs this tick */

    if (g_state.overall == OVERALL_WAITING) {
        /* gpio-safe, outputs off */
    } else if (g_mode_active == MODE_ESTIM) {
        estim_drive = true;
        switch (g_state.estim) {
            case ESTIM_PRE:        release = true; cath = true;            break;
            case ESTIM_PULSE1:     release = true; cath = true; en = true; active = true; break;
            case ESTIM_INTERPULSE: release = true;                         break;
            case ESTIM_PULSE2:     release = true; en = true; active = true; break;
            case ESTIM_POST:       release = true;                         break;
            case ESTIM_RESET:                                              break;
            default:               estim_drive = false;                    break;
        }
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

    if (g_fault_latched) {
        pwm = false; estim_drive = false; active = false;
    }

    /* D7: solid while stimulating, 5 Hz while a fault is latched, 1 Hz
     * heartbeat blip when idle. */
    if (++heartbeat >= HEARTBEAT_PERIOD_TICKS) {
        heartbeat = 0u;
    }
    bool led;
    if (active) {
        led = true;
    } else if (g_fault_latched) {
        led = (heartbeat / FAULT_BLINK_HALF_TICKS) & 1u;
    } else {
        led = (g_state.overall == OVERALL_WAITING && heartbeat < HEARTBEAT_ON_TICKS);
    }

    /* Apply unconditionally every tick: plain register stores, so the
     * safe module-pin state is self-healing within 10 us. */
    if (estim_drive) {
        /* Pins are in their GPIO mux in ESTIM mode (never switched to TIMA0). */
        if (release) { module_release_set(); } else { module_release_clear(); }
        if (cath)    { laser_gpio_estim_cath_set(); } else { laser_gpio_estim_cath_clear(); }
        if (en)      { laser_gpio_estim_en_set(); }   else { laser_gpio_estim_en_clear(); }
    } else if (pwm) {
        laser_pins_to_pwm();
        laser_timera_set_duty(duty);
    } else {
        laser_pins_to_gpio_safe();
        module_release_clear();
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
 * Mode switch (main loop, only while WAITING)
 * ----------------------------------------------------------------------- */

static void enter_mode(uint8_t mode)
{
    g_mode = mode;
    laser_pins_set_b_idle_high(mode == MODE_LASER);
    laser_pins_to_gpio_safe();
    g_estim_ready = false;
    g_i2c_error   = false;
    g_adc_pd   = 0u;
    g_adc_comp = 0u;

    if (mode == MODE_LASER) {
        module_laser_pins();            /* PA15 DAC, PA17/PA22 ADC */
        laser_dac_write12(0u);          /* setpoint goes out at pulse start */
        laser_dac_enable();
    } else {
        laser_dac_disable();
        module_estim_pins();            /* PA15 RELEASE, PA17/PA22 I2C */
        g_estim_dac_pending = true;     /* (re)program the module DAC when it is up */
    }
}

/* -----------------------------------------------------------------------
 * Housekeeping (1 kHz, main loop): fault arming, e-stim DAC, ADC readback
 * ----------------------------------------------------------------------- */

#define ESTIM_RETRY_MS   100u
#define ADC_PERIOD_MS     10u

static void module_housekeeping(void)
{
    static uint8_t  fault_high_ms = 0u;
    static uint8_t  estim_retry_ms = 0u;
    static uint8_t  adc_ms = 0u;
    static bool     adc_busy = false;

    bool fn_high = laser_gpio_fault_n_high();
    if (fn_high) {
        if (fault_high_ms < 255u) {
            fault_high_ms++;
        }
    } else {
        fault_high_ms = 0u;
        g_estim_ready = false;          /* isolated side down: DAC forgets its GAIN */
    }
    /* (Re-)arm the one-shot edge interrupt: never while a fault is still
     * latched (CMD_CLEAR_FAULT first), and only after 2 ms of FAULT_n high. */
    if (!g_fault_armed && !g_fault_latched && fault_high_ms >= 2u) {
        g_fault_armed = true;
        laser_gpio_fault_irq_enable();
    }

    if (g_mode == MODE_ESTIM) {
        adc_busy = false;
        /* Module DAC traffic only between trains and only with the module
         * powered (FAULT_n high for >= 2 ms covers the 250 µs of spec §7). */
        if (g_state.overall == OVERALL_WAITING && fn_high && fault_high_ms >= 2u) {
            if (!g_estim_ready) {
                if (estim_retry_ms == 0u) {
                    if (module_estim_dac_init()) {
                        g_estim_ready       = true;
                        g_i2c_error         = false;
                        g_estim_dac_pending = true;
                    } else {
                        g_i2c_error    = true;
                        estim_retry_ms = ESTIM_RETRY_MS;
                    }
                } else {
                    estim_retry_ms--;
                }
            }
            if (g_estim_ready && g_estim_dac_pending) {
                if (module_estim_dac_write(g_estim_dac)) {
                    g_estim_dac_pending = false;
                    g_i2c_error         = false;
                } else {
                    g_i2c_error    = true;
                    g_estim_ready  = false;
                    estim_retry_ms = ESTIM_RETRY_MS;
                }
            }
        }
    } else {
        /* Laser readbacks every ADC_PERIOD_MS: start one tick, read the next. */
        if (adc_busy) {
            uint16_t pd, comp;
            if (laser_adc_read(&pd, &comp)) {
                g_adc_pd   = pd;
                g_adc_comp = comp;
                adc_busy   = false;
            }
        } else if (++adc_ms >= ADC_PERIOD_MS) {
            adc_ms = 0u;
            laser_adc_start();
            adc_busy = true;
        }
    }
}

static uint8_t module_flags(void)
{
    uint8_t f = 0u;
    if (!laser_gpio_fault_n_high()) { f |= MODULE_FAULT_N_LOW; }
    if (g_fault_latched)            { f |= MODULE_FAULT_LATCHED; }
    if (g_estim_ready)              { f |= MODULE_ESTIM_READY; }
    if (g_i2c_error)                { f |= MODULE_I2C_ERROR; }
    return f;
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
 *   CMD_CONFIG  i,r,h   -> RSP_STATUS    (status-as-ack)
 *   CMD_TRIGGER         -> RSP_STATUS, then EVT_PULSE_START/_END
 *   CMD_QUERY           -> RSP_STATUS
 *   CMD_SET_MODE        -> RSP_STATUS    (refused while a pulse runs)
 *   CMD_ESTIM_CONFIG    -> RSP_STATUS
 *   CMD_LASER_CURRENT   -> RSP_STATUS    (DAC0 code for the next pulse; mid-pulse: now)
 *   CMD_ESTIM_CURRENT   -> RSP_STATUS    (module DAC code, written between trains)
 *   CMD_CLEAR_FAULT     -> RSP_STATUS
 *   CMD_GET_VERSION     -> RSP_VERSION   (protocol number + build version string;
 *                                         the broker checks both against its package)
 *   (async)             -> EVT_BUTTON on any debounced button change,
 *                          EVT_FAULT when a module fault latches
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
        .laser_dac        = g_laser_dac,
        .estim_dac        = g_estim_dac,
        .module           = module_flags(),
        .adc_pd           = g_adc_pd,
        .adc_comp         = g_adc_comp,
    };
    tx_frame(port, RSP_STATUS, (const uint8_t *)&s, sizeof s);
}

static void emit_version(UartPort *port)
{
    VersionPayload v = { .proto = (uint8_t)PROTO_VERSION, .reserved = 0u };
    /* NUL-padded copy; a 30-character string fills the field exactly. */
    for (size_t i = 0u; i < sizeof v.version; i++) {
        v.version[i] = '\0';
    }
    for (size_t i = 0u; i < sizeof v.version && fw_version[i] != '\0'; i++) {
        v.version[i] = fw_version[i];
    }
    tx_frame(port, RSP_VERSION, (const uint8_t *)&v, sizeof v);
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
                if ((m == MODE_LASER || m == MODE_ESTIM) && m != g_mode &&
                    g_state.overall == OVERALL_WAITING) {
                    enter_mode(m);
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

        case CMD_LASER_CURRENT:
            if (len == CMD_DAC_LEN) {
                uint16_t code = ((const DacPayload *)payload)->dac;
                if (code <= LASER_DAC_MAX) {
                    g_laser_dac = code;
                    /* Mid-pulse: take effect now.  Masked so the tick ISR
                     * cannot end the pulse (and zero DAC0) between the
                     * check and the write. */
                    __asm volatile ("cpsid i" ::: "memory");
                    if (g_mode == MODE_LASER &&
                        g_state.overall == OVERALL_TRIGGERED) {
                        laser_dac_write12(code);
                    }
                    __asm volatile ("cpsie i" ::: "memory");
                }
            }
            emit_status(port);
            break;

        case CMD_ESTIM_CURRENT:
            if (len == CMD_DAC_LEN) {
                uint16_t code = ((const DacPayload *)payload)->dac;
                if (code <= ESTIM_DAC_MAX) {
                    g_estim_dac         = code;
                    g_estim_dac_pending = true;
                }
            }
            emit_status(port);
            break;

        case CMD_CLEAR_FAULT:
            g_fault_latched = false;
            emit_status(port);
            break;

        case CMD_GET_VERSION:
            emit_version(port);
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
    if (g_fault_evt.pending) {
        FaultPayload f = { .module = module_flags(), .tick = g_fault_evt.tick };
        g_fault_evt.pending = false;
        tx_frame_all(EVT_FAULT, (const uint8_t *)&f, sizeof f);
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

    /* Boot indicator on D7 before any timer runs. */
    for (uint32_t n = 0u; n < BOOT_BLINK_FLASHES; n++) {
        laser_gpio_led_set();
        delay_cycles(BOOT_BLINK_HALF_CYCLES);
        laser_gpio_led_clear();
        delay_cycles(BOOT_BLINK_HALF_CYCLES);
    }

    laser_timera_init();
    laser_timerg_init_tick();
    laser_timerg_init_housekeeping();
    laser_dac_init();
    laser_adc_init();
    uart_init(&g_uart_pi,  UART1);
    uart_init(&g_uart_usb, UART0);
    frame_decoder_init(&g_rx_pi);
    frame_decoder_init(&g_rx_usb);

    enter_mode(MODE_LASER);             /* gpio-safe pins, DAC0 at zero until a pulse */
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

    /* GPIOA IRQ (shared GROUP1 vector): the BNC / Pi trigger edges and the
     * FAULT_n kill, at the top priority so a fault is acted on within a
     * few µs (it cannot pre-empt a running tick ISR, which is ~2 µs). */
    NVIC_SetPriority(GPIOA_INT_IRQn, 0);
    NVIC_ClearPendingIRQ(GPIOA_INT_IRQn);
    NVIC_EnableIRQ(GPIOA_INT_IRQn);

    while (1) {
        if (g_housekeeping_due) {
            g_housekeeping_due = false;
            drain_uart(&g_uart_pi,  &g_rx_pi);
            drain_uart(&g_uart_usb, &g_rx_usb);
            poll_buttons();
            module_housekeeping();
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

    if (mis & BOARD_FAULT_N_PIN) {
        /* FAULT_n fell: one-shot — mask the edge so a chattering line
         * cannot re-enter here; housekeeping re-arms after the latch is
         * cleared and the line has been high for 2 ms.  Outputs off first,
         * then latch and report. */
        GPIOA->CPU_INT.ICLR = BOARD_FAULT_N_PIN;
        laser_gpio_fault_irq_disable();
        g_fault_armed = false;
        fault_latch();
    }

    uint32_t fired_mask = mis & (BOARD_STIM_IN_PIN | BOARD_PI_TRIGGER_PIN);
    if (fired_mask) {
        GPIOA->CPU_INT.ICLR = fired_mask;
        g_hw_trigger_pending = true;
    }
}
