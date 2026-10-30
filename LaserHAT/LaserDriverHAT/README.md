# LaserDriverHAT — the LaserHAT Rev 2 core and the LaserDaughter laser-diode driver on one Raspberry Pi HAT (rev A, 2026-10-30)

One 65 × 57 mm, 4-layer HAT derived from the StimHAT (`../StimHAT/`): the StimHAT's HAT core — MSPM0G1507, CH340N
USB-UART, USB-C power path, HAT ID EEPROM, joystick / FIRE / BSL buttons, LEDs, BNC trigger in and sync out, OLED socket,
owl — kept footprint for footprint and track for track, the isolated e-stim stimulator removed, and the laser-diode driver
of the plug-in module `../LaserDaughter/` (rev 2.0, ordered 2026-10-01) brought in as its hand-made layout block.  The
Adafruit 4567 OLED bonnet stacks on the Pi header as on the StimHAT.  **Status: placed, the laser block's own copper
intact; the seven connections between the block and the HAT core are left for hand routing (below).  Not ordered.**

## Files

Generated like the StimHAT: `sch_parts.py` (single source of truth: parts, values, footprints, LCSC codes, pin → net) +
`sch_symbols.py` + `sch_engine.py` → `gen_schematic.py` writes `LaserDriverHAT.kicad_sch` and `laserdriverhat.kicad_sym`
(deterministic UUIDs: the HAT-core symbols keep the StimHAT's UUIDs).  `tools/netcheck.py` (drawing = `sch_parts`),
`tools/pcb_sync.py --keep-tracks` (headless F8, matches by reference), `tools/fresh_uuids.py`, `tools/stamp_fields.py`,
`tools/place.py` (placement table, outline, GND plane / pours, standoff keep-outs, silk, bonnet drawing; idempotent and
in sync with the board), `tools/project_settings.py` (net classes in the `.kicad_pro`), `tools/make_footprints.py`
(`laserdriverhat.pretty`: MSPM0 VQFN-32, ALPS joystick, right-angle BNC; the owl from `tools/owl_logo.py`),
`tools/make_bom.py` → `bom_LaserDriverHAT.csv`, `tools/make_fab.py` → `../fab/LaserDriverHAT/` (gerbers zip, JLC BOM / CPL,
3D renders `LaserDriverHAT_top.png` / `_bottom.png`), `tools/drc_summary.py`, `tools/fixups.py` / `maze_nets.py` / `stitch.py`
(hand-routing helpers).  The library nickname is `laserdriverhat` (was `stimhat`).  `LaserDriverHAT.kicad_dru`: one thermal
spoke allowed on the outer pours, and on R202 (see "Checks").  The StimHAT's Freerouting tools (autoroute, fan-out,
pre-route) and `board_init.py` were not carried over: they built the e-stim side.

## What changed against the StimHAT

**Removed** (schematic, board, BOM): the whole isolated half — U101 ISO7741F, U104 TLV76050, U105 DAC60501, U106 OPA2192,
U107 CD74HC4053, U108 DG418, U109 ISO1640, U110 TLV1702, R101–R121, C101–C127, D101–D104, J101 (electrodes), J102 (battery
/ DC-DC pod), J103 (pod 5 V), TP101 / TP102; the nets of the isolated side (GND_ISO, ±V_STIM, ±5V_ISO, …) and the six
HAT-side isolator lines (EN_H, CATH_H, RELEASE_H, FAULT_H, SDA_H, SCL_H); the isolation barrier (keep-out strips,
`hat_region` / `isolated_region` rule areas, the `.kicad_dru` barrier and `tht_connectors` / `j102_one_spoke` rules), the
Isolated / IsolatedPower / Rails net classes, the ISOLATED / NYLON / J102 / J103 silk, the DC-DC pod drawing.  On the board
360 StimHAT tracks / vias went with them (every one of a vanished net, BUTTON3's old route to PA15, the +5V spur to J103,
the MSPM0_3V3 branches to R107 / R108 / C103 / C101 / U101 and two MSPM0_3V3 vias left joined on In2 only); the other 450
are untouched, and all 58 HAT-core footprints are exactly where they were.

**One GND:** In1 is a single GND plane over the whole board, F / B carry full-board GND pours (0.25 mm clearance), In2 is
the routing layer it was.  MH4 no longer needs a nylon standoff.

**Kept:** everything else of the HAT core.  J7 is now **SYNC OUT** (value "BNC SYNC OUT", silk front and back, the LED
label "SYNC"): PA17 → U8B → J7 / D9 mirrors the laser pulse envelope, exactly the firmware's STIM_OUT behaviour; the net is
still `MCU_STIM_OUT`.

**Added:** the LaserDaughter's 26 fitted / jumper parts (its header sockets J1 = HAT_J8 and J3 = HAT_J9 are not fitted: their
six lines are now nets straight to U7 and the HAT's +5V / GND).  Values, footprints and LCSC codes as on the module
(`../tools/lcsc_parts.py` LASER), hand-fitted J2 (laser-diode socket) and J205 (RED shunt header), J4 (PD_K–LASER_V
solder jumper) DNP as on the module.  Reference mapping (module → HAT; the module's refs kept where the HAT core leaves
them free, +200 where R1–R26, C1–C18, U1–U8 or J5 are taken):

| Module | HAT | Part |
|---|---|---|
| R1, R2 | **R201, R202** | 100k / 33k LASER_V → DB_ADC_B divider |
| R3, R4, C11 | **R203, R204, C211** | 39k / 10k / 10 nF DB_DAC → IREF |
| R5, R6 | **R205, R206** | 187k / 10k boost feedback |
| R11, R12 | **R211, R212** | 1k 0.1 % / 4.7k photodiode → DB_ADC_A |
| C8, C9, C12 | **C208, C209, C212** | 22 µF boost in / out, 100 nF at U203 |
| U2, U3 | **U202, U203** | MT3608 boost, TLV2371 current servo |
| J5 | **J205** | RED shunt header (shorts D2) |
| D1–D4, J2, J4, L1, Q1, Q2, Rs1, SW5 | same | DSK14 ×2, KDZVTR2.7B / 2.4B, LD socket, PD jumper, 10 µH, AO9926B, NDT3055L, 2 Ω, PCM12 |
| J1, J3 | — | HAT_J8 / HAT_J9 headers, not fitted (lines become nets) |

Net names: the module's internal nets keep their names (`/SW`, `/IREF`, `/DUMMY_TOP`, `/DUMMY_MID`, `/DUMMY_BOT`,
`/LaserDrive`, `/IDrive`, `+12V`, `LASER_V`); its auto-named nets are `/LD_CATHODE` (Net-(J2-LD_Cathode)), `/PD_ANODE`,
`/PD_CATHODE`, `/Q2_GATE` (Net-(Q2-G)) and `/BOOST_FB` (Net-(U2-FB)); the header lines keep the CLAUDE.md names
`DB_PWM_A`, `DB_PWM_B`, `DB_DAC`, `DB_ADC_A`, `DB_ADC_B`.  There is no DB_GPIO / FAULT line: the laser module never had a
fault output (its J8.3 was unconnected).  Parts: 83 symbols, 67 machine placements, 44 JLC BOM lines.

## MCU pin map (U7 MSPM0G1507, VQFN-32 RHB)

The StimHAT's map with the east column re-used for the laser and one joystick line moved; every function checked against
the MSPM0G1507 datasheet table 6-2 (SLASEW9E).  Pi-header nets unchanged.

| Pin | Port | Net | Function |
|---|---|---|---|
| 1, 2 | PA0, PA1 | I2C_SDA, I2C_SCL | I2C0 (Pi / bonnet), fixed |
| 3 / 6 / 32 | NRST / PA2 / VCORE | NRST / ROSC / VCORE | as StimHAT |
| 7 | PA3 | — | spare |
| 8 | PA4 | PI_TRIGGER | GPIO IRQ ← Pi GPIO18 (J1.12) |
| 9 | PA5 | LED_MCU | D7 |
| **10** | **PA6** | **BUTTON3** (joystick down) | GPIO; **moved from PA15** to free DAC0 |
| 11 | PA7 | BUTTON4 (up) | GPIO |
| 12, 13 | PA8, PA9 | PI_RXD, PI_TXD | UART1 ↔ Pi |
| 14, 15 | PA10, PA11 | MCU_UART_TX / RX | UART0 ↔ CH340N (BSL) |
| 16, 17, 18 | PA12, PA13, PA14 | BUTTON1 (left / BACK), BUTTON6 (right), BUTTON2 (centre) | GPIO |
| **19** | **PA15** | **DB_DAC** | **DAC0_OUT** (the only DAC0 pin): laser current set-point, ≈ 102 mA / V |
| 20 | PA16 | BUTTON5 (FIRE) | GPIO |
| 21 | PA17 | MCU_STIM_OUT | GPIO → U8B → J7 SYNC OUT |
| 22 / 23 / 24 | PA18 / PA19 / PA20 | BSL_INVOKE / SWDIO / SWCLK | fixed |
| 25 | PA21 | MCU_STIM_IN | TIMG8_C0 capture ← U8A ← J6 TRIG IN |
| **26** | **PA22** | **DB_PWM_A** | **TIMA0_C1** (PF 5) — the firmware's CCP1 = laser switch (Q1 G1) |
| **27** | **PA23** | **DB_PWM_B** | **TIMA0_C3** (PF 4) — the firmware's CCP3 = dummy switch (Q1 G2) |
| 28, 29 | PA24, PA25 | — | spare (PA24 = TIMA0_C3N / TIMA1_C1, PA25 = TIMA0_C3 / C1N) |
| **30** | **PA26** | **DB_ADC_A** | **ADC0 ch 1** (A0_1): photodiode |
| **31** | **PA27** | **DB_ADC_B** | **ADC0 ch 0** (A0_0): LASER_V × 33k / 133k (12 V → 2.98 V) |

Why PA22 for PWM_A rather than PA24: LASER mode drives TIMA0 CCP1 (laser switch, high at zero / low at compare) and CCP3
(dummy switch, the complement on the same compare), `pwm_timer.c`; PA22 carries TIMA0_C1 and PA23 TIMA0_C3, so the timer
code is unchanged and only the IOMUX entries move.  PA24's C3N would have made the laser line a hardware complement of
the dummy line (a timer rewrite).  PA22 / PA23 are pins 26 / 27, next to each other and facing the laser block.

### Draft firmware note (not applied to `Firmware/`)

`Firmware/board.h` / `mcu.h` hold the StimHAT draft (uncommitted).  A LaserDriverHAT build needs:

* `BOARD_PWM_A_PIN (1u << 22)`, `IOMUX_PINCM47`, function TIMA0_CCP1 = PF 5 on PA22 (`IOMUX_PINCM47_PF_TIMA0_CCP1`, add to
  `mcu.h`); `BOARD_PWM_B_PIN (1u << 23)`, `IOMUX_PINCM53`, `IOMUX_PINCM53_PF_TIMA0_CCP3` (PF 4, as in the StimHAT draft).
  `pwm_timer.c` unchanged (CC1 / CC3); `output_mux.c` comments still name PA7 / PA12.
* `BOARD_DAC_PIN (1u << 15)` / `IOMUX_PINCM37` stays the DAC0 output (analog, PINCM left at reset default).
* ADC: `adc.c` must read **ADC0** channel 1 (PA26, photodiode) and channel 0 (PA27, LASER_V) instead of ADC1 ch 2 / 8.
* `BOARD_BUTTON3_PIN (1u << 6)`, `IOMUX_PINCM11` (PA6); drop PA6 from `BOARD_SPARE_PINS`, which becomes PA3 | PA24 | PA25.
* FAULT_n: no fault source on this board.  Keep the GPIO-IRQ code with `BOARD_FAULT_N_PIN` on a spare pin with its
  internal pull-up (e.g. PA24, `IOMUX_PINCM54`), which then never fires — or compile the fault path out for this board.
* E-stim mode does not exist on this board (no module): `CMD_SET_MODE ESTIM` should be refused.
* Pi side as for the StimHAT: `LASERHAT_NRST_PIN=9 LASERHAT_POWER_PIN=10 LASERHAT_TRIGGER_PIN=18`, brokerd `--gpio-pin 18`.

## Board

Outline, holes, Pi header, notch and bonnet drawing as the StimHAT.  The core occupies the top strip and the west half,
the BNCs the middle of the south edge.  **The laser block** is the LaserDaughter layout **translated by (−62.5, −57.25) mm,
not rotated**: the module outline x 101–127.5 / y 76–99.5 lands at x 38.5–65 / y 18.75–42.25, flush with the HAT's east
edge (drawn on User.Drawings).  Imported unchanged: all 26 footprints (position / orientation / side / footprint id,
J4 on the back as on the module), all 109 tracks and 23 vias (widths, layers, drills), the module's F + B GND pour (as zone
"Laser GND pour", priority 1, the module's 0.25 mm clearance / 0.5 mm spokes; it overlaps the HAT's own GND pours, same net),
and its labels 12V / 5V / RED (re-created by `place.py`).  Not imported: the module outline, its header sockets J1 / J3, its
title text and back-side copyright.  A check script (`verify_block.py`, session scratch) confirmed it: 132 / 132 module tracks / vias present
at the offset, 26 / 26 footprints identical, no HAT copper inside the block.  Fit: the block's courtyards end at y 42.45 (J2),
0.45 mm north of J7's body courtyard; the tall parts — J2 (laser-diode header) and SW5 (5 / 12 V slide, actuator pointing
west at x ≈ 38) — lie south of the bonnet's edge (y 31); under the bonnet the tallest is J205 with its 2.0 mm shunt (≈ 6 mm).
The block's former header lines end as **dangling stubs** where the header pads were (DRC "track_dangling" warnings: they
are the starting points for the hand routing): DB_PWM_A B.Cu at (56.66, 21.25), DB_PWM_B B.Cu (54.12, 21.25), +5V B.Cu
(48.8, 21.49), DB_DAC B.Cu (63.0, 29.83), DB_ADC_A F.Cu (64.3, 33.67), DB_ADC_B F.Cu (63.0, 34.91).

### Left for hand routing (DRC "unconnected", 7)

1. **+5V** to the block (U4.2 / the +5V network → L1.1 / the stub at (48.8, 21.49)).  The boost draws up to ≈ 0.85 A at
   5 V (12 V × 0.3 A / 0.85): route it wide (≥ 0.8 mm, In2 or a pour), and note the StimHAT's +5V path from the header has
   0.3 mm outer segments (rated ~0.3 A there) — widen that path or feed the block straight from J1.2 / J1.4.
2. **DB_PWM_A** U7.26 (PA22) → stub (56.66, 21.25) / Q1.2.
3. **DB_PWM_B** U7.27 (PA23) → stub (54.12, 21.25) / Q1.4.
4. **DB_DAC** U7.19 (PA15, south side) → R203.1 / stub (63.0, 29.83).
5. **DB_ADC_A** U7.30 (PA26) → stub (64.3, 33.67) / R211.1.
6. **DB_ADC_B** U7.31 (PA27) → stub (63.0, 34.91) / R201.2–R202.1.
7. **BUTTON3** U7.10 (PA6, west side) → SW7 pad 1 (its old route to pin 19 was removed).

GND is complete (pours, In1 plane, the module's GND vias reach In1).

## Checks (2026-10-30)

`gen_schematic.py` → netcheck **CONNECTIVITY OK** → ERC **0 violations** → netlist → `pcb_sync.py --keep-tracks` (no part
re-parked: the imported footprints already carried the new refs and the module's footprint ids) → `fresh_uuids.py` →
`stamp_fields.py` (LCSC fields: 0 mismatches vs `sch_parts`) → `../tools/fill_zones.py` → `../tools/path_check.py`
**83 symbols, 0 path mismatches** → `../tools/sync_check.py` **83 parts, 0 differences** → DRC **0 errors**, 7 unconnected
(the list above), warnings: 6 track_dangling (the block stubs above), 3 silk_over_copper (the owl's silk on J1's mask
openings, as on the StimHAT).  The LaserDaughter's own DRC has one error, `starved_thermal` on R2 pad 2 (one spoke to its
GND pour); the same pad is R202.2 here, so `LaserDriverHAT.kicad_dru` allows one spoke on R202 (`laser_r202_one_spoke`;
proven live: the error is gone with it and back without it) rather than changing the module's copper.
Fab outputs (`../fab/LaserDriverHAT/`) are pre-routing previews; regenerate after the hand routing.

Not done here: the hand routing above; `../tools/lcsc_verify.py` / stock check (the codes are the module's and the
StimHAT's, unchanged); the JLC placement-preview rotation check (top side only; J4 on the back is a DNP jumper).
