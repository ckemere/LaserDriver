"""Off-hardware tests for the C broker's extras: the UDP trigger listener
and the JSON edge cases.  (Shared broker behaviour is covered by
test_integration.py, which runs against both brokers.)

fake_mcu <-> laserhat-brokerd --gpio sim --udp 127.0.0.1:<port>

Run:  python3 -m pytest Pi/tests/test_brokerd.py
"""

import contextlib
import os
import socket
import struct
import subprocess
import sys
import time

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PI = os.path.join(HERE, "..")
sys.path.insert(0, PI)
sys.path.insert(0, HERE)

import hat_client  # noqa: E402
import udp_trigger as ut  # noqa: E402
from test_integration import BROKERD, _wait, build_brokerd  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _built():
    if not build_brokerd():
        pytest.skip("can't build laserhat-brokerd here")


def _free_udp_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@contextlib.contextmanager
def running_broker(*extra):
    """fake_mcu + brokerd; yields (HatClient, udp_port)."""
    sock = f"/tmp/lh_brokerd_{os.getpid()}_{time.monotonic_ns()}.sock"
    port = _free_udp_port()
    fake = subprocess.Popen([sys.executable, os.path.join(PI, "fake_mcu.py")],
                            stdout=subprocess.PIPE, text=True)
    slave = fake.stdout.readline().strip()
    broker = subprocess.Popen([BROKERD, "--device", slave, "--socket", sock,
                               "--udp", f"127.0.0.1:{port}", *extra])
    client = None
    try:
        assert _wait(lambda: os.path.exists(sock)), "broker socket never appeared"
        client = hat_client.HatClient(sock)
        assert _wait(lambda: client.get_state() is not None), "MCU never alive"
        yield client, port
    finally:
        if client:
            client.close()
        broker.terminate()
        fake.terminate()
        broker.wait(timeout=5)
        fake.wait(timeout=5)
        with contextlib.suppress(OSError):
            os.unlink(sock)


def stats(client) -> dict:
    r = client._command({"cmd": "stats"})
    assert r.get("ok"), r
    return r


def raw_udp(port, payload: bytes, timeout=0.2):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(payload, ("127.0.0.1", port))
        return s.recv(64)
    except socket.timeout:
        return None
    finally:
        s.close()


def test_udp_trigger_sim():
    with running_broker("--gpio", "sim") as (client, port):
        with ut.TriggerClient("127.0.0.1", port) as t:
            # ping: answered by the trigger thread, never fires
            ack = t.ping(timeout=0.5)
            assert ack is not None and ack.status == "pong"
            assert ack.edge_ns == 0 and ack.rx_ns > 0
            assert ack.flags & ut.F_GPIO_SIM
            assert stats(client)["udp_fired"] == 0

            # fire
            ack = t.fire(timeout=0.5)
            assert ack is not None and ack.status == "fired", ack
            assert ack.seq == t._seq
            assert not ack.flags & ut.F_MCU_DOWN
            assert 0 <= ack.pi_latency_ns < 50_000_000
            first_edge = ack.edge_ns

            # retry of the same seq: duplicate, original edge, no second pulse
            dup = t.fire(timeout=0.5, seq=ack.seq)
            assert dup is not None and dup.status == "duplicate"
            assert dup.edge_ns == first_edge

            # a new seq fires again
            again = t.fire(timeout=0.5)
            assert again is not None and again.status == "fired"
            assert again.edge_ns > first_edge

        st = stats(client)
        assert st["udp_fired"] == 2 and st["udp_duplicate"] == 1
        assert st["udp_ping"] == 1 and st["gpio"] == "sim"

        # wrong version -> bad_version reply; wrong magic -> silence
        bad_ver = struct.pack("<IBBHIQ", ut.MAGIC, 99, ut.TRIGGER, 0, 7, 0)
        r = ut.unpack_reply(raw_udp(port, bad_ver))
        assert r is not None and r[1] == "bad_version"
        assert raw_udp(port, b"\x00" * 20) is None
        assert raw_udp(port, b"short") is None
        assert stats(client)["udp_fired"] == 2

        # the GUI path (JSON trigger_gpio) shares the same line
        assert client.trigger_gpio()


def test_udp_no_gpio():
    with running_broker("--gpio", "none") as (client, port):
        with ut.TriggerClient("127.0.0.1", port) as t:
            ack = t.fire(timeout=0.5)
            assert ack is not None and ack.status == "no_gpio"
        assert not client.trigger_gpio()


def test_udp_allowlist():
    with running_broker("--gpio", "sim", "--udp-allow", "127.0.0.2") as (client, port):
        with ut.TriggerClient("127.0.0.1", port) as t:
            assert t.fire(timeout=0.2) is None
        st = stats(client)
        assert st["udp_denied"] == 1 and st["udp_fired"] == 0


def test_json_edge_cases():
    with running_broker("--gpio", "sim") as (client, port):
        c = client
        assert c._command({"cmd": "nope"}).get("error") == "unknown_cmd"
        r = c._command({"cmd": "set", "knob": "i", "value": "abc"})
        assert r.get("error") == "bad_value"
        assert not c._command({"cmd": "set", "knob": "zz", "value": 5})["ok"]
        assert not c._command({"cmd": "set", "knob": "i", "value": -1})["ok"]
        assert c._command({"cmd": "set", "knob": "i", "value": "150"})["ok"]
        assert _wait(lambda: c.get_state().intensity == 150)

        assert c.set_mode("estim")
        assert _wait(lambda: c.get_state().mode == 1)
        assert c.set_estim_dur(25)
        assert _wait(lambda: c.get_state().estim_dur_ticks == 25)
        assert not c.set_mode("bogus")
        assert c.set_mode("laser")

        # malformed JSON over the raw socket
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(c._sock.getpeername())
        f = s.makefile("rw")
        f.readline()                                    # initial state
        f.write("{not json\n")
        f.flush()
        replies = []
        while len(replies) < 1:
            line = f.readline()
            if '"reply"' in line:
                replies.append(line)
        assert "bad_json" in replies[0]
        s.close()
