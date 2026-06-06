#!/usr/bin/env python3
"""Fake MSPM0 — a PTY that speaks the magic-framed protocol, for testing
broker.py / hat_client.py / web_app.py off-hardware.

Opens a pseudo-terminal, prints the slave device path on stdout, and
answers the wire protocol: every command (CONFIG / TRIGGER / QUERY) is
answered with RSP_STATUS (status-as-ack), and a trigger also emits
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
        self._cmd = proto.StreamDecoder(proto.CMD_LEN)   # decode commands
        self._lock = threading.Lock()
        self._t0 = time.monotonic()
        self.state = {"intensity": 320, "ramp_ticks": 8000, "hold_ticks": 10000,
                      "button_mask": 0, "phase": "W"}

    def _tick(self) -> int:
        return int((time.monotonic() - self._t0) * 100_000) & 0xFFFFFFFF

    def _send(self, msg_type: int, payload: bytes = b"") -> None:
        with self._lock:
            os.write(self._fd, proto.encode_frame(msg_type, payload))

    def _send_status(self) -> None:
        s = self.state
        self._send(proto.RSP_STATUS, proto._STATUS.pack(
            s["intensity"], s["ramp_ticks"], s["hold_ticks"],
            s["button_mask"],
            proto.PHASE_WAITING if s["phase"] == "W" else proto.PHASE_TRIGGERED,
            self._tick()))

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
        if mtype == proto.CMD_CONFIG and len(payload) == 10:
            i, r, h = proto.unpack_config(payload)
            if 1 <= i <= 320 and 1 <= r <= 10_000_000 and 1 <= h <= 10_000_000:
                self.state.update(intensity=i, ramp_ticks=r, hold_ticks=h)
            self._send_status()          # status-as-ack (echoes result)
        elif mtype == proto.CMD_TRIGGER:
            if self.state["phase"] == "W":
                threading.Thread(target=self._do_pulse, daemon=True).start()
            self._send_status()
        elif mtype == proto.CMD_QUERY:
            self._send_status()

    def run(self) -> None:
        while True:
            try:
                data = os.read(self._fd, 256)
            except OSError:
                return
            if not data:
                return
            for mtype, payload in self._cmd.feed(data):
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
