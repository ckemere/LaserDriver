#!/usr/bin/env python3
"""LaserHAT eink MVP: render the Pi's primary IP address on the SSD1680Z.

Adapted from the user's adafruit_epd validation script.  One-shot:
detects IP, paints, exits.  systemd unit / timer wraps it for boot +
periodic refresh — see Pi/systemd/.

Pin map matches the LaserHAT schematic:
    CE0  -> EINK_CS         (board.CE0)
    D22  -> EINK_DC         (board.D22)
    D27  -> EINK_RESET      (board.D27)
    D17  -> EINK_BUSY       (board.D17)
    SPI0 -> EINK_SCK / COPI / CIPO
"""

import socket
import subprocess
import sys

import board
import busio
import digitalio
from adafruit_epd.epd import Adafruit_EPD
from adafruit_epd.ssd1680 import Adafruit_SSD1680Z


def primary_ip() -> str:
    """Return the Pi's primary IPv4 address as a string, or '?.?.?.?'.

    `hostname -I` lists all assigned IPs separated by spaces; the
    first one is the primary interface.  Falls back to a UDP-socket
    trick if `hostname` is unavailable.
    """
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True).split()
        if out:
            return out[0]
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Fallback: open a UDP socket "to" a public address; the OS picks
    # the route and we read back the local endpoint.  Doesn't actually
    # send anything.
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
        122,
        250,
        spi,
        cs_pin=digitalio.DigitalInOut(board.CE0),
        dc_pin=digitalio.DigitalInOut(board.D22),
        sramcs_pin=None,
        rst_pin=digitalio.DigitalInOut(board.D27),
        busy_pin=digitalio.DigitalInOut(board.D17),
    )
    display.rotation = 1  # landscape: 250 wide x 122 tall
    return display


def render(display: Adafruit_SSD1680Z, ip: str, hostname: str) -> None:
    display.fill(Adafruit_EPD.WHITE)

    # Header
    display.text("LaserHAT", 5, 5, Adafruit_EPD.BLACK, size=2)

    # IP address — the headline information
    display.text(f"IP: {ip}", 5, 45, Adafruit_EPD.BLACK, size=2)

    # Hostname underneath, smaller
    display.text(f"host: {hostname}", 5, 80, Adafruit_EPD.BLACK)

    # A thin red rule across the bottom for visual confirmation we're
    # actually rendering (not a stale frame stuck on the panel).
    display.fill_rect(0, 110, 250, 2, Adafruit_EPD.RED)

    display.display()


def main() -> int:
    ip = primary_ip()
    hostname = socket.gethostname()
    print(f"primary IP: {ip}", file=sys.stderr)
    print(f"hostname:   {hostname}", file=sys.stderr)

    display = make_display()
    render(display, ip, hostname)
    print("display refresh complete", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
