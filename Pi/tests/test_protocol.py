"""Unit tests for the binary wire codec (Pi/protocol.py).

Run:  python3 -m pytest Pi/tests/test_protocol.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import protocol as p


# --- COBS ---------------------------------------------------------------
@pytest.mark.parametrize("raw", [
    b"",
    b"\x00",
    b"\x00\x00",
    b"\x01\x02\x03",
    b"\x11\x22\x00\x33",
    bytes(range(256)),
    b"\xff" * 300,            # forces multiple 0xFF code-block splits
    b"\x00" * 50,
    bytes([0]) + bytes(range(1, 255)) + bytes([0]),
])
def test_cobs_roundtrip(raw):
    enc = p.cobs_encode(raw)
    assert 0 not in enc                      # invariant: no 0x00 in output
    assert p.cobs_decode(enc) == raw


def test_cobs_decode_rejects_embedded_zero():
    with pytest.raises(ValueError):
        p.cobs_decode(b"\x03\x01\x00")


# --- CRC ----------------------------------------------------------------
def test_crc16_known_vector():
    # CRC16-CCITT (0xFFFF init) of "123456789" is 0x29B1.
    assert p.crc16_ccitt(b"123456789") == 0x29B1


# --- frame round-trip ---------------------------------------------------
@pytest.mark.parametrize("msg_type,payload", [
    (p.CMD_TRIGGER, b""),
    (p.CMD_QUERY, b""),
    (p.CMD_SET_INTENSITY, p._U16.pack(320)),
    (p.CMD_SET_RAMP, p._U32.pack(8000)),
    (p.EVT_PULSE_START, p._U32.pack(0xDEADBEEF)),
    (p.EVT_BUTTON, bytes([0b0101, 0b0100])),
])
def test_frame_roundtrip(msg_type, payload):
    wire = p.encode_frame(msg_type, payload)
    assert wire.endswith(b"\x00")
    assert 0 not in wire[:-1]
    dec = p.StreamDecoder()
    frames = list(dec.feed(wire))
    assert frames == [(msg_type, payload)]


def test_status_roundtrip():
    wire = p.pack_status(intensity=200, ramp=8000, hold=10000,
                         button_mask=0b1010, armed=True, phase="T",
                         tick=123456)
    (mtype, payload), = p.StreamDecoder().feed(wire)
    assert mtype == p.RSP_STATUS
    st = p.unpack_status(payload)
    assert st == {
        "intensity": 200, "ramp_ticks": 8000, "hold_ticks": 10000,
        "button_mask": 0b1010, "gpio_armed": True, "phase": "T",
        "tick": 123456,
    }


# --- stream behaviour: framing, concatenation, resync -------------------
def test_stream_multiple_frames_one_feed():
    wire = (p.encode_frame(p.CMD_QUERY)
            + p.pack_set_intensity(1)
            + p.encode_frame(p.CMD_TRIGGER))
    frames = list(p.StreamDecoder().feed(wire))
    assert [f[0] for f in frames] == [p.CMD_QUERY, p.CMD_SET_INTENSITY,
                                      p.CMD_TRIGGER]


def test_stream_byte_at_a_time():
    wire = p.pack_set_ramp(12345)
    dec = p.StreamDecoder()
    out = []
    for b in wire:
        out.extend(dec.feed(bytes([b])))
    assert out == [(p.CMD_SET_RAMP, p._U32.pack(12345))]


def test_stream_resyncs_after_garbage():
    good = p.encode_frame(p.CMD_TRIGGER)
    # Leading garbage with no delimiter, then a stray delimiter, then good.
    stream = b"\x05\x06\x07\x00" + good
    frames = list(p.StreamDecoder().feed(stream))
    assert frames == [(p.CMD_TRIGGER, b"")]


def test_stream_drops_corrupted_crc():
    wire = bytearray(p.pack_set_intensity(123))
    # Flip a bit in the COBS body (not the delimiter) -> CRC fails.
    wire[1] ^= 0x01
    frames = list(p.StreamDecoder().feed(bytes(wire)))
    assert frames == []


def test_stream_recovers_after_corrupt_then_good():
    bad = bytearray(p.pack_set_intensity(123))
    bad[1] ^= 0x01
    good = p.encode_frame(p.CMD_TRIGGER)
    frames = list(p.StreamDecoder().feed(bytes(bad) + good))
    assert frames == [(p.CMD_TRIGGER, b"")]
