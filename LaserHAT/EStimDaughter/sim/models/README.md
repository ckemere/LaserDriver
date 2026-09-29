# Simulation models

| File / model | Part | Source |
|---|---|---|
| `OPAx192.lib`, subckt `OPAx192` (IN+ IN− VCC VEE OUT) | U5 OPA2192 (both halves) | TI PSpice model, Final 1.7 (26 Aug 2022), https://www.ti.com/lit/zip/SBOM862, unmodified. Needs ngspice's PSpice compatibility mode (`set ngbehavior=psa`); `spice.run()` writes that `.spiceinit` automatically. |
| `LM393_LM2903B.lib`, subckt `LM2903B` (IN+ IN− Vcc GND OUT) | U8 LM393 (both comparators) | TI "LM393 PSpice model" Rev B, https://www.ti.com/lit/zip/SLCJ016, unmodified (TI ships the LM2903B/LM393B model for the whole LM393 family, shared datasheet SLCS005). Open-collector output; the output floats to mid-supply if an input leaves the common-mode range (modelled behaviour). Integrates fastest with `.options method=gear` (`fault.py`). |

Every other part is modelled inside `../spice.py` from datasheet values:

| Part | Model |
|---|---|
| U4 DAC60501 | Ideal voltage source, `code/4096 × 1.25 V` (internal 2.5 V reference ÷ 2). The output buffer, INL and offset are not modelled. |
| U6 74HC4053 | Voltage-controlled switches driven by EN/CATH, R_on 100 Ω (typical at +5 / −4.7 V) |
| U7 DG419B | Switch on throw 1 (D–S1), closed while IN < 1.6 V (the part has no hysteresis). R_on 15 Ω; 12 pF off-capacitance each side; internal gate ±15 V with a 20 ns time constant; 1.3 pF injection into each terminal (≈ 38 pC per edge, the DG419B datasheet typical; the original DG419 was 20 Ω / 8 pF / 60 pC). |
| D2 BAT54C | Schottky diode model (IS 2e-7, RS 1.5 Ω, CJO 10 pF) |
| Fault detector passives, R19, ISO7761F input | R20–R28, C18 as drawn; R19 4.7 kΩ pull-up to +5V_ISO; the isolator input as a 10 µA sink while FAULT_n is high (datasheet maximum input current) |
| PS1 | Ideal ±V rails |
| Electrode | Randles cell: Rs + (Cdl ∥ Rct) |
