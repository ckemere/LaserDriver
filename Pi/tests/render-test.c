/*
 * render-test.c — compile the real oledd drawing code (font, text, chip,
 * header composition) without its main(), render two known screens, and
 * print the framebuffers as ASCII art.  CI diffs the output against
 * render-expected.txt, so any accidental change to the font table or
 * layout logic fails the build.
 *
 * Build:  gcc -O2 -Wall -Wextra -Werror -o render-test tests/render-test.c
 * Run:    ./render-test | diff - tests/render-expected.txt
 */
#define OLEDD_NO_MAIN
#pragma GCC diagnostic ignored "-Wunused-function"
#include "../oledd.c"

static void dump(const char *title)
{
    printf("== %s ==\n", title);
    for (int y = 0; y < OLED_H; y++) {
        for (int x = 0; x < OLED_W; x++)
            putchar((fb[(y / 8) * OLED_W + x] >> (y % 8)) & 1 ? '#' : '.');
        putchar('\n');
    }
}

int main(void)
{
    struct netinfo net;
    snprintf(net.eth, sizeof(net.eth), "192.168.17.10");
    snprintf(net.wifi, sizeof(net.wifi), "WAITING");

    /* Screen 1: no client — boot screen, wired-IP header phase, dot on */
    struct ui u;
    memset(&u, 0, sizeof(u));
    snprintf(u.tag, sizeof(u.tag), "LASERHAT");
    render_frame(&u, &net, 1, 1, "laserhat-pi");
    dump("boot screen, E: phase, dot on");

    /* Screen 2: GUI client connected — tag phase, param rows, TRIG chip,
     * dot off.  Exercises every glyph class: [ ] ( ) > : / - digits. */
    u.client_connected = 1;
    snprintf(u.tag, sizeof(u.tag), "LASERHAT[L]");
    snprintf(u.row[0], sizeof(u.row[0]), ">i:100/320");
    snprintf(u.row[1], sizeof(u.row[1]), " r:2000(20ms)");
    snprintf(u.row[2], sizeof(u.row[2]), " [mode:LASER]");
    snprintf(u.chip, sizeof(u.chip), "TRIG");
    u.chip_inverted = 1;
    render_frame(&u, &net, 0, 0, "laserhat-pi");
    dump("gui client, tag phase, TRIG chip");

    return 0;
}
