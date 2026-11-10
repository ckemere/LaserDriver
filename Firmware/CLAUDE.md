# Laser Driver Firmware

## Target
- Device: U7 on the HAT, Cortex-M0+, VQFN-32 (RHB):
  MSPM0G3507SRHBR on the Rev 2 HAT, MSPM0G1507SRHBR on the StimHAT and the
  LaserDriverHAT (the G3507 without CAN-FD: same pinout, IOMUX, memory map
  and the peripherals this firmware uses, so one linker script and one
  `mcu.h` serve both).
- **Three build targets from one source tree**, picked at compile time by
  `BOARD` (see "Board selection" below): `rev2`, `stim`, `laser`.
- Toolchains supported:
  - TI ARM LLVM (Clang) at /opt/ti/ti-cgt-armllvm_5.1.0.LTS — driven by `Makefile.ticlang`
  - arm-none-eabi-gcc (Pi-native) — driven by `Makefile.gcc`
  - Plain `Makefile` is a dispatcher that picks one based on `uname`
    (ARM Linux → gcc, x86_64 Linux / macOS → ticlang).

The firmware has no SysConfig dependency and no external SDK path
dependency. All peripheral init is hand-written register code in the
per-peripheral `*.c` modules (`gpio.c`, `uart.c`, `dac.c`, …); pin
assignments are in `board_<board>.h`, selected by `board.h`. The hand-curated
`mcu.h` exposes only the peripheral pointers, IRQ numbers, IOMUX
function codes, and CMSIS config this firmware actually uses. The
peripheral register layouts and bit definitions in `hw/` and CMSIS in
`cmsis/` come straight from the TI SDK (originals listed at the top
of `mcu.h`). The only external dependency is the compiler itself.

### Repository layout

```
mcu.h                    self-contained device header (~150 lines)
cmsis/                   minimal CMSIS Cortex-M0+ (7 files)
hw/                      peripheral register layouts + bit fields (8 files)
startup/                 startup_mspm0g350x_{gcc,ticlang}.c
linker/                  mspm0g3507.{lds,cmd}
main.c                   state machine, boot, IRQ handlers, frame dispatch
gpio.c/h uart.c/h …      per-peripheral application modules
protocol.h               binary wire protocol map (mirror of Pi/protocol.py)
framing.c/h              magic-word frame encode/decode
board.h                  board dispatcher (-DBOARD_REV2 / _STIM / _LASER)
board_rev2.h             LaserHAT Rev 2 pin map + feature flags
board_stim.h             StimHAT pin map + feature flags
board_laser.h            LaserDriverHAT pin map + feature flags
```

## Board selection

| `BOARD=` | Define | HAT | MCU | Modes | `RSP_VERSION.board` |
|---|---|---|---|---|---|
| `rev2` (default) | `-DBOARD_REV2` | LaserHAT Rev 2, plug-in modules on J8/J9 | G3507 | LASER + ESTIM (boots LASER) | `BOARD_TYPE_REV2` = 1 |
| `stim` | `-DBOARD_STIM` | StimHAT, isolated stimulator on the HAT | G1507 | ESTIM only | `BOARD_TYPE_STIM` = 2 |
| `laser` | `-DBOARD_LASER` | LaserDriverHAT, laser driver on the HAT | G1507 | LASER only | `BOARD_TYPE_LASER` = 3 |

`board.h` refuses to compile without exactly one define.  Every board header
defines the same macro set (listed at the top of `board.h`): pins / PINCMs /
function codes, the button pins in the reported bit order, LED, STIM_OUT/IN,
PI_TRIGGER, UARTs, spare pins, and the feature flags `BOARD_HAS_LASER`,
`BOARD_HAS_ESTIM`, `BOARD_HAS_FAULT_PIN`, `BOARD_HAS_BUTTON6`,
`BOARD_DEFAULT_MODE`, `BOARD_TYPE`.  The `.c` files contain no pin numbers;
code for a function a board lacks is compiled out with `#if BOARD_HAS_*`
(`pwm_timer.c`, `dac.c`, `adc.c` are empty on the StimHAT; the fault path
and all e-stim code are absent on the LaserDriverHAT).  `CMD_SET_MODE` to a
mode the board lacks is refused (the `RSP_STATUS` echo keeps the board's
mode).  The Rev 2 build behaves exactly as before the split.

Pi-side GPIOs for `make flash` follow the board: rev2 NRST 23 / POWER_EN 18,
stim and laser NRST 9 / POWER_EN 10; SWCLK 24 / SWDIO 25 on all three.


## Building with TI ARM LLVM (workstation)

```bash
export PATH=/opt/ti/ti-cgt-armllvm_5.1.0.LTS/bin:$PATH
export TI_ARM_LLVM=/opt/ti/ti-cgt-armllvm_5.1.0.LTS
make clean && make all BOARD=rev2      # or stim / laser; `make boards` = all three
# -> build/<board>/main.out
```

The lone toolchain warning ("Case insensitivity of options has been
deprecated; T must be written as t") is known harmless.

## Building with arm-none-eabi-gcc (on the Pi)

```bash
sudo apt install gcc-arm-none-eabi
make -f Makefile.gcc clean all BOARD=rev2    # BOARD=rev2 (default) | stim | laser
# -> build_gcc/<board>/main.elf
#    build_gcc/<board>/main.bin   (raw image for BSL)
#    build_gcc/<board>/main.hex   (Intel HEX for OpenOCD / probes)
make -f Makefile.gcc boards                  # all three boards
make -f Makefile.gcc clean-all               # remove build_gcc/ entirely
```

`clean` removes only the selected board's directory.  Every object depends
on all headers, so switching boards or editing a header rebuilds.

The same source tree builds under both toolchains. SDK files are
already in the repo under `sdk/` — no additional downloads needed.

## Module layout

| File | Responsibility |
|---|---|
| `board.h` | Board dispatcher; `board_rev2.h` / `board_stim.h` / `board_laser.h` hold each pin map (PINCMs, masks, function codes) and feature flags |
| `sysctl.c/h` | Clock tree, MFPCLK, BOR threshold |
| `gpio.c/h` | GPIOA power, IOMUX init from the board macros (incl. BUTTON6, interrupt polarity split at bit 16), button/LED/STIM_OUT inlines, FAULT_n (stubbed "high" without a fault pin) |
| `output_mux.c/h` | Switch lines A/B: GPIO-safe levels, and (laser boards) runtime IOMUX flips to TIMA0 (Rev 2 PA7/PA12, LaserDriverHAT PA22/PA23) |
| `pwm_timer.c/h` | Laser boards: TIMA0 100 kHz PWM on CCP1 (laser switch) with CCP3 (dummy switch) as its complement; not built for the StimHAT |
| `tick_timers.c/h` | TIMG0 100 kHz state-machine tick, TIMG6 1 kHz housekeeping |
| `dac.c/h` | Laser boards: DAC0 on PA15 (VDDA reference), the laser current setpoint |
| `adc.c/h` | Laser boards: photodiode + compliance-rail readback; instance and channels from the board (Rev 2 ADC1 ch 2 / 8, LaserDriverHAT ADC0 ch 1 / 0) |
| `module.c/h` | Laser pins to analog; e-stim RELEASE, bit-banged I2C (Rev 2 J9, StimHAT through the ISO1640), DAC60501 writes |
| `uart.c/h` | UART1 (Pi) + UART0 (USB-C) at 115200 8N1, one RX ring per port, blocking TX |
| `protocol.h` | Binary wire protocol map (message types + field layout); mirror of `Pi/protocol.py` |
| `framing.c/h` | Magic-word frame encode/decode (`SYNC \| TYPE \| payload`, no CRC) |
| `version.c/h` | `fw_version[]`, the build's `git describe` string (`-DFW_VERSION`, rebuilt every make); reported by `CMD_GET_VERSION` → `RSP_VERSION` with `PROTO_VERSION` |
| `main.c` | State machine, boot sequence, IRQ handlers, binary frame dispatch on both ports, `main` |

Each peripheral module exposes an `_init()` (and where useful `_start()`)
plus inline hot-path helpers. None of them include any `dl_*.h` driverlib
header — only the bare device header `<ti/devices/msp/msp.h>`.

## Pin maps (U7, VQFN-32)

All three side by side ("—" = spare, driven low; PA0/PA1 Pi I2C, PA2 ROSC,
PA19/PA20 SWD, PA8-PA11 UARTs and PA18 BSL are the same everywhere):

| Pin | Rev 2 (`board_rev2.h`) | StimHAT (`board_stim.h`) | LaserDriverHAT (`board_laser.h`) |
|---|---|---|---|
| PA3 | — | — | — |
| PA4 | — | PI_TRIGGER ← Pi GPIO18 | PI_TRIGGER ← Pi GPIO18 |
| PA5 | — | LED | LED |
| PA6 | FAULT_n (J8.3, pull-up) | — | BUTTON3 (down) |
| PA7 | PWM_A TIMA0_CCP1 / EN | BUTTON4 (up) | BUTTON4 (up) |
| PA12 | PWM_B TIMA0_CCP3 / CATH | BUTTON1 (left, BACK) | BUTTON1 (left, BACK) |
| PA13 | BUTTON4 (wheel roll) | BUTTON6 (right) | BUTTON6 (right) |
| PA14 | BUTTON2 (wheel push) | BUTTON2 (centre) | BUTTON2 (centre) |
| PA15 | DAC0_OUT / RELEASE (J9.3) | BUTTON3 (down) | DAC0_OUT (DB_DAC) |
| PA16 | BUTTON3 (wheel roll) | BUTTON5 FIRE | BUTTON5 FIRE |
| PA17 | ADC1 ch 2 / SDA (J9.4) | STIM_OUT | STIM_OUT ("SYNC OUT") |
| PA21 | BUTTON1 BACK | STIM_IN | STIM_IN |
| PA22 | "ADC1 ch 8" / SCL (J9.5) | FAULT_H (no pull) | PWM_A TIMA0_CCP1 (laser switch) |
| PA23 | BUTTON5 FIRE | CATH_H | PWM_B TIMA0_CCP3 (dummy switch) |
| PA24 | LED | EN_H | — |
| PA25 | STIM_OUT | RELEASE_H | — |
| PA26 | STIM_IN | SDA_H (ISO1640) | ADC0 ch 1 (photodiode) |
| PA27 | PI_TRIGGER ← Pi GPIO26 | SCL_H (ISO1640) | ADC0 ch 0 (LASER_V) |
| NRST / PWR_EN | Pi GPIO23 / GPIO18 | Pi GPIO9 / GPIO10 | Pi GPIO9 / GPIO10 |

Known Rev 2 issue, kept so the Rev 2 build is unchanged: PA22 is A0_7
(ADC0 channel 7), not an ADC1 input, so Rev 2's `adc_comp` does not read
J9.5 (see `board_rev2.h`).  StimHAT: never enable internal pull-ups on
PA23-PA25 (10k pull-downs, ISO7741 thresholds).  LaserDriverHAT: no fault
line (`BOARD_HAS_FAULT_PIN` 0).

### Rev 2 HAT detail (since 2026-10-14)

The Rev 1 firmware is git tag `firmware-rev1`.  Authoritative maps:
`LaserHAT/CLAUDE.md` ("Rev 2 MCU pin map"), `LaserHAT/StimHAT/README.md`
("MCU pin map"), `LaserHAT/LaserDriverHAT/README.md` ("MCU pin map"); the
`board_*.h` headers mirror them.

| MCU pin | Net | Used by |
|---|---|---|
| PA0/PA1 | I2C_SDA/SCL | Pi's I2C bus (OLED bonnet) — **left at reset default, never driven** |
| PA2  | ROSC | 100 k 0.1 % for the SYSOSC frequency-correction loop (`sysctl.c`) |
| PA6  | DB_GPIO = FAULT_n (J8.3) | input, pull-up; falling-edge GROUP1 IRQ (armed once high for 2 ms) kills EN/CATH/RELEASE and latches a fault |
| PA7  | DB_PWM_A (J8.5) | TIMA0_CCP1 laser switch (LASER); e-stim EN as GPIO (ESTIM); LOW when idle |
| PA8/PA9 | PI_RXD/PI_TXD | **UART1** ↔ Pi GPIO15/14 (`/dev/ttyS0`) |
| PA10/PA11 | MCU_UART_TX/RX | **UART0** ↔ CH340N on USB-C (and the ROM BSL) |
| PA12 | DB_PWM_B (J8.4) | TIMA0_CCP3 dummy switch, complement of A, HIGH when idle (LASER); e-stim CATH as GPIO, LOW when idle (ESTIM) |
| PA13 / PA14 / PA16 | BUTTON4 / 2 / 3 | SW7 thumbwheel roll / push / roll, active low |
| PA15 | DB_DAC (J9.3) | LASER: DAC0_OUT setpoint (VDDA ref); ESTIM: RELEASE push-pull output |
| PA17 / PA22 | DB_ADC_A / DB_ADC_B (J9.4 / J9.5) | LASER: ADC1.2 photodiode / ADC1.8 compliance divider; ESTIM: bit-banged I2C SDA / SCL (open-drain) |
| PA18 | BSL_INVOKE | SW6, active high (ROM samples it at reset); read into button bit 5 |
| PA19 / PA20 | SWDIO / SWCLK | ← Pi GPIO25 / GPIO24 |
| PA21 | BUTTON1 | SW8 BACK, active low |
| PA23 | BUTTON5 | SW9 FIRE, active low — fires a pulse on press |
| PA24 | LED_MCU | D7: ~2 s boot blink, 1 Hz heartbeat, solid during a pulse, 5 Hz while a fault is latched |
| PA25 | MCU_STIM_OUT | → U8 → J7 BNC + D9; HIGH for the pulse envelope |
| PA26 | MCU_STIM_IN | ← U8 ← J6 BNC; rising edge = trigger |
| PA27 | PI_TRIGGER | ← Pi GPIO26; rising edge = trigger |
| NRST | GPIO23 | ← Pi GPIO23 (R3 47 k, C3 10 n) |

Pi side: GPIO18 = MCU_POWER_EN (U5), GPIO23 = NRST, GPIO24 = SWCLK,
GPIO25 = SWDIO, GPIO26 = trigger, GPIO14/15 = UART.

## CRITICAL: Laser diode safety

The MCU must boot with PWM_A LOW (laser switch OFF) and PWM_B HIGH (dummy
switch conducting): Rev 2 PA7 / PA12, LaserDriverHAT PA22 / PA23
(`BOARD_PWM_B_BOOT_HIGH`; on the StimHAT PWM_B is CATH_H and boots LOW). `laser_gpio_init()` pre-loads DOUT bits before
enabling outputs; `enter_mode(MODE_LASER)` calls `laser_pins_to_gpio_safe()`
after `laser_timera_init()` so the IOMUX state at boot is unambiguous.
PA0/PA1 must never be configured as outputs: they sit on the Pi's I2C bus.

## Modes and the module lines

`CMD_SET_MODE` (only while idle, only to a mode the board has) calls
`enter_mode()`, which re-purposes J8/J9 on Rev 2 (`module.c`); the
StimHAT and LaserDriverHAT stay in their one mode.  Pin names below are
Rev 2's; the StimHAT uses EN_H PA24 / CATH_H PA23 / RELEASE_H PA25 /
SDA_H PA26 / SCL_H PA27 / FAULT_H PA22 with identical sequencing, the
LaserDriverHAT PWM PA22 / PA23, DAC PA15, ADC0 PA26 / PA27:

- **LASER:** PA7/PA12 flip between GPIO-safe and TIMA0 PWM per tick; DAC0
  drives J9.3 with `g_laser_dac` **for the duration of a pulse only** (written
  at trigger, zeroed at pulse end: the module's cascode Q1 must not carry the
  dummy current continuously, REV2_NOTES "Q1 is a cascode"; default 1216 ≈
  100 mA; `CMD_LASER_CURRENT`, max 3650 ≈ 300 mA, applied at once if a pulse
  is running); ADC1 samples J9.4/J9.5 every 10 ms from housekeeping.
- **ESTIM (spec §7):** PA7 = EN, PA12 = CATH (idle LOW), PA15 = RELEASE are
  driven as GPIOs by the tick ISR: PRE (RELEASE + CATH high, 10 µs) → PULSE1
  (EN) → gap (CATH low) → PULSE2 (EN) → POST (RELEASE high 200 µs) → RESET
  (RELEASE low 200 µs).  The amplitude (`CMD_ESTIM_CURRENT`) goes to the
  module's DAC60501 over bit-banged I2C on PA17/PA22 from housekeeping, only
  while idle and only after FAULT_n has been high ≥ 2 ms (GAIN init first,
  `MODULE_ESTIM_READY`).  Triggers are refused while FAULT_n is low.
- **Fault:** FAULT_n (PA6) falling edge → `GROUP1_IRQHandler` forces
  EN/CATH/RELEASE off and latches (`MODULE_FAULT_LATCHED`, `EVT_FAULT`); the
  tick ISR also latches if it sees FAULT_n low mid-train and aborts to
  WAITING.  `CMD_CLEAR_FAULT` clears.  The interrupt is **one-shot**: armed
  only after FAULT_n has been high for 2 ms (an unpowered e-stim module idles
  low), masked by its own handler when it fires, and re-armed 2 ms after
  FAULT_n is high again *and* the latch has been cleared — so a chattering
  line (a module whose isolated converter is folding back) cannot starve the
  tick ISR / main; the tick-ISR backstop still kills a pulse within 10 µs
  while the interrupt is masked.
  TIMA0's hardware FAULT0 input is not used: in ESTIM mode the pins are
  GPIOs, so a timer-side kill would not reach them.

## ISR and state-machine style

All pulse timing lives in **one** ISR. `TIMG0_IRQHandler` (the 100 kHz
tick) is the only place the state machine runs: it acks the timer,
advances the machine, and drives the outputs:

```c
void TIMG0_IRQHandler(void)
{
    if (laser_timerg_tick_ack() == GPTIMER_CPU_INT_IIDX_STAT_Z) {
        g_isr_ticks++;
        state_machine_tick();      /* advance MachineState */
        set_output_from_state();   /* idempotent hardware writes */
    }
}
```

This is deliberate: keeping the whole machine in the highest-priority
tick ISR means UART parsing, button polling, and housekeeping (all in
`main`) can take as long as they like without shifting a PWM-duty
write. The other ISRs stay minimal — `UART1_IRQHandler` / `UART0_IRQHandler`
push one RX byte into their port's ring; `TIMG6_IRQHandler` sets a
housekeeping flag; `GROUP1_IRQHandler` sets the hardware-trigger flag and,
for a FAULT_n edge, forces the module outputs off and sets the fault latch
(the only output writes outside the tick). Flags shared between an ISR and
`main` are `volatile`.

State is fully captured in `MachineState`. Within the tick ISR,
`state_machine_tick()` owns transitions; `set_output_from_state()` owns
hardware writes and is idempotent — it re-asserts the desired output
state every tick (all plain register stores, no read-modify-write), so a
perturbed IOMUX/GPIO self-heals within 10 µs. `main`
only reads the machine for the `CMD_QUERY` → `RSP_STATUS` response and
drains ISR-produced pulse-event records to emit the `EVT_PULSE_START` /
`EVT_PULSE_END` frames off the interrupt path.

## Commit rules

Run a clean build of all three boards before every commit:
```bash
make -f Makefile.gcc clean-all boards
```

Stage only:
- `main.c`
- `output_mux.c` / `.h`
- `sysctl.c` / `.h`
- `gpio.c` / `.h`
- `pwm_timer.c` / `.h`
- `tick_timers.c` / `.h`
- `dac.c` / `.h`
- `adc.c` / `.h`
- `module.c` / `.h`
- `uart.c` / `.h`
- `protocol.h`
- `framing.c` / `.h`
- `version.c` / `.h`
- `board.h`, `board_rev2.h`, `board_stim.h`, `board_laser.h`
- `mcu.h`
- `Makefile`, `Makefile.gcc`, `Makefile.ticlang`
- `CLAUDE.md`
- `targetConfigs/MSPM0G3507.ccxml`

Never stage `build/`, `build_gcc/`, or any leftover `syscfg_gen/`.

## Git workflow

- Never push directly to main.
- Create feature branches: `git checkout -b <short-description>`.
- Commit messages in imperative mood ("Add ...", not "Added ...").
- Push the branch when done.
