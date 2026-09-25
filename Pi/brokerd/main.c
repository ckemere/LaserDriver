/*
 * laserhat-brokerd — the LaserHAT broker daemon, in C.
 *
 * Drop-in replacement for Pi/broker.py (same UART protocol, same JSON
 * socket, same GPIO trigger line), plus a low-latency UDP trigger listener
 * that runs on its own real-time thread.  See Pi/brokerd/README.md.
 */

#include "brokerd.h"
#include "udp_trigger.h"

#include <getopt.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define DEFAULT_DEVICE "/dev/ttyS0"
#define DEFAULT_SOCKET "/run/laserhat/broker.sock"

/* ----- util ------------------------------------------------------------ */
double now_mono(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}

uint64_t ts_to_ns(const struct timespec *t)
{
    return (uint64_t)t->tv_sec * 1000000000ull + (uint64_t)t->tv_nsec;
}

bool split_hostport(const char *s, char *host, size_t hostcap, char *port,
                    size_t portcap)
{
    const char *colon = strrchr(s, ':');
    if (colon == NULL || colon[1] == '\0') {
        return false;
    }
    size_t hl = (size_t)(colon - s);
    if (hl >= hostcap || strlen(colon + 1) >= portcap) {
        return false;
    }
    memcpy(host, s, hl);
    host[hl] = '\0';
    if (strcmp(host, "*") == 0) {
        host[0] = '\0';
    }
    strcpy(port, colon + 1);
    return true;
}

int spawn_thread(pthread_t *t, void *(*fn)(void *), void *arg)
{
    pthread_attr_t a;
    pthread_attr_init(&a);
    pthread_attr_setstacksize(&a, 256 * 1024);
    int rc = pthread_create(t, &a, fn, arg);
    pthread_attr_destroy(&a);
    return rc;
}

/* ----- main ------------------------------------------------------------ */
static void usage(const char *argv0)
{
    fprintf(stderr,
        "usage: %s [options]\n"
        "  --device PATH        MCU UART (default $LASERHAT_DEVICE or " DEFAULT_DEVICE ")\n"
        "  --baud N             default 115200\n"
        "  --socket PATH        JSON socket (default $LASERHAT_SOCK or " DEFAULT_SOCKET ")\n"
        "  --control-tcp H:P    also serve the JSON protocol on TCP (off by default)\n"
        "  --gpio BACKEND       gpiomem (default on Linux) | sim | none\n"
        "  --no-gpio            same as --gpio none\n"
        "  --gpio-pin N         BCM pin wired to MCU PA19 (default 24)\n"
        "  --pulse-us N         trigger line high time, us (default 20)\n"
        "  --udp H:P            enable the UDP trigger listener (e.g. 192.168.17.10:%u)\n"
        "  --udp-allow IP       only accept triggers from this IPv4 source\n"
        "  --rt-prio N          SCHED_FIFO priority for the trigger thread (0 = off)\n"
        "  --cpu N              pin the trigger thread to CPU N\n"
        "  --spin               busy-poll the UDP socket (use with an isolated CPU)\n",
        argv0, LHT_DEFAULT_PORT);
}

int main(int argc, char **argv)
{
    const char *device = getenv("LASERHAT_DEVICE");
    const char *sock_path = getenv("LASERHAT_SOCK");
    const char *control_tcp = NULL;
    int baud = 115200, pin = 24, pulse_us = 20;
#ifdef __linux__
    GpioBackend backend = GPIO_GPIOMEM;
#else
    GpioBackend backend = GPIO_NONE;
#endif
    TriggerCfg tc = { .bind = NULL, .allow = NULL, .rt_prio = 0, .cpu = -1 };

    if (!device) device = DEFAULT_DEVICE;
    if (!sock_path) sock_path = DEFAULT_SOCKET;

    enum { O_DEVICE = 1, O_BAUD, O_SOCKET, O_CTCP, O_GPIO, O_NOGPIO, O_PIN,
           O_PULSE, O_UDP, O_ALLOW, O_PRIO, O_CPU, O_SPIN, O_HELP };
    static const struct option opts[] = {
        { "device", 1, 0, O_DEVICE }, { "baud", 1, 0, O_BAUD },
        { "socket", 1, 0, O_SOCKET }, { "control-tcp", 1, 0, O_CTCP },
        { "gpio", 1, 0, O_GPIO },     { "no-gpio", 0, 0, O_NOGPIO },
        { "gpio-pin", 1, 0, O_PIN },  { "pulse-us", 1, 0, O_PULSE },
        { "udp", 1, 0, O_UDP },       { "udp-allow", 1, 0, O_ALLOW },
        { "rt-prio", 1, 0, O_PRIO },  { "cpu", 1, 0, O_CPU },
        { "spin", 0, 0, O_SPIN },     { "help", 0, 0, O_HELP },
        { 0, 0, 0, 0 },
    };
    int o;
    while ((o = getopt_long(argc, argv, "", opts, NULL)) != -1) {
        switch (o) {
            case O_DEVICE: device = optarg; break;
            case O_BAUD:   baud = atoi(optarg); break;
            case O_SOCKET: sock_path = optarg; break;
            case O_CTCP:   control_tcp = optarg; break;
            case O_GPIO:
                if (strcmp(optarg, "gpiomem") == 0)   backend = GPIO_GPIOMEM;
                else if (strcmp(optarg, "sim") == 0)  backend = GPIO_SIM;
                else if (strcmp(optarg, "none") == 0) backend = GPIO_NONE;
                else { usage(argv[0]); return 2; }
                break;
            case O_NOGPIO: backend = GPIO_NONE; break;
            case O_PIN:    pin = atoi(optarg); break;
            case O_PULSE:  pulse_us = atoi(optarg); break;
            case O_UDP:    tc.bind = optarg; break;
            case O_ALLOW:  tc.allow = optarg; break;
            case O_PRIO:   tc.rt_prio = atoi(optarg); break;
            case O_CPU:    tc.cpu = atoi(optarg); break;
            case O_SPIN:   tc.spin = true; break;
            default:       usage(argv[0]); return o == O_HELP ? 0 : 2;
        }
    }
    if (pulse_us < 1 || pulse_us > 10000) {
        fprintf(stderr, "brokerd: --pulse-us must be 1..10000\n");
        return 2;
    }
    tc.pulse_ns = (uint32_t)pulse_us * 1000u;
    g_pulse_ns = tc.pulse_ns;

    /* Threads inherit this mask; main collects the signals with sigwait. */
    sigset_t sigs;
    sigemptyset(&sigs);
    sigaddset(&sigs, SIGINT);
    sigaddset(&sigs, SIGTERM);
    pthread_sigmask(SIG_BLOCK, &sigs, NULL);
    signal(SIGPIPE, SIG_IGN);

    if (tc.rt_prio > 0 && mlockall(MCL_CURRENT | MCL_FUTURE) != 0) {
        perror("brokerd: warning: mlockall (need LimitMEMLOCK=infinity)");
    }

    if (gpio_open(backend, pin) != 0) {
        fprintf(stderr, "brokerd: GPIO trigger unavailable\n");
        gpio_open(GPIO_NONE, pin);
    }

    fprintf(stderr, "brokerd: opening UART %s @ %d\n", device, baud);
    if (mcu_open(device, baud) != 0) {
        gpio_close();
        return 1;
    }

    int ufd = ipc_listen_unix(sock_path);
    if (ufd < 0) {
        gpio_close();
        return 1;
    }
    int tfd = -1;
    if (control_tcp && (tfd = ipc_listen_tcp(control_tcp)) < 0) {
        gpio_close();
        unlink(sock_path);
        return 1;
    }
    if (tc.bind && trigger_start(&tc) != 0) {
        gpio_close();
        unlink(sock_path);
        return 1;
    }

    mcu_start();
    ipc_serve(ufd);
    fprintf(stderr, "brokerd: serving on %s\n", sock_path);
    if (tfd >= 0) {
        ipc_serve(tfd);
        fprintf(stderr, "brokerd: JSON control on tcp %s\n", control_tcp);
    }
    if (tc.bind) {
        fprintf(stderr, "brokerd: UDP triggers on %s (pulse %d us, rt-prio %d%s)\n",
                tc.bind, pulse_us, tc.rt_prio, tc.spin ? ", spin" : "");
    }

    int sig;
    sigwait(&sigs, &sig);
    fprintf(stderr, "brokerd: signal %d, exiting\n", sig);
    gpio_close();
    unlink(sock_path);
    return 0;
}
