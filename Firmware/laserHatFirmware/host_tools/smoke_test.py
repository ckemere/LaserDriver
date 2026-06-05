#!/usr/bin/env python3
"""Round-trip smoke test for the LaserHAT binary UART protocol.

Run on the Pi after `make flash`.  The broker owns the serial port, so
stop it first:

    sudo systemctl stop laserhat-broker.service
    python3 host_tools/smoke_test.py            # default /dev/ttyS0
    python3 host_tools/smoke_test.py /dev/ttyAMA0
    sudo systemctl start laserhat-broker.service

Reuses the Pi-side codec (Pi/protocol.py) and transport (Pi/laser_hat.py)
so there is a single wire-protocol implementation.  You must be in the
`dialout` group (or run with sudo) to open the device.
"""

import os
import sys
import time

# Reuse the Pi-side protocol + transport (single source of truth).
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "Pi"))

import protocol as proto          # noqa: E402
from laser_hat import LaserUART, State   # noqa: E402


class Reader:
    """Buffers decoded frames so a single read() that returns several
    frames (e.g. RSP_ACK + EVT_PULSE_START together) doesn't lose any."""

    def __init__(self, uart):
        self._uart = uart
        self._buf = []

    def wait_for(self, types, timeout=2.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self._buf:
                mtype, payload = self._buf.pop(0)
                if mtype in types:
                    return mtype, payload
                continue           # unrelated frame; skip it
            self._buf.extend(self._uart.read_frames())
        return None


def query(uart, rdr: Reader) -> State:
    uart.send(proto.CMD_QUERY)
    got = rdr.wait_for({proto.RSP_STATUS})
    if not got:
        raise SystemExit("no RSP_STATUS — is the MCU flashed and powered?")
    st = State.from_status_payload(got[1])
    print(f"  state: {st}")
    return st


def set_knob(uart, rdr: Reader, msg_type, payload, label):
    uart.send(msg_type, payload)
    got = rdr.wait_for({proto.RSP_ACK})
    ok = bool(got) and got[1][1] == proto.ACK_OK
    print(f"  -> {label:12s} <- {'ACK ok' if ok else 'NO ACK / rejected'}")
    if not ok:
        raise SystemExit(f"set {label} failed")


def main() -> int:
    dev = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyS0"
    uart = LaserUART(dev, 115200)
    rdr = Reader(uart)
    print(f"opened {dev} at 115200 (binary framed protocol)")

    print("\n-- baseline query --")
    query(uart, rdr)

    print("\n-- set + read back --")
    set_knob(uart, rdr, proto.CMD_SET_INTENSITY, proto._U16.pack(100), "i=100")
    set_knob(uart, rdr, proto.CMD_SET_RAMP,      proto._U32.pack(2000), "r=2000")
    set_knob(uart, rdr, proto.CMD_SET_HOLD,      proto._U32.pack(500),  "h=500")
    query(uart, rdr)

    print("\n-- trigger a short pulse --")
    uart.send(proto.CMD_TRIGGER)
    ack = rdr.wait_for({proto.RSP_ACK})
    if not (ack and ack[1][1] == proto.ACK_OK):
        raise SystemExit("trigger not acked")
    start = rdr.wait_for({proto.EVT_PULSE_START})
    end = rdr.wait_for({proto.EVT_PULSE_END})
    if not (start and end):
        raise SystemExit(f"missing pulse events (start={bool(start)} end={bool(end)})")
    print("  <- EVT_PULSE_START / EVT_PULSE_END")

    print("\n-- restore defaults --")
    set_knob(uart, rdr, proto.CMD_SET_INTENSITY, proto._U16.pack(320),   "i=320")
    set_knob(uart, rdr, proto.CMD_SET_RAMP,      proto._U32.pack(8000),  "r=8000")
    set_knob(uart, rdr, proto.CMD_SET_HOLD,      proto._U32.pack(10000), "h=10000")
    query(uart, rdr)

    print("\nall checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
