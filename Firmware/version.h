#ifndef VERSION_H
#define VERSION_H

/* The firmware's own version string, baked in at build time (version.c).
 * Reported in RSP_VERSION so the Pi can tell whether the MCU runs the
 * firmware that shipped with the installed package. */
extern const char fw_version[];

#endif /* VERSION_H */
