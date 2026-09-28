# Simulation models

| File / model | Part | Source |
|---|---|---|
| `OPAx192.lib`, subckt `OPAx192` (IN+ IN− VCC VEE OUT) | U5 OPA2192 (both halves) | TI PSpice model, Final 1.7 (26 Aug 2022), https://www.ti.com/lit/zip/SBOM862, unmodified. Needs ngspice's PSpice compatibility mode (`set ngbehavior=psa`); `spice.run()` writes that `.spiceinit` automatically. |

Every other part is modelled inside `../spice.py` from datasheet values:

| Part | Model |
|---|---|
| U4 MCP4921 | Ideal voltage source, `code/4096 × VREF`. The output buffer, INL and offset are not modelled. |
| U3 TL431 + R8/R9 | Folded into VREF = 1.000 V |
| U6 74HC4053 | Voltage-controlled switches driven by EN/CATH, R_on 100 Ω (typical at +5 / −4.7 V) |
| U7 DG419 | Switch on throw 1 (D–S1), closed while IN < 1.6 V (the part has no hysteresis). R_on 20 Ω; 8 pF off-capacitance each side; internal gate ±15 V with a 20 ns time constant; 2 pF injection into each terminal (≈ 60 pC per edge, the datasheet typical). |
| D2 BAT54C | Schottky diode model (IS 2e-7, RS 1.5 Ω, CJO 10 pF) |
| PS1 | Ideal ±V rails |
| Electrode | Randles cell: Rs + (Cdl ∥ Rct) |
