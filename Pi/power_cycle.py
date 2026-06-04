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
# Pins to park (mode + drive state) so they can't phantom-power the MSP
# through its IO ESD diodes during the brief power-off window.
QUIET_PINS = [14, 24, 25]   # UART TX, SWDIO, SWCLK

DEFAULT_OFF_MS = 500


def _pinctrl(*args: str) -> None:
    subprocess.run(["pinctrl", *args], check=True)


def _get_pin_mode(pin: int) -> str:
    """Return the current `pinctrl` mode string for `pin`.

    pinctrl get output looks like:
        14: a5    pn | hi // GPIO14 = TXD1
    The second whitespace-separated token is the function / mode:
    a0..a8 = alt functions, ip = input, op = output, no = no function.
    """
    out = subprocess.run(["pinctrl", "get", str(pin)],
                         capture_output=True, text=True, check=True)
    parts = out.stdout.split()
    # parts[0] = "14:" ; parts[1] = "a5" (or whatever)
    return parts[1] if len(parts) > 1 else "ip"


def power_cycle(off_ms: int = DEFAULT_OFF_MS) -> None:
    if shutil.which("pinctrl") is None:
        print("error: pinctrl not found in PATH.  Install with:\n"
              "    sudo apt install raspi-utils", file=sys.stderr)
        raise SystemExit(2)

    # 0. Save the current mode of every pin we're about to override, so
    #    we can restore them after the cycle.  Crucial for GPIO 14
    #    (UART TX) — the kernel UART driver doesn't auto-reclaim it
    #    once another tool has stomped on its alt-function setting.
    saved_modes = {pin: _get_pin_mode(pin) for pin in QUIET_PINS}

    # 1. Park signal pins as plain inputs (high-Z).
    for pin in QUIET_PINS:
        _pinctrl("set", str(pin), "ip")
    # 2. Assert NRST.  Even if some current still sneaks into VDD via
    #    a remaining IO clamp, the MSP can't actually run.
    _pinctrl("set", str(NRST_PIN), "op", "dl")
    # 3. Cut the 3V3 rail.
    _pinctrl("set", str(POWER_PIN), "op", "dl")
    time.sleep(off_ms / 1000.0)
    # 4. Restore the rail.
    _pinctrl("set", str(POWER_PIN), "op", "dh")
    # 5. Let LDO + decoupling caps settle.
    time.sleep(0.05)
    # 6. Release NRST.  MCU boots from here.
    _pinctrl("set", str(NRST_PIN), "op", "dh")
    # 7. Release the power pin and NRST to input so their on-board
    #    pull-ups hold the MOSFET on / NRST high without us driving.
    _pinctrl("set", str(POWER_PIN), "ip")
    _pinctrl("set", str(NRST_PIN),  "ip")
    # 8. Restore each parked pin to its previous mode.  The UART TX
    #    line is the one this is really for — the SWD pins typically
    #    saved as "ip" and we re-set them to "ip", which is a no-op.
    for pin, mode in saved_modes.items():
        _pinctrl("set", str(pin), mode)
    # 9. Wait through the MCU's BCR + early SystemInit so anything
    #    that runs after this lands inside the boot-blink window with
    #    the MCU properly initialised.
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
