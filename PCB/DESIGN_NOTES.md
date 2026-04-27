# Laser Diode Driver — Current Steering PWM

## Overview
Constant-current laser diode driver with spike-free PWM modulation via
current steering topology. The regulated current from a feedback-controlled
MOSFET (Q1) is steered between the laser diode and a matched dummy load
by a complementary FET pair (Q2a/Q2b), ensuring zero current transients
at the laser. The MCU provides complementary PWM outputs directly — no
inverter is required.

Neither supported laser diode includes an internal monitor photodiode,
so this driver operates in open-loop constant-current mode. For closed-loop
automatic power control (APC), an external photodiode and beamsplitter
would need to be added.

## Supported Laser Diodes

### Sony SLD1255VFR — 641nm Red High Power
- **Part number:** SLD1255VFR
- **Manufacturer:** Sony
- **Package:** TO-38 (Φ3.8 mm), 2-pin + floating case
- **Pin mapping:** Pin 1 = LD anode, Pin 2 = LD cathode, Pin 3 = case (N.C.)
- **Threshold current:** 60 mA typical, 90 mA max
- **Operating current:** 230 mA typical at Po = 150 mW, 280 mA max
- **Forward voltage:** 2.6V typical, 3.0V max (at Po = 150 mW)
- **Output power:** 150 mW max CW (Tc = 0–45°C), 130 mW max CW (Tc = 0–60°C)
- **Slope efficiency:** 0.9 mW/mA typical (above threshold)
- **Monitor PD:** None (case pin is floating/N.C.)
- **Wavelength:** 635–647 nm (641 nm typical)
- **Reverse voltage:** 2V max
- **Laser class:** Class 3B per IEC 60825-1

### OSRAM PLT3 450GB — 450nm Blue Single Mode
- **Part number:** PLT3 450GB (ordering code Q65113A4975)
- **Manufacturer:** ams-OSRAM
- **Package:** TO-38 ICut (Φ3.2 mm), 2-pin + isolated case
- **Pin mapping:** Pin 1 = LD anode, Pin 2 = case (isolated), Pin 3 = LD cathode
- **Threshold current:** 12 mA typical, 30 mA max
- **Operating current:** 87 mA typical at Po = 100 mW, 120 mA max
- **Forward voltage:** 5.2V typical, 6.5V max (at Po = 100 mW)
- **Output power:** 100 mW typical, 110 mW absolute max
- **Monitor PD:** None (case is isolated, no electrical connection)
- **Wavelength:** 440–460 nm (450 nm typical)
- **Reverse voltage:** 2V max
- **Modulation frequency:** ≥100 MHz

### Important: Pin mapping differs between diodes
Both are TO-38 packages with 3 pins, but the pin assignments are NOT identical:

| Pin | SLD1255VFR (red)    | PLT3 450GB (blue)    |
|-----|---------------------|----------------------|
| 1   | LD Anode            | LD Anode             |
| 2   | LD Cathode          | Case (isolated)      |
| 3   | Case (N.C./float)   | LD Cathode           |

Pin 1 (anode) is the same, but the cathode is on different pins. Verify
wiring carefully when swapping between diodes.

## Supply Requirements

### For SLD1255VFR (red):
- **+5V**: Analog supply for LD path and op-amp (≈280 mA max, 1.4W)
- **+3.3V**: MCU logic rail for gate drive pull resistors (< 1 mA)
- Voltage stack at worst case: 3.0V(Vf) + 0.1V(Q2) + 0.3V(Q1) + 0.62V(Rsense) = 4.02V — fits within 5V

### For PLT3 450GB (blue):
- **+9V to +12V**: Analog supply for LD path and op-amp (≈120 mA max)
- **+3.3V**: MCU logic rail for gate drive pull resistors (< 1 mA)
- Voltage stack at worst case: 6.5V(Vf) + 0.1V(Q2) + 0.3V(Q1) + 0.56V(Rsense) = 7.46V — needs >8V supply

## MCU Interface (all 3.3V logic, active-high NMOS)
- **MCU_PWM (complementary pair):**
  - PWM̄ → Q2a gate (laser path): HIGH = laser ON, LOW = laser OFF
  - PWM → Q2b gate (dummy path): HIGH = dummy ON, LOW = dummy OFF
  - Use MCU timer complementary outputs with make-before-break dead-time
- **MCU_VREF**: DAC or filtered PWM output, 0–3.3V
  - Sets laser current: I_LD = VREF / Rsense

### Operating Points — SLD1255VFR (red), Rsense = 2.2Ω

| Target                | Vref    | Current | Optical Power           |
|-----------------------|---------|---------|-------------------------|
| Threshold             | 0.13V   | 60 mA   | ~0 mW (lasing onset)    |
| Low power             | 0.22V   | 100 mA  | ~9 mW                   |
| Medium power          | 0.31V   | 140 mA  | ~45 mW                  |
| High power            | 0.40V   | 180 mA  | ~80 mW                  |
| Nominal (100 mW)      | 0.44V   | 200 mA  | ~100 mW                 |
| Full power (150 mW)   | 0.51V   | 230 mA  | 150 mW (Tc ≤ 45°C)      |
| Abs. max              | 0.62V   | 280 mA  | Do not exceed            |

Optical power estimates based on typical slope efficiency of 0.9 mW/mA
above threshold. Actual power depends on individual device and temperature.
At elevated case temperatures (>45°C), derate to 130 mW max.

### Operating Points — PLT3 450GB (blue), Rsense = 4.7Ω

| Target                | Vref    | Current | Optical Power           |
|-----------------------|---------|---------|-------------------------|
| Threshold             | 0.06V   | 12 mA   | ~0 mW (lasing onset)    |
| Low power             | 0.19V   | 40 mA   | ~20 mW                  |
| Medium power          | 0.31V   | 65 mA   | ~50 mW                  |
| Nominal (100 mW)      | 0.41V   | 87 mA   | 100 mW                  |
| Abs. max              | 0.56V   | 120 mA  | ~110 mW                 |

## Bill of Materials — Red Laser (SLD1255VFR, 5V supply)

| Ref      | Part         | Value/Rating     | Package   | Notes                                          |
|----------|--------------|------------------|-----------|-------------------------------------------------|
| LD1      | SLD1255VFR   | 641nm laser      | TO-38     | Class 3B — eye protection required              |
| U1       | TLV2371      | R-R op-amp       | SOT-23-5  | 2.7–16V, 3 MHz GBW                             |
| Q1       | Si2302CDS    | N-MOSFET         | SOT-23    | Vth ~1V, current source (handles 280 mA)        |
| Q2a,Q2b  | (see note)   | Dual N-MOSFET    | SOT-363   | Must handle ≥280 mA; BSS138DW insufficient      |
| D1       | BAT54        | Schottky diode   | SOT-23    | LD reverse protection                           |
| D2       | 1N4148W      | Si diode         | SOD-123   | Dummy load voltage drop                         |
| Rsense   | —            | 2.2Ω 1%          | 0402      | Current sense (0.51V at 230 mA)                 |
| Rdummy   | —            | 8.2Ω             | 0805      | Matches LD Vf with D2 (640 mW at 280 mA)        |
| R_pd_a   | —            | 10kΩ             | 0402      | Q2a gate pull-down (fail-safe: laser path OFF)  |
| R_pu_b   | —            | 10kΩ             | 0402      | Q2b gate pull-up to 3.3V (fail-safe: dummy ON)  |
| C1       | —            | 100nF X7R        | 0402      | U1 Vcc bypass                                   |
| C2       | —            | 100nF X7R        | 0402      | LD supply bypass                                |
| C_bulk   | —            | 10µF X5R         | 0805      | Bulk decoupling, LD supply                      |
| C3       | —            | 10nF             | 0402      | Vref low-pass filter                            |

**Note on Q2a/Q2b:** The BSS138DW (200 mA rated) is insufficient for the
SLD1255VFR's 280 mA max current. Alternatives include the Si1902DL
(dual NMOS, SOT-363, 1.25A), or two separate Si2302CDS in SOT-23.

**Note on Rdummy power:** At 280 mA through 8.2Ω the resistor dissipates
~640 mW during the PWM off phase. Use an 0805 or 1206 rated for ≥0.5W.
An 0402 is not sufficient.

**Total: 13 components + laser diode** (no PD monitoring)

## Bill of Materials — Blue Laser (PLT3 450GB, 12V supply)

Changes from red laser BOM:

| Ref      | Change                                         |
|----------|-------------------------------------------------|
| LD1      | PLT3 450GB, TO-38 ICut                          |
| Rsense   | 4.7Ω 1% 0402 (0.41V at 87 mA)                  |
| Rdummy   | 36Ω 0603 (~270 mW at 87 mA)                     |
| D2       | 1N4148W ×3 in series (~2.1V total drop)          |
| Q2a,Q2b  | BSS138DW is acceptable (120 mA max < 200 mA)    |

All other components (U1, Q1, D1, R_pd_a, R_pu_b, C1, C2, C_bulk, C3) unchanged.
U1 (TLV2371) operates at 12V instead of 5V — within its 16V max rating.

## Dummy Load Matching

### Red laser (SLD1255VFR at 230 mA, 5V supply):
- LD path: V_LD ≈ 2.6V (typical forward voltage)
- Dummy path: V_D2 + I × Rdummy = 0.7V + 0.230 × 8.2 = 2.59V
- Node A voltage difference during switching: ~10 mV
- Caution: Rdummy dissipates 640 mW at 280 mA max — size accordingly

### Blue laser (PLT3 450GB at 87 mA, 12V supply):
- LD path: V_LD ≈ 5.2V (typical forward voltage)
- Dummy path: 3 × V_D2 + I × Rdummy = 2.1V + 0.087 × 36 = 5.23V
- Node A voltage difference during switching: ~30 mV

## Gate Drive Safety

Q2a and Q2b are NMOS transistors (gate HIGH = ON, gate LOW = OFF).
During MCU power-up, reset, or brownout, GPIO pins go high-impedance.
Floating MOSFET gates can charge unpredictably via stray capacitance
and allow uncontrolled current through the laser.

**Fail-safe pull resistors (required):**
- Q2a gate: 10kΩ pull-down to GND → laser path defaults OFF
- Q2b gate: 10kΩ pull-up to 3.3V → dummy path defaults ON

This ensures that if the current source starts up before the MCU, all
current flows safely into the dummy load. The laser remains dark until
the MCU explicitly asserts complementary PWM outputs.

## Thermal Considerations

### SLD1255VFR (red):
At full power (230 mA, 2.6V, 150 mW optical output), electrical input
is ~600 mW and ~450 mW is dissipated as heat. At max current (280 mA),
dissipation approaches 700 mW. The TO-38 package requires a proper
heatsink with good thermal interface. Derate output power above 45°C
case temperature (130 mW max at Tc = 60°C).

### PLT3 450GB (blue):
At full power (87 mA, 5.2V, 100 mW optical output), electrical input
is ~450 mW and ~350 mW is dissipated as heat. Heat exits only through
the base plate — ensure heatsink contact is on the base, not the can sides.

## Layout Guidelines
- Keep Q1-Rsense-GND current loop area as small as possible
- Place C2 and C_bulk directly at LD anode pad, short path to nearest GND via
- Route MCU signals (PWM, DAC) on opposite board side from supply
- Optional: 100pF–1nF cap from Q1 gate to source for loop compensation
- Estimated PCB area (excl. laser): ~7×9 mm on 2-layer board
- For the red laser at 280 mA, use wider traces (≥0.5 mm) for the current path

## Testing Without Laser
Before connecting the laser diode, substitute a standard red LED in
series with a small resistor to approximate the LD forward voltage drop.
Verify:
1. Voltage across Rsense tracks Vref / Rsense (confirming current regulation)
2. LED switches on/off with PWM signal
3. Probe node A with oscilloscope during PWM transitions (minimal voltage step)

For the red laser, start testing at low Vref (~0.15V / ~70 mA) before
increasing toward operating current. The SLD1255VFR draws significant
current and mistakes at full power are destructive.

## KiCad Schematic Notes
- The schematic uses embedded symbol definitions for portability
- Q2a and Q2b are shown as separate symbols — use a single dual-FET
  package (SOT-363) for matched thresholds where current rating allows
- Op-amp: TLV2371 in KiCad's Amplifier_Operational library; verify
  pinout matches -U or -R suffix variant you select
- Neither laser has a monitor PD — the PD monitoring section from
  earlier revisions has been removed

## Alternative: iC-Haus iC-HK + iC-WK
For a more integrated solution, consider the iC-HK (spike-free laser
switch) paired with iC-WK (CW APC driver) from iC-Haus. Note that the
iC-HK supports up to 700 mA pulsed / 150 mA CW per channel, which is
sufficient for the blue laser but marginal for the red laser at full
power. Check the iC-HK datasheet for CW derating at your duty cycle.
