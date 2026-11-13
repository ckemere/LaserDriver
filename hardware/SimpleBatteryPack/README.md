# SimpleBatteryPack — ±V battery board for the e-stim module, without the charger

Rev A, 2026-10-31.  The BatteryPack (`../BatteryPack`, rev E) with the charging infrastructure cut out.  One 100 × 100 mm
board carries two off-the-shelf 4S hobby packs (LiPo or Li-ion with an XT60 discharge plug, 850–1550 mAh class, about
70–76 × 35 × 30–37 mm) held under it by the case, permanently in series, and gives the e-stim module +V / 0 V / −V
(12.0–16.8 V per rail) on a 4-pin JST-PH.  One toggle does ON / OFF.  **The packs are charged off the board**: unplug the
XT60 and put the pack on an ordinary hobby balance charger.  2-layer (B.Cu = 0V plane; was 4-layer until 2026-11-01, changed for JLC's faster 2-layer turnaround), JLC assembled (toggle, XT60s and the
PH socket through-hole).

## What was cut, and why

| Cut | BatteryPack parts | Consequence |
|---|---|---|
| USB-C PD charger island | J1, U4 CH224A, U18 LDO, Q12 / Q13 VBUS switch, U5 CN3704 buck and its parts (Q6, D7, D8, L1, R25–R27, C3–C11, C22, C23, C28, RT1, R24, R42–R44) | no charging on the board |
| Relays | K1, K2 and their drivers (Q19, Q25, R85–R88, D19, D20) | — |
| Charge controller | U19 STM32F042 with C24–C27, R28, R29, R70–R74, SW2 BOOT, TP1–TP4, the CHG / DONE LEDs D9, D10, D17, D18 + R66–R69; `firmware/` | — |
| Charging interlock | U17 opto + R76 | both rails are still interlocked on 0V reaching the module (Q22, Q26) |
| Balancers + balance sockets | U6–U13 HY2213, Q7–Q10 / Q15–Q18, R31–R38 / R58–R65, C12–C19, J5 / J6 JST-XH | they only bleed a cell above 4.2 V, i.e. while charging; the hobby charger balances.  The balance leads are not plugged in on this board |

Everything else is BatteryPack's, with the same references, values and LCSC codes (`sch_parts.py`), plus one addition,
the −V interlock Q26, and four more M3 holes for the case (H9–H12).  83 parts.

## What is on it

| Block | Parts | Notes |
|---|---|---|
| Pack sockets | J7 (pack A, −V side: GND / 0V), J8 (pack B, +V side: 0V / +BATB), Amass XT60PW-M horizontal (C98732, ext), each set 10 mm back over a notch in the front edge | **0V = pack A's positive = pack B's negative = the output reference, always** |
| Toggle | SW1 MTS-202 DPDT ON-ON (C55159891, ext) | ON / OFF.  Pole 1 (common EN_A): ON → 0V.  Pole 2 (common EN_B): ON → +BATB.  OFF opens both (R40 / R82 hold the enables low) |
| +V chain (pack B) | F1 100 mA PTC, Q1 AO3401A, R1 / R2 100k, Q22 2N7002, R81 1M, U15B (LM393), R53 1M, R82 | +BATB → F1 → +SW → Q1 → +OUT (J3.1).  Q22 turns Q1 on while ENB_G (= EN_B through R81) is high **and its source, J3.4 (CAB), is at 0V**, which only the strap at the module end provides.  U15B pulls ENB_G low below 12.0 V (back above 12.8 V) |
| −V chain (pack A) | F2 100 mA PTC, Q11 AO3400A, R39 / R40 100k, **Q26 AO3401A**, U2B, R11 470k, Q14 + D1 (ON) | GND → F2 → Q11 → −V (J3.3).  Q11's gate is pack A / 2 from EN_AI through R39 / R40; U2B pulls it low below 12.0 V, back on above 12.9 V.  **EN_AI = CAB through Q26**, whose gate is Q20_G (pack A / 2 below 0V while the toggle is ON, 0V when OFF): −V needs the toggle ON *and* CAB at 0V, like +V |
| Gauge rails | Q20 + R77 / R78 + Q21 + R79 / R80 (+G = 0V through Q20); Q23 + R83 / R84 + Q24 (+GB = +BATB through Q23) | follow the toggle |
| Gauges | pack A: U3 CJ431, R3–R10, U1 / U2 LM393, D2–D4 + R13–R15; pack B: U16, R45–R52, U14 / U15, D12–D14 + R55–R57, D11 + R54 ON from +OUT | per pack: green ≥ 15.9 V, green ≥ 15.1 V, yellow ≥ 14.3 V |
| Output | J3 S4B-PH-K-S side-entry (+OUT, 0V, −V, CAB), opening on the right edge, the body's top on the Pi's SE corner (pin 1 lowest) | **pin 4 (CAB) must be strapped to 0V at the module end of the cable**, on its own wire (see below) |
| Mounting | M3 for the case: H1–H4 corners, H9 (48, 25) / H10 (48, 50) on the centre line between the packs, H11 / H12 in the middle of the left / right edges; H5–H8 M2.5 for the Raspberry Pi (58 × 49), 5 mm in from the top edge. No strap slots (removed 2026-11-01: the case holds the packs) | packs under the board in the case, Pi above on ≥ 11 mm standoffs. H9 / H10 are under the Pi: fit the case screws there before the Pi |

Standing draw ON: 10–16 mA (two gauges, ON LEDs) plus the module's ~10 mA; OFF: the cutoff comparators only.

## Operation

- **ON:** both output chains enabled, both gauges lit.  Both rails appear only while CAB is tied to 0V at the module.  A pack below 12.0 V
  drops its rail (the module's fault comparator reports a missing rail); it comes back above 12.8 / 12.9 V.
- **OFF:** both enables open, rails off, gauges dark.
- **Charging:** toggle OFF, unplug the pack's XT60, charge it on a hobby balance charger (4S, 16.8 V), plug it back in.
  Charge both packs to the same state: they are in series, and the lower one cuts its rail first.

Thresholds and values are BatteryPack's (see its README, "Thresholds and values"; the charger lines there do not apply).

## Why both rails are interlocked

BatteryPack interlocked only +V, on the argument that −V without 0V is harmless because nothing in the module conducts
without 0V.  That is a claim about the module, not something this board enforces, so −V now gets the same interlock.
Chain A switches in pack A's negative and is referenced to GND, 16 V below CAB, so CAB cannot simply be Q11's source the
way it is Q22's.  Instead, Q26 (P) passes CAB to R39 while the toggle is ON, using the gauge rail's existing gate node
Q20_G for its drive (−pack A / 2, inside the AO3401A's ±12 V).  The gauges stay on EN_A / EN_B and show without the
module plugged in.

## Board

Built from BatteryPack's board and scripted the same way, then **hand-placed and hand-routed by the user (2026-11-01)**.
The board is now the source: **do not re-run** `place.py`, `orient.py`, `layers2.py`, `j3_bus.py` or `autoroute.py`
(each resets placement or rips copper). The script notes below record how the starting point was made; "Hand layout"
describes the board as it is. Safe on the hand layout: `sync_check.py` / `netcheck.py` (read-only), `pcb_sync.py
--keep-tracks`, `make_fab.py`, and `../tools/track_tidy.py`'s jog steps (skip its HAT-only `header()` step).

- **Netlist:** `tools/pcb_sync.py` (netlist `tools/ref/SimpleBatteryPack.net`).
- **Outline, `tools/place.py`:** 100 × 100 mm with 3 mm corner radii, and two notches 18 × 10 mm (1.5 mm radii) in the
  front edge under the XT60s (2026-11-01). The sockets' faces sit on the notch bottoms (y 90), so a plugged-in pack's
  plug stays inside the outline and its lead comes straight up from the pack underneath. A case round the board and
  packs then has nothing sticking out of the front except the toggle lever. The corner holes and Pi / HAT drawings are
  BatteryPack's (Pi moved 5 mm in from the top edge); BatteryPack's three strap slots are gone, and with them their
  copper keep-outs: the B.Cu 0V plane runs unbroken through the middle of the board.
- **Hand edits:** `place.py` puts everything it draws (outline, keep-outs, its silk) in a group named `place.py` and on a
  re-run removes only that group, so text or graphics added in pcbnew survive it; footprint positions are always reset
  to its table.
- **Placement, `tools/place.py`:**
  - Both gauges and both output chains are in the front strip, on a grid.
  - Pack A's columns run left to right towards its LED column: rail switch, sense divider, CJ431, ladder,
    comparators, then decoupling and the D1 driver.
  - Pack B's gauge mirrors pack A's about x = 50.
  - The ladder and the dividers are literal stacks: 0603s turned pin 1 up, at a 3.2 mm pitch, so each node is the gap
    between two resistors.
  - The LM393s face their inputs to the ladder and their outputs to the LEDs. The two per gauge sit side by side in one
    row (the set-back XT60 fills the space below them, the Pi standoff the space above), each with its decoupling cap
    under its VCC corner.
  - Each chain sits below its gauge, beside its XT60. J3 is on the right edge, its body's top on the Pi's SE corner.
  - SW1 stands between the XT60s with its lever throwing along y; its ON / OFF silk is beside the lever ends, east of
    the switch. (Hand layout: SW1 is turned to −90°, see below.)
  - Rotations that are part of this layout are listed in `LOCKED` and left alone by `tools/orient.py`, which turns the
    rest (62 ratsnest crossings).
- **Layers, `tools/layers2.py`:** 2 copper layers (2026-11-01; the 4-layer version had an In1 0V plane and In2 rail
  pours for the gauges, `tools/layers4.py`, removed). F.Cu carries the parts and most routing; B.Cu is a 0V pour over
  the whole board, the plane. The gauges' rails (GND for gauge A, +GB for gauge B) are tracks.
- **Output bus, `tools/j3_bus.py`:** only +OUT, −V and CAB have to reach J3. They are pre-routed by hand, locked, on
  B.Cu along the board's edges, so they do not cut the 0V plane through the middle. The route runs down the right edge, then west
  along the bottom of the board below the XT60 and toggle pins (y 87.8 / 89.2), to the chains. The chain FETs' rotations
  are locked so the bus ends stay on their pads. The strip of B.Cu south of the bus is left unpoured (island removal).
- **Routing:** `tools/autoroute.py` (Freerouting) routes everything but 0V, which it is kept off (left one pin in the
  DSN). `tools/plane_vias.py 0V --apply` then drops a via to the B.Cu plane by each 0V SMD pad (THT pads are in the
  pour). A last `ROUTE_0V=1 tools/autoroute.py --continue` routes 0V as tracks for any pad whose via lands on a piece of
  plane the B.Cu tracks have cut off; check the fill is one piece afterwards (2026-11-01: one piece, 7948 mm²).
  `plane_vias.py` also takes `--pad REF.PAD` for a pad group that is tied by tracks but has no via.

### Hand layout (2026-11-01, the board as built)

- **Toggle SW1** is at −90°: pins 1 / 4 (0V, +BATB) at the back (y 74.8), the unused throws 3 / 6 at the front
  (y 84.2). A bat-handle toggle closes the end **opposite** the lever, so the lever pushed **toward the front (toward
  3 / 6) is ON** and toward the back is OFF. The silk says so: ON at the front end (y 84.25), OFF at the back (y 74.25).
- **Gauge A** (pack A, referenced to GND = pack A −): GND is hand-routed as 0.8 mm tracks, mostly on B.Cu through the
  0V plane. An F.Cu GND pour was tried and dropped: its edge came within an M3 washer's reach of H10, with the 0V plane
  on the other face, so a metal screw there could short pack A. Nearest GND copper to H10 is now 3.1 mm from the hole.
- **Gauge B** (pack B, referenced to 0V): an F.Cu 0V pour (x 64–83, y 44–76) under it, stitched to the B.Cu plane.
- **Output bus:** −V still follows the locked `j3_bus.py` route (right edge, then west along y 87.8). +OUT and CAB are
  hand-routed: CAB on B.Cu from J3.4 diagonally to y 45.5, west across the board to x 26.5, then down x 15 to Q26; a
  branch to Q22. The B.Cu 0V plane stays one piece around both ends of that run.
- **Pin rings:** `tht_to_pour` in `SimpleBatteryPack.kicad_dru` keeps 1 mm of bare board between every through-hole
  pin and a pour of another net. The XT60 and toggle pins carry big solder fillets, and a bridge from J7.1 (GND),
  J8.2 or SW1.4 (+BATB) to the 0V plane is a dead pack short.
- **Battery spacing:** pack A − (GND) to pack B + (+BATB) is ≥ 1 mm everywhere on both layers; within one pack the
  closest copper is 0.3 mm (track to pour, under solder mask).
- **Silk:** gauge labels (A, B, 80 / 50 / 20 %, ON) are 1.0 mm / 0.15 mm stroke, all front text at 180° (read with the
  notches away from you). "OUT" by J3 and "CK SDG" on the back are still 0.8 mm (below JLC's 1.0 mm). The back pack
  outlines start at y 11, clear of the H7 / H8 standoffs.
- **The owl (G1):** decorative copper with no net (its 0V connection was removed in the schematic), so it adds no
  unconnected items.

Result 2026-11-01 19:48 (hand layout): DRC 0 violations, 0 warnings, 0 unconnected, 0 schematic-parity issues;
`sync_check` 0 differences (84 parts); B.Cu 0V plane one piece, F.Cu 0V pour 9 pieces, all connected.

## Assembly notes and first-article checks

- **Toggle lever direction:** lever toward the "ON" silk (the front, pins 3 / 6) should close common 2 → 1 and 5 → 4.
  Check one MTS-202 with a meter before assembly (lever toward pins 1 / 4: 2–1 open, 2–3 closed). If it is the other
  way round, swap the ON / OFF texts on SW1 in the board (they are board-level edits now, not `make_footprints.py`'s).
- **0V interlock (both rails):** run CAB (J3.4) up the cable as its own wire and tie it to 0V **at the module**, not in
  the PH plug at this board (on the module's next rev, strap its socket's pins 2 and 4).  Then Q22 and Q26 conduct only
  while the 0V wire really reaches the module: a broken 0V wire, a cracked joint or an unseated module end turns both
  rails off, which is the failure that killed the module twice.  A strap in the battery-end plug works, but it only
  proves that plug is seated.  Without any strap neither rail comes on.
- **XT60 polarity:** the footprint puts − at pad 1 (the end with the two bevelled corners) and + at the square-cornered
  end, which is how hobby packs are wired (red to the flat side).  Check a pack's plug with a meter against the silk + / −
  before the first pack goes in.
- **JLC rotation:** check the SOT-23s, SOICs and LEDs in JLC's DFM preview (same correction table as BatteryPack).
- Extended parts: toggle, XT60 sockets, PTCs, PH-4 header.  Everything else is basic.

## Checks before fab

**The schematic is hand-edited since 2026-11-01** (gauge B's comparator units reassigned — U14 A/B = TH50B/TH80B,
U15 A = cutoff, U15 B = TH20B — and the owl taken off 0V), so `gen_schematic.py` / `sch_parts.py` are stale: **do not
re-run `gen_schematic.py`**, it would undo those edits, and `tools/netcheck.py` (which checks against `sch_parts.py`)
now reports the gauge-B nets as a mismatch.  Checks: ERC (0) → F8 / `tools/pcb_sync.py --keep-tracks` only if nets or
footprints changed → `kicad-cli pcb drc` (0 / 0 / 0, parity included) → `../tools/sync_check.py` → `python
tools/lcsc_check.py` → `python tools/make_fab.py` (writes `../fab/SimpleBatteryPack/`; not run yet).

Shared with BatteryPack and copied here: `battpack.pretty` / `battpack.3dshapes` / `battpack.kicad_sym` (some footprints
in them, such as the relay and opto, are unused), `sch_engine.py`, `sch_symbols.py` and the board tools.  Symbol UUIDs are
derived from the references, so they are the same as BatteryPack's for the parts the two boards share.
