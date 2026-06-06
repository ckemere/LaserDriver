"""End-to-end off-hardware test: fake_mcu <-> broker <-> hat_client.

Spawns the PTY simulator and the broker as subprocesses, then drives the
broker through a HatClient and checks that commands ACK, state mirrors
edits, and pulse/button events propagate.

Run:  python3 Pi/tests/test_integration.py
  or: python3 -m pytest Pi/tests/test_integration.py
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PI = os.path.join(HERE, "..")
sys.path.insert(0, PI)

import hat_client  # noqa: E402


def _wait(predicate, timeout=5.0, interval=0.02):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(interval)
    return False


def run() -> int:
    py = sys.executable
    sock = f"/tmp/lh_test_{os.getpid()}.sock"

    fake = subprocess.Popen([py, os.path.join(PI, "fake_mcu.py")],
                            stdout=subprocess.PIPE, text=True)
    slave = fake.stdout.readline().strip()
    assert slave, "fake_mcu did not report a device"

    broker = subprocess.Popen(
        [py, os.path.join(PI, "broker.py"),
         "--device", slave, "--no-gpio", "--socket", sock])

    failures = []
    try:
        assert _wait(lambda: os.path.exists(sock)), "broker socket never appeared"

        events = []
        client = hat_client.HatClient(sock, on_update=events.append)

        # MCU comes alive (broker polls QUERY, gets RSP_STATUS).
        if not _wait(lambda: client.get_state() is not None):
            failures.append("state never became alive")

        st = client.get_state()
        if st and st.intensity != 320:
            failures.append(f"unexpected default intensity {st.intensity}")

        # set intensity -> ACK ok, and the cached state mirrors it.
        if not client.set_intensity(200):
            failures.append("set_intensity not acked ok")
        if not _wait(lambda: getattr(client.get_state(), "intensity", None) == 200):
            failures.append("intensity edit did not reflect in state")

        # out-of-range set is rejected.
        if client.set_intensity(9999):
            failures.append("out-of-range intensity wrongly accepted")

        # trigger -> ACK ok, and pulse_start/pulse_end events propagate.
        del events[:]
        if not client.trigger():
            failures.append("trigger not acked ok")
        got_start = _wait(lambda: any(e.get("event") == "pulse_start" for e in events))
        got_end = _wait(lambda: any(e.get("event") == "pulse_end" for e in events))
        if not (got_start and got_end):
            failures.append(f"missing pulse events (start={got_start} end={got_end})")

        client.close()
    finally:
        broker.terminate()
        fake.terminate()
        broker.wait(timeout=5)
        fake.wait(timeout=5)
        try:
            os.unlink(sock)
        except OSError:
            pass

    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("integration OK: alive, set+mirror, range-reject, pulse events")
    return 0


def test_integration():
    assert run() == 0


if __name__ == "__main__":
    raise SystemExit(run())
