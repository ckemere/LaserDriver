# LaserHAT Schematic Design Rules

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

## Rule 3 — Preserve hand-edited schematics

**Never regenerate a sheet from scratch if a hand-edited original exists.**

- Load the hand-edited original with `Schematic.from_file(ORIGINAL_PATH)`.
- Apply only the minimal required changes (signal renames, power renames, additions).
- Preserve: all symbol positions, rotations, connected nets, property locations.
- `PCB/laser_driver.kicad_sch` is the authoritative original for the laser driver circuit.
  Load it in `build_laser_driver()` rather than placing symbols by coordinate.

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
