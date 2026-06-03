# LaserHAT firmware build & install

Two supported toolchains:

| Makefile        | Toolchain             | Where you'd typically run it       |
| --------------- | --------------------- | ---------------------------------- |
| `Makefile`      | TI ARM CLANG          | Linux / macOS workstation          |
| `Makefile.gcc`  | arm-none-eabi-gcc     | Raspberry Pi (or any Linux/macOS)  |

Both build the same source tree against the in-tree headers under
`mcu.h`, `cmsis/`, `hw/`, `startup/`, and `linker/`. No SysConfig, no
external SDK path.

---

## Building on Linux

```bash
make clean && make all
# → build/laser_driver.out
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
make -f Makefile.gcc clean all
# → build_gcc/laser_driver.elf
#   build_gcc/laser_driver.bin   (raw image for BSL)
#   build_gcc/laser_driver.hex   (Intel HEX for OpenOCD / probes)
```

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
(`/dev/ttyS0`). The current firmware runs at 9600 8N1 on whichever
UART is on those pins.

### Quick UART smoke test

```bash
picocom -b 9600 /dev/ttyS0
# type a byte — the MCU echoes it back
# exit: Ctrl-A Ctrl-X
```

Or scriptable:

```python
# pip install pyserial (or apt install python3-serial)
import serial
s = serial.Serial('/dev/ttyS0', 9600, timeout=1)
s.write(b'Hello MSPM0\n')
print(repr(s.read(len(b'Hello MSPM0\n'))))
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
