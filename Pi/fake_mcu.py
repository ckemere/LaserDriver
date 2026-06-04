#!/usr/bin/env python3
"""Fake MSPM0 — a PTY that speaks the binary protocol, for off-hardware
testing of broker.py / hat_client.py / web_app.py without a real board.

Opens a pseudo-terminal, prints the slave device path on stdout (so a
test harness or you can point the broker at it), and answers the wire
protocol: replies to QUERY/SET/TRIGGER/ARM and, on a trigger, emits
EVT_PULSE_START then EVT_PULSE_END after a short hold.

    python3 fake_mcu.py            # prints e.g. /dev/pts/7
    python3 broker.py --device /dev/pts/7 --no-gpio --socket /tmp/lh.sock
"""

from __future__ import annotations

import os
import pty
import struct
import sys
import threading
import time
import tty

import protocol as proto

PULSE_HOLD_S = 0.15


class FakeMCU:
    def __init__(self, fd: int):
        self._fd = fd
        self._dec = proto.StreamDecoder()
        self._lock = threading.Lock()
        self._t0 = time.monotonic()
        self.state = {
            "intensity": 320, "ramp_ticks": 8000, "hold_ticks": 10000,
            "button_mask": 0, "armed": 0, "phase": "W",
        }

    def _tick(self) -> int:
        return int((time.monotonic() - self._t0) * 100_000) & 0xFFFFFFFF

    def _send(self, msg_type: int, payload: bytes = b"") -> None:
        with self._lock:
            os.write(self._fd, proto.encode_frame(msg_type, payload))

    def _send_status(self) -> None:
        s = self.state
        self._send(proto.RSP_STATUS, proto._STATUS_STRUCT.pack(
            s["intensity"], s["ramp_ticks"], s["hold_ticks"],
            s["button_mask"], s["armed"],
            proto.PHASE_WAITING if s["phase"] == "W" else proto.PHASE_TRIGGERED,
            self._tick()))

    def _ack(self, cmd_type: int, status: int) -> None:
        self._send(proto.RSP_ACK, bytes([cmd_type, status]))

    def _do_pulse(self) -> None:
        self.state["phase"] = "T"
        self._send(proto.EVT_PULSE_START, struct.pack("<I", self._tick()))
        time.sleep(PULSE_HOLD_S)
        self.state["phase"] = "W"
        self._send(proto.EVT_PULSE_END, struct.pack("<I", self._tick()))

    def press_button(self, mask: int, edges: int) -> None:
        """Test hook: simulate a debounced button change."""
        self.state["button_mask"] = mask
        self._send(proto.EVT_BUTTON, bytes([mask, edges]))

    def handle(self, mtype: int, payload: bytes) -> None:
        if mtype == proto.CMD_QUERY:
            self._send_status()
        elif mtype == proto.CMD_SET_INTENSITY and len(payload) == 2:
            v = struct.unpack("<H", payload)[0]
            if 1 <= v <= 320:
                self.state["intensity"] = v
                self._ack(mtype, proto.ACK_OK)
            else:
                self._ack(mtype, proto.ACK_RANGE)
        elif mtype == proto.CMD_SET_RAMP and len(payload) == 4:
            self.state["ramp_ticks"] = struct.unpack("<I", payload)[0]
            self._ack(mtype, proto.ACK_OK)
        elif mtype == proto.CMD_SET_HOLD and len(payload) == 4:
            self.state["hold_ticks"] = struct.unpack("<I", payload)[0]
            self._ack(mtype, proto.ACK_OK)
        elif mtype == proto.CMD_TRIGGER:
            if self.state["phase"] == "W":
                self._ack(mtype, proto.ACK_OK)
                threading.Thread(target=self._do_pulse, daemon=True).start()
            else:
                self._ack(mtype, proto.ACK_BUSY)
        elif mtype == proto.CMD_ARM:
            self.state["armed"] = 1
            self._ack(mtype, proto.ACK_OK)
        else:
            self._ack(mtype, proto.ACK_UNKNOWN)

    def run(self) -> None:
        while True:
            try:
                data = os.read(self._fd, 256)
            except OSError:
                return
            if not data:
                return
            for mtype, payload in self._dec.feed(data):
                self.handle(mtype, payload)


def main() -> int:
    master_fd, slave_fd = pty.openpty()
    tty.setraw(master_fd)
    tty.setraw(slave_fd)
    slave_name = os.ttyname(slave_fd)
    print(slave_name, flush=True)
    print(f"fake_mcu: serving on {slave_name}", file=sys.stderr)

    mcu = FakeMCU(master_fd)
    try:
        mcu.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
