#!/usr/bin/env python3
"""Power-cycle the HAT's MSPM0 via its MCU_POWER_EN GPIO.

Board-aware (hat_id.py): the HAT ID EEPROM says which board this is, and
the pins follow from it -- Rev 2: POWER_EN 18, NRST 23, TRIGGER 26;
StimHAT / LaserDriverHAT: POWER_EN 10, NRST 9, TRIGGER 18 (SWCLK 24 /
SWDIO 25 on all three).  --board picks one when the EEPROM is blank
(contradicting the EEPROM needs --force); LASERHAT_POWER_PIN /
LASERHAT_NRST_PIN / LASERHAT_TRIGGER_PIN / LASERHAT_SWCLK_PIN /
LASERHAT_SWDIO_PIN override single pins; Rev 2 is the fallback.

Uses Raspberry Pi OS's stock `pinctrl` tool — pre-installed on every
recent Pi OS image, works the same on Pi 4 / Pi 5, doesn't care about
lgpio / RPi.GPIO.

The trick that makes this actually reset the MCU: every Pi GPIO that
connects to an MSP IO pin must be parked at a non-driving state before
GPIO 18 cuts the rail, otherwise the MSP's IO ESD diodes clamp the
signal back to VDD and phantom-power the chip just enough to keep it
half-running.  The biggest culprit in practice is Pi GPIO 14 (UART
TX), which the kernel UART driver normally idles HIGH.

Pins parked during the cycle (Rev 2 numbers; the board's own otherwise):
    GPIO 14 (UART TX -> MCU RX)   set to INPUT  (high-Z)
    GPIO 23 (NRST)                drive LOW    (asserted)
    GPIO 24 (SWCLK -> PA20)       set to INPUT
    GPIO 25 (SWDIO -> PA19)       set to INPUT
    GPIO 26 (PI_TRIGGER -> PA27)  set to INPUT

After the rail is restored, NRST is released back to HIGH so
the MCU comes out of reset, and the UART/SWD pins are left as inputs
— the kernel UART driver will reclaim GPIO 14/15 the next time
something opens /dev/ttyS0, and OpenOCD reclaims 18/24/25 itself at
the next flash.

Used by `make flash` as a prerequisite.

Manual use:
    python3 Pi/power_cycle.py           # default 500 ms off
    python3 Pi/power_cycle.py --ms 1000 # custom off-duration
    python3 Pi/power_cycle.py --board stim   # blank EEPROM: say which board
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time


# Pins come from hat_id.resolve() (HAT EEPROM, then the LASERHAT_*_PIN
# overrides -- Rev 1 boards get theirs from `make flash HAT_REV=1` -- then
# Rev 2 as the fallback).
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import hat_id  # noqa: E402

UART_TX_PIN = 14

# If we capture GPIO 14 in plain-input mode, that probably means a
# previous power_cycle left it parked instead of restoring the kernel
# UART driver's alt function.  Fall back to this alt so we don't carry
# the broken state forward indefinitely.
# - a5 = mini-UART (TXD1), used by /dev/ttyS0  (the LaserHAT default)
# - a0 = PL011    (TXD0), used by /dev/ttyAMA0
UART_TX_FALLBACK_ALT = "a5"

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


def quiet_pins(pins: dict) -> list:
    """Pins to park (mode + drive state) so they can't phantom-power the MSP
    through its IO ESD diodes during the brief power-off window: UART TX,
    SWCLK, SWDIO, PI_TRIGGER."""
    return [UART_TX_PIN, pins["swclk"], pins["swdio"], pins["trigger"]]


def power_cycle(off_ms: int = DEFAULT_OFF_MS, pins: dict = None) -> None:
    """pins: hat_id pin map (default: hat_id.resolve() -- EEPROM, env, Rev 2)."""
    if pins is None:
        pins = hat_id.resolve().pins
    POWER_PIN, NRST_PIN = pins["power"], pins["nrst"]
    QUIET_PINS = quiet_pins(pins)
    if shutil.which("pinctrl") is None:
        print("error: pinctrl not found in PATH.  Install with:\n"
              "    sudo apt install raspi-utils", file=sys.stderr)
        raise SystemExit(2)

    # 0. Save the current mode of every pin we're about to override, so
    #    we can restore them after the cycle.  Crucial for GPIO 14
    #    (UART TX) — the kernel UART driver doesn't auto-reclaim it
    #    once another tool has stomped on its alt-function setting.
    saved_modes = {pin: _get_pin_mode(pin) for pin in QUIET_PINS}
    # If 14 is already parked (a previous run failed to restore it),
    # use the known UART alt as the restore target instead of carrying
    # the broken state forward.
    if saved_modes.get(UART_TX_PIN) == "ip":
        print(f"GPIO 14 was already parked as input; will restore to "
              f"{UART_TX_FALLBACK_ALT} instead of 'ip'.", file=sys.stderr)
        saved_modes[UART_TX_PIN] = UART_TX_FALLBACK_ALT

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
    p.add_argument("--board", choices=list(hat_id.BOARDS),
                   help="board when the HAT EEPROM does not say (contradicting "
                        "it needs --force)")
    p.add_argument("--force", action="store_true",
                   help="let --board win over a contradicting HAT EEPROM")
    args = p.parse_args()
    r = hat_id.resolve(args.board, force=args.force)
    for n in r.notes:
        print(f"power_cycle: note: {n}", file=sys.stderr)
    if r.conflict and not args.force:
        print(f"power_cycle: refusing: the HAT EEPROM says {r.eeprom_board}, "
              f"--board says {args.board} (add --force to drive {args.board}'s pins)",
              file=sys.stderr)
        return 1
    print(f"power_cycle: {r.describe()}")
    print(f"power-cycling MCU: parking signal pins, GPIO {r.pins['power']} LOW "
          f"for {args.ms} ms …")
    power_cycle(args.ms, r.pins)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
