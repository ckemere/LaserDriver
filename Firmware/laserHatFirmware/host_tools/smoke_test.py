#!/usr/bin/env python3
"""Round-trip smoke test for the LaserHAT magic-framed protocol.

Run on the Pi after `make flash`.  The broker owns the serial port, so
stop it first:

    sudo systemctl stop laserhat-broker.service
    python3 host_tools/smoke_test.py            # default /dev/ttyS0
    python3 host_tools/smoke_test.py /dev/ttyAMA0
    sudo systemctl start laserhat-broker.service

Reuses the Pi-side codec (Pi/protocol.py) and transport (Pi/laser_hat.py)
so there is a single wire-protocol implementation.  Every command is
answered with RSP_STATUS (status-as-ack).  You must be in the `dialout`
group (or run with sudo) to open the device.
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "Pi"))

import protocol as proto          # noqa: E402
from laser_hat import LaserUART, State   # noqa: E402


class Reader:
    """Buffers decoded frames so a single read() that returns several
    frames (e.g. RSP_STATUS + EVT_PULSE_START) doesn't lose any."""

    def __init__(self, uart):
        self._uart = uart
        self._buf = []

    def wait_for(self, types, timeout=2.0):
        # Scan the buffer for a matching frame, removing only it so frames
        # that arrived out of order (e.g. EVT_PULSE_START before the status
        # ack) aren't discarded while waiting for a different type.
        end = time.monotonic() + timeout
        while True:
            for idx, (mtype, payload) in enumerate(self._buf):
                if mtype in types:
                    del self._buf[idx]
                    return mtype, payload
            if time.monotonic() >= end:
                return None
            self._buf.extend(self._uart.read_frames())


def status(uart, rdr: Reader, label: str) -> State:
    got = rdr.wait_for({proto.RSP_STATUS})
    if not got:
        raise SystemExit(f"{label}: no RSP_STATUS — MCU flashed and powered?")
    st = State.from_status_payload(got[1])
    print(f"  {label}: {st}")
    return st


def main() -> int:
    dev = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyS0"
    uart = LaserUART(dev, 115200)
    rdr = Reader(uart)
    print(f"opened {dev} at 115200 (magic-framed binary protocol)")

    print("\n-- baseline query --")
    uart.send(proto.CMD_QUERY)
    status(uart, rdr, "query")

    print("\n-- config (i=100 r=2000 h=500) --")
    uart.send(proto.CMD_CONFIG, proto._CONFIG.pack(100, 2000, 500))
    st = status(uart, rdr, "echo")
    if (st.intensity, st.ramp_ticks, st.hold_ticks) != (100, 2000, 500):
        raise SystemExit("config echo did not match")

    print("\n-- trigger a short pulse --")
    uart.send(proto.CMD_TRIGGER)
    status(uart, rdr, "ack")           # status-as-ack
    start = rdr.wait_for({proto.EVT_PULSE_START})
    end = rdr.wait_for({proto.EVT_PULSE_END})
    if not (start and end):
        raise SystemExit(f"missing pulse events (start={bool(start)} end={bool(end)})")
    print("  <- EVT_PULSE_START / EVT_PULSE_END")

    print("\n-- restore defaults --")
    uart.send(proto.CMD_CONFIG, proto._CONFIG.pack(320, 8000, 10000))
    status(uart, rdr, "echo")

    print("\nall checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
