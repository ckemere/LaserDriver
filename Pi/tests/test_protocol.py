"""Unit tests for the magic-framed wire codec (Pi/protocol.py).

Run:  python3 -m pytest Pi/tests/test_protocol.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import protocol as p


# --- frame round-trip ---------------------------------------------------
@pytest.mark.parametrize("msg_type,payload", [
    (p.CMD_TRIGGER, b""),
    (p.CMD_QUERY, b""),
    (p.CMD_CONFIG, p._CONFIG.pack(320, 8000, 10000)),
    (p.EVT_PULSE_START, p._U32.pack(0xDEADBEEF)),
    (p.EVT_BUTTON, bytes([0b0101, 0b0100])),
])
def test_frame_roundtrip(msg_type, payload):
    wire = p.encode_frame(msg_type, payload)
    assert wire.startswith(p.SYNC)
    # Only decode response-direction types via StreamDecoder.
    if msg_type in p.RSP_LEN:
        assert list(p.StreamDecoder().feed(wire)) == [(msg_type, payload)]


def test_status_roundtrip():
    wire = p.pack_status(200, 8000, 10000, 0b1010, "T", 123456)
    (mtype, payload), = p.StreamDecoder().feed(wire)
    assert mtype == p.RSP_STATUS
    assert p.unpack_status(payload) == {
        "intensity": 200, "ramp_ticks": 8000, "hold_ticks": 10000,
        "button_mask": 0b1010, "phase": "T", "tick": 123456,
        "mode": p.MODE_LASER, "estim_dur_ticks": 10, "estim_ipi_ticks": 10,
        "laser_dac": p.LASER_DAC_DEFAULT, "estim_dac": 0, "module": 0,
        "adc_pd": 0, "adc_comp": 0,
    }


def test_module_fields_roundtrip():
    wire = p.pack_status(1, 1, 1, 0, "W", 0, p.MODE_ESTIM, 50, 20,
                         laser_dac=3650, estim_dac=4095,
                         module=p.MODULE_FAULT_LATCHED | p.MODULE_ESTIM_READY,
                         adc_pd=123, adc_comp=3700)
    (mtype, payload), = p.StreamDecoder().feed(wire)
    f = p.unpack_status(payload)
    assert (f["laser_dac"], f["estim_dac"], f["adc_pd"], f["adc_comp"]) == (3650, 4095, 123, 3700)
    assert f["module"] & p.MODULE_FAULT_LATCHED and f["module"] & p.MODULE_ESTIM_READY
    assert p.status_in_range(f)
    f["laser_dac"] = p.LASER_DAC_MAX + 1
    assert not p.status_in_range(f)

    fault = p.encode_frame(p.EVT_FAULT, p._FAULT.pack(p.MODULE_FAULT_LATCHED, 99))
    (mtype, payload), = p.StreamDecoder().feed(fault)
    assert mtype == p.EVT_FAULT and p.unpack_fault(payload) == (p.MODULE_FAULT_LATCHED, 99)

    assert p.unpack_dac(p.pack_laser_current(1216)[3:]) == 1216
    assert p.laser_ma_to_dac(300) <= p.LASER_DAC_MAX
    assert abs(p.laser_dac_to_ma(3650) - 300) < 2
    assert abs(p.estim_dac_to_ua(4095) - 502) < 1
    assert abs(p.comp_to_volts(3700) - 12.0) < 0.2


# --- magic avoidance for CONFIG -----------------------------------------
def test_avoid_magic_nudges_only_collisions():
    # A value whose low 16 bits == 0xADDE must be nudged; others untouched.
    collide = 0x00010000 | p.MAGIC16          # low16 == magic, in range
    assert collide & 0xFFFF == p.MAGIC16
    assert p.avoid_magic(collide) != collide
    assert p.avoid_magic(collide) & 0xFFFF != p.MAGIC16
    assert p.avoid_magic(8000) == 8000


def test_config_payload_never_contains_sync():
    # After nudging r and h, no CONFIG payload contains the SYNC pair.
    for r in (p.MAGIC16, 0xADDE, 8000, 1, 10_000_000):
        for h in (p.MAGIC16, 0xADDE, 500):
            wire = p.pack_config(320, p.avoid_magic(r), p.avoid_magic(h))
            payload = wire[3:]                # strip SYNC + TYPE
            assert p.SYNC not in payload, (r, h)


# --- stream behaviour: framing, concatenation, resync -------------------
def test_stream_multiple_frames_one_feed():
    wire = (p.pack_status(1, 1, 1, 0, "W", 0)
            + p.encode_frame(p.EVT_PULSE_START, p._U32.pack(7))
            + p.encode_frame(p.EVT_BUTTON, bytes([1, 1])))
    types = [f[0] for f in p.StreamDecoder().feed(wire)]
    assert types == [p.RSP_STATUS, p.EVT_PULSE_START, p.EVT_BUTTON]


def test_stream_byte_at_a_time():
    wire = p.encode_frame(p.EVT_PULSE_END, p._U32.pack(12345))
    dec = p.StreamDecoder()
    out = []
    for b in wire:
        out.extend(dec.feed(bytes([b])))
    assert out == [(p.EVT_PULSE_END, p._U32.pack(12345))]


def test_stream_resyncs_after_garbage():
    good = p.encode_frame(p.EVT_PULSE_START, p._U32.pack(9))
    stream = b"\x11\x22\x33" + good          # leading junk, no SYNC
    assert list(p.StreamDecoder().feed(stream)) == [(p.EVT_PULSE_START,
                                                     p._U32.pack(9))]


def test_stream_recovers_after_dropped_byte():
    # Simulate a dropped byte mid-STATUS, then a clean frame after it.
    s = bytearray(p.pack_status(1, 1, 1, 0, "W", 0))
    del s[5]                                  # drop a byte -> misframed
    good = p.encode_frame(p.EVT_BUTTON, bytes([2, 2]))
    frames = list(p.StreamDecoder().feed(bytes(s) + good))
    # The good frame is recovered (the corrupt one may or may not appear,
    # but the decoder must resync to the trailing EVT_BUTTON).
    assert (p.EVT_BUTTON, bytes([2, 2])) in frames


def test_status_range_check_rejects_garbage():
    assert p.status_in_range(p.unpack_status(
        p.pack_status(200, 8000, 10000, 1, "W", 5)[3:]))
    assert not p.status_in_range({
        "intensity": 9999, "ramp_ticks": 1, "hold_ticks": 1,
        "button_mask": 0, "phase": "W", "tick": 0,
        "mode": p.MODE_LASER, "estim_dur_ticks": 1, "estim_ipi_ticks": 1})
