---
name: fab-bom-scheme
description: How parts are classified for JLC assembly (2026-09-30) - LCSC numbers live in tools/lcsc_parts.py and are stamped into the "LCSC Part #" field; DNP means not populated; hand-fit means no number + exclude-from-position-files
metadata:
  type: project
---

The user orders through KiCad's **Fabrication Toolkit**, which reads the footprint field `LCSC Part #`
(fallbacks `LCSC Part`, `JLCPCB Part #`, `LCSC`). Until 2026-09-30 the HAT and laser sheets carried four
misspelt variants with Rev 1 codes (every 0402 resistor = 47k, wrong ICs), so the toolkit's BOM was garbage.

- `tools/lcsc_parts.py` is the only source of codes (each verified against LCSC/JLC with
  `EStimDaughter/tools/lcsc_check.py` / `jlc_search.py`: MPN, package, value). `tools/stamp_lcsc.py` writes them
  into every symbol (text patch) and footprint (pcbnew); `make_laser_daughter.py` stamps its output; `jlc_fab.py`
  warns on drift.
- **DNP (symbol attribute) = not populated** (`lcsc_parts.NOT_FITTED`, e.g. HAT R1/R2 ID pull-ups).
- **Hand-fitted = `lcsc_parts.HAND_FIT`**: no part-number field + footprint "exclude from position files"
  (board-only flag). They stay in the BOM with an empty number so JLC shows "do not place". Pi header J1, BNCs,
  module sockets/headers, laser-diode socket J2, BACK button.
- The e-stim board keeps its own list (`EStimDaughter/bom_EStimDaughter.csv`, generator field `LCSC`); stamp_lcsc only
  sets its hand-fit flags.
- JLC basic parts matter to the user (each extended part adds a loading fee): LEDs are KT-0603 red/white (basic),
  R13 went 3k -> 2k for that reason.

- `lcsc_parts.NON_PARTS` (jumpers, holes, logo, test pads) → symbol exclude-from-BOM + footprint exclude-from-BOM/-pos.
- To see exactly what the user's Fabrication Toolkit produces: `git clone --depth 1
  https://github.com/bennymeg/Fabrication-Toolkit`, then in the kicad venv
  `from plugins.process import ProcessManager; pm = ProcessManager(pcbnew.LoadBoard(p)); pm.generate_tables(dir, False, True)`
  and read `pm.bom` / `pm.components` (it reads footprint *fields*, DNP via IsDNP, exclude flags via FP attributes).

**Why:** the user said "values need to match for things like resistors!!!" after a bad BOM; keep one source of truth.
**How to apply:** after editing lcsc_parts.py run `python tools/stamp_lcsc.py` then `tools/jlc_fab.py`; never hand-edit
the fields. Related: [[hat-manual-routing-handoff]], [[laserhat-user-preferences]].
