/*
 * MCU link: the single owner of the UART.  Behaviour mirrors broker.py's
 * Broker class — see that file and Pi/protocol.py for the rationale.
 *
 *   reader thread   decode frames, mirror state, route STATUS to the
 *                   waiting command (status-as-ack), broadcast events
 *   poller thread   CMD_QUERY every POLL_INTERVAL for state + liveness
 *   callers         ipc.c client threads, one command in flight at a time
 */

#include "brokerd.h"

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include <termios.h>
#include <unistd.h>

#define POLL_INTERVAL     0.25  /* s between liveness CMD_QUERY polls */
#define REPLY_TIMEOUT     0.5   /* s to wait for a STATUS echo */
#define LIVENESS_TIMEOUT  1.5   /* s without a status -> mcu_alive false */

/* STATUS range check (false-sync rejection).  Mirror of protocol.py. */
#define INTENSITY_MIN     1u
#define INTENSITY_MAX     320u
#define TICKS_MIN         1u
#define TICKS_MAX         10000000u
#define MAGIC16           ((uint16_t)(PROTO_SYNC0 | (PROTO_SYNC1 << 8)))

typedef struct {
    bool     mcu_alive;
    bool     have_status;           /* the config fields below are known */
    uint16_t intensity;
    uint32_t ramp_ticks;
    uint32_t hold_ticks;
    uint8_t  button_mask;
    char     phase;                 /* 'W' / 'T' */
    uint32_t tick;
    uint8_t  mode;
    uint32_t estim_dur_ticks;
    uint32_t estim_ipi_ticks;
} McuState;

static int g_fd = -1;

static pthread_mutex_t g_state_mu = PTHREAD_MUTEX_INITIALIZER;
static McuState        g_state = { .phase = 'W', .mode = MODE_LASER };
static double          g_last_status_at;

static atomic_bool g_alive_flag;
static atomic_bool g_pulse_flag;

/* One command in flight; its STATUS echo is handed over here. */
static pthread_mutex_t g_cmd_mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t g_reply_mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t  g_reply_cv;
static bool            g_reply_ready;
static StatusPayload   g_reply;

static pthread_mutex_t g_write_mu = PTHREAD_MUTEX_INITIALIZER;

/* ----- serial port ----------------------------------------------------- */
static speed_t baud_const(int baud)
{
    switch (baud) {
        case 9600:   return B9600;
        case 19200:  return B19200;
        case 38400:  return B38400;
        case 57600:  return B57600;
        case 115200: return B115200;
        case 230400: return B230400;
        default:     return 0;
    }
}

int mcu_open(const char *device, int baud)
{
    speed_t sp = baud_const(baud);
    if (sp == 0) {
        fprintf(stderr, "brokerd: unsupported baud %d\n", baud);
        return -1;
    }
    g_fd = open(device, O_RDWR | O_NOCTTY | O_CLOEXEC);
    if (g_fd < 0) {
        fprintf(stderr, "brokerd: open %s: %s\n", device, strerror(errno));
        return -1;
    }
    struct termios tio;
    if (tcgetattr(g_fd, &tio) == 0) {
        cfmakeraw(&tio);
        cfsetispeed(&tio, sp);
        cfsetospeed(&tio, sp);
        tio.c_cflag |= CLOCAL | CREAD;
        tio.c_cc[VMIN] = 0;
        tio.c_cc[VTIME] = 0;
        tcsetattr(g_fd, TCSANOW, &tio);
    }
    tcflush(g_fd, TCIFLUSH);

    pthread_condattr_t ca;
    pthread_condattr_init(&ca);
#ifdef __linux__
    pthread_condattr_setclock(&ca, CLOCK_MONOTONIC);
#endif
    pthread_cond_init(&g_reply_cv, &ca);
    pthread_condattr_destroy(&ca);
    return 0;
}

static int uart_send(uint8_t type, const void *payload, size_t len)
{
    uint8_t wire[3 + PROTO_MAX_PAYLOAD];
    wire[0] = PROTO_SYNC0;
    wire[1] = PROTO_SYNC1;
    wire[2] = type;
    memcpy(wire + 3, payload, len);
    size_t n = 3 + len, off = 0;

    pthread_mutex_lock(&g_write_mu);
    while (off < n) {
        ssize_t w = write(g_fd, wire + off, n - off);
        if (w < 0) {
            if (errno == EINTR || errno == EAGAIN) {
                continue;
            }
            pthread_mutex_unlock(&g_write_mu);
            fprintf(stderr, "brokerd: send failed: %s\n", strerror(errno));
            return -1;
        }
        off += (size_t)w;
    }
    pthread_mutex_unlock(&g_write_mu);
    return 0;
}

/* ----- state ----------------------------------------------------------- */
static void state_json_locked(char *buf, size_t cap)
{
    const McuState *s = &g_state;
    char i[16] = "null", r[16] = "null", h[16] = "null", ed[16] = "null",
         ei[16] = "null";
    if (s->have_status) {
        snprintf(i, sizeof i, "%u", s->intensity);
        snprintf(r, sizeof r, "%u", s->ramp_ticks);
        snprintf(h, sizeof h, "%u", s->hold_ticks);
        snprintf(ed, sizeof ed, "%u", s->estim_dur_ticks);
        snprintf(ei, sizeof ei, "%u", s->estim_ipi_ticks);
    }
    const char *alive = s->mcu_alive ? "true" : "false";
    snprintf(buf, cap,
             "{\"type\":\"state\",\"ok\":%s,\"mcu_alive\":%s,"
             "\"intensity\":%s,\"ramp_ticks\":%s,\"hold_ticks\":%s,"
             "\"button_mask\":%u,\"phase\":\"%c\",\"tick\":%u,\"mode\":%u,"
             "\"estim_dur_ticks\":%s,\"estim_ipi_ticks\":%s}\n",
             alive, alive, i, r, h, s->button_mask, s->phase, s->tick,
             s->mode, ed, ei);
}

void mcu_state_json(char *buf, size_t cap)
{
    pthread_mutex_lock(&g_state_mu);
    state_json_locked(buf, cap);
    pthread_mutex_unlock(&g_state_mu);
}

static void broadcast_state_locked(void)
{
    char line[512];
    state_json_locked(line, sizeof line);
    ipc_broadcast(line);
}

bool mcu_is_alive(void)     { return atomic_load_explicit(&g_alive_flag, memory_order_relaxed); }
bool mcu_pulse_active(void) { return atomic_load_explicit(&g_pulse_flag, memory_order_relaxed); }

static bool status_in_range(const StatusPayload *p)
{
    return p->intensity >= INTENSITY_MIN && p->intensity <= INTENSITY_MAX
        && p->ramp_ticks >= TICKS_MIN && p->ramp_ticks <= TICKS_MAX
        && p->hold_ticks >= TICKS_MIN && p->hold_ticks <= TICKS_MAX
        && p->button_mask <= 0x0F
        && (p->phase == PHASE_WAITING || p->phase == PHASE_TRIGGERED)
        && (p->mode == MODE_LASER || p->mode == MODE_ESTIM)
        && p->estim_dur_ticks >= ESTIM_DUR_MIN && p->estim_dur_ticks <= ESTIM_DUR_MAX
        && p->estim_ipi_ticks >= ESTIM_IPI_MIN && p->estim_ipi_ticks <= ESTIM_IPI_MAX;
}

static void apply_status(const StatusPayload *p)
{
    McuState n;
    pthread_mutex_lock(&g_state_mu);
    g_last_status_at = now_mono();
    n = g_state;
    n.mcu_alive       = true;
    n.have_status     = true;
    n.intensity       = p->intensity;
    n.ramp_ticks      = p->ramp_ticks;
    n.hold_ticks      = p->hold_ticks;
    n.button_mask     = p->button_mask;
    n.phase           = (p->phase == PHASE_WAITING) ? 'W' : 'T';
    n.tick            = p->tick;
    n.mode            = p->mode;
    n.estim_dur_ticks = p->estim_dur_ticks;
    n.estim_ipi_ticks = p->estim_ipi_ticks;
    bool changed = memcmp(&n, &g_state, sizeof n) != 0;
    g_state = n;
    atomic_store(&g_alive_flag, true);
    atomic_store(&g_pulse_flag, n.phase == 'T');
    if (changed) {
        broadcast_state_locked();
    }
    pthread_mutex_unlock(&g_state_mu);
}

static void check_liveness(void)
{
    pthread_mutex_lock(&g_state_mu);
    if (g_state.mcu_alive && g_last_status_at > 0.0
            && now_mono() - g_last_status_at > LIVENESS_TIMEOUT) {
        g_state.mcu_alive = false;
        atomic_store(&g_alive_flag, false);
        broadcast_state_locked();
    }
    pthread_mutex_unlock(&g_state_mu);
}

static void on_pulse(char phase, const char *event, const uint8_t *payload)
{
    uint32_t tick;
    memcpy(&tick, payload, 4);
    char line[128];
    snprintf(line, sizeof line,
             "{\"type\":\"event\",\"event\":\"%s\",\"tick\":%u}\n", event, tick);
    pthread_mutex_lock(&g_state_mu);
    g_state.phase = phase;
    atomic_store(&g_pulse_flag, phase == 'T');
    ipc_broadcast(line);
    broadcast_state_locked();
    pthread_mutex_unlock(&g_state_mu);
}

static void on_button(const uint8_t *payload)
{
    char line[128];
    snprintf(line, sizeof line,
             "{\"type\":\"event\",\"event\":\"button\",\"mask\":%u,\"edges\":%u}\n",
             payload[0], payload[1]);
    pthread_mutex_lock(&g_state_mu);
    g_state.button_mask = payload[0];
    ipc_broadcast(line);
    broadcast_state_locked();
    pthread_mutex_unlock(&g_state_mu);
}

static void handle_frame(uint8_t type, const uint8_t *payload)
{
    switch (type) {
        case RSP_STATUS: {
            StatusPayload p;
            memcpy(&p, payload, sizeof p);
            if (!status_in_range(&p)) {
                return;                 /* false sync; ignore */
            }
            apply_status(&p);
            pthread_mutex_lock(&g_reply_mu);
            g_reply = p;                /* status-as-ack */
            g_reply_ready = true;
            pthread_cond_signal(&g_reply_cv);
            pthread_mutex_unlock(&g_reply_mu);
            break;
        }
        case EVT_PULSE_START: on_pulse('T', "pulse_start", payload); break;
        case EVT_PULSE_END:   on_pulse('W', "pulse_end", payload);   break;
        case EVT_BUTTON:      on_button(payload);                     break;
        default: break;
    }
}

/* ----- stream decoder (Pi inbound = responses/events) ------------------ */
/* Same algorithm as protocol.StreamDecoder, including the inner-SYNC resync
 * for a frame truncated by a dropped byte. */
typedef struct {
    uint8_t buf[512];
    size_t  n;
} Decoder;

static int rsp_len(uint8_t type)
{
    switch (type) {
        case RSP_STATUS:      return (int)PROTO_STATUS_LEN;
        case EVT_PULSE_START: return 4;
        case EVT_PULSE_END:   return 4;
        case EVT_BUTTON:      return 2;
        default:              return -1;
    }
}

/* First i in [start, end) with SYNC at buf[i..i+1] fully before end. */
static long find_sync(const Decoder *d, size_t start, size_t end)
{
    if (end > d->n) {
        end = d->n;
    }
    for (size_t i = start; i + 2 <= end; i++) {
        if (d->buf[i] == PROTO_SYNC0 && d->buf[i + 1] == PROTO_SYNC1) {
            return (long)i;
        }
    }
    return -1;
}

static void drop(Decoder *d, size_t k)
{
    memmove(d->buf, d->buf + k, d->n - k);
    d->n -= k;
}

static void decoder_feed(Decoder *d, const uint8_t *data, size_t len)
{
    if (d->n + len > sizeof d->buf) {
        drop(d, d->n);              /* can't happen with 256-byte reads */
    }
    memcpy(d->buf + d->n, data, len);
    d->n += len;

    for (;;) {
        long j = find_sync(d, 0, d->n);
        if (j < 0) {
            if (d->n) {
                drop(d, d->n - 1);  /* keep a possible partial SYNC */
            }
            return;
        }
        if (j) {
            drop(d, (size_t)j);     /* junk before SYNC */
        }
        if (d->n < 3) {
            return;
        }
        int plen = rsp_len(d->buf[2]);
        if (plen < 0) {
            drop(d, 1);             /* false SYNC; advance and rescan */
            continue;
        }
        long inner = find_sync(d, 3, 3 + (size_t)plen + 1);
        if (inner >= 0) {
            drop(d, (size_t)inner);
            continue;
        }
        if (d->n < 3 + (size_t)plen) {
            return;
        }
        uint8_t type = d->buf[2];
        uint8_t payload[PROTO_MAX_PAYLOAD];
        memcpy(payload, d->buf + 3, (size_t)plen);
        drop(d, 3 + (size_t)plen);
        handle_frame(type, payload);
    }
}

static void *reader_loop(void *arg)
{
    (void)arg;
    Decoder dec = { .n = 0 };
    for (;;) {
        struct pollfd pfd = { .fd = g_fd, .events = POLLIN };
        int pr = poll(&pfd, 1, 100);
        if (pr > 0) {
            uint8_t data[256];
            ssize_t n = read(g_fd, data, sizeof data);
            if (n > 0) {
                decoder_feed(&dec, data, (size_t)n);
            } else if (n == 0 || (errno != EINTR && errno != EAGAIN)) {
                fprintf(stderr, "brokerd: UART read error: %s\n",
                        n == 0 ? "EOF" : strerror(errno));
                usleep(200000);
            }
        }
        check_liveness();
    }
    return NULL;
}

/* ----- command path (STATUS-correlated) -------------------------------- */
/* Send a command and wait for its STATUS echo.  true + *echo on success. */
static bool command(uint8_t type, const void *payload, size_t len,
                    StatusPayload *echo)
{
    bool ok = false;
    pthread_mutex_lock(&g_cmd_mu);

    pthread_mutex_lock(&g_reply_mu);
    g_reply_ready = false;
    pthread_mutex_unlock(&g_reply_mu);

    if (uart_send(type, payload, len) == 0) {
        struct timespec dl;
#ifdef __linux__
        clock_gettime(CLOCK_MONOTONIC, &dl);
#else
        clock_gettime(CLOCK_REALTIME, &dl);
#endif
        long long ns = (long long)dl.tv_nsec + (long long)(REPLY_TIMEOUT * 1e9);
        dl.tv_sec += (time_t)(ns / 1000000000LL);
        dl.tv_nsec = (long)(ns % 1000000000LL);

        pthread_mutex_lock(&g_reply_mu);
        while (!g_reply_ready) {
            if (pthread_cond_timedwait(&g_reply_cv, &g_reply_mu, &dl) == ETIMEDOUT) {
                break;
            }
        }
        if (g_reply_ready) {
            ok = true;
            if (echo) {
                *echo = g_reply;
            }
        }
        pthread_mutex_unlock(&g_reply_mu);
    }
    pthread_mutex_unlock(&g_cmd_mu);
    return ok;
}

static void *poller_loop(void *arg)
{
    (void)arg;
    for (;;) {
        command(CMD_QUERY, NULL, 0, NULL);      /* refresh state / liveness */
        usleep((useconds_t)(POLL_INTERVAL * 1e6));
    }
    return NULL;
}

void mcu_start(void)
{
    pthread_t t;
    spawn_thread(&t, reader_loop, NULL);
    spawn_thread(&t, poller_loop, NULL);
}

/* ----- client-facing operations ---------------------------------------- */
/* Nudge a ramp/hold value so its low 16 bits can't equal the SYNC word
 * (protocol.avoid_magic). */
static uint32_t avoid_magic(uint32_t ticks)
{
    if ((ticks & 0xFFFFu) == MAGIC16) {
        return ticks >= TICKS_MAX ? ticks - 1u : ticks + 1u;
    }
    return ticks;
}

bool mcu_set_knob(const char *knob, long long value)
{
    if (knob == NULL) {
        return false;
    }
    bool estim = strcmp(knob, "ed") == 0 || strcmp(knob, "ei") == 0;
    bool laser = strcmp(knob, "i") == 0 || strcmp(knob, "r") == 0
              || strcmp(knob, "h") == 0;
    if (!estim && !laser) {
        return false;
    }
    /* Values that don't fit the wire field are rejected before sending,
     * as struct.pack does in broker.py. */
    long long max = strcmp(knob, "i") == 0 ? 0xFFFFLL : 0xFFFFFFFFLL;
    if (value < 0 || value > max) {
        return false;
    }

    pthread_mutex_lock(&g_state_mu);
    bool known = g_state.have_status;
    McuState s = g_state;
    pthread_mutex_unlock(&g_state_mu);
    if (!known) {
        return false;
    }

    StatusPayload echo;
    if (estim) {
        EstimConfigPayload p = { s.estim_dur_ticks, s.estim_ipi_ticks };
        if (knob[1] == 'd') {
            p.pulse_dur_ticks = (uint32_t)value;
        } else {
            p.ipi_ticks = (uint32_t)value;
        }
        return command(CMD_ESTIM_CONFIG, &p, sizeof p, &echo)
            && echo.estim_dur_ticks == p.pulse_dur_ticks
            && echo.estim_ipi_ticks == p.ipi_ticks;
    }

    ConfigPayload p = { s.intensity, s.ramp_ticks, s.hold_ticks };
    switch (knob[0]) {
        case 'i': p.intensity  = (uint16_t)value; break;
        case 'r': p.ramp_ticks = (uint32_t)value; break;
        default:  p.hold_ticks = (uint32_t)value; break;
    }
    p.ramp_ticks = avoid_magic(p.ramp_ticks);
    p.hold_ticks = avoid_magic(p.hold_ticks);
    return command(CMD_CONFIG, &p, sizeof p, &echo)
        && echo.intensity == p.intensity
        && echo.ramp_ticks == p.ramp_ticks
        && echo.hold_ticks == p.hold_ticks;
}

bool mcu_set_mode(int mode)
{
    if (mode != MODE_LASER && mode != MODE_ESTIM) {
        return false;
    }
    uint8_t m = (uint8_t)mode;
    StatusPayload echo;
    return command(CMD_SET_MODE, &m, 1, &echo) && echo.mode == m;
}

bool mcu_trigger_uart(void)
{
    return command(CMD_TRIGGER, NULL, 0, NULL);
}

void mcu_query(void)
{
    command(CMD_QUERY, NULL, 0, NULL);
}
