/*
 * Which HAT is the Pi on?  C mirror of the parts of Pi/hat_id.py the broker
 * needs at startup: the board identity from the HAT ID EEPROM (published by
 * the Pi firmware at boot under /proc/device-tree/hat/) and the board's
 * trigger GPIO.  See hat_id.py for the full story; keep the tables in sync.
 *
 * Board precedence: the EEPROM when it names one of our products (vendor
 * "KemereLab" + product_id), else --board, else $LASERHAT_BOARD, else Rev 2.
 * Unlike the Python tools there is no --force here: a --board that
 * contradicts the EEPROM is reported and ignored.
 */

#include "brokerd.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const BoardDef g_boards[] = {
    /* name     product           pid     fw type            trigger */
    { "rev2",  "LaserHAT Rev 2", 0x0002, BOARD_TYPE_REV2,  26 },
    { "stim",  "StimHAT",        0x0003, BOARD_TYPE_STIM,  18 },
    { "laser", "LaserDriverHAT", 0x0004, BOARD_TYPE_LASER, 18 },
};
#define N_BOARDS (sizeof g_boards / sizeof g_boards[0])

const BoardDef *board_by_name(const char *name)
{
    for (size_t i = 0; name && i < N_BOARDS; i++) {
        if (strcmp(g_boards[i].name, name) == 0) {
            return &g_boards[i];
        }
    }
    return NULL;
}

const char *board_type_name(unsigned fw_type)
{
    for (size_t i = 0; i < N_BOARDS; i++) {
        if (g_boards[i].fw_type == fw_type) {
            return g_boards[i].name;
        }
    }
    return "unknown";
}

/* One device-tree string property (NUL-terminated in the file). */
static bool read_prop(const char *dir, const char *name, char *out, size_t cap)
{
    char path[512];
    snprintf(path, sizeof path, "%s/%s", dir, name);
    FILE *f = fopen(path, "rb");
    if (!f) {
        return false;
    }
    size_t n = fread(out, 1, cap - 1, f);
    fclose(f);
    out[n] = '\0';
    out[strcspn(out, "\r\n")] = '\0';
    return true;
}

const BoardDef *board_from_eeprom(const char *hat_dir, bool *present)
{
    char vendor[64] = "", product[64] = "", pid[32] = "";
    bool have_v = read_prop(hat_dir, "vendor", vendor, sizeof vendor);
    bool have_p = read_prop(hat_dir, "product", product, sizeof product);
    read_prop(hat_dir, "product_id", pid, sizeof pid);
    *present = have_v || have_p;
    if (!*present || strcmp(vendor, "KemereLab") != 0) {
        return NULL;
    }
    char *end;
    long id = strtol(pid, &end, 0);
    for (size_t i = 0; i < N_BOARDS; i++) {
        if ((end != pid && id == g_boards[i].pid)
                || strcmp(product, g_boards[i].product) == 0) {
            return &g_boards[i];
        }
    }
    return NULL;
}

const BoardDef *board_resolve(const char *hat_dir, const char *arg,
                              const char **source)
{
    bool present = false;
    const BoardDef *eeprom = board_from_eeprom(hat_dir, &present);
    const BoardDef *want = board_by_name(arg);
    if (eeprom) {
        if (want && want != eeprom) {
            fprintf(stderr, "brokerd: --board %s ignored: the HAT EEPROM says %s\n",
                    want->name, eeprom->name);
        }
        *source = "eeprom";
        return eeprom;
    }
    if (present) {
        fprintf(stderr, "brokerd: HAT EEPROM in %s is not a LaserHAT-family board\n",
                hat_dir);
    }
    if (want) {
        *source = "argument";
        return want;
    }
    const BoardDef *env = board_by_name(getenv("LASERHAT_BOARD"));
    if (env) {
        *source = "env";
        return env;
    }
    *source = "default";
    return &g_boards[0];
}
