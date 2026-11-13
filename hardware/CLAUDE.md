# Glance out HAT hardware — working rules

Four KiCad 9 projects.  Each schematic is generated from Python (`gen_schematic.py` + `sch_parts.py` +
`sch_symbols.py` + `sch_engine.py`, deterministic UUIDs); the boards were placed by script and then **finished by hand
by the user** (the production state of 2026-11-01 is hand-edited).  Scripts check, tidy and sync; they do not rebuild.

| Project | What | Generator / board scripts | Fab |
|---|---|---|---|
| `StimHAT/` | HAT core (MSPM0G1507, CH340N, USB-C path, HAT EEPROM, BNCs, joystick) + isolated constant-current stimulator, 4-layer | `gen_schematic.py`; `tools/` (`make_footprints.py`, `place.py`, `stamp_fields.py`, `make_bom.py`, `make_fab.py`, `drc_summary.py`, `netcheck.py`) | `fab/StimHAT`, `fab/orders/2026-11-01_StimHAT_rev3_production.zip` |
| `LaserDriverHAT/` | the same HAT core + the laser-diode driver (the former LaserDaughter module) | same layout as StimHAT | `fab/LaserDriverHAT`, `fab/orders/2026-11-01_LaserDriverHAT_rev3_production.zip` |
| `DCDCPod/` | isolated ±15 V supply pod that plugs into the StimHAT's J102/J103 | same; plus `tools/check_isolation.py` | `fab/DCDCPod`, `fab/orders/2026-11-01_DCDCPod_rev3_production.zip` |
| `SimpleBatteryPack/` | two 4S hobby packs in series → ±V for the stimulator, ON/OFF, no charger | same; Fabrication Toolkit output in `production/` | `SimpleBatteryPack/production/` |

Shared: `Footprints.pretty` / `Footprints.3dshapes` (owl logo, Pi header socket, PFET, slide switch, BNC; each
project's `fp-lib-table` points at `${KIPRJMOD}/../Footprints.pretty`), `LaserHAT.kicad_sym` (only read by the four
`sch_symbols.py` for the owl symbol art), `tools/` (board-agnostic helpers, below), `ref/LaserHAT_Rev2_ref.kicad_pcb`
(the archived Rev 2 HAT's footprints and outline, read by `StimHAT|LaserDriverHAT/tools/make_footprints.py`,
`StimHAT/tools/board_init.py` and `SimpleBatteryPack/tools/place.py`), `estim_interface/ESTIM_MODULE_SPEC.md` (the
stimulator contract, §7 = firmware/pins).  Session context: `../docs/memory/`; Rev 2 history and the Rev 2 MCU pin map:
`../docs/history/REV2_NOTES.md`.  The Rev 2 HAT, LaserDaughter, EStimDaughter and the relay BatteryPack are archived
at tag `archive/pre-glance-cleanup` (under `LaserHAT/`).

## Editing

- **Never re-run a board's `place.py`, `board_init.py`, `autoroute.py` or `gen_schematic.py` on the production files**;
  each README says which scripts are still safe on the hand layout.  Run a generator only in a scratch copy and diff.
- Never round-trip a `.kicad_sch` through kiutils 1.4.8 (it un-hides every `(hide yes)` field); patch the text
  (`tools/sexpr_patch.parse` for spans).
- **Never rebuild a board from scratch.**  Net or footprint changes: edit the schematic, then the user presses F8 in
  pcbnew, or `tools/pcb_sync.py board netlist --keep-tracks` (keeps placement and copper).  Check for KiCad lock files
  (`~*.lck`) before writing any board or schematic.
- PCB scripts run in the `kicad` venv / KiCad's bundled Python (`pcbnew`).  Collect, then `board.Remove()` at the end;
  compare items by `m_Uuid`; copy `VECTOR2I`s before editing; `pcbnew.FootprintLoad()` breaks after `LoadBoard()` — use
  `PCB_IO_KICAD_SEXPR().FootprintLoad`.
- Clean-up helpers (transactional, clearance-checked): `tools/track_tidy.py`, `tools/gnd_islands.py`,
  `tools/fill_zones.py` (refill before DRC), `tools/overlaps.py`; `tools/maze_io.py` + `tools/maze_route.py` for a single
  missing connection; `tools/netcheck.py board` for per-net copper connectivity; `tools/make_bnc_fp.py` builds the
  shared BNC footprint.
- DRC must run on a board next to its `.kicad_pro` (`python3 tools/drc_summary.py` in StimHAT / LaserDriverHAT / DCDCPod).

## Schematic ↔ board links (F8 safety)

KiCad pairs a footprint with its symbol by `(path "/<symbol uuid>")` (sub-sheets:
`/<sheet uuid>/<symbol uuid>`).  A mismatch makes F8 delete the footprint and add a fresh one,
losing the hand placement.  After **any** scripted edit:
`tools/path_check.py board sch` → 0 mismatches, and `tools/sync_check.py board sch` (read-only F8:
parts, footprint ids, values, DNP, pad nets, paths) → 0 differences.

## Part numbers and fab outputs

- Each project's `sch_parts.py` is the source of its LCSC codes; `tools/stamp_fields.py` writes them into the
  `LCSC Part #` fields, `tools/lcsc_check.py` / `tools/jlc_search.py` check them, `tools/make_bom.py` writes
  `bom_<Board>.csv`, `tools/make_fab.py` writes `fab/<Board>/` (gerbers zip, JLC BOM / CPL with the rotations in
  `tools/ref/jlc_rotations.csv`, renders).  The archives actually ordered are in `fab/orders/`.
- `tools/lcsc_parts.py` / `tools/lcsc_catalog.json` are reference data from the Rev 2 boards (the LASER table is where
  the LaserDriverHAT's laser-driver codes came from); the scripts that used them are archived.
- The Fabrication Toolkit's exact BOM/CPL can be reproduced with its `plugins.process.ProcessManager`
  (`../docs/memory/fab-bom-scheme.md`).

## Schematic conventions (for any new symbols or wires)

- Passives show only Reference and Value (pin names/numbers hidden).
- Every connected pin gets a 5.08 mm wire stub before its label; `GlobalLabel` for signals that
  cross sheets, `LocalLabel` within a sheet; symbols ≥ 5 mm apart; decoupling caps spread, not stacked.
- Never give a symbol that has a footprint a new UUID.
- `.kicad_pcb` files take no comments and no `(pintype ...)` in pads.

## Net names

Each project's `sch_parts.py` is the list (pin → net per part); the MCU pin maps are in the StimHAT and
LaserDriverHAT READMEs ("MCU pin map").
