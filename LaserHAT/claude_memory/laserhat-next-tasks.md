---
name: laserhat-next-tasks
description: "Status 2026-10-14: boards arrived; Rev 2 bring-up firmware written (HAT only, no modules); next = flash and run Firmware/TESTING.md, then module firmware, then merge pcb-rev2 into main"
metadata:
  type: project
---

0. **2026-10-14: boards arrived (ordered 2026-10-01, archives in `fab/orders/`).  Rev 2 bring-up firmware committed**
   (`Firmware/`, HAT alone: buttons, LED, J8 PWM, BNCs, both UARTs; Pi side moved to GPIO26 trigger / GPIO18 power /
   GPIO23 NRST; Rev 1 firmware = tag `firmware-rev1`).  Next: the user flashes and walks `Firmware/TESTING.md`; then
   module firmware (laser: DAC setpoint + ADC readback; e-stim: spec §7 sequencing, bit-banged I²C, TIMA0 fault);
   Pi header socket HLE-120-02-F-DV-BE ordered from Mouser.  When the hardware works, merge `pcb-rev2` into `main`.
1. **Route `EStimDaughter/EStimDaughter.kicad_pcb` by hand** (the user, possibly with a second Claude session working
   — done, rev M4c). Then DRC with the project rules, `tools/netcheck.py`, `tools/jlc_fab.py`.
2. **HAT:** e-stim outline (y 76–109, the M4c board) drawn on User.Drawings 2026-09-30 — done. Optionally the BNC
   courtyard margin, via jags and angled pad entries listed in [[hat-manual-routing-handoff]]; decide whether PA6/FAULT_n
   gets a HAT pull-up (the laser module leaves J8.3 open).
3. **Battery packs:** decide on a keyed JST-PH 3-pin connector (+V / 0V / −V) beside PS1, reverse-polarity Schottkys,
   and a switch; 4S Li-ion is the target (5S exceeds the OPA2192's ±18 V).
4. **Firmware** for e-stim mode per spec §7: bit-banged I²C on PA17/PA22, RELEASE on PA15, latched TIMA0 fault.

**Why:** the M4 design is final on paper; the layout and the firmware are what remains before ordering.
**How to apply:** all three boards are hand-routed — never rebuild one; check `.lck` files before writing boards.

Related: [[estim-module-status]], [[laserhat-user-preferences]].
