# EStimDaughter rev M4 — layout hand-off

For the session that routes `EStimDaughter.kicad_pcb` by hand. Read this, `README.md` §1–2 and
`../estim_interface/ESTIM_MODULE_SPEC.md` §2, §3, §7 first; `DESIGN_NOTES.md` for the why.

## State of the files (commit `ba12414` plus the uncommitted 2026-09-29 layout-session changes below)
- Schematic: final for M4 (netlist = `sch_parts.py`, ERC 0). Regenerate only with `python gen_schematic.py`
  (it is generated code — don't hand-edit the .kicad_sch); then `python tools/netcheck.py`.
- Board: **placed and routed** (all connections closed on 2026-09-29; DRC clean apart from silk and library-copy warnings). Every footprint, net, the outline, the barrier rule areas, the In1.Cu ground
  planes and the F/In2/B ground pours are in the file. The placement is a greedy first pass: move anything.
- After a hand layout, **never run `tools/build_pcb.py` or `tools/route_pcb.py` on the board** — they rebuild it from
  scratch. If the schematic changes, use KiCad's *Update PCB from Schematic* (F8).
  Since 2026-09-29 the generator emits **stable UUIDs** (symbol UUID = uuid5 of the reference) and every footprint carries
  its schematic path (`/<symbol uuid>`), so F8 matches by UUID and keeps placement and routing; no need to tick "re-link by reference".

## Fixed
| Item | Value |
|---|---|
| Outline | x 101.0–127.5, y 76.0–112.5 (HAT coordinates, y down); 26.5 × 36.5 mm. y > 100 overhangs the HAT. |
| J8 (1×5, bottom side, pins run +x) | pin 1 at (109.00, 78.50): GND_H, +5V_H, **FAULT_H, CATH_H, EN_H** (J8.3/J8.5 swapped 2026-09-29 evening, spec §3/§7; HAT copper change) |
| J9 (1×5, bottom side, pins run +y) | pin 1 at (125.50, 82.00): GND_H, +3V3_H, RELEASE_H, SDA_H, SCL_H (SDA/SCL swapped 2026-09-29, spec §7) |
| PS1 (DNP, SIP along the west edge) | pins at x 102.3, y 78.50 / 81.04 (HAT side: +5V_H, GND_H) and y 86.12 / 88.66 / 91.20 (isolated: +V_STIM, GND_ISO, −V_STIM). Its body (x 101–108, y 76–96) is on the top: keep that area free of top-side parts. Battery packs use the same three isolated pads. |
| Stack-up | **4 layers**: F.Cu parts, signals, GND pours / In1.Cu split ground planes / In2.Cu power (user-routed) / B.Cu long logic runs, V_IN, GND pours. Single-sided assembly: **no SMD on B.Cu** (J8/J9/J1 are hand-fitted). (2-layer tried and dropped 2026-09-29.) |
| Isolation barrier | 2 mm copper-free on all four layers along the L-shaped polyline (X0−1, 83.58) → (120, 83.58) → (120, 95.5) → (X1+1, 95.5) (band = ±1 mm about it: y 82.58–84.58, x 119–121, y 94.5–96.5). The `ISOLATION_BARRIER_0/1/2` rule areas in the board enforce it (no tracks, vias, pours). Reshaped 2026-09-29. |
| HAT domain (nets GND_H, +5V_H, +3V3_H, EN_H, CATH_H, RELEASE_H, SCL_H, SDA_H, FAULT_H) | north strip y < 82.58 and the east column x > 121, y < 94.5 |
| Isolated domain (everything else) | the rest: x < 119 south of y 84.58, plus the full width south of y 96.5 |
| Parts that straddle the barrier — the only ones allowed to | PS1 (pins 1–2 HAT side, 4–6 isolated), U1 ISO7741F (pins 1–8 north = HAT side, 9–16 south = isolated) and U9 ISO1640 (pins 1–4 east = HAT side, 5–8 west = isolated) |
| DRC rules (in `EStimDaughter.kicad_pro`; run DRC with the project) | clearance 0.15, track ≥ 0.15 (default 0.2, power class 0.3), via 0.5/0.3 (min 0.45), hole-to-hole 0.25, copper-to-edge 0.3, silk text ≥ 0.8 mm. Vias tented. |

## Decided, but you may move things
- Isolator channel order (2026-09-29) matches the placement: U1 pin 3 = RELEASE_H (from J9.3 in the east), 4 = EN_H
  (opposite J8.3), 5 = CATH_H (opposite J8.4), 6 = FAULT_H; outputs 14 / 13 / 12 = RELEASE / EN / CATH. FAULT_H from J8.5 (east) to pin 6
  (west) crosses the EN/CATH drops: take it off the J8.5 through-hole pad on In2.Cu and come up with one via near
  (115.3, 79.9). It cannot be moved to J8.3: PA6 is the MCU's only TIMA0 fault pin and PA7 has no fault function.
- U9: pin 3 = SDA_H, 2 = SCL_H (straight from J9.4 / J9.5); pin 6 = SDA, 7 = SCL, in the order the DAC pads want.
- J1 (electrode) on the south edge, currently x 115, y 111, pins pointing south. Any x on that edge is fine now
  (the edge is 12.5 mm beyond the HAT and its BACK button).
- U8 (TLV1702, M4b) with its string R23/R24/R25 (between +V and −V), R26 + D2 (level shift to FAULT_n), R19 and C19
  (100 n 50 V across ±V) as one block; it needs E1, ±V, GND_ISO, +5V_ISO and FAULT_n (to U1 pin 11). R20–R22, C18,
  R27, R28 are gone (2026-09-29).
- U2 under PS1's body region on the south side; U6 (ADG1436 LFCSP, M4c) south-west, C13/C14 as ±V taps near (106.7, 97.4) / (103.6, 97.1); C4/C5 at PS1's ±V pins.

## What matters electrically
- **E1 / ISENSE / E1_OUT** (U5A output → R13 → E1 → C16 → J1.1; U5.2 = ISENSE = R14 = J1.2 = U7.2): short, together,
  away from the I²C and EN/CATH lines. R14 is the sense resistor: its ISENSE end goes to U5 pin 2 with a dedicated
  short trace; its ground end to GND_ISO near U5.
- U5's rails: C11 / C12 at pins 8 / 4. U6: no cap of its own within 2 mm; C13 (+V) and C14 (−V) are taps on the west feed, C11/C12 at U5 are 5 mm away. U4: C10 at VDD, C9 at VREFIO. U1: C1 at pin 1,
  C2 between U1 pin 16 and U9 pin 5 (one cap for both VCC2 pins, they are 3.3 mm apart). U9: C17 at 4. PS1: C5 only (C6 is the +V bulk). LDO: C6 in, C7 out (required for stability).
- Isolated-side pours are GND_ISO, HAT-side pours GND_H, on F/In1/B, split along the barrier; In2 is the power layer. The 2026-09-29 power/logic routing came from `tools/fixroute.py` (grid router) on top of the hand-routed signals: legal but not pretty, tidy at will.
- Cable capacitance from E1_OUT to anything else < 500 pF (stability); nothing else is fast.

## Before pushing
```
kicad-cli pcb drc --severity-all -o route/drc.rpt EStimDaughter.kicad_pcb     # next to the .kicad_pro; must be clean
python tools/netcheck.py                                                        # schematic netlist == sch_parts.py
```
and check there is no copper of either domain across the barrier and no isolated-copper islands (DRC lists both).
Then `../tools/jlc_fab.py` regenerates `../fab/EStimDaughter` (gerbers, BOM, CPL, renders).

## Questions
Message the HAT session directly (name `laserhat-87` on 2026-09-29), or append them below and push:

### Open questions
1. **To `laserhat-87` (2026-09-29, not reachable from the module session):** J9.4 and J9.5 swapped meaning: **J9.4 "ADC_A" (PA17) = SDA, J9.5 "ADC_B" (PA22) = SCL**.
   **A (laserhat-87, 2026-09-29):** accepted — firmware only (PA17 = SDA, PA22 = SCL); spec §7 and REV2_NOTES say so now. Also note the fault detector changed to a ±V-supplied TLV1702 in the same day (parts R20–R22/C18/R27/R28 removed, D2 added; U8 keeps its footprint) — the board was synced with `tools/pcb_sync.py --keep-tracks`, new D2 is parked east of the outline. Firmware-only on the HAT (bit-banged I²C), no copper change. Spec §7 already says so; please acknowledge and update `REV2_NOTES.md` (the PA17/PA22 rows still say "e-stim SCK / MOSI") and the firmware pin defines.
2. **To `laserhat-87` (2026-09-29 evening, user decision):** the pulse-header standard changes: **J8.3 = FAULT_n (PA6, TIMA0_FAULT0), J8.5 = EN (PA7, TIMA0_CCP1)**; J8.4 = CATH unchanged. Please swap the two HAT traces to J8 pins 3 and 5, re-route the laser daughterboard's J8.3/J8.5 accordingly, and update `REV2_NOTES.md` (J8 row, PA6/PA7 rows) and firmware pin defines. Reason: the ISO7741's reverse channel exits on pin 6 at the west end of its HAT-side row, so FAULT on J8.3 makes every header line fall straight onto U1. Spec §3 and §7 are already updated.
