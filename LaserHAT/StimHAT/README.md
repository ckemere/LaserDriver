# StimHAT — the LaserHAT Rev 2 core and the e-stim module's stimulator on one Raspberry Pi HAT (rev A, 2026-10-29)

One 65 × 57 mm HAT (plus a 10 × 7.5 mm tab on the south-east) carries the Rev 2 HAT core — MSPM0G1507 (the G3507 minus CAN-FD, same pinout), CH340N USB-UART,
USB-C power path, HAT ID EEPROM, BNC trigger in / stim out, buttons and LEDs — and the kbest constant-current
stimulator that was the plug-in e-stim module, isolated from the Pi side by an ISO7741F and an ISO1640 and powered
by the battery pack (J102, JST-PH) or by a plug-in DC-DC pod (A0515S + LC filter + capacitance multipliers on its own
board, 2026-10-29) that plugs into J102's holes and takes 5 V from J103.  The
Adafruit 4567 OLED bonnet stacks on the Pi header above it as before; a 0.91" 128 × 32 I2C OLED module can be fitted
in an unpopulated right-angle socket instead.  4-layer, JLC economic assembly (top side only).

The design discussion that led here is in `../claude_memory/stim-hat-plan.md`; the panel-1g floorplan is what the
board follows.

## Files

`gen_schematic.py` + `sch_parts.py` + `sch_symbols.py` (+ `sch_engine.py`) generate `StimHAT.kicad_sch` with
deterministic UUIDs; `tools/netcheck.py` proves the drawing's connectivity equals `sch_parts.PARTS`; `tools/make_bom.py`
writes `bom_StimHAT.csv`; `tools/make_footprints.py` writes `stimhat.pretty/` (the MSPM0's VQFN-32 copied from the HAT
board and the ALPS SKRHADE010 joystick).  Board: `tools/board_init.py` (once), `tools/project_settings.py` (net classes
and constraints in the `.kicad_pro`), `tools/place.py` (outline, barrier rule areas, placement, silk; idempotent),
`tools/autoroute.py` (Freerouting headless), `tools/fresh_uuids.py` (after any `pcb_sync.py`: copied footprints share
their library UUIDs and KiCad's DRC then confuses them), `tools/drc_summary.py`, `tools/stamp_fields.py` (LCSC codes
onto the footprints), `tools/make_fab.py` → `../fab/StimHAT/`.  `StimHAT.kicad_dru` holds the isolation-barrier rule.

## What is on it

| Block | Parts | Notes |
|---|---|---|
| Pi header | J1 Samtec HLE-120-02 SMD socket with pass-through holes (hand-fitted) | as the Rev 2 HAT; a Pi fitted with an extended-pin header lets the bonnet stack above |
| USB-C | J5 GT-USB-7010ASV, R8 / R10 5.1k CC, Q5 AP30P30Q VBUS switch + R26 100k + SW10 MSK12C02, Q3 AP30P30Q + Q4 DMMT5401 + R21 / R22 ideal diode into +5V, D5 (white) + R13 | USB power only when SW10 enables it; the Pi's 5 V and the USB 5 V never fight |
| 3.3 V | U4 MCP1700-3.3 (+3V3: CH340N, U5 input), U5 AP2171W (MSPM0_3V3, enabled by Pi GPIO10 through R7), C1 / C2 / C6 / C12 / C13 / C16, JP5 | JP5 feeds +3V3 onto the Pi's 3.3 V pins for stand-alone use (open it with a Pi) |
| ID EEPROM | U1 M24C32, JP1 (WP), R1 / R2 3.9k DNP | HAT spec |
| MCU | U7 MSPM0G1507SRHBR (VQFN-32; the G3507 without CAN-FD, pin-compatible, better LCSC stock), R4 100k 0.1 % (ROSC), C4 470n (VCORE), R3 4.7k + C3 10n + JP4 (reset), SW6 TS-1088 (BSL, active high), D7 + R15 (MCU LED) | pin map below |
| USB-UART | U6 CH340N | `MCU_UART_TX/RX`; RTS can reset the MCU through JP4 |
| Controls | SW7 ALPS SKRHADE010 five-way joystick (mounted at 135°), SW9 TS-1088 FIRE | replaces the thumbwheel and the BACK button |
| BNC | J6 TRIGGER IN → R23 1k / R24 100k → U8A (SN74LVC2G17) → PA21; PA17 → U8B → R25 33 → J7 STIM OUT, D9 + R18 STIM LED | as the Rev 2 HAT |
| Display | J10 PinSocket 1 × 4 vertical, unpopulated (GND, 3.3 V, SCL, SDA) | for a 0.91" 128 × 32 SSD1306 module (LCSC C5248081) standing up along the header at the strip's west end, facing south, instead of the bonnet |
| Isolation | U101 ISO7741F (EN, CATH, RELEASE in; FAULT_n back; fail-safe low), U109 ISO1640 (I2C), R101–R103 10k pull-downs, R107 / R108 2.2k and R109 / R110 4.7k I2C pull-ups, C101–C103, C124 | the only parts whose pads lie on both sides of the barrier, with PS1 |
| Isolated supply | J102 B4B-PH-K-S from the battery pack (+V, 0V, −V, CAB = 0V) or the DC-DC pod's 2.0 mm pins in its holes; J103 1 × 2 header (5 V, GND, unpopulated) feeds the pod; C109 / C110 10 µF, D103 / D104 BZT52C20S clamps, U104 TLV76050 (+5V_ISO), R113 4.7k + D102 BZT52C4V3S (−4.3 V) | the A0515S, L101 / L102 + C105 / C106 and the Q101 / Q102 capacitance multipliers moved to the pod (see below) |
| Set-point | U105 DAC60501 (I2C 0x48), C114 / C115, U106B OPA2192 inverter (R105 / R106 10.0k 0.1 %), U107 CD74HC4053 on +5 / −4.3 V | switch 1 (CATH) picks ±VSET, switch 2 (EN) gates it, switch 3 inverts RELEASE for the SHORT switch |
| Output stage | U106A OPA2192, R114 1k, C120 100p, R115 47, R116 2.49k 0.1 %, C121 1 µF, J101 electrode header (E1, E2), TP101 (ISENSE) / TP102 (GND_ISO) test points | 502 µA full scale, 0.123 µA / LSB |
| SHORT | U108 DG418 (normally open, on while SHORT_IN is high = RELEASE low) | electrode shorted whenever RELEASE is low, including HAT-side power-down |
| Fault detector | U110 TLV1702 window on E1 (R117 10k / R118 215k / R119 10k taps), R120 10k, R121 4.7k, D101 BAT54WS, C122 | FAULT_n low past the trip point, with +5V_ISO down, or with a rail missing |
| Mechanical | MH1–MH4 M2.5 (HAT pattern), Pi 4 PoE / Pi 5 fan notch | MH4 lies in isolated copper: use a nylon standoff there |

## MCU pin map

See "MCU pin map (StimHAT, 2026-10-29)" below: it is the table the netlist follows (the Rev 2 HAT's map in `../CLAUDE.md`
no longer applies to this board).  Pi side for this board: `LASERHAT_NRST_PIN=9 LASERHAT_POWER_PIN=10 LASERHAT_TRIGGER_PIN=18`,
`laserhat-brokerd --gpio-pin 18`; no SPI0 / I2S / PWM-on-GPIO18 overlays.  The bonnet's buttons use GPIO 4, 5, 6, 17, 22, 23, 27,
none of which the HAT touches.

## Board

65 × 57 mm with the HAT outline (3 mm radii, the Pi 4 PoE / Pi 5 fan notch at x 59–65, y 8–16.5; the earlier tab is
gone, the pod took its place).  Top strip (y < 17.5) and west half: the core, all under the bonnet (9 mm
up, parts under 7 mm); the OLED socket J10 (vertical 1 × 4, unpopulated) right under the header at the strip's west
end, pins GND / 3V3 / SCL / SDA at x 11.75, y 11.88 / 14.42 / 16.96 / 19.5 — the 0.91" module comes with bare holes, so the header soldered to it decides how it
sits: straight pins stand it along the header, long edge horizontal; right-angle pins lay it flat over the strip with
its pin edge north (both outlines on User.Drawings; lying flat it covers SW6, the BSL button); JP1 moved to the strip's east end.  West edge, top
to bottom: SW10, J5, the three LEDs, FIRE, the joystick in the south-west corner.  Two right-angle BNCs mid-south
(bodies y 43–57, barrels past the edge; `stimhat:BNC_Amphenol_031-5540_RA`, right-angle only — the Rev 2 HAT's dual
footprint with the vertical 031-5539's diagonal post pad and body removed).  The band the vertical BNC bodies would have taken (y 36.5–43, outside the bonnet) carries the supply
connectors: J102 (`stimhat:JST_PH_B4B-PH-K_NoCrtYd`, the library footprint without courtyard and silk, 0.8 mm holes) at (44, 39.0)
rot 180 in an isolated pocket, pads +V / 0V / −V / CAB at x 44 / 42 / 40 / 38 (label on the back), and J103 (1 × 2
2.54 mm, pin 1 = 5 V west) at (19 / 21.54, 39.0) on the HAT side (the user moved both rows from y 40.1 to 39.0 on 2026-10-29;
see "Pre-order audit round 2" for what that means for the pod).  The DC-DC pod stands in the band between them
(board outline and PS1 overhang on User.Drawings; parts face south since 2026-10-30, PS1 above the BNC bodies; the pod's own isolation gap runs vertically at HAT x 22.4–24.9 and its copper within 3.5 mm of the HAT keeps to the HAT's barrier strip at x 34–36.5).  Isolated stimulator: block A (x 36.5–65, y 20–35, under the bonnet's
east end: isolators, DAC, inverter, 4053, output stage, SHORT, fault detector), the pocket (y 35–41.2, J102), strip B
(x 47.7–65, y 41.2–57: LDO, −4.3 V rail, decoupling, clamps) and the tab (J101 vertical electrode header,
pin 1 = E1 west).  Nothing hangs below the HAT.  Barrier (reworked 2026-10-29 night so the router draws no 2.5 mm halos): the 2.5 mm copper-free rule areas on all
copper layers (x 34–36.5 from y 17.5 to 43.7 west of block A and the pocket; y 41.2–43.7 between J102's pads and
J7's tails; x 45.2–47.7 east of J7; x 43–47.7 below J7's east post, y 51.3–57, so the tab's corner stays 2.5 mm
from HAT copper; y 17.5–20 north of block A; drawn on User.Comments) are exactly the gap between two named regions,
`hat_region` and `isolated_region` (rule areas that keep nothing out by themselves), and `StimHAT.kicad_dru` disallows
HAT-side copper (tracks, vias, pads, zones of any net class but Isolated / IsolatedPower / Rails) inside
`isolated_region` and isolated copper inside `hat_region`.  The distance then follows from the geometry: any copper of
one side lies in its region, the regions are ≥ 2.5 mm apart everywhere (checked at every corner), and the strips are
keep-outs on all four layers.  Pads of the straddling parts U101 / U109 / PS1 / J7 lie in the strips, where they are
allowed; their own creepage is the footprint's.  `tht_connectors` (0.3 mm around the hand-soldered pads of J101, J102
and PS1) stays a clearance rule.  Net classes:
Power and IsolatedPower 0.3 mm, Fine (USB), Default and Isolated 0.2 mm; board minimums 0.15 / 0.15, vias 0.6 / 0.3.
Standoff keep-outs r 3.25 at all four holes.  User.1 ("Bonnet"): the Adafruit 4567 bonnet from its EagleCAD board — outline (65 × 30.66, y 0.34–31.0, its header rows on J1's), holes, stacking socket, OLED module and active area, joystick, buttons.  User.Drawings: the standing 0.91" module, the notch note.

Routing (rev A, 2026-10-29): `tools/autoroute.py --passes 500` = rip → `tools/fanout.py` (locked dog-bone stub + via on
every netted pin of U7 and U101, alternately 0.45 / 0.95 mm out so the vias stagger, plus four GND thermal vias in U7's
exposed pad: without them Freerouting never finished the MCU's escape) → `tools/preroute.py` (hand-planned, locked:
SDA_H from U7.21 down between the south-row vias, east under the MCU and north along x 28.3 to R107; C1 into pin 4's
via; and the original tab's feeds — `preroute.py` still describes rev A's first tab, see the git history; the router
solved none of these reliably) → Freerouting → import → `tools/fixups.py drop-dangling-vias` and `--trim-stubs` remove the fan-out
vias the router did not use (locked pre-routes are never trimmed).  Freerouting stops after ~300 passes with 2–9
connections open and never the same ones; after the review's placement changes the last 2–3 (and the DRC fixes above)
were finished by hand with `tools/fixups.py` (`track`, `via`, `move-via`, `drop-seg`, later `rip-region`, `swap-fp`,
`maze`): the +5V trunk runs from J1.4 on the back along x 7.2, down the west edge at x 1.2 to the power LED, along the
south edge on the back (y 52.5) to x 24, then up the front under J6's body to C104 and on the back to PS1 pin 1; PS1
pin 2 (GND) reaches J7's ground tail on the back along x 33.3 / y 43.05, the BNC ground group (tails and posts) hangs
on C104 and R24; the BNC-out line from R25 dives under PS1's input end (two vias) and runs along y 43.3 to J7; +V_RAW
leaves pin 6 eastward on the front, −V_RAW leaves pin 4 on the back above pins 5–6 (`maze` found the rest, through
the gap between L101 and C105); GND_ISO of the pocket joins U108's; on the tab +V_RAW / −V_RAW come down the back
(x 53.55 / 54.2), GND_ISO goes round MH4 on the back (y 56.6) to the east edge and J102's pins 4 / 2, E1_OUT and ISENSE
come down the front west of J102 to J101.  `tools/preroute.py` holds the pre-routes a fresh run starts from; the hand
finishing is not scripted, so a full re-route restarts from the placement.  Result: 0 DRC errors, 0 unconnected
(isolation rule live), ERC 0 / 0.  The one remaining DRC warning is `lib_footprint_mismatch` on PS1 (stamped fields).
`fab/StimHAT/StimHAT_top.png` / `_bottom.png` are the renders.

**Four layers (2026-10-29 night):** JLC 4-layer 1.6 mm.  In1 carries two ground planes made by `tools/place.py`
(`plane()`): HAT GND west / north of the barrier (x < 34, y < 17.5, and the BNC J7 area down to y 43.6) and GND_ISO
under block A, the pocket, strip B and the tab; the rule areas (now on all four copper layers) keep the 2.5 mm barrier
and the standoff circles copper-free, `../tools/fill_zones.py` refills them (islands always removed), and
`j102_one_spoke` in the `.kicad_dru` lets J102's two 0V pads connect to the plane with a single thermal spoke (their
neighbours leave no room for two).  In2 is empty: power is routed there by hand.  **All copper was ripped for the
hand routing (300 open connections, DRC 0 errors / 0 warnings with the planes filled).**  `make_fab.py` exports In1 /
In2 gerbers.

**After the user's re-placement and isolated-block routing (2026-10-29, commits 03d3c56 / 912a3a7):** the tab is
gone (J101 sits in strip B), the BNCs moved east (J6 x 24.92, J7 x 40.92) so the strip east of J7 is now x 47.7–50.2
and the pocket's south strip y 41.2–43.7; the north strip starts at y 17.4; the isolated planes are notched under
U109 (its HAT-side pads end at y 18.0).  `tools/place.py`'s table was synced from the board (a rerun moves nothing).
Pours: GND / GND_ISO on In1 (planes), F and B (0.25 mm clearance, single thermal spokes allowed by
`outer_pours_one_spoke`); In2 is a plain routing layer for the power nets (the islands were dropped at the user's request).  The isolated
rails are a hand-laid 0.3 mm grid: +5V_ISO on In2 (row y 22.6 under the DAC / isolators, column x 38.52 past U101,
row y 32.0 to the LDO side), +V_STIM on In2 (trunk y 39.5 from J102.1 to the east edge, column x 58.63, feed x 56.95
from C116), −V_STIM on the back (row y 37.4 from J102.3 to x 59.85, column up to the output stage), −5V_ISO on the
back; the fan-out vias on the pads are the only vias.  The isolated block's power is routed: dog-bone vias from every +5V_ISO / +V_STIM pad
into its island (`/home/.../tmp/powerfan.py`-style script, 22 vias), −V_STIM / −5V_ISO and the stragglers by
`tools/maze_nets.py` (the maze router restricted to named nets) and by hand; `tools/stitch.py` drops a via into every
outer-pour piece that has none (rerun it after routing: `fill_zones`, `stitch.py --apply`, `fill_zones`).  Result:
DRC 0 errors, 123 open connections, all on the HAT side.

**Rev A round 6 (2026-10-29, placement only, routing in progress by hand):** J102 beside PS1, J101 alone on a 10 mm
tab, J10 a vertical socket at the strip's west end (JP1 → east end at (50, 10), C12 → (19.7, 12.3), C6 → (26.5, 10.6)
to clear it), MH4 keep-out r 3.25, PS1's silk outline and 3D model.  The copper these moves invalidated was ripped:
the open connections (DRC "unconnected") are J10's four pins, JP1 (both pins), C6 (both pads), C12's GND, MCU_PWR_EN
from J1 to its via at (23.4, 11.85), GND of J10 / C6 / U5.2 / the J1.39 area, +3V3_PI across the socket, J102's four
pads to PS1's pins (stubs), E1_OUT / ISENSE to J101, and the BNC-area GND stubs.  The fab outputs are from the
previous commit and are stale until the board is routed again.

**USB-C corner (2026-10-29 evening, after the user's isolated-block clean-up):** the user's routing closed the earlier
opens (U107.6 / C118.2, ISENSE, SHORT_IN, OA_IN); C118's new spot (53.5, 28.2) was synced into `place.py`, U105.1's
+5V_ISO link re-added as a 0.3 mm stub on the back, and two 0.25 mm +V_STIM leftovers of the old MST stubs (plus
their via at (46.95, 36.5)) deleted.  The USB-C power / switch / CH340 parts were then regrouped by `place.py` in the
west corner and routed by hand (`/home/.../tmp/route_corner.py`, 0.5 mm power, 0.2 mm signals): Q5 (VBUS switch,
(16.5, 19.9)), Q3 (ideal-diode P-FET, rot 180 at (16.5, 15.5)) and Q4 (DMMT5401 at (16.8, 10.5)) stand in one column
east of J10 - VBUS leaves J5's upper pads along y 21.6 straight into Q5's source pins (the lower pair is tied through
an In2 link at x 9.25), Q5's drain pins bridge Q3's drain pins across a 0.5 mm gap, +5V leaves Q3's north pins along
y 13.97, up x 19.5 to C12 (20.6, 11.3) / Q4.5 and along y 14.5 into U4.2; IDEAL_G runs Q4.4 -> Q3's gate -> R22
(14.1, 12.9), IDEAL_B down Q4's west column to R21 (15.66, 7.4); the VBUS_SW sense to Q4.6 and PWR_EN (Q5 gate ->
In2 row y 20.75 -> x 9.7 -> y 13.75 -> SW10.2) are on In2, R26 (14.2, 20.8) sits on the VBUS row with its PWR_EN
pad reached by a via.  CC: R8 (10.3, 22.75) / R10 (10.1, 27.0) straight off the pads.  USB D+/D-: the D- pair is
joined by a 0.2 mm bar at x 8.95 past the pad ends, the D+ pair through two vias under the jack body (In2, x 6.6),
then D+ runs down x 10.8 into U6.1 and D- down x 12.1 (between U6's pin columns) into U6.2.  C17 (16.7, 31.5) and
JP4 (19.3, 31.3) moved east of U6 so the corridor from U7.14/15 (17.55, 26.75 / 27.25) to U6.7/6 (12.77 / 14.04,
30.0) is free for the UART lines; R19 / R20 are north of J10, R4 / C1 north of U7.  Result: DRC 0 errors / 0 warnings,
96 open connections (none of the USB / switch / ideal-diode nets; U7's thermal pad still needs its ground via).

**Semi-final routing clean-up (2026-10-29 night, after the user's commit e4dab1b closed every connection):** the joystick fan
was re-laid as six 45° diagonals on a 1.0 mm x+y pitch (0.71 mm centre spacing, 0.5 mm copper gap against the 0.15 mm rule):
BUTTON4 one straight line from a back-side via at (17.5, 28.82) to pad 6, BUTTON1 next with a 1 mm jog at x 12 to clear pad 5,
then BUTTON6 / 2 / 3 / 5 from U7's south pins through rows 0.6 mm apart (y 29.25 / 29.85 / 30.45 / 31.05) and verticals 0.7 mm
apart (x 13.0 / 13.7 / 14.4, 15.4 for FIRE) into the pads the user had chosen.  MCU_STIM_OUT's via moved out of pin 20's
column to (23.0, 31.8) and BSL_INVOKE runs straight down x 24 into SW6; the GND stitch via that clashed with it was replaced
by one at (26.8, 32.5) feeding U8.2.  3D models: `stimhat.3dshapes/SW_ALPS_SKRHADE010.wrl` (generated) on the joystick, TI's
RHB VQFN-32 from the KiCad library on U7, and Q3 / Q5 / SW10 point at `../Footprints.3dshapes` (the shared models next to the
HAT project; `${KIPRJMOD}` is this directory).  The "USB" silk moved to (9.6, 24.6), out of U6's outline.  Result: DRC 0
errors / 0 warnings, 0 open connections; every outer-pour piece is stitched (the one GND_ISO sliver at (50.6, 25.4) hangs on
a pad).  The user also added TP102 (GND_ISO) and routed the LED from pin 9 (PA5), both now in the generators.

**Owl and labels (2026-10-29/30):** the lab's owl (`../Footprints.pretty/OwlLogo_Laser_14mm`, 17 x 14 mm, exposed-copper
laser eyes and beams) sits on U101 looking at U7.  `tools/owl_logo.py` derives `stimhat:OwlLogo_Eyes_14mm_R` at full size, mirrored so the
owl looks right (MIRROR = True negates every x): the eye copper is kept (two pads on GND, exposed), the copper beams become
silk lines, no courtyard; the script keeps G1 where it
finds it on the board (the user places the owl by hand) and only uses its POS for a first placement.  `--neuron X Y` (default
48.0 16.2, the centre of the empty pour square above the "ISOLATED" label) moves the neuron drawing to that board position, replaces
the four library beams by two converging silk lines per eye (from the socket edge to the soma) and turns each eye's copper square
to its beam angle (the sockets are round, 2.5 mm across, so the 1.64 mm square fits at any angle).  Re-run it after moving G1.  Rules for that hand
placement: the eyes are at (+0.8, -4.3) and (-2.7, -4.3) from the centre (mirrored), 1.64 mm square, so both must end west of x 33.7 (the
barrier strip starts at x 34 and the strip keep-outs deliberately do not forbid pads, because the isolators' own pads straddle
them - DRC will not catch an eye in the strip, and a custom-shaped pad's outline reaching into the isolated region is only
caught by its 0.5 mm anchor), and they must clear the +3V3 row at y 14 and the SCL_H / SDA_H diagonals by 0.2 mm; the neuron
at the beams' end may lie on passives (silk-over-pad warnings the user accepts).  At 70 % the owl fits the pocket north of
U101 without touching C101 (centre (29.6, 18.05)); at 75 % its belly reaches C101's pads, and C101 cannot move beside U101's
pin 1 without colliding with the RELEASE_H / EN_H routing.  Front-silk "TRIG IN" / "STIM OUT" stand on the jacks' outer sides
at x 16.3 / 49.4 (the two bodies are 0.4 mm apart, so nothing fits between them); the back-silk pair stays centred under
the jacks.

## Pre-order audit round 1 (2026-10-30)

Four independent read-only reviews (schematic logic, part / footprint / pinout vs datasheets, layout and fabrication, LCSC
stock / JLC class / part-number sync) ran against commit 4f280fb.  Verified correct: every IC / transistor / diode pinout and
every supply pin against its datasheet (ISO7741F and ISO1640 orientation included), the pin map vs the MSPM0 table, the
USB-C ideal-diode polarity, all 50 LCSC codes vs the stated value / package / tolerance / voltage, the part-number and DNP
sync between `sch_parts.py`, the schematic and the board, the 2.5 mm barrier everywhere except the two places below, the pod
mating geometry, the HAT mechanical pattern (identical to the fabricated Rev 2 HAT).  Fixed:

* **SW7 footprint (blocker):** the ALPS land drawing puts the three pads of a column at 0 / ±1.425 mm (the 3.85 mm span of
  three 1.0 mm pads) and the guide bosses 3.8 mm apart; `make_footprints.py` had ±1.85 and 2.15 - the bosses would have sat
  on copper and the switch off its paste.  Regenerated and swapped on the board; the fan's last segments follow the pads;
  pad 5 (common) got a via at (4.9, 39.95).
* **U8 (blocker, stock):** 74LVC2G17GW,125 (C80500) is out of stock at LCSC and JLC -> TI SN74LVC2G17DCKR (C50714), same SC-70-6
  pads and pinout.  `../tools/lcsc_parts.py` (the HAT's table) carries the same change.
* **Barrier (major):** an isolated SCL track ran at y 20.4 under U109, 2.30 mm from U109's HAT-side pads -> now a row at y 20.68
  into pin 6 from above, and the notch under U109 is structural: keep-out strip (38.2, 20.0)-(45.8, 20.55) and the isolated
  region / pours / plane start at y 20.55 there (C124 moved to (45.5, 21.8) to make room).  J7's tail pads were 2.42 mm from the
  isolated pours' south edge -> the south strip is now y 41.1-43.6 (pours, plane, both regions moved 0.1 mm).
* **C17** (the CH340N's bypass) had drifted to U7's north side -> back at U6 (14.9, 29.2), 3V3 pad on the via that feeds U6.5,
  GND pad on a new via.  **C127** 100 nF added at U107's VCC pin 16 (45.6, 31.6); C118 stays at pin 5 (the +5V_ISO analog input).
* **R3** 10 k -> 4.7 k (NRST ≈ 3.0 V against the Pi's boot-time pull-down on GPIO9, VIH 2.31 V), **C12** 100 nF -> 1 µF (the MCP1700's
  input capacitor); the net `U5B_IN` (the e-stim module's numbering) is `U106B_IN`.
* **J102** has front-silk "+V" / "-V" marks under its pins 1 / 3 (a reversed battery cable would put +V on CAB) and 0.8 mm holes
  for the pod's 0.5 mm square pins (JST PH allows 0.7-0.8).
* **LCSC:** fee-free equivalents for D101 (C7502694), D103 / D104 (C19077451), R115 (C25118), C121 (C28323 1 µF 50 V X7R 0805),
  C111 / C112 (C5199872 1 µF 50 V X7R 0603), R4 (C852472, same 0.1 % 25 ppm spec, a fraction of the price).  `stamp_fields.py`
  now clears a stale code on no-code parts (J1 carried a Harwin header code), keeps DNP parts out of the position files and
  skips board-only graphics (the owl G1 had stopped it).  BOM and fab outputs regenerated (the old ones still listed the G3507
  and the pod parts).  28 -> 23 Extended parts; U108 DG418 has 205 pcs at its only source - order soon.
* **+5V from the header:** the 0.3 mm In2 run between the header's hole rows is now 0.9 mm; the outer-layer segments stay 0.3 mm
  (widening them closed two ground-pour corridors).  The path is rated for the HAT and the pod (~0.3 A), not for back-powering a
  Pi from the USB-C port: keep SW10 off with a Pi fitted (unchanged policy).
* Stale texts (sheet notes, `sch_parts.py` docstring, this README's first pin table, `Firmware/board.h` spare-pin mask) follow the
  current pin map.

Reviewed and deliberately not changed: series resistors between U106B / VSET_P and the 74HC4053 inputs (the DAC60501**Z** powers
up at zero scale and the firmware writes GAIN before any code, spec §7, so VSET cannot exceed the HC4053's −4.3 V rail; the
pocket around U105 / U107 has no room for two more 0402s - a rev B item); a bulk capacitor on +5V (the Pi and the pod carry
the bulk; C12 1 µF meets the MCP1700 spec); a bypass of U8's own (C16 sits 2.6 mm from U8.5 on its VCC trace; the only free
spots collide with MCU_STIM_IN); U104's courtyard 0.15 mm under J102's plastic housing (J102 is fitted after SMT, its body is
0.3 mm from the SOT-23 leads); R118 215 k (the fault window is a design value); 0.8 mm silk labels; the Pi-side scripts'
defaults (Rev 2 HAT), which this board overrides through the LASERHAT_*_PIN variables.

## Pre-order audit round 2 (2026-10-30)

Four fresh agents (schematic, parts / footprints / pinouts, layout / fab, LCSC stock / sync) re-audited the design at
2422f0f.  No blocker; the reports are in the session's scratch directory (`audit2_*.md`).  Fixed:

* **Isolation barrier at U104** – its GND_ISO pad protruded 0.075 mm into the south keep-out strip (pads are allowed
  there), 2.44 mm from the HAT pours' corner at (47.7, 43.6).  The HAT polygons' corner east of x 46.5 now steps to
  y 43.7 (`tools/place.py`); the barrier measures ≥ 2.50 mm on every layer again (2.537 at U104.3).
* **U109.8 via** was inside the +5V_ISO pad (via-in-pad under paste): moved to (44.3, 23.3) with a short stub.
* **Via hole-to-hole** below JLC's 0.5 mm for different nets (the project rule is 0.25 mm, so DRC was silent): the
  I2C_SCL / I2C_SDA, BUTTON4 / LED_MCU, LED_MCU / PI_RXD and PI_RXD / PI_TRIGGER pairs beside U7 were spread to
  ≥ 0.55 mm.  Only J1's library NPTH pairs (0.395 mm, the Samtec footprint) remain.
* **Owl eye pads** had lost their GND net in round 1 (a netlist sync clears the nets of symbol-less footprints);
  `tools/stamp_fields.py` now re-assigns GND to G1's pads and the pipeline fills the zones after stamping.
* **R101–R103 100k → 10k**: the ISO7741's input leakage is 10 µA max, and 10 µA × 100k = 1.0 V is right at VIL
  (0.3 × 3.3 V).  These resistors are what hold EN / CATH / RELEASE low while the MCU is Hi-Z (NRST held low by the
  Pi, before gpio init, crashed firmware); 10k gives 0.1 V worst case for 0.33 mA per line when driven high.
* **C111 / C112** → C15849 (1 µF 50 V X5R 0603, Basic; C5199872 was Extended, not fee-free as round 1 claimed).
  Extended count 23.  Round 1's claim about D101 / D103 / D104 / R115 being fee-free holds (Preferred).
* `tools/make_footprints.py` attaches the 3D models of U7 and SW7 (regenerating in round 1 had dropped them);
  R113's code goes through the `L` table; stale U7 comment and six unused codes removed from `sch_parts.py`; README
  facts corrected (J102 / J103 rows at y 39.0, USB D+/D− lengths, U101.7 is EN1, the pod stands).

**Needs the user's decision before ordering – the DC-DC pod vs the OLED bonnet.**  The J102 / J103 rows were moved
from y 40.1 (the value the pod was designed for) to y 39.0 on 2026-10-29.  With the pins 1.0–1.3 mm in front of the
pod's board the pod's front face is at HAT y ≈ 40.0–40.3, and PS1's 10.16 mm body then reaches y ≈ 29.8–30.1 at
z 6.3–12.3 mm, i.e. ≈ 1 mm inside the bonnet's footprint (bonnet PCB edge y 31.0 at z 9–10.6).  At 40.1 the margin
was only 0.1–0.4 mm (the pod README's 0.2–0.4 is optimistic for a SIP body with ± 0.5 mm tolerance).  Options: rows
back to 40.1; rows at 40.5 with J6 / J7 0.5 mm further south (BNC bodies 0.5 mm further over the edge, pod back
0.5 mm from J7's body); or a shorter module on the pod.  `DCDCPod/README.md` and `DCDCPod/tools/place.py` must then
state the same row y.  Nothing on the StimHAT itself depends on the choice except the two rows and their routing.
**Resolved 2026-10-30 without moving the rows:** the pod was turned around (parts face south, PS1 along its top edge
over the BNC bodies, 1.0 mm above them; the back faces the bonnet 5 mm away) — see "The DC-DC pod" below and
`DCDCPod/README.md`.

Reviewed and deliberately not changed (round 2):

* **U8 input while the MCU is in reset** – PA21 is Hi-Z during NRST low, so the LVC Schmitt input floats for the
  ≈ 50 ms of a power cycle and chatter could reach the STIM OUT BNC.  A 100k pull-down on MCU_STIM_OUT would need a
  part there is no room for at U8; stim-out pulses during a reset are meaningless to a recording system anyway.
  Rev B item.
* **VSET_N vs the HC4053's VEE** stays a firmware guarantee (GAIN register written at init and after every fault).
  The hole: a +5V_ISO sag to 1.8–2.2 V leaves the DAC60501's registers undefined without a POR while the isolator
  still passes FAULT_n high.  Firmware: write GAIN before every code write, or read it back over the ISO1640.  Rev B:
  1–2.2k in series with VSET_N into U107.13.
* SW6 shorts PA18 to MSPM0_3V3 without a series resistor (as the Rev 2 HAT); Q4's Q1 sees 4.4–4.6 V emitter-base
  reverse bias in the normal Pi-powered state vs 5 V abs max (fine – do not lower R21); R118 215k (Extended, single
  use) kept over 220k Preferred (thresholds 2.2 % closer to the rails); J102's 1.2 × 1.75 pads with 0.8 mm holes
  leave a 0.2 mm ring (JLC minimum 0.13; optional 1.4 × 1.9); paste stays on the DNP R19 / R20 pads (hand fit later,
  JLC skips DNP parts); the owl's north beam crosses U109.1's mask opening (JLC clips silk on pads).
* Joystick direction mapping (a → A etc.) is a convention ALPS does not state: verify on the first board, remap in
  firmware if needed.  CPL rotations use the per-package offsets of the two assembled 2026-10-01 orders; confirm
  SW7, U105, U107 and U108 / U109 vs U6 in JLC's placement preview.
* U108 DG418 stock is 205 pcs at JLC and no other DG418 code has stock: order promptly or buy 20 at LCSC as spares.

## Pre-order audit round 3 (2026-10-30)

Three fresh agents (schematic, layout / fab, parts / stock / sync) re-audited 00d0f6b.  No blocker, no new major in
the schematic or the parts; everything of rounds 1–2 verified live.  Fixed:

* **Vias tangent to paste-covered pads** (the via-in-pad class of round 2, three more): C127.1's +5V_ISO via
  (hole 23 % inside the pad opening – a starved 0402 joint) moved to (45.14, 30.90); C112.1's via to (49.70, 38.56)
  and U108.4's to (60.63, 38.98), each with a 0.25 mm stub into the pad.  Hole-to-opening now 0.24 (C127.1),
  0.19 (C112.1) and 0.15 mm (U108.4 / C125.1, the via sits in the 0.6 mm gap between two same-net pads).
* **CPL rotation table** (`tools/ref/jlc_rotations.csv`, a copy of the Fabrication Toolkit's
  `transformations.csv`): the two `^VSSOP-10_-` rows were a typo that never matched, so U105 got no offset, and
  `^VSSOP-8_` had contradictory 180 / 270 rows with the first winning while the specific 3 × 3 mm row used a name
  KiCad does not (`3.0x3.0mm`).  The Toolkit itself has the same rows and the same first-match logic, so the
  2026-10-01 e-stim upload (VSSOP-8 +180, VSSOP-10 +0) inherited the accident – and that board's isolated side
  never ran (ISO1640 symbol swap), so no VSSOP placement was ever confirmed.  The table now gives every SO-family
  body (SOIC / SSOP / TSSOP / MSOP / VSSOP) the same +270: U105 90, U106 0, U110 270 in the CPL.  **JLC's
  orientation is per part, so the placement preview is a hard gate: check U105, U106, U110 first, then U101, U104, U107,
  U108, U109 vs U6 (JEITA SOIC gets 0), SW7, Q3 / Q5, D101–D104, D5 / D7 / D9, J5, SW10, and rotate in the preview as
  needed.**  (The EasyEDA / LCSC footprint drawings are not JLC's placement zero: the HAT-confirmed packages would
  need other offsets relative to them, so they cannot be used to pre-validate the table.)  `fab/README.md` corrected (the committed HAT / e-stim CPLs are raw KiCad exports; the uploads carried
  the Toolkit's offsets).
* Stale texts: README (2-layer, GPIO18 for MCU_PWR_EN, R3 10k, 45° joystick, U8 on PA26 / PA25, R107 / R108 4.7k,
  NRST pin 16, ADC channels) and the joystick symbol's pin names (now A/DOWN, B/LEFT, C/RIGHT, D/UP for the 135°
  mounting).

Noted, not changed: U7's exposed pad carries full paste over its two vias (same footprint as the assembled Rev 2 HAT);
the KiCad library 3D models of J5 and J1 are missing from this installation (cosmetic); the TLV76050 runs at
≈ 85–100 °C junction at a full pack (thermal shutdown 150 °C; rev B could add copper under U104); SW10's common
terminal is pad 2 per the drawing round 2 read (check PWR_EN ↔ GND continuity in the ON position on the first board);
firmware must never enable the MSPM0 pull-ups on PA23–PA25 while they are inputs (≈ 20k against the 10k pull-downs
would sit in the ISO7741's undefined band).

## Pre-order audit round 4 (2026-10-30, confirmation)

Two fresh agents (layout / fab, parts / sync / stock) re-checked 7da5960.  No blocker, no major, nothing new of
substance: the round-3 vias and stubs are in the gerbers (the shipped zip is byte-identical to a fresh export), the
barrier is 2.50 mm on all layers, 0 errors / 0 unconnected, CPL 95 = BOM 95.  Done in this round: U108.4's via
centred in the gap to C125.1 (x 60.63), README board paragraph brought up to date (no tab, J10 pin positions, the
pod stands).  Cosmetic track hygiene left for rev B: seven collinear overlapping same-net segments (+3V3 at
(24.95, 13.0), +5V_ISO at (37.85, 24.78) / (40.34, 23.75), +V_STIM at (56.56, 31.7), MSPM0_3V3 at (43.9, 17.0)) and a
dozen same-net 45° hairpins.

## Checks before fab

`python gen_schematic.py && python tools/netcheck.py && kicad-cli sch erc StimHAT.kicad_sch` (ERC 0 / 0),
`python tools/drc_summary.py` (0 errors, 0 unconnected), `../tools/path_check.py StimHAT.kicad_pcb StimHAT.kicad_sch`,
`../tools/sync_check.py StimHAT.kicad_pcb StimHAT.kicad_sch`, then `tools/stamp_fields.py`, `tools/make_bom.py` and `tools/make_fab.py`.
Hand-fitted: J1, J6, J7, J101, J102 (battery cable or the DC-DC pod), J103 (pod only), J10 (optional).  Not fitted: R19, R20
(the Pi has 1.8 k on GPIO 2/3; fit them only for stand-alone use with a J10 module that lacks its own pull-ups).
R1 / R2 (3.9 k on ID_SD / ID_SC) are fitted: the HAT design guide puts them on the HAT.

Second to fourth layout reviews (2026-10-29), applied: J101 became a **vertical** 1×2 header, pin 1 (square, west,
"E1") = E1, pin 2 = E2 return; the hand-soldered pads of J101, J102 and PS1 keep ≥ 0.3 mm from other copper
(`tht_connectors` rule in `StimHAT.kicad_dru`, proven live); the +5V_ISO feed above U109 moved to y 20.7 (barrier
2.55 mm, was exactly 2.50); J102's pins are labelled along the row; a "NYLON" marker sits above MH4; the stray "5V"
label went.  **PS1 moved (2026-10-29, after the fourth review)**: the reviews had it under a lengthened tab, where its
10 mm body hung over the Pi 4's AV jack and the HDMI1 cable and J101 collided with it; committing to the right-angle
BNCs freed the 6.7 mm band north of their bodies, which takes PS1 standing up with `stimhat:DCDC_SIP6_A0515S_BodyN`
(body south of the pin row, 0.9 / 5.1 mm from it per the Mornsun drawing, 1.6 mm pads so a track passes between pins
1 and 2), the tab shrank to 7.5 mm with J101 beside J102, and nothing hangs below the HAT.  "STIM OUT" / "TRIG IN" are
printed on both sides: the top labels sit between PS1's body and the BNCs and are hidden when PS1 is fitted.  Minors
from the fourth review that still apply: U101.7 is EN1 (tied high, no cap needed; C101 is at pin
1, 4.4 mm away), C116 sits at U110 rather than U106.8 — both are 100 nF-at-5 V class devices on short, quiet rails;
the +3V3 / MSPM0_3V3 / VBUS / ±V_STIM tracks run at 0.2–0.25 mm where their class says 0.3 (≤ 250 mA, fine); USB
D+/D− are 9.8 vs 8.0 mm long (full speed, irrelevant); re-check LCSC stock before ordering (10 codes
are not in the local catalog yet).  Noted, not changed: C114 (VREFIO)
is 6 mm from U105.10 with two vias (no room next to the pin; 1 µF on a buffered reference, fine); J10's and the BNC
ground legs' pads have tracks at the 0.15 mm class distance (J10 is unpopulated, the BNC legs are big pads — solder
them without flooding); the ± rail tracks run at 0.15 mm for ~4 mm on the back near (51–58, 34–38) (IPC-2221 B4);
FIRE / PWR / USB / DC-DC and the LED labels are 0.8 mm text; MH4: round nylon spacer / washer ≤ Ø 5.5 mm (copper at
2.9 mm from the hole); the J1 locating holes are 0.39 mm from the neighbouring pin holes (same footprint as the Rev 2
HAT, already built); the JLC CPL rotation table is the one the previous orders used — check U6, U7, U105 and the
diodes in JLC's preview.

Second schematic review (2026-10-29, no blocker / major): R107 / R108 4.7 k → 2.2 k (ISO1640 side-1 sink current
was at the bottom of its 0.5–3.5 mA range); stale texts fixed.  Noted, not changed: the Pi's GPIO14 / 16 / 24 / 25 /
26 drive MCU pins directly, so a Pi that pulls GPIO18 low without parking them (as `Pi/power_cycle.py` does, with
`LASERHAT_NRST_PIN=9` on this board) back-feeds MSPM0_3V3 through the MCU's clamps; JP4 (RTS → NRST) is for
stand-alone use only (two push-pull drivers otherwise); with SW10 on, the USB-C port back-powers the Pi through the
ideal diode — use a ≥ 3 A supply or keep SW10 off with a Pi fitted; the electrode pins have no series / TVS
protection beyond the op-amp's clamps (a candidate for rev B: 1 k in each lead).

Independent schematic review (2026-10-29), applied: the CH340N (U6) now runs from MSPM0_3V3 instead of +3V3 — on +3V3
its idle-high TXD / RTS# drove PA11 / NRST of the MCU while the Pi had the MCU rail switched off (abs-max violation and a
back-feed that made GPIO18 power-cycles unclean; inherited from the Rev 2 HAT), so the USB-UART now disappears from the
host while the MCU is off; C17 100 nF at U6; R3 47 k → 10 k so NRST sits at ≈ 2.75 V against the Pi's boot-time
pull-down on GPIO16 instead of ≈ 1.6 V; C125 / C126 100 nF 50 V at the DG418's V+ / V−; R19 / R20 DNP.  Noted, not
changed: JP1 open leaves the ID EEPROM write-enabled — close it after programming; do not terminate J7 in 50 Ω (the
74LVC2G17 through R25 33 Ω is for high-impedance trigger inputs); −5V_ISO measures ≈ −4.0 to −4.2 V (BZT52C4V3S at
2 mA, below its 5 mA test current), which is what the 4053 needs.

Independent layout review (2026-10-29), applied: `StimHAT.kicad_dru` had never been applied — KiCad 9 silently drops
a rule that carries a `(comment …)` entry (verified: the same rule fires without it), so the 2.5 mm barrier had not
been checked by DRC.  The file now has no comments and is proven live by a deliberate 25 mm test before a DRC result is
trusted.  With the rule live, three real intrusions were fixed (the I2C loop above U109 at 2.32 mm from its HAT-side
pads — U109's SOIC pads are 1.95 mm long — now the +5V_ISO feed alone runs above U109 at y 20.65 and SCL / SDA pass
below it; the passage tracks 2.18 mm from the pads of U104 / Q101 / C109 — those moved 0.3 mm east and the +5V / GND
passage tracks are pre-routed at x 46.5 / 47.15).  The four nets the schematic had left unlabelled (VREFIO, OA_IN,
U5B_IN, OA_OUT) and the NC pads of U105 / U108 are in the Isolated class.  The former 0.3 mm rule between the + and −
rails was dropped: the rails keep the 0.15 mm class clearance (IPC-2221 B4, coated, ≤ 50 V: 0.13 mm; the `Rails` class
only marks them, 0.3 mm wide).  Standoff keep-outs exclude tracks (r 3.25 mm; MH4 r 2.85 mm — fit a round nylon
standoff / washer ≤ Ø 5.5 mm there, nothing isolated lies under it).  Decouplers moved next to their pins (C1 / C16 /
C4 at U7, C17 at U6, C18 at U1, C103 at U109's side 1, C102 west of U109's side 2, C101 at U101, C116 / C117 at U106,
C118 / C119 at U107, C125 / C126 at U108, C112 at U104); R109 sits beside the SDA lane, R110 under U105; the LEDs sit
below the bonnet's edge (y ≥ 31.5); silk text 1.0 mm.  Noted, not changed: BNC pitch 15.6 mm (two plugs side by side
with ≈ 1 mm between the knurls); no copper pours (GND is 0.3 mm tracks; adequate at these currents); the USB pair is
unmatched (full speed only).

## MCU pin map (StimHAT, 2026-10-29)

Re-optimised for this placement (annealed over every function-legal assignment; report in the session notes): each
line leaves U7 on the side facing its destination, 0 facing violations, model crossings 81 → 41 (the rest are the
fixed-pin SWD / BSL / UART lines, best run on the back from their fan-out vias).  The laser variant keeps the same
positions: PWM, fault and ADC functions sit on the isolator-facing pins.

| Pin | Pad | Net | Function |
|---|---|---|---|
| 1, 2 | PA0, PA1 | I2C_SDA, I2C_SCL | I2C0 (fail-safe pins), fixed |
| 3 / 6 / 32 | NRST / PA2 / VCORE | NRST / ROSC / VCORE | fixed |
| 7 | PA3 | spare | I2C1, TIMG8 |
| 8 | PA4 | PI_TRIGGER | GPIO IRQ, ← Pi GPIO18 (header pin 12, directly above U7; was GPIO26 / pin 37 and PA27 until 2026-10-29) |
| 9 | PA5 | LED_MCU | GPIO, to D7 on the back (user's choice after routing) |
| 10 | PA6 | spare | |
| 11 | PA7 | BUTTON4 (up) | GPIO, runs on the back from a via beside pin 11 (swapped with BUTTON1 on the user's routing, 2026-10-29) |
| 12, 13 | PA8, PA9 | PI_RXD, PI_TXD | UART1 (only PA8/9 or PA17/18), fixed |
| 14, 15 | PA10, PA11 | MCU_UART_TX/RX | UART0 (BSL), fixed |
| 16, 17, 18, 19 | PA12, PA13, PA14, PA15 | BUTTON1 (left / BACK), BUTTON6 (right), BUTTON2 (centre), BUTTON3 (down) | GPIO; with pin 11 a five-track 45° fan from U7's south-west corner to SW7 (pads 4, 6 on the north-west column, 3, 2, 1 on the south-east one).  PA15 is DAC0_OUT: a laser variant that needs the DAC gives up one joystick direction |
| 20 | PA16 | BUTTON5 (FIRE) | GPIO, faces SW9 |
| 21 | PA17 | MCU_STIM_OUT | GPIO (TIMA1_C0 / TIMG7_C0 available) |
| 22 / 23 / 24 | PA18 / PA19 / PA20 | BSL_INVOKE / SWDIO / SWCLK | fixed |
| 25 | PA21 | MCU_STIM_IN | TIMG8_CCP0 capture, faces U8 |
| 26 | PA22 | FAULT_H | GPIO IRQ (the firmware's fault path; TIMA0's hardware fault inputs are only on PA26 / PA27, now the I2C lines), faces U101.6 |
| 27 | PA23 | CATH_H (PWM_B) | TIMA0_CCP3, faces U101.5 |
| 28 | PA24 | EN_H (PWM_A) | TIMA0_CCP3N (hardware complement of PWM_B with dead time) or TIMA1_CCP1 for a laser variant; a GPIO in e-stim mode, faces U101.4 |
| 29 | PA25 | RELEASE_H | GPIO, faces U101.3 |
| 30, 31 | PA26, PA27 | SDA_H, SCL_H (DB_ADC_A/B) | ADC0 ch 1 / ch 0, face U109 |

Header (2026-10-29, user's request): PI_TRIGGER = GPIO18 (pin 12), MCU_PWR_EN = GPIO10 (pin 19), NRST = GPIO9 (pin 21) - all
in the header's west half above U7; pins 11 / 13 / 15 (GPIO17 / 27 / 22) were ruled out because the bonnet's joystick grounds
them, pins 24 / 26 (GPIO8 / 7) because they pull up at boot.  Pi side: `LASERHAT_NRST_PIN=9 LASERHAT_POWER_PIN=10
LASERHAT_TRIGGER_PIN=18`, `laserhat-brokerd --gpio-pin 18`; SPI0 must stay disabled (GPIO9 / 10 are its MISO / MOSI).
SW7 is mounted at 135° (user's rotation): the ALPS drawing's directions a / b / c / d (contacts A = 1, B = 4, C = 3, D = 6)
then point south / west / east / north, so pad 1 = down, 4 = left, 3 = right, 6 = up - the nets follow that; verify on the
first board by pushing the stem toward each edge and checking which contact closes to the common.

The east column was re-ordered on 2026-10-29 (user's request, routing): top to bottom SCL_H, SDA_H toward U109, then RELEASE_H,
EN_H, CATH_H, FAULT_H in U101's pin order (its HAT-side pins 3-6 at y 26.05-27.95 against U7's 29-26 at y 25.75-27.25), STIM_IN
at the bottom toward U8.

Firmware: `Firmware/board.h` / `mcu.h` carry this map as an uncommitted draft; `pwm_timer.c` / `output_mux.c`
(CCP1 ↔ CCP3 roles), `adc.c` (ADC0 ch 1 / 0: PA26 = A0_1, PA27 = A0_0) and the GPIO IRQ bit masks still need the matching edits.  Found on the
way: PA22 is ADC0 ch 7, never ADC1.8, so the Rev 2 HAT's compliance readback channel was wrong.  Placement hints from
the analysis (the HAT side is hand-placed): R101–R103 in RELEASE / EN / CATH order to match U101's pads, R107 / R108
nets swapped to match U109's SCL / SDA order, R4 and the R3 / C3 / JP4 reset network north of U7.

## The DC-DC pod

The isolated supply that used to be on the HAT: A0515S-1WR3 (5 V → ±15 V, 1 W, SIP-7, Mornsun, min. load 10 %),
C104 4.7 µF at its input, L101 / L102 10 µH + C105 / C106 10 µF per rail, then an NPN / PNP capacitance multiplier per
rail (Q101 MMBT3904 / Q102 MMBT3906, base 4.7 k / 10 µF: ≈ 0.6 V drop per rail, 60 dB ripple rejection above 100 Hz).
On a 31 × 22.5 mm, 1.6 mm board that stands in the band (see `DCDCPod/README.md`, "Mechanical"): 2 × 2.54 mm pins at
its west end into J103 (5 V, GND), 4 × 2.0 mm pins at its east end into J102's holes (+V, 0V, −V, CAB = 0V) — J102's
JST socket is not fitted when the pod is used — same nets on the same holes as before.  Since 2026-10-30 the pod faces
**south**: its parts face looks at the BNC bodies, its bare back at the bonnet (5.1–5.4 mm from the bonnet's edge with
the rows at y 39.0), and PS1 sits along its top edge, body at z 16.6–22.6, hanging ≈ 10 mm south over J6 / J7's bodies
with 1.0 mm to their tops (15.6 mm); the pod's front face is at y ≈ 37.9, its back at ≈ 36.3.  Its own 2.5 mm
isolation gap runs vertically at HAT x 22.4–24.9 (between PS1's pins 2 / 4 and east of J1.2); within 3.5 mm of the HAT
its isolated copper is at x ≥ 37.3 and its 5 V copper at x ≤ 22.4, i.e. over the HAT's own sides of the barrier strip
at x 34–36.5.  The HAT keeps C109 / C110 and the 20 V clamps, so the pod needs no output capacitors of its own.

## Assembly notes and first-article checks

- Standoffs: M2.5 as a HAT; **MH4 (south-east) nylon** — it sits in the isolated copper.
- Fit J102 (JST) for the battery pack, or leave it off and plug the DC-DC pod into J102's holes and J103.  Never both.
- Joystick: mounted at 135°, directions line up with the board (up = away from the BNCs).  If a direction reads wrong,
  swap in firmware (BUTTON1/3/4/6).
- First power-up with a Pi: check +3V3, MSPM0_3V3 (GPIO18 high), +5V_ISO ≈ 5.0 V, +V_STIM / −V_STIM ≈ ±13.5 V (DC-DC) or
  pack minus ≈ 1.2 V, −5V_ISO ≈ −4.0 to −4.2 V, FAULT_n high; then the module checks from `../EStimDaughter/README.md`.
