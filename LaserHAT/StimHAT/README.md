# StimHAT — the LaserHAT Rev 2 core and the e-stim module's stimulator on one Raspberry Pi HAT (rev A, 2026-10-29)

One 65 × 57 mm HAT (plus a 12.5 mm tab on the south-east) carries the Rev 2 HAT core — MSPM0G3507, CH340N USB-UART,
USB-C power path, HAT ID EEPROM, BNC trigger in / stim out, buttons and LEDs — and the kbest constant-current
stimulator that was the plug-in e-stim module, isolated from the Pi side by an ISO7741F and an ISO1640 and powered
either by the A0515S DC-DC (hand-fitted, under the tab) or by the battery pack (JST-PH socket on the tab).  The
Adafruit 4567 OLED bonnet stacks on the Pi header above it as before; a 0.91" 128 × 32 I2C OLED module can be fitted
in an unpopulated right-angle socket instead.  2-layer, JLC economic assembly (top side only).

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
| 3.3 V | U4 MCP1700-3.3 (+3V3: CH340N, U5 input), U5 AP2171W (MSPM0_3V3, enabled by Pi GPIO18 through R7), C1 / C2 / C6 / C12 / C13 / C16, JP5 | JP5 feeds +3V3 onto the Pi's 3.3 V pins for stand-alone use (open it with a Pi) |
| ID EEPROM | U1 M24C32, JP1 (WP), R1 / R2 3.9k DNP | HAT spec |
| MCU | U7 MSPM0G3507 (VQFN-32), R4 100k 0.1 % (ROSC), C4 470n (VCORE), R3 10k + C3 10n + JP4 (reset), SW6 TS-1088 (BSL, active high), D7 + R15 (MCU LED) | pin map below |
| USB-UART | U6 CH340N | `MCU_UART_TX/RX`; RTS can reset the MCU through JP4 |
| Controls | SW7 ALPS SKRHADE010 five-way joystick (mounted at 45°), SW9 TS-1088 FIRE | replaces the thumbwheel and the BACK button |
| BNC | J6 TRIGGER IN → R23 1k / R24 100k → U8A (74LVC2G17) → PA26; PA25 → U8B → R25 33 → J7 STIM OUT, D9 + R18 STIM LED | as the Rev 2 HAT |
| Display | J10 PinSocket 1 × 4 right-angle, unpopulated (GND, 3.3 V, SCL, SDA) | for a 0.91" 128 × 32 SSD1306 module (LCSC C5248081) lying along the top strip, instead of the bonnet |
| Isolation | U101 ISO7741F (EN, CATH, RELEASE in; FAULT_n back; fail-safe low), U109 ISO1640 (I2C), R101–R103 100k pull-downs, R107 / R108 and R109 / R110 4.7k I2C pull-ups, C101–C103, C124 | the only parts whose pads lie on both sides of the barrier, with PS1 |
| Isolated supply | PS1 A0515S (±15 V from the HAT's 5 V, hand-fitted, **on the back of the tab**, DNP in the BOM) or J102 B4B-PH-K-S from the battery pack (+V, 0V, −V, CAB = 0V), L101 / L102 10 µH + C105 / C106 10 µF, Q101 / Q102 capacitance multipliers (R111 / R112 4.7k, C107 / C108 10 µF), C109 / C110, D103 / D104 BZT52C20S clamps, U104 TLV76050 (+5V_ISO), R113 4.7k + D102 BZT52C4V3S (−4.3 V), C104 | C104 is PS1's input cap, in the HAT-side strip of the tab |
| Set-point | U105 DAC60501 (I2C 0x48), C114 / C115, U106B OPA2192 inverter (R105 / R106 10.0k 0.1 %), U107 CD74HC4053 on +5 / −4.3 V | switch 1 (CATH) picks ±VSET, switch 2 (EN) gates it, switch 3 inverts RELEASE for the SHORT switch |
| Output stage | U106A OPA2192, R114 1k, C120 100p, R115 47, R116 2.49k 0.1 %, C121 1 µF, J101 electrode header (E1, E2) | 502 µA full scale, 0.123 µA / LSB |
| SHORT | U108 DG418 (normally open, on while SHORT_IN is high = RELEASE low) | electrode shorted whenever RELEASE is low, including HAT-side power-down |
| Fault detector | U110 TLV1702 window on E1 (R117 10k / R118 215k / R119 10k taps), R120 10k, R121 4.7k, D101 BAT54WS, C122 | FAULT_n low past the trip point, with +5V_ISO down, or with a rail missing |
| Mechanical | MH1–MH4 M2.5 (HAT pattern), Pi 4 PoE / Pi 5 fan notch | MH4 lies in isolated copper: use a nylon standoff there |

## Rev 2 MCU pin map (changes against the HAT)

| Pin | Port | Net | Function |
|---|---|---|---|
| 3 | NRST | NRST | **← Pi GPIO16 (header pin 36)**, not GPIO23: the bonnet's joystick-right grounds GPIO23 |
| 7 | PA3 | BUTTON6 | joystick right (new) |
| 10 | PA6 | FAULT_H | ISO7741F channel D (was J8.3) |
| 11 | PA7 | EN_H | ISO7741F channel B (was J8.5) |
| 16 | PA12 | CATH_H | ISO7741F channel C (was J8.4) |
| 17 / 18 / 20 | PA13 / PA14 / PA16 | BUTTON4 / 2 / 3 | joystick up / centre push / down (were the wheel) |
| 19 | PA15 | RELEASE_H | ISO7741F channel A (was J9.3) |
| 21 / 26 | PA17 / PA22 | SDA_H / SCL_H | bit-banged I2C to the ISO1640 (were J9.4 / J9.5) |
| 25 | PA21 | BUTTON1 | joystick left = BACK (was SW8) |
| 27 | PA23 | BUTTON5 | SW9 FIRE |

Everything else is as in `../CLAUDE.md`.  Firmware: the e-stim mode works unchanged (same lines, same DAC, same I2C);
add BUTTON6 to the button mask; on the Pi, `LASERHAT_NRST_PIN=16` (`Pi/power_cycle.py` defaults to 23, the bonnet's
joystick-right pin on this board).  The bonnet's buttons use GPIO 4, 5, 6, 17, 22,
23, 27, none of which the HAT now touches.

## Board

65 × 57 mm with the HAT outline (3 mm radii, the Pi 4 PoE / Pi 5 fan notch at x 59–65, y 8–16.5) and a tab x 46–65,
y 57–69.5 (HAT coordinates minus (100, 43)).  Top strip (y < 17.5) and west half: the core, all under the bonnet (9 mm
up, parts under 7 mm), the OLED socket J10 at the strip's east end.  West edge, top to bottom: SW10, J5, the three LEDs,
FIRE, the joystick in the south-west corner.  Two BNCs mid-south (bodies y 36.5–57, barrels past the edge).  Isolated
stimulator in an L: block A (x 36.5–65, y 20–34, under the bonnet's east end: isolators, DAC, inverter, 4053, output
stage, SHORT, fault detector), strip B (x 50–65, y 36.5–54.5: LDO, −4.3 V rail, filter, multipliers, clamps) and the
tab's east part (J102, J101).  PS1 stands under the tab, where nothing is below it (beyond the Pi's edge; the BNC
barrels are on top); its two input pins and C104 sit in the HAT-side strip along the tab's west edge, fed on the bottom
layer through the passage x 46–48 east of J7.  Barrier: 2.5 mm copper-free rule areas (drawn on User.Comments) plus
the `StimHAT.kicad_dru` rule (Isolated / IsolatedPower net classes vs everything else ≥ 2.5 mm).  Net classes: Power
and IsolatedPower 0.3 mm, Fine (USB), Default and Isolated 0.2 mm; board minimums 0.15 / 0.15, vias 0.6 / 0.3.
No copper pours.  User.Drawings: the bonnet outline, the 0.91" module outline, the notch note.

Routing (rev A, 2026-10-29): `tools/autoroute.py --passes 500` = rip → `tools/fanout.py` (locked dog-bone stub + via on
every netted pin of U7 and U101, alternately 0.45 / 0.95 mm out so the vias stagger, plus four GND thermal vias in U7's
exposed pad: without them Freerouting never finished the MCU's escape) → `tools/preroute.py` (hand-planned, locked:
SDA_H from U7.21 down between the south-row vias, east under the MCU and north along x 28.3 to R107; C1 into pin 4's
via; the +5V / GND feed of the tab's HAT strip down the passage east of J7; and the tab's isolated part — −V_RAW,
+V_RAW, GND_ISO, E1_OUT, ISENSE through the corridor west of MH4 and around J102 to PS1's pins and J101, where the
mirrored pin orders of J102 and PS1 force the three supply nets to cross on alternate layers; the router solved none
of these reliably) → Freerouting → import → `tools/fixups.py drop-dangling-vias` and `--trim-stubs` remove the fan-out
vias the router did not use (locked pre-routes are never trimmed).  Freerouting stops after ~300 passes with 2–9
connections open and never the same ones; after the review's placement changes the last 2–3 (and the DRC fixes above)
were finished by hand with `tools/fixups.py` (`track`, `via`, `move-via`, `drop-seg`): the +5V trunk to the tab runs
from J1.4 on the back along x 7.2, then down the west edge at x 1.2 to the power LED and on along the edge; the tab's
five isolated nets go through the corridor west of MH4 (-V_RAW front x 53.6, +V_RAW back 53.55, GND_ISO back 54.9,
E1_OUT back 55.6, ISENSE back 56.2) and around J102, whose pin order is the mirror of PS1's; GND_ISO of the LDO area
joins the battery socket along the east edge past MH4.  `tools/preroute.py` holds the pre-routes a fresh run starts
from; the hand finishing is not scripted, so a full re-route restarts from the placement.  Result: 0 DRC errors,
0 unconnected (isolation rule live), ERC 0 / 0.  The four remaining DRC warnings are `lib_footprint_mismatch` on J6,
J7, J101 and PS1: their silk outlines hang past the board edge (BNC barrels, the electrode header, PS1's body), so
`fixups.py silk-strip` deleted them from the board copies.  `fab/StimHAT/StimHAT_top.png` / `_bottom.png` are the
renders.

## Checks before fab

`python gen_schematic.py && python tools/netcheck.py && kicad-cli sch erc StimHAT.kicad_sch` (ERC 0 / 0),
`python tools/drc_summary.py` (0 errors, 0 unconnected), `../tools/path_check.py StimHAT.kicad_pcb StimHAT.kicad_sch`,
`../tools/sync_check.py StimHAT.kicad_pcb StimHAT.kicad_sch`, then `tools/stamp_fields.py` and `tools/make_fab.py`.
Hand-fitted: J1, J6, J7, J101, J102, PS1 (DNP in the BOM; fit it or feed J102), J10 (optional).  Not fitted: R19, R20
(the Pi has 1.8 k on GPIO 2/3; fit them only for stand-alone use with a J10 module that lacks its own pull-ups).
R1 / R2 (3.9 k on ID_SD / ID_SC) are fitted: the HAT design guide puts them on the HAT.

Second schematic review (2026-10-29, no blocker / major): R107 / R108 4.7 k → 2.2 k (ISO1640 side-1 sink current
was at the bottom of its 0.5–3.5 mA range); stale texts fixed.  Noted, not changed: the Pi's GPIO14 / 16 / 24 / 25 /
26 drive MCU pins directly, so a Pi that pulls GPIO18 low without parking them (as `Pi/power_cycle.py` does, with
`LASERHAT_NRST_PIN=16` on this board) back-feeds MSPM0_3V3 through the MCU's clamps; JP4 (RTS → NRST) is for
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
standoff / washer ≤ Ø 5.7 mm there, nothing isolated lies under it).  Decouplers moved next to their pins (C1 / C16 /
C4 at U7, C17 at U6, C18 at U1, C103 at U109's side 1, C102 west of U109's side 2, C101 at U101, C116 / C117 at U106,
C118 / C119 at U107, C125 / C126 at U108, C112 at U104); R109 sits beside the SDA lane, R110 under U105; the LEDs sit
below the bonnet's edge (y ≥ 31.5); silk text 1.0 mm.  Noted, not changed: BNC pitch 15.6 mm (two plugs side by side
with ≈ 1 mm between the knurls); no copper pours (GND is 0.3 mm tracks; adequate at these currents); the USB pair is
unmatched (full speed only).

## Assembly notes and first-article checks

- Standoffs: M2.5 as a HAT; **MH4 (south-east) nylon** — it sits in the isolated copper.
- Solder PS1 from the top (its pins come up through the tab) with the body on the back; it overhangs the tab's west
  edge by 1.2 mm under the BNC barrel, which is on the top side.  Do not fit PS1 and the battery pack together.
- Joystick: mounted at 45°, directions line up with the board (up = away from the BNCs).  If a direction reads wrong,
  swap in firmware (BUTTON1/3/4/6).
- First power-up with a Pi: check +3V3, MSPM0_3V3 (GPIO18 high), +5V_ISO ≈ 5.0 V, +V_STIM / −V_STIM ≈ ±13.5 V (DC-DC) or
  pack minus ≈ 1.2 V, −5V_ISO ≈ −4.0 to −4.2 V, FAULT_n high; then the module checks from `../EStimDaughter/README.md`.
