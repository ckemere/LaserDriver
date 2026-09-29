# E-stim module for LaserHAT Rev 2 (rev M3)

Isolated, charge-balanced, biphasic constant-current stimulator on a plug-in daughter board for the LaserHAT Rev 2
(Raspberry Pi HAT with an MSPM0G3507). It is one of the HAT's two daughter boards; the other is the laser-diode module.
Interface per `LaserHAT/estim_interface/ESTIM_MODULE_SPEC.md`.

> Imported into `LaserHAT/EStimDaughter/` from `kbest/estim_module` (kbest commit `9200766`). It was renamed to match `LaserDaughter/`, with the project files and script paths updated. The kbest repo remains the history: `DESIGN_NOTES.md`'s references to `../biphasic_stim` (rev E, the circuit this module derives from) point there.

Status (rev M3, 2026-09-28): schematic complete and verified (ERC 0, netlist = `sch_parts.py`); PCB on the new 26.5 × 36.5 mm outline, **single-sided**, routed, **DRC clean, 0 unconnected**. Fab files in `../fab/EStimDaughter` regenerated.

**Files**
- `EStimDaughter.kicad_pro`, `.kicad_sch`, `.kicad_pcb`: the design.
- `estim.kicad_sym` + `sym-lib-table`, `estim.pretty/` + `fp-lib-table`: project symbol and footprint libraries, including the DC-DC footprint and its 3D model. Keep them next to the design files.
- `bom_EStimDaughter.csv`: BOM with LCSC part numbers.
- `renders/`: `3d_top.png`, `3d_bottom.png`, `3d_iso.png`, and `3d_top_ps1_dnp.png` (converter not fitted).
- `sim/`: ngspice simulation of the final circuit, with its one vendor model (section 5).

---

## 1. What the module does

```
 HAT side (GND_H)            ║ barrier ║            isolated side (GND_ISO)
                             ║  2 mm   ║
 J8.2 +5V ──────────────► PS1 isolated DC-DC ────► ±15 V ──► LDO → +5V_ISO,  zener → −5V_ISO
                             ║         ║
 J8.3 PWM_A = EN   ──┐       ║         ║        ┌─► 74HC4053: CATH selects +VSET / −VSET, EN selects that or 0 V
 J8.4 PWM_B = CATH ──┤  U1   ║ ISO7761F║ ───────┤
 J9.3 CS_n  ─────────┤ 5 fwd ║         ║        ├─► MCP4921 12-bit DAC (VREF 1.000 V: TL431 + 0.1 % divider)
 J9.4 SCK   ─────────┤ 1 rev ║         ║        │      └─► OPA2192 B: unity inverter makes −VSET
 J9.5 MOSI  ─────────┘       ║         ║        │
 J8.5 FAULT_n ◄──────────────╫─────────╫────────┤  LM393 window on the electrode voltage: low = compliance /
                             ║         ║        │  open-electrode fault (also low while the isolated side is unpowered)
                             ║         ║
                             ║         ║  OPA2192 A: floating-load V→I; I = V_IN / 2.00 kΩ → J1 E1 / E2
                             ║         ║  DG419 SHORT switch across E1–E2: closed ~200 µs after EN and CATH are both low
```

| Parameter | Value |
|---|---|
| Waveform | Cathodic-first biphasic. Both phases come from one set-point, so they're matched by construction. |
| Current | 0–500 µA, 12-bit (0.12 µA/LSB). Intended range 20–250 µA. |
| Phase width / interphase gap | 20–100 µs each, timed by the HAT |
| Compliance | About ±13.5 V from the ±15 V rails. Into the worst-case electrode (15 kΩ, 1.6 nF) that allows about 220 µs at 100 µA but only about 21 µs at 500 µA. High currents with long phases need a lower-impedance electrode. |
| Charge balance | 0.003–0.07 % phase mismatch (simulated). A passive short resets the electrode after every pair. |
| Electrode (design load) | Tungsten microwire: Rs 5–15 kΩ, Cdl 1.6–3.2 nF, Rct 2 MΩ |
| Isolation | Functional, to break 60 Hz ground loops (not a safety barrier). Separate grounds, with a 2 mm copper-free gap on every layer. Only the DC-DC (PS1) and the digital isolator (U1) cross it. |
| HAT power | +5 V about 0.1–0.2 A (budget 500 mA). +3.3 V only for the isolator's HAT side (a few mA). |

### HAT interface

| HAT pin | MCU | Module signal |
|---|---|---|
| J8.1, J9.1 GND | — | GND_H |
| J8.2 +5V | — | DC-DC input |
| J8.3 PWM_A | PA7 TIMA0_CCP1 | **EN**: current flows while high |
| J8.4 PWM_B | PA12 TIMA0_CCP3 | **CATH**: 1 = cathodic, 0 = anodic |
| J8.5 GPIO | PA6 TIMA0_FAULT0 | **FAULT_n**: low = fault (electrode voltage past the compliance window, open electrode) or isolated side not powered (module not ready) |
| J9.2 +3V3 | MSPM0_3V3 | ISO7761F VCC1 |
| J9.3 "DAC" | PA15 as GPIO | CS_n |
| J9.4 "ADC_A" | PA17 as GPIO | SCK |
| J9.5 "ADC_B" | PA22 as GPIO | MOSI |

MCU pins per `../REV2_NOTES.md` (HAT NOTICE 10 in `../estim_interface/QUESTIONS.md`); the J8/J9 pinout itself is frozen.

### Firmware contract
- **Amplitude.** One 16-bit SPI write (mode 0,0, bit-banged, any clock up to a few MHz) between trains, to the MCP4921 with BUF = 1 and gain 1×.
  I = code / 4096 × 1.000 V / 2.00 kΩ.
- **Pulse pair.**
  1. CATH high ≥ 5 µs before EN rises.
  2. EN high for t_pw.
  3. EN low for the gap; CATH falls during the gap.
  4. EN high for t_pw.
  5. EN low.
- **SHORT** is automatic. The electrode is shorted about 200 µs after both EN and CATH are low, and released as soon as either rises.
- **FAULT_n** reads low until the isolated supply is up (treat that as "not ready"), and pulses low whenever the electrode voltage leaves the compliance window during a pulse (see *Fault detector* below). The HAT latches TIMA0_FAULT0 (forces PWM_A/B low) and clears it between trains; a fault during a train therefore ends the train, and the Pi is told.
- **Fail-safe.** EN, CATH, SCK and MOSI are pulled low, and CS_n is pulled high, before the isolator. The ISO7761F outputs low when its HAT side is unpowered. So an unconfigured or unpowered HAT gives zero current with the electrode shorted.

### Fault detector (rev M2)
U8, an LM393, compares a scaled copy of the electrode-side voltage E1 (E1_LS = 0.0767·E1 + 1.42 V, R20/R21/R22 with C18) with two thresholds derived from the rails (TH_P from +V, TH_N from −V, each 110 k / 12 k / 27 k). Both open-collector outputs pull FAULT_n low (R19 4.7 k to +5V_ISO) while |E1| > 0.915·V, i.e. 13.9 V at ±15 V, 11.1 V at ±12 V, 16.6 V at ±18 V. The thresholds track the rails, so the detector needs no adjustment between the DC-DC converter and battery packs. Simulated (`sim/fault.py`): it fires 7–12 µs before the electrode current starts to collapse and stays low for the rest of the over-compliance phase (≥ 3 µs); an open electrode trips it 3.8 µs after EN rises; in-compliance trains never come within 0.3 V of the window. The HAT's TIMA0 fault input is latched and forces EN and CATH low, so a train that hits compliance is cut at the first phase that does; firmware should keep the fault input's glitch filter short (≤ 1 µs) or off, clear the latch only between trains, and report the event to the Pi. Because the same line is the module-ready flag, the start-up behaviour (low until +5V_ISO is up) is unchanged.

---

## 2. Fab and assembly parameters

| Item | Value |
|---|---|
| Outline | **26.5 × 36.5 mm** rectangle, drawn in **HAT board coordinates**: x 101.0–127.5, y 76.0–112.5 mm. The module extends 12.5 mm past the HAT's south edge (y = 100), over the Pi's USB-C / micro-HDMI edge (HAT NOTICE 12). J8/J9 pads land exactly on the HAT sockets. |
| Layers | **4**: F.Cu signal / In1.Cu split ground planes (GND_H \| GND_ISO) / In2.Cu signal / B.Cu signal |
| Thickness | 1.6 mm |
| Track / clearance | 0.15 mm minimum each (signal 0.2 mm, power 0.3 mm) |
| Vias | 124, all 0.5 mm pad / 0.3 mm drill, tented. No blind or buried vias. |
| Hole-to-hole / copper-to-edge | ≥ 0.25 / ≥ 0.3 mm |
| Plated holes | 1.0 mm (headers and DC-DC) |
| Fiducials / tooling / mounting holes | None |
| Silkscreen | 0.8 mm text. Most reference designators are hidden for lack of room, so assembly goes by the CPL. PS1's pads are labelled 5V / GND / −V / 0V / +V. |
| Surface finish, colour | Not specified |

### Assembly

| Side / type | Parts |
|---|---|
| Top SMT (56) | U1 ISO7761F (SSOP-16), U2 TLV76050 (SOT-23), U3 TL431 (SOT-23), U4 MCP4921 (MSOP-8), U5 OPA2192 (VSSOP-8), U6 74HC4053BQ (DHVQFN-16), U7 DG419BDQ (MSOP-8), U8 LM393 (VSSOP-8), D1 (SOD-323), D2 (SOT-23), 44 passives, plus two bare test pads TP1 ISENSE / TP2 GND_ISO |
| Bottom SMT | **none** (single-sided assembly, JLC Economic tier) |
| Through-hole, hand-soldered | **J8, J9**: male 1×5 0.1" headers on the **underside**, into the HAT sockets. **J1**: 1×2 0.1" right-angle electrode header on the south edge. Its plastic body overhangs the edge by about 2.5 mm and its pins by about 9 mm. |
| **DNP** | **PS1**, the isolated 5 V → ±15 V DC-DC (SIP, pins 1 2 4 5 6 on 0.1", 10 mm tall, top side). Fit one of: RECOM **RB-0515D/HP** (Mouser; verified drop-in), Mornsun A0515S-1WR3, or LCSC C5369388 (YLPTEC). Solder it or use a machined-pin SIP socket. Alternatively leave it empty and wire two battery packs: + → **+V**, centre tap → **0V**, − → **−V** (up to ±18 V; draw about 10 mA per rail). |
| LCSC parts | 29 unique (M1: 25; M2 adds LM393DGKR C34440 and the 12 k / 27 k / 110 k 0402 resistors). Stock checked 2026-09-26 for the M1 set; re-run `tools/lcsc_check.py` before ordering. |

Extended parts:
- ICs: ISO7761FDBQR, TLV76050DBZR, MCP4921-E/MS, OPA2192IDGKR, 74HC4053PW, DG419DY, TL431, LM393DGKR.
- Diodes: BAT54C, BZT52C4V7S.
- Resistors: 0.1 % 15.0k, 10.0k and 2.00k (0603); 47 Ω (0402).
- Capacitors: 1 µF 50 V (0603 and 0805), 4.7 µF (0603), 2.2 nF (0402).

**Panelization notes**
- The design needs **4 layers**; assembly is **single-sided** since M3 (the 23.5 mm outline of M1/M2 could not be routed single-sided: `../SMA_VS_BNC_STUDY.md`).
- Copper comes within 0.3 mm of the edge. Prefer tab routing with mouse bites to V-scoring.
- Leave a routed gap (not a V-score) along the south edge, where J1 overhangs. J1 is hand-fitted after depanelizing.
- Put fiducials and tooling holes on the panel rails.

---

## 3. Design decisions

| Decision | Reason |
|---|---|
| Digital-only isolation: bit-banged SPI to an isolated DAC | No analog signal crosses the barrier, and the amplitude is exact. A PWM-filtered set-point was evaluated and rejected: amplitude spread, and offset at low codes. |
| ±VSET from one DAC through an inverter, selected by a 74HC4053 | Both phases derive from the same set-point, which gives 0.003–0.07 % charge balance without trimming |
| Floating-load V→I op-amp (OPA2192, ±15 V) with a 2.00 kΩ 0.1 % sense resistor | Current accuracy is set by one precision resistor. The ±15 V rails give about ±13.5 V compliance for 5–15 kΩ electrodes at up to 500 µA. |
| C16, 1 µF DC block in series with the electrode | Safety: no DC can reach tissue under any single fault (stuck EN, latched op-amp, bad DAC code). The worst case is C16 × V ≈ 15 µC, after which the current stops. Normal pulses cost only about 50 mV of compliance. The trade-off: U5A's DC feedback comes from the SHORT closing between pulses (see open items). |
| 500 µA full scale (R14 = 2.00 kΩ, VREF 1.000 V) | Set by the electrode, not the circuit. I_max ≈ 14.5 V / (Rs + 2 kΩ + pw/Cdl): about 180–250 µA at 100 µs and 490–690 µA at 20 µs for microwires. For larger or coated electrodes, lower R14 (1.00 k → 1 mA, 499 Ω → 2 mA full scale); nothing else changes. High current on microwires would need higher rails, which means a different op-amp, switch and converter. |
| TL431 reference + 0.1 % divider for the DAC's 1.000 V VREF | ±0.5 % amplitude accuracy. A DAC with an internal reference would lose accuracy (about ±2 %) and needs a larger package. |
| DG419 analog switch for the passive SHORT (E1 to E2) | One ±15 V part, driven straight from the hold timer. Simulated: electrode charge resets to 0 mV every cycle, and the switch's charge injection doesn't accumulate. |
| Hold timer (BAT54C OR + RC, ~200 µs) derives SHORT from EN/CATH | No extra HAT signal needed. The electrode is shorted whenever the module is idle. |
| ISO7761F (5 forward + 1 reverse channel, fail-safe low) | Fits all five control lines plus FAULT_n. Its default outputs are the safe state. |
| FAULT_n from an LM393 window on E1 (rev E circuit, restored in M2) | Open-collector, so the same line is also the module-ready flag: R19 is unpowered until the isolated side is up. Trip points track the rails (±0.915 V), so the detector works from ±12 V converters to ±18 V battery packs without a change. |
| PS1 is DNP | Keeps the choice open between the DC-DC and batteries. Batteries avoid the converter's switching common-mode noise, which couples through 20–75 pF of isolation capacitance. The isolator adds only about 2 pF. |
| 4 layers, parts on the top only (M3) | The split ground planes on In1.Cu make the isolated domain routable; the 12.5 mm southward extension (26.5 × 36.5 mm) is what made single-sided assembly possible — M1/M2 needed both sides on 23.5 mm. Isolation itself comes from the copper-free barrier, not the layer count. |
| Right-angle 0.1" electrode header on the south edge | The spec's accessible edges are south and west. The cable exits away from the HAT. |

---

## 4. Open items
- **Fab files:** `../fab/EStimDaughter` (gerbers, drill, JLC BOM and CPL). Check part rotations in JLC's placement preview, especially the DHVQFN (U6) and MSOP parts.
- **Enclosure clearance:** the module overhangs the HAT's south edge by 12.5 mm and J1 overhangs the module's south edge by another ~9 mm, above the Pi's USB-C / HDMI cable plugs.
- **Electrode cable:** keep E1-to-ground capacitance under 500 pF (twisted pair, shield tied to E2) for output-stage stability.
- **Bench check:** the DG419's control input has no hysteresis. It may chatter for about 1 µs as the SHORT closes on the slow hold-timer edge. That was harmless in simulation.
- **U5A DC operating point:** C16 blocks DC, so while the SHORT is open U5A has no DC feedback. Its output drifts at about Vos / (R14 · C16), which is up to about 12 V/s at the OPA2192's ±25 µV maximum offset. The SHORT re-closes and resets it whenever EN and CATH are both low for ≥ ~250 µs. That happens every cycle at pair rates up to roughly 1.5 kHz, so normal use is fine. A continuous faster train lasting more than about 0.1 s should be simulated (extend `sim/train.py`) or avoided.
- **PS1 availability:** one distributor lists the Mornsun A0515S-1WR3 as NRND/obsolete. The RECOM RB-0515D/HP is the verified alternative.

---

## 5. Simulation (`sim/`)

A self-contained ngspice model of the final circuit, with part names matching the schematic. `sim/spice.py` builds the netlists:
- **U5A/U5B (OPA2192):** TI's PSpice macro-model, `sim/models/OPAx192.lib`.
- **U8 (LM393):** TI's LM2903B PSpice macro-model, `sim/models/LM393_LM2903B.lib` (used by `fault.py`; the other scripts model only the detector's divider load on E1).
- **Everything else** is modelled from datasheet values: DAC, 74HC4053, DG419 with charge injection, BAT54C hold timer, rails, the ISO7761F input load on FAULT_n, and a Randles-cell electrode. `sim/models/README.md` lists every model.

**Requirements**
- ngspice ≥ 40. It's found on `PATH`, or set `NGSPICE=/path/to/ngspice`.
- Python 3 with `numpy` and `matplotlib`.

`spice.run()` puts ngspice in PSpice-compatible mode itself, by writing a `.spiceinit` with `set ngbehavior=psa` next to each temporary deck. No other setup is needed.

**Running**
```bash
cd sim
python stability.py      # U5A loop gain / phase margin vs cable capacitance and electrode   (~1 min)
python setpoint.py       # current accuracy and cathodic/anodic matching, 20-500 uA        (~1 min)
python compliance.py     # max phase width before saturation vs current, 4 rail/electrode cases (~2-5 min)
python train.py          # 5-pair 1 kHz trains with the real SHORT path vs without          (~2-5 min)
python fault.py          # fault detector: trip points, timing vs saturation, open electrode, false trips (~10 min)
```
Add `--quick` to any script for a few-second smoke test with fewer cases. Each script prints a table and writes
`sim/results/<name>.json` and `<name>.png`. Rails default to ±15 V (`RAIL` in `spice.py`; 16.8 V models two 4S Li-ion packs).
Component values are in `VALUES` in `spice.py`, so change them there.

**Expected results.** These were checked in `--quick` mode when the model was written; the full sweeps haven't been run yet.

| Script | Check | Quick-mode result |
|---|---|---|
| `stability.py` | Phase margin ≥ 45° for cable ≤ 500 pF | 70.7° with no cable, 48.4° with 470 pF (Rs 10 k, Cdl 2.2 n) |
| `setpoint.py` | Error vs ideal, and phase matching | 250 µA: −0.35 % in both phases (op-amp tracking of the Cdl ramp, ≈ 1/(2π·GBW·Cdl·R14)), pair charge mismatch −0.006 % |
| `compliance.py` | Max phase width before saturation, worst electrode | 100 µA: 221 µs. 500 µA: 21.5 µs. |
| `train.py` | Charge left on the electrode each cycle | With SHORT, Vcdl after each cycle is +0.8 mV, +1.5 mV, … This is C16 absorbing the net faradaic charge; it converges over about C16·Rct ≈ 2 s. Without SHORT it ratchets to about −1 V. |
| `fault.py` (full run, 2026-09-28) | FAULT_n fires before U5A runs out of headroom, never on an in-compliance train | Trip points ±0.915 V (13.9 V at ±15 V). 250 µA phase-width sweeps: FAULT_n goes low 7–12 µs before the electrode current starts to fall (15 V worst electrode: 63.1 vs 70.2 µs; 12 V: 72.2 vs 80.3; 16.8 V: 111.7 vs 123.5; 18 V: 81.1 vs 89.9), while the pair mismatch is still < 0.01 %. Open electrode: low 3.8 µs after EN at 12–18 V. Trains at 250 µA × 60 µs, 100 µA × 100 µs and 20 µA × 20 µs: FAULT_n stays at 4.95 V, ≥ 0.3 V of window margin. |

Not modelled:
- component tolerances (0.1 % resistors, TL431, DAC INL/offset);
- the MCP4921's output buffer near 0 V;
- the isolated converter's ripple and common-mode noise.

