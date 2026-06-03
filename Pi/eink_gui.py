#!/usr/bin/env python3
"""LaserHat eink GUI.

Polls the MSPM0 firmware over UART, runs a small UI state machine on
button-press edges, pushes config changes back, and renders the
result onto the SSD1680Z panel.

Physical button placement (per the LaserHAT mechanical layout):

       +--------+
       |   B1   |  trigger (firmware also fires a pulse on B1 release,
       +--------+   so the Pi just labels it; no UART send needed)
       |        |
       | EINK   |
       |        |
       +--------+
       |   B2   |  cycle selected parameter
       +--------+
       +---+----+
       | B3 | B4 |  decrement / increment selected parameter
       +---+----+

Eink full refresh on this panel takes ~3 s, so we coalesce changes
and only push a new frame at most once every REFRESH_MIN_GAP seconds.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional

import board
import busio
import digitalio
from adafruit_epd.epd import Adafruit_EPD
from adafruit_epd.ssd1680 import Adafruit_SSD1680Z

from laser_hat import LaserHat, State


# --------------------------------------------------------------- config
POLL_INTERVAL = 0.05         # seconds between '?' polls
REFRESH_MIN_GAP = 2.0        # don't paint more often than this

# Button bit positions in State.button_mask.
B1, B2, B3, B4 = 0b0001, 0b0010, 0b0100, 0b1000

# Parameters the GUI can edit, in cycle order, with step sizes and bounds.
@dataclass
class Param:
    name: str            # short name shown on screen ('i', 'r', 'h')
    full: str            # long label
    step: int
    minimum: int
    maximum: int
    unit: str            # display unit suffix ('', 'ticks', ...)
    fmt_value: callable  # how to render the value


def _ticks_to_ms_str(ticks: int) -> str:
    """100 kHz tick → milliseconds, 1 decimal place."""
    return f"{ticks} ({ticks / 100:.1f} ms)"


PARAMS: list[Param] = [
    Param("i", "intensity",   step=8,    minimum=1,   maximum=320,
          unit="", fmt_value=lambda v: f"{v} / 320"),
    Param("r", "ramp_ticks",  step=200,  minimum=1,   maximum=10_000_000,
          unit="ticks", fmt_value=_ticks_to_ms_str),
    Param("h", "hold_ticks",  step=500,  minimum=1,   maximum=10_000_000,
          unit="ticks", fmt_value=_ticks_to_ms_str),
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


def make_display() -> Adafruit_SSD1680Z:
    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
    display = Adafruit_SSD1680Z(
        122, 250, spi,
        cs_pin=digitalio.DigitalInOut(board.CE0),
        dc_pin=digitalio.DigitalInOut(board.D22),
        sramcs_pin=None,
        rst_pin=digitalio.DigitalInOut(board.D27),
        busy_pin=digitalio.DigitalInOut(board.D17),
    )
    display.rotation = 1            # landscape: 250 wide × 122 tall
    return display


def render(
    display: Adafruit_SSD1680Z,
    state: State,
    selected: int,
    ip: str,
    hostname: str,
) -> None:
    display.fill(Adafruit_EPD.WHITE)

    BLACK = Adafruit_EPD.BLACK
    RED   = Adafruit_EPD.RED

    # ---------- header row ----------
    display.text("LaserHAT", 50, 2, BLACK, size=2)
    phase_label = "WAIT" if state.phase == "W" else "TRIG"
    phase_color = BLACK if state.phase == "W" else RED
    display.text(phase_label, 195, 2, phase_color, size=2)

    # ---------- B1 hint, top-left ----------
    display.text("B1:", 0, 25, BLACK)
    display.text("TRIG", 0, 35, BLACK)

    # ---------- B2 hint, mid/bottom-left ----------
    display.text("B2:", 0, 70, BLACK)
    display.text("SEL", 0, 80, BLACK)

    # ---------- parameter list ----------
    rows = [
        ("i", state.intensity),
        ("r", state.ramp_ticks),
        ("h", state.hold_ticks),
    ]
    base_x = 35
    base_y = 25
    for idx, ((name, value), param) in enumerate(zip(rows, PARAMS)):
        y = base_y + idx * 16
        if idx == selected:
            display.text(">", base_x - 8, y, RED)
        display.text(f"{name}:", base_x, y, BLACK)
        display.text(param.fmt_value(value), base_x + 24, y, BLACK)

    # ---------- B3 / B4 hints across the bottom ----------
    bottom_y = 100
    display.text("B3:-", 35,  bottom_y, BLACK)
    display.text("B4:+", 115, bottom_y, BLACK)

    # ---------- IP + hostname, bottom-right corner ----------
    display.text(ip,       170, bottom_y,      BLACK)
    display.text(hostname, 170, bottom_y + 10, BLACK)

    # ---------- thin red rule above bottom legend ----------
    display.fill_rect(35, bottom_y - 4, 215, 1, RED)

    display.display()


# --------------------------------------------------------------- main loop
def apply_change(hat: LaserHat, param: Param, current: int, direction: int) -> Optional[int]:
    """Compute the new value and push it to the MCU.  Returns new value
    on success, None on failure / no-op."""
    new = current + direction * param.step
    new = max(param.minimum, min(param.maximum, new))
    if new == current:
        return None
    setter = {
        "i": hat.set_intensity,
        "r": hat.set_ramp,
        "h": hat.set_hold,
    }[param.name]
    if not setter(new):
        return None
    return new


def main() -> int:
    print(f"opening UART …", file=sys.stderr)
    hat = LaserHat()

    print("opening display …", file=sys.stderr)
    display = make_display()
    ip = primary_ip()
    hostname = socket.gethostname()
    print(f"IP {ip}  hostname {hostname}", file=sys.stderr)

    selected = 0
    prev_buttons = 0
    last_rendered_key: Optional[tuple] = None
    last_render_at = 0.0
    last_ip_check = 0.0
    ip_check_gap = 30.0

    state = hat.get_state()
    if state is None:
        print("ERROR: no response from MCU; is it flashed and powered?",
              file=sys.stderr)
        return 1
    render(display, state, selected, ip, hostname)
    last_render_at = time.monotonic()
    last_rendered_key = (state.intensity, state.ramp_ticks, state.hold_ticks,
                         state.phase, selected, ip)

    while True:
        now = time.monotonic()
        state = hat.get_state()
        if state is None:
            time.sleep(POLL_INTERVAL)
            continue

        # press-edge detection
        pressed_now = state.button_mask
        edges = pressed_now & ~prev_buttons
        prev_buttons = pressed_now

        # B2: cycle parameter
        if edges & B2:
            selected = (selected + 1) % len(PARAMS)

        # B3 / B4: decrement / increment the selected parameter
        if edges & B3:
            param = PARAMS[selected]
            current = {"i": state.intensity,
                       "r": state.ramp_ticks,
                       "h": state.hold_ticks}[param.name]
            apply_change(hat, param, current, direction=-1)
        if edges & B4:
            param = PARAMS[selected]
            current = {"i": state.intensity,
                       "r": state.ramp_ticks,
                       "h": state.hold_ticks}[param.name]
            apply_change(hat, param, current, direction=+1)
        # B1 release is handled by the firmware itself (fires the pulse).

        # periodic IP refresh (DHCP changes)
        if now - last_ip_check >= ip_check_gap:
            last_ip_check = now
            ip = primary_ip()

        key = (state.intensity, state.ramp_ticks, state.hold_ticks,
               state.phase, selected, ip)
        if key != last_rendered_key and (now - last_render_at) >= REFRESH_MIN_GAP:
            render(display, state, selected, ip, hostname)
            last_render_at = time.monotonic()
            last_rendered_key = key

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(130)
