# BatteryPack — ±V battery board for the e-stim module (rev D: series packs, floating charger)

Rev D, 2026-10-28.  One 100 × 100 mm board carries two off-the-shelf 4S hobby packs (any LiPo or Li-ion pack with the
standard JST-XH 5-pin balance plug and an XT60 discharge plug, 850–1550 mAh class, about 70–76 × 35 × 30–37 mm) strapped
to its underside, permanently in series, and gives the e-stim module +V / 0 V / −V (12.0–16.8 V per rail) on a 4-pin
JST-PH.  One USB-C PD charger floats on its own ground and a relay, run by a small MCU, switches it between the packs; one
toggle does ON / OFF.  2-layer, JLC assembled (toggle, XH and PH sockets, XT60s and the relay through-hole).

Rev C (commit `8b583b4`) charged the packs in parallel through a RUN / OFF / CHARGE toggle.  That made one half of the board
jump by a pack voltage between the modes, needed a PTC link and an equalising rule for mismatched packs, and left no single
reference for a ground pour.  Rev D fixes the pack topology and moves all the switching into the charger.  Rev B
(`6fa6e9d`) was a 4S 18650 board with clips, two of them stacked.  The output cable to the module is unchanged except that
its pin 4 is now an interlock.

Files: `gen_schematic.py` + `sch_parts.py` + `sch_symbols.py` (+ `sch_engine.py`) generate `BatteryPack.kicad_sch`
(deterministic UUIDs, like the e-stim module); `tools/netcheck.py` proves the drawing matches `sch_parts.py`;
`tools/make_bom.py` writes `bom_BatteryPack.csv`; `tools/make_footprints.py` writes `battpack.pretty/` (toggle, relay,
opto; the clip footprint is kept for rev B).  Board: `tools/board_init.py` (once), `tools/pcb_sync.py` (footprints and
nets from the netlist), `tools/place.py` (outline, slots, holes, placement, silk; idempotent) and `tools/autoroute.py`
(rip-up, stubs out of pads narrower than their net class, Freerouting headless through DSN/SES, stub clean-up, DRC) built
it — the user is remote, so the layout is scripted rather than hand-placed like the other boards.  Hand edits in pcbnew
are fine afterwards; re-running `place.py` + `autoroute.py` discards them.  `tools/stamp_fields.py` puts the LCSC codes on
the footprints, `tools/make_fab.py` writes `../fab/BatteryPack/` (gerbers, JLC BOM + CPL).  `firmware/` is the charge
controller's program (see below).

## What is on it

| Block | Parts | Notes |
|---|---|---|
| Pack sockets | per pack an XT60 and a JST-XH: J7 / J5 (pack A, −V side), J8 / J6 (pack B, +V side); XT60 = Amass XT60PW-M horizontal (C98732, ext), XH = JST S5B-XH-A-1 right-angle (C163038, ext) | the XT60 discharge plug carries the run and charge current (J7 = GND / 0V, J8 = 0V / +BATB; the plug is keyed, the footprint silk marks + and −); the balance plug gives the cell taps (XH pin 1 = black = pack negative, 2–4 = taps, 5 = pack positive; pins 1 and 5 parallel the XT60).  J5 = GND, C1, C2, C3, 0V; J6 = 0V, B1, B2, B3, +BATB.  **0V = pack A's positive = pack B's negative = the output reference, always.**  A pack with an XT30 lead needs an XT30-to-XT60 adapter |
| Balancers | pack A: U6–U9 HY2213-BB3A (C113632, ext), Q7–Q10 AO3400A, R35–R38 100 R 1206, R31–R34, C12–C15; pack B: U10–U13, Q15–Q18, R62–R65, R58–R61, C16–C19 | 42 mA bleed above 4.200 V, release 4.19 V, 2.5 µA standing, per cell of both packs |
| Toggle | SW1 MTS-202 DPDT ON-ON (C55159891, ext; **JLC stock 195 on 2026-10-28**) | **ON / OFF**.  Pole 1 (common EN_A): ON → 0V.  Pole 2 (common EN_B): ON → +BATB.  OFF opens both: outputs off, gauges dark (R40 / R82 hold the enables low) |
| +V chain (pack B) | F1 100 mA PTC MF-MSMF010-2 (C12430, ext), Q1 AO3401A, R1/R2 100k, Q22 2N7002, R81 1M, U15B (LM393), R53 1M | +BATB → F1 → +SW → Q1 → +OUT (J3.1).  Q22 pulls Q1's gate low while ENB_G (= EN_B through R81) is high **and its source, J3.4, is at 0V** — the module's plug straps pin 4 to pin 2, so +V can only appear with 0V connected.  U15B pulls ENB_G low below 12.0 V (back above 12.8 V), the opto U17 pulls it low while a brick is plugged in |
| −V chain (pack A) | F2 100 mA PTC, Q11 AO3400A (N, in pack A's negative), R39/R40 100k, U2B (LM393), R11 470k, Q14 + D1 (ON) | GND → F2 → Q11 → −V (J3.3).  Q11's gate is pack A / 2 from EN_A (= 0V when ON); U2B pulls it low below 12.0 V, back on above 12.9 V.  −V alone is harmless to the module (nothing in it conducts without 0V), so chain A is not interlocked.  Q14 lights D1 while Q11 conducts |
| Gauge rails | Q20 AO3401A + R77/R78 + Q21 2N7002 + R79/R80 (+G = 0V through Q20); Q23 + R83/R84 + Q24 (+GB = +BATB through Q23) | both rails follow EN_A / EN_B only: the gauges show whenever the toggle is ON, charging or not |
| Gauges | pack A: U3 CJ431, R3–R10, U1/U2 LM393, D2–D4 + R13–R15 on +G; pack B: U16, R45–R52, U14/U15, D12–D14 + R55–R57 on +GB, D11 + R54 ON from +OUT | per pack: green ≥ 15.9 V, green ≥ 15.1 V, yellow ≥ 14.3 V, ~1 mA each (the ladder's R4 / R46 is 6.2k now that the rail is the pack itself, not the pack − 0.25 V) |
| Charging interlock | U17 EL817S1 opto (C2912100, ext), R76 10k | LED from the island's VBUS; transistor holds ENB_G at 0V → +V off (and the module's fault line reports it) whenever a brick is in, so the brick's mains leakage can never reach the electrode |
| **Charger island** (floats on CGND) | J1 USB-C (C165948, ext), U4 CH224A (C42459160, ext) + C3 + R24 120k, U18 TLV76033 LDO (C2683368, ext) + C22/C23, **Q13 AO3401A VBUS switch** + R43/R44 + Q12 2N7002 + R42, U5 CN3704 (C51659, ext), Q6 AO3401A, D7/D8 SS34, L1 22 µH (C408453, ext), R25+R26 0.2 R, C4–C11, R27, RT1 NTC (C13564, ext), R28/R29 10k | PD brick negotiated to 20 V (the CH224A's DP / DM stay open: the USB data lines belong to the MCU).  Q13 passes VBUS to the charger only while the MCU drives CHG_EN; the charger's output +CHG / CGND goes to the relay.  1 A CC into one pack at a time, 16.8 V ±1 % CV, termination 92 mA, trickle 150 mA below 11.2 V, re-charge below 16.0 V, 18.1 V over-voltage cut, NTC stops it hot / cold.  The island is the only part of the board whose potential moves (it rides on GND or on 0V); the brick is mains-isolated, so that is fine.  **Up to 2 A:** R25 + R26 = 0.1 R, L1 20 µH, a 45 W brick (the HFD2's contacts are rated 2 A) |
| Relay | K1 Hongfa HFD2/024-M (C18198081, ext), Q19 2N7002, D19 1N4148W | 24 V coil straight from VBUS (2.9 kΩ: 7 mA at 20 V; pick-up ≤ 18 V), DPDT 2 A: released = pack A (NC: +CHG → 0V, CGND → GND), energised = pack B (NO: +CHG → +BATB, CGND → 0V).  Only ever switched with the charger off |
| MCU | U19 STM32F042F4P6 (C81002, ext), C24–C26, R70 10k + SW2 BOOT (TS-1187A, C318884), R71/R72 and R73/R74 100k/18k senses, TP1–TP4 (SWDIO / SWCLK / GND / 3V3) | powered from VBUS through U18, so it exists only while a source is plugged in.  Reads CHRG / DONE, the connected pack and VBUS; drives the relay, CHG_EN and the four LEDs.  USB DFU bootloader on the same USB-C (see Firmware) |
| Status LEDs | gauge A column: D4 / D3 / D2 (80 / 50 / 20 %), D1 ON, D9 CHG (red), D10 DONE (green); gauge B column: D14 / D13 / D12, D11 ON, D17 CHG, D18 DONE; R66–R69 | the two columns are paired in the middle of the front strip (A left, B right) with the row labels between them |
| Output | J3 B4B-PH-K-S (+OUT, 0V, −V, CAB) | same 4-wire cable to the module as rev B / C; **pin 4 (CAB) must be strapped to pin 2 (0V) in the module's plug** (a wire loop in the PH plug until the module's next rev has the socket wired that way) |
| Mounting | H1–H4 M3 at (4, 4), (96.5, 3.5), (4, 96), (96, 96); three 3.5 × 22 mm strap slots at x 3–6.5, 45.75–50.25, 90.5–94, y 39–61; **H5–H8 M2.5 at (89, 52.5), (31, 52.5), (89, 3.5), (31, 3.5) = a Raspberry Pi's 58 × 49 pattern, long axis along x** | packs under the board on 40 mm standoffs (packs are up to 37 mm thick); two 20 mm hobby battery straps, each through an outer slot and the shared middle slot.  The Pi (3B+ / 4 / 5, with the HAT on it) lies along the top edge above the board on M2.5 standoffs over x 7.5–92.5, y 0–56: its "bottom" face (USB-C power, micro-HDMI, the long edge opposite the header and the OLED bonnet) is flush with the board's top edge, its header runs along y = 56, the SD-card end is at x 92.5.  The HAT covers x 27.5–92.5, y 0–56, so the e-stim module (26.5 × 33 mm, 9 mm past the HAT's edge) hangs over the top edge at the top-right corner (x 65–91.5, y −9..24) with its electrode header at (80, −7) pointing up: the stimulation wires and the Pi's power / HDMI cables all leave over the top edge.  The module's battery pads (its PS1 position) are at x 84.5–91.5, y −3..3, 36 mm up; J3 (pins x 76.5–82.5 at y 4; the Pi standoff H7 (89, 3.5) has the corner itself) is right below them, the cable rises straight up and passes west of the HAT's thumbwheel (x 88.7–98.5, y 6.5–19, 25 mm up).  **Standoffs ≥ 11 mm** (the XT60 sockets and the electrolytic are under the Pi; the relay is not).  All four Pi standoffs fall inside the pack envelopes: fix them from the top (threaded standoff + screw) or use low heads below.  The HAT's outline (its Edge.Cuts, copied by `tools/place.py` from `../LaserDriver.kicad_pcb`, MH1 on H5, rotated with the Pi) is drawn on User.Comments and the Pi's 85 × 56 outline on User.Drawings; neither goes to the gerbers |

Standing draw ON: 10–16 mA (two gauges, ON LEDs); OFF: about 40 µA (balancers, the charger's sleep current through the
relay's released contacts).  The e-stim module itself draws about 10 mA.

## Operation

- **ON:** both output chains enabled (+V from pack B, −V from pack A, 0 V = their junction), both gauges lit.  +V appears
  only with the module's plug in (J3.4 strapped to 0V in the plug).  A pack below 12.0 V drops its rail (the module's
  fault comparator reports a missing rail); it comes back above 12.8 / 12.9 V.
- **OFF:** both enables open, rails off, gauges dark.
- **Charging:** plug a 20 V PD brick (≥ 30 W) into J1 in either toggle position; the outputs go off (U17) and the MCU
  takes over: it connects pack A, reads it at rest, connects pack B, reads it, and starts on the lower one.  It charges
  in slots of 3 minutes, pausing the charger at each slot end to read the connected pack at rest and swapping to the other
  pack when that one's last resting reading is lower by more than 50 mV, so both packs climb together ("charge the lower
  pack").  DONE from the CN3704 flags a pack full; a flagged pack is never reconnected until the brick is unplugged.  Both
  full: charger off, both DONE LEDs on.  The charger is power-cycled at every reconnection so the CN3704 starts a fresh
  cycle even on a pack above its 16.0 V recharge threshold.  Full charge takes the same time as rev C's parallel scheme
  (the 1 A is time-shared) but each pack gets its own CC/CV and termination, and mismatched packs no longer matter.
- **Not a brick** (a PC port, 5 V): the MCU boots (DFU if BOOT is held) and blinks both CHG LEDs slowly; nothing charges.
- The relay only moves with the charger off (dry switching); the output capacitors' equalising into the next pack is the
  only inrush the contacts see.

## Thresholds and values

Gauge rails = the packs (P-FETs, no drop).  VS = rail × 0.1357 with the output live (R9 68k ∥ R11 against R10 10k),
× 0.1271 cut off.  Ladder from 2.495 V: 6.2k, 2k, 2k, 6.2k, 30k → TH80 2.162 V, TH50 2.054 V, TH20 1.946 V, THCUT 1.613 V →
15.9 / 15.1 / 14.3 V (pack) and 11.9 V (cutoff) / 12.7 V (re-enable, pack B via R53 1M from +OUT) / 12.8 V (pack A via R11
470k from Q11's gate, which sits at pack A / 2).  Charger: Ich = 200 mV / 0.2 R = 1 A (0.7 C for a 1300 mAh pack); Ieoc =
9.17 % (EOC grounded); CH224A CFG1 120k = 20 V request.  Q13: Vgs = −VBUS/2 = −10 V (R43/R44).  MCU senses: 100k / 18k
(16.8 V → 2.56 V, 20 V → 3.05 V).  Relay coil: 2.9 kΩ, 7 mA at 20 V.

## Firmware (`firmware/`)

`main.c` + `startup.c` + `stm32f042f4.ld` + `Makefile`: bare-metal C for the STM32F042F4P6 (HSI 8 MHz, SysTick 1 ms,
ADC, IWDG; no USB stack — the ROM bootloader does the flashing).  Build with `arm-none-eabi-gcc` (`make`), flash with
`dfu-util -a 0 -s 0x08000000:leave -D battpack.bin` (`make flash`) after entering DFU: a blank chip boots into DFU by
itself; afterwards hold SW2 (BOOT) while plugging the board's USB-C into a PC.  SWD on TP1 / TP2 (+ TP3 GND, TP4 3V3) is
the fallback.  Pins and the algorithm are documented at the top of `main.c`.  **Check on the first board:** that the
F042's DFU bootloader enumerates on the TSSOP-20 (its USB pins PA11 / PA12 are remapped onto pins 17 / 18 by the
bootloader on this package; ST's AN2606 lists DFU for the F042 and the 20-pin dev boards use it, but it was not tried
here).  The firmware has not been compiled in this checkout (no ARM toolchain); it passes a host syntax check.  Fab renders:
`../fab/BatteryPack/BatteryPack_top.png`, `_bottom.png`, `_front.png`.

## Board

100 × 100 mm (JLC's cheapest size tier), mirror-symmetric about x = 50.  Packs underneath, long axis along y, envelopes
x 7–45 and 51–89, y 10–86 (silk outlines on the back), leads round the front edge (y = 100): XH sockets J5 (pins x 10.5–20.5)
and J6 (x 79.5–89.5) outboard, XT60 sockets J7 (pins x 28.3 / 35.5) and J8 (x 64.5 / 71.7) inboard, faces flush with the edge,
the USB-C J1 (50, 95.8) flush in the middle between them with C3 beside it.  Front strip (y 56–100, the only part not under
the Pi): the two gauge LED columns at x 46 (A) and x 54 (B), rows 80 / 50 / 20 % / ON / CHG / DONE at y 62.5–75 with the
labels between them and the resistors outboard (x 41.5 / 58.5), the toggle at (50, 83.5) with its lever along x (ON to the
right); in the outer thirds, visible either side of the LED pair, the relay K1 standing at (84.5, 70) by pack B's sockets with
its driver Q19 / D19 above it, and the CH224A at (15.5, 70) by pack A's (its CC lines run to J1 as fine tracks).  Under the Pi (y < 56): gauge A's comparators and ladder top left (x 8–32), its rail switch at x 8; gauge B's
mirrored top right (x 70–92); pack A's balancers at x 9–38, pack B's at x 62–91 (rows y 28–52, outer columns one row up);
the +V chain at x 61–70 and the −V chain along the top edge (x 36–54, y 3) either side of the MCU, J3 at (76.5, 4).  The
charger island fills the centre column: MCU row at y 5–14 (U19, BOOT button, test points on the edge at y 4.3, the LDO),
the CN3704 and its passives at y 15–22, the electrolytic, buck switch, diodes, inductor and sense resistors at y 22–35,
the opto U17 on the slot's left flank.  (A first layout had the relay beside the middle slot and the CH224A on the flank:
the island was then too dense to route the MCU's LED lines and the charger output.)  Netclasses: Power 0.8 mm (GND, 0V, +BATB, C1–C3, B1–B3, +SW, +OUT, −V,
GNDF, CGND, +CHG, CAB), Charger 0.4 mm (SW, SWA, CSP, RCS, VBUS, VCHG, RLY_K), Fine 0.25 / 0.15 mm (USB-C CC1/CC2/D+/D−),
Default 0.3 / 0.2 mm.  Board minimums 0.15 / 0.15 (JLC: 0.127).  **A 0V pour covers the back side** (the output reference,
the one node every fixed-side part shares; 0.3 mm clearance, thermal reliefs, J3's 0V pin solid), which rev C could not have:
its 0V moved between GND and +BAT with the toggle.  The charger island's parts simply sit over it (the island floats on GND
or 0V anyway).  Rule areas keep vias out from under the Pi standoffs (r 3.0) and copper 0.5 mm away from the slots.  Routed
by Freerouting with the last connections (fine-pitch pad exits of U5 / U19, the −V run along the top edge, a few ground
links) finished by `../tools/maze_route.py`; 5.9 m of track, 2268 segments, 244 vias (rev C: 3.8 m / 1115 / 137 with 34
fewer parts).  Reference designators are hidden on the silk; the silk carries OUT, BOOT,
the test-point names, PD 20V / DFU at the USB-C, the LED row labels and A / B, PACK A / PACK B at the sockets and the
title on the back; the toggle footprint carries ON / OFF.

## Assembly notes and first-article checks

- **Toggle lever direction:** the silk assumes the usual toggle convention (lever away from the closed contacts): lever
  toward "ON" closes pins 1/4 (0V → EN_A, +BATB → EN_B), toward "OFF" closes the unused 3/6.  Verify with a meter on the
  first board; if the switch is the other way round, swap the two silk words in `tools/make_footprints.py`.
- **Plug interlock:** before the first use, strap pins 2 and 4 together in the PH plug of the module cable (or wire the
  module's PH-4 socket that way on its next rev).  Without the strap +V never comes on.
- **Pack plug polarity:** JST-XH pin 1 (the socket's marked end, x 10.5 on J5 and x 79.5 on J6) must take the pack's black
  wire.  Every 4S hobby pack wires the balance plug this way; check the first pack with a meter against the silk.  The XT60
  is keyed; check that the pack's + (the pin at the rounded side of the plug) lands on the XT60PW's + (x 28.3 / 64.5) before
  the first pack goes in — a pack wired the wrong way round would short through the XH pins.
- **JLC rotation:** check SOT-23, SOIC, TSSOP (U5, U19), the ESSOP, the LEDs (cathode = pad 1, KENTO parts as on the
  HAT), the opto (pin 1 dot) and the electrolytic in JLC's DFM preview before ordering.  The relay's pin 1 is marked with
  a silk dot; it is a 16-pin DIP grid with pins 1, 4, 6, 8 / 16, 13, 11, 9 populated.
- **Relay pick-up:** the 24 V coil must pull in from 20 V minus the cable drop (Hongfa: ≤ 18 V).  With a long or thin
  cable, listen for the click at the first pack swap; the 12 V HFD2 with a series resistor is the fallback.
- **First charge:** packs at any state, toggle anywhere, plug a 20 V brick in: within a second the MCU reads both packs
  (relay clicks twice) and CHG lights on the lower one.  Meter on CSP−+CHG (200 mV = 1 A) and on the connected pack's XH
  pins; every 3 minutes the charger pauses for a second and may swap.  DONE at ~90 mA per pack; both DONE = idle.  RT1 reads
  the board temperature next to the charger; a 10k fixed resistor in its place disables temperature control.
- **Straps:** 20 mm hobby battery straps (the usual 5-inch-quad ones, 200–250 mm long); the middle slot takes both.
- Extended parts (feeder fee each): toggle, XH and XT60 sockets, PTCs, USB-C, CH224A, CN3704, inductor, electrolytic,
  HY2213, NTC, PH-4 header, relay, opto, LDO, STM32.  Everything else is basic.

## Checks before fab

`python gen_schematic.py` → `python tools/netcheck.py` (CONNECTIVITY OK) → ERC (0) → `tools/pcb_sync.py` only if
nets or footprints changed (`--keep-tracks`) → `../tools/path_check.py` / `sync_check.py` → `kicad-cli pcb drc` →
`python tools/lcsc_check.py` → `python tools/make_fab.py`.

**XT60 footprint and 3D model.**  `battpack.pretty/XT60PW-M.kicad_mod` is KiCad's AMASS_XT60PW-M footprint with its
model pointed at `battpack.3dshapes/XT60PW-M.step`, which `tools/make_xt60_model.py` builds with CadQuery (KiCad 9 ships
no model for the horizontal part; the model reuses the vertical XT60-M nose and adds the PW's body, bent pins and legs).

**Part numbers on the board.**  `sch_parts.py` holds the LCSC codes; the generator writes them into every symbol as the
`LCSC Part #` field and `tools/stamp_fields.py` writes the same field (hidden, F.Fab) into every footprint, syncs the
Values and marks H1–H8 and the test points excluded from BOM and position files — so a BOM/CPL made straight from the PCB
with the Fabrication Toolkit carries the codes too.  Re-run `stamp_fields.py` after changing a value or code in
`sch_parts.py`.  Values of switches, LEDs, connectors, the relay, the inductor and the NTC are JLC's model strings (their
matcher compares the BOM Comment with them); plain R/C values still draw JLC's harmless "comment differs" note, as on the HAT.
