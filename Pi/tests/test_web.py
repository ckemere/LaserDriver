"""Smoke test for the migrated web app against fake_mcu + broker.

Drives web_app.create_app(HatClient) via Flask's test client and checks
the API routes round-trip through the broker to the fake MCU.

Run:  python3 Pi/tests/test_web.py
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PI = os.path.join(HERE, "..")
sys.path.insert(0, PI)

import hat_client  # noqa: E402
import web_app     # noqa: E402


def _wait(pred, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


def run() -> int:
    py = sys.executable
    sock = f"/tmp/lh_web_{os.getpid()}.sock"
    fake = subprocess.Popen([py, os.path.join(PI, "fake_mcu.py")],
                            stdout=subprocess.PIPE, text=True)
    slave = fake.stdout.readline().strip()
    broker = subprocess.Popen([py, os.path.join(PI, "broker.py"),
                               "--device", slave, "--no-gpio", "--socket", sock])
    failures = []
    try:
        assert _wait(lambda: os.path.exists(sock)), "no broker socket"
        client = hat_client.HatClient(sock)
        assert _wait(lambda: client.get_state() is not None), "MCU not alive"

        app = web_app.create_app(client)
        c = app.test_client()

        st = c.get("/api/state").get_json()
        if not st.get("ok"):
            failures.append(f"/api/state not ok: {st}")

        r = c.post("/api/set/i", json={"value": 150}).get_json()
        if not r.get("ok"):
            failures.append(f"set i failed: {r}")
        if not _wait(lambda: c.get("/api/state").get_json().get("intensity") == 150):
            failures.append("intensity not reflected via /api/state")

        r = c.post("/api/set/i", json={"value": 99999}).get_json()
        if r.get("ok"):
            failures.append("out-of-range set wrongly ok")

        r = c.post("/api/trigger").get_json()
        if not r.get("ok"):
            failures.append(f"trigger failed: {r}")

        # GPIO trigger has no real pin under --no-gpio, so expect ok False
        # (broker returns False when PiTrigger is absent) — just confirm the
        # route doesn't 500.
        resp = c.post("/api/trigger_gpio")
        if resp.status_code != 200:
            failures.append(f"trigger_gpio status {resp.status_code}")

        client.close()
    finally:
        broker.terminate(); fake.terminate()
        broker.wait(timeout=5); fake.wait(timeout=5)
        try:
            os.unlink(sock)
        except OSError:
            pass

    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("web OK: state, set+mirror, range-reject, trigger, trigger_gpio route")
    return 0


def test_web():
    assert run() == 0


if __name__ == "__main__":
    raise SystemExit(run())
