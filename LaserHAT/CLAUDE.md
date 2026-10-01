# LaserHAT Schematic Design Rules

## Rev 2 workflow (supersedes the generator below)

The schematics were hand-edited in KiCad after Rev 1, so `generate_schematics.py`,
`fix_labels.py` and `merge_template.py` are stale — do not run them.  Rev 2 is produced by
re-runnable scripts in `tools/` that start from the Rev 1 files in git (`a722d88`) and apply
minimal edits (see `REV2_NOTES.md`):

- `tools/rev2_migrate.py`, `tools/make_laser_daughter.py` — schematic edits.  They write back
  with `tools/sexpr_patch.py`, which splices only changed items into the original text:
  kiutils 1.4.8 cannot round-trip KiCad 9's `(hide yes)` and would un-hide every field.
  Symbols they add get **stable UUIDs** (`schlib.add_symbol`: uuid5 of sheet/ref/unit), so
  re-running them never makes KiCad's "Update PCB from Schematic" replace footprints.
- Use KiCad's bundled Python (`pcbnew`) for PCB scripts:
  `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`;
  kicad-cli is `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` (not on PATH).
  In that Python, defer every `board.Remove()` to the end, compare items by `m_Uuid` (not `is`),
  and copy `VECTOR2I`s before editing (`GetStart()` returns a live reference).
- Use the `kicad` micromamba env for everything else.
- **2026-09-30: the HAT schematics were hand-edited and re-saved in KiCad (commit 9a940e9), so
  `rev2_migrate.py` is stale as well — do not re-run it; patch the `.kicad_sch` text directly.**
  **2026-10-01: the laser module sheet has been hand-edited in KiCad too, so `make_laser_daughter.py` is
  stale (its output drops the hand edits and re-adds TP1) — do not re-run it;** patch the `.kicad_sch` text
  (e.g. `sexpr_patch.patch` for properties) and sync the board with `pcb_sync.py --keep-tracks`.  After any schematic
  or board scripting, `tools/path_check.py board.kicad_pcb root.kicad_sch` must report 0 mismatches,
  otherwise KiCad's F8 replaces footprints and the hand placement is lost.
- **Part numbers:** `tools/lcsc_parts.py` is the only source of LCSC codes (verified against LCSC/JLC on
  2026-09-30).  `tools/stamp_lcsc.py` writes them into the `LCSC Part #` field of every symbol and footprint
  (the field the Fabrication Toolkit reads) and removes the misspelt Rev 1 variants; run it after editing
  the table.  Two flags, two meanings: `lcsc_parts.NOT_FITTED` → symbol **DNP** (not populated);
  `lcsc_parts.HAND_FIT` → no part number, excluded from BOM **and** position files (JLC rejects any BOM
  designator missing from the CPL, so "in the BOM but not placed" is not possible); DNP parts are excluded
  from the BOM as well; `lcsc_parts.NON_PARTS` (jumpers, holes, logo, test
  pads) → excluded from BOM and position files.  `stamp_lcsc.py` applies all three and also writes each
  part's Description/Datasheet from `tools/lcsc_catalog.json` (the Rev 1 sheets carried descriptions of
  parts long replaced — "200Ω" on a 2 k resistor).  **Before any fab export run, in this order:**
  `tools/lcsc_verify.py` (every Value vs LCSC's parameter table, all three boards; `--refresh` re-fetches),
  `tools/sync_check.py board sch` (netlist vs board: parts, footprints, values, DNP, pad nets, paths) and
  `tools/path_check.py`; all must report 0.  The Fabrication Toolkit's own BOM/CPL can be reproduced
  headlessly with its `plugins.process.ProcessManager` (see `claude_memory/fab-bom-scheme.md`).

### The HAT PCB is hand-placed and hand-routed (2026-09-28)

- **Never run `tools/build_hat_pcb.sh` on `LaserDriver.kicad_pcb`** — it rebuilds from Rev 1 and
  overwrites the hand layout.  (The laser/e-stim daughterboards still use their build scripts.)
- Check for KiCad lock files (`~LaserDriver.kicad_pcb.lck`, `~LaserDriver.kicad_sch.lck`) before
  writing the board **or regenerating schematics**; eeschema/pcbnew keep in-memory copies.
- Net changes: re-run `rev2_migrate.py`, then either the user presses F8 in pcbnew, or
  `tools/pcb_sync.py board net --keep-tracks` (keeps placement and copper).
- Clean-up helpers (all transactional, clearance-checked): `tools/track_tidy.py` (header
  midlines, via/pad jags, tiny segments), `tools/silk_declutter.py`, `tools/gnd_islands.py`
  (read-only check), `tools/fill_zones.py` (refill before DRC).  DRC must run on a board next to
  `LaserDriver.kicad_pro` (project rules: clearance 0.15, hole clearance 0.25).
- Fab outputs: `tools/jlc_fab.py LaserHAT` (LCSC numbers in `tools/lcsc_parts.py`).
- Backups of each stage are in `stash/`.

### Rev 2 MCU pin map (U7 MSPM0G3507 RHB, rot −90; authoritative copy: `rev2_migrate.py` PIN_MAP)

| Pin | Port | Net | Function |
|---|---|---|---|
| 1, 2 | PA0, PA1 | I2C_SDA, I2C_SCL | I2C0 → Pi GPIO2/3 (OLED bonnet). Only fail-safe OD pins: keep here |
| 3 | NRST | GPIO23 net | reset ← Pi GPIO23 (J1.16), R3 47k / C3 10n, JP4 RTS_NRST |
| 6 / 32 | PA2 / VCORE | ROSC / VCORE | R4 100k 0.1 % / C4 |
| 7, 8, 9 | PA3–PA5 | — | spare |
| 10 | PA6 | DB_GPIO | J8.3 FAULT_n → **TIMA0_FAULT0** (hardware PWM kill); J8 pins 3/5 swapped 2026-09-29 |
| 11 | PA7 | DB_PWM_A | J8.5 EN, **TIMA0_CCP1** |
| 12, 13 | PA8, PA9 | PI_RXD, PI_TXD | **UART1** TX/RX ↔ Pi GPIO15/14 |
| 14, 15 | PA10, PA11 | MCU_UART_TX/RX | UART0 ↔ CH340N (BSL) — fixed |
| 16 | PA12 | DB_PWM_B | J8.4 CATH, **TIMA0_CCP3** (independent channel, not a complement) |
| 17 / 18 / 20 | PA13 / PA14 / PA16 | BUTTON4 / 2 / 3 | SW7 wheel roll / push / roll |
| 19 | PA15 | DB_DAC | J9.3 DAC0 (e-stim CS_n) — fixed |
| 21 | PA17 | DB_ADC_A | J9.4 ADC1.2 (e-stim bit-banged I²C SDA; PA17 only muxes I2C1_SCL, so hardware I2C1 needs a pin move — see REV2_NOTES) |
| 22 | PA18 | BSL_INVOKE | SW6 (active **high**) — fixed |
| 23, 24 | PA19, PA20 | SWDIO, SWCLK | ← Pi GPIO25 / GPIO24 (swapped vs Rev 1) — fixed MCU side |
| 25 | PA21 | BUTTON1 | SW8 BACK |
| 26 | PA22 | DB_ADC_B | J9.5 ADC1.8 (e-stim bit-banged I²C SCL; no I2C function on PA22) |
| 27 | PA23 | BUTTON5 | SW9 FIRE |
| 28 | PA24 | LED_MCU | D7 |
| 29 / 30 / 31 | PA25 / PA26 / PA27 | MCU_STIM_OUT / MCU_STIM_IN / PI_TRIGGER | U8 → J7 (TIMG12) / J6 → U8 (TIMG8 capture) / ← Pi GPIO26 (TIMG7) |

- Buttons SW7/SW8/SW9 are **active low** (commons on GND, internal pull-ups); SW6 stays active high.
- PWM_A/B and FAULT must stay on one TIMA timer (shared timebase + hardware fault kill).
- Pi header vs Rev 1: SWD swapped (GPIO24 = SWCLK, GPIO25 = SWDIO); NRST ↔ MCU_POWER_EN swapped
  (GPIO23 = NRST, GPIO18 = MCU_POWER_EN); trigger is GPIO26 → PA27.  Flash Rev 2 with
  `make flash HAT_REV=2` (Firmware/Makefile.gcc; `Pi/power_cycle.py` reads LASERHAT_*_PIN).
- OLED bonnet (Adafruit 4567) runs only on 3.3 V and ties header pins 1/17 together itself.
- J8/J9 pad positions are frozen (module contract: `estim_interface/ESTIM_MODULE_SPEC.md`, §7 = what was agreed
  with the e-stim module, §8 = how the HAT and module sessions coordinate). The old `QUESTIONS.md` log is gone.

The rules below (passives, stubs, UUID preservation, spacing) still apply to new edits.

---

This file governs how `generate_schematics.py` produces KiCad schematics.  
Follow these rules exactly when modifying or extending the generator.

---

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r ../requirements.txt   # kiutils==1.4.8
```

Run the generator:

```bash
.venv/bin/python3 LaserHAT/generate_schematics.py
```

All output schematics are written into `LaserHAT/`. Open `LaserHAT/LaserDriver.kicad_pro` in KiCad to review.

---

## Rule 1 — Passive parts: show only Reference and Value

For resistors, capacitors, and inductors (lib entries `R`, `C`, `L` and their variants):

- Hide pin names: `ls.pinNamesHide = True`  
- Hide pin numbers: `ls.hidePinNumbers = True`  
- Also set `pin.nameEffects.hide = True` and `pin.numberEffects.hide = True` on every pin

Do **not** add extra properties or pin annotations to passive symbols.

---

## Rule 2 — Every connected pin gets a ≥5 mm wire stub before its net label

Wire stub length: **5.08 mm** (200 mil grid).

Formula:
```
wire_end = (px - 5.08·cos(pin_angle),  py - 5.08·sin(pin_angle))
label_angle = (pin_angle + 180) % 360
```

- `px, py` is the pin connection point (the tip of the pin in schematic space).
- The wire goes from `(px, py)` to `wire_end`.
- The label sits at `wire_end` with `label_angle` so its tail points toward the component.

Use `GlobalLabel` (not `LocalLabel`) for signals that cross sheets. Use `LocalLabel` only for
signals confined to a single sheet.

---

## Rule 3 — Preserve hand-edited schematics; never break UUID links

**Never regenerate a sheet from scratch if a hand-edited original exists.**

- Load the hand-edited original with `Schematic.from_file(ORIGINAL_PATH)`.
- Apply only the minimal required changes (signal renames, power renames, additions).
- Preserve: all symbol positions, rotations, connected nets, property locations.
- `PCB/laser_driver.kicad_sch` is the authoritative original for the laser driver circuit.
  Load it in `build_laser_driver()` rather than placing symbols by coordinate.
- `PCB/laserhat_root_orig.kicad_sch` is the authoritative original for the root schematic's
  40-pin GPIO header. `build_root()` loads `j1_sym` from it so the UUID
  `212bfd25-0010-0000-0000-000000000001` is never changed — that UUID is what the PCB
  footprint's `(path ...)` field references. Regenerating it with a fresh UUID silently
  breaks schematic↔PCB synchronisation.

**UUID invariant**: KiCad matches schematic symbols to PCB footprints via the symbol
instance UUID embedded in the footprint as `(path "/<uuid>")`.  If a generator creates
a new random UUID for a symbol that already has a footprint, that footprint becomes
orphaned. Always preserve UUIDs for any symbol that has a matching PCB footprint.

When copying lib symbols from an existing schematic, always call `_fix_lib_sym_angles(ls)`
to set `pin.position.angle = 0` on any pin where `angle is None` (eeschema rejects the
two-number `(at X Y)` form — it requires `(at X Y angle)`).

---

## Rule 4 — Generous spacing; use multiple sheets

- Separate functional blocks into separate hierarchical sheets.
- Minimum component spacing: **5 mm** (200 mil) between symbol bodies.
- Decoupling caps: offset from their IC, spread vertically, not stacked.
- Sheet hierarchy boxes in the root schematic: spread across the full A3 canvas
  (e.g., x = 20, 100, 190 for three sheets at y ≈ 80).

---

## KiCad PCB file rules

- **No comments** — KiCad's S-expression parser rejects any comment syntax (`;`, `#`, `//`). Never add comments to `.kicad_pcb` files.
- **No `(pintype ...)`** in pad entries — that token is schematic-only; pcbnew will reject it.
- The PCB template (`LaserDriver.kicad_pcb`) contains only the board outline (Edge.Cuts), four M2.5 mounting holes, and the 40-pin GPIO header. All component footprints are added via "Update PCB from Schematic" in KiCad.

## KiCad S-expression conventions (kiutils)

- Always use kiutils `to_file()` — never hand-write S-expressions. kiutils handles
  UUID formatting (unquoted), field ordering, and syntax correctly.
- `PageSettings(paperSize="A3")` — use a `PageSettings` object, not a plain string.
- `HierarchicalSheetProjectInstance(name='', paths=[])` — the correct constructor;
  set `sh.instances = []` and let KiCad populate on first save.
- Lib symbols sourced by round-tripping existing schematics through kiutils into `/tmp/`.

---

## Signal naming conventions

| Net name       | Meaning                                  |
|----------------|------------------------------------------|
| `+LASER_V`     | Boost-derived laser supply (≈12 V)       |
| `+3V3`         | 3.3 V MCU rail                           |
| `VREF`         | DAC reference / analog setpoint          |
| `PWM_LASER`    | Main PWM to laser driver                 |
| `PWM_DUMMY`    | Complementary PWM (dummy load)           |
| `TRIGGER`      | External BNC trigger input               |
| `UART_TX/RX`   | MCU ↔ USB-UART bridge                   |
| `SWCLK/SWDIO`  | SWD debug port                           |
| `I2C_SCL/SDA`  | I²C bus (EEPROM)                        |
