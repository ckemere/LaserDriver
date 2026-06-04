"""Pi-GPIO trigger driver.

Drives Pi GPIO 24, which is wired to MSPM0 PA19 (the Pi-trigger pin
the firmware reclaimed from SWDIO at boot).  A rising edge there
fires a pulse directly via the MCU's GPIO edge ISR, bypassing UART
entirely — useful when you need sub-100 µs latency from an external
event (e.g. an openephys packet) to laser-on.

Use as a library:

    from pi_trigger import PiTrigger
    with PiTrigger() as t:
        t.fire()

Or as a CLI smoke tool:

    python3 pi_trigger.py fire
"""

from __future__ import annotations

import time
from typing import Optional

from gpiozero import DigitalOutputDevice


# Pi GPIO 24 -> MSPM0 PA19 per LaserHAT/gpio_design.md.
DEFAULT_PIN = 24

# 500 µs is comfortably longer than the MCU's 10 µs TIMG0 tick AND
# the worst-case Python time.sleep() jitter on Pi OS.  Setting a
# floor of ~500 µs guarantees the firmware's edge ISR sees the edge.
DEFAULT_PULSE_S = 0.0005


class PiTrigger:
    def __init__(self, pin: int = DEFAULT_PIN, pulse_s: float = DEFAULT_PULSE_S):
        self._pin = DigitalOutputDevice(pin, active_high=True, initial_value=False)
        self._pulse_s = pulse_s

    def fire(self, pulse_s: Optional[float] = None) -> None:
        """Drive the line high for pulse_s seconds, then low."""
        self._pin.on()
        time.sleep(pulse_s if pulse_s is not None else self._pulse_s)
        self._pin.off()

    def close(self) -> None:
        self._pin.close()

    def __enter__(self) -> "PiTrigger":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _main() -> int:
    import sys

    if len(sys.argv) != 2 or sys.argv[1] != "fire":
        print("usage: pi_trigger.py fire", file=sys.stderr)
        return 2

    with PiTrigger() as t:
        t.fire()
    print("fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
