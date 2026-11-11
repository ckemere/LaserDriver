/*
 * oledd.c — LaserHAT OLED daemon for the Adafruit 2.23" 128x32 bonnet
 * (SSD1305, I2C address 0x3C on /dev/i2c-1, panel reset on GPIO 4) or, with
 * LASERHAT_OLED_PANEL=ssd1306, a generic 0.91" 128x32 SSD1306 module on J10.
 *
 * Modeled on pioled-ip.c: no libraries beyond libc plus the kernel's
 * i2c-dev and GPIO character-device interfaces, embedded 5x7 font,
 * cross-compiles statically.  Differences from the SSD1306 PiOLED:
 * the SSD1305 has 132 column drivers for a 128-wide glass (columns are
 * offset by 4) and wants a different init sequence — both taken from
 * Adafruit's CircuitPython SSD1305 driver, which is known-good on this
 * bonnet.
 *
 * The daemon owns the panel and always keeps the header row alive:
 *
 *   row 0:  alternates every 3 s between the client's tag (LASERHAT[L]),
 *           "E:<wired ip>" and "W:<wifi ip>" — "WAITING" until an
 *           interface has an address.  A heartbeat dot in the top-right
 *           cell blinks at 1 Hz as long as this process is running.
 *   rows 1-3: body — owned by the connected GUI client; while no client
 *           is connected they show hostname + both addresses.
 *
 * The GUI (oled_gui.py) connects over a Unix socket and speaks a tiny
 * line protocol (ASCII, newline-terminated; text is upcased by the
 * 5x7 font, 21 character cells per row):
 *
 *   TAG <text>          header-left text shown during the tag phase
 *   ROW <1|2|3> <text>  set a body row (drawn from column 0)
 *   CHIP <label> <0|1>  bottom-right status chip, 1 = inverted (filled)
 *   CHIP OFF            remove the chip
 *   CLEAR               clear tag, body rows and chip
 *   FLUSH               repaint now (otherwise repaint happens each tick)
 *
 * Socket path: $LASERHAT_OLED_SOCK, default /run/laserhat-oled/oled.sock.
 * Build:  gcc -O2 -Wall -o oledd oledd.c
 */

#include <arpa/inet.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <ifaddrs.h>
#include <linux/gpio.h>
#include <linux/i2c-dev.h>
#include <net/if.h>
#include <netinet/in.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#define I2C_DEV    "/dev/i2c-1"
#define I2C_ADDR   0x3C
#define OLED_W     128
#define OLED_H     32
#define PAGES      (OLED_H / 8)          /* 4 pages of 8 vertical pixels */
/* Panel type, from LASERHAT_OLED_PANEL (default "ssd1305" = the Adafruit
 * 2.23" bonnet; "ssd1306" = a generic 0.91" 128x32 SSD1306 module on J10).
 * The SSD1305 has 132 column drivers for the 128-wide glass (columns are
 * offset by 4) and takes SSD1305-only setup commands that an SSD1306
 * misreads as other commands (hence random pixels on the wrong panel). */
static int panel_ssd1306 = 0;
static int col_offset = 4;               /* SSD1305 4, SSD1306 0 */
#define CELLS      (OLED_W / 6)          /* 5px glyph + 1px gap = 21 cells */
#define DOT_COL    120                   /* heartbeat dot cell, top right  */

#define DEFAULT_SOCK "/run/laserhat-oled/oled.sock"

#define TICK_MS      250                 /* repaint / poll cadence         */
#define NET_PHASE_S  3                   /* header alternation period      */
#define NET_POLL_S   2                   /* getifaddrs() cadence           */

static uint8_t fb[OLED_W * PAGES];       /* framebuffer, column-major pages */
static volatile sig_atomic_t running = 1;

/* ---- 5x7 font: one glyph = 5 column bytes, bit0 = top pixel ---- */
static const char font_index[] = " .:-/0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ?[]()><";
static const uint8_t font[][5] = {
    {0x00, 0x00, 0x00, 0x00, 0x00},  /* space */
    {0x00, 0x60, 0x60, 0x00, 0x00},  /* . */
    {0x00, 0x36, 0x36, 0x00, 0x00},  /* : */
    {0x08, 0x08, 0x08, 0x08, 0x08},  /* - */
    {0x60, 0x10, 0x08, 0x04, 0x03},  /* / */
    {0x3E, 0x51, 0x49, 0x45, 0x3E},  /* 0 */
    {0x00, 0x42, 0x7F, 0x40, 0x00},  /* 1 */
    {0x42, 0x61, 0x51, 0x49, 0x46},  /* 2 */
    {0x21, 0x41, 0x45, 0x4B, 0x31},  /* 3 */
    {0x18, 0x14, 0x12, 0x7F, 0x10},  /* 4 */
    {0x27, 0x45, 0x45, 0x45, 0x39},  /* 5 */
    {0x3C, 0x4A, 0x49, 0x49, 0x30},  /* 6 */
    {0x01, 0x71, 0x09, 0x05, 0x03},  /* 7 */
    {0x36, 0x49, 0x49, 0x49, 0x36},  /* 8 */
    {0x06, 0x49, 0x49, 0x29, 0x1E},  /* 9 */
    {0x7E, 0x09, 0x09, 0x09, 0x7E},  /* A */
    {0x7F, 0x49, 0x49, 0x49, 0x36},  /* B */
    {0x3E, 0x41, 0x41, 0x41, 0x22},  /* C */
    {0x7F, 0x41, 0x41, 0x41, 0x3E},  /* D */
    {0x7F, 0x49, 0x49, 0x49, 0x41},  /* E */
    {0x7F, 0x09, 0x09, 0x09, 0x01},  /* F */
    {0x3E, 0x41, 0x49, 0x49, 0x3A},  /* G */
    {0x7F, 0x08, 0x08, 0x08, 0x7F},  /* H */
    {0x00, 0x41, 0x7F, 0x41, 0x00},  /* I */
    {0x20, 0x40, 0x41, 0x3F, 0x01},  /* J */
    {0x7F, 0x08, 0x14, 0x22, 0x41},  /* K */
    {0x7F, 0x40, 0x40, 0x40, 0x40},  /* L */
    {0x7F, 0x02, 0x0C, 0x02, 0x7F},  /* M */
    {0x7F, 0x02, 0x04, 0x08, 0x7F},  /* N */
    {0x3E, 0x41, 0x41, 0x41, 0x3E},  /* O */
    {0x7F, 0x09, 0x09, 0x09, 0x06},  /* P */
    {0x3E, 0x41, 0x51, 0x21, 0x5E},  /* Q */
    {0x7F, 0x09, 0x19, 0x29, 0x46},  /* R */
    {0x46, 0x49, 0x49, 0x49, 0x31},  /* S */
    {0x01, 0x01, 0x7F, 0x01, 0x01},  /* T */
    {0x3F, 0x40, 0x40, 0x40, 0x3F},  /* U */
    {0x1F, 0x20, 0x40, 0x20, 0x1F},  /* V */
    {0x7F, 0x20, 0x18, 0x20, 0x7F},  /* W */
    {0x63, 0x14, 0x08, 0x14, 0x63},  /* X */
    {0x03, 0x04, 0x78, 0x04, 0x03},  /* Y */
    {0x61, 0x51, 0x49, 0x45, 0x43},  /* Z */
    {0x02, 0x01, 0x51, 0x09, 0x06},  /* ? */
    {0x00, 0x7F, 0x41, 0x41, 0x00},  /* [ */
    {0x00, 0x41, 0x41, 0x7F, 0x00},  /* ] */
    {0x00, 0x1C, 0x22, 0x41, 0x00},  /* ( */
    {0x00, 0x41, 0x22, 0x1C, 0x00},  /* ) */
    {0x00, 0x41, 0x22, 0x14, 0x08},  /* > */
    {0x08, 0x14, 0x22, 0x41, 0x00},  /* < */
};

static const uint8_t *glyph(char c)
{
    const char *p = strchr(font_index, toupper((unsigned char)c));
    if (!p)
        p = strchr(font_index, '?');
    return font[p - font_index];
}

/* ---- drawing into the framebuffer ---- */

static void draw_text(int page, int cell, const char *s)
{
    for (; *s && cell < CELLS; s++, cell++)
        memcpy(&fb[page * OLED_W + cell * 6], glyph(*s), 5);
}

/* Bottom-right status chip, mirroring the old PIL layout: a 2px gap,
 * then (for inverted) a filled box with the label knocked out of it. */
static void draw_chip(const char *label, int inverted)
{
    int len = (int)strlen(label);
    int cw = len * 6 + 5;
    int x0 = OLED_W - cw;
    int x;

    if (x0 < 2)
        return;
    memset(&fb[3 * OLED_W + x0 - 2], 0x00, cw + 2);
    for (x = x0 - 2; x < OLED_W; x++)          /* also the row of pixels  */
        fb[2 * OLED_W + x] &= 0x7F;            /* just above the chip box */

    if (inverted)
        memset(&fb[3 * OLED_W + x0], 0xFF, cw);
    for (int i = 0; i < len; i++)
        for (int c = 0; c < 5; c++)
            fb[3 * OLED_W + x0 + 3 + i * 6 + c] ^= glyph(label[i])[c];
}

/* ---- network state: first IPv4 on a wired (names eth… or en…) and a
 * wireless (wl…) interface; "WAITING" until one appears ---- */

struct netinfo {
    char eth[INET_ADDRSTRLEN + 1];
    char wifi[INET_ADDRSTRLEN + 1];
};

static void poll_net(struct netinfo *n)
{
    struct ifaddrs *addrs, *a;

    snprintf(n->eth, sizeof(n->eth), "WAITING");
    snprintf(n->wifi, sizeof(n->wifi), "WAITING");

    if (getifaddrs(&addrs) != 0)
        return;
    for (a = addrs; a; a = a->ifa_next) {
        if (!a->ifa_addr || a->ifa_addr->sa_family != AF_INET)
            continue;
        if ((a->ifa_flags & IFF_LOOPBACK) || !(a->ifa_flags & IFF_UP))
            continue;
        struct sockaddr_in *sin = (struct sockaddr_in *)a->ifa_addr;
        int wired = !strncmp(a->ifa_name, "eth", 3) ||
                    !strncmp(a->ifa_name, "en", 2);
        int wifi  = !strncmp(a->ifa_name, "wl", 2);
        if (wired && !strcmp(n->eth, "WAITING"))
            inet_ntop(AF_INET, &sin->sin_addr, n->eth, sizeof(n->eth));
        else if (wifi && !strcmp(n->wifi, "WAITING"))
            inet_ntop(AF_INET, &sin->sin_addr, n->wifi, sizeof(n->wifi));
    }
    freeifaddrs(addrs);
}

/* ---- UI model: what the client (or the built-in default) shows ---- */

struct ui {
    char tag[CELLS + 1];        /* header-left text for the tag phase */
    char row[3][CELLS + 1];     /* body rows 1..3                     */
    char chip[CELLS + 1];       /* "" = no chip                       */
    int  chip_inverted;
    int  client_connected;
};

/* Compose the whole frame.  net_phase: 0 = tag, 1 = E:, 2 = W:.
 * blink: heartbeat dot on/off. */
static void render_frame(const struct ui *u, const struct netinfo *n,
                         int net_phase, int blink, const char *hostname)
{
    char line[CELLS + 8];

    memset(fb, 0, sizeof(fb));

    switch (net_phase) {
    case 1:  snprintf(line, sizeof(line), "E:%s", n->eth);  break;
    case 2:  snprintf(line, sizeof(line), "W:%s", n->wifi); break;
    default: snprintf(line, sizeof(line), "%s", u->tag);    break;
    }
    line[CELLS - 1] = '\0';                 /* keep the dot cell clear */
    draw_text(0, 0, line);

    memset(&fb[0 * OLED_W + DOT_COL], 0, 6);
    if (blink)
        memcpy(&fb[0 * OLED_W + DOT_COL], glyph('.'), 5);

    if (u->client_connected) {
        for (int r = 0; r < 3; r++)
            draw_text(r + 1, 0, u->row[r]);
        if (u->chip[0])
            draw_chip(u->chip, u->chip_inverted);
    } else {
        /* boot / no-GUI screen: hostname + both addresses, static */
        draw_text(1, 0, hostname);
        snprintf(line, sizeof(line), "E:%s", n->eth);
        draw_text(2, 0, line);
        snprintf(line, sizeof(line), "W:%s", n->wifi);
        draw_text(3, 0, line);
    }
}

/* ---- I2C transport: control byte 0x00 = commands, 0x40 = data ---- */

static int oled_cmds(int fd, const uint8_t *cmds, size_t n)
{
    uint8_t buf[64];
    buf[0] = 0x00;
    memcpy(buf + 1, cmds, n);
    if (write(fd, buf, n + 1) != (ssize_t)(n + 1)) {
        perror("i2c command write");
        return -1;
    }
    return 0;
}

/* Init sequence per Adafruit's CircuitPython SSD1305 driver (the stack
 * this replaces), which is known-good on the 2.23" bonnet. */
static int oled_init(int fd)
{
    static const uint8_t init1306[] = {    /* SSD1306 128x32 (Solomon app note / Adafruit SSD1306 driver) */
        0xAE,                          /* display off                  */
        0xD5, 0x80,                    /* clock divide ratio           */
        0xA8, OLED_H - 1,              /* multiplex ratio: 32 rows     */
        0xD3, 0x00,                    /* display offset 0             */
        0x40,                          /* start line 0                 */
        0x8D, 0x14,                    /* charge pump on               */
        0x20, 0x00,                    /* horizontal addressing mode   */
        0xA1,                          /* segment remap (flip X)       */
        0xC8,                          /* COM scan reversed (flip Y)   */
        0xDA, 0x02,                    /* COM pins: sequential (128x32)*/
        0x81, 0x8F,                    /* contrast                     */
        0xD9, 0xF1,                    /* precharge                    */
        0xDB, 0x40,                    /* VCOMH deselect               */
        0xA4,                          /* resume from RAM              */
        0xA6,                          /* normal (not inverted)        */
        0x2E,                          /* deactivate scroll            */
        0xAF,                          /* display on                   */
    };
    if (panel_ssd1306)
        return oled_cmds(fd, init1306, sizeof(init1306));
    static const uint8_t init[] = {
        0xAE,                          /* display off                  */
        0xD5, 0x80,                    /* clock divide ratio           */
        0xA1,                          /* segment remap (flip X)       */
        0xA8, OLED_H - 1,              /* multiplex ratio: 32 rows     */
        0xD3, 0x00,                    /* display offset 0             */
        0xAD, 0x8E,                    /* master config: internal DC   */
        0xD8, 0x05,                    /* area color / low-power mode  */
        0x20, 0x00,                    /* horizontal addressing mode   */
        0x40,                          /* start line 0                 */
        0x2E,                          /* deactivate scroll            */
        0xC8,                          /* COM scan reversed (flip Y)   */
        0xDA, 0x12,                    /* COM pins: alternative        */
        0x91, 0x3F, 0x3F, 0x3F, 0x3F,  /* current-drive LUT            */
        0x81, 0xFF,                    /* contrast                     */
        0xD9, 0xD2,                    /* precharge                    */
        0xDB, 0x34,                    /* VCOMH deselect               */
        0xA6,                          /* normal (not inverted)        */
        0xA4,                          /* resume from RAM              */
        0x8D, 0x14,                    /* charge pump on (internal Vcc)*/
        0xAF,                          /* display on                   */
    };
    return oled_cmds(fd, init, sizeof(init));
}

static int oled_flush(int fd)
{
    const uint8_t window[] = {
        0x21, (uint8_t)col_offset, (uint8_t)(col_offset + OLED_W - 1),  /* column range */
        0x22, 0x00, PAGES - 1,                                          /* page range   */
    };
    if (oled_cmds(fd, window, sizeof(window)) < 0)
        return -1;

    uint8_t buf[1 + 64];
    for (size_t off = 0; off < sizeof(fb); off += 64) {
        size_t n = sizeof(fb) - off < 64 ? sizeof(fb) - off : 64;
        buf[0] = 0x40;
        memcpy(buf + 1, fb + off, n);
        if (write(fd, buf, n + 1) != (ssize_t)(n + 1)) {
            perror("i2c data write");
            return -1;
        }
    }
    return 0;
}

/* ---- panel reset: GPIO 4 low -> high via the GPIO character device.
 * The header chip is gpiochip0 on most Pis but not all (early Pi 5
 * kernels used gpiochip4), so find the chip whose line 4 is "GPIO4".
 * Non-fatal on failure: the panel usually comes up fine after a cold
 * power-on even without a reset pulse. ---- */

/* Open GPIO4 (the bonnet's panel reset) as an output; -1 when no chip has
 * it or the line is busy.  The caller closes the fd, which releases it. */
static int reset_line_open(void)
{
    char path[32];

    for (int chip = 0; chip < 8; chip++) {
        snprintf(path, sizeof(path), "/dev/gpiochip%d", chip);
        int cfd = open(path, O_RDONLY);
        if (cfd < 0)
            continue;

        struct gpio_v2_line_info info;
        memset(&info, 0, sizeof(info));
        info.offset = 4;
        if (ioctl(cfd, GPIO_V2_GET_LINEINFO_IOCTL, &info) < 0 ||
            strcmp(info.name, "GPIO4") != 0) {
            close(cfd);
            continue;
        }

        struct gpio_v2_line_request req;
        memset(&req, 0, sizeof(req));
        req.offsets[0] = 4;
        req.num_lines = 1;
        req.config.flags = GPIO_V2_LINE_FLAG_OUTPUT;
        strncpy(req.consumer, "oledd-reset", sizeof(req.consumer) - 1);
        if (ioctl(cfd, GPIO_V2_GET_LINE_IOCTL, &req) < 0) {
            close(cfd);
            return -1;                  /* right chip, line busy */
        }
        close(cfd);
        return req.fd;
    }
    return -1;
}

static void reset_line_set(int lfd, int high)
{
    struct gpio_v2_line_values v = { .mask = 1, .bits = high ? 1 : 0 };
    ioctl(lfd, GPIO_V2_LINE_SET_VALUES_IOCTL, &v);
}

static void sleep_ms(int ms)
{
    struct timespec t = { .tv_sec = ms / 1000, .tv_nsec = (ms % 1000) * 1000000L };
    nanosleep(&t, NULL);
}

/* Read the panel's status register (the only thing an SSD130x answers to
 * over I2C): -1 = no acknowledge at 0x3C. */
static int oled_status(int fd)
{
    uint8_t b;
    return read(fd, &b, 1) == 1 ? b : -1;
}

/* Which panel is on the bus?  The bonnet's SSD1305 has its reset pin on
 * GPIO4 and stops acknowledging while that line is held low; a 0.91"
 * module on J10 has no reset line to the Pi and keeps answering.  So:
 *   GPIO4 low  + ACK          -> SSD1306 module
 *   GPIO4 low  + no ACK, then
 *   GPIO4 high + ACK          -> SSD1305 bonnet
 *   no ACK either way         -> nothing on the bus (-1)
 * Returns 1 for the module, 0 for the bonnet.  The status byte differs
 * too in practice (0x41 bonnet, 0x42 module, reserved bits), which is
 * logged as a cross-check but not relied on.  Without a usable GPIO4
 * the result is -2 (caller keeps the configured default). */
static int detect_panel(int fd)
{
    int lfd = reset_line_open();
    if (lfd < 0)
        return -2;
    reset_line_set(lfd, 0);
    sleep_ms(10);
    int st_low = oled_status(fd);
    reset_line_set(lfd, 1);
    sleep_ms(10);
    int st_high = oled_status(fd);
    close(lfd);                         /* released; panel out of reset */
    if (st_low >= 0) {
        fprintf(stderr, "oledd: panel answers with GPIO4 reset low (status 0x%02x): SSD1306 module on J10%s\n",
                st_low, (st_low & 0x0F) == 0x01 ? " (status byte looks like the bonnet's, though)" : "");
        return 1;
    }
    if (st_high >= 0) {
        fprintf(stderr, "oledd: panel answers only out of reset (status 0x%02x): SSD1305 bonnet%s\n",
                st_high, (st_high & 0x0F) == 0x02 ? " (status byte looks like the module's, though)" : "");
        return 0;
    }
    return -1;
}

/* Pulse the bonnet's reset (harmless for the J10 module, which is not
 * connected to GPIO4). */
static void reset_panel(void)
{
    int lfd = reset_line_open();
    if (lfd < 0) {
        fprintf(stderr, "warning: could not pulse GPIO4 reset, continuing\n");
        return;
    }
    reset_line_set(lfd, 1); sleep_ms(10);
    reset_line_set(lfd, 0); sleep_ms(10);
    reset_line_set(lfd, 1); sleep_ms(10);
    close(lfd);
}

/* ---- Unix socket + line protocol ---- */

static int listen_on(const char *path)
{
    int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK, 0);
    if (fd < 0) {
        perror("socket");
        return -1;
    }
    struct sockaddr_un sa;
    memset(&sa, 0, sizeof(sa));
    sa.sun_family = AF_UNIX;
    strncpy(sa.sun_path, path, sizeof(sa.sun_path) - 1);
    unlink(path);
    if (bind(fd, (struct sockaddr *)&sa, sizeof(sa)) < 0 ||
        listen(fd, 1) < 0) {
        perror(path);
        close(fd);
        return -1;
    }
    chmod(path, 0666);      /* local UI socket on a single-user instrument */
    return fd;
}

/* Returns 1 if the command asked for an immediate repaint (FLUSH). */
static int handle_line(struct ui *u, char *line)
{
    char *cmd = strtok(line, " ");
    if (!cmd)
        return 0;

    if (!strcmp(cmd, "TAG")) {
        char *rest = strtok(NULL, "");
        snprintf(u->tag, sizeof(u->tag), "%s", rest ? rest : "");
    } else if (!strcmp(cmd, "ROW")) {
        char *num = strtok(NULL, " ");
        char *rest = strtok(NULL, "");
        int r = num ? atoi(num) : 0;
        if (r >= 1 && r <= 3)
            snprintf(u->row[r - 1], sizeof(u->row[0]), "%s", rest ? rest : "");
    } else if (!strcmp(cmd, "CHIP")) {
        char *label = strtok(NULL, " ");
        char *inv = strtok(NULL, " ");
        if (!label || !strcmp(label, "OFF")) {
            u->chip[0] = '\0';
        } else {
            snprintf(u->chip, sizeof(u->chip), "%s", label);
            u->chip_inverted = inv && atoi(inv);
        }
    } else if (!strcmp(cmd, "CLEAR")) {
        memset(u->row, 0, sizeof(u->row));
        u->chip[0] = '\0';
        u->tag[0] = '\0';
    } else if (!strcmp(cmd, "FLUSH")) {
        return 1;
    }
    return 0;
}

static void handle_signal(int sig)
{
    (void)sig;
    running = 0;
}

#ifndef OLEDD_NO_MAIN
/* Boot-screen tag: the board's name from the HAT ID EEPROM (the Pi firmware
 * publishes it under /proc/device-tree/hat at boot; mirror of hat_id.py's
 * tags), so the panel names the board before the GUI connects. */
static const char *boot_tag(void)
{
    char vendor[32] = "", product[32] = "";
    FILE *f = fopen("/proc/device-tree/hat/vendor", "rb");
    if (f) {
        size_t n = fread(vendor, 1, sizeof(vendor) - 1, f);
        vendor[n] = '\0';
        fclose(f);
    }
    f = fopen("/proc/device-tree/hat/product", "rb");
    if (f) {
        size_t n = fread(product, 1, sizeof(product) - 1, f);
        product[n] = '\0';
        fclose(f);
    }
    if (strcmp(vendor, "KemereLab") == 0) {
        if (strcmp(product, "StimHAT") == 0)
            return "STIMHAT";
        if (strcmp(product, "LaserDriverHAT") == 0)
            return "LASERDRV";
    }
    return "LASERHAT";
}

int main(void)
{
    const char *sock_path = getenv("LASERHAT_OLED_SOCK");
    const char *panel = getenv("LASERHAT_OLED_PANEL");
    int panel_auto = 1;                 /* LASERHAT_OLED_PANEL unset or "auto" */
    if (panel && strcmp(panel, "ssd1306") == 0) {
        panel_ssd1306 = 1;
        panel_auto = 0;
    } else if (panel && strcmp(panel, "ssd1305") == 0) {
        panel_auto = 0;
    } else if (panel && *panel && strcmp(panel, "auto") != 0) {
        fprintf(stderr, "oledd: unknown LASERHAT_OLED_PANEL '%s' (auto | ssd1305 | ssd1306), detecting\n", panel);
    }
    if (!sock_path || !*sock_path)
        sock_path = DEFAULT_SOCK;

    /* The unit starts very early in boot (sysinit), possibly before the
     * i2c-dev module has loaded or udev has set the device's group, so
     * retry the open for up to ~30 s instead of failing outright. */
    int i2c = -1;
    int waited = 0;
    for (; running && waited < 150; waited++) {
        i2c = open(I2C_DEV, O_RDWR);
        if (i2c >= 0)
            break;
        struct timespec ms200 = { .tv_sec = 0, .tv_nsec = 200 * 1000 * 1000 };
        nanosleep(&ms200, NULL);
    }
    if (i2c < 0) {
        perror("open " I2C_DEV);
        fprintf(stderr, "Is I2C enabled? (sudo raspi-config -> Interface Options)\n");
        return 1;
    }
    /* journald timestamps this — it marks the moment pixels can appear */
    fprintf(stderr, "panel bus ready after %d ms\n", waited * 200);
    if (ioctl(i2c, I2C_SLAVE, I2C_ADDR) < 0) {
        perror("ioctl I2C_SLAVE");
        return 1;
    }
    if (panel_auto) {
        /* The unit starts ~1 s into boot, before udev has made /dev/gpiochip*
         * group-readable, so the GPIO4 open fails at first: keep trying for
         * ~10 s (also covers a slow module).  -1 = nothing answered yet,
         * -2 = GPIO4 not usable (permissions, or another owner). */
        int det = -1;
        for (int tries = 0; running && tries < 50; tries++) {
            det = detect_panel(i2c);
            if (det >= 0)
                break;
            sleep_ms(200);
        }
        if (det == 1) {
            panel_ssd1306 = 1;
        } else if (det == -1) {
            fprintf(stderr, "oledd: no panel answers at 0x%02x; assuming the bonnet\n", I2C_ADDR);
        } else if (det == -2) {
            /* No reset line to probe with: fall back to the status byte's
             * reserved low bits, which differ in practice (0x41 SSD1305
             * bonnet, 0x42 SSD1306 module). */
            int st = oled_status(i2c);
            if (st >= 0 && (st & 0x0F) == 0x02)
                panel_ssd1306 = 1;
            fprintf(stderr, "oledd: GPIO4 unavailable for the reset probe; status byte 0x%02x -> %s "
                            "(set LASERHAT_OLED_PANEL to override)\n",
                    st < 0 ? 0 : st, panel_ssd1306 ? "SSD1306 module" : "SSD1305 bonnet");
        }
    }
    col_offset = panel_ssd1306 ? 0 : 4;
    fprintf(stderr, "oledd: panel %s%s\n", panel_ssd1306 ? "ssd1306 128x32 (J10 module)" : "ssd1305 (Adafruit bonnet)",
            panel_auto ? " [auto]" : " [configured]");
    reset_panel();
    if (oled_init(i2c) < 0)
        return 1;

    int lfd = listen_on(sock_path);
    if (lfd < 0)
        return 1;

    struct sigaction sa = { .sa_handler = handle_signal };
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);
    signal(SIGPIPE, SIG_IGN);

    char hostname[CELLS + 1] = "?";
    gethostname(hostname, sizeof(hostname) - 1);

    struct ui u;
    memset(&u, 0, sizeof(u));
    snprintf(u.tag, sizeof(u.tag), "%s", boot_tag());

    struct netinfo net;
    poll_net(&net);

    int cfd = -1;
    char inbuf[512];
    size_t inlen = 0;
    time_t last_net_poll = time(NULL);

    unsigned tick = 0;
    int ticks_per_s = 1000 / TICK_MS;

    while (running) {
        struct pollfd pfds[2] = {
            { .fd = lfd, .events = POLLIN },
            { .fd = cfd, .events = POLLIN },   /* fd -1 = ignored */
        };
        poll(pfds, 2, TICK_MS);

        if (pfds[0].revents & POLLIN) {
            int nfd = accept(lfd, NULL, NULL);
            if (nfd >= 0) {
                if (cfd >= 0) {
                    close(cfd);        /* newest client wins */
                    inlen = 0;
                }
                cfd = nfd;
                memset(u.row, 0, sizeof(u.row));
                u.chip[0] = '\0';
                u.client_connected = 1;
            }
        }

        int want_flush = 0;
        if (cfd >= 0 && (pfds[1].revents & (POLLIN | POLLHUP))) {
            if (inlen >= sizeof(inbuf) - 1) {
                inlen = 0;   /* a line longer than the buffer: drop it; also keeps the
                              * fortified read() bound provably in range (gcc 13+ -Werror) */
            }
            ssize_t n = read(cfd, inbuf + inlen, sizeof(inbuf) - 1 - inlen);
            if (n <= 0) {
                close(cfd);
                cfd = -1;
                inlen = 0;
                u.client_connected = 0;
            } else {
                inlen += (size_t)n;
                inbuf[inlen] = '\0';
                char *start = inbuf, *nl;
                while ((nl = strchr(start, '\n'))) {
                    *nl = '\0';
                    want_flush |= handle_line(&u, start);
                    start = nl + 1;
                }
                inlen = strlen(start);
                memmove(inbuf, start, inlen + 1);
                if (inlen >= sizeof(inbuf) - 2)
                    inlen = 0;         /* garbage line longer than buffer */
            }
        }

        time_t now = time(NULL);
        if (now - last_net_poll >= NET_POLL_S) {
            last_net_poll = now;
            poll_net(&net);
        }

        /* tag / E: / W: header phases, NET_PHASE_S seconds each */
        int net_phase = (int)((now / NET_PHASE_S) % 3);
        int blink = (tick / ticks_per_s) & 1;   /* 1 Hz from 250ms ticks */
        tick++;

        render_frame(&u, &net, net_phase, blink, hostname);
        if (oled_flush(i2c) < 0)
            break;
        (void)want_flush;   /* repaint happens every tick anyway */
    }

    /* blank + power the panel down on exit so pixels don't burn in */
    memset(fb, 0, sizeof(fb));
    oled_flush(i2c);
    uint8_t off = 0xAE;
    oled_cmds(i2c, &off, 1);
    close(i2c);
    if (cfd >= 0)
        close(cfd);
    close(lfd);
    unlink(sock_path);
    return 0;
}
#endif /* OLEDD_NO_MAIN */
