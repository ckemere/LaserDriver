"""Pi-GPIO trigger driver.

Drives the HAT's PI_TRIGGER line: Pi GPIO 26 -> MSPM0 PA27 on the Rev 2
HAT, GPIO 18 -> PA4 on the StimHAT and LaserDriverHAT (Rev 1 used GPIO 24
-> PA19).  The default pin follows the board (hat_id.resolve(): HAT EEPROM,
then $LASERHAT_TRIGGER_PIN, then Rev 2).  A rising edge there
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

import hat_id


def default_pin() -> int:
    """The trigger GPIO for the board this Pi is on (see hat_id.py)."""
    return hat_id.resolve().pins["trigger"]


DEFAULT_PIN = default_pin()

# 500 µs is comfortably longer than the MCU's 10 µs TIMG0 tick AND
# the worst-case Python time.sleep() jitter on Pi OS.  Setting a
# floor of ~500 µs guarantees the firmware's edge ISR sees the edge.
DEFAULT_PULSE_S = 0.0005


class PiTrigger:
    def __init__(self, pin: Optional[int] = None, pulse_s: float = DEFAULT_PULSE_S):
        self.pin = DEFAULT_PIN if pin is None else pin
        self._pin = DigitalOutputDevice(self.pin, active_high=True, initial_value=False)
        self._pulse_s = pulse_s

    def fire(self, pulse_s: Optional[float] = None) -> None:
        """Drive the line high for pulse_s seconds, then low."""
        self._pin.on()
        time.sleep(pulse_s if pulse_s is not None else self._pulse_s)
        self._pin.off()

    def close(self) -> None:
        # Drive low explicitly before releasing the line.  gpiozero's
        # close() sets the pin back to input/high-impedance; without
        # this step, the input transition can look like a rising edge
        # to the MCU and fire a spurious pulse.  The MCU also has an
        # internal pull-down on PA27 as a backstop.
        try:
            self._pin.off()
        finally:
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

    print(hat_id.resolve().describe())
    with PiTrigger() as t:
        t.fire()
    print(f"fired GPIO {t.pin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
