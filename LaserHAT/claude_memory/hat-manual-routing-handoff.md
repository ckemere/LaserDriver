---
name: hat-manual-routing-handoff
description: "LaserHAT Rev 2 HAT board status (2026-09-28) — hand-routed by the user, cleaned up, committed on pcb-rev2; never regenerate it with build_hat_pcb.sh"
metadata:
  node_type: memory
  type: project
  originSessionId: 1e5b4086-f717-4b1c-9f99-2a4cfed7a528
  modified: 2026-09-28T21:43:44.955Z
---

State as of 2026-09-28. The HAT PCB (`LaserHAT/LaserDriver.kicad_pcb`) is **placed and routed by hand by the user** and committed on branch `pcb-rev2`.

**Status:**
- DRC is clean apart from known items: silk-at-edge on the SW7/BNC outlines, the BNC courtyard overlap (0.28 mm, cosmetic), the Samtec J1 library-mismatch note, and 4 single-spoke GND thermals.
- 0 unconnected, 0 parity issues. 56 signal vias.
- Silkscreen decluttered: references hidden except JP1/JP4/JP5; user labels at 1.0–1.5 mm.
- Fab outputs regenerated in `fab/LaserHAT`.

The pin map, header-pin swaps and button polarity live in `LaserHAT/CLAUDE.md` (Rev 2 section) and `REV2_NOTES.md`.

**Why:** hard-won layout. Two earlier near-misses:
- Rebuilding would wipe the hand layout.
- Random symbol UUIDs made KiCad's F8 replace footprints. Fixed: `schlib.add_symbol` now uses uuid5.

**How to apply:**
- Never run `tools/build_hat_pcb.sh` on the HAT.
- Check for `~LaserDriver*.lck` before writing the board or regenerating schematics.
- Change nets with `rev2_migrate.py`, then either the user presses F8 or run `pcb_sync.py --keep-tracks`.
- Refill zones before DRC, and run DRC next to `LaserDriver.kicad_pro`.
- Take a `stash/` backup before any scripted board edit.

Still to do on the HAT (2026-09-29): extend the `DAUGHTERBOARD` keep-out and the Dwgs.User module-outline marker to y 112.5 (the e-stim module now overhangs the south edge).

Open, optional:
- The BNC courtyard margin (0.54 → 0.25 mm in `make_bnc_fp.py`).
- 6 via jags crowded by neighbours.
- Angled pad entries at R7.2, U6.1, U6.4 and R24.1.

Related: [[laserhat-rev2-goals]], [[pcb-workspace-setup]], [[laserhat-user-preferences]], [[laserhat-next-tasks]].
