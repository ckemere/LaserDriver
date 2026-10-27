---
name: laserhat-next-tasks
description: "Status 2026-10-27: BatteryPack rev C (two hobby 4S packs on one 100 x 100 board, one charger) built and committed on branch battery-pack, awaiting the user's review; firmware version check in v0.2.0-rc7; module firmware untested on modules; next = user tests TESTING.md 10-11, then merge pcb-rev2 into main"
metadata:
  type: project
---

0h. **2026-10-27 (later): BatteryPack rev C = two hobby 4S packs on one 100 × 100 board** (user chose the hobby-pack idea
   from 0g and kept the charger).  J5/J6 JST-XH right-angle sockets take any 4S pack's balance plug (pin 1 black = pack
   negative); packs strap under the board (slots at x 3–6.5 / 45.75–50.25 / 90.5–94, y 39–61; 40 mm standoffs).  Circuit:
   pack A = −V side (GND..+BAT), pack B = +V side (0V..+BATB); MTS-203 pole 1 (common 0V): RUN → +BAT (series), CHARGE →
   GND (negatives joined); pole 2 (common +BATB): RUN → +RUN → F1 → Q1 (P) → +OUT, CHARGE → +CHGB → F3 (1.1 A PTC) → +BAT
   (positives joined: both packs in parallel on the one CN3704, 0.5 A each).  −V chain: GND → F2 → Q11 (N-FET in pack A's
   negative, gate = +BAT/2 only in RUN via R39 from 0V, U2B cutoff with swapped inputs, R11 470k hysteresis, Q14 lights
   D1).  Second gauge (U14–U16, R45–R57, D11–D14) on +GB/0V; +G = 0V or +CHGB via D15/D16.  VBUS switch Q13 (P) + Q12
   (gate on +CHGB): the charger sees VBUS only in CHARGE, so a brick in RUN/OFF does nothing (CH224A CFG1-floating
   behaviour is undefined, so the inhibit is on VBUS, not CFG1).  No stack cable / J4 / slave enable; CGND merged into
   GND.  Checks: netcheck OK, ERC 0, DRC 0/0/0, path/sync 0, lcsc_check all codes (toggle stock 192), fab 136 placements /
   44 BOM lines.  `tools/autoroute.py` now runs rip / stubs / DSN / SES each in its own process (pcbnew segfaulted
   otherwise), gives fine-pitch pads on 0.8 mm nets a 2 mm stub, and prunes stubs per layer; `place.py` adds copper
   keep-outs round the slots (Freerouting ignored the edge clearance there).  Not ordered.  User checks: toggle lever
   direction, pack plug polarity vs silk, JLC rotations, first charge (README).  Later the same day: XT60 sockets J7 / J8 (Amass XT60PW-M,
   C98732, 15.6k stock, $0.60 vs $0.38 for an XT30PW) added at the front edge inboard of the XH sockets, so the pack's
   discharge lead carries the run and charge current and the balance lead only the taps (XH pins 1 / 5 parallel the
   XT60; XT30 packs need an adapter — the user chose XT60).  Pack B's ON LED moved into its LED column (R54 on +OUT
   beside Q1, thin net to D11 at (97.5, 78)); chain B now right of gauge B (x 81–90, y 62–80), toggle (49, 84) and J3
   (45.5, 94.5) between the XT60s.  `tools/autoroute.py`'s pipeline still ends with remove_dangling; `trim_stubs` is run
   after it by hand (import autoroute; trim_stubs(BOARD)) and is what clears the last track_dangling warnings.  XT60PW-M footprint copied into battpack.pretty so its 3D model
   (`battpack.3dshapes/XT60PW-M.step`, built by `tools/make_xt60_model.py` with CadQuery from KiCad's vertical XT60-M
   housing + Amass drawing XT60PW-M30) renders; KiCad 9 ships no model for the horizontal part.  Then H5–H8 M2.5 (29.5/87.5, 7.5/56.5) = Raspberry Pi 58 × 49 pattern so the Pi + HAT
   sit above the board (y 4–60, ports end 11 mm past the right edge, ≥ 11 mm standoffs); balancer rows moved up 3 mm (pack B 1 mm left),
   CHRG / DONE moved to the top edge (y 2.5, x 66–84, outside the Pi; the right-edge route past the standoff
   and slot keep-outs was unroutable), R9–R11 and C3 nudged; rule
   areas (no vias, r 3.0) under the Pi standoffs — a no-tracks version made the left pack's C1 run unroutable.  Datasheets in `BatteryPack/parts/ds/`
   (git-ignored).  Rev B (18650 clips, stacked boards) = commit 6fa6e9d.
0g. **Ideas to come back to (user, 2026-10-27; not scheduled, nothing built):**
   (a) **Stimulator on the battery board.**  Since the e-stim module needs its own pack board anyway, consider one PCB
   that carries the cells, chargers and the stimulator circuit (DAC, Howland stage, switches, fault comparator) with
   the isolators on it, and a standard cable (ribbon or shielded multi-way) carrying the HAT's module lines (EN, CATH,
   RELEASE, FAULT_n, SDA, SCL, +5V, +3V3, GND = J8/J9) from the Pi/HAT.  The HAT stays as it is: the "module" in J8/J9
   becomes a passive breakout to the cable.  The pluggable-module concept stays for the laser.
   (b) **18350 cells instead of 18650** (35 mm long, same 18 mm diameter, ~1000 mAh): both 4S packs fit one 100 × 120
   board (two cells end to end per row, the same MYOUNG clips 18 mm apart instead of 48), so one board gives ±V: one
   USB-C + CH224A feeding two CN3704s on a common CGND (the series link is opened in CHARGE), one toggle, no stack cable
   / J4 / slave enable, charge current halved (R25+R26 0.4 R).  Run time is not the issue (module ≈ 10 mA + gauge
   5–8 mA → 60+ h on 18350); the trade is cell sourcing (vape/flashlight brands, few protected cells) vs size and weight.
   (a) + (b) together = the whole stimulator on one board.
0f. **2026-10-26: `BatteryPack/` rev B built end to end** (4S 18650 pack board, two stacked = ±V for the e-stim module): on-board USB-C PD charger (CH224A 20 V + CN3704 1 A / 16.8 V), HY2213 balancer per cell, MTS-203 RUN/OFF/CHARGE toggle (pole 2 switches the output ground in RUN and the USB-C ground in CHARGE, so charging boards can never loop through a shared-negative brick), LM393 cutoff + 3-LED gauge, 4-wire stack cable with a slave enable (upper toggle runs both boards). Schematic generated (ERC 0, netcheck OK); board placed by `tools/place.py` and routed with Freerouting headless (user is remote); DRC 0/0, path/sync checks 0, `lcsc_check` clean, `tools/make_fab.py` → `fab/BatteryPack/`.  Committed on branch `battery-pack` 2026-10-27; not ordered.  2026-10-27: at the user's request the board grew to 100 × 120 mm and was re-placed + rerouted by `tools/place.py` + new `tools/autoroute.py` (rip-up, pad stubs, Freerouting headless, stub clean-up): all cells + left / − right with 4 mm silk marks, balancers beside their clips, toggle between the headers and the charger, gauge LEDs by their comparators (DRC 0/0); JLC upload: the board footprints had no `LCSC Part #` field (the user's Fabrication Toolkit BOM came out without codes, six descriptive-value parts unmatched) → `tools/stamp_fields.py` stamps the field + values + hole exclusions onto the PCB, the generator writes `LCSC Part #` into the symbols, named parts' values = JLC model strings; the module end of the supply cable is PS1 pads 6/5/4 = +V/0V/−V on the e-stim board until its next rev gets the PH-4 socket.  User to check: toggle lever direction vs the RUN/CHG silk (meter), JLC DFM rotations, first-charge measurements (README).  E-stim next rev: PH-4 socket (+V / 0 V / −V / nc) beside PS1.
0d. **2026-10-20:** no light pulses — the MCU was still on v0.2.0-rc1 (never reflashed; rc1 has no laser
   DAC set-point).  Added firmware version reporting + validation in `v0.2.0-rc7` (rc6 failed CI, superseded): `CMD_GET_VERSION` → `RSP_VERSION`
   (`PROTO_VERSION` 2, `version.c` string = deb VERSION), broker probe once per MCU boot (`fw_version`/`fw_proto`/
   `fw_expected`/`fw_ok`, `--fw-version-file`), web banner, OLED `FW!` chip, `laserhat-flash` verifies after writing,
   `laser_hat.py version`.  Old firmware ignores the command (timeout = "older than rc7 or blank").
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
