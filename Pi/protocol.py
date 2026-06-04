"""LaserHat binary wire protocol — host (Pi) side.

Frames are exchanged over /dev/ttyS0 in both directions.  This module is
the single Python source of truth for the format; the firmware mirror is
Firmware/laserHatFirmware/protocol.h.  The two MUST stay in sync — if you
change a message type or field layout here, change it there too.

Frame layout
------------
    payload   = TYPE(u8) || fields (little-endian, fixed width)
    body      = payload || CRC16_CCITT(payload)   (CRC as 2 bytes, LE)
    wire      = COBS(body) || 0x00                (0x00 is the delimiter)

COBS (Consistent Overhead Byte Stuffing) guarantees the encoded bytes
never contain 0x00, so the 0x00 delimiter unambiguously ends a frame and
a decoder can always resync on it.  A frame whose CRC fails (or that
fails to COBS-decode) is dropped; the next 0x00 starts a fresh frame.

Everything here is pure stdlib.
"""

from __future__ import annotations

import struct
from typing import Iterator, Tuple

# --- message types -------------------------------------------------------
# Host -> MCU (commands).  High bit clear.
CMD_SET_INTENSITY = 0x01   # u16
CMD_SET_RAMP      = 0x02   # u32
CMD_SET_HOLD      = 0x03   # u32
CMD_TRIGGER       = 0x04   # (no fields)
CMD_ARM           = 0x05   # (no fields)
CMD_QUERY         = 0x06   # (no fields)

# MCU -> Host (responses + events).  High bit set.
RSP_ACK           = 0x81   # u8 cmd_type, u8 status
RSP_STATUS        = 0x82   # u16 i, u32 r, u32 h, u8 btn, u8 armed, u8 phase, u32 tick
EVT_PULSE_START   = 0x83   # u32 tick
EVT_PULSE_END     = 0x84   # u32 tick
EVT_BUTTON        = 0x85   # u8 mask, u8 edges

# ACK status codes (RSP_ACK second byte).
ACK_OK      = 0x00
ACK_RANGE   = 0x01
ACK_BUSY    = 0x02
ACK_UNKNOWN = 0x03

# Phase byte values in RSP_STATUS (match the firmware's 'W'/'T').
PHASE_WAITING   = ord("W")
PHASE_TRIGGERED = ord("T")

# struct format for RSP_STATUS fields (after the TYPE byte), little-endian:
#   intensity u16, ramp u32, hold u32, btn u8, armed u8, phase u8, tick u32
_STATUS_STRUCT = struct.Struct("<HIIBBBI")
_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")

# Largest body we will ever assemble/accept (payload + 2 CRC).  RSP_STATUS
# is the biggest payload at 1 + 17 = 18 bytes; round up generously.
MAX_BODY = 64
MAX_WIRE = MAX_BODY + (MAX_BODY // 254) + 2 + 1   # COBS worst case + delimiter


# --- CRC16-CCITT (poly 0x1021, init 0xFFFF, no final xor) ----------------
def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


# --- COBS ----------------------------------------------------------------
def cobs_encode(data: bytes) -> bytes:
    """Encode data so the result contains no 0x00 byte."""
    out = bytearray()
    code_idx = len(out)
    out.append(0)            # placeholder for the first code byte
    code = 1
    for byte in data:
        if byte != 0:
            out.append(byte)
            code += 1
            if code == 0xFF:
                out[code_idx] = code
                code_idx = len(out)
                out.append(0)
                code = 1
        else:
            out[code_idx] = code
            code_idx = len(out)
            out.append(0)
            code = 1
    out[code_idx] = code
    return bytes(out)


def cobs_decode(data: bytes) -> bytes:
    """Inverse of cobs_encode.  Raises ValueError on a malformed block.

    A valid COBS block never contains 0x00, so its presence means the
    delimiter was lost or the block is corrupt.
    """
    if 0 in data:
        raise ValueError("0x00 inside COBS block")
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        code = data[i]
        if code == 0:
            raise ValueError("unexpected 0x00 in COBS block")
        i += 1
        end = i + code - 1
        if end > n:
            raise ValueError("COBS block overruns input")
        out.extend(data[i:end])
        i = end
        if code != 0xFF and i < n:
            out.append(0)
    return bytes(out)


# --- frame encode / decode ----------------------------------------------
def encode_frame(msg_type: int, payload: bytes = b"") -> bytes:
    """Build a complete wire frame (COBS body + 0x00 delimiter)."""
    body = bytes([msg_type]) + payload
    crc = crc16_ccitt(body)
    body += _U16.pack(crc)
    return cobs_encode(body) + b"\x00"


def decode_body(body: bytes) -> Tuple[int, bytes]:
    """Given a COBS-decoded body (payload+crc), verify CRC and split.

    Returns (msg_type, payload).  Raises ValueError on CRC mismatch or a
    runt frame.
    """
    if len(body) < 3:
        raise ValueError("frame too short")
    payload, crc_bytes = body[:-2], body[-2:]
    want = _U16.unpack(crc_bytes)[0]
    got = crc16_ccitt(payload)
    if want != got:
        raise ValueError(f"CRC mismatch: want {want:#06x} got {got:#06x}")
    return payload[0], payload[1:]


class StreamDecoder:
    """Feed raw RX bytes; iterate complete, CRC-checked frames.

    Frames are delimited by 0x00.  A block that fails to COBS-decode or
    fails CRC is silently dropped (resync happens at the next 0x00).
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> Iterator[Tuple[int, bytes]]:
        for byte in data:
            if byte == 0:
                block = bytes(self._buf)
                self._buf.clear()
                if not block:
                    continue
                try:
                    body = cobs_decode(block)
                    yield decode_body(body)
                except ValueError:
                    continue   # drop and resync
            else:
                if len(self._buf) < MAX_WIRE:
                    self._buf.append(byte)
                else:
                    # Runaway frame (lost a delimiter); reset to resync.
                    self._buf.clear()


# --- typed field (un)packers --------------------------------------------
def pack_set_intensity(value: int) -> bytes:
    return encode_frame(CMD_SET_INTENSITY, _U16.pack(value))


def pack_set_ramp(ticks: int) -> bytes:
    return encode_frame(CMD_SET_RAMP, _U32.pack(ticks))


def pack_set_hold(ticks: int) -> bytes:
    return encode_frame(CMD_SET_HOLD, _U32.pack(ticks))


def unpack_status(payload: bytes) -> dict:
    i, r, h, btn, armed, phase, tick = _STATUS_STRUCT.unpack(payload)
    return {
        "intensity": i,
        "ramp_ticks": r,
        "hold_ticks": h,
        "button_mask": btn,
        "gpio_armed": bool(armed),
        "phase": "W" if phase == PHASE_WAITING else "T",
        "tick": tick,
    }


def pack_status(intensity: int, ramp: int, hold: int, button_mask: int,
                armed: bool, phase: str, tick: int) -> bytes:
    phase_byte = PHASE_WAITING if phase == "W" else PHASE_TRIGGERED
    return encode_frame(
        RSP_STATUS,
        _STATUS_STRUCT.pack(intensity, ramp, hold, button_mask,
                            1 if armed else 0, phase_byte, tick),
    )
