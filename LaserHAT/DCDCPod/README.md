# DCDCPod — isolated ±15 V supply pod for the StimHAT (rev A, 2026-10-29; turned around 2026-10-30)

The isolated supply that left the StimHAT on 2026-10-29 (StimHAT/README.md, "The DC-DC pod"): a Mornsun A0515S-1WR3
(5 V → ±15 V, 1 W), its 4.7 µF input capacitor, a 10 µH / 10 µF LC filter per rail and an NPN / PNP capacitance
multiplier per rail (≈ 0.6 V drop, ≈ 60 dB ripple rejection above 100 Hz), on a 31 × 22.5 mm two-layer 1.6 mm
board that **stands vertically on the StimHAT's top side** in the band north of the BNC bodies, parts face south, PS1
along its top edge hanging over the BNC bodies, and plugs into the HAT with two right-angle pin headers on its bottom
edge: J1 (1 × 2, 2.54 mm) into J103 (5 V / GND) and J2 (1 × 4, 2.0 mm) into the
holes of J102 (+V / 0V / −V / CAB; the JST socket is not fitted when the pod is used).  No output capacitors: the HAT
keeps C109 / C110 and the 20 V clamps.  Generated like the battery pack and the StimHAT; not ordered.

Files: `gen_schematic.py` + `sch_parts.py` + `sch_symbols.py` + `sch_engine.py` → `DCDCPod.kicad_sch` (deterministic
UUIDs, ERC 0 / 0) and `dcdcpod.kicad_sym`; `tools/netcheck.py` proves the drawing equals `sch_parts.PARTS`;
`tools/ref/DCDCPod.net` is the exported netlist; `tools/make_footprints.py` → `dcdcpod.pretty` (the StimHAT's
`DCDC_SIP6_A0515S_BodyN` with its VRML model in `dcdcpod.3dshapes`, and copies of KiCad's two horizontal pin headers
without the pin drawing beyond the body and without the silk pin-1 mark, mirrored along the pin row so that pad 1 is
at the far end of the row — see Mechanical); `fp-lib-table` points only at `dcdcpod.pretty`
(everything else is KiCad's standard library).  Board: `tools/board_init.py` (once: rules, net classes, footprints from the
netlist via `tools/pcb_sync.py`; `--reload J1 J2` re-loads footprints that `make_footprints.py` changed),
`tools/place.py` (placement, outline, barrier rule areas, silk; idempotent),
`tools/route.py` (scripted tracks, 0.3 mm, no vias; idempotent), `tools/project_settings.py` (classes / constraints into
the `.kicad_pro`), `tools/fresh_uuids.py`, `tools/stamp_fields.py` (LCSC field onto the footprints),
`tools/drc_summary.py`, `tools/check_isolation.py` (see Checks), `tools/make_fab.py` → `../fab/DCDCPod/` (gerbers, JLC BOM + CPL,
top / bottom / perspective renders, README).  `DCDCPod_schematic.pdf` is the drawing.  Python: `~/.venvs/kicad/bin/python` for the pcbnew scripts.

## Circuit

| Block | Parts | Nets |
|---|---|---|
| 5 V in | J1 pin 1 = 5 V, pin 2 = GND (into HAT J103); C104 4.7 µF 0603 (C69335) | +5V, GND |
| Converter | PS1 A0515S-1WR3, SIP, pins 1 +Vin, 2 −Vin, 4 −Vo, 5 0V, 6 +Vo; hand-fitted, no LCSC code (RECOM RB-0515D/HP is pin-compatible) | +V_RAW, 0V, −V_RAW |
| Filter | L101 / L102 10 µH 0805 (C139245) in series with +Vo / −Vo, C105 / C106 10 µF 25 V 0805 (C15850) after them to 0V | +V_F, −V_F |
| Multipliers | Q101 MMBT3904 (C20526): C = +V_F, B from +V_F through R111 4.7 k (C25900) with C107 10 µF to 0V, E = +V_OUT; Q102 MMBT3906 (C53444) mirror image on −V_F with R112 / C108, E = −V_OUT | QB_P, QB_N, +V_OUT, −V_OUT |
| Out | J2 (into HAT J102's holes): **pin 1 = CAB (= 0V), 2 = −V_OUT, 3 = 0V, 4 = +V_OUT** — the mirror of the HAT's J102 numbering (1 = +V … 4 = CAB); pin 1 (square pad) is the west-most pin, on HAT x 38 (unchanged since rev A was drawn facing north: the mirrored header footprint keeps the pin → net table) | |
| Test points | TP1 +V_OUT, TP2 0V, TP3 −V_OUT: 1.0 mm pads **on the back** over J2 (the back faces the bonnet, 5 mm away; reachable with the pod unplugged) | |

Load: the stimulator draws ≈ 10 mA per rail, well above the A0515S's 10 % minimum (3.3 mA at 1 W); the multipliers
drop ≈ 0.6 V, so expect ≈ ±14 V at the HAT's J102.  All three codes not already in `../tools/lcsc_catalog.json` were
looked up at JLC on 2026-10-29: C20526 = MMBT3904 (basic), C53444 = onsemi MMBT3906LT1G (extended), C139245 = Fenghua
CMP201209XD100MT 10 µH 0805 (extended).

## Mechanical: how the pod sits on the HAT (since 2026-10-30)

Pod coordinates: x 0–31 runs along the HAT's band, y 0–22.5 runs down the pod (y 22.5 = bottom edge, 0.5 mm above
the HAT's surface; height above the HAT **z = 23.0 − pod y**).  The front (F.Cu, every part) faces **south**, toward
the BNC bodies, and is seen from the south, so HAT east is on the right: **HAT x = pod x + 15** (the pod still covers
HAT x 15–46).  The HAT's free band is x 15–46, y 36.5–43.1 (parts ≤ 1 mm) with the J102 / J103 rows at **y 39.0**, the
BNC bodies (15.6 mm tall) from y 43.1 and the OLED bonnet (PCB at z 9–10.6) over y < 31.0.

| | pod (x, y) | net | HAT x | HAT hole |
|---|---|---|---|---|
| J1.1 | (4.00, 18.10) | +5V | 19.00 | J103.1 5 V |
| J1.2 | (6.54, 18.10) | GND | 21.54 | J103.2 GND |
| J2.1 | (23.00, 18.90) | 0V (CAB) | 38.00 | J102.4 CAB |
| J2.2 | (25.00, 18.90) | −V_OUT | 40.00 | J102.3 −V |
| J2.3 | (27.00, 18.90) | 0V | 42.00 | J102.2 0V |
| J2.4 | (29.00, 18.90) | +V_OUT | 44.00 | J102.1 +V |

Same nets on the same HAT holes as rev A facing north; J1.1 → J2.1 = 19.00 mm, J1.1 → J2.4 = 25.00 mm (checked by
`tools/check_isolation.py`, pin by pin with its net).  Both headers are rotated 270° (pins toward the bottom edge).  A
right-angle header on the front with its pins pointing down numbers its pins westward, which would have reversed both
headers on the HAT; `tools/make_footprints.py` therefore mirrors the two header footprints along their row (pad 1 at
the far end, pad N at the origin; the header is symmetric, so pads, body and 3D model land in the same places) and the
schematic keeps its pin → net table.  J2's pads are 3.6 mm above the edge (its 2.0 mm header has 4.2 mm tails: 3.6 mm
reach below the edge → ≈ 3 mm into the HAT, 1.5 mm out of its underside), J1's 4.4 mm (6 mm tails → ≈ 5 mm into the
HAT: trim after soldering) — as in rev A.

**Depth (HAT y).**  KiCad's models of the two headers put the horizontal pin 1.27 mm (2.54 mm header) and 1.00 mm (2.0 mm
header) in front of the board, so with both pin rows in the HAT's holes at y 39.0 the pod's front face is at HAT y
37.73 (J1) – 38.00 (J2), nominally 37.87 with each pin 0.13 mm off its hole centre (taken up by the hole slack / pin
flex; J102's holes are 0.75–0.8 mm for 0.5 mm square pins, so fit J2 first).  The board sits **north** of its pins.

| | value |
|---|---|
| pod height | 22.5 mm (bottom edge z 0.5, top edge z 23.0) |
| board | 1.6 mm; back face at HAT y 36.13–36.40 (nominal 36.27) |
| back → bonnet PCB edge (y 31.0) | **5.1–5.4 mm** (and the bonnet is at z 9–10.6) |
| front → BNC bodies (y 43.1) | 5.1–5.4 mm; below PS1 nothing stands more than 2.54 mm out of the face (J1's body; J2's 2.0, 0805s ≈ 1.3) |
| PS1 pin row | pod y 1.3, z 21.7 |
| PS1 body (6.00 mm along the pod: 0.9 mm above / 5.1 mm below the pin row) | pod y 0.4–6.4, **z 16.6–22.6** (0.4 mm inside the top edge) |
| PS1 body → BNC body tops (15.6 mm) | **1.0 mm** |
| PS1 body depth (10.16 mm out of the face) | HAT y ≈ 37.9 → 48.0, i.e. ≈ 4.9 mm over the BNC bodies (J6 and the west end of J7; PS1 covers HAT x 16.4–36.0) |

PS1's body is the only thing south of y 40.3 and it is 1.0 mm above the BNC bodies; nothing on the pod reaches north of
its back except the header tails and solder (≈ 3 mm, at z 4–5, under the bonnet's height).  The 1.6 mm board needs no
clipped tails and no low fillets any more (rev A's 1.2 mm board and those rules existed only for its 0.66 mm back
clearance to the BNC bodies); the 2.0 mm header's 1.5 mm protrusion under the HAT is unchanged.

**Layout.**  PS1 at (3.6, 1.3) rot 0 along the top edge: pins 1 / 2 (+Vin, GND) at x 3.6 / 6.14 on the 5 V side, pins
4 / 5 / 6 (−Vo, 0V, +Vo) at x 11.22 / 13.76 / 16.3 on the isolated side, body below the pin row (pod y 0.4–6.4, marked
face down toward the HAT).  5 V side (x < 7.43): +5V and GND straight down x 3.6 / 6.14 to J1, C104 (0603) across them
at y 7.6.  Isolated side, all below / beside PS1: negative block — L102 under PS1.4 and C106 under PS1.5 (y 8.6), the
−V_F bus along y 10.6, R112 and C108 below it at x 13.9, Q102 (C on the bus) at (16.7, 11.5); positive block beside
PS1's body (x 21.8–30.7, y 0.4–9.4) — L101 at the top edge fed along y 1.3 under the body, Q101, C105, R111, C107.  Front
0V from PS1.5 straight down to C106 and along y 4.0 under the body to C105 / C107 and on down x 27 to J2.3, so both
filter ripple loops (PS1.4 / 6 → L → C → PS1.5) are short; C108's 0V goes to J2.1 along y 17.0; −V_OUT from Q102 down
x 17.65 and along y 15.8 to J2.2; +V_OUT down the east edge (x 30.3) to J2.4.  Back: PS1.5 → TP2 → J2.1 (joins the two
front 0V pieces), the CAB strap J2.1 → J2.3 below J2.2, TP3 / TP1 straight above J2.2 / J2.4.  No vias (PS1's and J2's
THT pads are the layer changes).  Silk: pin names at both headers, "ISOLATED", "5V SIDE" (front); "DC-DC POD / 5V ->
±15V rev A" and the test-point names (back).  Corner radius 1.0 mm (PS1's pin-1 silk mark sits at x 0.8 next to the
top-west corner).

## Isolation

`hat_region` (x ≤ 7.43, top to bottom) and `iso_region` (x ≥ 9.93 for y ≤ 19.5, plus x ≥ 21.5 below) are rule areas
that keep nothing out by themselves; the `barrier` rule area (no tracks, vias or pours on both layers; drawn on
User.Comments) is the rest: the 2.5 mm strip x 7.43–9.93 from the top edge to the bottom edge (between PS1's pins 2 and
4, whose pads are 3.48 mm apart, and 0.04 mm east of J1.2's pad) plus the strip x 9.93–21.5 along the bottom edge
(y > 19.5, i.e. < 3.5 mm above the HAT), so the pod's isolated copper near the HAT stays over the HAT's own isolated
side.  `DCDCPod.kicad_dru` (as the StimHAT's): copper of a net outside class `Iso` may not intersect `iso_region`, `Iso`
copper may not intersect `hat_region`, and the two classes must be 2.5 mm apart (`isolation_gap`); `tht_connectors`
asks 0.3 mm around the header / SIP pads.  The 5 V side is J1, C104 and PS1's pins 1 / 2 only.  On the HAT, the pod's
isolated copper within 3.5 mm of the bottom edge is at HAT x ≥ 37.3 (J2.1's pad) and its 5 V copper at x ≤ 22.4 (J1.2's
pad), as in rev A, i.e. over the HAT's own regions (HAT barrier x 34–36.5); isolated copper higher up (z ≥ 3.5) may be
over the HAT's 5 V side (HAT x 24.9–36.5): ≥ 2.5 mm above the band's ≤ 1 mm parts.  The pod's own vertical gap is at
HAT x 22.4–24.9, no longer over the HAT's barrier strip.

## Checks (2026-10-30, after turning the pod around)

- `kicad-cli sch erc --severity-all`: 0 errors, 0 warnings (schematic unchanged).  `tools/netcheck.py`: CONNECTIVITY OK
  (11 nets).
- `kicad-cli pcb drc --severity-all` (via `tools/drc_summary.py --all`, project rules + `DCDCPod.kicad_dru`): **0 errors,
  0 warnings, 0 unconnected**.
- `tools/check_isolation.py`: smallest isolated ↔ 5 V-side copper distance by shape **3.481 mm** (PS1.4 vs PS1.2); every
  copper item inside its region, none in the barrier; a 0V track dropped into the 5 V region of a copy (at (1, 12))
  fails DRC with `iso_copper_in_hat_region` and `isolation_gap` (the rule file is live); all 17 footprint paths equal
  their symbols' UUIDs in the netlist; every header pin on its HAT x (pod x + 15) with its net, pin spacing 19.00 /
  25.00 mm, rows collinear.
- `tools/make_fab.py`: 11 placements, 6 BOM lines; J1, J2, PS1 hand-fitted, TP1–TP3 bare pads.

## Open points / to verify before ordering

1. **PS1 body side.**  The footprint is the StimHAT's `DCDC_SIP6_A0515S_BodyN` (body 0.9 mm behind / 5.1 mm in front of
   the pin row, pin 1 left in the marked-face view), still "pending the user's check on a physical module".  On the pod
   the body is drawn **below** the pin row (toward the HAT, marked face down).  If the real module's body lies on the
   other side of its pins, the body moves up 4.2 mm, to z 20.8–26.8, and sticks out 3.8 mm above the top edge: the
   BNC margin only grows, but the module then overhangs the board — check with the module in hand (looking at the
   pod's front with pin 1 on the left, the marked face must face down) and decide whether that overhang is
   acceptable or the module goes rot 180 on a re-placed board.  The 1.0 mm margin to the BNC tops also has to hold the
   module's 6.0 mm tolerance and how flush it sits on the face.
2. Confirm JLC rotations of the SOT-23s and 0805s in the DFM preview.
3. The HAT's J102 holes are 0.75–0.8 mm for 0.5 mm square pins (0.71 mm diagonal): a snug fit, which is also what holds
   the pod upright.  Fit J2 first, then J1, solder on the HAT's underside.
4. A BNC plug's bayonet sleeve sits beyond the HAT's south edge (y > 57); PS1's body ends at y ≈ 48, so it does not
   obstruct mating, but fingers turning the bayonet are close to it.
