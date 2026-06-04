"""Client library for the LaserHat broker (broker.py).

GUIs use this instead of opening the serial port: it connects to the
broker's Unix socket, keeps a local cache of the latest broadcast State,
invokes a callback on every state/event update (so GUIs are event-driven,
not polling), and offers the same set_* / trigger / arm methods the old
direct-UART LaserHat had.

IPC is newline-delimited JSON; see broker.py for the message shapes.
"""

from __future__ import annotations

import json
import queue
import socket
import threading
from typing import Callable, Optional

from laser_hat import State

DEFAULT_SOCKET = "/run/laserhat/broker.sock"


def _state_from_msg(msg: dict) -> Optional[State]:
    if not msg.get("mcu_alive") or msg.get("intensity") is None:
        return None
    return State(
        intensity=msg["intensity"],
        ramp_ticks=msg["ramp_ticks"],
        hold_ticks=msg["hold_ticks"],
        button_mask=msg.get("button_mask", 0),
        gpio_armed=msg.get("gpio_armed", False),
        phase=msg.get("phase", "W"),
        tick=msg.get("tick", 0),
    )


class HatClient:
    """Thread-safe broker client.

    on_update(msg: dict) is called from the reader thread for every
    broadcast — both {"type": "state", ...} and {"type": "event", ...}.
    Keep the callback quick; offload heavy work (e.g. an eink repaint).
    """

    def __init__(
        self,
        socket_path: str = DEFAULT_SOCKET,
        on_update: Optional[Callable[[dict], None]] = None,
        timeout: float = 1.0,
    ):
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(socket_path)
        self._rf = self._sock.makefile("r", encoding="utf-8")
        self._send_lock = threading.Lock()
        self._reply_q: "queue.Queue[dict]" = queue.Queue(maxsize=4)
        self._on_update = on_update
        self._timeout = timeout

        self._state: Optional[State] = None
        self._state_lock = threading.Lock()
        self._stop = False

        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    # ----- reader -------------------------------------------------------
    def _read_loop(self) -> None:
        try:
            for line in self._rf:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                mtype = msg.get("type")
                if mtype == "reply":
                    try:
                        self._reply_q.put_nowait(msg)
                    except queue.Full:
                        pass
                    continue
                if mtype == "state":
                    with self._state_lock:
                        self._state = _state_from_msg(msg)
                if self._on_update is not None:
                    try:
                        self._on_update(msg)
                    except Exception:        # noqa: BLE001 — don't kill reader
                        pass
        except (OSError, ValueError):
            pass

    # ----- command path -------------------------------------------------
    def _command(self, msg: dict) -> dict:
        with self._send_lock:
            try:
                while True:
                    self._reply_q.get_nowait()
            except queue.Empty:
                pass
            self._sock.sendall((json.dumps(msg) + "\n").encode())
            try:
                return self._reply_q.get(timeout=self._timeout)
            except queue.Empty:
                return {"ok": False, "error": "timeout"}

    # ----- public API ---------------------------------------------------
    def get_state(self) -> Optional[State]:
        with self._state_lock:
            return self._state

    def set_intensity(self, value: int) -> bool:
        return self._command({"cmd": "set", "knob": "i", "value": value}).get("ok", False)

    def set_ramp(self, ticks: int) -> bool:
        return self._command({"cmd": "set", "knob": "r", "value": ticks}).get("ok", False)

    def set_hold(self, ticks: int) -> bool:
        return self._command({"cmd": "set", "knob": "h", "value": ticks}).get("ok", False)

    def trigger(self) -> bool:
        return self._command({"cmd": "trigger"}).get("ok", False)

    def trigger_gpio(self) -> bool:
        return self._command({"cmd": "trigger_gpio"}).get("ok", False)

    def arm(self) -> bool:
        return self._command({"cmd": "arm"}).get("ok", False)

    def request_query(self) -> None:
        self._command({"cmd": "query"})

    def close(self) -> None:
        self._stop = True
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self) -> "HatClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
