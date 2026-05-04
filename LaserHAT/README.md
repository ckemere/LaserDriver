# LaserDriver Pi HAT

A Raspberry Pi HAT for driving laser diodes in neuroscience experiments.
The board sits on top of a Pi, receives trigger pulses from experiment software
running on the Pi, and produces precisely timed laser pulses with
software-programmable intensity.

---

## Big Picture

The central challenge in optogenetics and fiber-photometry experiments is
getting clean, fast, digitally-controlled laser pulses synchronized to
behavior or electrophysiology acquisition. USB-connected laser drivers
introduce latency and jitter through the OS scheduler; GPIO-connected drivers
are faster but require dedicated single-board computers or FPGAs.

This board solves the problem with a two-layer approach:

1. **The Raspberry Pi** runs experiment software (Python / Bonsai), handles
   high-level logic, and asserts a single GPIO edge when a pulse should start.
2. **The MSPM0G3507 MCU** on the HAT responds to that edge in hardware,
   generates the PWM waveform with sub-microsecond jitter, and controls the
   laser driver directly.

The Pi handles "what and when" at the millisecond timescale.  
The MCU handles "how precisely" at the microsecond timescale.

---

## Board Overview

| Item | Value |
|---|---|
| Form factor | Raspberry Pi HAT (65 × 56.5 mm) |
| Connector | 40-pin PinSocket on B.Cu (female, mates with Pi's male header) |
| MCU | TI MSPM0G3507RGZR (48 MHz ARM Cortex-M0+) |
| Laser supply | MT3608 boost converter — 5 V → ~12 V |
| UART bridge | CH340N USB-to-UART (USB-C receptacle) |
| Debug port | 5-pin SWD header (NRST / SWCLK / SWDIO / 3V3 / GND) |
| Laser connector | 6-pin shrouded header |

---

## Schematic Hierarchy

The project uses a KiCad hierarchical design with one root sheet and three
child sheets:

```
LaserDriver.kicad_sch          ← root: RPi GPIO header + sheet hierarchy
├── laser_driver_circuit.kicad_sch   ← MT3608 boost + current-steering driver
├── mspm0_controller.kicad_sch       ← MSPM0G3507 + decoupling + SWD header
└── usb_uart.kicad_sch               ← CH340N + USB-C receptacle + solder bridges
```

The root schematic was built from the official RPi HAT template, preserving
every GPIO label and decoupling element exactly.

---

## Power System

### Supply rails

```
Raspberry Pi 5 V (Pin 2/4)
    │
    ├──▶ MT3608 boost converter ──▶ +LASER_V (~12 V) ──▶ laser diode anode
    │
    └──▶ Pi 3.3 V (Pin 1/17) ─── P-MOSFET switch ──▶ VCC_3V3_MCU ──▶ MSPM0
```

The MCU is **not** powered directly from the always-on 3.3 V rail.  Instead,
a P-channel MOSFET controlled by **GPIO17** acts as a software power switch.
This allows the Pi to hard-reset the MCU by toggling GPIO17 low, which is
useful during firmware development and for fault recovery.

### MT3608 boost converter

The MT3608 (SOT-23-6) is a fixed-frequency current-mode boost controller.
On this board it is configured to produce ~12 V from the Pi's 5 V rail using
a standard resistor divider on the feedback pin (BOOST_FB).

Key signals in `laser_driver_circuit.kicad_sch`:

| Net | Description |
|---|---|
| `VCC_5V_IN` | 5 V input from Pi (VBUS via GPIO header) |
| `BOOST_SW` | Inductor switching node (do not probe with a scope ground clip) |
| `BOOST_FB` | Resistor divider feedback to MT3608 FB pin |
| `BOOST_EN` | Enable pin — pulled high, can be driven low to shut down boost |
| `+LASER_V` | ~12 V output — laser diode anode supply |

Input and output decoupling capacitors are placed close to the MT3608 on the
PCB layout; do not move them during placement.

---

## Laser Driver Circuit

The driver uses a **current-steering PWM topology** with a matched dual
N-MOSFET pair (BSS138DW, SOT-363).

```
+LASER_V ──▶ [Laser Diode] ──▶ [Q_main] ──▶ GND   (PWM_LASER = high → lasing)
+LASER_V ──▶ [Dummy Load ] ──▶ [Q_dummy] ──▶ GND   (PWM_DUMMY = high → dark)
```

`PWM_LASER` and `PWM_DUMMY` are always complementary: when the laser is
off, current flows through the dummy load instead of turning off abruptly.
This keeps the supply voltage stable and prevents the inductive spike from
the laser diode bond wire from coupling back into the supply.

A **TLV2371** rail-to-rail op-amp provides a feedback path for DC bias
control.  The MCU's **DAC output (VREF)** sets the target current; the
op-amp closes the loop by adjusting gate drive on Q_main.

### Component choices

- **Q2 (dual MOSFET pair):** BSS138DW (SOT-363) for matched threshold
  voltage. The schematic notes that `Si1902DL` (1.25 A rated) is required for
  high-power red lasers; the BSS138DW is adequate for lower-power blue lasers.
- **Laser connector:** 6-pin shrouded header (J_LASER) carries
  `+LASER_V`, `GND`, `PWM_LASER`, `PWM_DUMMY`, `VREF`, and `ADC` (monitor).
- **SolderJumper SJ1:** bypasses the op-amp feedback path for open-loop
  testing. Install closed only during calibration.

---

## MSPM0G3507 Controller

The MSPM0G3507RGZR is a 48 MHz Cortex-M0+ with hardware timers, a 12-bit
DAC, and SWD debug — all necessary for this application.

### GPIO assignments

| MSPM0 pin | Signal | Direction | Description |
|---|---|---|---|
| PA8 | `PWM_LASER` | output | TIMA0_CCP0 — laser PWM |
| PA22 | `PWM_DUMMY` | output | TIMA0_CCP0_CMPL — complementary |
| PA12 | `VREF` | output | DAC0_OUT — laser current setpoint |
| PB21 | `TRIGGER` | input | Trigger from Pi GPIO26 |
| PA10 | `UART_TX` | output | UART to CH340N / Pi GPIO14 |
| PA11 | `UART_RX` | input | UART from CH340N / Pi GPIO15 |
| PA19 | `SWCLK` | input | SWD clock |
| PA20 | `SWDIO` | bidirectional | SWD data |
| NRST | `NRST` | input | Reset (from SWD header) |
| VDD/VDDA | `VCC_3V3_MCU` | power | Switched 3.3 V from Pi |
| VSS/VSSA | `GND` | power | Ground |

### Decoupling

Five 100 nF capacitors are placed on the MCU's VDD/VDDA/VSS/VSSA pins.
Their placement on the PCB layout is critical — keep them within 1 mm of
the MCU pads.

### SWD debug header (J_SWD, 5-pin, 1.27 mm pitch)

| Pin | Signal |
|---|---|
| 1 | NRST |
| 2 | SWCLK |
| 3 | SWDIO |
| 4 | 3.3 V |
| 5 | GND |

OpenOCD with a CMSIS-DAP probe is recommended for firmware flashing.

---

## USB/UART Interface

The USB-C connector and CH340N bridge serve two purposes depending on
hardware configuration:

### Mode 1 — Pi-controlled (normal operation)

Solder bridges **SB1 and SB2 are removed** (open, factory default).

The Pi communicates with the MSPM0 directly over its own UART
(GPIO14 = TX, GPIO15 = RX).  The CH340N is powered down (no USB cable
connected).  The MCU receives experiment parameters (pulse width,
intensity, timing mode) from Pi userspace at startup, then operates
autonomously from the TRIGGER edge.

### Mode 2 — Standalone / development (USB-C active)

Solder bridges **SB1 and SB2 are installed** (closed).

A USB-C cable connects a laptop directly to the CH340N, which presents
as a virtual COM port.  The CH340N bridges USB to the MSPM0's UART.
This mode is used for:
- Firmware development without a Pi attached
- Interactive calibration and testing
- Updating pulse parameters from a laptop in the rig

**Do not connect USB-C and Pi UART simultaneously** — both would drive the
same TX/RX lines and contention will damage one of the drivers.

### USB-C UFP detection

Two 5.1 kΩ pull-down resistors on CC1 and CC2 identify the board as a
USB device (UFP) to the host.  This is required by the USB-C specification
for Type-C cables to deliver power — without them, some hosts will not
enumerate the device.

### CH340N power

The CH340N is powered from VBUS_5V (the USB-C VBUS pin) through a
decoupling capacitor.  When no USB cable is connected the chip is
unpowered, drawing no current from the Pi's 5 V rail.

---

## Raspberry Pi GPIO Usage

| Pi GPIO | Pin | Function |
|---|---|---|
| GPIO17 | Pin 11 | MCU power switch (P-MOSFET gate) |
| GPIO14 (TXD) | Pin 8 | UART TX → MCU RX |
| GPIO15 (RXD) | Pin 10 | UART RX ← MCU TX |
| GPIO26 | Pin 37 | TRIGGER → MCU PB21 |
| 5 V | Pin 2/4 | Laser supply rail (MT3608 input) |
| 3.3 V | Pin 1/17 | MCU power (via GPIO17 P-MOSFET switch) |

---

## Net Naming Conventions

| Net | Description |
|---|---|
| `VCC_5V_IN` | 5 V from Pi GPIO header |
| `+LASER_V` | ~12 V boost output (laser anode supply) |
| `VCC_3V3_MCU` | Switched 3.3 V to MCU |
| `VBUS_5V` | USB-C VBUS (powers CH340N only) |
| `PWM_LASER` | Laser PWM (MCU → driver Q_main gate) |
| `PWM_DUMMY` | Complementary dummy-load PWM |
| `VREF` | DAC output — laser current setpoint |
| `TRIGGER` | Pi GPIO26 → MCU input |
| `UART_TX/RX` | MCU ↔ CH340N or Pi UART |
| `SWCLK/SWDIO` | SWD debug bus |

---

## Schematic Generation

The schematics are generated from Python scripts using the `kiutils` library.
`laser_driver_circuit.kicad_sch` is hand-edited and is never overwritten by
the generator — it is the authoritative source for the laser driver topology.

```bash
# One-time setup
python3 -m venv .venv
.venv/bin/pip install -r ../requirements.txt   # kiutils==1.4.8

# Regenerate all schematics (except laser_driver_circuit)
.venv/bin/python3 LaserHAT/generate_schematics.py

# Fix hierarchical labels in child sheets (if needed after regeneration)
.venv/bin/python3 LaserHAT/fix_labels.py
```

Open `LaserHAT/LaserDriver.kicad_pro` in KiCad to review, then run
**Tools → Update PCB from Schematic** to push component changes to the PCB.
