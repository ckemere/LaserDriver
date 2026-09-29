# EStimDaughter rev M4 — layout hand-off

For the session that routes `EStimDaughter.kicad_pcb` by hand. Read this, `README.md` §1–2 and
`../estim_interface/ESTIM_MODULE_SPEC.md` §2, §3, §7 first; `DESIGN_NOTES.md` for the why.

## State of the files (commit `ba12414`, 2026-09-29)
- Schematic: final for M4 (netlist = `sch_parts.py`, ERC 0). Regenerate only with `python gen_schematic.py`
  (it is generated code — don't hand-edit the .kicad_sch); then `python tools/netcheck.py`.
- Board: **placed, not routed.** Every footprint, net, the outline, the barrier rule areas, the In1.Cu ground
  planes and the F/In2/B ground pours are in the file. The placement is a greedy first pass: move anything.
- After a hand layout, **never run `tools/build_pcb.py` or `tools/route_pcb.py` on the board** — they rebuild it from
  scratch. If the schematic changes, use KiCad's *Update PCB from Schematic* (F8).

## Fixed
| Item | Value |
|---|---|
| Outline | x 101.0–127.5, y 76.0–112.5 (HAT coordinates, y down); 26.5 × 36.5 mm. y > 100 overhangs the HAT. |
| J8 (1×5, bottom side, pins run +x) | pin 1 at (109.00, 78.50): GND_H, +5V_H, EN_H, CATH_H, FAULT_H |
| J9 (1×5, bottom side, pins run +y) | pin 1 at (125.50, 82.00): GND_H, +3V3_H, RELEASE_H, SCL_H, SDA_H |
| PS1 (DNP, SIP along the west edge) | pins at x 102.3, y 78.50 / 81.04 (HAT side: +5V_H, GND_H) and y 86.12 / 88.66 / 91.20 (isolated: +V_STIM, GND_ISO, −V_STIM). Its body (x 101–108, y 76–96) is on the top: keep that area free of top-side parts. Battery packs use the same three isolated pads. |
| Stack-up | 4 layers: F.Cu signal / In1.Cu split ground planes (GND_H, GND_ISO) / In2.Cu signal / B.Cu signal. Single-sided assembly: **no SMD on B.Cu** (J8/J9/J1 are hand-fitted). |
| Isolation barrier | 2 mm copper-free on all four layers along the polyline (X0−1, 83.58) → (108, 83.58) → (108, 81.6) → (122, 81.6) → (122, 107.0) → (X1+1, 107.0) (band = ±1 mm about it). The `ISOLATION_BARRIER_*` rule areas in the board enforce it (no tracks, vias, pours). |
| HAT domain (nets GND_H, +5V_H, +3V3_H, EN_H, CATH_H, RELEASE_H, SCL_H, SDA_H, FAULT_H) | north strip y < 80.6 (x < 107: y < 82.58) and the east column x > 123, y < 106 |
| Isolated domain (everything else) | the rest: x < 121 south of y 84.58 (x 109–121 from y 82.6), plus the full width south of y 108 |
| Parts that straddle the barrier — the only ones allowed to | PS1 (pins 1–2 HAT side, 4–6 isolated), U1 ISO7741F and U9 ISO1640 (pins 1–8 HAT side east, 9–16 / 5–8 isolated west) |
| DRC rules (in `EStimDaughter.kicad_pro`; run DRC with the project) | clearance 0.15, track ≥ 0.15 (default 0.2, power class 0.3), via 0.5/0.3 (min 0.45), hole-to-hole 0.25, copper-to-edge 0.3, silk text ≥ 0.8 mm. Vias tented. |

## Decided, but you may move things
- J1 (electrode) on the south edge, currently x 115, y 111, pins pointing south. Any x on that edge is fine now
  (the edge is 12.5 mm beyond the HAT and its BACK button).
- U8 (LM393) and its threshold networks R23–R28, the E1 tap R20/R21/R22/C18 and C19 as one block; it only needs E1,
  ±V, +5V_ISO and FAULT_n (to U1 pin 11).
- U2 and the −5 V parts (R6, D1, C8) under PS1's body region on the south side; C4/C5 at PS1's ±V pins.

## What matters electrically
- **E1 / ISENSE / E1_OUT** (U5A output → R13 → E1 → C16 → J1.1; U5.2 = ISENSE = R14 = J1.2 = U7.2): short, together,
  away from the I²C and EN/CATH lines. R14 is the sense resistor: its ISENSE end goes to U5 pin 2 with a dedicated
  short trace; its ground end to GND_ISO near U5.
- U5's rails: C11 / C12 at pins 8 / 4. U6: C13 at 16, C14 at 7 (−5V_ISO). U4: C10 at VDD, C9 at VREFIO. U1: C1 / C2
  at 1 / 16. U9: C17 / C20 at 4 / 5. LDO: C6 in, C7 out (required for stability).
- Isolated-side pours are GND_ISO, HAT-side pours GND_H; keep the In1 planes as they are (split along the barrier).
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
(none)
