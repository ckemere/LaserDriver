#!/usr/bin/env python3
"""LaserHat web GUI.

Tiny Flask app that exposes the LaserHat parameters and trigger button
to a browser.  Reuses laser_hat.LaserHat for UART comms — same client
object the eink GUI uses, just driven from HTTP routes.

Routes:
    GET  /                  the single page
    GET  /api/state         current MCU state as JSON
    POST /api/set/<knob>    body { "value": N } where knob in {i, r, h}
    POST /api/trigger       fire a pulse via UART 't' command
    POST /api/trigger_gpio  fire a pulse via Pi GPIO 24 -> MSPM0 PA19 edge
    GET  /api/healthz       cheap liveness check

The app binds 0.0.0.0:8080 by default; override via PORT env var.

NOTE: this process and Pi/eink_gui.py both want exclusive UART access.
Stop one before starting the other.  A unified daemon that owns the
UART and serves both surfaces will replace this once they both work.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from dataclasses import asdict
from typing import Optional

from flask import Flask, jsonify, render_template, request

from laser_hat import LaserHat, State
from pi_trigger import PiTrigger


# --------------------------------------------------------------- helpers
def primary_ip() -> str:
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True).split()
        if out:
            return out[0]
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "?.?.?.?"
    finally:
        s.close()


def _state_dict(state: Optional[State]) -> dict:
    if state is None:
        return {"ok": False, "error": "no_response"}
    return {
        "ok": True,
        "intensity":  state.intensity,
        "ramp_ticks": state.ramp_ticks,
        "hold_ticks": state.hold_ticks,
        "button_mask": state.button_mask,
        "phase":       state.phase,      # "W" or "T"
        "tick":        state.tick,
    }


# --------------------------------------------------------------- app
def create_app(hat: LaserHat, gpio_trigger: PiTrigger) -> Flask:
    app = Flask(__name__)
    app.config["hat"] = hat
    app.config["gpio_trigger"] = gpio_trigger
    app.config["hostname"] = socket.gethostname()

    @app.route("/")
    def index() -> str:
        return render_template(
            "index.html",
            hostname=app.config["hostname"],
            ip=primary_ip(),
        )

    @app.route("/api/state")
    def api_state():
        return jsonify(_state_dict(app.config["hat"].get_state()))

    @app.route("/api/set/<knob>", methods=["POST"])
    def api_set(knob: str):
        body = request.get_json(silent=True) or {}
        try:
            value = int(body["value"])
        except (KeyError, ValueError, TypeError):
            return jsonify(ok=False, error="bad_value"), 400

        setter = {
            "i": app.config["hat"].set_intensity,
            "r": app.config["hat"].set_ramp,
            "h": app.config["hat"].set_hold,
        }.get(knob)
        if setter is None:
            return jsonify(ok=False, error="unknown_knob"), 400

        if not setter(value):
            return jsonify(ok=False, error="firmware_rejected"), 400
        return jsonify(ok=True, value=value)

    @app.route("/api/trigger", methods=["POST"])
    def api_trigger():
        """UART-path trigger ('t' command).  Emits OK pulse start/end."""
        ok = app.config["hat"].trigger()
        return jsonify(ok=ok, path="uart")

    @app.route("/api/trigger_gpio", methods=["POST"])
    def api_trigger_gpio():
        """GPIO-path trigger (rising edge on Pi GPIO 24 -> MSPM0 PA19).
        Bypasses UART entirely; firmware fires the pulse from its GPIO
        edge ISR.  No ACK from the MCU — use ? afterwards if you want
        to observe the phase. """
        app.config["gpio_trigger"].fire()
        return jsonify(ok=True, path="gpio")

    @app.route("/api/healthz")
    def api_healthz():
        return jsonify(ok=True)

    return app


def main() -> int:
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")

    print(f"opening UART …", file=sys.stderr)
    hat = LaserHat()

    print(f"opening GPIO trigger pin …", file=sys.stderr)
    gpio_trigger = PiTrigger()

    print(f"serving on {host}:{port} (http://{primary_ip()}:{port}/)",
          file=sys.stderr)

    app = create_app(hat, gpio_trigger)
    # threaded=True so a slow UART round-trip doesn't block other clients.
    app.run(host=host, port=port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(130)
