#!/usr/bin/env python3
"""LaserHat web GUI.

Tiny Flask app that exposes the LaserHat parameters and trigger button
to a browser.  Talks to the broker daemon (broker.py) over its Unix
socket via hat_client.HatClient — it does NOT open the serial port, so
it can run at the same time as the OLED GUI (both are broker clients).

Routes:
    GET  /                  the single page
    GET  /api/state         current MCU state as JSON (from the broker's cache)
    POST /api/set/<knob>    body { "value": N } where knob in {i, r, h}
    POST /api/trigger       fire a pulse via the UART trigger command
    POST /api/trigger_gpio  fire a pulse via Pi GPIO 24 -> MSPM0 PA19 edge
    GET  /api/healthz       cheap liveness check

The app binds 0.0.0.0:8080 by default; override via PORT env var.  The
broker socket path is LASERHAT_SOCK (default /run/laserhat/broker.sock).
"""

from __future__ import annotations

import os
import socket
import sys
from typing import Optional

from flask import Flask, jsonify, render_template, request

from hat_client import DEFAULT_SOCKET, HatClient
from laser_hat import State
from params import ESTIM_PARAMS_BY_NAME, PARAMS_BY_NAME


# --------------------------------------------------------------- helpers
def _if_ipv4(name: str) -> Optional[str]:
    """IPv4 address of one interface via SIOCGIFADDR (stdlib only)."""
    import fcntl
    import struct
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        packed = fcntl.ioctl(
            s.fileno(), 0x8915,  # SIOCGIFADDR
            struct.pack("256s", name.encode()[:15]))
        return socket.inet_ntoa(packed[20:24])
    except OSError:
        return None
    finally:
        s.close()


def interface_ips() -> dict:
    """{'wired': ip-or-None, 'wifi': ip-or-None} — first eth*/en* and wl*
    interface with an IPv4 address.  Mirrors oledd's header logic."""
    ips = {"wired": None, "wifi": None}
    try:
        names = [n for _, n in socket.if_nameindex()]
    except OSError:
        names = []
    for name in names:
        kind = ("wired" if name.startswith(("eth", "en")) else
                "wifi" if name.startswith("wl") else None)
        if kind and ips[kind] is None:
            ips[kind] = _if_ipv4(name)
    return ips


def net_line() -> str:
    """'wired 192.168.17.10 · wifi waiting' — for the page header."""
    ips = interface_ips()
    return (f"wired {ips['wired'] or 'waiting'} · "
            f"wifi {ips['wifi'] or 'waiting'}")


def _state_dict(state: Optional[State]) -> dict:
    if state is None:
        return {"ok": False, "error": "no_response"}
    return {
        "ok": True,
        "intensity":       state.intensity,
        "ramp_ticks":      state.ramp_ticks,
        "hold_ticks":      state.hold_ticks,
        "button_mask":     state.button_mask,
        "phase":           state.phase,
        "tick":            state.tick,
        "mode":            state.mode,
        "estim_dur_ticks": state.estim_dur_ticks,
        "estim_ipi_ticks": state.estim_ipi_ticks,
    }


# --------------------------------------------------------------- app
def create_app(client: HatClient) -> Flask:
    app = Flask(__name__)
    app.config["client"] = client
    app.config["hostname"] = socket.gethostname()

    @app.route("/")
    def index() -> str:
        return render_template(
            "index.html",
            hostname=app.config["hostname"],
            ip=net_line(),
            params=PARAMS_BY_NAME,
            estim_params=ESTIM_PARAMS_BY_NAME,
        )

    @app.route("/api/net")
    def api_net():
        return jsonify(interface_ips())

    @app.route("/api/state")
    def api_state():
        return jsonify(_state_dict(app.config["client"].get_state()))

    @app.route("/api/set/<knob>", methods=["POST"])
    def api_set(knob: str):
        body = request.get_json(silent=True) or {}
        try:
            value = int(body["value"])
        except (KeyError, ValueError, TypeError):
            return jsonify(ok=False, error="bad_value"), 400

        setter = {
            "i":  app.config["client"].set_intensity,
            "r":  app.config["client"].set_ramp,
            "h":  app.config["client"].set_hold,
            "ed": app.config["client"].set_estim_dur,
            "ei": app.config["client"].set_estim_ipi,
        }.get(knob)
        if setter is None:
            return jsonify(ok=False, error="unknown_knob"), 400

        if not setter(value):
            return jsonify(ok=False, error="firmware_rejected"), 400
        return jsonify(ok=True, value=value)

    @app.route("/api/trigger", methods=["POST"])
    def api_trigger():
        """UART-path trigger.  Firmware emits pulse start/end events that
        the broker broadcasts to all clients."""
        ok = app.config["client"].trigger()
        return jsonify(ok=ok, path="uart")

    @app.route("/api/trigger_gpio", methods=["POST"])
    def api_trigger_gpio():
        """GPIO-path trigger (rising edge on Pi GPIO 24 -> MSPM0 PA19).
        Bypasses UART for the trigger itself; firmware fires the pulse
        from its GPIO edge ISR.  The broker owns the PiTrigger pin and
        arms PA19 once (lazily) — no per-trigger re-arm here."""
        ok = app.config["client"].trigger_gpio()
        return jsonify(ok=ok, path="gpio")

    @app.route("/api/set_mode", methods=["POST"])
    def api_set_mode():
        body = request.get_json(silent=True) or {}
        mode = body.get("mode")
        if mode not in ("laser", "estim"):
            return jsonify(ok=False, error="unknown_mode"), 400
        ok = app.config["client"].set_mode(mode)
        return jsonify(ok=ok, mode=mode)

    @app.route("/api/healthz")
    def api_healthz():
        return jsonify(ok=True)

    return app


def main() -> int:
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    sock = os.environ.get("LASERHAT_SOCK", DEFAULT_SOCKET)

    print(f"connecting to broker at {sock} …", file=sys.stderr)
    client = HatClient(sock)

    ips = interface_ips()
    urls = " ".join(f"http://{ip}:{port}/"
                    for ip in (ips["wired"], ips["wifi"]) if ip)
    print(f"serving on {host}:{port} ({urls or 'no addresses yet'})",
          file=sys.stderr)

    app = create_app(client)
    # threaded=True so a slow broker round-trip doesn't block other clients.
    app.run(host=host, port=port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(130)
