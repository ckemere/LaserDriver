#!/usr/bin/env python3
"""LaserHat broker daemon.

The single owner of /dev/ttyS0.  Speaks the binary framed protocol to the
MCU (see protocol.py / laser_hat.py) and exposes a dependency-light
Unix-domain socket to local clients (eink GUI, web GUI — see hat_client.py).

Model: pub/sub.
  * Clients PUBLISH commands up   (set / trigger / trigger_gpio / arm / query).
  * Broker BROADCASTS down        (state snapshots + button / pulse events).

The broker also owns the GPIO trigger (PiTrigger) and the one-time PA19
arming, so clients never touch the serial port or the trigger pin directly.

IPC is newline-delimited JSON (pure stdlib).  Client -> broker:
    {"cmd": "set", "knob": "i", "value": 320}
    {"cmd": "trigger"}            {"cmd": "trigger_gpio"}
    {"cmd": "arm"}               {"cmd": "query"}
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
import socket
import socketserver
import sys
import threading
import time
from typing import Optional

import protocol as proto
from laser_hat import DEFAULT_BAUD, DEFAULT_DEVICE, LaserUART, State

try:
    from pi_trigger import PiTrigger
except Exception:                       # gpiozero may be absent off-Pi
    PiTrigger = None


DEFAULT_SOCKET = os.environ.get("LASERHAT_SOCK", "/run/laserhat/broker.sock")
POLL_INTERVAL = 0.25                    # s between liveness CMD_QUERY polls
ACK_TIMEOUT = 0.5                       # s to wait for an RSP_ACK
LIVENESS_TIMEOUT = 1.5                  # s without a status -> mcu_alive False


class Broker:
    def __init__(self, uart: LaserUART, gpio_trigger=None):
        self._uart = uart
        self._gpio = gpio_trigger

        # Authoritative mirror of MCU state, as the JSON dict we broadcast.
        self._state = {
            "type": "state", "ok": False, "mcu_alive": False,
            "intensity": None, "ramp_ticks": None, "hold_ticks": None,
            "button_mask": 0, "gpio_armed": False, "phase": "W", "tick": 0,
        }
        self._state_lock = threading.Lock()
        self._last_status_at = 0.0
        self._armed = False             # broker's cached arm state

        # Command serialisation: one command in flight, ACK routed here.
        self._cmd_lock = threading.Lock()
        self._reply_q: "queue.Queue[bytes]" = queue.Queue(maxsize=4)

        # Subscribers: each client has a Queue drained by its writer thread.
        self._subs: set[queue.Queue] = set()
        self._subs_lock = threading.Lock()

        self._stop = threading.Event()

    # ----- subscriber registry / broadcast ------------------------------
    def subscribe(self) -> "queue.Queue":
        q: "queue.Queue" = queue.Queue(maxsize=256)
        with self._subs_lock:
            self._subs.add(q)
        # Prime the new subscriber with the current state snapshot.
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
                pass                    # slow client; drop rather than block

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
            try:
                fields = proto.unpack_status(payload)
            except Exception:             # noqa: BLE001
                return
            self._apply_status(fields)
        elif mtype == proto.RSP_ACK:
            try:
                self._reply_q.put_nowait(payload)
            except queue.Full:
                pass
        elif mtype == proto.EVT_PULSE_START:
            tick = int.from_bytes(payload[:4], "little") if len(payload) >= 4 else 0
            self._set_phase("T")
            self._broadcast({"type": "event", "event": "pulse_start", "tick": tick})
        elif mtype == proto.EVT_PULSE_END:
            tick = int.from_bytes(payload[:4], "little") if len(payload) >= 4 else 0
            self._set_phase("W")
            self._broadcast({"type": "event", "event": "pulse_end", "tick": tick})
        elif mtype == proto.EVT_BUTTON and len(payload) >= 2:
            mask, edges = payload[0], payload[1]
            with self._state_lock:
                self._state["button_mask"] = mask
            self._broadcast({"type": "event", "event": "button",
                             "mask": mask, "edges": edges})
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
            self._armed = fields.get("gpio_armed", self._armed)
        if changed:
            self._broadcast_state()

    def _set_phase(self, phase: str) -> None:
        changed = False
        with self._state_lock:
            if self._state["phase"] != phase:
                self._state["phase"] = phase
                changed = True
        if changed:
            self._broadcast_state()

    def _check_liveness(self) -> None:
        with self._state_lock:
            alive = self._state["mcu_alive"]
            stale = (time.monotonic() - self._last_status_at) > LIVENESS_TIMEOUT
            flip = alive and stale and self._last_status_at > 0.0
            if flip:
                self._state["mcu_alive"] = False
                self._state["ok"] = False
        if flip:
            self._broadcast_state()

    # ----- poller -------------------------------------------------------
    def poller_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._uart.send(proto.CMD_QUERY)
            except Exception as exc:      # noqa: BLE001
                print(f"broker: query send failed: {exc}", file=sys.stderr)
            self._stop.wait(POLL_INTERVAL)

    # ----- command path (ACK-correlated) --------------------------------
    def _command(self, msg_type: int, payload: bytes = b"") -> Optional[bytes]:
        """Send a command and wait for the next RSP_ACK.  Returns the ACK
        payload (bytes) or None on timeout."""
        with self._cmd_lock:
            # Drop any stale ACK before issuing.
            try:
                while True:
                    self._reply_q.get_nowait()
            except queue.Empty:
                pass
            self._uart.send(msg_type, payload)
            try:
                return self._reply_q.get(timeout=ACK_TIMEOUT)
            except queue.Empty:
                return None

    @staticmethod
    def _ack_ok(ack: Optional[bytes]) -> bool:
        return bool(ack) and len(ack) >= 2 and ack[1] == proto.ACK_OK

    # ----- client-facing operations -------------------------------------
    def set_knob(self, knob: str, value: int) -> bool:
        spec = {
            "i": (proto.CMD_SET_INTENSITY, proto._U16),
            "r": (proto.CMD_SET_RAMP, proto._U32),
            "h": (proto.CMD_SET_HOLD, proto._U32),
        }.get(knob)
        if spec is None:
            return False
        msg_type, packer = spec
        try:
            ok = self._ack_ok(self._command(msg_type, packer.pack(value)))
        except Exception:                 # struct error (out of range for width)
            return False
        if ok:
            field = {"i": "intensity", "r": "ramp_ticks", "h": "hold_ticks"}[knob]
            with self._state_lock:
                self._state[field] = value
            self._broadcast_state()
        return ok

    def trigger_uart(self) -> bool:
        return self._ack_ok(self._command(proto.CMD_TRIGGER))

    def arm(self) -> bool:
        ok = self._ack_ok(self._command(proto.CMD_ARM))
        if ok:
            self._armed = True
            with self._state_lock:
                self._state["gpio_armed"] = True
            self._broadcast_state()
        return ok

    def trigger_gpio(self) -> bool:
        if self._gpio is None:
            return False
        if not self._armed:
            self.arm()                    # lazy one-time arm
        self._gpio.fire()
        return True

    def request_query(self) -> None:
        try:
            self._uart.send(proto.CMD_QUERY)
        except Exception:                 # noqa: BLE001
            pass

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
            ok = broker.set_knob(knob, value)
            return {"type": "reply", "cmd": "set", "knob": knob, "ok": ok}
        if cmd == "trigger":
            return {"type": "reply", "cmd": "trigger",
                    "ok": broker.trigger_uart()}
        if cmd == "trigger_gpio":
            return {"type": "reply", "cmd": "trigger_gpio",
                    "ok": broker.trigger_gpio()}
        if cmd == "arm":
            return {"type": "reply", "cmd": "arm", "ok": broker.arm()}
        if cmd == "query":
            broker.request_query()
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
