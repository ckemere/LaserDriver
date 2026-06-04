#!/usr/bin/env python3
"""LaserHat eink GUI on the slim SSD1680 driver.

A broker client (hat_client.HatClient): it does NOT open the serial port,
so it runs alongside the web GUI.  Button presses arrive as EVT_BUTTON
broadcasts (the firmware reports debounced edges); state arrives as
broadcast snapshots — no polling.  The UI state machine dispatches button
edges, pushes config edits back through the broker, and repaints the
panel with partial refresh for fast feedback.

Button mapping (per physical layout):

       +--------+
       |   B1   |  trigger pulse — firmware fires on release.
       +--------+
       |        |
       |  EINK  |
       |        |
       +--------+
       |   B2   |  cycle selected parameter
       +--------+
       +---+----+
       | B3 | B4 |  decrement / increment selected parameter
       +---+----+

Refresh strategy:
- First paint after boot: full refresh (clears any leftover image).
- Routine updates (button edits, phase change): partial (~300 ms).
- Every Nth partial: full refresh, to clear ghosting (managed inside
  EinkPanel.display()).
- After button presses, wait SETTLE_GAP seconds of quiet before
  pushing a frame, so rapid B4 presses coalesce to one update.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from eink_panel import EinkPanel
from hat_client import DEFAULT_SOCKET, HatClient
from laser_hat import State


# --------------------------------------------------------------- config
POLL_INTERVAL = 0.05         # seconds between '?' polls
SETTLE_GAP    = 0.30         # render after this much quiet time
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
@dataclass
class Param:
    name: str
    step: int
    minimum: int
    maximum: int
    fmt: callable    # value -> display string


def _ticks_to_ms_str(ticks: int) -> str:
    return f"{ticks} ({ticks / 100:.1f} ms)"


PARAMS: list[Param] = [
    Param("i", step=8,   minimum=1, maximum=320,        fmt=lambda v: f"{v} / 320"),
    Param("r", step=200, minimum=1, maximum=10_000_000, fmt=_ticks_to_ms_str),
    Param("h", step=500, minimum=1, maximum=10_000_000, fmt=_ticks_to_ms_str),
]


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
    panel: EinkPanel,
    state: State,
    selected: int,
    ip: str,
    hostname: str,
    *,
    force_full: bool = False,
) -> None:
    W, H = panel.size                  # (250, 122)
    img = panel.new_canvas()
    draw = ImageDraw.Draw(img)

    font_big = load_font(18)
    font_med = load_font(13)
    font_sm  = load_font(10)

    BLACK = 0
    WHITE = 1

    # Header
    draw.text((50, 0), "LaserHAT", fill=BLACK, font=font_big)
    phase_label = "WAIT" if state.phase == "W" else "TRIG"
    # Invert phase chip on TRIG
    if state.phase == "T":
        draw.rectangle((190, 0, W - 1, 20), fill=BLACK)
        draw.text((196, 1), phase_label, fill=WHITE, font=font_med)
    else:
        draw.text((196, 1), phase_label, fill=BLACK, font=font_med)

    # Button hints on the left edge
    draw.text((0, 30), "B1\nTRIG", fill=BLACK, font=font_sm, spacing=0)
    draw.text((0, 75), "B2\nSEL",  fill=BLACK, font=font_sm, spacing=0)

    # Parameter list
    base_x = 38
    base_y = 25
    row_h  = 18
    for idx, p in enumerate(PARAMS):
        y = base_y + idx * row_h
        if idx == selected:
            draw.text((base_x - 11, y - 1), ">", fill=BLACK, font=font_med)
        draw.text((base_x, y), f"{p.name}:", fill=BLACK, font=font_med)
        draw.text((base_x + 22, y), p.fmt(_value_for(state, p.name)),
                  fill=BLACK, font=font_med)

    # Bottom legend + IP / hostname
    draw.line((35, 95, W - 1, 95), fill=BLACK, width=1)
    draw.text((38,  100), "B3:-",      fill=BLACK, font=font_med)
    draw.text((90,  100), "B4:+",      fill=BLACK, font=font_med)
    draw.text((150, 100), f"{ip}",     fill=BLACK, font=font_sm)
    draw.text((150, 111), hostname,    fill=BLACK, font=font_sm)

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
    panel = EinkPanel(rotation=1)

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
