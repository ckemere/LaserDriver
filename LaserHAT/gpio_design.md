# LaserHAT GPIO Design — Pi ↔ MSPM0 Interconnect

Derived from the KiCad schematics in `LaserHAT/` as of branch `laser-hat`,
2026-06-03. Where this document and `LaserHAT/README.md` disagree, this
document is the live source — README is stale on at least two pins (see
*Discrepancies* at the bottom).

---

## 1. Raspberry Pi 40-pin header → HAT signal map

Derived from `LaserDriver.kicad_sch` by matching Pi-side `GPIOxx` labels and
HAT-side hierarchical labels at coincident (x, y) positions on the connector
stubs.

### Pins the HAT actively uses

| Pi pin | Pi GPIO | HAT net | Direction (Pi POV) | Purpose |
|---|---|---|---|---|
| 8  | GPIO14 (TXD0) | `MCU_UART_TX`  | out | UART TX → MSPM0 RX (PA11) |
| 10 | GPIO15 (RXD0) | `MCU_UART_RX`  | in  | UART RX ← MSPM0 TX (PA10) |
| 11 | GPIO17        | `EINK_BUSY`    | in  | SSD1680Z BUSY line |
| 12 | GPIO18        | `MSPM0_NRST`   | out | MSPM0 reset (SWD + BSL entry) |
| 13 | GPIO27        | `EINK_RESET`   | out | SSD1680Z reset |
| 15 | GPIO22        | `EINK_DC`      | out | SSD1680Z data/command select |
| 16 | GPIO23        | `MCU_POWER_EN` | out | P-MOSFET gate → MSPM0 3V3 switch |
| 18 | GPIO24        | `MSPM0_SWDIO`  | bi  | SWD data |
| 19 | GPIO10 (MOSI) | `EINK_COPI`    | out | SPI0 → eink |
| 21 | GPIO9  (MISO) | `EINK_CIPO`    | in  | SPI0 ← eink |
| 22 | GPIO25        | `MSPM0_SWCLK`  | out | SWD clock |
| 23 | GPIO11 (SCLK) | `EINK_SCK`     | out | SPI0 clock → eink |
| 24 | GPIO8  (CE0)  | `EINK_CS`      | out | SPI0 CS0 → eink |
| 27 | ID_SD (GPIO0) | `ID_SDA`       | bi  | HAT-ID EEPROM I²C data |
| 28 | ID_SC (GPIO1) | `ID_SCL`       | out | HAT-ID EEPROM I²C clock |
| 2/4 | +5V          | `+5V`          | pwr | MT3608 boost input + CH340N VBUS-alt |
| 1/17| +3V3         | `+3V3`         | pwr | Source for `MSPM0_3V3` via P-MOSFET |

### Pins the HAT leaves alone

GPIO 2 (SDA1), GPIO 3 (SCL1), GPIO 4 (GPCLK0), GPIO 5, GPIO 6, GPIO 7 (CE1),
GPIO 12 (PWM0), GPIO 13 (PWM1), GPIO 16, GPIO 19, GPIO 20, GPIO 21, GPIO 26 —
no stub wire on the HAT side. Free for the Pi user.

### Observations

- **SPI0 is fully consumed by the eink.** GPIO 7 (SPI0.CE1) is *not* taken,
  so a second SPI peripheral could share SPI0 if needed.
- **GPIO 0/1 are the HAT-ID EEPROM (AT24C256) I²C** per the standard Pi HAT
  spec. Boot-time HAT identification works without firmware support.
- **GPIO 26 is no longer the BNC trigger path.** The current schematic has
  no direct Pi-to-MCU trigger pin — the BNC reaches the MCU only through
  the `STIM_TRIGGER` net which sits in the BNC area of the schematic and
  is *not* exported to a Pi GPIO. This is a behavior change from the
  README and the project-memory note (see *Discrepancies*).
- **NRST is on GPIO 18, not on a dedicated jumper.** OpenOCD’s `linuxgpiod`
  configuration must claim GPIO 18 as `srst`.

---

## 2. MSPM0G3507 pin map (U7, VQFN-32 / SRHBR variant)

U7 is the populated MCU. IC1 (the 48-pin SPTR footprint elsewhere on the
sheet) is not used and should be ignored when reading this section.

Derived by walking the `MSPM0G3507SRHBR` lib_symbol pin offsets against
U7's placement at schematic (152.4, 236.22) and matching hierarchical
labels by coincident coordinate. Cross-checked on three known pins
(NRST → pin 3, PA10 → pin 14, PA11 → pin 15) which agreed exactly.

| Pin | Datasheet name | Net | Function | Notes |
|----|---|---|---|---|
| 1  | PA0/FCC_IN | *(none)* | unused | |
| 2  | PA1 | *(none)* | unused | |
| 3  | NRST | `MSPM0_NRST` | reset | ← Pi GPIO 18 + 5-pin SWD header |
| 4  | VDD | `MSPM0_3V3` | power | |
| 5  | VSS | GND | power | |
| 6  | PA2/ROSC | *(none)* | unused | likely on ROSC net |
| 7  | PA3/COMP1_OUT/LFXIN | `BUTTON1` | input | blocks ext. LFCLK crystal — fine if internal LFOSC used |
| 8  | PA4/LFCLK_IN/LFXOUT | `BUTTON2` | input | same caveat |
| 9  | PA5/HFXIN/FCC_IN | `BUTTON3` | input | blocks ext. HFCLK crystal |
| 10 | PA6/HFCLK_IN/HFXOUT | `BUTTON4` | input | same |
| 11 | PA7/CLK_OUT | *(none)* | unused | |
| 12 | PA8 | *(none)* | **unused** | ⚠ firmware assumes this is `PWM_LASER` — it is not |
| 13 | PA9/RTC_OUT/CLK_OUT | *(none)* | unused | |
| 14 | PA10/CLK_OUT | `MCU_UART_TX` | UART0 TX | → Pi GPIO 15 |
| 15 | PA11 | `MCU_UART_RX` | UART0 RX | ← Pi GPIO 14 |
| 16 | PA12/FCC_IN | *(none)* | unused | |
| 17 | PA13 | `STIM_MIRROR` | output | trigger echo / indicator |
| 18 | PA14/CLK_OUT/A0_12 | `STIM_TRIGGER` | input | BNC trigger lands here |
| 19 | PA15/A1_0/DAC_OUT | `MSPM0_DAC` | DAC0 out | → op-amp current setpoint |
| 20 | PA16/A1_1/FCC_IN | *(none)* | unused | |
| 21 | PA17/A1_2 | `MSPM0_ADC` | ADC1 ch2 | laser current monitor |
| 22 | PA18/A1_3 | `MSPM0_BSL_INVOKE` | input | BSL entry strap; not routed to root sheet |
| 23 | PA19/SWDIO | `MSPM0_SWDIO` | SWD data | ← Pi GPIO 24; reusable as GPIO post-boot |
| 24 | PA20/SWCLK | `MSPM0_SWCLK` | SWD clock | ← Pi GPIO 25; reusable as GPIO post-boot |
| 25 | PA21/A1_7/VREF- | `PWM_LASER` | TIMA0_CCP0 (PINCM46 PF=5) | laser drive |
| 26 | PA22/CLK_OUT/A0_7 | `PWM_DUMMY` | TIMA0_CCP0_CMPL (PINCM47 PF=7) | hardware complement of PA21 |
| 27 | PA23/VREF+ | *(none)* | unused | likely VREF cap |
| 28 | PA24/A0_3 | *(none)* | unused | |
| 29 | PA25/A0_2/OPA0_IN1+ | *(none)* | unused | |
| 30 | PA26/A0_1 | *(none)* | unused | |
| 31 | PA27/RTC_OUT/A0_0 | *(none)* | unused | |
| 32 | VCORE | `VCORE` | power | core reg cap |
| 33 | EPAD | GND | thermal/ground | |

### PWM pin assignment (fixed 2026-06-03)

The original firmware configured `TIMA0_CCP0` on PA8 — but PA8 is
unconnected on U7. PA21 (where `PWM_LASER` actually lands) also supports
`TIMA0_CCP0` via PINCM46 PF=5, and PA22 supports `TIMA0_CCP0_CMPL` via
PINCM47 PF=7 as before. So the fix was just changing the IOMUX function
constants in `laser_pwm_control.c` from PINCM19/PA8 to PINCM46/PA21. No
timer change, no syscfg change.

Bench verification still TBD: PA21 should toggle at 100 kHz during a
triggered pulse with PA22 as its hardware complement.

### Remaining firmware/HW gaps

- syscfg already pins BUTTON.TRIGGER on PA3 (matches `BUTTON1` on the
  schematic), so the README/CLAUDE.md text claiming PB21 is stale doc
  only — firmware is correct on this point.
- `BUTTON2..4` (PA4..PA6), `STIM_TRIGGER` (PA14), `STIM_MIRROR` (PA13),
  and `MSPM0_ADC` (PA17) are not yet declared in syscfg. They need
  adding before the firmware can read trigger/mirror/buttons or sample
  the laser-current monitor.

### SWCLK/SWDIO as additional GPIO

PA19/PA20 default to SWD function at reset, but firmware can reconfigure
their IOMUX to GPIO and reclaim them — for example as low-jitter trigger
inputs driven by the Pi on GPIO 24/25. NRST always restores SWD function
at the next reset, so flashing still works:

```
Pi: power-cycle MCU via GPIO 23 → assert NRST via GPIO 18
    → PA19/PA20 are SWD again → flash → release NRST
    → firmware reclaims PA19/PA20 as GPIO inputs
```

Restriction: the Pi can't simultaneously hold an SWD session and use
GPIO 24/25 as trigger lines — has to be either/or per boot cycle.

---

## 3. Eink display (SSD1680Z) — SPI bus owned by Pi

The Pi drives the eink directly over SPI0 + four control lines. The MSPM0
**does not own the eink**. The button/menu state machine on the MCU
edits `PulseConfigLive` and the *Pi* renders the display when it sees a
config-change event over UART.

This is a meaningful architectural choice and worth being explicit about:

- **Pro:** SSD1680Z init sequence and partial-update bookkeeping live in
  Python on the Pi, where iteration is fast. MCU code is leaner.
- **Pro:** SPI is heavy traffic; keeping it off the MCU frees SPI1 for
  future use (extra DAC, current sensor, etc.).
- **Con:** the MCU cannot show "live" status when the Pi daemon is down
  or absent. Standalone mode (USB-C only, no Pi) means no display.
- **Con:** all eink driver work moves out of firmware and into the Pi
  daemon (Phase 5 of the firmware roadmap).

This supersedes the earlier firmware-roadmap Phase 4 (which assumed an
MCU-driven eink). The four buttons remain MCU-side; the display
becomes a Pi-side responsibility.

---

## 4. Programming and reset paths

### SWD path (Pi → MCU)

Wired and complete:

```
Pi GPIO 25 ── MSPM0_SWCLK ── PA19
Pi GPIO 24 ── MSPM0_SWDIO ── PA20
Pi GPIO 18 ── MSPM0_NRST  ── NRST  (also on 5-pin SWD header)
```

A 5-pin 1.27 mm header (`NRST/SWCLK/SWDIO/3V3/GND`) provides an external
CMSIS-DAP fallback. OpenOCD on the Pi using the `linuxgpiod` adapter is
the recommended primary path:

```
swd_pins  = {SWCLK = GPIO25, SWDIO = GPIO24, SRST = GPIO18}
power_en  = GPIO23  # toggle MSPM0_POWER_EN around flash for clean reset
```

### BSL path (UART bootloader)

The MSPM0G3507 ROM bootloader is invoked when `BSL_INVOKE` is held at the
correct level during NRST release. The schematic exposes `MSPM0_BSL_INVOKE`
on the MSPM0 sheet, but **the root sheet does not route it to a Pi GPIO**
that I could locate. Two likely interpretations — needs verification:

1. **Driven from the CH340N RTS line** (`CH340_RTS` is the only RTS-class
   signal in the design and the USB-UART sheet exposes it but does not
   internally connect it). In that case BSL is reachable only via USB-C,
   not via Pi UART. This is the Arduino-style auto-reset-into-bootloader
   pattern.
2. **Strapped to a test point or solder jumper.** In that case BSL is
   manual and infrequent.

**This is the single most important schematic question to settle before
committing to a flashing workflow.** Tracing `MSPM0_BSL_INVOKE` and
`CH340_RTS` to ground truth tells us whether routine firmware updates can
ride the existing Pi UART or whether SWD is the only Pi-side option.

### MCU power gate

`MCU_POWER_EN` on Pi GPIO 23 controls the P-MOSFET that gates the
3.3 V rail feeding `VCC_3V3_MCU`. The Pi can:

- power-cycle the MCU at will (recovery, post-flash clean boot)
- intentionally keep the MCU off while the Pi handles startup logic
- assert `MCU_POWER_EN` then immediately drive `MSPM0_NRST` to get a
  deterministic reset on every boot

The MOSFET is active-high gate to a P-channel device, so GPIO 23 = HIGH
means MCU powered. Drive LOW in early Pi boot before claiming any other
HAT pin, to guarantee no MCU activity during host setup.

---

## 5. Bus and electrical contention

### Pi UART vs. CH340N

`MCU_UART_TX` / `MCU_UART_RX` are physically the same wires as
`CH340_TX` / `CH340_RX` (joined at the MSPM0 pins). The USB-UART sheet
notes solder bridges SB1/SB2 select which side is active. Driving both
simultaneously will burn one of the line drivers.

**Pi-side software must assume:**

- if USB-C is plugged in *and* the solder bridges are closed, the Pi UART
  must be kept tri-stated (or just not used)
- the safe default is "Pi UART live, USB-C unused"; the inverse needs
  manual board configuration

### SWD vs. eink

No overlap — eink is on SPI0 (GPIO 8/9/10/11 + 17/22/27), SWD is on
GPIO 18/24/25. They can run concurrently.

### Pi UART vs. SWD/NRST during flash

`linuxgpiod`-based OpenOCD will hold NRST asserted during connect and
release on exit. While NRST is held, the MCU UART RX is in reset and
the Pi UART line goes nowhere — the Pi daemon should pause and reopen
the UART around `make flash`.

---

## 6. Discrepancies between schematic, README, and project memory

| Item | README / memory says | Schematic actually shows | Resolution |
|---|---|---|---|
| MCU power switch GPIO | GPIO 17 | GPIO 23 | Update README; firmware doesn't care |
| MCU package | 48-pin SPTR | 32-pin SRHBR (U7 populated; IC1 unused) | Firmware syscfg + pin tables target U7 |
| PWM_LASER pin | PA8 / TIMA0_CCP0 | PA21 / TIMA0_CCP0 (PINCM46 PF=5) | Fixed — firmware updated to PA21 mux constants |
| Button trigger pin | PB21 | PB21 doesn't exist on VQFN-32; BUTTON1 is PA3 | Update syscfg, retire PB21 |
| BNC trigger pin | GPIO 26 → PB21 | PA14 (`STIM_TRIGGER`), no Pi route | Trigger sources are UART or BNC, or repurpose PA19/PA20 |
| MCU-driven eink | Implied by firmware roadmap | Eink is on Pi SPI0 | Eink driver work moves to Pi daemon |
| Four buttons | Not in README | PA3..PA6 = BUTTON1..4 | Local UI plan stays |
| BSL invoke | Not mentioned | PA18 = `MSPM0_BSL_INVOKE`; not exported to Pi | BSL only via on-board strap/USB-C path; not from Pi UART |
| Eink ↔ MCU SPI link | Not in README | Missing — Pi-only eink wiring | Known design flaw; track as HW issue for next board rev |

---

## 7. Open items before any firmware change touches these pins

1. **Bench-verify PA21/PA22 PWM.** With the updated firmware flashed,
   trigger a pulse and scope PA21 and PA22. PA21 should toggle at 100 kHz
   with PA22 as the hardware complement. PA8 should remain static.
2. **Extend `laser_driver.syscfg`** as state-machine work needs them:
   add `BUTTON2..4` (PA4..PA6), `STIM_TRIGGER` (PA14 input),
   `STIM_MIRROR` (PA13 output), `MSPM0_ADC` (PA17, ADC1 ch2 for current
   monitor). These are unused by the current firmware but needed for
   Phases 3–5 of the firmware roadmap.
3. **File a HW-revision issue** for the next board spin: wire the
   SSD1680Z control lines to the MSPM0 in addition to the Pi, so the HAT
   can drive the eink in standalone mode (USB-C only, no Pi).
4. **Decide on Pi-asserted trigger path.** Options:
   - UART command only (carries Pi scheduler jitter, ~ms-class)
   - Repurpose PA19 or PA20 (currently SWD) as Pi-driven trigger in
     normal operation, with NRST restoring SWD for flash sessions
   - Defer to a future board rev that adds a dedicated Pi-GPIO →
     MCU-GPIO trigger line
