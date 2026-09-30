---
name: kicad-python-footprint-loader
description: "KiCad 9.0.8 macOS bundled Python: FootprintLoad returns untyped SWIG objects once a board is loaded; load footprints first"
metadata:
  type: project
---

In KiCad 9.0.8's bundled Python on macOS, `pcbnew.FootprintLoad()` raises (`SwigPyObject has no attribute FootprintLoad`) and
`PCB_IO_KICAD_SEXPR().FootprintLoad()` returns a typed `FOOTPRINT` **only before** the first `pcbnew.LoadBoard()` call in the
process; afterwards every load (and even a second `LoadBoard`) comes back as an untyped SwigPyObject and `Cast_to_FOOTPRINT`
does not help. Working recipe: load every footprint you need first (`pcbnew.FOOTPRINT(raw)` for extra copies), then `LoadBoard`,
then `board.Add(fp)`. The other session's `tools/pcb_sync.py` (not in this checkout) reportedly does the same.

**How to apply:** structure pcbnew scripts as load-footprints → LoadBoard → edit → ZONE_FILLER → Save. kicad-cli render/drc are fine.

Related: [[pcb-workspace-setup]], [[estim-module-status]].

**Footprint ↔ symbol link (verified 2026-09-29 from a real F8 save):** for symbols on the root sheet KiCad 9 writes the
footprint path as `/<symbol uuid>` only (no root-sheet uuid; the HAT board's `/<sheet>/<symbol>` paths are sub-sheets), plus
`(sheetname "/")` and `(sheetfile "X.kicad_sch")`. F8 also needs the full `Lib:Name` FPID and the schematic's net names
(local labels are `/NAME`), or it replaces / renames everything. `kicad-cli pcb drc --schematic-parity` does not check paths.

Multi-unit symbols: KiCad picked unit 3 for U5 (OPA2192, power unit) and unit 1 for U8, so do not assume unit 1; after a
regeneration, take the paths from an F8-saved copy or match by reference once.
