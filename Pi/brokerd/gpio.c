/*
 * The trigger line: Pi GPIO 24 -> MSPM0 PA19 (LaserHAT/gpio_design.md).
 *
 * GPIO_GPIOMEM drives the BCM2711 (Raspberry Pi 4) GPIO block directly
 * through /dev/gpiomem: raising the line is one store to GPSET0, no
 * syscall.  The register layout is the BCM2835-family one (Pi 0-4); the
 * Pi 5 moved GPIO behind RP1 and has no /dev/gpiomem, so this backend
 * fails cleanly there.
 *
 * The MCU latches the rising edge in hardware (GROUP1 edge interrupt) and
 * starts the pulse on its next 10 us tick, so the high time only has to
 * be long enough to be a clean edge; it is not a timing parameter.
 */

#include "brokerd.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

/* Word offsets into the GPIO block. */
#define GPFSEL0   0u        /* 0x00: function select, 10 pins per word */
#define GPSET0    7u        /* 0x1C: write 1 = drive high (pins 0-31) */
#define GPCLR0   10u        /* 0x28: write 1 = drive low  (pins 0-31) */
#define GPIO_MAP_LEN 4096u

static GpioBackend        g_backend = GPIO_NONE;
static volatile uint32_t *g_regs;
static uint32_t           g_mask;
static int                g_pin;

static void set_function(uint32_t fsel)
{
    volatile uint32_t *reg = &g_regs[GPFSEL0 + (uint32_t)g_pin / 10u];
    unsigned shift = ((unsigned)g_pin % 10u) * 3u;
    *reg = (*reg & ~(7u << shift)) | (fsel << shift);
}

static void warn_if_not_bcm2711(void)
{
    char compat[256] = "";
    FILE *f = fopen("/proc/device-tree/compatible", "r");
    if (f) {
        size_t n = fread(compat, 1, sizeof compat - 1, f);
        fclose(f);
        for (size_t i = 0; i < n; i++) {
            if (compat[i] == '\0') compat[i] = ' ';   /* NUL-separated list */
        }
        compat[n] = '\0';
    }
    if (strstr(compat, "brcm,bcm2711") == NULL) {
        fprintf(stderr, "brokerd: warning: not a BCM2711 (Pi 4); compatible = '%s'\n",
                compat);
    }
}

int gpio_open(GpioBackend backend, int pin)
{
    g_pin = pin;
    g_mask = 1u << (unsigned)pin;
    if (backend != GPIO_GPIOMEM) {
        g_backend = backend;
        return 0;
    }
    if (pin < 0 || pin > 27) {
        fprintf(stderr, "brokerd: GPIO pin %d out of range\n", pin);
        return -1;
    }
    warn_if_not_bcm2711();
    int fd = open("/dev/gpiomem", O_RDWR | O_SYNC | O_CLOEXEC);
    if (fd < 0) {
        fprintf(stderr, "brokerd: open /dev/gpiomem: %s\n", strerror(errno));
        return -1;
    }
    void *m = mmap(NULL, GPIO_MAP_LEN, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (m == MAP_FAILED) {
        fprintf(stderr, "brokerd: mmap /dev/gpiomem: %s\n", strerror(errno));
        return -1;
    }
    g_regs = m;
    /* Latch the output low BEFORE switching to output, so claiming the pin
     * can never produce a rising edge (which would fire the laser). */
    g_regs[GPCLR0] = g_mask;
    set_function(1u);                   /* 001 = output */
    g_regs[GPCLR0] = g_mask;
    g_backend = GPIO_GPIOMEM;
    return 0;
}

bool gpio_available(void) { return g_backend != GPIO_NONE; }
bool gpio_is_sim(void)    { return g_backend == GPIO_SIM; }

bool gpio_pulse(uint32_t width_ns, struct timespec *edge)
{
    if (g_backend == GPIO_NONE) {
        return false;
    }
    if (g_regs) {
        g_regs[GPSET0] = g_mask;
    }
    clock_gettime(CLOCK_REALTIME, edge);

    struct timespec t0, t;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    do {
        clock_gettime(CLOCK_MONOTONIC, &t);
    } while (ts_to_ns(&t) - ts_to_ns(&t0) < width_ns);

    if (g_regs) {
        g_regs[GPCLR0] = g_mask;
    }
    return true;
}

/* Called at exit.  The mapping is deliberately left in place: the trigger
 * thread may still be inside gpio_pulse(), and a late GPSET/GPCLR on an
 * input pin only touches the output latch. */
void gpio_close(void)
{
    g_backend = GPIO_NONE;              /* new pulses become no-ops */
    if (g_regs) {
        /* Drive low, then release to input; the MCU's PA19 pull-down holds
         * the line low, so the release is not an edge. */
        g_regs[GPCLR0] = g_mask;
        set_function(0u);               /* 000 = input */
        g_regs[GPCLR0] = g_mask;
    }
}
