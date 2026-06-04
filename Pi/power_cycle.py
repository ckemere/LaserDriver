#!/usr/bin/env python3
"""Power-cycle the LaserHAT's MSPM0 via Pi GPIO 23 (MCU_POWER_EN).

Uses Raspberry Pi OS's stock `pinctrl` tool instead of any Python GPIO
library — pinctrl ships pre-installed on every recent Pi OS image,
works the same on Pi 4 / Pi 5, and doesn't care about lgpio / RPi.GPIO
shenanigans.

GPIO 23 gates the P-MOSFET that feeds the MCU's 3V3 rail.  Driving
LOW cuts power; releasing back to input (with the on-board pull-up
restoring the HIGH state) re-applies it.  The MCU comes back up at
its hardware-default state — most importantly, with PA19 acting as
SWDIO so SWD reflashing works for the next few seconds before the
firmware can reconfigure it.

Used by `make flash` / `make load` / `make burn` as a prerequisite.

Manual use:
    python3 Pi/power_cycle.py           # default 500 ms off
    python3 Pi/power_cycle.py --ms 1000 # custom off-duration
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time


POWER_PIN = 23
DEFAULT_OFF_MS = 500


def _pinctrl(*args: str) -> None:
    """Run `pinctrl <args>`.  Raises CalledProcessError on failure."""
    subprocess.run(["pinctrl", *args], check=True)


def power_cycle(off_ms: int = DEFAULT_OFF_MS) -> None:
    if shutil.which("pinctrl") is None:
        print("error: pinctrl not found in PATH.  Install with:\n"
              "    sudo apt install raspi-utils", file=sys.stderr)
        raise SystemExit(2)

    # Drive LOW (output, level low) — cuts MCU power.
    _pinctrl("set", str(POWER_PIN), "op", "dl")
    time.sleep(off_ms / 1000.0)
    # Drive HIGH (output, level high) — restores MCU power.
    _pinctrl("set", str(POWER_PIN), "op", "dh")
    # Give the chip time to get through its BCR + SystemInit before any
    # downstream tool (openocd) tries to talk to it.
    time.sleep(0.1)
    # Optionally release the pin back to input so the board's pull-up
    # holds the line HIGH — keeps the MOSFET on without us continuing
    # to drive it.  Not strictly necessary, but tidier.
    _pinctrl("set", str(POWER_PIN), "ip")


def _main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ms", type=int, default=DEFAULT_OFF_MS,
                   help="off-duration in milliseconds (default 500)")
    args = p.parse_args()
    print(f"power-cycling MCU: GPIO {POWER_PIN} LOW for {args.ms} ms …")
    power_cycle(args.ms)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
