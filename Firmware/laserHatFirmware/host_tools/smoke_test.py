#!/usr/bin/env python3
"""Round-trip smoke test for the LaserHAT UART protocol.

Run on the Pi after `make flash`:

    python3 host_tools/smoke_test.py            # default /dev/ttyS0
    python3 host_tools/smoke_test.py /dev/ttyAMA0

You must be in the `dialout` group (or run with sudo) to open the device.
"""

import sys
import time

import serial


def cmd(s: serial.Serial, line: str, *, expect: str = "OK") -> str:
    """Send a line; return the first response line, stripped."""
    s.reset_input_buffer()
    s.write(line.encode("ascii") + b"\n")
    s.flush()
    reply = s.readline().decode("ascii", errors="replace").rstrip("\r\n")
    print(f"  -> {line!s:10s}  <- {reply!s}")
    if not reply.startswith(expect):
        raise SystemExit(f"unexpected reply {reply!r} to {line!r}")
    return reply


def main() -> int:
    dev = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyS0"
    s = serial.Serial(dev, 115200, timeout=1.0)
    print(f"opened {dev} at 115200")
    s.reset_input_buffer()

    print("\n-- baseline query --")
    cmd(s, "?")

    print("\n-- set + read back --")
    cmd(s, "i 100")
    cmd(s, "r 2000")
    cmd(s, "h 500")
    cmd(s, "?")

    print("\n-- trigger a short pulse --")
    s.reset_input_buffer()
    s.write(b"t\n")
    s.flush()
    # `t` has no immediate ACK; we get start, then later end.
    for _ in range(2):
        line = s.readline().decode("ascii", errors="replace").rstrip("\r\n")
        print(f"  <- {line}")
        if not line.startswith("OK pulse"):
            raise SystemExit(f"expected 'OK pulse ...', got {line!r}")

    print("\n-- restore defaults --")
    cmd(s, "i 320")
    cmd(s, "r 8000")
    cmd(s, "h 10000")
    cmd(s, "?")

    print("\nall checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
