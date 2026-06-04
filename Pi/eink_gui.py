#!/usr/bin/env python3
"""LaserHat eink GUI on the slim SSD1680 driver.

Polls the MSPM0 firmware at 20 Hz, runs press-edge detection on the
debounced button mask, dispatches to a tiny UI state machine, pushes
config edits back, and repaints the panel with partial refresh for
fast feedback.

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

import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from eink_panel import EinkPanel
from laser_hat import LaserHat, State


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


def _set_for(hat: LaserHat, name: str):
    return {"i": hat.set_intensity, "r": hat.set_ramp, "h": hat.set_hold}[name]


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
    print("opening UART …", file=sys.stderr)
    hat = LaserHat()

    print("opening display …", file=sys.stderr)
    panel = EinkPanel(rotation=1)

    ip = primary_ip()
    hostname = socket.gethostname()
    print(f"IP {ip}  hostname {hostname}", file=sys.stderr)

    state = hat.get_state()
    if state is None:
        print("ERROR: no response from MCU; is it flashed and powered?",
              file=sys.stderr)
        return 1

    selected = 0
    prev_buttons = state.button_mask

    # First paint: force full refresh to clear ghosting.
    render(panel, state, selected, ip, hostname, force_full=True)

    last_painted_key = (state.intensity, state.ramp_ticks, state.hold_ticks,
                        state.phase, selected, ip)
    last_press_at  = 0.0
    last_ip_check  = time.monotonic()

    while True:
        now = time.monotonic()

        new_state = hat.get_state()
        if new_state is None:
            time.sleep(POLL_INTERVAL)
            continue

        # Press-edge detection.
        edges = new_state.button_mask & ~prev_buttons
        prev_buttons = new_state.button_mask
        if edges:
            last_press_at = now

        # B2: cycle selected parameter.
        if edges & B2:
            selected = (selected + 1) % len(PARAMS)

        # B3 / B4: -/+ on selected.
        for bit, direction in ((B3, -1), (B4, +1)):
            if edges & bit:
                p = PARAMS[selected]
                cur = _value_for(new_state, p.name)
                new = max(p.minimum, min(p.maximum, cur + direction * p.step))
                if new != cur:
                    _set_for(hat, p.name)(new)
                    # Refresh our snapshot of the value without waiting
                    # for the next poll, so multiple presses stack up
                    # correctly within one settle window.
                    setattr(new_state,
                            {"i": "intensity",
                             "r": "ramp_ticks",
                             "h": "hold_ticks"}[p.name], new)

        # Periodic IP refresh.
        if now - last_ip_check >= IP_CHECK_GAP:
            last_ip_check = now
            ip = primary_ip()

        # Render when state has changed AND the user has been quiet for
        # SETTLE_GAP — that way a burst of B4 presses coalesces to one
        # refresh at the final value.
        key = (new_state.intensity, new_state.ramp_ticks, new_state.hold_ticks,
               new_state.phase, selected, ip)
        if key != last_painted_key and (now - last_press_at) >= SETTLE_GAP:
            render(panel, new_state, selected, ip, hostname)
            last_painted_key = key

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(130)
