# DCDCPod — isolated ±15 V supply pod for the StimHAT (rev A, 2026-10-29)

The isolated supply that left the StimHAT on 2026-10-29 (StimHAT/README.md, "The DC-DC pod"): a Mornsun A0515S-1WR3
(5 V → ±15 V, 1 W), its 4.7 µF input capacitor, a 10 µH / 10 µF LC filter per rail and an NPN / PNP capacitance
multiplier per rail (≈ 0.6 V drop, ≈ 60 dB ripple rejection above 100 Hz), on a 31 × 19.5 mm two-layer board that
**stands vertically on the StimHAT's top side** in the band north of the BNC bodies and plugs into the HAT with two
right-angle pin headers on its bottom edge: J1 (1 × 2, 2.54 mm) into J103 (5 V / GND) and J2 (1 × 4, 2.0 mm) into the
holes of J102 (+V / 0V / −V / CAB; the JST socket is not fitted when the pod is used).  No output capacitors: the HAT
keeps C109 / C110 and the 20 V clamps.  Generated like the battery pack and the StimHAT; not ordered.

Files: `gen_schematic.py` + `sch_parts.py` + `sch_symbols.py` + `sch_engine.py` → `DCDCPod.kicad_sch` (deterministic
UUIDs, ERC 0 / 0) and `dcdcpod.kicad_sym`; `tools/netcheck.py` proves the drawing equals `sch_parts.PARTS`;
`tools/ref/DCDCPod.net` is the exported netlist; `tools/make_footprints.py` → `dcdcpod.pretty` (the StimHAT's
`DCDC_SIP6_A0515S_BodyN` with its VRML model in `dcdcpod.3dshapes`, and copies of KiCad's two horizontal pin headers
without the pin drawing beyond the body and without the silk pin-1 mark); `fp-lib-table` points only at `dcdcpod.pretty`
(everything else is KiCad's standard library).  Board: `tools/board_init.py` (once: rules, net classes, footprints from the
netlist via `tools/pcb_sync.py`), `tools/place.py` (placement, outline, barrier rule areas, silk; idempotent),
`tools/route.py` (scripted tracks, 0.3 mm, no vias; idempotent), `tools/project_settings.py` (classes / constraints into
the `.kicad_pro`), `tools/fresh_uuids.py`, `tools/stamp_fields.py` (LCSC field onto the footprints),
`tools/drc_summary.py`, `tools/check_isolation.py` (see Checks), `tools/make_fab.py` → `../fab/DCDCPod/` (gerbers, JLC BOM + CPL,
renders, README; move to `../fab/DCDCPod/` when ordering — this project was built without touching the other
directories).  `DCDCPod_schematic.pdf` is the drawing.  Python: `~/.venvs/kicad/bin/python` for the pcbnew scripts.

## Circuit

| Block | Parts | Nets |
|---|---|---|
| 5 V in | J1 pin 1 = 5 V, pin 2 = GND (into HAT J103); C104 4.7 µF 0603 (C69335) | +5V, GND |
| Converter | PS1 A0515S-1WR3, SIP, pins 1 +Vin, 2 −Vin, 4 −Vo, 5 0V, 6 +Vo; hand-fitted, no LCSC code (RECOM RB-0515D/HP is pin-compatible) | +V_RAW, 0V, −V_RAW |
| Filter | L101 / L102 10 µH 0805 (C139245) in series with +Vo / −Vo, C105 / C106 10 µF 25 V 0805 (C15850) after them to 0V | +V_F, −V_F |
| Multipliers | Q101 MMBT3904 (C20526): C = +V_F, B from +V_F through R111 4.7 k (C25900) with C107 10 µF to 0V, E = +V_OUT; Q102 MMBT3906 (C53444) mirror image on −V_F with R112 / C108, E = −V_OUT | QB_P, QB_N, +V_OUT, −V_OUT |
| Out | J2 (into HAT J102's holes): **pin 1 = CAB (= 0V), 2 = −V_OUT, 3 = 0V, 4 = +V_OUT** — the mirror of the HAT's J102 numbering (1 = +V … 4 = CAB), because the pod faces north and its pin 1 (square pad) is the east-most pin | |
| Test points | TP1 +V_OUT, TP2 0V, TP3 −V_OUT: 1.0 mm pads **on the back** (reachable with the pod unplugged; the back faces the BNC bodies 0.7 mm away when it is plugged in) | |

Load: the stimulator draws ≈ 10 mA per rail, well above the A0515S's 10 % minimum (3.3 mA at 1 W); the multipliers
drop ≈ 0.6 V, so expect ≈ ±14 V at the HAT's J102.  All three codes not already in `../tools/lcsc_catalog.json` were
looked up at JLC on 2026-10-29: C20526 = MMBT3904 (basic), C53444 = onsemi MMBT3906LT1G (extended), C139245 = Fenghua
CMP201209XD100MT 10 µH 0805 (extended).

## Mechanical: how the pod sits on the HAT

Pod coordinates: x 0–31 runs along the HAT's band, y 0–19.5 runs down the pod (y 19.5 = bottom edge, ≈ 0.5 mm above
the HAT's surface), the front (F.Cu, all parts) faces **north** (toward smaller HAT y).  Seen from the north, HAT east
is on the left, so **HAT x = 46 − pod x**.  The HAT's free band is x 15–46, y 36.5–43.1 (parts ≤ 1 mm), with the BNC
bodies (15.6 mm tall) from y 43.1 and the OLED bonnet (9 mm up) over y < 31.

| | pod (x, y) | net | HAT x | HAT hole |
|---|---|---|---|---|
| J2.4 | (2.00, 15.90) | +V_OUT | 44.00 | J102.1 +V |
| J2.3 | (4.00, 15.90) | 0V | 42.00 | J102.2 0V |
| J2.2 | (6.00, 15.90) | −V_OUT | 40.00 | J102.3 −V |
| J2.1 | (8.00, 15.90) | 0V (CAB) | 38.00 | J102.4 CAB |
| J1.2 | (24.46, 15.10) | GND | 21.54 | J103.2 GND |
| J1.1 | (27.00, 15.10) | +5V | 19.00 | J103.1 5 V |

J1.1 → J2.1 = 19.00 mm, J1.1 → J2.4 = 25.00 mm, as on the HAT (checked by `tools/check_isolation.py`).  Both headers
are rotated 270° (pins toward the bottom edge, pin numbers increasing westward on the HAT); J2's pads are 3.6 mm above
the edge (its 2.0 mm header has 4.2 mm tails: 3.6 mm reach below the edge → ≈ 3 mm into the HAT, 1.5 mm out of its
underside), J1's 4.4 mm (6 mm tails → ≈ 5 mm into the HAT: trim after soldering).

**Depth (HAT y).**  KiCad's models of the two headers put the horizontal pin 1.27 mm (2.54 mm header) and 1.00 mm (2.0 mm
header) in front of the board.  With both pin rows in the HAT's holes at y 40.1 the pod's front face is at HAT y
≈ 41.1–41.37; nominally 41.24, each pin 0.13 mm off its hole centre, taken up by the hole slack / pin flex (J102's holes
are 0.75–0.8 mm, the 0.5 mm pins have ≈ 0.03 mm of slack on the diagonal, so the pins bend a little; fit J2 first).
Back of the board (1.2 mm): y ≈ 42.44, **0.66 mm from the BNC bodies at 43.1** — the user's limit was y ≤ 42.8.  Hence:
1.2 mm board thickness (set in the board file; 1.6 mm leaves 0.26 mm), **header tails clipped flush with the back and
low solder fillets**, nothing on the back but the test-point pads.  PS1's body (10 mm) reaches north to y ≈ 31.2: the
bonnet's edge is at 31.0, so the margin to the bonnet PCB (z 9–10.6) is only ≈ 0.2–0.4 mm (see Open points).  The pod's
top edge is 20 mm above the HAT; nothing else is taller than PS1.

**Layout.**  PS1 at (17.74, 12.8) rot 180: pins 1 / 2 (+Vin, GND) at x 17.74 / 15.2 on the 5 V side, pins 4 / 5 / 6
(−Vo, 0V, +Vo) at x 10.12 / 7.58 / 5.04 on the isolated side, body y 7.7–13.7 toward the top edge with the marked face
up.  Isolated parts in two rows above PS1: bottom row (y 5.55) C105, L101, C106, L102 (0805, vertical), top row (y 1.95)
Q101, R111, C107, C108, R112, Q102 (courtyards 0.05–0.1 mm apart — the 6.4 mm between the top edge and PS1's courtyard
hold exactly two rows).  C104 right of PS1's body at (22.5, 10.8), J1 below it.  Routing channels: x 1.2 (+V_OUT, west
edge), x 6.1 (0V, between L101 and C106), x 8.85 (−V_OUT, between C106 / L102 and between PS1's pins 5 and 4, 0.32 mm
from each), the +V_F / −V_F buses at y 4.6 through the top pads of the bottom row; the CAB strap (J2.3 → J2.1) and the
test-point links are on the back.  Silk: "DC-DC POD / 5V -> ±15V / rev A", "ISOLATED", "5V SIDE", pin names at both
headers (front), "DC-DC POD rev A" and the test-point names on the back.

## Isolation

`iso_region` (x ≤ 11.4 everywhere, plus the top strip y ≤ 6.65 for x ≤ 20) and `hat_region` (x ≥ 13.9 for y ≥ 9.15,
plus x ≥ 22.5 everywhere) are rule areas that keep nothing out by themselves; the `barrier` rule area (no tracks, vias or
pours on both layers; drawn on User.Comments) is exactly the 2.5 mm gap between them: x 11.4–13.9 from PS1's pin row
down to the bottom edge (between pins 2 and 4, whose pads are 3.48 mm apart), then across PS1's body at y 6.65–9.15 and
up to the top edge at x 20–22.5, so the isolated parts can use the strip over PS1.  `DCDCPod.kicad_dru` (as the
StimHAT's): copper of a net outside class `Iso` may not intersect `iso_region`, `Iso` copper may not intersect
`hat_region`, and the two classes must be 2.5 mm apart (`isolation_gap`); `tht_connectors` asks 0.3 mm around the
header / SIP pads.  The 5 V side is J1, C104 and PS1's pins 1 / 2 only.  On the HAT, the pod's isolated copper at the
bottom edge is at HAT x ≥ 37.3 and its 5 V copper at x ≤ 22.4, i.e. over the HAT's own regions; any pod copper more
than 2 mm above the bottom edge is ≥ 2.5 mm from HAT copper in 3D regardless of x.

## Checks (2026-10-29)

- `kicad-cli sch erc --severity-all`: 0 errors, 0 warnings.  `tools/netcheck.py`: CONNECTIVITY OK (11 nets).
- `kicad-cli pcb drc --severity-all` (via `tools/drc_summary.py --all`, project rules + `DCDCPod.kicad_dru`): **0 errors,
  0 warnings, 0 unconnected**.
- `tools/check_isolation.py`: smallest isolated ↔ 5 V-side copper distance by shape **3.481 mm** (PS1.4 vs PS1.2); every
  copper item inside its region, none in the barrier; a 0V track dropped into the 5 V region of a copy fails DRC with
  `iso_copper_in_hat_region` (the rule file is live); all 17 footprint paths equal their symbols' UUIDs in the netlist;
  header pin spacing 19.00 / 25.00 mm, rows collinear.
- `tools/make_fab.py`: 11 placements, 6 BOM lines; J1, J2, PS1 hand-fitted, TP1–TP3 bare pads.

## Open points / to verify before ordering

1. **PS1 body side.**  The footprint is the StimHAT's `DCDC_SIP6_A0515S_BodyN` (body 0.9 mm behind / 5.1 mm in front of
   the pin row, pin 1 left in the marked-face view), still "pending the user's check on a physical module".  On the pod
   the body is drawn toward the top edge; if the real module's body lies on the other side of its pins, it would land on
   the header bodies — check with the module in hand (looking at the pod's front with the pin numbers increasing to the
   right from pin 6, the marked face must be on top).
2. **Bonnet margin.**  PS1's front at HAT y ≈ 31.2 vs the bonnet edge at 31.0 (≈ 0.2–0.4 mm; the module's 10 mm height
   has its own tolerance).  If it touches: bias the pod toward J1's pin height (front at 41.37, +0.13 mm) or shave the
   module's label face; a shorter SIP module (RECOM RB-0515D/HP is also 10 mm) does not help.
3. **Back clearance.**  0.66 mm to the BNC bodies: header tails must be clipped flush and the back kept bare.  An SMD
   right-angle header would remove the tails (different footprint, same pin geometry to re-check).
4. Order as 1.2 mm; the render / fab README say so.  Confirm JLC rotations of the SOT-23s and 0805s in the DFM preview.
5. The HAT's J102 holes are 0.75–0.8 mm for 0.5 mm square pins (0.71 mm diagonal): a snug fit, which is also what holds
   the pod upright.  Fit J2 first, then J1, solder on the HAT's underside.
