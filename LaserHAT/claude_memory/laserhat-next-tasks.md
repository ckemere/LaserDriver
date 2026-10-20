---
name: laserhat-next-tasks
description: "Status 2026-10-20: firmware version check in v0.2.0-rc6 (MCU had never been reflashed past rc1 -> no laser current); HAT firmware works on hardware; module firmware in v0.2.0-rc3 (laser DAC zero between pulses, e-stim spec §7, fault latch), untested on modules; next = user tests TESTING.md steps 10-11 (multimeter checks added), then merge pcb-rev2 into main"
metadata:
  type: project
---

0d. **2026-10-20:** no light pulses — the MCU was still on v0.2.0-rc1 (never reflashed; rc1 has no laser
   DAC set-point).  Added firmware version reporting + validation in `v0.2.0-rc6`: `CMD_GET_VERSION` → `RSP_VERSION`
   (`PROTO_VERSION` 2, `version.c` string = deb VERSION), broker probe once per MCU boot (`fw_version`/`fw_proto`/
   `fw_expected`/`fw_ok`, `--fw-version-file`), web banner, OLED `FW!` chip, `laserhat-flash` verifies after writing,
   `laser_hat.py version`.  Old firmware ignores the command (timeout = "older than rc6 or blank").
0c. **2026-10-19:** e-stim module on the bench: RB-0515D/HP fitted, 5 V on its leads, outputs at ±1.5 V (folded back),
   nothing loading the rails (40 kΩ to Com, 20 kΩ on +5V_ISO).  Next: feed ±9 V from batteries into pins 6/5/4 and
   measure the draw (expect ≈9 mA / ≈1.5 mA) → if fine, the converter is faulty (warranty).  Laser module: boost reads
   11.82 V (nominal R5/R6), 5 V OK; J5 RED is 2.00 mm pitch (Harwin M22-2510205 header + M22-1900005 shunt; issue text
   drafted, not posted — no GitHub token here).  Suspected SD-card corruption from HAT power cycles → safe shutdown
   added (`Pi/power.py`, `laserhat-power.path`, OLED `[off]` row, web "shut down"/"reboot"), tag `v0.2.0-rc4`.
0b. **2026-10-15:** rc2 held the laser DAC at the setpoint continuously; the module's cascode rule (REV2_NOTES "Q1 is a
   cascode": no dummy current between pulses) says it must be zero between pulses.  Fixed in `v0.2.0-rc3` (DAC0 written at
   trigger, zeroed at pulse end; `current` mid-pulse applies at once).  TESTING.md 10/11 now have multimeter-only checks
   (laser: `config 1 1 10000000` long pulse, Rs1 0.20 V = 100 mA; e-stim: rails vs TP2, VSET_P = 0.25 V at code 820).
   PS1 for the e-stim module ordered from Mouser (919-RB-0515D/HP).
0a. **2026-10-14 evening: the user flashed v0.2.0-rc1 and reported "Success!" (HAT alone).**  Module firmware then
   written (LASER: DAC0 setpoint `CMD_LASER_CURRENT` + ADC1 readback; ESTIM: spec §7 GPIO sequencing, bit-banged
   I²C DAC60501 `CMD_ESTIM_CURRENT`, FAULT_n GPIO-IRQ latch `EVT_FAULT`/`CMD_CLEAR_FAULT`; STATUS = 34 bytes; boot
   blink 4 s → 2 s).  Not yet run with a module; `Firmware/TESTING.md` steps 10–11 are the plan.  Still open: the
   wheel roll direction (B3/B4), whether SWD attaches outside the boot blink (then shorten it further).
0. **2026-10-14: boards arrived (ordered 2026-10-01, archives in `fab/orders/`).  Rev 2 bring-up firmware committed**
   (`Firmware/`, HAT alone: buttons, LED, J8 PWM, BNCs, both UARTs; Pi side moved to GPIO26 trigger / GPIO18 power /
   GPIO23 NRST; Rev 1 firmware = tag `firmware-rev1`).  Next: the user flashes and walks `Firmware/TESTING.md`; then
   module firmware (laser: DAC setpoint + ADC readback; e-stim: spec §7 sequencing, bit-banged I²C, TIMA0 fault);
   Pi header socket HLE-120-02-F-DV-BE ordered from Mouser.  **Delivery = tag:** `main` (C broker, Debian package,
   `.github/workflows/pi-deploy.yml`) was merged into `pcb-rev2` on 2026-10-14; pushing a `v*` tag builds the debs and
   the golden Raspberry Pi OS images with this firmware (first Rev 2 tag: `v0.2.0-rc1`); on the Pi `sudo laserhat-flash`
   programs the MCU with the Rev 2 pins in `Firmware/openocd/pi-swd.cfg`.  When the hardware works, merge `pcb-rev2` into `main`.
1. **Route `EStimDaughter/EStimDaughter.kicad_pcb` by hand** (the user, possibly with a second Claude session working
   — done, rev M4c). Then DRC with the project rules, `tools/netcheck.py`, `tools/jlc_fab.py`.
2. **HAT:** e-stim outline (y 76–109, the M4c board) drawn on User.Drawings 2026-09-30 — done. Optionally the BNC
   courtyard margin, via jags and angled pad entries listed in [[hat-manual-routing-handoff]]; decide whether PA6/FAULT_n
   gets a HAT pull-up (the laser module leaves J8.3 open).
3. **Battery packs:** decide on a keyed JST-PH 3-pin connector (+V / 0V / −V) beside PS1, reverse-polarity Schottkys,
   and a switch; 4S Li-ion is the target (5S exceeds the OPA2192's ±18 V).
4. **Firmware** for e-stim mode per spec §7 — done 2026-10-14 (GPIO-IRQ fault latch instead of TIMA0 FAULT0, since the
   e-stim lines are GPIO-driven); needs hardware confirmation.

**Why:** the M4 design is final on paper; the layout and the firmware are what remains before ordering.
**How to apply:** all three boards are hand-routed — never rebuild one; check `.lck` files before writing boards.

Related: [[estim-module-status]], [[laserhat-user-preferences]].
