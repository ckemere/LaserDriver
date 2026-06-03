# Laser Driver Firmware

## Target
- Device: MSPM0G3507SRHBR (Cortex-M0+, VQFN-32, U7 on the HAT)
- Toolchains supported:
  - TI ARM LLVM (Clang) at /opt/ti/ti-cgt-armllvm_5.1.0.LTS — driven by `Makefile.ticlang`
  - arm-none-eabi-gcc (Pi-native) — driven by `Makefile.gcc`
  - Plain `Makefile` is a dispatcher that picks one based on `uname`
    (ARM Linux → gcc, x86_64 Linux / macOS → ticlang).

The firmware has no SysConfig dependency and no external SDK path
dependency. All peripheral init is hand-written register code in
`laser_*.c`; pin assignments are in `board.h`. The hand-curated
`mcu.h` exposes only the peripheral pointers, IRQ numbers, IOMUX
function codes, and CMSIS config this firmware actually uses. The
peripheral register layouts and bit definitions in `hw/` and CMSIS in
`cmsis/` come straight from the TI SDK (originals listed at the top
of `mcu.h`). The only external dependency is the compiler itself.

### Repository layout

```
mcu.h                    self-contained device header (~150 lines)
cmsis/                   minimal CMSIS Cortex-M0+ (7 files)
hw/                      peripheral register layouts + bit fields (7 files)
startup/                 startup_mspm0g350x_{gcc,ticlang}.c
linker/                  mspm0g3507.{lds,cmd}
laser_*.c / laser_*.h    application code
board.h                  pin assignments
```

## Building with TI ARM LLVM (workstation)

```bash
export PATH=/opt/ti/ti-cgt-armllvm_5.1.0.LTS/bin:$PATH
export TI_ARM_LLVM=/opt/ti/ti-cgt-armllvm_5.1.0.LTS
make clean && make all
# -> build/laser_driver.out
```

The lone toolchain warning ("Case insensitivity of options has been
deprecated; T must be written as t") is known harmless.

## Building with arm-none-eabi-gcc (on the Pi)

```bash
sudo apt install gcc-arm-none-eabi
make -f Makefile.gcc clean all
# -> build_gcc/laser_driver.elf
#    build_gcc/laser_driver.bin   (raw image for BSL)
#    build_gcc/laser_driver.hex   (Intel HEX for OpenOCD / probes)
```

The same source tree builds under both toolchains. SDK files are
already in the repo under `sdk/` — no additional downloads needed.

## Module layout

| File | Responsibility |
|---|---|
| `board.h` | Pin map (PINCMs, masks, function codes) |
| `laser_sysctl.c/h` | Clock tree, MFPCLK, BOR threshold |
| `laser_gpio.c/h` | GPIOA power, IOMUX init, button/LED inlines |
| `laser_pwm_control.c/h` | Runtime IOMUX flips between GPIO-safe and TIMA0 |
| `laser_timera.c/h` | TIMA0 100 kHz complementary PWM |
| `laser_timerg.c/h` | TIMG0 100 kHz state-machine tick |
| `laser_dac.c/h` | DAC0 + internal VREF (2.5 V) |
| `laser_uart.c/h` | UART0 at 9600 baud (placeholder echo) |
| `laser_driver.c` | State machine, boot sequence, IRQ handlers, `main` |

Each peripheral module exposes an `_init()` (and where useful `_start()`)
plus inline hot-path helpers. None of them include any `dl_*.h` driverlib
header — only the bare device header `<ti/devices/msp/msp.h>`.

## Pin map (U7, VQFN-32)

| MCU pin | Net | Used by |
|---|---|---|
| PA3  | BUTTON1 | input, PULL_DOWN, active-high |
| PA10 | UART0 TX | UART module |
| PA11 | UART0 RX | UART module |
| PA13 | STIM_MIRROR LED | mirrors laser-on; blinks during boot |
| PA15 | DAC0 OUT | analog current setpoint |
| PA19 | SWDIO | debug |
| PA20 | SWCLK | debug |
| PA21 | PWM_LASER | TIMA0_CCP0 (laser bridge) |
| PA22 | PWM_DUMMY | TIMA0_CCP0_CMPL (dummy bridge) |

Full design map in `LaserHAT/gpio_design.md`.

## CRITICAL: Laser diode safety

The MCU must boot with PA21 LOW (laser path OFF) and PA22 HIGH (dummy
path conducting). `laser_gpio_init()` pre-loads DOUT bits before
enabling outputs; `laser_pins_to_gpio_safe()` is called explicitly
after `laser_timera_init()` so the IOMUX state at boot is unambiguous.

## ISR and state-machine style

Keep ISRs to a single volatile flag/counter update:

```c
void TIMG0_IRQHandler(void)
{
    if (laser_timerg_ack() == GPTIMER_CPU_INT_IIDX_STAT_Z) {
        isr_ticks++;
    }
}
```

No state-machine logic, peripheral writes, or multi-step code inside
ISRs. Flags written by ISRs and read in `main` are `volatile`.

State is fully captured in `MachineState`. The main loop is three
lines: `get_next_state(state)` → `set_output(state)` → `__WFI()`.
`get_next_state` owns transitions; `set_output` owns hardware writes
and is idempotent.

## Commit rules

Run a clean build before every commit:
```bash
make clean && make all
```

Stage only:
- `laser_driver.c`
- `laser_pwm_control.c` / `.h`
- `laser_sysctl.c` / `.h`
- `laser_gpio.c` / `.h`
- `laser_timera.c` / `.h`
- `laser_timerg.c` / `.h`
- `laser_dac.c` / `.h`
- `laser_uart.c` / `.h`
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
