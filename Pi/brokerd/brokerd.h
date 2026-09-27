#ifndef BROKERD_H
#define BROKERD_H

/*
 * laserhat-brokerd — C replacement for Pi/broker.py.
 *
 *   mcu.c      owns the UART: framing, STATUS-as-ack command path, poller,
 *              liveness, the mirrored MCU state.
 *   ipc.c      newline-JSON pub/sub server (Unix socket, optionally TCP);
 *              wire-compatible with broker.py, so hat_client.py and the
 *              GUIs are unchanged.
 *   json.c     the minimal JSON object parser ipc.c needs.
 *   gpio.c     the trigger line (Pi GPIO 24 -> MCU PA19) via /dev/gpiomem.
 *   trigger.c  the low-latency UDP trigger listener (see udp_trigger.h).
 */

#include <pthread.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <time.h>

#include "protocol.h"

/* ---- mcu.c ------------------------------------------------------------ */
int  mcu_open(const char *device, int baud);   /* 0 ok, -1 error (printed) */
void mcu_start(void);                          /* reader + poller threads */

/* Client-facing operations (each blocks for the STATUS echo). */
bool mcu_set_knob(const char *knob, long long value);
bool mcu_set_mode(int mode);
bool mcu_trigger_uart(void);
void mcu_query(void);

/* Current state as one JSON line (with trailing newline). */
void mcu_state_json(char *buf, size_t cap);

/* Lock-free reads for the trigger thread. */
bool mcu_is_alive(void);
bool mcu_pulse_active(void);

/* ---- ipc.c ------------------------------------------------------------ */
int  ipc_listen_unix(const char *path);        /* listening fd, or -1 */
int  ipc_listen_tcp(const char *hostport);     /* listening fd, or -1 */
void ipc_serve(int listen_fd);                 /* spawns the accept thread */
void ipc_broadcast(const char *line);          /* line includes '\n' */

/* ---- json.c ----------------------------------------------------------- */
typedef enum { JV_STR, JV_NUM, JV_BOOL, JV_NULL, JV_OTHER } JsonType;

typedef struct {
    char     key[32];
    JsonType type;
    char     str[64];       /* JV_STR (truncated) */
    double   num;           /* JV_NUM; JV_BOOL as 0/1 */
} JsonField;

typedef struct {
    JsonField f[16];
    int       n;
} JsonObj;

bool json_parse_object(const char *s, JsonObj *out);
const JsonField *json_get(const JsonObj *o, const char *key);
/* Python int() semantics for the subset we accept. */
bool json_as_int(const JsonField *f, long long *out);
/* Append s as a JSON string literal (with quotes). */
void json_put_str(char *dst, size_t cap, const char *s);

/* ---- gpio.c ----------------------------------------------------------- */
typedef enum { GPIO_NONE, GPIO_SIM, GPIO_GPIOMEM } GpioBackend;

int  gpio_open(GpioBackend backend, int pin);  /* 0 ok, -1 error (printed) */
bool gpio_available(void);
bool gpio_is_sim(void);
/* Raise the line, stamp CLOCK_REALTIME into *edge, hold width_ns
 * (busy-wait), lower it.  No-op (returns false) if unavailable. */
bool gpio_pulse(uint32_t width_ns, struct timespec *edge);
void gpio_close(void);

/* ---- trigger.c -------------------------------------------------------- */
typedef struct {
    const char *bind;       /* "HOST:PORT" */
    const char *allow;      /* only accept this source IPv4 (NULL = any) */
    int         rt_prio;    /* SCHED_FIFO priority, 0 = don't change */
    int         cpu;        /* pin to this CPU, -1 = don't */
    bool        spin;       /* busy-poll the socket instead of blocking */
    uint32_t    pulse_ns;   /* GPIO high time */
} TriggerCfg;

int  trigger_start(const TriggerCfg *cfg);     /* 0 ok, -1 error (printed) */
void trigger_stats_json(char *buf, size_t cap); /* ,"k":v,... fragment */

/* The configured GPIO high time, shared with ipc.c's trigger_gpio. */
extern uint32_t g_pulse_ns;

/* ---- util (main.c) ---------------------------------------------------- */
double now_mono(void);
uint64_t ts_to_ns(const struct timespec *t);
/* Parse numeric "IPV4:PORT" (IPV4 may be empty or "*" for any).  No
 * getaddrinfo: the packaged binary is static, where NSS lookups break. */
struct sockaddr_in;
bool parse_ipv4_port(const char *s, struct sockaddr_in *out);
/* pthread_create with a small stack (all memory is mlock'ed). */
int spawn_thread(pthread_t *t, void *(*fn)(void *), void *arg);

#endif /* BROKERD_H */
