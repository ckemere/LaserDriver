#!/usr/bin/env python3
"""LaserHat eink one-shot: render IP + hostname, exit.

Uses the same slim SSD1680 driver as eink_gui.py.  Runs as a oneshot
service on boot and on a timer (see Pi/systemd/eink-ip.{service,timer})
so the displayed IP follows DHCP changes.
"""

from __future__ import annotations

import socket
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

from eink_panel import EinkPanel


FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def load_font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size=size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


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


def main() -> int:
    ip = primary_ip()
    hostname = socket.gethostname()
    print(f"primary IP: {ip}", file=sys.stderr)
    print(f"hostname:   {hostname}", file=sys.stderr)

    panel = EinkPanel(rotation=1)
    W, H = panel.size

    img = panel.new_canvas()
    draw = ImageDraw.Draw(img)

    font_big = load_font(22)
    font_med = load_font(16)

    draw.text((5, 0),   "LaserHAT",       fill=0, font=font_big)
    draw.text((5, 35),  f"IP: {ip}",      fill=0, font=font_big)
    draw.text((5, 75),  f"host: {hostname}", fill=0, font=font_med)
    draw.line((0, 115, W - 1, 115), fill=0, width=2)

    # Always force a full refresh on the one-shot so the displayed
    # image is clean (no ghosting from whatever was up before).
    panel.display(img, force_full=True)
    print("display refresh complete", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
