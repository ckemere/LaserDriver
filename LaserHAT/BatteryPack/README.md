# BatteryPack — ±V battery board for the e-stim module (rev C: two hobby 4S packs)

Rev C, 2026-10-27.  One 100 × 100 mm board carries two off-the-shelf 4S hobby packs (any LiPo or Li-ion pack with the
standard JST-XH 5-pin balance plug, 850–1550 mAh class, about 70–76 × 35 × 30–37 mm) strapped to its underside, and gives
the e-stim module +V / 0 V / −V (12.0–16.8 V per rail) on a 4-pin JST-PH.  One USB-C PD charger charges both packs in
parallel; one toggle does RUN / OFF / CHARGE.  2-layer, JLC assembled (toggle, XH sockets and PH header through-hole).

Rev B (commit `6fa6e9d`) was a 4S 18650 board with clips, two of them stacked over a 4-wire cable; rev C replaces the
clips with pack sockets and merges the two boards.  The output cable to the module is unchanged.

Files: `gen_schematic.py` + `sch_parts.py` + `sch_symbols.py` (+ `sch_engine.py`) generate `BatteryPack.kicad_sch`
(deterministic UUIDs, like the e-stim module); `tools/netcheck.py` proves the drawing matches `sch_parts.py`;
`tools/make_bom.py` writes `bom_BatteryPack.csv`; `tools/make_footprints.py` writes `battpack.pretty/` (toggle; the clip
footprint is kept for rev B).  Board: `tools/board_init.py` (once: rules, netclasses, footprints from the netlist via
`tools/pcb_sync.py`), `tools/place.py` (outline, slots, holes, placement, silk; idempotent) and `tools/autoroute.py`
(rip-up, stubs out of pads narrower than their net class, Freerouting headless through DSN/SES, stub clean-up, DRC)
built it — the user is remote, so the layout is scripted rather than hand-placed like the other boards.  Hand edits in
pcbnew are fine afterwards; re-running `place.py` + `autoroute.py` discards them.  `tools/stamp_fields.py` puts the LCSC
codes on the footprints, `tools/make_fab.py` writes `../fab/BatteryPack/` (gerbers, JLC BOM + CPL).

## What is on it

| Block | Parts | Notes |
|---|---|---|
| Pack sockets | per pack an XT60 and a JST-XH: J7 / J5 (pack A, −V side), J8 / J6 (pack B, +V side); XT60 = Amass XT60PW-M horizontal (C98732, ext), XH = JST S5B-XH-A-1 right-angle (C163038, ext) | the XT60 discharge plug carries the run and charge current (J7 = GND / +BAT, J8 = 0V / +BATB; the plug is keyed, the footprint silk marks + and −); the balance plug gives the cell taps (XH pin 1 = black = pack negative, 2–4 = taps, 5 = pack positive; pins 1 and 5 parallel the XT60).  J5 = GND, C1, C2, C3, +BAT; J6 = 0V, B1, B2, B3, +BATB.  A pack with an XT30 lead needs an XT30-to-XT60 adapter |
| Balancers | pack A: U6–U9 HY2213-BB3A (C113632, ext), Q7–Q10 AO3400A, R35–R38 100 R 1206, R31–R34, C12–C15; pack B: U10–U13, Q15–Q18, R62–R65, R58–R61, C16–C19 | 42 mA bleed above 4.200 V, release 4.19 V, 2.5 µA standing, per cell of both packs |
| Toggle | SW1 MTS-203 DPDT centre-off (C55160018, ext; **JLC stock 192 on 2026-10-27**) | **RUN / OFF / CHARGE**.  Pole 1 (common 0V = pack B's negative): RUN → +BAT (packs in series, 0V = output 0 V); CHARGE → GND (negatives joined).  Pole 2 (common +BATB): RUN → +RUN (pack B's output chain); CHARGE → +CHGB → F3 → +BAT (positives joined).  OFF opens both; R30 1M holds 0V at GND |
| Link fuse | F3 MF-MSMF110/24X-2 1.1 A PTC (C210835, ext) | in the CHARGE link between the two packs' positives: limits the equalising current if the packs are at different voltages when switched to CHARGE |
| +V chain (pack B) | F1 100 mA PTC MF-MSMF010-2 (C12430, ext), Q1 AO3401A, R1/R2 100k, U15B (LM393), R53 1M | +RUN → F1 → +SW → Q1 → +OUT (J3.1).  Off below 12.0 V, back on above 12.8 V |
| −V chain (pack A) | F2 100 mA PTC, Q11 AO3400A (N, in pack A's negative), R39/R40 100k, U2B (LM393), R11 470k, Q14 + D1 (ON) | GND → F2 → Q11 → −V (J3.3).  Q11's gate is +BAT/2 only in RUN (R39 from 0V); U2B pulls it low below 12.0 V, back on above 12.9 V.  Q14 lights D1 while Q11 conducts without loading −V |
| Gauges | pack A: U3 CJ431, R3–R10, U1/U2 LM393, D2–D4 + R13–R15 on rail +G (= 0V or +CHGB via D15/D16); pack B: U16, R45–R52, U14/U15, D12–D14 + R55–R57 on +GB (= +SW or +CHGB via D5/D6), D11 (right-edge column) + R54 ON from +OUT | per pack: green ≥ 16.0 V, green ≥ 15.2 V, yellow ≥ 14.4 V, ~1 mA each; both gauges show in RUN and CHARGE, dark in OFF |
| Charger | J1 USB-C (C165948, ext), U4 CH224A (C42459160, ext) + C3 + R24 120k, **Q13 AO3401A VBUS switch** + R43/R44 + Q12 AO3400A + R41/R42, U5 CN3704 (C51659, ext), Q6 AO3401A, D7/D8 SS34, L1 22 µH (C408453, ext), R25+R26 0.2 R, C4–C11, R27, RT1 NTC (C13564, ext), D9 CHRG red, D10 DONE green | PD brick negotiated to 20 V; Q13 passes VBUS to the charger only in CHARGE (Q12's gate sees +CHGB), so a brick plugged in while RUN or OFF does nothing.  1 A CC shared by the two packs in parallel, 16.8 V ±1 % CV, termination 92 mA, trickle 150 mA below 11.2 V, re-charge below 16.0 V, 18.1 V over-voltage cut, NTC stops it hot / cold.  Everything on GND (= pack A's negative = the USB-C shell) |
| Output | J3 B4B-PH-K-S (+OUT, 0V, −V, nc) | same 4-wire cable to the module as rev B (pin 4 unused) |
| Mounting | H1–H4 M3 at (4, 4), (96, 4), (4, 96), (96, 96); three 3.5 × 22 mm strap slots at x 3–6.5, 45.75–50.25, 90.5–94, y 39–61; **H5–H8 M2.5 at (29.5, 7.5), (87.5, 7.5), (29.5, 56.5), (87.5, 56.5) = a Raspberry Pi's 58 × 49 pattern** | packs under the board on 40 mm standoffs (packs are up to 37 mm thick); two 20 mm hobby battery straps, each through the outer slot and the shared middle slot.  The Pi (3B+ / 4 / 5, with the HAT on it) sits above the board on 11 mm or taller M2.5 standoffs over x 26–100, y 4–60: its ports end overhangs the right edge by 11 mm, the toggle, the pack sockets, the output header and every LED stay uncovered; the tallest part under it is the 22 µF electrolytic (~7 mm) and the USB-C charger cable plugs in under the overhang |

Standing draw in RUN: 10–16 mA (two gauges, ON LEDs); in CHARGE with no brick: the same from the packs; in OFF about
40 µA (balancers, charger output stage).  The e-stim module itself draws about 10 mA.

## Operation

- **RUN:** packs in series, both output chains enabled; +V = pack B, −V = pack A, 0 V = their junction.  A pack below
  12.0 V drops its rail (the module's fault comparator reports a missing rail); it comes back above 12.8 / 12.9 V.
- **OFF:** both toggle poles open, 0V tied to GND through 1M, both rails float, gauges dark.
- **CHARGE:** the packs are joined in parallel (negatives by the toggle, positives through F3) across the one charger;
  both outputs are open (Q1 unpowered, Q11's gate at 0 V).  Plug a 20 V PD brick (≥ 30 W) into J1: CHRG lights, both
  gauges show their pack, DONE lights at 92 mA total.  The module can stay connected: it sees 0 V across its rails.
- Switching to CHARGE with the packs at different voltages: the fuller pack feeds the emptier one through F3 (1.1 A
  hold, 2.2 A trip); a large mismatch trips F3, which then limits the equalisation to a trickle until the charger has
  brought the lower pack up.  Charge the packs separately on a hobby charger if they differ by more than a volt.
- A brick plugged in while RUN or OFF does nothing (Q13 open): charge only in CHARGE.

## Thresholds and values

Gauge rails: +GB = pack B − 0.25 V, +G = pack A − 0.25 V in RUN (SS14 at ~5 mA); in CHARGE both come from +CHGB (pack B's
terminal: pack A's gauge then reads pack B through F3 — a few tens of mV low while charging).  VS = rail × 0.1357 with
the output live (R9 68k ∥ R11 against R10 10k), × 0.1271 cut off.  Ladder from 2.495 V: 6.8k, 2k, 2k, 6.2k, 30k →
TH80 2.137 V, TH50 2.029 V, TH20 1.920 V, THCUT 1.595 V → 16.0 / 15.2 / 14.4 V (pack) and 12.0 V (cutoff) / 12.8 V
(re-enable, pack B via R53 1M from +OUT) / 12.9 V (pack A via R11 470k from Q11's gate, which sits at +BAT/2).
Charger: Ich = 200 mV / 0.2 R = 1 A total (0.5 A per pack when balanced; 0.4 C for a 1300 mAh pack); Ieoc = 9.17 %
(EOC grounded); CH224A CFG1 120k = 20 V request.  Q13: Vgs = −VBUS/2 = −10 V (R43/R44), Rds ~50 mΩ at 1 A.

## Board

100 × 100 mm (JLC's cheapest size tier).  Packs underneath, long axis along y, envelopes x 7–45 and 51–89, y 10–86
(silk outlines on the back), leads round the front edge (y = 100): XH sockets J5 (pins x 10.5–20.5) and J6 (x 79.5–89.5)
outboard, XT60 sockets J7 (pins x 28.8 / 36, + on the left) and J8 (x 61.8 / 69) inboard, faces flush with the edge.
Top side: pack A's gauge top left (LEDs on the left edge at y 10–22), its balancers mid left (x 8–38,
y 39–61), its −V chain bottom left; the charger top right with the USB-C on the right edge at y 14 and its CHRG / DONE LEDs on the top edge at y 2.5
(x 66–84, outside the Pi's edge at y 4); pack B's balancers mid right (x 52–82), its gauge lower right (80 / 50 / 20 % / ON LEDs on the right edge at y 66–78, below the Pi's edge), its +V chain right of the gauge (x 81–90, y 62–80); toggle at (49, 84) and J3 at (45.5–51.5, 94.5) between
the XT60s, F3 / R30 at (40, 70–76).  Netclasses: Power 0.8 mm
(+BAT, GND, 0V, +BATB, C1–C3, B1–B3, +RUN, +SW, +OUT, +CHGB, −V, GNDF), Charger 0.4 mm (SW, SWA, CSP, RCS, VBUS, VCHG),
Fine 0.25 / 0.15 mm (USB-C CC1/CC2/D+/D−), Default 0.3 / 0.2 mm.  Board minimums 0.15 / 0.15 (JLC: 0.127).  No copper
pours; rule areas keep vias out from under the Pi standoffs (r 3.0) and 0.5 mm round the slots.  Reference designators are hidden on the silk; the silk carries PACK A / PACK B at the sockets, OUT, RUN/CHG,
LED functions, CHRG / DONE and the USB-C label.

## Assembly notes and first-article checks

- **Toggle lever direction:** the silk assumes the usual toggle convention (lever away from the closed contacts):
  lever toward "RUN" closes pins 1/4 (RUN), toward "CHG" closes 3/6.  Verify with a meter on the first board; if the
  switch is the other way round, swap the two silk words in `tools/make_footprints.py` and on the board.
- **Pack plug polarity:** JST-XH pin 1 (the socket's marked end, x 10.5 on J5 and x 79.5 on J6) must take the pack's black
  wire.  Every 4S hobby pack wires the balance plug this way; check the first pack with a meter against the silk.  The
  XT60 is keyed; check that the pack's + (the pin at the rounded side of the plug) lands on the XT60PW's + (x 28.8 / 61.8)
  before the first pack goes in — a pack wired the wrong way round would short through the XH pins.
- **JLC rotation:** check SOT-23, SOIC, TSSOP, the LEDs (cathode = pad 1, KENTO parts as on the HAT) and the
  electrolytic in JLC's DFM preview before ordering.
- **USB-C:** front flush with the board edge (footprint origin 4.2 mm inside).  CH224A requests 20 V; a 5 V-only
  source leaves the CN3704 below its lock-out, nothing charges.
- **First charge:** both packs at about the same voltage, toggle to CHARGE, meter on CSP−BAT (200 mV = 1 A) and on each
  pack's XH pins; confirm DONE at ~90 mA and the balancer resistors warming on the fullest cells.  RT1 reads the board
  temperature next to the charger; a 10k fixed resistor in its place disables temperature control.
- **Straps:** 20 mm hobby battery straps (the usual 5-inch-quad ones, 200–250 mm long); the middle slot takes both.
- Extended parts (feeder fee each): toggle, XH and XT60 sockets, PTCs, USB-C, CH224A, CN3704, inductor, electrolytic, HY2213,
  NTC, PH-4 header.  Everything else is basic.

## Checks before fab

`python gen_schematic.py` → `python tools/netcheck.py` (CONNECTIVITY OK) → ERC (0) → `tools/pcb_sync.py` only if
nets or footprints changed (`--keep-tracks`) → `../tools/path_check.py` / `sync_check.py` → `kicad-cli pcb drc` →
`python tools/lcsc_check.py` → `python tools/make_fab.py`.

**XT60 footprint and 3D model.**  `battpack.pretty/XT60PW-M.kicad_mod` is KiCad's AMASS_XT60PW-M footprint with its
model pointed at `battpack.3dshapes/XT60PW-M.step`, which `tools/make_xt60_model.py` builds with CadQuery (KiCad 9 ships
no model for the horizontal part; the model reuses the vertical XT60-M nose and adds the PW's body, bent pins and legs).

**Part numbers on the board.**  `sch_parts.py` holds the LCSC codes; the generator writes them into every symbol as the
`LCSC Part #` field and `tools/stamp_fields.py` writes the same field (hidden, F.Fab) into every footprint, syncs the
Values and marks H1–H4 excluded from BOM and position files — so a BOM/CPL made straight from the PCB with the
Fabrication Toolkit carries the codes too.  Re-run `stamp_fields.py` after changing a value or code in `sch_parts.py`.
Values of switches, LEDs, connectors, the inductor and the NTC are JLC's model strings (their matcher compares the BOM
Comment with them); plain R/C values still draw JLC's harmless "comment differs" note, as on the HAT.
