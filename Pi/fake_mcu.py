#!/usr/bin/env python3
"""Fake MSPM0 — a PTY that speaks the magic-framed protocol, for testing
broker.py / hat_client.py / web_app.py off-hardware.

Opens a pseudo-terminal, prints the slave device path on stdout, and
answers the wire protocol: every command (CONFIG / TRIGGER / QUERY) is
answered with RSP_STATUS (status-as-ack), and a trigger also emits
EVT_PULSE_START then EVT_PULSE_END after a short hold.

    python3 fake_mcu.py            # prints e.g. /dev/pts/7
    python3 broker.py --device /dev/pts/7 --no-gpio --socket /tmp/lh.sock

--board rev2|stim|laser|unknown emulates that board's firmware build: the
RSP_VERSION board byte (unknown = 0, the firmware from before the
three-board split), the modes it accepts (stim: e-stim only, laser: laser
only -- CMD_SET_MODE to the other is answered with the unchanged mode,
like the real firmware) and the mode it boots in.  SIGUSR1 simulates a
press + release of the board's last button: bit 6 (joystick right) on a
StimHAT / LaserDriverHAT, bit 4 (FIRE) otherwise.
"""

from __future__ import annotations

import argparse
import os
import pty
import signal
import struct
import sys
import threading
import time
import tty

import protocol as proto

PULSE_HOLD_S = 0.15

# What CMD_GET_VERSION is answered with (tests override through the
# environment; FAKE_MCU_NO_VERSION=1 ignores the command like the firmware
# builds before protocol 2 did).
FAKE_VERSION = os.environ.get("FAKE_MCU_VERSION", "fake")
FAKE_PROTO = int(os.environ.get("FAKE_MCU_PROTO", str(proto.PROTO_VERSION)))
FAKE_NO_VERSION = os.environ.get("FAKE_MCU_NO_VERSION") == "1"
FAKE_BOARD = os.environ.get("FAKE_MCU_BOARD", "rev2")

BOARD_MODES = {"rev2": (proto.MODE_LASER, proto.MODE_ESTIM),
               "unknown": (proto.MODE_LASER, proto.MODE_ESTIM),
               "stim": (proto.MODE_ESTIM,),
               "laser": (proto.MODE_LASER,)}
BUTTON_HOLD_S = 0.4          # > the broker's 0.25 s poll: STATUS carries the bit


class FakeMCU:
    def __init__(self, fd: int, board: str = FAKE_BOARD):
        self._fd = fd
        self.board = board
        self.modes = BOARD_MODES[board]
        self._cmd = proto.StreamDecoder(proto.CMD_LEN)   # decode commands
        self._lock = threading.Lock()
        self._t0 = time.monotonic()
        self.state = {"intensity": 320, "ramp_ticks": 8000, "hold_ticks": 10000,
                      "button_mask": 0, "phase": "W",
                      "mode": self.modes[0],
                      "estim_dur_ticks": 10, "estim_ipi_ticks": 10,
                      "laser_dac": proto.LASER_DAC_DEFAULT,
                      "estim_dac": proto.ESTIM_DAC_DEFAULT,
                      "module": 0, "adc_pd": 0, "adc_comp": 0}
        if self.state["mode"] == proto.MODE_ESTIM:      # StimHAT boots in e-stim
            self.state["module"] = proto.MODULE_ESTIM_READY

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
            self._tick(),
            s["mode"], s["estim_dur_ticks"], s["estim_ipi_ticks"],
            s["laser_dac"], s["estim_dac"], s["module"],
            s["adc_pd"], s["adc_comp"]))

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

    def press_last_button(self) -> None:
        """Test hook (SIGUSR1): press and release the board's last button."""
        bit = proto.BUTTON_RIGHT if self.board in ("stim", "laser") else 0x10
        self.press_button(bit, bit)
        time.sleep(BUTTON_HOLD_S)
        self.press_button(0, bit)

    def fault(self) -> None:
        """Test hook: simulate a latched module fault."""
        self.state["module"] |= proto.MODULE_FAULT_LATCHED
        self.state["phase"] = "W"
        self._send(proto.EVT_FAULT, proto._FAULT.pack(self.state["module"], self._tick()))

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
        elif mtype == proto.CMD_SET_MODE and len(payload) == 1:
            # A board refuses the mode it does not have (echo = unchanged).
            if payload[0] in self.modes and self.state["phase"] == "W":
                self.state["mode"] = payload[0]
                # The real e-stim module reports ready once its DAC acks.
                ready = proto.MODULE_ESTIM_READY if payload[0] == proto.MODE_ESTIM else 0
                self.state["module"] = (self.state["module"] & proto.MODULE_FAULT_LATCHED) | ready
            self._send_status()          # status-as-ack (echoes result)
        elif mtype == proto.CMD_LASER_CURRENT and len(payload) == 2:
            code = proto.unpack_dac(payload)
            if code <= proto.LASER_DAC_MAX:
                self.state["laser_dac"] = code
            self._send_status()
        elif mtype == proto.CMD_ESTIM_CURRENT and len(payload) == 2:
            code = proto.unpack_dac(payload)
            if code <= proto.ESTIM_DAC_MAX:
                self.state["estim_dac"] = code
            self._send_status()
        elif mtype == proto.CMD_CLEAR_FAULT:
            self.state["module"] &= ~proto.MODULE_FAULT_LATCHED
            self._send_status()
        elif mtype == proto.CMD_ESTIM_CONFIG and len(payload) == 8:
            dur, ipi = proto._ESTIM_CONFIG.unpack(payload)
            if (proto.ESTIM_TICKS_MIN <= dur <= proto.ESTIM_TICKS_MAX
                    and proto.ESTIM_TICKS_MIN <= ipi <= proto.ESTIM_TICKS_MAX):
                self.state.update(estim_dur_ticks=dur, estim_ipi_ticks=ipi)
            self._send_status()
        elif mtype == proto.CMD_GET_VERSION:
            if not FAKE_NO_VERSION:      # old firmware: silently ignored
                self._send(proto.RSP_VERSION, proto.pack_version_payload(
                    FAKE_PROTO, FAKE_VERSION,
                    proto.BOARD_TYPES_BY_NAME.get(self.board, proto.BOARD_TYPE_UNKNOWN)))

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
    ap = argparse.ArgumentParser(description="fake LaserHAT MCU on a PTY")
    ap.add_argument("--board", choices=list(BOARD_MODES), default=FAKE_BOARD,
                    help="firmware build to emulate (default $FAKE_MCU_BOARD or rev2)")
    args = ap.parse_args()
    master_fd, slave_fd = pty.openpty()
    tty.setraw(master_fd)
    tty.setraw(slave_fd)
    slave_name = os.ttyname(slave_fd)
    print(slave_name, flush=True)
    print(f"fake_mcu: serving on {slave_name} as a {args.board} board", file=sys.stderr)

    mcu = FakeMCU(master_fd, args.board)
    # The handler only starts a thread: the main thread may hold _lock.
    signal.signal(signal.SIGUSR1, lambda *_: threading.Thread(
        target=mcu.press_last_button, daemon=True).start())
    try:
        mcu.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
