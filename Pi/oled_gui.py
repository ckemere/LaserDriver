#!/usr/bin/env python3
"""LaserHat OLED GUI on the Adafruit 2.23" 128x32 bonnet (SSD1305).

Replaces the old eink GUI: same broker-client design, same button state
machine, just a smaller (128x32) display.  It is a broker client
(hat_client.HatClient): it does NOT open the serial port, so it runs
alongside the web GUI.  Button presses arrive as EVT_BUTTON broadcasts
(the firmware reports debounced edges); state arrives as broadcast
snapshots — no polling.  The UI dispatches button edges, pushes config
edits back through the broker, and repaints the panel.

The bonnet has no onboard buttons; the four buttons below are LaserHAT's
own, reported by the MCU:

    B1  trigger pulse — firmware fires on release.
    B2  cycle selected parameter (i -> r -> h)
    B3  decrement selected parameter
    B4  increment selected parameter

The 128x32 panel is much smaller than the old eink, so the layout is
compacted: a header line (phase chip + IP) over the three parameter
rows, with the selected row marked by '>'.  The OLED repaints fully in a
couple of milliseconds, so there is no partial-vs-full refresh logic —
we still coalesce rapid presses with SETTLE_GAP to avoid visible churn.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time

from PIL import ImageDraw, ImageFont

from oled_panel import OledPanel
from hat_client import DEFAULT_SOCKET, HatClient
from laser_hat import State
from params import PARAMS


# --------------------------------------------------------------- config
POLL_INTERVAL = 0.05         # seconds between state reads
SETTLE_GAP    = 0.15         # render after this much quiet time
IP_CHECK_GAP  = 30.0         # poll IP this often

# Button bits in State.button_mask.
B1, B2, B3, B4 = 0b0001, 0b0010, 0b0100, 0b1000

# Try a few common font paths; fall back to the PIL default bitmap.
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]


def load_font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size=size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


# --------------------------------------------------------------- params
# Step sizes and ranges come from params.PARAMS (shared with the web GUI).
# Only the display-specific value formatting lives here, keyed by knob name.
def _ticks_to_ms_str(ticks: int) -> str:
    return f"{ticks} ({ticks / 100:.1f}ms)"


_FMT = {
    "i": lambda v: f"{v}/320",
    "r": _ticks_to_ms_str,
    "h": _ticks_to_ms_str,
}


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


def _value_for(state: State, name: str) -> int:
    return {"i": state.intensity, "r": state.ramp_ticks, "h": state.hold_ticks}[name]


def _set_for(client: HatClient, name: str):
    return {"i": client.set_intensity, "r": client.set_ramp,
            "h": client.set_hold}[name]


# --------------------------------------------------------------- render
def render(
    panel: OledPanel,
    state: State,
    selected: int,
    ip: str,
    hostname: str,
    *,
    force_full: bool = False,
) -> None:
    W, H = panel.size                  # (128, 32)
    img = panel.new_canvas()
    draw = ImageDraw.Draw(img)

    font = load_font(8)

    ON  = 1     # lit pixel
    OFF = 0     # dark

    # Header line: phase chip (left), IP (right-aligned).
    phase_label = "TRIG" if state.phase == "T" else "WAIT"
    if state.phase == "T":
        draw.rectangle((0, 0, 27, 8), fill=ON)         # inverted chip on TRIG
        draw.text((2, 0), phase_label, fill=OFF, font=font)
    else:
        draw.text((2, 0), phase_label, fill=ON, font=font)

    ip_w = draw.textlength(ip, font=font)
    draw.text((max(30, W - ip_w), 0), ip, fill=ON, font=font)

    # Parameter rows — one per knob, selected row marked with '>'.
    base_y = 8
    row_h  = 8
    for idx, p in enumerate(PARAMS):
        y = base_y + idx * row_h
        prefix = ">" if idx == selected else " "
        text = f"{prefix}{p.name}: {_FMT[p.name](_value_for(state, p.name))}"
        draw.text((0, y), text, fill=ON, font=font)

    panel.display(img, force_full=force_full)


# --------------------------------------------------------------- main loop
def main() -> int:
    sock = os.environ.get("LASERHAT_SOCK", DEFAULT_SOCKET)

    # UI state shared between the broker reader thread (button callback)
    # and the main render loop.
    ui = {"selected": 0, "last_press": 0.0}
    ui_lock = threading.Lock()

    def handle_button(edges: int, client: HatClient) -> None:
        with ui_lock:
            ui["last_press"] = time.monotonic()
            if edges & B2:                       # cycle selected parameter
                ui["selected"] = (ui["selected"] + 1) % len(PARAMS)
            selected = ui["selected"]
        # B3 / B4: -/+ on the selected parameter, pushed via the broker.
        # The resulting state broadcast repaints us.
        direction = (-1 if edges & B3 else 0) + (1 if edges & B4 else 0)
        if direction:
            st = client.get_state()
            if st is not None:
                p = PARAMS[selected]
                cur = _value_for(st, p.name)
                new = max(p.minimum, min(p.maximum, cur + direction * p.step))
                if new != cur:
                    _set_for(client, p.name)(new)

    def on_update(msg: dict) -> None:
        if msg.get("type") == "event" and msg.get("event") == "button":
            handle_button(int(msg.get("edges", 0)), client)

    print(f"connecting to broker at {sock} …", file=sys.stderr)
    client = HatClient(sock, on_update=on_update)

    print("opening display …", file=sys.stderr)
    panel = OledPanel()

    ip = primary_ip()
    hostname = socket.gethostname()
    print(f"IP {ip}  hostname {hostname}", file=sys.stderr)

    # Wait for the first broadcast state (broker polls the MCU on connect).
    deadline = time.monotonic() + 5.0
    state = None
    while state is None and time.monotonic() < deadline:
        state = client.get_state()
        time.sleep(0.05)
    if state is None:
        print("ERROR: no response from MCU; is it flashed and powered?",
              file=sys.stderr)
        return 1

    with ui_lock:
        selected = ui["selected"]
    render(panel, state, selected, ip, hostname, force_full=True)
    last_painted_key = (state.intensity, state.ramp_ticks, state.hold_ticks,
                        state.phase, selected, ip)
    last_ip_check = time.monotonic()

    while True:
        now = time.monotonic()
        state = client.get_state()
        with ui_lock:
            selected = ui["selected"]
            last_press_at = ui["last_press"]
        if state is None:
            time.sleep(POLL_INTERVAL)
            continue

        # Periodic IP refresh.
        if now - last_ip_check >= IP_CHECK_GAP:
            last_ip_check = now
            ip = primary_ip()

        # Repaint when something visible changed AND the user has been quiet
        # for SETTLE_GAP, so a burst of B4 presses coalesces to one refresh
        # at the final value.
        key = (state.intensity, state.ramp_ticks, state.hold_ticks,
               state.phase, selected, ip)
        if key != last_painted_key and (now - last_press_at) >= SETTLE_GAP:
            render(panel, state, selected, ip, hostname)
            last_painted_key = key

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(130)
