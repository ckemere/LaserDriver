#!/usr/bin/env python3
"""Power-cycle the LaserHAT's MSPM0 via Pi GPIO 23 (MCU_POWER_EN).

GPIO 23 gates the P-MOSFET that feeds the MCU's 3V3 rail.  Idle the line
HIGH (pulled up on the board) leaves the MCU powered.  Driving LOW for
a few hundred milliseconds cuts power; releasing brings the MCU back
up at its hardware-default state — most importantly, with PA19 acting
as SWDIO so SWD reflashing works for the next few seconds before the
firmware reconfigures it.

Used by `make flash` / `make load` / `make burn` as a prerequisite, so
re-flashing always starts from a known-good state regardless of what
the previously-running firmware did to PA19.

Manual use:
    python3 Pi/power_cycle.py           # default 300 ms off
    python3 Pi/power_cycle.py --ms 500  # custom off-duration
"""

from __future__ import annotations

import argparse
import time

from gpiozero import DigitalOutputDevice


POWER_PIN = 23
DEFAULT_OFF_MS = 300


def power_cycle(off_ms: int = DEFAULT_OFF_MS) -> None:
    pin = DigitalOutputDevice(POWER_PIN, active_high=True, initial_value=True)
    try:
        pin.off()             # drive LOW -> MCU power cut
        time.sleep(off_ms / 1000.0)
        pin.on()              # drive HIGH -> MCU power restored
        # Give the chip ~100 ms to get through its BCR + into SystemInit
        # before `make flash` invokes openocd.  That puts us safely inside
        # the boot-blink window where PA19 is still in its SWDIO default.
        time.sleep(0.1)
    finally:
        pin.close()


def _main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ms", type=int, default=DEFAULT_OFF_MS,
                   help="off-duration in milliseconds (default 300)")
    args = p.parse_args()
    print(f"power-cycling MCU: GPIO 23 LOW for {args.ms} ms …")
    power_cycle(args.ms)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
