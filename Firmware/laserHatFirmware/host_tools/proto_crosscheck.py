#!/usr/bin/env python3
"""Cross-check the firmware framing against Pi/protocol.py.

Builds proto_selftest (native gcc) and confirms the C frame encoder
produces byte-identical wire output to protocol.encode_frame, and that the
C command decoder recovers what was sent.

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

# (type, payload) — covers both directions for the encoder; only command
# types are fed through the C decoder (the MCU only decodes commands).
CASES = [
    (p.CMD_TRIGGER, b""),
    (p.CMD_QUERY, b""),
    (p.CMD_CONFIG, p._CONFIG.pack(320, 8000, 10000)),
    (p.CMD_CONFIG, p._CONFIG.pack(1, 1, 10_000_000)),
    (p.RSP_STATUS, p._STATUS.pack(200, 8000, 10000, 0b1010,
                                  p.PHASE_TRIGGERED, 123456)),
    (p.EVT_PULSE_START, p._U32.pack(0xDEADBEEF)),
    (p.EVT_BUTTON, bytes([0b0101, 0b0100])),
]


def build():
    subprocess.run(
        ["cc", "-I" + FW, os.path.join(HERE, "proto_selftest.c"),
         os.path.join(FW, "framing.c"), "-o", BIN],
        check=True,
    )


def c(*args):
    return subprocess.run([BIN, *args], capture_output=True, text=True,
                          check=True).stdout.strip()


def main():
    build()
    failures = 0
    for mtype, payload in CASES:
        want = p.encode_frame(mtype, payload).hex()
        got = c("encode", f"{mtype:02x}", payload.hex())
        if got != want:
            print(f"ENCODE MISMATCH type={mtype:#04x}\n  py={want}\n  c ={got}")
            failures += 1
            continue
        if mtype in p.CMD_LEN:                # decoder handles commands only
            dec = c("decode", want)
            exp = f"{mtype:02x} {payload.hex()}".strip()
            if dec != exp:
                print(f"DECODE MISMATCH type={mtype:#04x}\n  exp={exp}\n  got={dec}")
                failures += 1

    if failures:
        print(f"\n{failures} mismatch(es)")
        return 1
    print(f"OK: {len(CASES)} frames byte-identical C<->Python")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
