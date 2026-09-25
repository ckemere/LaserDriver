/*
 * Low-latency UDP trigger listener (protocol: udp_trigger.h).
 *
 * One dedicated thread, optionally SCHED_FIFO and pinned to a CPU, blocks
 * in recvmsg() (or busy-polls with --spin).  The hot path between a
 * datagram arriving and the GPIO edge is: header check, source check,
 * duplicate check, one register store.  Timestamps, stats and the ACK all
 * happen after the edge.  No locks are taken on the hot path.
 */

#include "brokerd.h"
#include "udp_trigger.h"

#include <arpa/inet.h>
#include <errno.h>
#include <netdb.h>
#include <netinet/in.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#define DUP_WINDOW_NS  1000000000ull    /* same peer + seq within 1 s */

uint32_t g_pulse_ns = 20000;

static TriggerCfg     g_cfg;
static int            g_sock = -1;
static bool           g_have_allow;
static struct in_addr g_allow;

static atomic_ullong st_rx, st_fired, st_dup, st_ping, st_bad, st_denied;
static atomic_ullong st_lat_last_ns, st_lat_max_ns;

void trigger_stats_json(char *buf, size_t cap)
{
    snprintf(buf, cap,
             ",\"udp_enabled\":%s,\"udp_rx\":%llu,\"udp_fired\":%llu,"
             "\"udp_duplicate\":%llu,\"udp_ping\":%llu,\"udp_bad\":%llu,"
             "\"udp_denied\":%llu,\"latency_last_ns\":%llu,\"latency_max_ns\":%llu,"
             "\"gpio\":\"%s\"",
             g_sock >= 0 ? "true" : "false",
             (unsigned long long)st_rx, (unsigned long long)st_fired,
             (unsigned long long)st_dup, (unsigned long long)st_ping,
             (unsigned long long)st_bad, (unsigned long long)st_denied,
             (unsigned long long)st_lat_last_ns, (unsigned long long)st_lat_max_ns,
             !gpio_available() ? "none" : gpio_is_sim() ? "sim" : "gpiomem");
}

static void setup_realtime(void)
{
#ifdef __linux__
    if (g_cfg.cpu >= 0) {
        cpu_set_t set;
        CPU_ZERO(&set);
        CPU_SET(g_cfg.cpu, &set);
        int rc = pthread_setaffinity_np(pthread_self(), sizeof set, &set);
        if (rc != 0) {
            fprintf(stderr, "brokerd: warning: pin trigger thread to CPU %d: %s\n",
                    g_cfg.cpu, strerror(rc));
        }
    }
#else
    if (g_cfg.cpu >= 0) {
        fprintf(stderr, "brokerd: warning: --cpu is Linux-only; ignored\n");
    }
#endif
    if (g_cfg.rt_prio > 0) {
        struct sched_param sp = { .sched_priority = g_cfg.rt_prio };
        int rc = pthread_setschedparam(pthread_self(), SCHED_FIFO, &sp);
        if (rc != 0) {
            fprintf(stderr, "brokerd: warning: SCHED_FIFO %d for trigger thread: %s "
                            "(need LimitRTPRIO= or CAP_SYS_NICE)\n",
                    g_cfg.rt_prio, strerror(rc));
        }
    }
}

/* Kernel receive timestamp from the control messages, if present. */
static bool kernel_rx_ts(struct msghdr *mh, uint64_t *ns)
{
    for (struct cmsghdr *cm = CMSG_FIRSTHDR(mh); cm; cm = CMSG_NXTHDR(mh, cm)) {
        if (cm->cmsg_level != SOL_SOCKET) {
            continue;
        }
#ifdef SCM_TIMESTAMPNS
        if (cm->cmsg_type == SCM_TIMESTAMPNS) {
            struct timespec ts;
            memcpy(&ts, CMSG_DATA(cm), sizeof ts);
            *ns = ts_to_ns(&ts);
            return true;
        }
#endif
        if (cm->cmsg_type == SCM_TIMESTAMP) {
            struct timeval tv;
            memcpy(&tv, CMSG_DATA(cm), sizeof tv);
            *ns = (uint64_t)tv.tv_sec * 1000000000ull + (uint64_t)tv.tv_usec * 1000ull;
            return true;
        }
    }
    return false;
}

static void *trigger_loop(void *arg)
{
    (void)arg;
    setup_realtime();

    /* Last fired trigger, for duplicate (retry) suppression. */
    struct sockaddr_in last_peer = { 0 };
    uint32_t last_seq = 0;
    uint64_t last_edge_ns = 0, last_rx_ns = 0;
    bool     have_last = false;

    int rflags = g_cfg.spin ? MSG_DONTWAIT : 0;
    for (;;) {
        uint8_t buf[64];
        union { char c[256]; struct cmsghdr align; } ctl;
        struct sockaddr_in peer;
        struct iovec iov = { buf, sizeof buf };
        struct msghdr mh = {
            .msg_name = &peer, .msg_namelen = sizeof peer,
            .msg_iov = &iov, .msg_iovlen = 1,
            .msg_control = ctl.c, .msg_controllen = sizeof ctl.c,
        };
        ssize_t n = recvmsg(g_sock, &mh, rflags);
        if (n < 0) {
            if (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) {
                fprintf(stderr, "brokerd: udp recv: %s\n", strerror(errno));
                usleep(1000);
            }
            continue;
        }
        struct timespec t_user;
        clock_gettime(CLOCK_REALTIME, &t_user);

        /* ---- hot path: decide, then fire ---- */
        LhtRequest req;
        if ((size_t)n < sizeof req) {
            atomic_fetch_add(&st_bad, 1);
            continue;
        }
        memcpy(&req, buf, sizeof req);
        if (req.magic != LHT_MAGIC) {
            atomic_fetch_add(&st_bad, 1);
            continue;                       /* not ours: no reply */
        }
        if (g_have_allow && peer.sin_addr.s_addr != g_allow.s_addr) {
            atomic_fetch_add(&st_denied, 1);
            continue;
        }

        LhtReply rep = {
            .magic = LHT_MAGIC, .version = LHT_VERSION, .type = LHT_ACK,
            .seq = req.seq, .client_ts = req.client_ts,
        };
        bool pulse_was_active = mcu_pulse_active();
        bool fired = false;
        struct timespec edge = { 0 };

        if (req.version != LHT_VERSION) {
            rep.status = LHT_BAD_VERSION;
        } else if (req.type == LHT_PING) {
            rep.status = LHT_PONG;
        } else if (req.type != LHT_TRIGGER) {
            rep.status = LHT_BAD_TYPE;
        } else if (have_last && req.seq == last_seq
                   && peer.sin_addr.s_addr == last_peer.sin_addr.s_addr
                   && peer.sin_port == last_peer.sin_port
                   && ts_to_ns(&t_user) - last_rx_ns < DUP_WINDOW_NS) {
            rep.status = LHT_DUPLICATE;
            rep.edge_ns = last_edge_ns;
        } else if (gpio_pulse(g_pulse_ns, &edge)) {
            rep.status = LHT_FIRED;
            fired = true;
        } else {
            rep.status = LHT_NO_GPIO;
        }

        /* ---- after the edge: bookkeeping + ACK ---- */
        atomic_fetch_add(&st_rx, 1);
        uint64_t rx_ns;
        if (!kernel_rx_ts(&mh, &rx_ns)) {
            rx_ns = ts_to_ns(&t_user);
            rep.flags |= LHT_F_RX_TS_USER;
        }
        rep.rx_ns = rx_ns;
        if (!mcu_is_alive())  rep.flags |= LHT_F_MCU_DOWN;
        if (pulse_was_active) rep.flags |= LHT_F_MCU_BUSY;
        if (gpio_is_sim())    rep.flags |= LHT_F_GPIO_SIM;

        if (fired) {
            rep.edge_ns = ts_to_ns(&edge);
            last_peer = peer;
            last_seq = req.seq;
            last_edge_ns = rep.edge_ns;
            last_rx_ns = ts_to_ns(&t_user);
            have_last = true;
            atomic_fetch_add(&st_fired, 1);
            if (rep.edge_ns > rx_ns) {
                unsigned long long lat = rep.edge_ns - rx_ns;
                atomic_store(&st_lat_last_ns, lat);
                if (lat > atomic_load(&st_lat_max_ns)) {
                    atomic_store(&st_lat_max_ns, lat);
                }
            }
        } else if (rep.status == LHT_DUPLICATE) {
            atomic_fetch_add(&st_dup, 1);
        } else if (rep.status == LHT_PONG) {
            atomic_fetch_add(&st_ping, 1);
        } else if (rep.status != LHT_NO_GPIO) {
            atomic_fetch_add(&st_bad, 1);
        }

        sendto(g_sock, &rep, sizeof rep, 0, (struct sockaddr *)&peer, sizeof peer);
    }
    return NULL;
}

int trigger_start(const TriggerCfg *cfg)
{
    g_cfg = *cfg;
    g_pulse_ns = cfg->pulse_ns;

    if (cfg->allow) {
        if (inet_pton(AF_INET, cfg->allow, &g_allow) != 1) {
            fprintf(stderr, "brokerd: bad --udp-allow address '%s'\n", cfg->allow);
            return -1;
        }
        g_have_allow = true;
    }

    char host[128], port[16];
    if (!split_hostport(cfg->bind, host, sizeof host, port, sizeof port)) {
        fprintf(stderr, "brokerd: bad --udp HOST:PORT '%s'\n", cfg->bind);
        return -1;
    }
    struct addrinfo hints = { .ai_family = AF_INET, .ai_socktype = SOCK_DGRAM,
                              .ai_flags = AI_PASSIVE }, *ai;
    int rc = getaddrinfo(host[0] ? host : NULL, port, &hints, &ai);
    if (rc != 0) {
        fprintf(stderr, "brokerd: %s: %s\n", cfg->bind, gai_strerror(rc));
        return -1;
    }
    g_sock = socket(ai->ai_family, ai->ai_socktype, 0);
    if (g_sock < 0 || bind(g_sock, ai->ai_addr, ai->ai_addrlen) < 0) {
        fprintf(stderr, "brokerd: udp %s: %s\n", cfg->bind, strerror(errno));
        freeaddrinfo(ai);
        if (g_sock >= 0) close(g_sock);
        g_sock = -1;
        return -1;
    }
    freeaddrinfo(ai);

    int one = 1;
#ifdef SO_TIMESTAMPNS
    setsockopt(g_sock, SOL_SOCKET, SO_TIMESTAMPNS, &one, sizeof one);
#else
    setsockopt(g_sock, SOL_SOCKET, SO_TIMESTAMP, &one, sizeof one);
#endif

    pthread_t t;
    if (spawn_thread(&t, trigger_loop, NULL) != 0) {
        fprintf(stderr, "brokerd: can't start trigger thread\n");
        return -1;
    }
    return 0;
}
