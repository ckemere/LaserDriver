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
    picocom                    # raw serial terminal (protocol is binary — see smoke_test.py)
    python3-serial             # pyserial, for the scripted UART smoke test
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
sudo systemctl stop laserhat-broker.service   # frees Pi GPIO 24 (= SWDIO)
sudo apt install openocd
make flash             # builds if needed, then programs and resets
# `make load` and `make burn` are aliases for the same thing.
make reset             # just reset the MCU, leave flash contents alone
sudo systemctl start laserhat-broker.service
```

> **Flash with the laser unplugged**, and **stop the broker first**. PA19
> doubles as SWDIO *and* the Pi-GPIO trigger; the broker holds Pi GPIO 24
> for the trigger pin, so OpenOCD can't claim SWDIO until it's stopped.
> `make flash` power-cycles the MCU and halts the core during the boot
> blink, so PA19 stays SWDIO and the firmware never runs to fire the laser
> — but if anything attaches SWD to an already-running MCU, the SWD wiggling
> on PA19 looks like trigger edges. Unplugging the laser makes that moot.

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

The firmware speaks a **magic-word-framed binary protocol** on UART0
(115200 8N1).  Each frame is `SYNC(DE AD) | TYPE | payload`, where the
payload length is implied by the type — no length field, no byte-stuffing,
**no CRC**.  The message map is the single source of truth in `protocol.h`
(mirrored in `Pi/protocol.py`):

```
Host -> MCU                          MCU -> Host
  CMD_CONFIG  i u16,                   RSP_STATUS  i,r,h,buttons,phase,tick
              r u32 (10 µs ticks),     EVT_PULSE_START  tick
              h u32 (10 µs ticks)      EVT_PULSE_END    tick
  CMD_TRIGGER                          EVT_BUTTON       mask, edges
  CMD_QUERY
```

Defaults at boot: `i=320 r=8000 h=10000`.  **Every command is answered with
`RSP_STATUS`** (status-as-ack) — so the host confirms the resulting state
end-to-end; that echo is the integrity check.  `CMD_CONFIG` sets all three
stim parameters at once (atomic; out-of-range leaves the config unchanged,
which the echo reveals).  A trigger also emits `EVT_PULSE_START` when the
pulse begins and `EVT_PULSE_END` when it returns to idle; button edges
arrive unsolicited as `EVT_BUTTON`.

No CRC is needed: every command's `RSP_STATUS` echo verifies the values
end-to-end, decoded `STATUS`/event fields are range-checked, and the host
guarantees a `CMD_CONFIG` payload never contains the `SYNC` bytes (it nudges
the ~150 ramp/hold values whose low 16 bits would equal `DE AD`), so the
MCU's resync on the next `SYNC` is exact.

**PA19** is the Pi-GPIO trigger input from boot — there is no arm command.
The firmware claims it at the *end* of boot, after the ~4 s blink, so the
blink is the SWD flashing window (see "Flashing" — flash with the laser
unplugged, since SWD activity on PA19 looks like trigger edges).

Because the protocol is binary you can't drive it from a terminal like
`picocom`. Use the round-trip smoke tool — it reuses the Pi-side codec
(`Pi/protocol.py`) so there's one wire-protocol implementation. The
broker owns the port, so stop it first:

```bash
sudo systemctl stop laserhat-broker.service
python3 host_tools/smoke_test.py            # default /dev/ttyS0
python3 host_tools/smoke_test.py /dev/ttyAMA0
sudo systemctl start laserhat-broker.service
```

For ad-hoc pokes there's also `Pi/laser_hat.py query|trigger|config|watch`
(same caveat — stop the broker first). Either way you must be in the
`dialout` group:

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
