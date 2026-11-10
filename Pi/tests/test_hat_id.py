"""Board identity (Pi/hat_id.py): HAT EEPROM encoder / parser, the
/proc/device-tree/hat reader, and the board / pin resolution precedence.
Also the laserhat-eeprom CLI's offline commands.

Pure stdlib (pytest optional):
    python3 -m pytest Pi/tests/test_hat_id.py
    python3 Pi/tests/test_hat_id.py
"""

import os
import struct
import subprocess
import sys
import tempfile
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PI = os.path.join(HERE, "..")
sys.path.insert(0, PI)

import hat_id as h      # noqa: E402
import protocol as p    # noqa: E402


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    raise AssertionError(f"{fn.__name__} did not raise {exc.__name__}")


def make_hat_dir(root, vendor="KemereLab", product="StimHAT", pid="0x0003",
                 pver="0x0001", u="5b2e4c1a-0000-4000-8000-000000000001"):
    """A fake /proc/device-tree/hat as the Pi firmware writes it
    (NUL-terminated string properties)."""
    d = os.path.join(root, "hat")
    os.makedirs(d, exist_ok=True)
    for name, value in (("vendor", vendor), ("product", product),
                        ("product_id", pid), ("product_ver", pver), ("uuid", u)):
        if value is not None:
            with open(os.path.join(d, name), "wb") as f:
                f.write(value.encode() + b"\0")
    return d


# ------------------------------------------------------------- CRC + format
def _eepmake_getcrc(data: bytes) -> int:
    """Bit-for-bit transliteration of getcrc() in the Raspberry Pi hats
    repo's eepmake.c, to pin our table-free CRC to the reference."""
    out, bits_read, i, size = 0, 0, 0, len(data)
    while size > 0:
        bit_flag = out >> 15
        out = ((out << 1) & 0xFFFF) | ((data[i] >> bits_read) & 1)
        bits_read += 1
        if bits_read > 7:
            bits_read, i, size = 0, i + 1, size - 1
        if bit_flag:
            out ^= 0x8005
    for _ in range(16):
        bit_flag = out >> 15
        out = (out << 1) & 0xFFFF
        if bit_flag:
            out ^= 0x8005
    crc, a, b = 0, 0x8000, 0x0001
    while a:
        if a & out:
            crc |= b
        a >>= 1
        b <<= 1
    return crc


def test_crc16_matches_spec():
    assert h.crc16(b"123456789") == 0xBB3D          # CRC-16/ARC check value
    for blob in (b"", b"\x00", b"R-Pi", bytes(range(256)), h.build_eeprom("stim")):
        assert h.crc16(blob) == _eepmake_getcrc(blob), blob[:8]


def test_build_and_parse_every_board():
    for name, board in h.BOARDS.items():
        u = uuid.uuid4()
        image = h.build_eeprom(name, u)
        sig, ver, res, numatoms, eeplen = struct.unpack_from("<4sBBHI", image)
        assert (sig, ver, res, numatoms) == (b"R-Pi", 1, 0, 2)
        assert eeplen == len(image) <= h.EEPROM_SIZE
        img = h.parse_eeprom(image + b"\xff" * 64)      # erased tail ignored
        assert img.vendor == "KemereLab" and img.product == board.product
        assert (img.product_id, img.product_ver) == (board.pid, board.pver)
        assert img.uuid == str(u)
        assert img.hat_info().board == name
        assert [a["type"] for a in img.atoms] == [h.ATOM_VENDOR_INFO, h.ATOM_GPIO_MAP]
        assert [a["count"] for a in img.atoms] == [0, 1]
        assert img.gpio_map == bytes(30)                # no GPIO set-up requested


def test_fixed_identities():
    want = {"rev2": ("LaserHAT Rev 2", 0x0002, 0x0002),
            "stim": ("StimHAT", 0x0003, 0x0001),
            "laser": ("LaserDriverHAT", 0x0004, 0x0001)}
    assert {k: (b.product, b.pid, b.pver) for k, b in h.BOARDS.items()} == want
    assert h.VENDOR == "KemereLab"
    # the firmware board byte each board expects
    assert {k: b.fw_type for k, b in h.BOARDS.items()} == {
        "rev2": p.BOARD_TYPE_REV2, "stim": p.BOARD_TYPE_STIM, "laser": p.BOARD_TYPE_LASER}
    assert all(p.board_type_name(b.fw_type) == k for k, b in h.BOARDS.items())


def test_atom_layout_and_lengths():
    u = uuid.UUID("12345678-1234-5678-9abc-def012345678")
    image = h.build_eeprom("laser", u)
    off = 12
    atype, count, dlen = struct.unpack_from("<HHI", image, off)
    assert (atype, count) == (1, 0)
    data = image[off + 8:off + 8 + dlen - 2]
    # uuid: the 128-bit value little-endian (eepmake serial_1 = last 8 digits)
    assert data[:4] == bytes.fromhex("78563412")
    assert data[:16] == u.int.to_bytes(16, "little")
    pid, pver, vslen, pslen = struct.unpack_from("<HHBB", data, 16)
    assert (pid, pver, vslen, pslen) == (4, 1, 9, 14)
    assert data[22:] == b"KemereLabLaserDriverHAT"
    assert dlen == len(data) + 2 == 22 + 9 + 14 + 2
    crc = struct.unpack_from("<H", image, off + 8 + dlen - 2)[0]
    assert crc == h.crc16(image[off:off + 8 + dlen - 2])
    off += 8 + dlen
    atype, count, dlen = struct.unpack_from("<HHI", image, off)
    assert (atype, count, dlen) == (2, 1, 32)
    assert off + 8 + dlen == len(image)


def test_parse_rejects_corruption():
    image = bytearray(h.build_eeprom("rev2"))
    _raises(ValueError, h.parse_eeprom, b"\xff" * 64)         # blank part
    _raises(ValueError, h.parse_eeprom, bytes(image[:10]))
    bad = bytearray(image)
    bad[30] ^= 0x01                                          # flip a vendor-atom bit
    _raises(ValueError, h.parse_eeprom, bytes(bad))
    bad = bytearray(image)
    struct.pack_into("<I", bad, 8, len(image) + 50)          # eeplen past the data
    _raises(ValueError, h.parse_eeprom, bytes(bad))
    bad = bytearray(image)
    bad[4] = 2                                               # format version
    _raises(ValueError, h.parse_eeprom, bytes(bad))


def test_random_uuid_per_image():
    a, b = h.parse_eeprom(h.build_eeprom("stim")), h.parse_eeprom(h.build_eeprom("stim"))
    assert a.uuid != b.uuid


# ----------------------------------------------------- /proc/device-tree/hat
def test_read_hat_and_board_mapping():
    with tempfile.TemporaryDirectory() as root:
        assert h.read_hat(os.path.join(root, "missing")) is None
        d = make_hat_dir(root)
        info = h.read_hat(d)
        assert (info.vendor, info.product, info.product_id, info.product_ver) == \
            ("KemereLab", "StimHAT", 3, 1)
        assert info.board == "stim"
    with tempfile.TemporaryDirectory() as root:
        assert h.read_hat(make_hat_dir(root, product="LaserDriverHAT", pid="0x0004")).board == "laser"
    with tempfile.TemporaryDirectory() as root:
        assert h.read_hat(make_hat_dir(root, product="LaserHAT Rev 2", pid="0x0002",
                                       pver="0x0002")).board == "rev2"
    with tempfile.TemporaryDirectory() as root:      # someone else's HAT
        assert h.read_hat(make_hat_dir(root, vendor="Adafruit", pid="0x0003")).board == "unknown"
    with tempfile.TemporaryDirectory() as root:      # our vendor, future product
        assert h.read_hat(make_hat_dir(root, product="Thing", pid="0x0099")).board == "unknown"
    with tempfile.TemporaryDirectory() as root:      # garbled id, known name
        assert h.read_hat(make_hat_dir(root, pid="zz")).board == "stim"


def test_parsed_image_matches_device_tree_view():
    """What we write is what the firmware will publish: the parsed image's
    fields put into a fake hat dir resolve to the same board."""
    for name in h.BOARDS:
        img = h.parse_eeprom(h.build_eeprom(name))
        with tempfile.TemporaryDirectory() as root:
            d = make_hat_dir(root, img.vendor, img.product, f"0x{img.product_id:04x}",
                             f"0x{img.product_ver:04x}", img.uuid)
            assert h.read_hat(d).board == name
            assert h.read_hat(d).uuid == img.uuid


# ----------------------------------------------------------------- resolution
def test_resolution_precedence():
    nowhere = "/nonexistent/laserhat-hat"
    # nothing known -> Rev 2
    r = h.resolve(None, env={}, directory=nowhere)
    assert (r.board, r.source) == ("rev2", "default")
    assert r.pins == {"swclk": 24, "swdio": 25, "nrst": 23, "power": 18, "trigger": 26}
    # $LASERHAT_BOARD
    r = h.resolve(None, env={"LASERHAT_BOARD": "stim"}, directory=nowhere)
    assert (r.board, r.source) == ("stim", "env")
    assert r.pins == {"swclk": 24, "swdio": 25, "nrst": 9, "power": 10, "trigger": 18}
    # --board beats $LASERHAT_BOARD when there is no EEPROM identity
    r = h.resolve("laser", env={"LASERHAT_BOARD": "stim"}, directory=nowhere)
    assert (r.board, r.source) == ("laser", "argument")
    _raises(ValueError, h.resolve, "rev3", env={}, directory=nowhere)
    # a bad $LASERHAT_BOARD is ignored with a note
    r = h.resolve(None, env={"LASERHAT_BOARD": "nope"}, directory=nowhere)
    assert r.board == "rev2" and r.notes

    with tempfile.TemporaryDirectory() as root:
        d = make_hat_dir(root)                                   # a StimHAT EEPROM
        # EEPROM beats $LASERHAT_BOARD
        r = h.resolve(None, env={"LASERHAT_BOARD": "rev2"}, directory=d)
        assert (r.board, r.source, r.eeprom_board, r.conflict) == ("stim", "eeprom", "stim", False)
        assert r.pins["trigger"] == 18 and r.pins["nrst"] == 9 and r.pins["power"] == 10
        # agreeing --board: still the EEPROM's, no conflict
        r = h.resolve("stim", env={}, directory=d)
        assert (r.board, r.source, r.conflict) == ("stim", "eeprom", False)
        # contradicting --board: EEPROM kept, conflict flagged ...
        r = h.resolve("rev2", env={}, directory=d)
        assert (r.board, r.source, r.conflict) == ("stim", "eeprom", True)
        # ... unless forced
        r = h.resolve("rev2", env={}, directory=d, force=True)
        assert (r.board, r.source, r.conflict) == ("rev2", "argument", True)
        assert r.pins["trigger"] == 26
        # per-pin environment overrides go on top of the board's table
        r = h.resolve(None, env={"LASERHAT_TRIGGER_PIN": "21", "LASERHAT_NRST_PIN": "9",
                                 "LASERHAT_POWER_PIN": "x"}, directory=d)
        assert r.board == "stim" and r.pins["trigger"] == 21 and r.pins["nrst"] == 9
        assert r.pin_overrides == {"trigger": "LASERHAT_TRIGGER_PIN"}   # 9 == the table's
        assert r.pins["power"] == 10 and any("LASERHAT_POWER_PIN" in n for n in r.notes)
        assert "TRIGGER=21*" in r.describe() and "HAT EEPROM" in r.describe()

    with tempfile.TemporaryDirectory() as root:              # foreign HAT
        d = make_hat_dir(root, vendor="Pimoroni", product="Blinkt")
        r = h.resolve(None, env={}, directory=d)
        assert r.foreign_hat and (r.board, r.source) == ("rev2", "default") and r.notes
        r = h.resolve("laser", env={}, directory=d)
        assert (r.board, r.source, r.conflict) == ("laser", "argument", False)


def test_rev1_style_env_overrides_on_fallback():
    # Firmware/Makefile.gcc HAT_REV=1 exports the Rev 1 pins
    r = h.resolve(None, env={"LASERHAT_POWER_PIN": "23", "LASERHAT_NRST_PIN": "18"},
                  directory="/nonexistent")
    assert r.board == "rev2" and r.pins["power"] == 23 and r.pins["nrst"] == 18


def test_shell_output_is_eval_safe():
    env = dict(os.environ, LASERHAT_HAT_DIR="/nonexistent", LASERHAT_BOARD="laser")
    env.pop("LASERHAT_TRIGGER_PIN", None)
    out = subprocess.run([sys.executable, os.path.join(PI, "hat_id.py"), "shell"],
                         capture_output=True, text=True, env=env, check=True).stdout
    vals = dict(line.split("=", 1) for line in out.splitlines())
    assert vals["LH_BOARD"] == "'laser'" and vals["LH_TRIGGER"] == "'18'"
    assert vals["LH_BOARD_SOURCE"] == "'env'" and vals["LH_CONFLICT"] == "'0'"
    # and through a real shell
    r = subprocess.run(["sh", "-c", 'eval "$(cat)"; echo "$LH_BOARD $LH_NRST $LH_POWER"'],
                       input=out, capture_output=True, text=True, check=True)
    assert r.stdout.strip() == "laser 9 10"


# ------------------------------------------------------------ laserhat-eeprom
def test_eeprom_cli_make_and_write_refusal():
    tool = os.path.join(PI, "laserhat-eeprom")
    env = dict(os.environ, LASERHAT_HAT_DIR="/nonexistent")
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "stim.eep")
        subprocess.run([sys.executable, tool, "make", "stim", "-o", out, "--uuid",
                        "00000000-0000-4000-8000-0000000000aa"], check=True,
                       capture_output=True, env=env)
        with open(out, "rb") as f:
            img = h.parse_eeprom(f.read())
        assert img.product == "StimHAT" and img.uuid.endswith("0000000000aa")
        # write without --yes: shows the image, writes nothing, exit 1
        r = subprocess.run([sys.executable, tool, "write", "laser", "--image", out],
                           capture_output=True, text=True, env=env)
        assert r.returncode == 1          # image is a StimHAT's, not a laser's
        r = subprocess.run([sys.executable, tool, "write", "stim", "--image", out],
                           capture_output=True, text=True, env=env)
        assert r.returncode == 1 and "--yes" in r.stdout
        r = subprocess.run([sys.executable, tool, "read"], capture_output=True,
                           text=True, env=env)
        assert r.returncode == 0 and "board rev2" in r.stdout


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as e:      # noqa: BLE001
                fails += 1
                print("FAIL", name, repr(e))
    raise SystemExit(1 if fails else 0)
