# BatteryPack — 4S 18650 pack board for the e-stim module (rev B)

Rev B, 2026-10-26.  One board holds four 18650 cells in series (12.0–16.8 V) with an on-board USB-C PD charger and
per-cell balancers; two identical boards stacked give the ±V supply the e-stim module wants (+V / 0 V / −V on a 4-pin
JST-PH).  Replaces the hand-wired battery cases.  100 × 96 mm, 2-layer, JLC assembled (clips and toggle through-hole).

Files: `gen_schematic.py` + `sch_parts.py` + `sch_symbols.py` (+ `sch_engine.py`) generate `BatteryPack.kicad_sch`
(deterministic UUIDs, like the e-stim module); `tools/netcheck.py` proves the drawing matches `sch_parts.py`;
`tools/make_bom.py` writes `bom_BatteryPack.csv`; `tools/make_footprints.py` writes `battpack.pretty/` (clip, toggle).
Board: `tools/board_init.py` (once: rules, netclasses, footprints from the netlist via `tools/pcb_sync.py`) and
`tools/place.py` (outline, holes, placement, silk) built it; Freerouting (`~/Tools/freerouting-2.4.1.jar`, headless with
`--gui.enabled=false`, DSN/SES through `pcbnew.ExportSpecctraDSN` / `ImportSpecctraSES`) routed it; from here on the
board is edited in place, never rebuilt.  `tools/make_fab.py` writes `../fab/BatteryPack/` (gerbers, JLC BOM + CPL).

## What is on it

| Block | Parts | Notes |
|---|---|---|
| Cells | BC1–BC8 MYOUNG MY-18650-01 clips (C2979183, extended) | four rows at 20 mm pitch, clips 48.0 mm apart (pin rows); cells alternate direction so the series links are short: row 1 + left, row 2 + right, row 3 + left, row 4 + right (silk "+"/"−" at each clip) |
| Balancers | U6–U9 HY2213-BB3A (C113632, ext), Q7–Q10 AO3400A, R35–R38 100 R 1206, R31–R34 100 R, C12–C15 100 n | one per cell in the band under the cells: 42 mA bleed above 4.200 V, release 4.19 V, 2.5 µA standing |
| Toggle | SW1 MTS-203 DPDT centre-off (C55160018, ext), F1 100 mA PTC (C12430, ext) | **RUN / OFF / CHARGE**.  Pole 1 (+BAT): RUN → +RUN → F1 → +SW → Q1 → +OUT; CHARGE → +CHG.  Pole 2 (GND): RUN → J3.2 (output ground); CHARGE → CGND (USB-C ground + charger return).  OFF opens both |
| Cutoff | U2B (LM393), Q1 AO3401A, R1/R2 100k, R11 1M | +OUT off below 12.0 V (3.0 V/cell), back on above 12.8 V |
| Gauge | U3 CJ431, R3–R11, U1/U2 LM393, D2–D4 + R13–R15 from the gauge rail +G (= +SW or +CHG via D5/D6 SS14) | D4 green ≥ 16.0 V, D3 green ≥ 15.2 V, D2 yellow ≥ 14.4 V, ~1 mA each; works in RUN and in CHARGE |
| ON | D1 red + R12 from +OUT | lit whenever the output is live |
| Charger | J1 USB-C (C165948, ext), U4 CH224A (C42459160, ext) + C3 + R24 120k, U5 CN3704 (C51659, ext), Q6 AO3401A, D7/D8 SS34, L1 22 µH (C408453, ext), R25+R26 0.2 R, C4–C11, R27, RT1 NTC (C13564, ext), D9 CHRG red, D10 DONE green | PD brick negotiated to 20 V; 1 A CC, 16.8 V ±1 % CV, termination 92 mA, trickle 150 mA below 11.2 V, re-charge below 16.0 V, 18.1 V over-voltage cut, NTC stops it hot / cold.  Everything referenced to CGND, which meets GND only in CHARGE (R30 1M otherwise) |
| Slave enable | Q2 AO3401A, Q3/Q5 AO3400A, Q4 AO3401A, R16–R23 | the upper board's +RUN arrives on J3.4 and switches this board's +RUN on through Q4 (0.3 mA), blocked in CHARGE by Q5 |
| Output | J3 B4B-PH-K-S (+OUT, OUT_GND, LINK_N, STACK_IN), J4 same (GND, LINK_N, NC, +RUN) | 4-wire straight cable J3 → J4 between boards; upper J3 to the module |
| Mounting | H1–H4 M3 at (8, 4), (96, 4), (8, 92), (96, 92) | 25 mm standoffs clear the clips + cells and the toggle lever (≈19 mm) |

Standing draw in RUN: 5–8 mA (reference, comparators, LEDs); in CHARGE with no brick: the same from the pack (the
gauge stays on); in OFF: about 40 µA (charger and balancers).  A lower board left in OFF draws only that until the
upper toggle enables it.

## Stacking and switching (two boards = ±V)

- Lower J3 → upper J4 (4-wire JST-PH cable): lower +OUT → upper GND (= 0 V); lower OUT_GND → LINK_N → upper J3.3
  (= −V); upper +RUN → lower STACK_IN.  Upper J3 = +V / 0 V / −V / +RUN to the e-stim module (pin 4 unused there).
- **Upper toggle = the stack switch.**  Lower toggle stays in OFF (its output follows the upper one) and goes to
  CHARGE only to charge.  RUN on the lower board is for a board used on its own.
- Charging: put the board(s) to charge in CHARGE, plug a PD brick (20 V, ≥ 30 W) into each.  A board in CHARGE has
  both output lines open, so no combination of bricks (shared negatives included) can loop a pack; the stack cable can
  stay in.  Plugging a brick into a board in RUN does nothing (its USB ground floats; DONE may light).
- Fully charged packs give ±16.8 V: within the ADG1436's 35 V rail-to-rail maximum (33.6 V).

## Thresholds and values

Gauge rail +G = +BAT − 0.25 V (SS14 at ~5 mA).  VS = +G × 0.1357 with +OUT live (R9 68k ∥ R11 1M against R10 10k),
× 0.1271 cut off.  Ladder from 2.495 V: R4 6.8k, R5 2k, R6 2k, R7 6.2k, R8 30k → TH80 2.137 V, TH50 2.029 V,
TH20 1.920 V, THCUT 1.595 V → 16.0 / 15.2 / 14.4 V (pack) and 12.0 V (cutoff) / 12.8 V (re-enable); worst error 29 mV.
Charger: Ich = 200 mV / 0.2 R = 1 A; Ieoc = 9.17 % (EOC grounded); CH224A CFG1 120k = 20 V request.

## Board

100 × 96 mm.  Netclasses: Power 0.8 mm (+BAT, GND, C1–C3, +RUN, +SW, +OUT, OUT_GND, LINK_N, +CHG), Charger 0.4 mm
(SW, SWA, CSP, RCS, VBUS, CGND), Fine 0.25 / 0.15 mm (USB-C CC1/CC2/D+/D−), Default 0.3 / 0.2 mm.  Board minimums
0.15 / 0.15 (JLC: 0.127).  No copper pours.  DRC 0 violations, 0 unconnected; `path_check` / `sync_check` 0.
Reference designators are hidden on the silk; the silk carries the cell polarity, RUN/CHG, LED functions, OUT / LINK IN
and the USB-C label.

## Assembly notes and first-article checks

- **Toggle lever direction:** the silk assumes the usual toggle convention (lever away from the closed contacts):
  lever toward "RUN" closes pins 1/4 (RUN), toward "CHG" closes 3/6.  Verify with a meter on the first board; if the
  switch is the other way round, swap the two silk words in `tools/make_footprints.py` and on the board.
- **JLC rotation:** JLC's CPL rotation convention differs from KiCad's for some packages; check SOT-23, SOIC, TSSOP,
  the LEDs (cathode = pad 1, KENTO parts as on the HAT) and the electrolytic in JLC's DFM preview before ordering.
- **USB-C:** front flush with the board edge (footprint origin 4.2 mm inside).  CH224A requests 20 V; a 5 V-only
  source leaves the CN3704 below its lock-out, nothing charges.
- **First charge:** meter on every clip (cell voltages) and on CSP−BAT (200 mV = 1 A) during the first charge; confirm
  DONE at ~90 mA and the balancer resistors warming on the fullest cell.  The NTC RT1 sits beside cell 3; a 10k
  fixed resistor in its place disables temperature control.
- **Clips:** arms grip the cell body (16 ± 1 mm sprung opening for an 18.3–18.6 mm cell); fallback MYOUNG
  MY-18650-04-J / -05-J SMT end contacts if a batch is too tight.
- Extended parts (feeder fee each): clips, toggle, PTC, USB-C, CH224A, CN3704, inductor, electrolytic, HY2213, NTC,
  PH-4 header.  Everything else is basic.

## Checks before fab

`python gen_schematic.py` → `python tools/netcheck.py` (CONNECTIVITY OK) → ERC (0) → `tools/pcb_sync.py` only if
nets or footprints changed (`--keep-tracks`) → `../tools/path_check.py` / `sync_check.py` → `kicad-cli pcb drc` →
`python tools/lcsc_check.py` → `python tools/make_fab.py`.
