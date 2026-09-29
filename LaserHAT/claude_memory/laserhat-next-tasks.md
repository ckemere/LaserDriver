---
name: laserhat-next-tasks
description: "Next LaserHAT tasks as of 2026-09-29: hand-route the rev M4 e-stim board, extend the HAT's module keep-out to y 112.5, decide the battery connector, regenerate fab outputs after routing"
metadata:
  type: project
---

1. **Route `EStimDaughter/EStimDaughter.kicad_pcb` by hand** (the user, possibly with a second Claude session working
   from `EStimDaughter/LAYOUT_HANDOFF.md`). Then DRC with the project rules, `tools/netcheck.py`, `tools/jlc_fab.py`.
2. **HAT:** extend the `DAUGHTERBOARD` keep-out and the Dwgs.User outline marker on `LaserDriver.kicad_pcb` to
   y 112.5 (user's edit — scripted edits of the hand-routed HAT are refused). Optionally the BNC courtyard margin,
   via jags and angled pad entries listed in [[hat-manual-routing-handoff]].
3. **Battery packs:** decide on a keyed JST-PH 3-pin connector (+V / 0V / −V) beside PS1, reverse-polarity Schottkys,
   and a switch; 4S Li-ion is the target (5S exceeds the OPA2192's ±18 V).
4. **Firmware** for e-stim mode per spec §7: bit-banged I²C on PA17/PA22, RELEASE on PA15, latched TIMA0 fault.

**Why:** the M4 design is final on paper; the layout and the firmware are what remains before ordering.
**How to apply:** the HAT is hand-routed — never `tools/build_hat_pcb.sh`; check `.lck` files before writing boards.

Related: [[estim-module-status]], [[laserhat-user-preferences]].
