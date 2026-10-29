---
name: stim-hat-plan
description: "2026-10-28/29: why and how the e-stim module and the HAT became one board (StimHAT/): the brainstorm's decisions (dedicated HATs, cheaper switch parts, bonnet kept, joystick, floorplan 1g with the isolated L-block), what was rejected (SPI DAC readback: the DAC60501 has no SDO; 1.54 in display; bare-glass OLED; STM32 core), and the StimHAT rev A build (generator, barrier rule areas, PS1 under the tab)"
metadata:
  type: project
  originSessionId: 3d2bbd2f-69c2-4c9f-abdd-a97d90e88da4
  modified: 2026-10-29T00:30:00.000Z
---

**The brainstorm (user, 2026-10-28 evening, a forked session while the pack rev D was being built).**  Starting point:
the daughterboard concept (one HAT + laser / e-stim modules) was elegant, but the e-stim module's isolated supply had
become a whole battery-pack project, the module BOM was $25 with seven ICs over $1 (ADG1436 $8.22, DG419 $4.89,
ISO7741F $2.65, OPA2192 $2.48, DAC60501 $2.30, ISO1640 $1.72, TLV1702 $1.09), and JLC's per-order fees ($3 per extended
type, $8 setup) made the second PCBA order cost more than its parts.  Conclusions, in the order they were reached:
1. **Two dedicated HATs** (laser, stim) instead of HAT + modules: one PCBA order per system, no J8/J9 contract, no
   stacking-height limit.  Shared core kept identical through one generator / part table; the ID EEPROM tells the
   firmware which board it is on.  Double-sided assembly rejected (JLC standard PCBA: $50 setup + $17 stencil, more
   than a separate single-sided module order).
2. **Cheaper stimulator, same signal path**: the switches only ever carry +/-1.25 V, so a 74HC4053 on +5 / -4.7 V
   replaces the ADG1436 (the -5 V rail is a Zener + resistor, as rev M1-M3 had; a 79L05 would cost 3-6 mA quiescent and
   is fixed at -5.0 V, at the HC4053's 10 V total-supply limit); a DG418 (SPST, same family, 100 ns) replaces the
   DG419 whose second throw was unused; the 4053's spare switch inverts RELEASE for it.  PhotoMOS for the SHORT
   switch rejected (0.1-0.35 ms switching; latency matters to the user).  **SPI DAC rejected**: the DACx0501 has no
   SDO pin, so SPI loses the readback the I2C path has; ISO7741F + ISO1640 stay (ISO7721/7720 fail-low "F" variants
   cost $2.22 / $1.35, not the $0.67 of the plain parts; plain default-high parts would only suit lines that idle
   high).  Stimulator ICs $23.50 -> $14.70.
3. **Isolated supply**: the A0515S DC-DC deserves a second chance (its bench fold-back on 2026-10-19 is explained by
   the ISO1640 pin swap): DC-DC -> LC -> capacitance multiplier per rail -> +/-13.5 V, PSRR does the rest.  Board
   carries pads for both the DC-DC (PS1) and the pack (J102).  20 V Zener clamps rail-to-GND_ISO so a floating
   GND_ISO can no longer push the switch ICs past their 25 V ratings (the module-killing plug-in order).
4. **Display**: the user wants the Adafruit 4567 bonnet (known quantity, 1.3 in 128 x 64 + joystick) kept; a 0.91 in
   128 x 32 I2C module (LCSC C5248081, 38 x 12 mm, pins at one end) is the alternative (unpopulated 4-pin right-angle
   socket at the top strip's east end, module lies west 2.5 mm up; same SSD1306 128 x 32 as the bonnet's software).
   Rejected: 0.96 in module on a header (needs new Pi-side resolution code), 1.54 in module (43 x 37.5: needs
   standoffs over the bottom band and SMAs instead of BNCs), bare-glass OLED through a slot (only the 0.96 in glass
   fits; 1.54 in would push the core to the back).  **Bonnet clash found**: its joystick-right is GPIO23 = the Rev 2
   HAT's NRST; the StimHAT takes NRST from GPIO16 (header pin 36).
5. **Navigation**: ALPS SKRHADE010 five-way (0.86 $, machine-placed, mounted at 45 deg so its directions line up)
   replaces the thumbwheel + BACK (left = BACK, right = new BUTTON6 on PA3); FIRE stays separate.  Encoder (EC11,
   $2.40, hand-fit) and the RKJXT1F42001 combo ($5.27) were the alternatives.
6. **MCU**: STM32F072 (USB DFU in ROM, 2 DACs, $2.52, no STM32 is in JLC's basic library any more) was weighed; the
   user keeps the MSPM0G3507 + CH340N: the CH340N exists only for the no-Pi use case and a plain UART keeps one code
   path (a CDC stack costs flash and complexity, not cycles).  LCSC stock of the MSPM0G3507 was 31 on 2026-10-28.
7. **Floorplan (panel 1g of the plan artifact)**: BNCs mid-south, joystick + FIRE on the west/south-west, USB-C and the
   power slide on the west edge, the core under the bonnet's west end, the isolated block in an L under the bonnet's
   east end (parts <= 7 mm under the 9 mm gap) + the strip east of the BNCs + a 12.5 mm south-east tab (electrode header,
   battery socket); the DC-DC is the only part over 7 mm and stands under the tab.  The non-isolated top strip
   (y < 17.5) keeps the 0.91 in socket's holes on HAT-side copper.  Isolated area ~1020 mm2 (module: 970).
   Plan pages: https://claude.ai/artifact/7xx4Rqfi35yJTENZ5k76P1 (floorplans 1-1g, chain, cost, decisions) and
   https://claude.ai/artifact/28RZs4Ed3CAZporzwAyyCS (switch block, Zener rail explained).

**StimHAT rev A build (2026-10-29, branch worktree-stim-hat off battery-pack).**  `LaserHAT/StimHAT/`: generator =
the pack's engine (`sch_engine.py`) + `sch_symbols.py` (e-stim symbols + the HAT core ICs, ISO1640 with the correct
1 VCC1 / 4 GND1 / 5 GND2 / 8 VCC2 pinout, side 1 = MCU) + `sch_parts.py` (core refs as on the HAT, stim refs = module
+ 100) + `gen_schematic.py` (10 blocks, A1).  Board by `tools/board_init.py` (copies the MSPM0 footprint and the HAT's
project footprints through `pcb_sync.py --src ../LaserDriver.kicad_pcb`), `tools/project_settings.py` (net classes
Default / Power / Fine / Isolated / IsolatedPower, constraints), `tools/place.py` (outline with notch + tab, barrier
rule areas, placement, silk), `tools/autoroute.py` (Freerouting), `StimHAT.kicad_dru` (Isolated vs non-isolated
>= 2.5 mm; +/-V rails 0.3 mm).  **Gotcha**: footprints copied by pcb_sync share their library UUIDs; KiCad's DRC then
reports courtyard overlaps between parts 40 mm apart — `tools/fresh_uuids.py` after every sync.  SOIC/TSSOP
isolators straddle the barrier with their pad rows; PS1's SIP straddles it on the tab (pins 1-2 in the HAT strip
x 46-50.7, fed under the BNC J7 on B.Cu through x 46-47.5).  Strip B needed 0805 inductors / capacitors and SOD-323
Zeners to fit.  MH4 sits in isolated copper (nylon standoff).

**Why:** the user wants the simplest, cheapest, robust path: one HAT per modality, known display, no latency added,
readback kept.  **How to apply:** regenerate with `gen_schematic.py` -> `netcheck.py` -> ERC; placement changes in
`place.py` then `autoroute.py` (every board edit in its own process); `drc_summary.py` for the placement guard;
hand-fit list and first-article checks in `StimHAT/README.md`.

Related: [[battery-pack-board]], [[estim-module-status]], [[laserhat-next-tasks]], [[laserhat-user-preferences]].
