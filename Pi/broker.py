#!/usr/bin/env python3
"""LaserHat broker daemon.

The single owner of /dev/ttyS0.  Speaks the magic-framed binary protocol
to the MCU (see protocol.py / laser_hat.py) and exposes a dependency-light
Unix-domain socket to local clients (OLED GUI, web GUI — see hat_client.py).

Model: pub/sub.
  * Clients PUBLISH commands up   (set / trigger / trigger_gpio / query).
  * Broker BROADCASTS down        (state snapshots + button / pulse events).

Every MCU command is answered with RSP_STATUS (status-as-ack): the broker
sends a command, waits for the STATUS echo, and (for config) verifies the
MCU now holds the values it sent.  That echo is the integrity check — the
wire protocol has no CRC.  A decoded STATUS is range-checked to reject a
rare false sync.

The broker owns the GPIO trigger pin; PA19 is a trigger from boot, so there
is no arming step.

IPC is newline-delimited JSON.  Client -> broker:
    {"cmd": "set", "knob": "i", "value": 320}   {"cmd": "trigger"}
    {"cmd": "trigger_gpio"}                      {"cmd": "query"}
Broker -> client:
    {"type": "state", "ok": true, "intensity": ..., "phase": "W", ...}
    {"type": "event", "event": "button", "mask": .., "edges": ..}
    {"type": "event", "event": "pulse_start"|"pulse_end", "tick": ..}
    {"type": "reply", "cmd": "set", "ok": true}
"""

from __future__ import annotations

import json
import os
import queue
import socketserver
import sys
import threading
import time
from typing import Optional

import protocol as proto
from laser_hat import DEFAULT_BAUD, DEFAULT_DEVICE, LaserUART

try:
    from pi_trigger import PiTrigger
except Exception:                       # gpiozero may be absent off-Pi
    PiTrigger = None


DEFAULT_SOCKET = os.environ.get("LASERHAT_SOCK", "/run/laserhat/broker.sock")
POLL_INTERVAL = 0.25                    # s between liveness CMD_QUERY polls
REPLY_TIMEOUT = 0.5                     # s to wait for a STATUS echo
LIVENESS_TIMEOUT = 1.5                  # s without a status -> mcu_alive False
_KNOB_FIELD = {"i": "intensity", "r": "ramp_ticks", "h": "hold_ticks"}


class Broker:
    def __init__(self, uart: LaserUART, gpio_trigger=None):
        self._uart = uart
        self._gpio = gpio_trigger

        self._state = {
            "type": "state", "ok": False, "mcu_alive": False,
            "intensity": None, "ramp_ticks": None, "hold_ticks": None,
            "button_mask": 0, "phase": "W", "tick": 0,
        }
        self._state_lock = threading.Lock()
        self._last_status_at = 0.0

        # One command in flight; its STATUS echo is routed here.
        self._cmd_lock = threading.Lock()
        self._reply_q: "queue.Queue[dict]" = queue.Queue(maxsize=4)

        self._subs: set[queue.Queue] = set()
        self._subs_lock = threading.Lock()
        self._stop = threading.Event()

    # ----- subscriber registry / broadcast ------------------------------
    def subscribe(self) -> "queue.Queue":
        q: "queue.Queue" = queue.Queue(maxsize=256)
        with self._subs_lock:
            self._subs.add(q)
        with self._state_lock:
            q.put(dict(self._state))
        return q

    def unsubscribe(self, q: "queue.Queue") -> None:
        with self._subs_lock:
            self._subs.discard(q)

    def _broadcast(self, msg: dict) -> None:
        with self._subs_lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass

    def _broadcast_state(self) -> None:
        with self._state_lock:
            self._broadcast(dict(self._state))

    # ----- UART reader loop ---------------------------------------------
    def reader_loop(self) -> None:
        while not self._stop.is_set():
            try:
                frames = list(self._uart.read_frames())
            except Exception as exc:      # noqa: BLE001
                print(f"broker: UART read error: {exc}", file=sys.stderr)
                time.sleep(0.2)
                continue
            for mtype, payload in frames:
                self._handle_frame(mtype, payload)
            self._check_liveness()

    def _handle_frame(self, mtype: int, payload: bytes) -> None:
        if mtype == proto.RSP_STATUS:
            fields = proto.unpack_status(payload)
            if not proto.status_in_range(fields):
                return                    # false sync; ignore
            self._apply_status(fields)
            try:
                self._reply_q.put_nowait(fields)   # status-as-ack
            except queue.Full:
                pass
        elif mtype == proto.EVT_PULSE_START:
            self._pulse("T", "pulse_start", payload)
        elif mtype == proto.EVT_PULSE_END:
            self._pulse("W", "pulse_end", payload)
        elif mtype == proto.EVT_BUTTON and len(payload) >= 2:
            with self._state_lock:
                self._state["button_mask"] = payload[0]
            self._broadcast({"type": "event", "event": "button",
                             "mask": payload[0], "edges": payload[1]})
            self._broadcast_state()

    def _pulse(self, phase: str, event: str, payload: bytes) -> None:
        tick = int.from_bytes(payload[:4], "little") if len(payload) >= 4 else 0
        with self._state_lock:
            self._state["phase"] = phase
        self._broadcast({"type": "event", "event": event, "tick": tick})
        self._broadcast_state()

    def _apply_status(self, fields: dict) -> None:
        changed = False
        with self._state_lock:
            self._last_status_at = time.monotonic()
            if not self._state["mcu_alive"]:
                self._state["mcu_alive"] = True
                self._state["ok"] = True
                changed = True
            for k, v in fields.items():
                if self._state.get(k) != v:
                    self._state[k] = v
                    changed = True
        if changed:
            self._broadcast_state()

    def _check_liveness(self) -> None:
        flip = False
        with self._state_lock:
            if (self._state["mcu_alive"] and self._last_status_at > 0.0
                    and time.monotonic() - self._last_status_at > LIVENESS_TIMEOUT):
                self._state["mcu_alive"] = False
                self._state["ok"] = False
                flip = True
        if flip:
            self._broadcast_state()

    # ----- poller -------------------------------------------------------
    def poller_loop(self) -> None:
        while not self._stop.is_set():
            self._command(proto.CMD_QUERY)        # refresh state / liveness
            self._stop.wait(POLL_INTERVAL)

    # ----- command path (STATUS-correlated) -----------------------------
    def _command(self, msg_type: int, payload: bytes = b"") -> Optional[dict]:
        """Send a command and wait for its STATUS echo (the ack).  Returns
        the decoded STATUS fields, or None on timeout."""
        with self._cmd_lock:
            try:
                while True:
                    self._reply_q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._uart.send(msg_type, payload)
            except Exception as exc:      # noqa: BLE001
                print(f"broker: send failed: {exc}", file=sys.stderr)
                return None
            try:
                return self._reply_q.get(timeout=REPLY_TIMEOUT)
            except queue.Empty:
                return None

    # ----- client-facing operations -------------------------------------
    def set_knob(self, knob: str, value: int) -> bool:
        field = _KNOB_FIELD.get(knob)
        if field is None:
            return False
        with self._state_lock:
            i = self._state["intensity"]
            r = self._state["ramp_ticks"]
            h = self._state["hold_ticks"]
        if None in (i, r, h):
            return False                  # no baseline config yet
        cfg = {"intensity": i, "ramp_ticks": r, "hold_ticks": h}
        cfg[field] = value
        # Guarantee the CONFIG payload can't contain the SYNC bytes.
        r = proto.avoid_magic(cfg["ramp_ticks"])
        h = proto.avoid_magic(cfg["hold_ticks"])
        i = cfg["intensity"]
        try:
            payload = proto._CONFIG.pack(i, r, h)
        except Exception:                 # out of struct range
            return False
        echo = self._command(proto.CMD_CONFIG, payload)
        # Verify the MCU now holds what we sent (the status-as-ack check).
        return bool(echo and echo["intensity"] == i
                    and echo["ramp_ticks"] == r and echo["hold_ticks"] == h)

    def trigger_uart(self) -> bool:
        return self._command(proto.CMD_TRIGGER) is not None

    def trigger_gpio(self) -> bool:
        if self._gpio is None:
            return False
        self._gpio.fire()                 # PA19 is a trigger from boot; no arm
        return True

    def stop(self) -> None:
        self._stop.set()


# --- Unix socket server --------------------------------------------------
class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        broker: Broker = self.server.broker          # type: ignore[attr-defined]
        q = broker.subscribe()
        stop = threading.Event()

        def writer() -> None:
            while not stop.is_set():
                try:
                    msg = q.get(timeout=0.5)
                except queue.Empty:
                    continue
                try:
                    self.wfile.write((json.dumps(msg) + "\n").encode())
                    self.wfile.flush()
                except OSError:
                    stop.set()
                    return

        wt = threading.Thread(target=writer, daemon=True)
        wt.start()
        try:
            for raw in self.rfile:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    q.put({"type": "reply", "ok": False, "error": "bad_json"})
                    continue
                q.put(self._dispatch(broker, msg))
        except OSError:
            pass
        finally:
            stop.set()
            broker.unsubscribe(q)

    @staticmethod
    def _dispatch(broker: Broker, msg: dict) -> dict:
        cmd = msg.get("cmd")
        if cmd == "set":
            knob = msg.get("knob")
            try:
                value = int(msg["value"])
            except (KeyError, ValueError, TypeError):
                return {"type": "reply", "cmd": "set", "ok": False,
                        "error": "bad_value"}
            return {"type": "reply", "cmd": "set", "knob": knob,
                    "ok": broker.set_knob(knob, value)}
        if cmd == "trigger":
            return {"type": "reply", "cmd": "trigger",
                    "ok": broker.trigger_uart()}
        if cmd == "trigger_gpio":
            return {"type": "reply", "cmd": "trigger_gpio",
                    "ok": broker.trigger_gpio()}
        if cmd == "query":
            broker._command(proto.CMD_QUERY)
            return {"type": "reply", "cmd": "query", "ok": True}
        return {"type": "reply", "ok": False, "error": "unknown_cmd"}


class _Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, path: str, broker: Broker):
        self.broker = broker
        super().__init__(path, _Handler)


def _prepare_socket_path(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="LaserHat broker daemon")
    p.add_argument("--device", default=os.environ.get("LASERHAT_DEVICE",
                                                       DEFAULT_DEVICE))
    p.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    p.add_argument("--socket", default=DEFAULT_SOCKET)
    p.add_argument("--no-gpio", action="store_true",
                   help="don't open the PiTrigger GPIO (off-hardware testing)")
    args = p.parse_args()

    print(f"broker: opening UART {args.device} @ {args.baud}", file=sys.stderr)
    uart = LaserUART(args.device, args.baud)

    gpio = None
    if not args.no_gpio and PiTrigger is not None:
        try:
            gpio = PiTrigger()
        except Exception as exc:          # noqa: BLE001
            print(f"broker: GPIO trigger unavailable: {exc}", file=sys.stderr)

    broker = Broker(uart, gpio)
    threading.Thread(target=broker.reader_loop, daemon=True).start()
    threading.Thread(target=broker.poller_loop, daemon=True).start()

    _prepare_socket_path(args.socket)
    server = _Server(args.socket, broker)
    try:
        os.chmod(args.socket, 0o660)
    except OSError:
        pass
    print(f"broker: serving on {args.socket}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        broker.stop()
        server.shutdown()
        uart.close()
        try:
            os.unlink(args.socket)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
