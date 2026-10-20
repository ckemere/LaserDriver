# Laser Driver Firmware

## Target
- Device: MSPM0G3507SRHBR (Cortex-M0+, VQFN-32, U7 on the HAT)
- Toolchains supported:
  - TI ARM LLVM (Clang) at /opt/ti/ti-cgt-armllvm_5.1.0.LTS — driven by `Makefile.ticlang`
  - arm-none-eabi-gcc (Pi-native) — driven by `Makefile.gcc`
  - Plain `Makefile` is a dispatcher that picks one based on `uname`
    (ARM Linux → gcc, x86_64 Linux / macOS → ticlang).

The firmware has no SysConfig dependency and no external SDK path
dependency. All peripheral init is hand-written register code in the
per-peripheral `*.c` modules (`gpio.c`, `uart.c`, `dac.c`, …); pin
assignments are in `board.h`. The hand-curated
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
board.h                  pin assignments
```

## Building with TI ARM LLVM (workstation)

```bash
export PATH=/opt/ti/ti-cgt-armllvm_5.1.0.LTS/bin:$PATH
export TI_ARM_LLVM=/opt/ti/ti-cgt-armllvm_5.1.0.LTS
make clean && make all
# -> build/main.out
```

The lone toolchain warning ("Case insensitivity of options has been
deprecated; T must be written as t") is known harmless.

## Building with arm-none-eabi-gcc (on the Pi)

```bash
sudo apt install gcc-arm-none-eabi
make -f Makefile.gcc clean all
# -> build_gcc/main.elf
#    build_gcc/main.bin   (raw image for BSL)
#    build_gcc/main.hex   (Intel HEX for OpenOCD / probes)
```

The same source tree builds under both toolchains. SDK files are
already in the repo under `sdk/` — no additional downloads needed.

## Module layout

| File | Responsibility |
|---|---|
| `board.h` | Pin map (PINCMs, masks, function codes) |
| `sysctl.c/h` | Clock tree, MFPCLK, BOR threshold |
| `gpio.c/h` | GPIOA power, IOMUX init, button/LED/STIM_OUT inlines |
| `output_mux.c/h` | Runtime IOMUX flips between GPIO-safe and TIMA0 on PA7/PA12 |
| `pwm_timer.c/h` | TIMA0 100 kHz PWM on CCP1 (PA7) with CCP3 (PA12) as its complement |
| `tick_timers.c/h` | TIMG0 100 kHz state-machine tick, TIMG6 1 kHz housekeeping |
| `dac.c/h` | DAC0 on PA15 (VDDA reference): the laser module's current setpoint |
| `adc.c/h` | ADC1 channels 2 / 8 (PA17 / PA22): photodiode + compliance-rail readback in laser mode |
| `module.c/h` | J9 pin roles per mode; e-stim RELEASE, bit-banged I2C, DAC60501 writes |
| `uart.c/h` | UART1 (Pi) + UART0 (USB-C) at 115200 8N1, one RX ring per port, blocking TX |
| `protocol.h` | Binary wire protocol map (message types + field layout); mirror of `Pi/protocol.py` |
| `framing.c/h` | Magic-word frame encode/decode (`SYNC \| TYPE \| payload`, no CRC) |
| `version.c/h` | `fw_version[]`, the build's `git describe` string (`-DFW_VERSION`, rebuilt every make); reported by `CMD_GET_VERSION` → `RSP_VERSION` with `PROTO_VERSION` |
| `main.c` | State machine, boot sequence, IRQ handlers, binary frame dispatch on both ports, `main` |

Each peripheral module exposes an `_init()` (and where useful `_start()`)
plus inline hot-path helpers. None of them include any `dl_*.h` driverlib
header — only the bare device header `<ti/devices/msp/msp.h>`.

## Pin map (U7, VQFN-32) — **Rev 2 HAT** (since 2026-10-14)

The firmware targets the Rev 2 HAT only; the Rev 1 firmware is git tag
`firmware-rev1`.  Authoritative map: `LaserHAT/CLAUDE.md` ("Rev 2 MCU pin
map"); `board.h` mirrors it.

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

The MCU must boot with PA7 LOW (laser switch OFF) and PA12 HIGH (dummy
switch conducting). `laser_gpio_init()` pre-loads DOUT bits before
enabling outputs; `enter_mode(MODE_LASER)` calls `laser_pins_to_gpio_safe()`
after `laser_timera_init()` so the IOMUX state at boot is unambiguous.
PA0/PA1 must never be configured as outputs: they sit on the Pi's I2C bus.

## Modes and the module lines

`CMD_SET_MODE` (only while idle) calls `enter_mode()`, which re-purposes
J8/J9 (`module.c`):

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

Run a clean build before every commit:
```bash
make clean && make all
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
- `board.h`
- `Makefile`, `Makefile.gcc`
- `CLAUDE.md`
- `targetConfigs/MSPM0G3507.ccxml`

Never stage `build/`, `build_gcc/`, or any leftover `syscfg_gen/`.

## Git workflow

- Never push directly to main.
- Create feature branches: `git checkout -b <short-description>`.
- Commit messages in imperative mood ("Add ...", not "Added ...").
- Push the branch when done.
