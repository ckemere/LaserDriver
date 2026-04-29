# Laser Driver Firmware

## Target
- Device: MSPM0G3507 (Cortex-M0+, g350x subfamily)
- SDK: /opt/ti/mspm0_sdk_2_10_00_04
- Compiler: TI ARM LLVM (Clang) at /opt/ti/ti-cgt-armllvm_5.1.0.LTS
- SysConfig: /opt/ti/sysconfig_1.27.0

## Environment

```bash
export PATH=/opt/ti/ti-cgt-armllvm_5.1.0.LTS/bin:$PATH
export TI_ARM_LLVM=/opt/ti/ti-cgt-armllvm_5.1.0.LTS
export SYSCONFIG_ROOT=/opt/ti/sysconfig_1.27.0
export SDK_ROOT=/opt/ti/mspm0_sdk_2_10_00_04
```

Verify:
```bash
tiarmclang --version
$SYSCONFIG_ROOT/sysconfig_cli.sh --version
```

## Project Structure

```
Firmware/laserDriverTest/
  laser_driver.c          <- Application source (committed)
  laser_driver.syscfg     <- Peripheral/pin config (committed)
  Makefile                <- Full build pipeline (committed)
  CLAUDE.md               <- This file (committed)
  targetConfigs/
    MSPM0G3507.ccxml      <- CCS debug/flash config (committed, not used in CLI build)
  syscfg_gen/             <- SysConfig output, generated at build time (NOT committed)
  build/                  <- Compiled objects and binary (NOT committed)
```

## Building

Run from the `Firmware/laserDriverTest/` directory:
```bash
make clean && make all
```

Pipeline the Makefile executes in order:
1. SysConfig reads laser_driver.syscfg -> writes syscfg_gen/
   Generates: ti_msp_dl_config.c, ti_msp_dl_config.h, device.opt,
              device.cmd.genlibs, device_linker.cmd
2. Compile laser_driver.c, syscfg_gen/ti_msp_dl_config.c,
   and the g350x startup file -> build/*.o
3. Link using TI linker with --search_path for driverlib -> build/laser_driver.out

## Toolchain Notes

- Device family define and flags come from syscfg_gen/device.opt — do not
  add -DDeviceFamily_XYZ manually, it will conflict
- Driverlib is resolved via --search_path=$(SDK_ROOT)/source, referenced
  by device.cmd.genlibs as a relative path. TI's linker uses --search_path,
  not -L
- The startup file is startup_mspm0g350x_ticlang.c — the g350x subfamily
  covers the G3505/G3506/G3507. This is correct for the MSPM0G3507
- CMSIS headers are required at $(SDK_ROOT)/source/third_party/CMSIS/Core/Include
- The linker will warn "Case insensitivity of options has been deprecated"
  for -T and -L — these are known harmless warnings from the toolchain

## If You See Missing Header Errors

Errors about missing ti_msp_dl_config.h or anything under syscfg_gen/
mean SysConfig has not run. Always fix with `make clean && make all`.
Never manually create or edit files in syscfg_gen/.

## Peripheral Configuration

Edit laser_driver.syscfg to change pins, clocks, or peripherals.
Never edit syscfg_gen/ files — they are overwritten on every build.

## Button Trigger (PB21)

A momentary push-button is wired between PB21 and GND, active-low.  SysConfig
configures PB21 as a digital input with the internal pull-up resistor enabled
(`BUTTON_PORT` / `BUTTON_TRIGGER_PIN` macros in the generated header).

**Behavior:** press and *release* the button to fire one trapezoidal laser pulse
(ramp-up → hold-high → ramp-down → hold-low). The system then returns to
`OVERALL_WAITING` and ignores the laser sub-states until the next button release.
Presses that arrive while a cycle is already running are silently ignored.

**Debounce:** the button is polled on every TIMG0 tick (100 kHz). The state
advances only after the pin has been stable for `DEBOUNCE_TICKS` (1000 ticks =
10 ms) consecutive ticks, so contact bounce does not cause false triggers or
missed releases.

**State machine integration:** the `MachineState` struct has three orthogonal
sub-states: `overall` (`OVERALL_WAITING` / `OVERALL_TRIGGERED`), `button`
(`BUTTON_IDLE` / `BUTTON_PRESSED` / `BUTTON_RELEASED`), and `laser`
(`LASER_IDLE` / `LASER_RAMP_UP` / `LASER_HOLD_HIGH` / `LASER_RAMP_DOWN` /
`LASER_HOLD_LOW`).  `BUTTON_RELEASED` is a one-tick transient that generates a
boolean `trigger` flag consumed by the `OVERALL_WAITING` case to start a cycle.

## CRITICAL: Laser diode safety

To prevent current spikes on the laser diode that might damage it or 
other unintentional outcomes, the system MUST boot up with the GPIO
driving the laser branch of the bridge OFF and (less importantly)
the GPIO driving the dummy branch ON.

## CRITICAL: Commit Rules

Before every commit:
1. Run `make clean && make all` from Firmware/laserDriverTest/
2. Confirm zero errors and zero new warnings beyond the known toolchain
   warnings listed above
3. Only stage:
   - laser_driver.c
   - laser_driver.syscfg
   - laser_pwm_control.c
   - laser_pwm_control.h
   - Makefile
   - CLAUDE.md
   - targetConfigs/MSPM0G3507.ccxml
4. Never stage syscfg_gen/ or build/

## ISR and State Machine Style

Keep ISRs as short as possible — ideally a single volatile flag or counter write:

```c
/* Good: ISR only records that a tick happened */
static volatile uint32_t isr_ticks = 0;
void TIMG0_IRQHandler(void) {
    switch (DL_TimerG_getPendingInterrupt(TIMG0)) {
        case DL_TIMERG_IIDX_ZERO: isr_ticks++; break;
        default: break;
    }
}
```

Never put state machines, peripheral writes, or multi-step logic inside an ISR.
Flags written by ISRs and read in main must be `volatile`.

## State Machine Philosophy

The state machine is fully described by a `LaserState` struct that carries all
counters needed to determine both the next state and the hardware output:

```c
typedef struct {
    Phase    phase;      /* which leg of the waveform we are in */
    uint32_t ramp_step;  /* current PWM duty step (0..RAMP_STEPS) */
    uint32_t tick_count; /* ticks elapsed in the current phase */
} LaserState;
```

The main loop is exactly three lines — no logic lives outside these two functions:

```c
while (1) {
    state = get_next_state(state);
    set_output(state);
    __WFI();
}
```

`get_next_state(state)` owns all transition logic. It gates on `isr_ticks` so
it is safe to call on every WFI wakeup (spurious wakes are no-ops). It advances
counters and phase, then returns the new state by value.

`set_output(state)` owns all hardware writes. Given only the state struct it
sets the pin-mux (GPIO-safe vs PWM) and the PWM duty register. It is
idempotent — calling it repeatedly with the same state is harmless.

## Git Workflow
- Never push directly to main
- Create a feature branch for each task using the format: 
  git checkout -b <short-description>
- After a successful build, commit only the files listed in 
  Commit Rules above
- Push the branch to origin when done
- Commit messages should be imperative mood: "Add PWM config" 
  not "Added" or "Adding"
