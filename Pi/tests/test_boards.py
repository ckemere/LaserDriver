"""Board awareness end to end: fake_mcu --board <b> <-> broker (both brokers)
<-> hat_client, with a fake HAT EEPROM node (LASERHAT_HAT_DIR).

Covers: the broker publishes `board` (from the EEPROM / --board / fallback)
and `fw_board` (RSP_VERSION.board), fw_ok goes false when they disagree
(UNKNOWN fw_board = old firmware: a mismatch only on a StimHAT /
LaserDriverHAT), a single-mode board's refusal of the other mode passes
through (set_mode -> ok false, mode unchanged), and the StimHAT's 6th
button (mask bit 6) gets through the broker's STATUS range check.

Run:  python3 -m pytest Pi/tests/test_boards.py
"""

import os
import signal
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PI = os.path.join(HERE, "..")
sys.path.insert(0, PI)
sys.path.insert(0, HERE)

import hat_client  # noqa: E402
import protocol as proto  # noqa: E402
from test_hat_id import make_hat_dir  # noqa: E402
from test_integration import (_wait, build_brokerd, c_broker,  # noqa: E402
                              python_broker)

HAT_FIELDS = {"rev2": ("LaserHAT Rev 2", "0x0002", "0x0002"),
              "stim": ("StimHAT", "0x0003", "0x0001"),
              "laser": ("LaserDriverHAT", "0x0004", "0x0001")}


def scenario(broker_cmd, hat_board, fake_board, broker_extra=(), env_extra=None):
    """Start fake_mcu (as fake_board) + a broker that sees a HAT EEPROM for
    hat_board (None = no EEPROM).  Yields (client, fake process)."""
    tmp = tempfile.TemporaryDirectory()
    if hat_board is None:
        hat_dir = os.path.join(tmp.name, "no-hat")
    else:
        product, pid, pver = HAT_FIELDS[hat_board]
        hat_dir = make_hat_dir(tmp.name, product=product, pid=pid, pver=pver)
    env = dict(os.environ, LASERHAT_HAT_DIR=hat_dir, **(env_extra or {}))
    sock = os.path.join(tmp.name, "broker.sock")
    fake = subprocess.Popen([sys.executable, os.path.join(PI, "fake_mcu.py"),
                             "--board", fake_board],
                            stdout=subprocess.PIPE, text=True, env=env)
    slave = fake.stdout.readline().strip()
    broker = subprocess.Popen(broker_cmd(slave, sock, *broker_extra), env=env)
    return tmp, fake, broker, sock


class Running:
    def __init__(self, *a, **kw):
        self.args, self.kw = a, kw

    def __enter__(self):
        self.tmp, self.fake, self.broker, sock = scenario(*self.args, **self.kw)
        assert _wait(lambda: os.path.exists(sock)), "broker socket never appeared"
        self.events = []
        self.client = hat_client.HatClient(sock, on_update=self.events.append)
        assert _wait(lambda: self.client.get_state() is not None), "MCU never alive"
        assert _wait(lambda: self.client.get_state().fw_ok is not None), \
            "version probe never completed"
        return self

    def __exit__(self, *exc):
        self.client.close()
        for proc in (self.broker, self.fake):
            proc.terminate()
        for proc in (self.broker, self.fake):
            proc.wait(timeout=5)
        self.tmp.cleanup()


def check_identity(broker_cmd):
    # (EEPROM board, fake firmware board, extra broker args, env,
    #  -> board, board_source, fw_board, fw_ok)
    cases = [
        ("stim", "stim", (), None, "stim", "eeprom", "stim", True),
        ("laser", "laser", (), None, "laser", "eeprom", "laser", True),
        ("rev2", "rev2", (), None, "rev2", "eeprom", "rev2", True),
        ("stim", "rev2", (), None, "stim", "eeprom", "rev2", False),
        ("rev2", "stim", (), None, "rev2", "eeprom", "stim", False),
        ("laser", "stim", (), None, "laser", "eeprom", "stim", False),
        # old firmware (board byte 0): fine on Rev 2, not on the new boards
        ("rev2", "unknown", (), None, "rev2", "eeprom", "unknown", True),
        ("stim", "unknown", (), None, "stim", "eeprom", "unknown", False),
        ("laser", "unknown", (), None, "laser", "eeprom", "unknown", False),
        # no EEPROM: --board, then $LASERHAT_BOARD, then Rev 2
        (None, "unknown", (), None, "rev2", "default", "unknown", True),
        (None, "stim", (), None, "rev2", "default", "stim", False),
        (None, "stim", ("--board", "stim"), None, "stim", "argument", "stim", True),
        (None, "laser", (), {"LASERHAT_BOARD": "laser"}, "laser", "env", "laser", True),
        # the EEPROM wins over a contradicting --board in the daemons
        ("stim", "stim", ("--board", "rev2"), None, "stim", "eeprom", "stim", True),
    ]
    failures = []
    for hat, fake, extra, env, board, source, fw_board, ok in cases:
        with Running(broker_cmd, hat, fake, extra, env) as r:
            st = r.client.get_state()
            got = (st.board, st.board_source, st.fw_board, st.fw_ok)
            if got != (board, source, fw_board, ok):
                failures.append(f"hat={hat} fake={fake} extra={extra} env={env}: "
                                f"{got} != {(board, source, fw_board, ok)}")
    assert not failures, "\n".join(failures)


def check_mode_refusal_and_button(broker_cmd):
    with Running(broker_cmd, "stim", "stim") as r:
        c = r.client
        assert c.get_state().mode == proto.MODE_ESTIM          # boots in e-stim
        assert not c.set_mode("laser")                         # refused: echo unchanged
        assert c.get_state().mode == proto.MODE_ESTIM
        assert c.set_mode("estim")
        assert c.set_estim_dac(820)                            # normal knobs still work

        # 6th button: SIGUSR1 makes the fake press + hold + release "right"
        del r.events[:]
        r.fake.send_signal(signal.SIGUSR1)
        assert _wait(lambda: any(e.get("event") == "button"
                                 and e.get("mask") == proto.BUTTON_RIGHT
                                 for e in r.events)), "no bit-6 button event"
        # The STATUS polls during the 0.4 s hold carry bit 6, and the broker
        # must accept them (range check).  The EVT_BUTTON broadcast repeats
        # the last tick; only an accepted STATUS brings a new tick with the
        # bit still set -> at least two distinct ticks with mask == bit 6.
        def held_ticks():
            return {e.get("tick") for e in r.events if e.get("type") == "state"
                    and e.get("button_mask") == proto.BUTTON_RIGHT}
        assert _wait(lambda: len(held_ticks()) >= 2), \
            f"no STATUS with bit 6 accepted (ticks {held_ticks()})"
        assert _wait(lambda: c.get_state().button_mask == 0)
        assert c.get_state() is not None

    with Running(broker_cmd, "laser", "laser") as r:
        c = r.client
        assert c.get_state().mode == proto.MODE_LASER
        assert not c.set_mode("estim")
        assert c.get_state().mode == proto.MODE_LASER
        assert c.set_laser_dac(1500)

    with Running(broker_cmd, "rev2", "rev2") as r:             # both modes
        assert r.client.set_mode("estim") and r.client.set_mode("laser")


def test_oled_compose_per_board():
    import oled_gui
    from laser_hat import State
    base = dict(intensity=100, ramp_ticks=2000, hold_ticks=500, button_mask=0,
                phase="W", tick=0)
    tag, rows, chip, _ = oled_gui.compose(State(**base, mode=1, board="stim"), 0)
    assert tag == "STIMHAT[E]" and chip == "WAIT"
    assert oled_gui._MODE_ITEM not in oled_gui._items_for(State(**base, mode=1, board="stim"))
    tag, *_ = oled_gui.compose(State(**base, mode=0, board="laser"), 0)
    assert tag == "LASERDRV[L]"
    st = State(**base, mode=0, board="rev2")
    assert oled_gui.compose(st, 0)[0] == "LASERHAT[L]"
    assert oled_gui._MODE_ITEM in oled_gui._items_for(st)
    # a board / firmware mismatch shows FW! like a version mismatch
    assert oled_gui.compose(State(**base, mode=1, board="stim", fw_ok=False), 0)[2] == "FW!"


def test_board_identity_python():
    check_identity(python_broker)


def test_mode_refusal_and_button_python():
    check_mode_refusal_and_button(python_broker)


def test_board_identity_brokerd():
    import pytest
    if not build_brokerd():
        pytest.skip("can't build laserhat-brokerd here")
    check_identity(c_broker)


def test_mode_refusal_and_button_brokerd():
    import pytest
    if not build_brokerd():
        pytest.skip("can't build laserhat-brokerd here")
    check_mode_refusal_and_button(c_broker)


if __name__ == "__main__":
    for broker in (python_broker, c_broker):
        if broker is c_broker and not build_brokerd():
            continue
        check_identity(broker)
        check_mode_refusal_and_button(broker)
    print("boards OK")
