# Laser Diode Driver — Pi HAT Design

## Overview

Constant-current laser diode driver with spike-free PWM modulation via current-steering
topology. The regulated current from a feedback-controlled MOSFET (Q1) is steered between
the laser diode and a matched dummy load by a complementary FET pair (Q2a/Q2b), ensuring
zero current transients at the laser. The MCU provides complementary PWM outputs directly —
no inverter required.

The full system is a Raspberry Pi HAT. The MSPM0G3507 microcontroller handles all laser
timing and PWM; the Pi communicates with it over UART and can power-cycle it via a GPIO-
controlled MOSFET switch. An alternative USB-C UART interface allows standalone operation
without a Pi.

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     Raspberry Pi HAT                             │
│                                                                  │
│  ┌──────────────┐    UART      ┌──────────────────────────┐     │
│  │  Raspberry   │◄────────────►│   MSPM0G3507             │     │
│  │  Pi (host)   │    SWD       │   Controller             │     │
│  │              │◄────────────►│                          │     │
│  │  GPIO trigger│─────────────►│  PA8  → PWM_LASER ─────►├──┐  │
│  │  GPIO PWR_EN │─► PMOS ─────►│  VDD                    │  │  │
│  └──────────────┘              │  PA22 → PWM_DUMMY ─────►├──┤  │
│                                │  PA12 → VREF ──────────►├──┤  │
│  ┌──────────────┐              │  PB21 ◄── TRIGGER        │  │  │
│  │  USB-C UART  │◄────────────►│  (alt. path, standalone) │  │  │
│  │  (CH340N)    │    UART      └──────────────────────────┘  │  │
│  └──────────────┘                                             │  │
│                                                               │  │
│  ┌──────────────┐              ┌──────────────────────────┐  │  │
│  │  BNC trigger │─────────────►│   Laser Driver Circuit   │◄─┘  │
│  │  connector   │              │                          │     │
│  └──────────────┘              │   5V → Boost → 12V       │     │
│                                │   Current steering       │     │
│  ┌──────────────┐              │   Op-amp feedback        │     │
│  │  SWD 5-pin   │              │   Dummy load matching    │     │
│  │  0.1" header │              └──────────────────────────┘     │
│  └──────────────┘                                               │
└──────────────────────────────────────────────────────────────────┘
```

## Testing Status (as of April 2026)

### Verified on breadboard / development hardware:
- Core current-steering topology: Q1, Q2a/Q2b complementary bridge, U1 op-amp feedback
- MSPM0G3507 firmware: complementary PWM on PA8/PA22, DAC on PA12, button trigger on PB21
- Trapezoidal ramp state machine with debounced release detection
- Red laser (SLD1255VFR) operated at low power for initial testing

### Designed but not yet built/tested:
- Boost converter (5V → 12V) for laser supply
- BNC trigger interface
- MSPM0 UART interface to Raspberry Pi
- MSPM0 power-cycle MOSFET switch
- USB-C UART standalone interface (CH340N)
- SWD debug header
- HAT PCB form factor and HAT EEPROM
- Blue laser (PLT3 450GB) at any power level

### Components from BOM with notes:
- Q2a/Q2b: BSS138DW was tested but is **insufficient** for the red laser (200 mA rated
  vs 280 mA max). Si1902DL (dual NMOS, SOT-363, 1.25A) is the intended production part.
- C_bulk: specified but not populated in breadboard testing; recommended for PCB
- R_pu_b pull-up and R_pd_a pull-down: populated and confirmed necessary for safe
  power-up behavior (laser defaults OFF)

## Supported Laser Diodes

### Sony SLD1255VFR — 641nm Red High Power
- **Package:** TO-38 (Φ3.8 mm), 2-pin + floating case
- **Pin mapping:** Pin 1 = LD anode, Pin 2 = LD cathode, Pin 3 = case (N.C.)
- **Threshold current:** 60 mA typical, 90 mA max
- **Operating current:** 230 mA typical at Po = 150 mW, 280 mA max
- **Forward voltage:** 2.6V typical, 3.0V max (at Po = 150 mW)
- **Output power:** 150 mW max CW (Tc = 0–45°C), 130 mW max CW (Tc = 0–60°C)
- **Slope efficiency:** 0.9 mW/mA typical (above threshold)
- **Wavelength:** 635–647 nm (641 nm typical)
- **Reverse voltage:** 2V max
- **Laser class:** Class 3B per IEC 60825-1
- **Min supply voltage:** 5V (Vf 3.0V + 0.1V Q2 + 0.3V Q1 + 0.62V Rsense = 4.02V)

### OSRAM PLT3 450GB — 450nm Blue Single Mode
- **Package:** TO-38 ICut (Φ3.2 mm), 2-pin + isolated case
- **Pin mapping:** Pin 1 = LD anode, Pin 2 = case (isolated), Pin 3 = LD cathode
- **Threshold current:** 12 mA typical, 30 mA max
- **Operating current:** 87 mA typical at Po = 100 mW, 120 mA max
- **Forward voltage:** 5.2V typical, 6.5V max (at Po = 100 mW)
- **Output power:** 100 mW typical, 110 mW absolute max
- **Wavelength:** 440–460 nm (450 nm typical)
- **Reverse voltage:** 2V max
- **Min supply voltage:** 9V (Vf 6.5V + 0.1V Q2 + 0.3V Q1 + 0.56V Rsense = 7.46V)
- **Intended supply:** 12V (from boost converter)

### Important: Pin mapping differs between diodes
Both are TO-38 with 3 pins, but cathode location is **NOT** the same:

| Pin | SLD1255VFR (red)    | PLT3 450GB (blue)    |
|-----|---------------------|----------------------|
| 1   | LD Anode            | LD Anode             |
| 2   | LD Cathode          | Case (isolated)      |
| 3   | Case (N.C./float)   | LD Cathode           |

Verify wiring carefully when swapping between diodes.

### Stacking multiple diodes in series
Stacking increases Vf; the boost converter is designed to support this:
- 2× red in series: Vf ≈ 5.2V → 8V supply needed (boost to 9V)
- 3× red in series: Vf ≈ 7.8V → 10V supply needed (boost to 12V)
- 1 blue + 1 red: Vf ≈ 7.8V → 10V supply needed (boost to 12V)

The sense resistor must be re-sized for the stacked current, and Rdummy must be
re-matched for the stacked forward voltage. The boost output is set by FB resistors
and can be adjusted at design time for the intended diode stack.

## Supply Architecture (HAT Design)

### Power inputs:
- **5V**: From Pi 40-pin header (pins 2, 4) — used as boost converter input and
  CH340N power. Can also be provided via USB-C VBUS in standalone mode.
- **3.3V**: From Pi 40-pin header (pins 1, 17) — MCU logic rail (via MOSFET switch),
  gate pull resistors, and I2C pull-ups.

### Power rails generated on-board:
- **LASER_V (12V)**: MT3608 boost converter from 5V. Set by R_FB1/R_FB2.
  Sufficient for blue laser and stacked red lasers.
- **VCC_3V3_MCU**: Pi 3.3V switched via P-channel MOSFET (Q_PWR). Allows
  the Pi to power-cycle the MSPM0 via GPIO17.

### MSPM0 power: dedicated LDO vs Pi 3.3V rail
The MSPM0G3507 draws ~4–8 mA active at 32 MHz (plus negligible GPIO current).
The Pi's 3.3V regulator can supply several hundred mA on modern Pi models,
making a dedicated LDO unnecessary. The Pi 3.3V rail is used directly, gated
by Q_PWR for power-cycle control.

If using the board in standalone mode (USB-C, no Pi), a dedicated 3.3V LDO
(e.g., AMS1117-3.3, LDL1117S33R) from VBUS is required. This can be added
as a DNP component, bypassed when the Pi provides power.

### 12V external supply alternative
If a 12V bench supply or wall adapter is available, the boost converter can be
omitted (or its output replaced by the external supply via a separate connector).
In this case:
- Q1 (Si2302CDS) still operates within spec (Vds ≤ 12V, well within 20V max)
- U1 (TLV2371) operates at 12V supply — within its 16V max rating ✓
- R_pd_a pull-down and R_pu_b pull-up still reference 3.3V logic (separate rail)
- No changes to the laser driver circuit are required for 12V input

## Raspberry Pi HAT GPIO Assignments

| Pi Header Pin | GPIO     | Function          | MSPM0 / Use                    |
|---------------|----------|-------------------|---------------------------------|
| 2, 4          | 5V       | Power             | Boost converter input           |
| 1, 17         | 3.3V     | Power             | Logic and MCU supply (via switch)|
| 6, 9, 14, 20, 25, 30, 34, 39 | GND | Ground | Common ground |
| 8             | GPIO14/TXD | Pi UART TX     | → MSPM0 PA11 (RX)              |
| 10            | GPIO15/RXD | Pi UART RX     | ← MSPM0 PA10 (TX)              |
| 11            | GPIO17   | PWR_EN (active LOW) | → Q_PWR gate (P-MOSFET)    |
| 12            | GPIO18   | Trigger           | → MSPM0 PB21 (parallel w/ BNC) |
| 16            | GPIO23   | SWCLK             | → MSPM0 PA19                   |
| 18            | GPIO24   | SWDIO             | → MSPM0 PA20                   |
| 22            | GPIO25   | NRST              | → MSPM0 NRST                   |
| 27            | GPIO0/ID_SD | HAT EEPROM SDA | AT24C256 SDA                  |
| 28            | GPIO1/ID_SC | HAT EEPROM SCL | AT24C256 SCL                  |

### MSPM0 UART assignment
UART0 is routed to PA10 (TX) and PA11 (RX) to avoid conflicts with the PWM pins:
- PA8: TIMA0_CCP0 (laser bridge, in use)
- PA9: avoid — adjacent to PA8, used for PWM complementary in some configs

### Pi SWD / OpenOCD
The Pi can run OpenOCD with the `bcm2835gpio` or `sysfsgpio` bit-bang interface
targeting GPIO23/GPIO24/GPIO25 for SWCLK/SWDIO/NRST. This allows firmware updates
from the Pi over SWD without an external debugger.

## MSPM0 Power-Cycle MOSFET

Q_PWR is a P-channel MOSFET (DMG2305UX, SOT-23) controlling the 3.3V supply to
the MSPM0:

```
Pi 3.3V ──┬── Source
           │
          Q_PWR (P-MOSFET, DMG2305UX)
           │
          Drain ──► VCC_3V3_MCU (MSPM0 VDD, pull-ups, etc.)
           │
          Gate
           │
     ┌─────┴──────┐
     │            │
  R_GATE (1kΩ) R_PD (10kΩ)
     │            │
  Pi GPIO17      GND
```

- GPIO17 LOW (or floating, pull-down active): Vgs ≈ -3.3V → MOSFET ON → MSPM0 powered
- GPIO17 HIGH: Vgs ≈ 0V → MOSFET OFF → MSPM0 power-cycled

DMG2305UX: Vth = -0.45V to -1.0V, 2.3A continuous, SOT-23. Well suited for this use.

## BNC Trigger Interface

The BNC connector center pin connects to both Pi GPIO18 and MSPM0 PB21. The MSPM0
has its internal pull-up enabled (configured in SysConfig). The firmware uses
active-low trigger with 10 ms debounce.

A 50Ω termination resistor (DNP by default) can be populated if the BNC source
drives into a 50Ω load. Without termination, the input is high-impedance.

## SWD Debug Header (J_SWD)

5-pin 0.1" (2.54 mm pitch) single-row header, compatible with standard ARM SWD
cables and with the XDS110 / J-Link debugger pinout (adapt via flying leads):

| Pin | Signal | MSPM0 Pin |
|-----|--------|-----------|
| 1   | NRST   | NRST      |
| 2   | SWCLK  | PA19      |
| 3   | SWDIO  | PA20      |
| 4   | +3.3V  | VDD reference |
| 5   | GND    | VSS       |

These same signals are also connected to Pi GPIOs 23/24/25 for OpenOCD bit-bang.
When using an external debugger via J_SWD, the Pi GPIOs should be configured as
inputs (high-impedance) to avoid conflicts.

## Boost Converter (5V → 12V)

### Design: MT3608 (SOT-23-6)

| Parameter | Value |
|-----------|-------|
| Input voltage | 4.5V–28V (connected to Pi 5V) |
| Output voltage | 12V (set by R_FB1/R_FB2) |
| Switching frequency | 1.2 MHz |
| Max switch current | 2A |
| Efficiency at load | ~85% @ 200 mA out |

**Feedback resistors** (Vfb = 0.6V, Vout = Vfb × (1 + R_FB1/R_FB2)):
- For 12V: R_FB1 = 187kΩ (E96), R_FB2 = 10kΩ → Vout = 11.82V ≈ 12V
- For 9V: R_FB1 = 140kΩ, R_FB2 = 10kΩ → Vout = 9.0V

**Inductor:** L1, 22µH, Isat ≥ 1.5A (e.g., CDRH4D28-220NC or SRR4028-220Y)

**Schottky diode:** D_BOOST, 1A/30V (e.g., SS14, SB130, MBRS130LT3G)

**Input caps:** C_IN1 10µF X5R 0805 + C_IN2 100nF X7R 0402

**Output caps:** C_OUT1 10µF X5R 0805 + C_OUT2 100nF X7R 0402

The EN pin is pulled HIGH via 100kΩ to VIN (always-on). To add software enable,
route EN to an MSPM0 GPIO or a Pi GPIO via a buffer.

### Power budget from Pi 5V rail:
- Blue laser (87 mA at 12V): input current ≈ 87 × 12 / (5 × 0.85) ≈ 246 mA
- Red laser (280 mA at 5V, no boost needed but boost present): ≈ 394 mA input
- Recommendation: size the Pi power supply for ≥3A if driving red laser at full power

## HAT EEPROM

Per the Raspberry Pi HAT specification, an EEPROM on I2C address 0x50 is required.
- **Part:** AT24C256 (256 kbit, 32 kbyte) or AT24C32
- **Interface:** I2C on ID_SD/ID_SC (Pi GPIO0/GPIO1, pins 27/28)
- **Address:** A0=A1=A2=GND → 0b1010000 = 0x50
- **Write protect:** WP=GND (write enabled; tie to VCC to protect after programming)
- **Pull-ups:** R_I2C_SDA, R_I2C_SCL = 4.7kΩ to 3.3V

## USB-C UART Interface (Standalone Mode)

The CH340N provides a USB full-speed to UART bridge without requiring an external
crystal (internal oscillator). This allows the board to be used without a Pi.

**USB-C connector:** For UART only (no USB Power Delivery). CC1 and CC2 pins must
each have a 5.1kΩ pull-down to GND for proper host detection per USB-C spec.

**Power:** CH340N operates from VBUS (5V). Its 3.3V output (V3 pin) can optionally
power the MSPM0 when the Pi is absent, but requires a diode OR between Pi 3.3V
source and CH340N V3 output to avoid back-driving.

**UART sharing with Pi:** The MSPM0 UART TX/RX lines are shared between Pi UART
and CH340N. Only one should be active at a time. Solder bridges (SB1, SB2) allow
disconnecting the Pi UART path. By default, both are connected — this is safe
as long as the Pi UART is disabled in software when using USB-C.

## MCU Interface Summary

| Signal     | MSPM0 Pin | Direction | Connected to              |
|------------|-----------|-----------|---------------------------|
| PWM_LASER  | PA8       | Output    | Q2a gate (laser bridge)   |
| PWM_DUMMY  | PA22      | Output    | Q2b gate (dummy bridge)   |
| VREF       | PA12      | Output    | U1 non-inverting input    |
| TRIGGER    | PB21      | Input     | BNC center, Pi GPIO18     |
| UART_TX    | PA10      | Output    | Pi GPIO15/RXD, CH340N RXD |
| UART_RX    | PA11      | Input     | Pi GPIO14/TXD, CH340N TXD |
| SWCLK      | PA19      | Input     | Pi GPIO23, J_SWD pin 2    |
| SWDIO      | PA20      | Bidir     | Pi GPIO24, J_SWD pin 3    |
| NRST       | NRST      | Input     | Pi GPIO25, J_SWD pin 1    |

## Operating Points — SLD1255VFR (red), Rsense = 2.2Ω

| Target                | Vref    | Current | Optical Power           |
|-----------------------|---------|---------|-------------------------|
| Threshold             | 0.13V   | 60 mA   | ~0 mW (lasing onset)    |
| Low power             | 0.22V   | 100 mA  | ~9 mW                   |
| Medium power          | 0.31V   | 140 mA  | ~45 mW                  |
| High power            | 0.40V   | 180 mA  | ~80 mW                  |
| Nominal (100 mW)      | 0.44V   | 200 mA  | ~100 mW                 |
| Full power (150 mW)   | 0.51V   | 230 mA  | 150 mW (Tc ≤ 45°C)      |
| Abs. max              | 0.62V   | 280 mA  | Do not exceed            |

## Operating Points — PLT3 450GB (blue), Rsense = 4.7Ω

| Target                | Vref    | Current | Optical Power           |
|-----------------------|---------|---------|-------------------------|
| Threshold             | 0.06V   | 12 mA   | ~0 mW (lasing onset)    |
| Low power             | 0.19V   | 40 mA   | ~20 mW                  |
| Medium power          | 0.31V   | 65 mA   | ~50 mW                  |
| Nominal (100 mW)      | 0.41V   | 87 mA   | 100 mW                  |
| Abs. max              | 0.56V   | 120 mA  | ~110 mW                 |

## Gate Drive Safety

Q2a and Q2b are NMOS (gate HIGH = ON). During MCU power-up or brownout, GPIOs
are high-impedance. Fail-safe pull resistors are **required**:

- **R_pd_a** (Q2a gate, laser path): 10kΩ pull-down to GND → laser path defaults OFF
- **R_pu_b** (Q2b gate, dummy path): 10kΩ pull-up to 3.3V → dummy path defaults ON

This ensures that if Q1 starts up before the MCU, all current flows into the dummy
load. The laser stays dark until the MCU explicitly asserts complementary PWM outputs.

This behavior was verified on the breadboard: with pull resistors in place, no laser
current flows during MCU initialization.

## Dummy Load Matching

### Red laser (SLD1255VFR at 230 mA, 5V supply):
- LD path: V_LD ≈ 2.6V
- Dummy path: V_D2 + I × Rdummy = 0.7V + 0.230 × 8.2 = 2.59V ✓
- Node A ΔV at switch: ~10 mV

### Blue laser (PLT3 450GB at 87 mA, 12V supply):
- LD path: V_LD ≈ 5.2V
- Dummy path: 3 × 0.7V + 0.087 × 36 = 5.23V ✓
- Node A ΔV at switch: ~30 mV

## Bill of Materials — Laser Driver Circuit

### Core components (applicable to both diodes):
| Ref          | Part             | Value/Rating       | Package   | Notes                                             |
|--------------|------------------|--------------------|-----------|---------------------------------------------------|
| U1           | TLV2371          | R-R op-amp         | SOT-23-5  | 2.7–16V, 3 MHz GBW; works at both 5V and 12V     |
| Q1           | Si2302CDS        | N-MOSFET           | SOT-23    | Vth ~1V, current source; handles 280 mA           |
| Q2a, Q2b     | Si1902DL         | Dual N-MOSFET      | SOT-363   | 1.25A, matched; BSS138DW not adequate for red     |
| D1           | BAT54            | Schottky           | SOT-23    | LD reverse protection                             |
| R_pd_a       | —                | 10kΩ               | 0402      | Q2a gate pull-down (fail-safe: laser path OFF)    |
| R_pu_b       | —                | 10kΩ               | 0402      | Q2b gate pull-up to 3.3V (fail-safe: dummy ON)   |
| C1           | —                | 100nF X7R          | 0402      | U1 Vcc bypass — **include on PCB**               |
| C2           | —                | 100nF X7R          | 0402      | LD supply bypass — **include on PCB**             |
| C_bulk       | —                | 10µF X5R           | 0805      | Bulk decoupling on LD supply — **required on PCB** |
| C3           | —                | 10nF X7R           | 0402      | Vref low-pass (RC filter with source impedance)   |

### Red laser specific:
| Ref    | Part         | Value      | Package | Notes                                    |
|--------|--------------|------------|---------|------------------------------------------|
| LD1    | SLD1255VFR   | 641nm red  | TO-38   | Class 3B; eye protection required        |
| Rsense | —            | 2.2Ω 1%    | 0402    | 0.51V at 230 mA; 0.25W rating needed    |
| Rdummy | —            | 8.2Ω       | 0805    | 640 mW at 280 mA — 0805 or 1206 ≥0.5W  |
| D2     | 1N4148W      | Si diode   | SOD-123 | Dummy path voltage drop                  |

### Blue laser specific:
| Ref    | Part       | Value      | Package  | Notes                                     |
|--------|------------|------------|----------|-------------------------------------------|
| LD1    | PLT3 450GB | 450nm blue | TO-38    | 12V supply required                       |
| Rsense | —          | 4.7Ω 1%    | 0402     | 0.41V at 87 mA                            |
| Rdummy | —          | 36Ω        | 0603     | ~270 mW at 87 mA                          |
| D2     | 1N4148W ×3 | Si diode   | SOD-123  | 3 in series; ~2.1V total drop             |

### Boost converter:
| Ref      | Part           | Value        | Package   | Notes                                     |
|----------|----------------|--------------|-----------|-------------------------------------------|
| U_BOOST  | MT3608         | Boost reg    | SOT-23-6  | 1.2 MHz, 2A switch; Vfb = 0.6V           |
| L1       | CDRH4D28-220NC | 22µH         | 4×4 mm    | Isat ≥ 1.5A; low DCR                     |
| D_BOOST  | SS14           | 1A/40V Schottky | SMA    | Rectifier diode for boost output          |
| R_FB1    | —              | 187kΩ 1%     | 0402      | FB divider top; sets 12V output           |
| R_FB2    | —              | 10kΩ 1%      | 0402      | FB divider bottom; Vout = 0.6×(1+R1/R2)  |
| C_IN1    | —              | 10µF X5R     | 0805      | Boost input bulk cap                      |
| C_IN2    | —              | 100nF X7R    | 0402      | Boost input HF bypass                     |
| C_OUT1   | —              | 10µF X5R     | 0805      | Boost output bulk cap (≥16V rating)       |
| C_OUT2   | —              | 100nF X7R    | 0402      | Boost output HF bypass (≥16V rating)      |

## Bill of Materials — MSPM0 Controller and Power

| Ref      | Part           | Value        | Package   | Notes                                         |
|----------|----------------|--------------|-----------|-----------------------------------------------|
| U2       | MSPM0G3507     | 64-QFN MCU   | RGZ 9×9mm | Main controller; 32 MHz, DAC, UART, SWD       |
| Q_PWR    | DMG2305UX      | P-MOSFET     | SOT-23    | 3.3V MSPM0 power switch; Vth < -1V           |
| R_GATE   | —              | 1kΩ          | 0402      | Gate resistor for Q_PWR                       |
| R_PD     | —              | 10kΩ         | 0402      | Gate pull-down; MSPM0 defaults ON at boot     |
| C_MCU1   | —              | 100nF X7R    | 0402      | MSPM0 VDD bypass (×4, one per VDD pin)        |
| C_MCU2   | —              | 10µF X5R     | 0805      | MSPM0 VDD bulk cap                            |
| C_VDDA   | —              | 100nF X7R    | 0402      | MSPM0 VDDA bypass                             |
| C_VDDA2  | —              | 1µF X5R      | 0402      | MSPM0 VDDA bulk                               |

## Bill of Materials — HAT Infrastructure

| Ref       | Part           | Value        | Package   | Notes                                        |
|-----------|----------------|--------------|-----------|----------------------------------------------|
| U_EEPROM  | AT24C256       | 256kb EEPROM | SOIC-8    | HAT ID EEPROM; address 0x50                  |
| R_I2C_SDA | —              | 4.7kΩ        | 0402      | I2C SDA pull-up to 3.3V                      |
| R_I2C_SCL | —              | 4.7kΩ        | 0402      | I2C SCL pull-up to 3.3V                      |
| J1        | (Pi header)    | 2×20 0.1"    | Through-hole | Tall version (11 mm) to clear Pi components |
| J_BNC     | BNC PCB        | —            | PCB edge  | Trigger input                                |
| R_TERM    | —              | 50Ω DNP      | 0402      | BNC termination; do not populate by default  |
| J_SWD     | PinHeader_1×5  | 0.1" pitch   | Through-hole | SWD/NRST debug header                      |

## Bill of Materials — USB-C UART Interface

| Ref       | Part       | Value      | Package   | Notes                                           |
|-----------|------------|------------|-----------|-------------------------------------------------|
| U_USB     | CH340N     | USB-UART   | SOIC-8    | No external crystal needed; internal oscillator |
| J_USB     | USB-C      | Connector  | SMD       | Only USB 2.0 data used; no PD circuitry        |
| R_CC1     | —          | 5.1kΩ      | 0402      | CC1 pull-down for USB-C host detection          |
| R_CC2     | —          | 5.1kΩ      | 0402      | CC2 pull-down for USB-C host detection          |
| C_USB1    | —          | 100nF X7R  | 0402      | CH340N VCC bypass                              |
| C_USB2    | —          | 100nF X7R  | 0402      | CH340N V3 (3.3V out) bypass                   |
| SB1, SB2  | —          | 0Ω solder  | 0402      | Disconnect Pi UART path when using USB-C alone  |

## Thermal Considerations

### SLD1255VFR (red):
At full power (230 mA, 2.6V, 150 mW optical), dissipation ≈ 450 mW in package.
TO-38 requires a heatsink. Derate to 130 mW above 45°C case temperature.

### PLT3 450GB (blue):
At full power (87 mA, 5.2V, 100 mW optical), dissipation ≈ 350 mW. Heat exits
through the base plate — heatsink contact must be on base, not can sides.

### Q1 (Si2302CDS, current source):
Worst case: Vds ≈ 12V – 3.0V – 0.62V = 8.4V at 280 mA → 2.35W. SOT-23 is
insufficient for sustained operation at these levels. For 12V supply with red laser,
use a device with better thermal handling (SOT-223 or D-PAK) or add heatsink.
At 5V supply: Vds ≈ 1.8V at 280 mA → 504 mW; still needs attention in PCB layout.

## Layout Guidelines

- Keep Q1-Rsense-GND current loop area as small as possible
- Place C2 and C_bulk directly at LD anode pad, short path to nearest GND via
- Place boost converter on opposite board side from sensitive VREF trace
- Route VREF (DAC output) away from switching nodes (SW of boost converter)
- Route MCU signals (PWM_LASER, PWM_DUMMY, VREF) away from boost inductor
- Boost inductor SW node: minimize copper area to reduce EMI
- BNC signal trace: keep short; 50Ω impedance not critical (low frequency)
- SWD header: no special requirements; route near MSPM0
- Use ≥0.5 mm traces for laser current path (Q1 drain → Q2a source → Rsense → GND)
- Use ground pour on both layers; connect with many vias

## Schematic Structure (KiCad Hierarchical)

```
laser_hat.kicad_sch          (root: Pi HAT overview)
├── laser_driver_circuit.kicad_sch   (laser driver + boost)
├── mspm0_controller.kicad_sch       (MSPM0G3507 controller)
└── usb_uart.kicad_sch               (USB-C UART interface)
```

Hierarchical labels connect the sub-sheets at the root level:
- PWM_LASER, PWM_DUMMY, VREF: MSPM0 → Laser Driver
- TRIGGER: Root (BNC/Pi GPIO) → MSPM0
- UART_TX, UART_RX: Pi / USB-UART → MSPM0
- SWCLK, SWDIO, NRST: Pi / J_SWD → MSPM0
- LASER_V: Root (boost output on Laser Driver sheet) → Laser Driver power
- VCC_3V3_MCU: Root (Q_PWR output) → MSPM0 VDD

## Alternative Integrated Driver ICs

For a more integrated solution, consider the iC-Haus iC-HK (spike-free laser switch)
paired with iC-WK (CW APC driver). The iC-HK supports up to 700 mA pulsed / 150 mA CW,
which is sufficient for the blue laser but marginal for the red laser at full CW power.
This topology replaces Q2a/Q2b/D2/Rdummy but keeps Q1 (current source) and U1 (APC).
