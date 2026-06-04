#!/usr/bin/env python3
"""Power-cycle the LaserHAT's MSPM0 via Pi GPIO 23 (MCU_POWER_EN).

Uses Raspberry Pi OS's stock `pinctrl` tool — pre-installed on every
recent Pi OS image, works the same on Pi 4 / Pi 5, doesn't care about
lgpio / RPi.GPIO.

The trick that makes this actually reset the MCU: every Pi GPIO that
connects to an MSP IO pin must be parked at a non-driving state before
GPIO 23 cuts the rail, otherwise the MSP's IO ESD diodes clamp the
signal back to VDD and phantom-power the chip just enough to keep it
half-running.  The biggest culprit in practice is Pi GPIO 14 (UART
TX), which the kernel UART driver normally idles HIGH.

Pins parked during the cycle:
    GPIO 14 (UART TX -> PA11 RX)  set to INPUT  (high-Z)
    GPIO 18 (NRST)                drive LOW    (asserted)
    GPIO 24 (SWDIO -> PA19)       set to INPUT
    GPIO 25 (SWCLK -> PA20)       set to INPUT

After the rail is restored, GPIO 18 (NRST) is released back to HIGH so
the MCU comes out of reset, and the UART/SWD pins are left as inputs
— the kernel UART driver will reclaim GPIO 14/15 the next time
something opens /dev/ttyS0, and OpenOCD reclaims 18/24/25 itself at
the next flash.

Used by `make flash` as a prerequisite.

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


POWER_PIN = 23   # MCU_POWER_EN -> P-MOSFET gate
NRST_PIN  = 18   # MSPM0 NRST
QUIET_PIN_INPUTS = [14, 24, 25]   # UART TX, SWDIO, SWCLK

DEFAULT_OFF_MS = 500


def _pinctrl(*args: str) -> None:
    subprocess.run(["pinctrl", *args], check=True)


def power_cycle(off_ms: int = DEFAULT_OFF_MS) -> None:
    if shutil.which("pinctrl") is None:
        print("error: pinctrl not found in PATH.  Install with:\n"
              "    sudo apt install raspi-utils", file=sys.stderr)
        raise SystemExit(2)

    # 1. Park signal pins so they can't phantom-power the MSP through
    #    its IO ESD diodes once the rail drops.
    for pin in QUIET_PIN_INPUTS:
        _pinctrl("set", str(pin), "ip")
    # 2. Assert NRST.  Belt-and-braces: even if some current still
    #    sneaks into the rail, the MSP can't run code.
    _pinctrl("set", str(NRST_PIN), "op", "dl")
    # 3. Cut the 3V3 rail.
    _pinctrl("set", str(POWER_PIN), "op", "dl")
    time.sleep(off_ms / 1000.0)
    # 4. Restore the rail.
    _pinctrl("set", str(POWER_PIN), "op", "dh")
    # 5. Give the LDO + decoupling caps a moment to settle.
    time.sleep(0.05)
    # 6. Release NRST.  MCU boots from here.
    _pinctrl("set", str(NRST_PIN), "op", "dh")
    # 7. Release the power pin to input so the on-board pull-up holds
    #    the MOSFET on without us continuing to drive it.
    _pinctrl("set", str(POWER_PIN), "ip")
    # 8. Release NRST to input too.
    _pinctrl("set", str(NRST_PIN), "ip")
    # 9. Wait through the MCU's BCR + early SystemInit so the next tool
    #    (openocd) lands inside the boot-blink window with the MCU
    #    properly initialised.
    time.sleep(0.1)


def _main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ms", type=int, default=DEFAULT_OFF_MS,
                   help="off-duration in milliseconds (default 500)")
    args = p.parse_args()
    print(f"power-cycling MCU: parking signal pins, GPIO {POWER_PIN} LOW for {args.ms} ms …")
    power_cycle(args.ms)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
