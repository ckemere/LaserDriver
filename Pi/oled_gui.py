#!/usr/bin/env python3
"""LaserHat OLED GUI on the Adafruit 2.23" 128x32 bonnet (SSD1305).

Broker-client design: does NOT open the serial port, runs alongside the
web GUI.  Button presses arrive as EVT_BUTTON broadcasts; state arrives
as broadcast snapshots — no polling.

Button mapping (LaserHAT hardware buttons, reported by MCU):
    B1  trigger pulse — firmware fires on release.
    B2  cycle selected row (laser: i→r→h→[mode]; estim: dur→IPI→[mode])
    B3  decrement selected value  (on [mode] row: no-op on −)
    B4  increment selected value  (on [mode] row: toggle LASER↔ESTIM)

Display layout (128×32, font 8px → 4 rows):
    Row 0  header: "LaserHAT[L|E]"  +  IP (right-aligned if it fits)
    Row 1  ┐
    Row 2  ├  3-row scrolling window over the selectable items
    Row 3  ┘  phase chip (WAIT/TRIG) pinned to bottom-right corner

In LASER mode the selectable items are: i, r, h, [mode]
In ESTIM mode the selectable items are: dur (ed), IPI (ei), [mode]
The window scrolls so the selected item is always visible.
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
from params import ESTIM_PARAMS, PARAMS


# --------------------------------------------------------------- config
POLL_INTERVAL = 0.05         # seconds between state reads
SETTLE_GAP    = 0.15         # render after this much quiet time
IP_CHECK_GAP  = 30.0         # poll IP this often

# Button bits in State.button_mask / EVT_BUTTON edges.
B1, B2, B3, B4 = 0b0001, 0b0010, 0b0100, 0b1000

# Sentinel object for the mode-toggle row in the selection cycle.
_MODE_ITEM = object()

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


# --------------------------------------------------------------- item helpers

def _items_for(state: State) -> list:
    """Ordered selectable items for the current mode (params + mode sentinel)."""
    if state.mode == 1:     # ESTIM
        return list(ESTIM_PARAMS) + [_MODE_ITEM]
    return list(PARAMS) + [_MODE_ITEM]


def _value_for(state: State, name: str) -> int:
    return {
        "i":  state.intensity,
        "r":  state.ramp_ticks,
        "h":  state.hold_ticks,
        "ed": state.estim_dur_ticks,
        "ei": state.estim_ipi_ticks,
    }[name]


def _set_for(client: HatClient, name: str):
    return {
        "i":  client.set_intensity,
        "r":  client.set_ramp,
        "h":  client.set_hold,
        "ed": client.set_estim_dur,
        "ei": client.set_estim_ipi,
    }[name]


_FMT = {
    "i":  lambda v: f"{v}/320",
    "r":  lambda v: f"{v}({v/100:.0f}ms)",
    "h":  lambda v: f"{v}({v/100:.0f}ms)",
    "ed": lambda v: f"{v * 10}us",
    "ei": lambda v: f"{v * 10}us",
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
    W, H = panel.size           # (128, 32)
    img = panel.new_canvas()
    draw = ImageDraw.Draw(img)
    font = load_font(8)
    ON, OFF = 1, 0

    # Header: brand with mode tag [L]/[E], IP right-aligned if it fits.
    mode_tag = "E" if state.mode == 1 else "L"
    brand = f"LaserHAT[{mode_tag}]"
    draw.text((0, 0), brand, fill=ON, font=font)
    brand_w = draw.textlength(brand, font=font)
    ip_w = draw.textlength(ip, font=font)
    if brand_w + 4 + ip_w <= W:
        draw.text((W - ip_w, 0), ip, fill=ON, font=font)

    # 3-row scrolling window over selectable items.
    items = _items_for(state)
    n_vis = 3
    win_start = max(0, min(selected, len(items) - n_vis))
    visible = items[win_start:win_start + n_vis]

    base_y, row_h = 8, 8
    for row_i, item in enumerate(visible):
        abs_i = win_start + row_i
        prefix = ">" if abs_i == selected else " "
        if item is _MODE_ITEM:
            mode_str = "ESTIM" if state.mode == 1 else "LASER"
            text = f"{prefix}[mode:{mode_str}]"
        else:
            text = f"{prefix}{item.name}:{_FMT[item.name](_value_for(state, item.name))}"
        draw.text((0, base_y + row_i * row_h), text, fill=ON, font=font)

    # Phase chip pinned to bottom-right, drawn over the tail of the last row.
    phase_label = "TRIG" if state.phase == "T" else "WAIT"
    cw = int(draw.textlength(phase_label, font=font)) + 5
    x0 = W - cw
    y0 = base_y + (n_vis - 1) * row_h
    draw.rectangle((x0 - 2, y0 - 1, W, H), fill=OFF)
    if state.phase == "T":
        draw.rectangle((x0, y0, W - 1, H - 1), fill=ON)
        draw.text((x0 + 3, y0), phase_label, fill=OFF, font=font)
    else:
        draw.text((x0 + 3, y0), phase_label, fill=ON, font=font)

    panel.display(img, force_full=force_full)


# --------------------------------------------------------------- main loop

def main() -> int:
    sock = os.environ.get("LASERHAT_SOCK", DEFAULT_SOCKET)

    ui = {"selected": 0, "last_press": 0.0}
    ui_lock = threading.Lock()

    def handle_button(edges: int, client: HatClient) -> None:
        st = client.get_state()
        items = _items_for(st) if st is not None else list(PARAMS) + [_MODE_ITEM]

        with ui_lock:
            ui["last_press"] = time.monotonic()
            if edges & B2:
                ui["selected"] = (ui["selected"] + 1) % len(items)
            # Clamp in case mode just switched and shrunk the item list.
            selected = min(ui["selected"], len(items) - 1)
            ui["selected"] = selected

        direction = (-1 if edges & B3 else 0) + (1 if edges & B4 else 0)
        if direction and st is not None:
            item = items[selected]
            if item is _MODE_ITEM:
                # B4 = switch to ESTIM, B3 = switch to LASER.
                if edges & B4:
                    client.set_mode("estim")
                elif edges & B3:
                    client.set_mode("laser")
            else:
                cur = _value_for(st, item.name)
                new = max(item.minimum, min(item.maximum, cur + direction * item.step))
                if new != cur:
                    _set_for(client, item.name)(new)

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

    last_painted_key = (
        state.intensity, state.ramp_ticks, state.hold_ticks,
        state.phase, selected, ip,
        state.mode, state.estim_dur_ticks, state.estim_ipi_ticks,
    )
    last_ip_check = time.monotonic()

    while True:
        now = time.monotonic()
        state = client.get_state()

        # Clamp selected to the current item list length (handles mode switch).
        if state is not None:
            items = _items_for(state)
            with ui_lock:
                if ui["selected"] >= len(items):
                    ui["selected"] = len(items) - 1
                selected = ui["selected"]
                last_press_at = ui["last_press"]
        else:
            with ui_lock:
                selected = ui["selected"]
                last_press_at = ui["last_press"]

        if state is None:
            time.sleep(POLL_INTERVAL)
            continue

        if now - last_ip_check >= IP_CHECK_GAP:
            last_ip_check = now
            ip = primary_ip()

        key = (
            state.intensity, state.ramp_ticks, state.hold_ticks,
            state.phase, selected, ip,
            state.mode, state.estim_dur_ticks, state.estim_ipi_ticks,
        )
        if key != last_painted_key and (now - last_press_at) >= SETTLE_GAP:
            render(panel, state, selected, ip, hostname)
            last_painted_key = key

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(130)
