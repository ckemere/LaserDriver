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

## CRITICAL: Commit Rules

Before every commit:
1. Run `make clean && make all` from Firmware/laserDriverTest/
2. Confirm zero errors and zero new warnings beyond the known toolchain
   warnings listed above
3. Only stage:
   - laser_driver.c
   - laser_driver.syscfg
   - Makefile
   - CLAUDE.md
   - targetConfigs/MSPM0G3507.ccxml
4. Never stage syscfg_gen/ or build/
