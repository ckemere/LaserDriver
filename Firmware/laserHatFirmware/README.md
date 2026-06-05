# LaserHAT firmware build & install

Two supported toolchains, picked automatically by `Makefile` based on `uname`:

| Makefile           | Toolchain             | Selected on                       |
| ------------------ | --------------------- | --------------------------------- |
| `Makefile.gcc`     | arm-none-eabi-gcc     | ARM Linux (Raspberry Pi)          |
| `Makefile.ticlang` | TI ARM CLANG          | x86_64 Linux, macOS (Intel + AS)  |

Plain `make` dispatches to the right one. To force a particular
toolchain on any host, invoke explicitly:

```bash
make -f Makefile.gcc      # GCC build, regardless of host
make -f Makefile.ticlang  # TI CLANG build, regardless of host
```

Both build the same source tree against the in-tree headers under
`mcu.h`, `cmsis/`, `hw/`, `startup/`, and `linker/`. No SysConfig, no
external SDK path.

---

## Building on Linux

```bash
make clean && make all
# → build/main.out
```

The Makefile defaults to TI ARM CLANG at
`/opt/ti/ti-cgt-armllvm_5.1.0.LTS/bin/tiarmclang`. Override if you
installed elsewhere:

```bash
make CC=/some/other/path/tiarmclang
```

Or change the version once via `TI_TOOLCHAIN_VER`:

```bash
make TI_TOOLCHAIN_VER=4.0.3.LTS
```

---

## Building on macOS

Install TI ARM CLANG from
<https://www.ti.com/tool/download/ARM-CGT-CLANG> (the macOS `.pkg`).
Default install path is `~/ti/ti-cgt-armllvm_<version>.LTS/` and the
Makefile picks that up automatically:

```bash
make clean && make all
```

**Apple Silicon**: TI ships the toolchain x86_64-only.  Install
Rosetta once:

```bash
softwareupdate --install-rosetta
```

---

## Building on the Raspberry Pi

### Pi package dependencies

```bash
sudo apt update
sudo apt install \
    git \
    make \
    gcc-arm-none-eabi          # cross-compiler for the MSPM0
```

Recommended additions for testing, flashing, and debugging:

```bash
sudo apt install \
    picocom                    # interactive serial terminal
    python3-serial             # pyserial, for scripted UART tests
    openocd                    # SWD flashing via Pi GPIO (linuxgpiod)
    gdb-multiarch              # ARM-capable debugger
```

`make` and `git` ship with Raspberry Pi OS by default, but listed for
completeness on a minimal install. `openocd` and `gdb-multiarch` are
not used by the current firmware build but you'll want them for
`make flash` and on-target debugging once those land.

### Build

```bash
make clean all
# (the dispatcher Makefile auto-routes to Makefile.gcc on ARM Linux)
# → build_gcc/main.elf
#   build_gcc/main.bin   (raw image for BSL)
#   build_gcc/main.hex   (Intel HEX for OpenOCD / probes)
```

### Flashing the MCU over SWD from the Pi

The HAT brings SWCLK/SWDIO/NRST out to Pi GPIO 25/24/18 (see the
wiring table at the bottom of this file). OpenOCD on the Pi can drive
those pins directly via the kernel's libgpiod interface — no external
debug probe required.

```bash
sudo apt install openocd
make flash             # builds if needed, then programs and resets
# `make load` and `make burn` are aliases for the same thing.
make reset             # just reset the MCU, leave flash contents alone
```

`make flash` does not run an OpenOCD verify pass. The target-side
CRC algorithm in `ti_mspm0.cfg` / OpenOCD 0.12.0+dev hangs the MCU
even though the write itself is reliable. Visual confirmation is the
~4-second STIM_MIRROR boot blink right after the flash command
finishes.

#### What `make flash` actually does

The flashing dance evolved to dodge two MSPM0-specific quirks that
made naive flashing unreliable. Today the rule does three things in
order:

1. **`power_cycle`** (Pi/power_cycle.py, a prerequisite of the rule).
   Park Pi GPIOs 14 (UART TX), 24 (SWDIO), 25 (SWCLK) as inputs and
   assert NRST so the MSP can't be **phantom-powered** through its IO
   ESD diodes — a HIGH on any of those lines clamps back to the MSP's
   VDD rail and keeps the chip half-running even after GPIO 23 cuts
   the P-MOSFET. Then drop GPIO 23 LOW for 500 ms (cap drain), release
   it, release NRST, and restore each parked pin to the alt-function
   mode it had before (saved at the start of the cycle so the kernel
   UART driver continues to own GPIO 14).

2. **OpenOCD probes SWD while the MCU is in the boot blink window.**
   PA19 is in its hardware-default SWDIO function for the ~4 seconds
   it takes the boot blink to finish. (PA19 reclaim is now opt-in via
   the `g` UART command — see protocol below — so the next firmware
   boot also stays SWD-friendly until something asks otherwise.)

3. **Explicit `init` / `halt` / `flash write_image` / `reset run` /
   `shutdown`**, instead of OpenOCD's higher-level `program ... reset`.
   The shorthand tries to halt-on-reset using DEMCR vector catch, and
   that latch doesn't engage reliably on MSPM0 — halt times out and
   init fails. Halting a freely-running CPU (i.e. one in the boot
   blink busy-wait) via a plain DAP halt request works every time.

The OpenOCD config (`openocd/pi-swd.cfg`) uses
`reset_config srst_only srst_nogate` — NRST is wired but OpenOCD does
not assert it during connect (an earlier attempt with
`connect_assert_srst` made MEM-AP examination fail because DEBUGSS was
held in reset alongside the core).

#### Recovery if `make flash` leaves something stuck

If a flash run is interrupted mid-cycle and leaves GPIO 14 parked as
plain input, the kernel UART driver doesn't reclaim the line and the
web app / smoke test will report "MCU no response". Restore by hand:

```bash
pinctrl get 14                # current state
pinctrl set 14 a5             # back to mini-UART (/dev/ttyS0)
# or `a0` if you've enabled PL011 with dtoverlay=disable-bt
```

`power_cycle.py` now detects this state on its next run and
auto-restores to the configured fallback alt
(`UART_TX_FALLBACK_ALT` in the script — defaults to `a5`), so a fresh
`make flash` is also a valid recovery path.

**Prerequisites:**

1. **`gpio` group membership** — needed to access `/dev/gpiochip*`
   without `sudo`. Default on Raspberry Pi OS; verify with `groups`.
   If you're not in it, `sudo usermod -aG gpio $USER && newgrp gpio`.
2. **No other process holding the SWD pins.** If you've configured
   GPIO 18/24/25 for anything else in `/boot/firmware/config.txt`,
   `make flash` will fail to claim the lines.
3. **OpenOCD with the TI MSPM0 target driver.** The Pi OS Bookworm
   `openocd` package (0.12.0+dev) ships `target/ti_mspm0.cfg`, which
   is what `make flash` defaults to. If your install puts the file
   under a different name, override:
   `make flash OPENOCD_TARGET=target/whatever.cfg`.

**Pi 5 note:** the Pi 5 exposes the user GPIO bank as
`/dev/gpiochip4` (RP1 chip), not `/dev/gpiochip0`. Override the chip
number on the make command line:

```bash
make flash OPENOCD_GPIOCHIP=4
```

You can edit `openocd/pi-swd.cfg` to make that the default if you're
always on a Pi 5.

### Pi UART (serial console to the MCU)

The Pi's UART is wired straight through to the MCU on GPIO 14/15.
One-time setup so you can talk to the MCU over `/dev/ttyS0`:

```bash
sudo raspi-config
# Interface Options → Serial Port:
#   Login shell over serial?  No
#   Hardware serial enabled?  Yes
sudo reboot
```

Confirm `/boot/firmware/config.txt` has `enable_uart=1` and
`/boot/firmware/cmdline.txt` does **not** contain `console=serial0`
(raspi-config should remove it; if it didn't, edit by hand and reboot).

On Pi 3 / Pi 4 add `dtoverlay=disable-bt` to `/boot/firmware/config.txt`
if you want the full PL011 (`/dev/ttyAMA0`) instead of the mini-UART
(`/dev/ttyS0`). The current firmware runs at 115200 8N1 on whichever
UART is on those pins.

### Quick UART smoke test

The firmware speaks a tiny line-based ASCII protocol on UART0 (115200
8N1, `\n`-terminated each direction):

```
i N    set intensity (peak PWM duty, 1..320)
r N    set ramp-up duration (in 10 µs ticks)
h N    set hold (high) duration (in 10 µs ticks)
t      trigger one pulse via UART
g      arm PA19 as a GPIO-input trigger (was SWDIO at boot)
?      query state -> "OK i=N r=N h=N b=BBBB g=0|1 phase=W|T tick=TTT"
```

Defaults at boot: `i=320 r=8000 h=10000 g=0`. Each command echoes the
resulting value as `OK ...`; out-of-range / unknown / busy responses
come back as `ERR <reason>`. `t` does not ACK immediately — the ACK
pair is `OK pulse start=TTT` when the state machine enters the
pulse, then `OK pulse end=TTT` when it returns to idle.

`g` is one-way: once armed, PA19 stays a GPIO trigger input until the
MCU is reset. This keeps SWD reflashing reliable on a fresh boot — the
firmware never reconfigures the SWDIO pin unless a client explicitly
asks. The web app's *TRIGGER (GPIO)* button sends `g` automatically
before driving Pi GPIO 24, so users don't need to think about it.

```bash
picocom -b 115200 /dev/ttyS0
# at the prompt:
#   ?      <enter>   -> OK i=320 r=8000 h=10000 b=0 g=0 phase=W tick=...
#   i 100  <enter>   -> OK i=100
#   t      <enter>   -> OK pulse start=... / OK pulse end=...
#   g      <enter>   -> OK g=1   (then Pi GPIO 24 edges become triggers)
# exit: Ctrl-A Ctrl-X
```

Or scriptable — `host_tools/smoke_test.py` exercises the whole
command set end-to-end:

```bash
python3 host_tools/smoke_test.py            # default /dev/ttyS0
python3 host_tools/smoke_test.py /dev/ttyAMA0
```

You'll need to be in the `dialout` group:

```bash
sudo usermod -aG dialout $USER && newgrp dialout
```

---

## Where the MCU is wired to the Pi

| Pi pin    | Pi GPIO       | HAT signal     | MSPM0 pin |
| --------- | ------------- | -------------- | --------- |
| 8         | GPIO 14 (TX)  | `MCU_UART_TX`  | PA10 (RX) |
| 10        | GPIO 15 (RX)  | `MCU_UART_RX`  | PA11 (TX) |
| 11        | GPIO 17       | `EINK_BUSY`    | —         |
| 12        | GPIO 18       | `MSPM0_NRST`   | NRST      |
| 16        | GPIO 23       | `MCU_POWER_EN` | (3V3 gate) |
| 18        | GPIO 24       | `MSPM0_SWDIO`  | PA19      |
| 22        | GPIO 25       | `MSPM0_SWCLK`  | PA20      |

Full design map: `LaserHAT/gpio_design.md`.
