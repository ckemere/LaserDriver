#ifndef SYSCTL_H
#define SYSCTL_H

/*
 * System control init — register-level replacement for the SYSCTL portion
 * of SysConfig's SYSCFG_DL_init().  Targets MSPM0G3507 (G3x0x family).
 *
 * After laser_sysctl_init():
 *   - BOR threshold = level 0 (min, reset on under-voltage)
 *   - SYSOSC = base frequency (32 MHz, BUSCLK source)
 *   - HFXT and SYSPLL disabled (defaults; explicit for determinism)
 *   - MFPCLK enabled, sourced from SYSOSC (required for DAC clock)
 *
 * Safe to call once at boot before any peripheral init that depends on
 * bus clock or MFPCLK.
 */

void laser_sysctl_init(void);

#endif /* SYSCTL_H */
