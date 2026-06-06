"""LaserHat binary UART transport (host side).

Speaks the COBS+CRC16 framed protocol the MSPM0 firmware uses on
/dev/ttyS0 (115200 8N1).  See protocol.py for the wire format and
Firmware/laserHatFirmware/protocol.h for the firmware mirror.

This module is the *single UART owner*: only the broker (broker.py)
instantiates LaserUART.  GUIs talk to the broker over its Unix socket
(see hat_client.py), never to the serial port directly.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

import serial

import protocol as proto


DEFAULT_DEVICE = "/dev/ttyS0"
DEFAULT_BAUD = 115200


@dataclass
class State:
    intensity: int          # 1..320
    ramp_ticks: int         # 100 kHz ticks
    hold_ticks: int
    button_mask: int        # 4 bits, bit n = button n+1 pressed
    phase: str              # 'W' (waiting) or 'T' (triggered)
    tick: int               # MSPM0 isr_ticks at the time of query

    def button(self, n: int) -> bool:
        """True if button n (1..4) is pressed."""
        return bool(self.button_mask & (1 << (n - 1)))

    @classmethod
    def from_status_payload(cls, payload: bytes) -> "State":
        return cls(**proto.unpack_status(payload))


class LaserUART:
    """Low-level binary transport over the serial port.

    Not thread-safe for concurrent senders; the broker serialises sends
    behind its own command lock and runs a single reader loop.
    """

    def __init__(
        self,
        device: str = DEFAULT_DEVICE,
        baud: int = DEFAULT_BAUD,
        timeout: float = 0.1,
    ):
        self._ser = serial.Serial(device, baud, timeout=timeout)
        self._dec = proto.StreamDecoder()
        self._write_lock = threading.Lock()
        self._ser.reset_input_buffer()

    def close(self) -> None:
        self._ser.close()

    def __enter__(self) -> "LaserUART":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def send(self, msg_type: int, payload: bytes = b"") -> None:
        """Encode and write one command frame."""
        wire = proto.encode_frame(msg_type, payload)
        with self._write_lock:
            self._ser.write(wire)
            self._ser.flush()

    def read_frames(self) -> Iterator[Tuple[int, bytes]]:
        """Block up to the serial timeout for bytes, yield decoded frames.

        Yields nothing on a timeout with no data; callers loop on it.
        """
        data = self._ser.read(256)
        if data:
            yield from self._dec.feed(data)


# --- tiny CLI for smoke-testing the raw link (no broker) ----------------
def _main() -> int:
    import argparse
    import time

    p = argparse.ArgumentParser(description="LaserHat binary UART smoke tool")
    p.add_argument("--device", default=DEFAULT_DEVICE)
    p.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("query")
    sub.add_parser("trigger")
    sub.add_parser("watch", help="print every frame until Ctrl-C")
    sp = sub.add_parser("config", help="set intensity ramp hold at once")
    sp.add_argument("intensity", type=int)
    sp.add_argument("ramp", type=int)
    sp.add_argument("hold", type=int)

    args = p.parse_args()
    uart = LaserUART(args.device, args.baud)

    def wait_status(deadline=1.0):
        end = time.monotonic() + deadline
        while time.monotonic() < end:
            for mtype, payload in uart.read_frames():
                if mtype == proto.RSP_STATUS:
                    return State.from_status_payload(payload)
        return None

    if args.cmd == "query":
        uart.send(proto.CMD_QUERY)
        print(wait_status() or "no response")
    elif args.cmd == "trigger":
        uart.send(proto.CMD_TRIGGER)
        print(wait_status() or "no response")    # status echo is the ack
    elif args.cmd == "config":
        r = proto.avoid_magic(args.ramp)
        h = proto.avoid_magic(args.hold)
        uart.send(proto.CMD_CONFIG, proto._CONFIG.pack(args.intensity, r, h))
        print(wait_status() or "no response")
    elif args.cmd == "watch":
        names = {v: k for k, v in vars(proto).items()
                 if k.isupper() and isinstance(v, int)}
        try:
            while True:
                for mtype, payload in uart.read_frames():
                    print(names.get(mtype, hex(mtype)), payload.hex())
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
