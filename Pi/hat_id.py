#!/usr/bin/env python3
"""Which HAT is this Pi plugged into?  Board identity, Pi GPIO pins, and the
Raspberry Pi HAT ID EEPROM format.

Three boards share one MCU protocol (protocol.py) but not one Pi pin-out:

    board  product          pid     pver    SWCLK SWDIO NRST POWER_EN TRIGGER
    rev2   LaserHAT Rev 2   0x0002  0x0002   24    25    23     18      26
    stim   StimHAT          0x0003  0x0001   24    25     9     10      18
    laser  LaserDriverHAT   0x0004  0x0001   24    25     9     10      18

Every board carries an M24C32 HAT ID EEPROM (U1, address 0x50 on the
ID_SD/ID_SC pins = GPIO 0/1, write-protect jumper JP1).  The Pi firmware
reads it once at boot and publishes it under /proc/device-tree/hat/
(vendor, product, product_id, product_ver, uuid); that is the source of
truth for the board type, available before the MCU is powered, so the
flash/power tools drive the right GPIOs.  The MCU firmware's own board byte
(RSP_VERSION.board) is only a cross-check, done by the brokers.

Resolution (resolve()):

  board   1. the HAT EEPROM, when it names one of our products;
          2. otherwise an explicit --board argument;
          3. otherwise $LASERHAT_BOARD (e.g. from /etc/default/laserhat);
          4. otherwise Rev 2 (the board the software assumed before).
          An explicit --board that contradicts the EEPROM is flagged as a
          conflict: the tools refuse unless --force (then --board wins).
  pins    the board's table above, then each $LASERHAT_*_PIN variable that
          is set overrides that one pin (LASERHAT_NRST_PIN,
          LASERHAT_POWER_PIN, LASERHAT_TRIGGER_PIN, LASERHAT_SWCLK_PIN,
          LASERHAT_SWDIO_PIN; Firmware/Makefile.gcc's HAT_REV=1 uses them).

$LASERHAT_HAT_DIR replaces /proc/device-tree/hat (tests).

CLI (used by laserhat-flash; `laserhat-eeprom read` is the friendly view):

    python3 hat_id.py show  [--board B]     human-readable resolution
    python3 hat_id.py shell [--board B]     LH_*=... lines for `eval`

Pure stdlib.
"""

from __future__ import annotations

import os
import struct
import uuid as uuidlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# --------------------------------------------------------------------- boards
VENDOR = "KemereLab"

BOARD_REV2, BOARD_STIM, BOARD_LASER, BOARD_UNKNOWN = "rev2", "stim", "laser", "unknown"
FALLBACK_BOARD = BOARD_REV2


@dataclass(frozen=True)
class Board:
    name: str               # 'rev2' / 'stim' / 'laser' (== protocol.BOARD_TYPE_NAMES)
    product: str            # HAT EEPROM product string
    pid: int                # HAT EEPROM product id
    pver: int               # HAT EEPROM product version
    fw_type: int            # protocol.BOARD_TYPE_* the matching firmware reports
    tag: str                # OLED header tag (<= 8 chars, '[L]' / '[E]' appended)
    modes: tuple            # MCU modes the board's firmware accepts
    pins: Dict[str, int]    # BCM numbers: swclk swdio nrst power trigger


BOARDS: Dict[str, Board] = {
    BOARD_REV2: Board("rev2", "LaserHAT Rev 2", 0x0002, 0x0002, 1, "LASERHAT",
                      ("laser", "estim"),
                      {"swclk": 24, "swdio": 25, "nrst": 23, "power": 18, "trigger": 26}),
    BOARD_STIM: Board("stim", "StimHAT", 0x0003, 0x0001, 2, "STIMHAT",
                      ("estim",),
                      {"swclk": 24, "swdio": 25, "nrst": 9, "power": 10, "trigger": 18}),
    BOARD_LASER: Board("laser", "LaserDriverHAT", 0x0004, 0x0001, 3, "LASERDRV",
                       ("laser",),
                       {"swclk": 24, "swdio": 25, "nrst": 9, "power": 10, "trigger": 18}),
}
BOARDS_BY_PID = {b.pid: b for b in BOARDS.values()}

PIN_NAMES = ("swclk", "swdio", "nrst", "power", "trigger")
PIN_ENV = {"swclk": "LASERHAT_SWCLK_PIN", "swdio": "LASERHAT_SWDIO_PIN",
           "nrst": "LASERHAT_NRST_PIN", "power": "LASERHAT_POWER_PIN",
           "trigger": "LASERHAT_TRIGGER_PIN"}
BOARD_ENV = "LASERHAT_BOARD"

DEFAULT_HAT_DIR = "/proc/device-tree/hat"


def hat_dir() -> str:
    return os.environ.get("LASERHAT_HAT_DIR", DEFAULT_HAT_DIR)


def label(board: str) -> str:
    b = BOARDS.get(board)
    return b.product if b else "unknown HAT"


# ----------------------------------------------------------- /proc/device-tree
@dataclass
class HatInfo:
    """What the Pi firmware published from the HAT EEPROM at boot."""
    vendor: str = ""
    product: str = ""
    product_id: Optional[int] = None
    product_ver: Optional[int] = None
    uuid: str = ""

    @property
    def board(self) -> str:
        """Our board name, or 'unknown' (blank vendor, another vendor's HAT,
        or one of our product ids this software does not know)."""
        if self.vendor != VENDOR:
            return BOARD_UNKNOWN
        b = BOARDS_BY_PID.get(self.product_id) if self.product_id is not None else None
        if b is None:                     # tolerate a bad pid, trust the name
            b = next((x for x in BOARDS.values() if x.product == self.product), None)
        return b.name if b else BOARD_UNKNOWN


def _read_prop(directory: str, name: str) -> Optional[str]:
    try:
        with open(os.path.join(directory, name), "rb") as f:
            raw = f.read()
    except OSError:
        return None
    return raw.split(b"\0", 1)[0].decode("utf-8", "replace").strip()


def _int_or_none(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    try:
        return int(s, 0)
    except ValueError:
        try:
            return int(s, 16)
        except ValueError:
            return None


def read_hat(directory: Optional[str] = None) -> Optional[HatInfo]:
    """The HAT node the firmware made at boot, or None when there is none
    (no EEPROM, a blank one, JP-less board, or the Pi was booted without
    the HAT)."""
    d = directory or hat_dir()
    if not os.path.isdir(d):
        return None
    vendor = _read_prop(d, "vendor")
    product = _read_prop(d, "product")
    if vendor is None and product is None:
        return None
    return HatInfo(vendor=vendor or "", product=product or "",
                   product_id=_int_or_none(_read_prop(d, "product_id")),
                   product_ver=_int_or_none(_read_prop(d, "product_ver")),
                   uuid=_read_prop(d, "uuid") or "")


# ----------------------------------------------------------------- resolution
@dataclass
class Resolution:
    board: str                      # effective board ('rev2' / 'stim' / 'laser')
    source: str                     # 'eeprom' | 'argument' | 'env' | 'default'
    hat: Optional[HatInfo]          # the EEPROM's view (None = no HAT node)
    eeprom_board: Optional[str]     # hat.board, None without a HAT node
    pins: Dict[str, int]
    pin_overrides: Dict[str, str] = field(default_factory=dict)  # pin -> env var
    conflict: bool = False          # --board contradicts the EEPROM
    notes: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return label(self.board)

    @property
    def foreign_hat(self) -> bool:
        """A HAT EEPROM is present but does not name one of our boards."""
        return self.hat is not None and self.eeprom_board == BOARD_UNKNOWN

    def describe(self) -> str:
        src = {"eeprom": "from the HAT EEPROM", "argument": "from --board",
               "env": f"from ${BOARD_ENV}",
               "default": "fallback: no HAT EEPROM identity"}[self.source]
        pins = " ".join(
            f"{n.upper()}={self.pins[n]}" + ("*" if n in self.pin_overrides else "")
            for n in PIN_NAMES)
        s = f"board {self.board} ({self.label}, {src}); GPIO {pins}"
        if self.pin_overrides:
            s += " (* = " + ", ".join(sorted(set(self.pin_overrides.values()))) + ")"
        return s


def resolve(board_arg: Optional[str] = None, env: Optional[dict] = None,
            directory: Optional[str] = None, force: bool = False) -> Resolution:
    """Work out the board and its pins (precedence in the module docstring).
    force: let board_arg win over a contradicting EEPROM (else the result
    keeps the EEPROM's board and sets .conflict)."""
    env = os.environ if env is None else env
    if board_arg is not None and board_arg not in BOARDS:
        raise ValueError(f"unknown board {board_arg!r} (choose {', '.join(BOARDS)})")
    hat = read_hat(directory)
    eeprom_board = hat.board if hat is not None else None
    notes: List[str] = []
    conflict = False

    if eeprom_board in BOARDS:
        board, source = eeprom_board, "eeprom"
        if board_arg is not None and board_arg != eeprom_board:
            conflict = True
            notes.append(f"--board {board_arg} contradicts the HAT EEPROM ({eeprom_board})")
            if force:
                board, source = board_arg, "argument"
    else:
        if hat is not None:
            notes.append(f"HAT EEPROM present but not one of ours: vendor "
                         f"{hat.vendor!r} product {hat.product!r} "
                         f"id {hat.product_id!r}")
        env_board = (env.get(BOARD_ENV) or "").strip().lower()
        if board_arg is not None:
            board, source = board_arg, "argument"
        elif env_board in BOARDS:
            board, source = env_board, "env"
        else:
            if env_board:
                notes.append(f"ignoring ${BOARD_ENV}={env_board!r} (unknown board)")
            board, source = FALLBACK_BOARD, "default"

    pins = dict(BOARDS[board].pins)
    overrides: Dict[str, str] = {}
    for name, var in PIN_ENV.items():
        raw = env.get(var)
        if raw is None or raw.strip() == "":
            continue
        try:
            value = int(raw, 0)
        except ValueError:
            notes.append(f"ignoring ${var}={raw!r} (not a number)")
            continue
        if not 0 <= value <= 27:
            notes.append(f"ignoring ${var}={raw!r} (not a header GPIO 0..27)")
            continue
        if value != pins[name]:
            overrides[name] = var
        pins[name] = value
    return Resolution(board, source, hat, eeprom_board, pins, overrides,
                      conflict, notes)


# ------------------------------------------------------------- gpiochip lookup
_GPIO_GET_CHIPINFO_IOCTL = 0x8044B401      # _IOR(0xB4, 0x01, struct gpiochip_info)
_HEADER_CHIP_LABELS = ("pinctrl-bcm2711", "pinctrl-bcm2835", "pinctrl-rp1",
                       "pinctrl-bcm2712")


def gpiochip(env: Optional[dict] = None) -> int:
    """The /dev/gpiochipN that carries the 40-pin header (OpenOCD's linuxgpiod
    -chip): 0 on a Pi 4, 0 or 4 on a Pi 5 depending on the kernel.
    $OPENOCD_GPIOCHIP overrides; falls back to 0."""
    env = os.environ if env is None else env
    if env.get("OPENOCD_GPIOCHIP", "").strip():
        return int(env["OPENOCD_GPIOCHIP"], 0)
    try:
        import fcntl
    except ImportError:                    # not Linux
        return 0
    for n in range(16):
        path = f"/dev/gpiochip{n}"
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError:
            continue
        try:
            buf = fcntl.ioctl(fd, _GPIO_GET_CHIPINFO_IOCTL, bytes(68))
        except OSError:
            continue
        finally:
            os.close(fd)
        lbl = buf[32:64].split(b"\0", 1)[0].decode("ascii", "replace")
        if lbl in _HEADER_CHIP_LABELS:
            return n
    return 0


# ======================================================= HAT EEPROM format
# Raspberry Pi "HAT ID EEPROM" format (raspberrypi/hats, eeprom-format.md),
# little-endian throughout:
#
#   header  12 B   "R-Pi" (52 2D 50 69) | version 0x01 | reserved 0x00 |
#                  numatoms u16 | eeplen u32 (header + all atoms, bytes)
#   atom    8 B    type u16 | count u16 (0, 1, 2 ... in order) |
#                  dlen u32 (= len(data) + 2)
#           data   dlen - 2 bytes
#           crc    u16 CRC-16 (poly 0x8005 reflected = 0xA001, init 0, no
#                  xorout: CRC-16/ARC) over type..data, i.e. the whole atom
#                  except the CRC itself (eepmake's getcrc).
#
#   atom 0x0001 vendor info: uuid 16 B (the UUID's 128-bit value,
#                  little-endian: eepmake's serial_1..serial_4), pid u16,
#                  pver u16, vslen u8, pslen u8, vendor string, product
#                  string (ASCII, no terminator).
#   atom 0x0002 GPIO map: bank_drive u8, power u8, then one byte per GPIO
#                  0..27 (bit 7 is_used, bits 6:5 pull, bits 2:0 function).
#
# Our GPIO map is the minimal valid one: bank_drive 0 (leave the default
# drive / slew / hysteresis), power 0 (the HAT does not back-power the Pi --
# the StimHAT's USB-C path can, but only with SW10 on and no Pi fitted is
# that the supported use), and every pin byte 0 = "not used", so the
# firmware leaves each GPIO at its boot default (input, default pull).
# That is deliberate: the boards were designed around the boot-default
# pulls (e.g. the StimHAT's R3 is sized against GPIO 9's boot pull-down),
# and the Pi software claims the lines it drives at run time.  No device-tree
# atom: nothing on the HAT needs a kernel driver.
EEPROM_SIGNATURE = b"R-Pi"
EEPROM_VERSION = 1
ATOM_VENDOR_INFO = 0x0001
ATOM_GPIO_MAP = 0x0002
ATOM_LINUX_DT = 0x0003
ATOM_CUSTOM = 0x0004
EEPROM_SIZE = 4096                    # M24C32
EEPROM_PAGE = 32                      # M24C32 page-write size

_HEADER = struct.Struct("<4sBBHI")
_ATOM_HDR = struct.Struct("<HHI")
_VENDOR_FIXED = struct.Struct("<16sHHBB")


def crc16(data: bytes) -> int:
    """CRC-16/ARC as the HAT EEPROM spec (eepmake getcrc) defines it."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def uuid_bytes(u: uuidlib.UUID) -> bytes:
    return u.int.to_bytes(16, "little")


def encode_atom(atype: int, count: int, data: bytes) -> bytes:
    body = _ATOM_HDR.pack(atype, count, len(data) + 2) + data
    return body + struct.pack("<H", crc16(body))


def vendor_info_data(u: uuidlib.UUID, pid: int, pver: int,
                     vendor: str, product: str) -> bytes:
    v, p = vendor.encode("ascii"), product.encode("ascii")
    if len(v) > 255 or len(p) > 255:
        raise ValueError("vendor / product strings are limited to 255 bytes")
    return _VENDOR_FIXED.pack(uuid_bytes(u), pid, pver, len(v), len(p)) + v + p


def gpio_map_data(bank_drive: int = 0, power: int = 0,
                  pins: Optional[Dict[int, int]] = None) -> bytes:
    pin_bytes = bytearray(28)
    for gpio, value in (pins or {}).items():
        pin_bytes[gpio] = value
    return bytes([bank_drive, power]) + bytes(pin_bytes)


def build_eeprom(board: str, u: Optional[uuidlib.UUID] = None) -> bytes:
    """The complete EEPROM image for one of our boards (a fresh random UUID
    unless one is given)."""
    b = BOARDS[board]
    u = u or uuidlib.uuid4()
    atoms = [encode_atom(ATOM_VENDOR_INFO, 0,
                         vendor_info_data(u, b.pid, b.pver, VENDOR, b.product)),
             encode_atom(ATOM_GPIO_MAP, 1, gpio_map_data())]
    eeplen = _HEADER.size + sum(len(a) for a in atoms)
    image = _HEADER.pack(EEPROM_SIGNATURE, EEPROM_VERSION, 0, len(atoms), eeplen) \
        + b"".join(atoms)
    assert len(image) == eeplen <= EEPROM_SIZE
    return image


@dataclass
class EepromImage:
    version: int
    numatoms: int
    eeplen: int
    atoms: List[dict]
    vendor: Optional[str] = None
    product: Optional[str] = None
    product_id: Optional[int] = None
    product_ver: Optional[int] = None
    uuid: Optional[str] = None
    gpio_map: Optional[bytes] = None

    def hat_info(self) -> HatInfo:
        return HatInfo(self.vendor or "", self.product or "", self.product_id,
                       self.product_ver, self.uuid or "")


def parse_eeprom(blob: bytes) -> EepromImage:
    """Decode (and check: signature, lengths, every atom's CRC) an EEPROM
    image; trailing bytes past eeplen (0xFF on an erased part) are ignored.
    Raises ValueError on anything malformed."""
    if len(blob) < _HEADER.size:
        raise ValueError("shorter than the 12-byte header")
    sig, version, _res, numatoms, eeplen = _HEADER.unpack_from(blob)
    if sig != EEPROM_SIGNATURE:
        raise ValueError(f"bad signature {sig!r} (blank EEPROM?)")
    if version != EEPROM_VERSION:
        raise ValueError(f"unsupported format version {version}")
    if not _HEADER.size <= eeplen <= len(blob):
        raise ValueError(f"eeplen {eeplen} outside the {len(blob)}-byte image")
    img = EepromImage(version, numatoms, eeplen, [])
    off = _HEADER.size
    for i in range(numatoms):
        if off + _ATOM_HDR.size > eeplen:
            raise ValueError(f"atom {i} header runs past eeplen")
        atype, count, dlen = _ATOM_HDR.unpack_from(blob, off)
        end = off + _ATOM_HDR.size + dlen
        if dlen < 2 or end > eeplen:
            raise ValueError(f"atom {i} (type {atype:#06x}) dlen {dlen} runs past eeplen")
        body = blob[off:end - 2]
        (crc,) = struct.unpack_from("<H", blob, end - 2)
        if crc != crc16(body):
            raise ValueError(f"atom {i} (type {atype:#06x}) CRC {crc:#06x} != "
                             f"{crc16(body):#06x}")
        # count should be i (eepmake numbers atoms 0, 1, 2 ...); not
        # enforced, a foreign tool's numbering is its own business.
        data = body[_ATOM_HDR.size:]
        img.atoms.append({"type": atype, "count": count, "dlen": dlen,
                          "data": data, "crc": crc})
        if atype == ATOM_VENDOR_INFO:
            if len(data) < _VENDOR_FIXED.size:
                raise ValueError("vendor atom too short")
            ub, pid, pver, vslen, pslen = _VENDOR_FIXED.unpack_from(data)
            if _VENDOR_FIXED.size + vslen + pslen != len(data):
                raise ValueError("vendor atom string lengths do not add up")
            s = _VENDOR_FIXED.size
            img.vendor = data[s:s + vslen].decode("ascii", "replace")
            img.product = data[s + vslen:s + vslen + pslen].decode("ascii", "replace")
            img.product_id, img.product_ver = pid, pver
            img.uuid = str(uuidlib.UUID(int=int.from_bytes(ub, "little")))
        elif atype == ATOM_GPIO_MAP:
            if len(data) != 30:
                raise ValueError(f"GPIO map atom is {len(data)} bytes, not 30")
            img.gpio_map = data
        off = end
    if off != eeplen:
        raise ValueError(f"atoms end at {off}, eeplen says {eeplen}")
    return img


# ------------------------------------------------------------------------ CLI
def _shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def _main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="LaserHAT board identity / pins")
    p.add_argument("what", choices=["show", "shell"])
    p.add_argument("--board", choices=list(BOARDS))
    p.add_argument("--force", action="store_true",
                   help="let --board win over a contradicting HAT EEPROM")
    a = p.parse_args(argv)
    r = resolve(a.board, force=a.force)
    if a.what == "show":
        print(r.describe())
        for n in r.notes:
            print("note:", n)
        return 0
    hat = r.hat or HatInfo()
    out = {"LH_BOARD": r.board, "LH_BOARD_LABEL": r.label,
           "LH_BOARD_SOURCE": r.source,
           "LH_EEPROM_BOARD": r.eeprom_board or "",
           "LH_EEPROM_VENDOR": hat.vendor, "LH_EEPROM_PRODUCT": hat.product,
           "LH_CONFLICT": "1" if r.conflict else "0",
           "LH_FOREIGN_HAT": "1" if r.foreign_hat else "0",
           "LH_DESCRIBE": r.describe(),
           "LH_NOTES": "; ".join(r.notes),
           "LH_GPIOCHIP": str(gpiochip())}
    for n in PIN_NAMES:
        out[f"LH_{n.upper()}"] = str(r.pins[n])
    for k, v in out.items():
        print(f"{k}={_shell_quote(v)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
