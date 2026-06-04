"""SSD1680 / GDEY0213B74 eink panel driver.

Slim self-contained driver that supports both full-refresh (~3 s,
clears ghosting) and fast partial refresh (~300 ms, used for
interactive UI updates).  Replaces the adafruit_epd + adafruit_blinka
stack — we want control over the speed knobs.

Drawing is done in PIL: caller produces a 1-bit (mode '1') PIL Image
and hands it to `display()`.  The driver handles rotation, packing
into the panel's RAM layout, and the SPI command sequence.

Pin map matches the LaserHAT schematic (defaults):
    GPIO 8  -> CS    (handled by spidev on /dev/spidev0.0)
    GPIO 10 -> MOSI
    GPIO 11 -> SCK
    GPIO 22 -> DC
    GPIO 27 -> RST
    GPIO 17 -> BUSY

Reference: SSD1680 datasheet, GDEY0213B74 controller init from the
GoodDisplay reference code.
"""

from __future__ import annotations

import time
from typing import Optional

import spidev
from gpiozero import DigitalInputDevice, DigitalOutputDevice
from PIL import Image


# Native panel orientation: 122 wide × 250 tall.  The framebuffer
# addressing rounds the X dimension up to the next byte (128 / 8 = 16),
# so one row is 16 bytes regardless of the visible 122.
PANEL_W = 122
PANEL_H = 250
RAM_W   = 128            # X-axis byte alignment
BUF_BYTES_PER_ROW = RAM_W // 8     # 16
BUF_BYTES_TOTAL   = BUF_BYTES_PER_ROW * PANEL_H   # 4000

# Default partial-refresh cadence — full refresh every Nth display()
# call clears accumulated ghosting.
DEFAULT_FULL_REFRESH_EVERY = 30


class EinkPanel:
    """SSD1680Z / GDEY0213B74 panel.

    Use as either landscape (250×122) or portrait (122×250) by
    selecting `rotation` at construction time.  The PIL Image you pass
    to display() should match the chosen orientation's logical size.
    """

    def __init__(
        self,
        dc_pin: int = 22,
        rst_pin: int = 27,
        busy_pin: int = 17,
        spi_bus: int = 0,
        spi_device: int = 0,
        spi_hz: int = 4_000_000,
        rotation: int = 1,    # 0 = native portrait, 1 = landscape
        full_refresh_every: int = DEFAULT_FULL_REFRESH_EVERY,
    ):
        if rotation not in (0, 1, 2, 3):
            raise ValueError("rotation must be 0..3")

        self._spi = spidev.SpiDev()
        self._spi.open(spi_bus, spi_device)
        self._spi.max_speed_hz = spi_hz
        self._spi.mode = 0

        self._dc   = DigitalOutputDevice(dc_pin)
        self._rst  = DigitalOutputDevice(rst_pin)
        self._busy = DigitalInputDevice(busy_pin)

        self._rotation = rotation
        self._full_refresh_every = full_refresh_every
        self._partials_since_full = full_refresh_every  # force full on first paint

        self._initialised = False
        self.reset_and_init()

    # ------------------------------------------------------------------
    # low-level command / data
    # ------------------------------------------------------------------
    def _cmd(self, cmd: int, data: Optional[bytes] = None) -> None:
        self._dc.off()
        self._spi.writebytes([cmd])
        if data is not None:
            self._dc.on()
            self._write_bulk(data)

    def _write_bulk(self, data) -> None:
        # spidev.writebytes2 handles arbitrary lengths; writebytes caps
        # around 4 KB on some kernels.  writebytes2 chunks internally.
        self._spi.writebytes2(bytes(data))

    def _wait_busy(self, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        while self._busy.value:    # busy = HIGH on SSD1680
            if time.monotonic() > deadline:
                raise TimeoutError("SSD1680 BUSY did not release")
            time.sleep(0.005)

    # ------------------------------------------------------------------
    # init / waveform setup
    # ------------------------------------------------------------------
    def reset_and_init(self) -> None:
        """Hardware-reset the panel and run the full-refresh init sequence.

        Idempotent — safe to call again at any time, e.g. before
        forcing a full refresh after long partial-update sessions.
        """
        self._rst.off()
        time.sleep(0.01)
        self._rst.on()
        time.sleep(0.01)
        self._wait_busy()

        self._cmd(0x12)            # SW reset
        self._wait_busy()

        # Driver output control: MUX = PANEL_H - 1, GD/SM/TB = 0
        last_y = PANEL_H - 1
        self._cmd(0x01, bytes([last_y & 0xFF, (last_y >> 8) & 0xFF, 0x00]))

        # Data entry mode: X increment, Y increment, address counter
        # updated in X direction.
        self._cmd(0x11, bytes([0x03]))

        # RAM X/Y window — full panel.
        self._cmd(0x44, bytes([0x00, (RAM_W // 8) - 1]))
        self._cmd(0x45, bytes([0x00, 0x00, last_y & 0xFF, (last_y >> 8) & 0xFF]))

        # Border waveform.
        self._cmd(0x3C, bytes([0x05]))

        # Display update control: bypass red RAM (B/W only).
        self._cmd(0x21, bytes([0x00, 0x80]))

        # Temperature sensor control: internal sensor.
        self._cmd(0x18, bytes([0x80]))

        # RAM cursor at origin.
        self._cmd(0x4E, bytes([0x00]))
        self._cmd(0x4F, bytes([0x00, 0x00]))
        self._wait_busy()

        self._initialised = True
        self._partials_since_full = self._full_refresh_every

    # ------------------------------------------------------------------
    # buffer packing
    # ------------------------------------------------------------------
    @property
    def size(self) -> tuple[int, int]:
        """Logical (width, height) for the chosen rotation."""
        if self._rotation in (1, 3):
            return (PANEL_H, PANEL_W)   # landscape: 250 × 122
        return (PANEL_W, PANEL_H)       # portrait:  122 × 250

    def new_canvas(self) -> Image.Image:
        return Image.new("1", self.size, color=1)   # 1 = white

    def _image_to_buffer(self, image: Image.Image) -> bytearray:
        """Convert a logical-size PIL Image to a panel-native RAM buffer."""
        if image.mode != "1":
            image = image.convert("1")
        # Rotate to native portrait (122×250).
        if self._rotation == 1:        # landscape, top-of-panel on the left
            image = image.rotate(-90, expand=True)
        elif self._rotation == 2:      # 180° portrait
            image = image.rotate(180, expand=True)
        elif self._rotation == 3:      # landscape, top-of-panel on the right
            image = image.rotate(90, expand=True)

        # Pad to RAM_W (128) on the right side.
        if image.size != (PANEL_W, PANEL_H):
            raise ValueError(
                f"image size {image.size} != panel logical size after rotate")

        padded = Image.new("1", (RAM_W, PANEL_H), color=1)
        padded.paste(image, (0, 0))

        # PIL "1" mode packs MSB-first per byte already; tobytes() gives
        # exactly what the SSD1680 expects.  Invert because SSD1680 wants
        # 1 = white, 0 = black, matching PIL "1" mode.
        return bytearray(padded.tobytes())

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------
    def display(self, image: Image.Image, *, force_full: bool = False) -> None:
        """Push `image` to the panel.

        By default uses partial refresh for speed, and forces a full
        refresh every `full_refresh_every` calls to clear ghosting.
        Pass `force_full=True` to do a full refresh now.
        """
        buf = self._image_to_buffer(image)

        do_full = force_full or self._partials_since_full >= self._full_refresh_every
        if do_full:
            self._send_full(buf)
            self._partials_since_full = 0
        else:
            self._send_partial(buf)
            self._partials_since_full += 1

    def _send_full(self, buf: bytes) -> None:
        # Reset cursor; write BW RAM.
        self._cmd(0x4E, bytes([0x00]))
        self._cmd(0x4F, bytes([0x00, 0x00]))
        self._cmd(0x24, buf)             # WRITE_RAM
        # Also write the same data to the red plane as white (0xFF)
        # so the controller doesn't try to paint stale red pixels.
        self._cmd(0x26, bytes([0xFF]) * len(buf))
        # Update sequence + activate.
        self._cmd(0x22, bytes([0xF7]))
        self._cmd(0x20)
        self._wait_busy()

    def _send_partial(self, buf: bytes) -> None:
        # Cursor reset, write new BW frame.
        self._cmd(0x4E, bytes([0x00]))
        self._cmd(0x4F, bytes([0x00, 0x00]))
        self._cmd(0x24, buf)
        # Trigger fast partial refresh: 0xFF = partial waveform, then 0x20 activate.
        self._cmd(0x22, bytes([0xFF]))
        self._cmd(0x20)
        self._wait_busy()

    # ------------------------------------------------------------------
    # power / cleanup
    # ------------------------------------------------------------------
    def sleep(self) -> None:
        """Put the panel into deep sleep.  Call reset_and_init() to wake."""
        self._cmd(0x10, bytes([0x01]))
        time.sleep(0.1)

    def close(self) -> None:
        try:
            self.sleep()
        finally:
            self._spi.close()
            self._dc.close()
            self._rst.close()
            self._busy.close()

    def __enter__(self) -> "EinkPanel":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
