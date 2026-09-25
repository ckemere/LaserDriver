/*
 * Newline-JSON pub/sub server, wire-compatible with broker.py:
 *
 *   client -> broker   {"cmd": "set", "knob": "i", "value": 320}
 *                      {"cmd": "trigger"}  {"cmd": "trigger_gpio"}
 *                      {"cmd": "query"}    {"cmd": "set_mode", "mode": "estim"}
 *                      {"cmd": "stats"}    (brokerd only: trigger counters)
 *   broker -> client   {"type": "state", ...}  {"type": "event", ...}
 *                      {"type": "reply", "cmd": ..., "ok": ...}
 *
 * Each client gets a reader thread (commands; may block on the UART) and a
 * writer thread draining a bounded queue, so a slow client never stalls the
 * UART reader's broadcasts — they are dropped for that client instead.
 */

#include "brokerd.h"

#include <errno.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

#define QUEUE_SOFT  256     /* broadcasts beyond this are dropped */
#define QUEUE_HARD  288     /* replies may use the headroom */
#define LINE_MAX_IN 4096

typedef struct Client {
    int             fd;
    pthread_mutex_t mu;
    pthread_cond_t  cv;
    char           *q[QUEUE_HARD];
    int             head, count;
    bool            closed;
    pthread_t       writer;
    struct Client  *next;
} Client;

static pthread_mutex_t g_clients_mu = PTHREAD_MUTEX_INITIALIZER;
static Client         *g_clients;

static void push(Client *c, const char *line, bool is_reply)
{
    pthread_mutex_lock(&c->mu);
    int cap = is_reply ? QUEUE_HARD : QUEUE_SOFT;
    if (!c->closed && c->count < cap) {
        char *copy = strdup(line);
        if (copy) {
            c->q[(c->head + c->count) % QUEUE_HARD] = copy;
            c->count++;
            pthread_cond_signal(&c->cv);
        }
    }
    pthread_mutex_unlock(&c->mu);
}

void ipc_broadcast(const char *line)
{
    pthread_mutex_lock(&g_clients_mu);
    for (Client *c = g_clients; c; c = c->next) {
        push(c, line, false);
    }
    pthread_mutex_unlock(&g_clients_mu);
}

static void *writer_loop(void *arg)
{
    Client *c = arg;
    for (;;) {
        pthread_mutex_lock(&c->mu);
        while (c->count == 0 && !c->closed) {
            pthread_cond_wait(&c->cv, &c->mu);
        }
        if (c->closed) {
            pthread_mutex_unlock(&c->mu);
            return NULL;
        }
        char *line = c->q[c->head];
        c->head = (c->head + 1) % QUEUE_HARD;
        c->count--;
        pthread_mutex_unlock(&c->mu);

        size_t len = strlen(line), off = 0;
        while (off < len) {
            ssize_t w = send(c->fd, line + off, len - off, 0);
            if (w < 0 && errno == EINTR) {
                continue;
            }
            if (w <= 0) {
                break;
            }
            off += (size_t)w;
        }
        free(line);
        if (off < len) {
            pthread_mutex_lock(&c->mu);
            c->closed = true;
            pthread_mutex_unlock(&c->mu);
            shutdown(c->fd, SHUT_RDWR);     /* wakes the reader */
            return NULL;
        }
    }
}

/* ----- command dispatch ------------------------------------------------ */
static void reply_ok(char *out, size_t cap, const char *cmd, bool ok)
{
    snprintf(out, cap, "{\"type\":\"reply\",\"cmd\":\"%s\",\"ok\":%s}\n",
             cmd, ok ? "true" : "false");
}

static void dispatch(const char *line, char *out, size_t cap)
{
    JsonObj msg;
    if (!json_parse_object(line, &msg)) {
        snprintf(out, cap, "{\"type\":\"reply\",\"ok\":false,\"error\":\"bad_json\"}\n");
        return;
    }
    const JsonField *cmdf = json_get(&msg, "cmd");
    const char *cmd = (cmdf && cmdf->type == JV_STR) ? cmdf->str : "";

    if (strcmp(cmd, "set") == 0) {
        long long value;
        if (!json_as_int(json_get(&msg, "value"), &value)) {
            snprintf(out, cap, "{\"type\":\"reply\",\"cmd\":\"set\",\"ok\":false,"
                               "\"error\":\"bad_value\"}\n");
            return;
        }
        const JsonField *kf = json_get(&msg, "knob");
        const char *knob = (kf && kf->type == JV_STR) ? kf->str : NULL;
        bool ok = mcu_set_knob(knob, value);
        snprintf(out, cap, "{\"type\":\"reply\",\"cmd\":\"set\",\"knob\":");
        if (knob) {
            json_put_str(out, cap, knob);
        } else {
            strncat(out, "null", cap - strlen(out) - 1);
        }
        size_t n = strlen(out);
        snprintf(out + n, cap - n, ",\"ok\":%s}\n", ok ? "true" : "false");
    } else if (strcmp(cmd, "trigger") == 0) {
        reply_ok(out, cap, cmd, mcu_trigger_uart());
    } else if (strcmp(cmd, "trigger_gpio") == 0) {
        struct timespec edge;
        reply_ok(out, cap, cmd, gpio_pulse(g_pulse_ns, &edge));
    } else if (strcmp(cmd, "query") == 0) {
        mcu_query();
        reply_ok(out, cap, cmd, true);
    } else if (strcmp(cmd, "set_mode") == 0) {
        const JsonField *mf = json_get(&msg, "mode");
        int mode = -1;
        if (mf && mf->type == JV_STR) {
            if (strcmp(mf->str, "laser") == 0) mode = MODE_LASER;
            if (strcmp(mf->str, "estim") == 0) mode = MODE_ESTIM;
        }
        reply_ok(out, cap, cmd, mcu_set_mode(mode));
    } else if (strcmp(cmd, "stats") == 0) {
        snprintf(out, cap, "{\"type\":\"reply\",\"cmd\":\"stats\",\"ok\":true");
        size_t n = strlen(out);
        trigger_stats_json(out + n, cap - n);
        n = strlen(out);
        snprintf(out + n, cap - n, "}\n");
    } else {
        snprintf(out, cap, "{\"type\":\"reply\",\"ok\":false,\"error\":\"unknown_cmd\"}\n");
    }
}

/* ----- per-client reader ----------------------------------------------- */
static void *client_loop(void *arg)
{
    Client *c = arg;
    char state[512];

    pthread_mutex_lock(&g_clients_mu);
    c->next = g_clients;
    g_clients = c;
    pthread_mutex_unlock(&g_clients_mu);
    mcu_state_json(state, sizeof state);
    push(c, state, true);

    char buf[LINE_MAX_IN];
    size_t n = 0;
    bool discarding = false;            /* inside an overlong line */
    for (;;) {
        ssize_t r = recv(c->fd, buf + n, sizeof buf - n, 0);
        if (r < 0 && errno == EINTR) {
            continue;
        }
        if (r <= 0) {
            break;
        }
        n += (size_t)r;

        char *start = buf, *nl;
        while ((nl = memchr(start, '\n', (size_t)(buf + n - start))) != NULL) {
            *nl = '\0';
            if (discarding) {
                discarding = false;
            } else {
                char *line = start;
                while (*line == ' ' || *line == '\t' || *line == '\r') line++;
                if (*line) {
                    char out[1024];
                    dispatch(line, out, sizeof out);
                    push(c, out, true);
                }
            }
            start = nl + 1;
        }
        n = (size_t)(buf + n - start);
        memmove(buf, start, n);
        if (n == sizeof buf) {          /* line too long: reject it */
            n = 0;
            if (!discarding) {
                push(c, "{\"type\":\"reply\",\"ok\":false,\"error\":\"bad_json\"}\n", true);
            }
            discarding = true;
        }
    }

    pthread_mutex_lock(&g_clients_mu);
    for (Client **pp = &g_clients; *pp; pp = &(*pp)->next) {
        if (*pp == c) {
            *pp = c->next;
            break;
        }
    }
    pthread_mutex_unlock(&g_clients_mu);

    pthread_mutex_lock(&c->mu);
    c->closed = true;
    pthread_cond_signal(&c->cv);
    pthread_mutex_unlock(&c->mu);
    shutdown(c->fd, SHUT_RDWR);         /* unblocks a writer stuck in send */
    pthread_join(c->writer, NULL);

    close(c->fd);
    for (int i = 0; i < c->count; i++) {
        free(c->q[(c->head + i) % QUEUE_HARD]);
    }
    pthread_mutex_destroy(&c->mu);
    pthread_cond_destroy(&c->cv);
    free(c);
    return NULL;
}

/* ----- listeners ------------------------------------------------------- */
static void *accept_loop(void *arg)
{
    int lfd = (int)(intptr_t)arg;
    for (;;) {
        int fd = accept(lfd, NULL, NULL);
        if (fd < 0) {
            if (errno != EINTR && errno != ECONNABORTED) {
                fprintf(stderr, "brokerd: accept: %s\n", strerror(errno));
                usleep(100000);
            }
            continue;
        }
        int one = 1;
        setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one); /* ENOTSUP on AF_UNIX: fine */

        Client *c = calloc(1, sizeof *c);
        if (c == NULL) {
            close(fd);
            continue;
        }
        c->fd = fd;
        pthread_mutex_init(&c->mu, NULL);
        pthread_cond_init(&c->cv, NULL);
        if (spawn_thread(&c->writer, writer_loop, c) != 0) {
            close(fd);
            free(c);
            continue;
        }
        pthread_t t;
        if (spawn_thread(&t, client_loop, c) != 0) {
            pthread_mutex_lock(&c->mu);
            c->closed = true;
            pthread_cond_signal(&c->cv);
            pthread_mutex_unlock(&c->mu);
            pthread_join(c->writer, NULL);
            close(fd);
            free(c);
            continue;
        }
        pthread_detach(t);
    }
    return NULL;
}

void ipc_serve(int listen_fd)
{
    pthread_t t;
    spawn_thread(&t, accept_loop, (void *)(intptr_t)listen_fd);
}

int ipc_listen_unix(const char *path)
{
    struct sockaddr_un sa = { .sun_family = AF_UNIX };
    if (strlen(path) >= sizeof sa.sun_path) {
        fprintf(stderr, "brokerd: socket path too long: %s\n", path);
        return -1;
    }
    strcpy(sa.sun_path, path);

    /* mkdir -p the parent (normally systemd's RuntimeDirectory does it). */
    char dir[sizeof sa.sun_path];
    strcpy(dir, path);
    for (char *p = dir + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            mkdir(dir, 0750);
            *p = '/';
        }
    }
    unlink(path);

    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0 || bind(fd, (struct sockaddr *)&sa, sizeof sa) < 0
            || listen(fd, 16) < 0) {
        fprintf(stderr, "brokerd: unix socket %s: %s\n", path, strerror(errno));
        if (fd >= 0) close(fd);
        return -1;
    }
    chmod(path, 0660);
    return fd;
}

int ipc_listen_tcp(const char *hostport)
{
    struct sockaddr_in sa;
    if (!parse_ipv4_port(hostport, &sa)) {
        fprintf(stderr, "brokerd: bad IPV4:PORT '%s'\n", hostport);
        return -1;
    }
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    int one = 1;
    if (fd >= 0) {
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    }
    if (fd < 0 || bind(fd, (struct sockaddr *)&sa, sizeof sa) < 0
            || listen(fd, 16) < 0) {
        fprintf(stderr, "brokerd: tcp %s: %s\n", hostport, strerror(errno));
        if (fd >= 0) close(fd);
        return -1;
    }
    return fd;
}
