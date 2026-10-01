---
name: laserhat-next-tasks
description: "Status 2026-10-01: all three Rev 2 boards ordered from JLC (fab/orders/); next = bring-up, then merge pcb-rev2 into main; Rev 2 firmware pin map still to write"
metadata:
  type: project
---

0. **2026-10-01: HAT, laser module and e-stim module ordered** (archives in `fab/orders/`). When the hardware
   works, merge `pcb-rev2` into `main`. Bring-up needs the Rev 2 firmware pin map (`Firmware/` is still Rev 1 apart
   from `make flash HAT_REV=2`): buttons active-low on PA13/14/16/21/23, PWM on PA7/PA12 (TIMA0), FAULT PA6, UART1 to the Pi.
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
