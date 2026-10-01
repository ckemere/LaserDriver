---
name: hat-manual-routing-handoff
description: "LaserHAT Rev 2 HAT board status — hand-routed by the user on pcb-rev2; generators and builders were deleted 2026-10-01, so scripts only check/sync/tidy"
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
- Random symbol UUIDs once made KiCad's F8 replace footprints (the laser module had 11 such footprints). Relink with
  `pcb_sync.py --keep-tracks` and verify with `tools/path_check.py` / `sync_check.py` —
  path = "/<symbol uuid>" on the root sheet, "/<sheet uuid>/<symbol uuid>" on sub-sheets, any unit of a multi-unit part.

**How to apply:**
- Never rebuild a board from scratch (the builders are gone; the boards are the user's layouts).
- Check for `~LaserDriver*.lck` before writing the board or regenerating schematics.
- Change nets by patching the `.kicad_sch` text, then either the user presses F8 or run `pcb_sync.py --keep-tracks`.
- Refill zones before DRC, and run DRC next to `LaserDriver.kicad_pro`.
- Before a scripted board edit make sure the current board is committed (the old `stash/` backups were deleted 2026-10-01; git is the backup).

2026-09-30: the e-stim board outline (x 101–127.5, y 76–109, its actual M4c Edge.Cuts) is drawn on User.Drawings beside the laser module's; scripted edits of the HAT board are fine when the user asks for them (J8 re-route done the same day).

Open, optional:
- The BNC courtyard margin (0.54 → 0.25 mm in `make_bnc_fp.py`).
- 6 via jags crowded by neighbours.
- Angled pad entries at R7.2, U6.1, U6.4 and R24.1.

Related: [[laserhat-rev2-goals]], [[pcb-workspace-setup]], [[laserhat-user-preferences]], [[laserhat-next-tasks]].

2026-10-01: the laser module sheet is hand-edited too (AO9926B dual FET as Q1, D2/D4 swapped); all generators were deleted the same day — patch the `.kicad_sch` text and sync the board with `pcb_sync.py --keep-tracks` / `sync_check.py`. The user's own Claude session on the laptop also edits CLAUDE.md, lcsc_parts.py and lcsc_catalog.json: pull before touching them.
