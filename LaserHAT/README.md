# LaserDriver Pi HAT

A Raspberry Pi HAT for driving laser diodes in neuroscience experiments.
The board sits on top of a Pi, receives trigger pulses that the Pi relays
from experiment software on the network, and produces precisely timed laser
pulses with software-programmable intensity.

---

## Big Picture

The central challenge in optogenetics and fiber-photometry experiments is
getting clean, fast, digitally-controlled laser pulses synchronized to
behavior or electrophysiology acquisition. USB-connected laser drivers
introduce latency and jitter through the OS scheduler; GPIO-connected drivers
are faster but require dedicated single-board computers or FPGAs.

This board solves the problem with a two-layer approach:

1. **A remote experiment machine** (Python / Bonsai / Open Ephys, …) runs
   the high-level logic and decides when a pulse should start. It sends a
   UDP trigger datagram to the Pi.
2. **The Raspberry Pi** runs the broker (`Pi/brokerd/`), whose real-time
   trigger thread turns each datagram into a single GPIO edge as fast as
   possible and ACKs it. The Pi also hosts the OLED and web GUIs for
   setting parameters.
3. **The MSPM0G3507 MCU** on the HAT responds to that edge in hardware,
   generates the PWM waveform with sub-microsecond jitter, and controls the
   laser driver directly.

The remote machine handles "what and when."
The Pi gets the trigger from the network to the HAT with minimal, measured latency.
The MCU handles "how precisely" at the microsecond timescale.

---

## Board Overview

| Item | Value |
|---|---|
| Target Pi | Raspberry Pi 4 |
| Form factor | Raspberry Pi HAT (65 × 56.5 mm) |
| Connector | 40-pin PinSocket on B.Cu (female, mates with Pi's male header) |
| MCU | TI MSPM0G3507SRHBR (U7, VQFN-32, ARM Cortex-M0+) |
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
a P-channel MOSFET controlled by **GPIO23** (`MCU_POWER_EN`) acts as a
software power switch. This allows the Pi to hard-reset the MCU by toggling
GPIO23 low. `Pi/power_cycle.py` does this before every flash
(`laserhat-flash`, `make flash`), and it is also useful for fault recovery.

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

The MSPM0G3507SRHBR (U7, VQFN-32) is a Cortex-M0+ with hardware timers, a
12-bit DAC, and SWD debug — all necessary for this application. (The 48-pin
IC1 footprint on the sheet is not populated.)

### GPIO assignments

Pins used by the firmware (`Firmware/board.h`; the full pin-by-pin map,
including unused pins, is in `gpio_design.md` §2):

| MSPM0 pin | Net | Direction | Description |
|---|---|---|---|
| PA21 | `PWM_LASER` | output | TIMA0_CCP0 — laser PWM |
| PA22 | `PWM_DUMMY` | output | TIMA0_CCP0_CMPL — hardware complement of PA21 |
| PA15 | `MSPM0_DAC` | output | DAC0_OUT — laser current setpoint |
| PA14 | `STIM_TRIGGER` | input | BNC trigger, rising edge (internal pull-down) |
| PA19 | `MSPM0_SWDIO` | bidirectional → input | SWD data during the ~4 s boot blink, then the **Pi trigger input** (← Pi GPIO 24, rising edge, pull-down) |
| PA20 | `MSPM0_SWCLK` | input | SWD clock (← Pi GPIO 25) |
| PA13 | `STIM_MIRROR` | output | Stimulus mirror / boot-blink indicator; EStim output |
| PA3–PA6 | `BUTTON1`–`BUTTON4` | input | Front-panel buttons (active-high, pull-down) |
| PA10 | `MCU_UART_TX` | output | UART0 TX → Pi GPIO15 / CH340N |
| PA11 | `MCU_UART_RX` | input | UART0 RX ← Pi GPIO14 / CH340N |
| NRST | `MSPM0_NRST` | input | Reset (← Pi GPIO 18 and the SWD header) |
| VDD | `MSPM0_3V3` | power | Switched 3.3 V from Pi (GPIO23 P-MOSFET) |
| VSS / EPAD | `GND` | power | Ground |

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
intensity, timing mode) from Pi userspace, then fires autonomously on a
trigger edge: Pi GPIO 24 → PA19 (network triggers relayed by the broker),
the BNC input on PA14, or button 1.

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

Pins the Pi software drives (the full header map from the schematic,
including the legacy eink SPI wiring the software no longer uses, is in
`gpio_design.md` §1):

| Pi GPIO | Pin | Function |
|---|---|---|
| GPIO14 (TXD) | Pin 8 | UART TX → MCU RX (PA11) — `/dev/ttyS0`, owned by the broker |
| GPIO15 (RXD) | Pin 10 | UART RX ← MCU TX (PA10) |
| GPIO18 | Pin 12 | MCU NRST (flashing) |
| GPIO23 | Pin 16 | MCU power switch (`MCU_POWER_EN`, P-MOSFET gate) |
| GPIO24 | Pin 18 | **Trigger** → MCU PA19 (driven by the broker); SWDIO while flashing |
| GPIO25 | Pin 22 | SWCLK → MCU PA20 (flashing) |
| GPIO0 / GPIO1 | Pin 27 / 28 | HAT ID EEPROM (I²C) |
| GPIO2 / GPIO3, GPIO4 | Pin 3 / 5, 7 | Adafruit OLED bonnet (I²C, reset) — not used by the HAT itself |
| 5 V | Pin 2/4 | Laser supply rail (MT3608 input) |
| 3.3 V | Pin 1/17 | MCU power (via the GPIO23 P-MOSFET switch) |

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
| `STIM_TRIGGER` | BNC trigger → MCU PA14 |
| `MSPM0_SWDIO` | Pi GPIO24 ↔ MCU PA19: SWD data, then the Pi trigger line |
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
