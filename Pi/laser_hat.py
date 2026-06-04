"""LaserHat UART client.

Wraps the line-based ASCII protocol the MSPM0 firmware speaks on
/dev/ttyS0 (115200 8N1).  See Firmware/laserHatFirmware/README.md
for the protocol reference.

Designed to be shared by the eink GUI and any future network / browser
front-ends; nothing here is GUI-specific.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Optional

import serial


# Default device for the Pi mini-UART (Pi 4 default on GPIO 14/15).
DEFAULT_DEVICE = "/dev/ttyS0"
DEFAULT_BAUD = 115200


# Sample status line:
#   OK i=320 r=8000 h=10000 b=0 g=0 phase=W tick=12345678
#
# The `g=` field was added when PA19 reclaim became opt-in; the regex
# tolerates older firmware that omits it.
_STATUS_RE = re.compile(
    r"^OK\s+"
    r"i=(?P<i>\d+)\s+"
    r"r=(?P<r>\d+)\s+"
    r"h=(?P<h>\d+)\s+"
    r"b=(?P<b>\d+)\s+"
    r"(?:g=(?P<g>[01])\s+)?"
    r"phase=(?P<phase>[WT])\s+"
    r"tick=(?P<tick>\d+)\s*$"
)


@dataclass
class State:
    intensity: int          # 1..320
    ramp_ticks: int         # 100 kHz ticks
    hold_ticks: int
    button_mask: int        # 4 bits, bit n = button n+1 pressed
    gpio_armed: bool        # True if PA19 is acting as the Pi-GPIO trigger input
    phase: str              # 'W' (waiting) or 'T' (triggered)
    tick: int               # MSPM0 isr_ticks at the time of query

    def button(self, n: int) -> bool:
        """True if button n (1..4) is pressed."""
        return bool(self.button_mask & (1 << (n - 1)))


class LaserHat:
    """One-line-at-a-time client for the MSPM0 firmware.

    Thread-safe: an internal lock serialises requests so two threads
    can share a single LaserHat without interleaving lines.
    """

    def __init__(
        self,
        device: str = DEFAULT_DEVICE,
        baud: int = DEFAULT_BAUD,
        timeout: float = 0.25,
    ):
        self._ser = serial.Serial(device, baud, timeout=timeout)
        self._lock = threading.Lock()
        # Discard any stale bytes from previous sessions.
        self._ser.reset_input_buffer()

    def close(self) -> None:
        self._ser.close()

    def __enter__(self) -> "LaserHat":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ----- low-level send / receive ----------------------------------
    def _send_line(self, line: str) -> Optional[str]:
        """Send a command, return the first response line (None on timeout)."""
        with self._lock:
            self._ser.reset_input_buffer()
            self._ser.write(line.encode("ascii") + b"\n")
            self._ser.flush()
            reply = self._ser.readline().decode("ascii", errors="replace")
        reply = reply.rstrip("\r\n")
        return reply or None

    # ----- protocol commands -----------------------------------------
    def get_state(self) -> Optional[State]:
        reply = self._send_line("?")
        if reply is None:
            return None
        m = _STATUS_RE.match(reply)
        if not m:
            return None
        return State(
            intensity=int(m["i"]),
            ramp_ticks=int(m["r"]),
            hold_ticks=int(m["h"]),
            button_mask=int(m["b"]),
            gpio_armed=(m["g"] == "1") if m["g"] else False,
            phase=m["phase"],
            tick=int(m["tick"]),
        )

    def _set(self, verb: str, value: int) -> bool:
        reply = self._send_line(f"{verb} {value}")
        return reply is not None and reply.startswith(f"OK {verb}=")

    def set_intensity(self, value: int) -> bool:
        return self._set("i", value)

    def set_ramp(self, ticks: int) -> bool:
        return self._set("r", ticks)

    def set_hold(self, ticks: int) -> bool:
        return self._set("h", ticks)

    def trigger(self) -> bool:
        """Fire a pulse.  Returns True if the MCU accepted the command
        (was in WAITING).  Does not wait for pulse_start / pulse_end."""
        with self._lock:
            self._ser.reset_input_buffer()
            self._ser.write(b"t\n")
            self._ser.flush()
            reply = self._ser.readline().decode("ascii", errors="replace").rstrip("\r\n")
        # 't' has no immediate OK; firmware emits "OK pulse start=..." when
        # it actually triggers (which can take a few ms).  An empty reply
        # means the readline() timed out — a powered-off or wedged MCU —
        # so report failure rather than a phantom success (matches
        # get_state()).  A synchronous "ERR ..." (e.g. busy) is failure too.
        return bool(reply) and not reply.startswith("ERR")

    def arm_gpio_trigger(self) -> bool:
        """Reclaim PA19 on the MCU from SWDIO to a GPIO-input trigger
        pin.  PA19 then responds to rising edges on Pi GPIO 24.

        PA19 starts every boot as SWDIO so SWD flashing always works on
        a fresh MCU; clients who want the GPIO-path trigger must opt in
        by calling this once.  No disarm — reset the MCU to restore
        SWDIO (e.g. `make flash` power-cycles the MCU via GPIO 23)."""
        reply = self._send_line("g")
        return reply is not None and reply.startswith("OK g=")


# ----- quick CLI for smoke-testing without the GUI -------------------
def _main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="LaserHat UART CLI")
    p.add_argument("--device", default=DEFAULT_DEVICE)
    p.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("query")
    sub.add_parser("trigger")
    sp = sub.add_parser("set")
    sp.add_argument("knob", choices=["i", "r", "h"])
    sp.add_argument("value", type=int)
    sub.add_parser("watch", help="poll ? every 0.2 s until Ctrl-C")

    args = p.parse_args()
    hat = LaserHat(args.device, args.baud)

    if args.cmd == "query":
        print(hat.get_state())
    elif args.cmd == "trigger":
        ok = hat.trigger()
        print("OK" if ok else "ERR")
    elif args.cmd == "set":
        ok = {
            "i": hat.set_intensity,
            "r": hat.set_ramp,
            "h": hat.set_hold,
        }[args.knob](args.value)
        print("OK" if ok else "ERR")
    elif args.cmd == "watch":
        try:
            while True:
                print(hat.get_state())
                time.sleep(0.2)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
