# kbest e-stim module for LaserHAT Rev 2 — rev M1

Plug-in isolated biphasic constant-current stimulator. Interface is frozen by
`LaserHAT/estim_interface/ESTIM_MODULE_SPEC.md`; HAT-side questions Q1–Q4 in `QUESTIONS.md` are all answered.
The circuit is kbest rev E (`../biphasic_stim/DESIGN_NOTES.md`) with the changes below.

## Interface (HAT coordinates, top view)

| HAT line | MCU | Module use |
|---|---|---|
| J8.1 / J9.1 | GND | GND_H (HAT side of the barrier) |
| J8.2 | +5V | A0515S input (±15 V isolated out) |
| J9.2 | +3V3 | ISO7761F side 1 (VCC1) |
| J8.3 PWM_A | PA21 TIMA0_CCP0 | **EN**: current flows while high |
| J8.4 PWM_B | PA22 TIMA0_CCP1 | **CATH**: 1 = cathodic, 0 = anodic |
| J8.5 GPIO | PA26 TIMA0_FAULT0 | **FAULT_n**: low = isolated side not up |
| J9.3 "DAC" | PA15 GPIO | CS_n (MCP4921) |
| J9.4 "ADC_A" | PA17 GPIO | SCK |
| J9.5 "ADC_B" | PA16 GPIO | MOSI |

Defaults while the MCU pins are Hi-Z:
- pull-downs on EN, CATH, SCK and MOSI;
- a pull-up on CS_n;
- the ISO7761F outputs low when side 1 is unpowered.

So an unconfigured or unpowered HAT means zero current, and the electrode shorted.

## Firmware contract
- **Set-point.** One 16-bit SPI write, mode 0,0, between trains: MCP4921 with BUF = 1 and gain 1×.
  I = code / 4096 × 1.0 V / 2.00 kΩ, so full scale is 500 µA and one LSB is 0.12 µA.
- **Pulse pair.**
  1. CATH high ≥ 5 µs before EN rises.
  2. EN high for t_pw.
  3. EN low for the interphase gap; CATH falls during the gap.
  4. EN high for t_pw.
  5. EN low.
- **SHORT.** SHORT closes by itself about 200 µs after both EN and CATH are low (the HOLD RC: R15, C17). It opens as soon as either line goes high.
- **FAULT_n.** Reads low until the isolated side is powered, and high otherwise. Treat low at start-up as "module not ready" (HAT Q4).

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
| LM393 compliance window (U8, 9 R, 2 C) removed; R19 4.7 k pulls FAULT_n high | The module would not route at ~80 % courtyard fill on the isolated side. User's choice (2026-09-26). FAULT_n now only means "isolated side up". No on-board open-electrode / compliance detection. |
| SHORT: back-to-back 2N7002 + BSS84 level shifter + 10 V zener (Q1–Q4, R16–R18, D3) replaced by one **DG419DY** (C6581, ±15 V SPDT, 20 Ω) | 8 parts become 1. Throw 1 conducts while IN is low, so IN is driven straight from HOLD, and the 74LVC1G14 (U7) and its cap are removed too. BOM goes from 55 to 46 lines. Costs about +$1.77 per board and saves two extended-part fees. |
| TMUX6136 (±15 V switch for the 4053) considered and **not** used | $5.78 against $0.23, to remove three cheap parts (−5 V zener rail). |
| MCP4821 (internal-reference DAC) considered and **not** used | Only SOIC-8 is stocked, so there is no routing gain. It would trade ±0.5 % → ±2 % amplitude accuracy for 5 fewer parts. Still an option if BOM cost matters. |
| ISO7761 forward channels reassigned: A MOSI, B CS, C SCK, D CATH, E EN | Shortest wiring at U1 (free pin swap). |

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
- Outline x 101–127.5, y 76–99.5 (HAT coordinates).
- 4 layers:
  - F.Cu: signal.
  - In1.Cu: split ground planes. GND_H covers the north strip over J8 and the east column over J9; GND_ISO covers the rest.
  - In2.Cu: signal.
  - B.Cu: signal.
- 2 mm copper-free barrier on all layers. Only PS1 (A0515S, pins 1–2 on the HAT side) and U1 (ISO7761F) cross it.
- Verified: no pad, track, via or pour of either domain lies on the other side.
- Ground pours on F, In2 and B are confined to their own domain and stitched to the planes.

**Connectors and placement**
- J8 and J9 are male 1×5 headers on B.Cu, at exactly the spec pad positions (verified).
- J1 is a 1×2 right-angle 0.1″ header on the south edge. Its plastic body overhangs the edge by about 2.5 mm, and the pins point south.
- Parts are on both sides: 15 SMT on top, 27 SMT on the bottom (plus 2 bare test pads), and 4 through-hole (J1, J8, J9, PS1 DNP). This is unavoidable on 623 mm² with the barrier and header corridors.
- The DC-DC (10 mm tall) stands along the west edge.
- The optional M2.5 hole at (103.5, 96.5) was not added: it collides with the DC-DC body.

**Routing and DRC**
- Rules: 0.15 mm clearance, 0.15–0.3 mm tracks, 0.5/0.3 mm vias, vias tented.
- Freerouting, plus a placement-jitter search (Freerouting is deterministic for a given input).
- A ground via fix-up, then a small grid router (`tools/fixroute.py`) for the last few connections.
- DRC: clean, 0 unconnected.
- Most reference designators don't fit at 0.8 mm text and are hidden. Assembly uses the CPL file, not the silkscreen.

**Build:**
```
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 tools/route_pcb.py
```
Environment: `SEEDS=...` selects the placement variants. KiCad's Python needs numpy (`pip install --user`).

Fab files (JLCPCB) are **not** exported yet. That waits for review of `renders/3d_top.png`, `3d_bottom.png` and `3d_iso.png`.
