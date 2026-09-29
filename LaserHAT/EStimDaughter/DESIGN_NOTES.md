# kbest e-stim module for LaserHAT Rev 2 — rev M4

Plug-in isolated biphasic constant-current stimulator. Interface is frozen by
`LaserHAT/estim_interface/ESTIM_MODULE_SPEC.md` (§7 is the agreed contract).
The circuit is kbest rev E (`../biphasic_stim/DESIGN_NOTES.md`) with the changes below.

## Interface (HAT coordinates, top view)

| HAT line | MCU | Module use |
|---|---|---|
| J8.1 / J9.1 | GND | GND_H (HAT side of the barrier) |
| J8.2 | +5V | A0515S input (±15 V isolated out) |
| J9.2 | +3V3 | ISO7761F side 1 (VCC1) |
| J8.3 PWM_A | PA7 TIMA0_CCP1 | **EN**: current flows while high |
| J8.4 PWM_B | PA12 TIMA0_CCP3 | **CATH**: 1 = cathodic, 0 = anodic |
| J8.5 GPIO | PA6 TIMA0_FAULT0 | **FAULT_n**: low = compliance / open-electrode fault, or isolated side not up |
| J9.3 "DAC" | PA15 GPIO | **RELEASE**: high = SHORT switch open (M4; was CS_n) |
| J9.4 "ADC_A" | PA17 GPIO, open-drain | **SDA** (M4; was SCK; SDA/SCL swapped 2026-09-29 for the layout) |
| J9.5 "ADC_B" | PA22 GPIO, open-drain | **SCL** (M4; was MOSI) |

(MCU pins as of the HAT's 2026-09-28 routing: PA21/PA22/PA26/PA16 were the pre-remap pins. J9.3–5 meanings per spec §7.)

Defaults while the MCU pins are Hi-Z:
- pull-downs on EN, CATH and RELEASE;
- pull-ups on SDA/SCL (I²C idle);
- the ISO7741F outputs low when side 1 is unpowered.

So an unconfigured or unpowered HAT means zero current, and the electrode shorted.

## Firmware contract
- **Set-point.** Bit-banged I²C to the DAC60501Z (address 0x48) between trains: once after power-up GAIN register 0x04 = 0x0100 (REF-DIV = 1, BUFF-GAIN = 0), then DAC register 0x08 = code << 4.
  I = code / 4096 × 1.25 V / 2.49 kΩ, so full scale is 502 µA and one LSB is 0.123 µA.
- **Pulse pair.**
  1. RELEASE high ≥ 1 µs before EN (SHORT switch opens).
  2. CATH high before EN rises.
  3. EN high for t_pw.
  4. EN low for the interphase gap; CATH falls during the gap.
  5. EN high for t_pw.
  6. EN low; RELEASE low ~200 µs later for ≥ 200 µs (electrode reset), then as the experiment wants.
- **SHORT.** Driven by RELEASE through the ISO7741F: low = E1 shorted to E2. The M1–M3 hold timer (D2, R15, C17) is gone.
- **FAULT_n.** Low while the isolated side is unpowered (treat low at start-up as "module not ready"), and low while the electrode voltage E1 is outside the LM393 window (|E1| > ~0.915 × V: compliance limit reached, or an open electrode). The HAT latches it on TIMA0_FAULT0, which forces EN and CATH low; firmware clears it between trains (Q4).

## PS1 (isolated ±15 V) is DNP: converter or batteries
- PS1 is not fitted by JLC. It is excluded from the BOM and placement files and flagged DNP in the schematic and on the board.
  - Its pads are labelled on the top silkscreen: 5V, GND (HAT side); −V, 0V, +V (isolated).
- **Converter.** Fit an A0515S-1WR3 (Mornsun), or any pin-compatible 1 W 5 V → ±15 V SIP with this pinout:
  - pin 1 = +Vin;
  - pin 2 = GND in;
  - pin 4 = −Vo;
  - pin 5 = 0 V;
  - pin 6 = +Vo.

  Solder it, or use a 0.1" machined-pin SIP socket. LCSC C5369388 is a YLPTEC clone ($1.89).
  **Verified drop-in: RECOM RB-0515D/HP** (Mouser), checked against RECOM RB datasheet rev 1/2019. It has the same dual pinout (1 +Vin, 2 −Vin, 4 −Vout, 5 Com, 6 +Vout), 2.54 mm pitch, 1.0 mm holes and a 19.6 × 6.0 × 10.2 mm body; 0% minimum load; /HP = 2 kVDC isolation + continuous short-circuit protection; 20–75 pF isolation capacitance; ±5% output accuracy (the rails only set compliance). One distributor listing flags the Mornsun part as NRND/obsolete: check when ordering.
- **Batteries.** Leave pins 1 and 2 empty. Wire:
  - + of the upper pack → **+V** (pin 6);
  - the centre tap → **0V** (pin 5);
  - − of the lower pack → **−V** (pin 4).

  Range is about ±8 V to ±18 V (OPA2192 limit: 36 V total), with compliance ≈ V − 1.5 V. Draw is about 8–10 mA per rail. Batteries remove the converter's switching common-mode noise, which couples through tens of pF of isolation capacitance. The ISO7761 still couples about 2 pF.

## Changes from rev E (M1)

| Change | Why |
|---|---|
| LM393 compliance window (U8, 9 R, 2 C) removed; R19 4.7 k pulls FAULT_n high | The module would not route at ~80 % courtyard fill on the isolated side. User's choice (2026-09-26). FAULT_n then only meant "isolated side up". **Restored in M2** (below). |
| SHORT: back-to-back 2N7002 + BSS84 level shifter + 10 V zener (Q1–Q4, R16–R18, D3) replaced by one **DG419DY** (C6581, ±15 V SPDT, 20 Ω) | 8 parts become 1. Throw 1 conducts while IN is low, so IN is driven straight from HOLD, and the 74LVC1G14 (U7) and its cap are removed too. BOM goes from 55 to 46 lines. Costs about +$1.77 per board and saves two extended-part fees. |
| TMUX6136 (±15 V switch for the 4053) considered and **not** used | $5.78 against $0.23, to remove three cheap parts (−5 V zener rail). |
| MCP4821 (internal-reference DAC) considered and **not** used | Only SOIC-8 is stocked, so there is no routing gain. It would trade ±0.5 % → ±2 % amplitude accuracy for 5 fewer parts. Still an option if BOM cost matters. |
| ISO7761 forward channels reassigned: A MOSI, B CS, C SCK, D CATH, E EN | Shortest wiring at U1 (free pin swap). |

## Changes from M1 (M2, 2026-09-28)

| Change | Why |
|---|---|
| LM393 compliance / open-electrode window **restored**, exactly as in rev E: U8 LM393DGKR (VSSOP-8, C34440), R20 100 k / R21 12 k / R22 27 k + C18 100 p make E1_LS = 0.0767·E1 + 1.42 V; R23–R25 (110 k / 12 k / 27 k) make TH_P from +V and R26–R28 make TH_N from −V; both open collectors wired-OR onto FAULT_n with the existing R19 4.7 k pull-up; C19 100 n decoupling. | The HAT side is ready for it (J8.5 → PA6 = TIMA0_FAULT0, latched hardware kill of EN and CATH), and on-board compliance / open-electrode detection is a safety improvement over "isolated side up" alone. 12 parts, all 0402 except U8; every LCSC number was already in the rev E BOM. |
| Board rebuilt (`tools/route_pcb.py`) with U8 anchored on the bottom west of U2, under the DC-DC body, out of the U1 → U4 SPI corridor. | With U8 in that corridor Freerouting left the SPI lines and CATH open. |

Trip points are ±0.915·V: 11.1 V at ±12 V, 13.9 V at ±15 V, 15.5 V at ±16.8 V, 16.6 V at ±18 V (E1_LS stays ≤ 2.8 V, inside the LM393's Vcc − 1.5 V input range).

## Changes from M2 (M3, 2026-09-28): smaller packages

| Change | Why |
|---|---|
| U6 74HC4053PW (TSSOP-16) → **74HC4053BQ** (DHVQFN-16, 2.5 × 3.5 mm; Nexperia C547007) | Same pinout; courtyard 43.5 → 18.2 mm². The centre pad is not a supply pin ("float or VCC" per the datasheet) and is left unconnected. |
| U7 DG419DY (SOIC-8) → **DG419BDQ** (MSOP-8; Vishay C2673354) | Same pinout; courtyard 41.1 → 23.2 mm². DG419B datasheet, ±15 V: R_on 15 Ω (was 20), charge injection 38 pC (was 60), C_off 12 pF per terminal (was 8), t_ON/t_OFF 62/53 ns. Sims re-run with those values: phase margin 67.3° / 46.2° at 0 / 470 pF cable (was 70.8 / 48.5; still ≥ 45°), train reset unchanged (Vcdl +0.8 / +1.5 mV). |

Routing result on the old 26.5 × 23.5 mm outline: the freed ~43 mm² did **not** get Freerouting to zero (12 seeds, 9–21 open before fix-ups, best 5–6 unconnected after); the greedy placer scattered the signal-path passives. Alternatives considered and rejected the same day: SMA jacks instead of the HAT's BNCs with a wider module (`../SMA_VS_BNC_STUDY.md`), a 2×5 header at one end. **Chosen: extend the module 12.5 mm south over the Pi's port edge** (HAT NOTICE 12).

| Change | Why |
|---|---|
| Outline **26.5 × 36.5 mm**, y 76–112.5 | +12.5 mm of isolated area; the module's underside is ≈ 24 mm above the Pi's PCB, the USB-C / micro-HDMI plugs below it are ≤ 9 mm tall. |
| **Single-sided**: every SMD on the top (`SINGLE_SIDED` in `tools/build_pcb.py`) | JLC Economic assembly. Isolated-side courtyard fill ≈ 36 %. |
| HAT column ends at y 100; horizontal barrier y 100.2–102.2 for x ≥ 121 | The SE corner below it is isolated and holds U8 and its nine resistors as one block. |
| Anchors by signal flow: U2 and the −5 V parts under PS1's body (x 101–108, y 97–103), U3 → U6 → U4 across the top, U5 below them, U7 between the output stage and J1, D2 beside U1's EN/CATH pins, J1 at the new south edge (x 113–116, y 111) | J1 leaves the BACK-button thumb zone; EN/CATH, SPI and the electrode path are all short. |

Result: seed 0 of `tools/route_pcb.py` plus small fix-ups (two dangling stubs from the grid router removed, U6's silk outline moved to F.Fab, ground vias added for C17 and U1 pin 8): **DRC clean, 0 unconnected**, 124 vias, 56 SMD on top, none on the bottom. `renders/m3_placement.png` and `m3_layers.png` show the placement and the copper per layer.

### Fault detector: simulation (`sim/fault.py`, full run 2026-09-28)
- **Timing vs saturation**, 250 µA cathodic-first pairs with the phase width swept through the compliance limit: FAULT_n goes low 7–12 µs before the electrode current starts to fall (1 % below its plateau) and stays low for the rest of the over-compliance phase — 15 V, 15 k/1.6 n: 63.1 µs vs 70.2 µs; 12 V, 10 k/2.2 n: 72.2 vs 80.3; 16.8 V, 10 k/2.2 n: 111.7 vs 123.5; 18 V, 15 k/1.6 n: 81.1 vs 89.9. At the first width that trips, the pulse is only 0.2–3 µs long; a phase 5 µs longer gives ≥ 5 µs. The pair's charge mismatch is still < 0.01 % when FAULT_n fires; it reaches 1 % only 10–15 µs later. So a latched fault at the first trip protects the tissue from the imbalance, not just the amplifier.
- **Open electrode** (Rs → 1 GΩ): U5A slews to the rail and FAULT_n is low 3.8 µs after EN rises, at 12, 15 and 18 V. It stays low (~350 µs) until the hold timer closes the DG419 and the loop recovers.
- **No false trips**: 5-pair 1 kHz trains at 250 µA × 60 µs (10 k/2.2 n), 100 µA × 100 µs (15 k/1.6 n) and 20 µA × 20 µs, with DG419 charge injection, the hold-timer edges and the ISO7761F's 10 µA input load: FAULT_n stays at 4.95 V, and the window margin is ≥ 304 mV (250 µA × 60 µs, cathodic side).
- The divider's load on E1 (100 k) changes nothing measurable in the other sims: phase margin 70.8° / 48.5° (was 70.7° / 48.4°), set-point −0.35 %, compliance 221 / 21.4 µs, train +0.8 / +1.5 mV.
- ngspice note: the LM2903B macro-model integrates in ~2 s per pair with `method=gear` and a 50 ns step; with a 20 ns step or the default trap method it can crawl for minutes once U5A saturates.

**Firmware consequences** (spec §7): keep TIMA0_FAULT0 latched with a short (≤ 1 µs) or no glitch filter, clear it only between trains, and report the fault to the Pi with the train aborted. Start-up behaviour is unchanged (low = not ready until +5V_ISO is up).

## Changes from M3 (M4, 2026-09-29): I²C DAC, dedicated RELEASE line

| Change | Why |
|---|---|
| ISO7761F → **ISO7741F** (3 forward + 1 reverse) + **ISO1640** bidirectional I²C isolator (SOIC-8) | Seven signals across the barrier: EN, CATH, RELEASE, SDA, SCL forward, FAULT_n back. |
| MCP4921 (SPI) + TL431 / R7 / R8 / R9 / C9 reference → **DAC60501Z** (I²C, internal 2.5 V reference ÷ 2 = 0–1.25 V, ±0.1 %), R14 2.00 k → **2.49 k 0.1 %** | I²C needs two lines, SPI three: the third J9 line becomes RELEASE with no connector change. The internal reference is at least as accurate as the TL431 divider and saves 5 parts. Full scale stays ~500 µA. |
| Hold timer (D2 BAT54C, R15, C17) removed; DG419B IN driven by RELEASE | The HAT decides when the electrode is shorted: precise release before the pulse, reset after the pair, and the option to leave the electrode open while recording (no 15 Ω loop in the tissue). Fail-safe unchanged: RELEASE pulled low + isolator default low = shorted. |
| J9.3/4/5 = RELEASE / SDA / SCL (were CS_n / SCK / MOSI; SDA/SCL swapped on 2026-09-29 so the ISO1640 and the DAC connect without crossings); R3 becomes the RELEASE pull-down, R4/R5 removed; R7/R8 and R9/R15 are the I²C pull-ups (4.7 k) | Spec §7. |
| Isolator channel order follows the layout (2026-09-29): U1 A = RELEASE, B = CATH, C = EN (FAULT_n stays on the reverse channel D); U9's "SDA" channel (pins 2/7) carries SCL and its "SCL" channel (3/6) carries SDA — both ISO1640 channels are identical and bidirectional | Straight connections from J8/J9 into U1/U9 and from U9 into the DAC. FAULT_H (J8.5, east) to U1 pin 6 (west) still needs one via: PA6 is the only TIMA0 fault pin on the MCU, so it cannot move to J8.3. |

Board: rebuilt on the M3 outline with U9 straddling the barrier below U1 — **placed only, not routed**; the user routes it by hand. On 2026-09-29 the barrier became a plain L (y 83.58 from the west edge to x 120, then x 120 south to y 95.5, then east to the edge), so the HAT domain is the north strip y < 82.58 plus the east column x > 121, y < 94.5.

### DG419 SHORT: simulation (`../biphasic_stim/sim/p1_dg419.py`, log `p1_dg419.log`)
Model:
- ideal switch with 20 Ω on-resistance;
- 8 pF off-capacitance on each side;
- 60 pC charge injection into **each** terminal. This is a worst case: the datasheet quotes 60 pC typical into 10 nF at ±15 V, measured on one terminal.

The train is five pairs at 1 kHz, with SHORT closing from 20 µs after each pair until 10 µs before the next.

| Train | Cdl at end of every cycle (MOSFET → DG419) | Faradaic charge per cycle (MOSFET → DG419) |
|---|---|---|
| 250 µA × 100 µs | −6.52 mV → **0.00 mV** | −795 → −817 pC |
| 20 µA × 20 µs | −6.52 mV → **0.00 mV** | −9.3 → **−5.6 pC** |

The injection is reset by every closure, so nothing accumulates.

Caveat: the DG419 input has no hysteresis. On HOLD's slow decay the switch may chatter for about 1 µs as it closes. That happens while the electrode is idle and about to be shorted anyway.

## Board (`EStimDaughter.kicad_pcb`)

**Outline and stack-up**
- Outline x 101–127.5, y 76–112.5 (HAT coordinates; M1/M2 ended at y 99.5).
- 4 layers:
  - F.Cu: signal.
  - In1.Cu: split ground planes. GND_H covers the north strip over J8 (y < 82.58) and the east column over J9 (x > 121, y < 94.5); GND_ISO covers the rest. The F/In2/B pours use the same two outlines.
  - In2.Cu: signal.
  - B.Cu: signal.
- 2 mm copper-free barrier on all layers (rule areas `ISOLATION_BARRIER_0/1/2`). Only PS1 (pins 1–2 on the HAT side), U1 (ISO7741F) and U9 (ISO1640) cross it.
- Verified: no pad, track, via or pour of either domain lies on the other side.
- Ground pours on F, In2 and B are confined to their own domain and stitched to the planes.

**Connectors and placement**
- J8 and J9 are male 1×5 headers on B.Cu, at exactly the spec pad positions (verified).
- J1 is a 1×2 right-angle 0.1″ header on the south edge. Its plastic body overhangs the edge by about 2.5 mm, and the pins point south.
- M3: all 56 SMT parts (plus 2 bare test pads) on the top, and 4 through-hole (J1, J8, J9, PS1 DNP). M1/M2 (623 mm²) needed both sides at 54 % / 59 % courtyard fill of the isolated domain.
- The DC-DC (10 mm tall) stands along the west edge; the +5 V LDO and the −5 V zener sit below its body.
- The optional M2.5 hole at (103.5, 96.5) was not added: it collides with the DC-DC body.
- J1 (electrode) is at the far south edge, x 113–116, y 111, clear of the HAT's BACK-button thumb zone.

**Routing and DRC**
- Rules: 0.15 mm clearance, 0.15–0.3 mm tracks, 0.5/0.3 mm vias, vias tented.
- Freerouting, plus a placement-jitter search (Freerouting is deterministic for a given input).
- A ground via fix-up, then a small grid router (`tools/fixroute.py`) for the last few connections.
- M3: DRC clean, 0 unconnected (Freerouting seed 0 plus fix-ups; commit `bbd4e76`). M1 was clean too; M2 on the 23.5 mm outline never got below 4 open items in 27 seeds, and re-feeding a routed board to Freerouting (`COMPLETE_PASSES`) only rips up more.
- M4: placed with `tools/build_pcb.py` (planes and pours from `route_pcb.py`), not routed.
- Most reference designators don't fit at 0.8 mm text and are hidden. Assembly uses the CPL file, not the silkscreen.

**Build:**
```
python tools/route_pcb.py          # a Python that imports pcbnew (KiCad's bundled one on macOS; ~/.venvs/kicad on Ubuntu)
```
Environment: `SEEDS=...` selects the placement variants; `FREEROUTING` is the Freerouting command (default: the macOS app;
on Linux e.g. `FREEROUTING="java -jar ~/Tools/freerouting-2.4.1.jar"`, Freerouting 2.4 needs Java 25); `KICAD_CLI` and
`KICAD_FOOTPRINTS` override the kicad-cli binary and the standard footprint directory when they are not on PATH /
in `/usr/share/kicad`. KiCad's Python needs numpy (`pip install --user`).

Fab files (JLCPCB) are **not** exported yet. That waits for review of `renders/3d_top.png`, `3d_bottom.png` and `3d_iso.png`.
