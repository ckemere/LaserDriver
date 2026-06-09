"""Adafruit 2.23" 128x32 OLED Bonnet (SSD1305, I2C) panel driver.

Thin wrapper over Adafruit's framebuf SSD1305 driver that exposes the
same tiny interface the GUI expects from the old EinkPanel:
`size`, `new_canvas()`, and `display(img)`.  Drop-in replacement for
`eink_panel.EinkPanel` so `oled_gui.py` can stay close to the old
`eink_gui.py`.

Differences from eink:
- No partial vs full refresh distinction (OLED repaints the whole frame
  every time, in a millisecond or two), so `display(force_full=...)` is
  accepted and ignored.
- Pixels are lit, not inked: the canvas is dark (0) and the foreground
  is on (1).  `new_canvas()` returns a black image accordingly.

Hardware: Adafruit product 4567.  SSD1305 over I2C at 0x3C, with the
panel reset tied to GPIO 4 (BCM).  The bonnet has no onboard buttons;
LaserHAT's buttons come from the MCU over the broker, so nothing else
in the stack changes.

The SSD1305 has 132 column drivers for a 128-wide panel; Adafruit's
driver handles the column offset internally, which is the main reason
to lean on it here rather than hand-roll the init like eink_panel did.
"""

from __future__ import annotations

import board
import busio
import digitalio
from PIL import Image

import adafruit_ssd1305


PANEL_W = 128
PANEL_H = 32
I2C_ADDR = 0x3C
RESET_PIN = board.D4   # GPIO 4 (BCM), per the bonnet's wiring


class OledPanel:
    """128x32 SSD1305 OLED bonnet, presented with the EinkPanel interface."""

    def __init__(
        self,
        *,
        width: int = PANEL_W,
        height: int = PANEL_H,
        addr: int = I2C_ADDR,
        rotation: int = 0,     # 0 = native, 2 = mounted upside-down
    ):
        if rotation not in (0, 2):
            raise ValueError("rotation must be 0 or 2 for the 128x32 bonnet")
        self._w = width
        self._h = height
        self._rotation = rotation

        i2c = busio.I2C(board.SCL, board.SDA)
        reset = digitalio.DigitalInOut(RESET_PIN)
        self._oled = adafruit_ssd1305.SSD1305_I2C(
            width, height, i2c, addr=addr, reset=reset
        )
        self._oled.fill(0)
        self._oled.show()

    @property
    def size(self) -> tuple[int, int]:
        """Logical (width, height) the GUI draws into."""
        return (self._w, self._h)

    def new_canvas(self) -> Image.Image:
        return Image.new("1", self.size, 0)    # 0 = pixel off (dark)

    def display(self, image: Image.Image, *, force_full: bool = False) -> None:
        """Push `image` (a logical-size 1-bit PIL Image) to the panel.

        `force_full` exists only for interface parity with EinkPanel and
        is ignored — the OLED always repaints the full frame.
        """
        if image.mode != "1":
            image = image.convert("1")
        if self._rotation == 2:
            image = image.rotate(180)
        self._oled.image(image)
        self._oled.show()

    def close(self) -> None:
        try:
            self._oled.fill(0)
            self._oled.show()
        except Exception:
            pass

    def __enter__(self) -> "OledPanel":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
