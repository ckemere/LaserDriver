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

---

## Design Status

### Tested on Breadboard (confirmed working)
The core current-steering topology was validated on a breadboard with the
following components and configuration:

- **U1 (TLV2371):** op-amp feedback loop confirmed; current follows VREF
- **Q1 (Si2302CDS or DMG2302U):** N-MOSFET current source; stable operation
- **Q2a/Q2b:** Spike-free current steering verified; PWM transitions show
  near-zero current glitch at laser node (measured < 5 mV step)
- **D1 (BAT54):** Reverse protection in place; not triggered in normal use
- **D2 (1N4148W):** Dummy load voltage compensation; matching confirmed
- **Rsense:** Current regulation accuracy verified against VREF
- **MSPM0G3507:** Complementary PWM (TIMA0) and DAC (PA12) outputs tested;
  timer-driven ramp and button-triggered pulse operation confirmed in firmware

The above circuit was powered from a bench 5V supply. **No PCB has been
fabricated.** Everything below the dashed line (HAT, boost supply, MSPM0
connections to Pi) is proposed but untested.

### Proposed (Not Yet Tested)
The following additions are included in the HAT design and are based on
standard practice / datasheet recommendations, but have not been
breadboard-validated:

| Item | Status | Notes |
|------|--------|-------|
| MT3608 boost (5V→12V) | Proposed | Standard MT3608 application circuit; values from datasheet |
| Fail-safe pull resistors (R_pd_a, R_pu_b) | Proposed | Analytically correct; not verified on bench |
| Extra decoupling caps (C1, C2, C_bulk, C_VDDA) | Proposed | Standard bypass practice |
| C3 (10nF VREF filter) | Proposed | RC filter on DAC output; not yet tested |
| DMG2305UX P-MOSFET power switch for MSPM0 | Proposed | Standard power-switching application |
| Si1902DL for Q2 (red laser, 280 mA) | Proposed | Required—BSS138DW is insufficient at 280 mA |
| HAT EEPROM (AT24C256C) | Proposed | Standard Pi HAT requirement |
| CH340N USB-C UART interface | Proposed | No-crystal mode per datasheet |
| MSPM0 on Pi 3V3 rail | Proposed | Draws ~5–8 mA; Pi 3V3 can supply this |

**Key risk areas to verify during bring-up:**
1. Boost converter output voltage and stability under load (target 11.8V)
2. P-MOSFET gate timing — ensure Pi GPIO17 is low on boot (MSPM0 ON by default)
3. SB1/SB2 solder bridge position when switching between Pi-UART and USB-C modes
4. MSPM0 3V3 draw — measure to confirm < 20 mA total (Pi limit per HAT spec)

---

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

---

## Supply Requirements

### For SLD1255VFR (red):
- **+5V (or +12V from boost):** Analog supply for LD path and op-amp (≈280 mA max, 1.4W)
- **+3.3V:** MCU logic rail for gate drive pull resistors (< 1 mA from laser path)
- Voltage stack at worst case (5V supply): 3.0V(Vf) + 0.1V(Q2) + 0.3V(Q1) + 0.62V(Rsense) = 4.02V — fits within 5V
- Voltage stack at worst case (12V supply): same; extra headroom available, not needed

### For PLT3 450GB (blue):
- **+12V from boost:** Analog supply for LD path and op-amp (≈120 mA max)
- **+3.3V:** MCU logic rail for gate drive pull resistors (< 1 mA)
- Voltage stack at worst case: 6.5V(Vf) + 0.1V(Q2) + 0.3V(Q1) + 0.56V(Rsense) = 7.46V — requires ≥8V supply; 12V provides sufficient margin
- U1 (TLV2371) at 12V: within 16V absolute max — safe

### Boost Converter (MT3608, 5V→12V)
- Vin = 5V (USB/Pi 5V rail via VBUS)
- Vout = 0.6V × (1 + R_FB1/R_FB2) = 0.6 × (1 + 187kΩ/10kΩ) = 11.82V ≈ 12V
- R_FB1 = 187kΩ 1%, R_FB2 = 10kΩ 1%
- L1 = 22µH (ferrite shielded)
- D_BOOST = SS14 (Schottky, 1A, 40V)
- C_IN = 10µF + 100nF; C_OUT = 10µF 16V + 100nF 16V
- R_EN = 100kΩ to Vin (always enabled)
- Efficiency estimate: ~85–90% at 100 mA load

---

## MCU Interface (all 3.3V logic, active-high NMOS)
- **MCU_PWM (complementary pair):**
  - PWM → Q2a gate (laser path): HIGH = laser ON, LOW = laser OFF
  - PWM̄ → Q2b gate (dummy path): HIGH = dummy ON, LOW = dummy OFF
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

---

## Bill of Materials — Red Laser (SLD1255VFR, 12V boost supply)

| Ref        | Part           | Value/Rating      | Package   | Notes                                             |
|------------|----------------|-------------------|-----------|---------------------------------------------------|
| LD1        | SLD1255VFR     | 641nm laser       | TO-38     | Class 3B — eye protection required                |
| U_BOOST    | MT3608         | Boost converter   | SOT-23-6  | 5V→12V; R_FB1=187k, R_FB2=10k, L1=22µH           |
| D_BOOST    | SS14           | Schottky 1A 40V   | SMA       | Boost output rectifier                            |
| U1         | TLV2371        | R-R op-amp        | SOT-23-5  | 2.7–16V, 3 MHz GBW; safe at 12V                  |
| Q1         | Si2302CDS      | N-MOSFET          | SOT-23    | Vth ~1V, current source (handles 280 mA)          |
| Q2a,Q2b    | Si1902DL       | Dual N-MOSFET     | SOT-363   | 1.25A rated — required for 280 mA (BSS138DW insufficient) |
| D1         | BAT54          | Schottky diode    | SOT-23    | LD reverse protection                             |
| D2         | 1N4148W        | Si diode          | SOD-123   | Dummy load voltage drop                           |
| Rsense     | —              | 2.2Ω 1%           | 0402      | Current sense (0.51V at 230 mA)                   |
| Rdummy     | —              | 8.2Ω              | 0805      | Matches LD Vf with D2; 640 mW at 280 mA — ≥0805  |
| R_pd_a     | —              | 10kΩ              | 0402      | Q2a gate pull-down (fail-safe: laser path OFF)    |
| R_pu_b     | —              | 10kΩ              | 0402      | Q2b gate pull-up to 3.3V (fail-safe: dummy ON)    |
| C1         | —              | 100nF X7R         | 0402      | U1 Vcc bypass                                     |
| C2         | —              | 100nF X7R         | 0402      | LD supply bypass                                  |
| C_bulk     | —              | 10µF X5R          | 0805      | Bulk decoupling, LD supply                        |
| C3         | —              | 10nF              | 0402      | Vref low-pass filter (RC with series resistor)    |
| C_IN1      | —              | 10µF 10V X5R      | 0805      | Boost input bulk cap                              |
| C_IN2      | —              | 100nF 10V X7R     | 0402      | Boost input HF bypass                             |
| C_OUT1     | —              | 10µF 16V X5R      | 0805      | Boost output bulk cap                             |
| C_OUT2     | —              | 100nF 16V X7R     | 0402      | Boost output HF bypass                            |
| R_FB1      | —              | 187kΩ 1%          | 0402      | Boost feedback, sets Vout                         |
| R_FB2      | —              | 10kΩ 1%           | 0402      | Boost feedback reference divider                  |
| L1         | —              | 22µH shielded     | 5×5 mm    | Boost inductor; Isat ≥ 0.5A                       |
| J_LD       | —              | 3-pin TO-38 socket| 0.1" THT  | Laser diode connector                             |

**Note on Q2a/Q2b:** The BSS138DW (200 mA rated) is insufficient for the
SLD1255VFR's 280 mA max current. Alternatives include the Si1902DL
(dual NMOS, SOT-363, 1.25A), or two separate Si2302CDS in SOT-23.

**Note on Rdummy power:** At 280 mA through 8.2Ω the resistor dissipates
~640 mW during the PWM off phase. Use an 0805 or 1206 rated for ≥0.5W.
An 0402 is not sufficient.

## Bill of Materials — Blue Laser (PLT3 450GB, 12V boost supply)

Changes from red laser BOM:

| Ref        | Change                                           |
|------------|--------------------------------------------------|
| LD1        | PLT3 450GB, TO-38 ICut                           |
| Rsense     | 4.7Ω 1% 0402 (0.41V at 87 mA)                   |
| Rdummy     | 36Ω 0603 (~270 mW at 87 mA)                      |
| D2         | 1N4148W ×3 in series (~2.1V total drop)           |
| Q2a,Q2b    | BSS138DW acceptable (120 mA max < 200 mA)        |

All other components unchanged.

---

## Dummy Load Matching

### Red laser (SLD1255VFR at 230 mA, 12V supply):
- LD path: V_LD ≈ 2.6V (typical forward voltage)
- Dummy path: V_D2 + I × Rdummy = 0.7V + 0.230 × 8.2 = 2.59V
- Node A voltage difference during switching: ~10 mV
- Caution: Rdummy dissipates 640 mW at 280 mA max — size accordingly

### Blue laser (PLT3 450GB at 87 mA, 12V supply):
- LD path: V_LD ≈ 5.2V (typical forward voltage)
- Dummy path: 3 × V_D2 + I × Rdummy = 2.1V + 0.087 × 36 = 5.23V
- Node A voltage difference during switching: ~30 mV

---

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

---

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

---

## Layout Guidelines
- Keep Q1-Rsense-GND current loop area as small as possible
- Place C2 and C_bulk directly at LD anode pad, short path to nearest GND via
- Route MCU signals (PWM, DAC) on opposite board side from supply
- Optional: 100pF–1nF cap from Q1 gate to source for loop compensation
- For the red laser at 280 mA, use wider traces (≥0.5 mm) for the current path
- Boost converter: place L1, D_BOOST, C_OUT close together; keep switching node short
- Boost output (12V) runs at up to 500 mA peak inductor current — route away from analog signals

---

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

---

## Raspberry Pi HAT Design (LaserHAT/)

The HAT design adds the following blocks to the core laser driver circuit:

### MSPM0G3507 Controller
- Powered from Pi 3V3 rail via a DMG2305UX P-MOSFET power switch
- Pi GPIO17 drives Q_PWR gate through 1kΩ; 10kΩ pull-down → MSPM0 ON by default
- Pi GPIO17 HIGH → Q_PWR OFF → MSPM0 powered down (forced reset/power cycle)
- MSPM0 draws ~5–8 mA; well within Pi 3V3 50 mA headroom
- SWD debug (SWCLK/SWDIO/NRST) routed to a 5-pin 0.1" header for OpenOCD

### BNC Trigger Input
- BNC connector replaces the push button from the breadboard design
- 50Ω termination resistor (DNP by default — leave open for standard logic signals)
- Trigger signal routed to both PB21 on MSPM0 and Pi GPIO (GPIO26 suggested)

### UART Connection
- PA10 (UART0_TX) / PA11 (UART0_RX) connected to Pi GPIO14/15 (Pi UART TX/RX)
- SB1/SB2 solder bridges: installed = CH340N USB-C active; removed = Pi UART active
- Prevents bus contention when both Pi and CH340N connected

### HAT EEPROM
- AT24C256C at I2C address 0x50 (A0=A1=A2=GND)
- Connected to Pi ID_SD/ID_SC (GPIO0/GPIO1)
- 4.7kΩ pull-ups on SDA/SCL
- Required per Raspberry Pi HAT specification

### USB-C Standalone Mode
- CH340N SOIC-8 (no crystal) provides USB-C UART when Pi is absent
- 5.1kΩ CC1/CC2 resistors for USB-C UFP (device) detection
- 1MΩ shield-to-GND isolation resistor
- SB1/SB2 removed to disconnect CH340N from MSPM0 UART when Pi is in use

---

## KiCad Schematic Notes
- The HAT schematic is a 4-sheet hierarchical design in `LaserHAT/`
- Root sheet (`LaserDriver.kicad_sch`) contains Pi GPIO header, power switch, BNC, SWD header, EEPROM
- Sheet 2 (`laser_driver_circuit.kicad_sch`): MT3608 boost + laser driver circuit
- Sheet 3 (`mspm0_controller.kicad_sch`): MSPM0G3507RGZR with decoupling
- Sheet 4 (`usb_uart.kicad_sch`): CH340N USB-C bridge with solder bridges
- Q2a and Q2b are shown as separate symbols — use Si1902DL (SOT-363) for
  matched thresholds in the red laser configuration

## Alternative: iC-Haus iC-HK + iC-WK
For a more integrated solution, consider the iC-HK (spike-free laser
switch) paired with iC-WK (CW APC driver) from iC-Haus. Note that the
iC-HK supports up to 700 mA pulsed / 150 mA CW per channel, which is
sufficient for the blue laser but marginal for the red laser at full
power. Check the iC-HK datasheet for CW derating at your duty cycle.
