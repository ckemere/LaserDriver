#!/usr/bin/env python3
"""Cross-check the firmware C codec against Pi/protocol.py.

Builds proto_selftest (native gcc), then for a set of frames confirms the
C encoder produces byte-identical wire output to protocol.encode_frame and
that the C decoder recovers what protocol.StreamDecoder does.

Run from anywhere:  python3 host_tools/proto_crosscheck.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.dirname(HERE)
PI = os.path.join(FW, "..", "..", "Pi")
sys.path.insert(0, PI)

import protocol as p  # noqa: E402

BIN = "/tmp/proto_selftest"

CASES = [
    (p.CMD_TRIGGER, b""),
    (p.CMD_QUERY, b""),
    (p.CMD_SET_INTENSITY, p._U16.pack(320)),
    (p.CMD_SET_INTENSITY, p._U16.pack(1)),
    (p.CMD_SET_RAMP, p._U32.pack(8000)),
    (p.CMD_SET_HOLD, p._U32.pack(10_000_000)),
    (p.RSP_ACK, bytes([p.CMD_SET_RAMP, p.ACK_OK])),
    (p.EVT_PULSE_START, p._U32.pack(0xDEADBEEF)),
    (p.EVT_BUTTON, bytes([0b0101, 0b0100])),
    (p.RSP_STATUS, p._STATUS_STRUCT.pack(200, 8000, 10000, 0b1010, 1,
                                         p.PHASE_TRIGGERED, 123456)),
]


def build():
    subprocess.run(
        ["cc", "-I" + FW, os.path.join(HERE, "proto_selftest.c"),
         os.path.join(FW, "crc16.c"), os.path.join(FW, "cobs.c"),
         os.path.join(FW, "framing.c"), "-o", BIN],
        check=True,
    )


def c(*args):
    return subprocess.run([BIN, *args], capture_output=True, text=True,
                          check=True).stdout.strip()


def main():
    build()

    # CRC vector.
    assert c("crc") == "29b1", c("crc")

    failures = 0
    for mtype, payload in CASES:
        want = p.encode_frame(mtype, payload).hex()
        got = c("encode", f"{mtype:02x}", payload.hex())
        if got != want:
            print(f"ENCODE MISMATCH type={mtype:#04x}\n  py={want}\n  c ={got}")
            failures += 1
            continue
        # Round-trip: C decode of the wire must recover type+payload.
        dec = c("decode", want)
        exp = f"{mtype:02x} {payload.hex()}".strip()
        if dec != exp:
            print(f"DECODE MISMATCH type={mtype:#04x}\n  exp={exp}\n  got={dec}")
            failures += 1

    if failures:
        print(f"\n{failures} mismatch(es)")
        return 1
    print(f"OK: {len(CASES)} frames byte-identical C<->Python, CRC vector matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
