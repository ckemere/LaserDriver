#!/usr/bin/env python3
"""LaserHat OLED GUI on the Adafruit 2.23" 128x32 bonnet (SSD1305).

Broker-client design: does NOT open the serial port, runs alongside the
web GUI.  Button presses arrive as EVT_BUTTON broadcasts; state arrives
as broadcast snapshots — no polling.

The panel itself is owned by the compiled oledd daemon (oledd.c), which
this process talks to over a Unix socket with a tiny line protocol
(TAG / ROW / CHIP / FLUSH — see oledd.c).  oledd draws the header's
alternating E:/W: IP display and the heartbeat dot on its own, so this
GUI only composes the mode tag and the three body rows.  No Pillow, no
adafruit-blinka — stdlib only.

Button mapping (Rev 2 HAT edge controls, reported by the MCU):
    B5  FIRE (SW9)       — the firmware fires a pulse on press; nothing to do here
    B2  SELECT (wheel push) — cycle selected row (laser: i→r→h→ld→[mode]→[off];
                           estim: dur→IPI→sd→[mode]→[off]); on a latched fault
                           the push also clears it
    B3  wheel roll       — decrement selected value  (on [mode] row: switch to LASER)
    B4  wheel roll       — increment selected value  (on [mode] row: switch to ESTIM)
    B1  BACK (SW8)       — jump back to the first row (also cancels an armed [off])
  [off] row: one roll (either way) arms it — the row reads "[off] roll again";
  a second roll the same way within 5 s requests an orderly shutdown through
  laserhat-power.path (power.py); the other direction, BACK or 5 s cancels.
  Then the OLED shows SHUTTING DOWN and goes blank when oledd stops: wait for
  the Pi's green LED to stop before cutting 5 V.
  If the wheel turns out to roll the "wrong" way, swap B3/B4 below.

Display layout (oledd cells: 21 columns × 4 rows):
    Row 0  header, owned by oledd: alternates LASERHAT[L|E] tag /
           E:<wired IP> / W:<wifi IP or WAITING>, heartbeat dot at right
    Row 1  ┐
    Row 2  ├  3-row scrolling window over the selectable items
    Row 3  ┘  phase chip (WAIT/TRIG) pinned to bottom-right corner

In LASER mode the selectable items are: i, r, h, ld (current, mA), [mode], [off]
In ESTIM mode the selectable items are: dur (ed), IPI (ei), sd (amplitude, µA), [mode], [off]
The window scrolls so the selected item is always visible.  The chip shows
FAULT (inverted) while a module fault is latched, and the e-stim rows show
"!" after the amplitude until the module's DAC has acknowledged (ready).
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time

import power
import protocol as proto
from hat_client import DEFAULT_SOCKET, HatClient
from laser_hat import State
from params import ESTIM_PARAMS, PARAMS


# --------------------------------------------------------------- config
POLL_INTERVAL = 0.05         # seconds between state reads
SETTLE_GAP    = 0.15         # render after this much quiet time

DEFAULT_OLED_SOCKET = "/run/laserhat-oled/oled.sock"

# Button bits in State.button_mask / EVT_BUTTON edges (see Pi/protocol.py).
B1, B2, B3, B4, B5 = 0b00001, 0b00010, 0b00100, 0b01000, 0b10000

# Sentinel objects for the mode-toggle and shutdown rows in the selection cycle.
_MODE_ITEM = object()
_OFF_ITEM = object()

OFF_ARM_S = 5.0              # second roll must come within this window


# --------------------------------------------------------------- oledd client

class OledClient:
    """Line-protocol client of the oledd panel daemon.

    Reconnects lazily: if oledd restarts, the next frame re-establishes
    the connection and repaints, so neither daemon depends on start
    order.
    """

    def __init__(self, path: str = DEFAULT_OLED_SOCKET):
        self._path = path
        self._sock: socket.socket | None = None

    def _connect(self) -> None:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect(self._path)
        self._sock = s

    def send_frame(self, tag: str, rows: list[str],
                   chip: str | None, chip_inverted: bool) -> bool:
        lines = [f"TAG {tag}"]
        for i in range(3):
            lines.append(f"ROW {i + 1} {rows[i] if i < len(rows) else ''}")
        if chip:
            lines.append(f"CHIP {chip} {1 if chip_inverted else 0}")
        else:
            lines.append("CHIP OFF")
        lines.append("FLUSH")
        payload = ("\n".join(lines) + "\n").encode("ascii", "replace")

        for attempt in (0, 1):
            try:
                if self._sock is None:
                    self._connect()
                self._sock.sendall(payload)
                return True
            except OSError:
                if self._sock is not None:
                    try:
                        self._sock.close()
                    except OSError:
                        pass
                    self._sock = None
                if attempt:
                    return False
        return False

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None


# --------------------------------------------------------------- item helpers

def _items_for(state: State) -> list:
    """Ordered selectable items for the current mode (params + mode sentinel)."""
    if state.mode == 1:     # ESTIM
        return list(ESTIM_PARAMS) + [_MODE_ITEM, _OFF_ITEM]
    return list(PARAMS) + [_MODE_ITEM, _OFF_ITEM]


def _value_for(state: State, name: str) -> int:
    return {
        "i":  state.intensity,
        "r":  state.ramp_ticks,
        "h":  state.hold_ticks,
        "ed": state.estim_dur_ticks,
        "ei": state.estim_ipi_ticks,
        "ld": state.laser_dac,
        "sd": state.estim_dac,
    }[name]


def _set_for(client: HatClient, name: str):
    return {
        "i":  client.set_intensity,
        "r":  client.set_ramp,
        "h":  client.set_hold,
        "ed": client.set_estim_dur,
        "ei": client.set_estim_ipi,
        "ld": client.set_laser_dac,
        "sd": client.set_estim_dac,
    }[name]


_FMT = {
    "i":  lambda v: f"{v}/320",
    "r":  lambda v: f"{v}({v/100:.0f}ms)",
    "h":  lambda v: f"{v}({v/100:.0f}ms)",
    "ed": lambda v: f"{v * 10}us",
    "ei": lambda v: f"{v * 10}us",
    "ld": lambda v: f"{proto.laser_dac_to_ma(v):.0f}mA",
    "sd": lambda v: f"{proto.estim_dac_to_ua(v):.0f}uA",
}


# --------------------------------------------------------------- render

def compose(state: State, selected: int, off_armed: bool = False,
            shutting_down: bool = False) -> tuple[str, list[str], str, bool]:
    """Build (tag, rows, chip_label, chip_inverted) for the oledd frame."""
    mode_tag = "E" if state.mode == 1 else "L"
    tag = f"LASERHAT[{mode_tag}]"
    if shutting_down:
        return tag, ["SHUTTING DOWN", "wait for blank +", "green LED off"], "OFF", True

    # 3-row scrolling window over selectable items.
    items = _items_for(state)
    n_vis = 3
    win_start = max(0, min(selected, len(items) - n_vis))
    visible = items[win_start:win_start + n_vis]

    rows = []
    for row_i, item in enumerate(visible):
        abs_i = win_start + row_i
        prefix = ">" if abs_i == selected else " "
        if item is _MODE_ITEM:
            mode_str = "ESTIM" if state.mode == 1 else "LASER"
            rows.append(f"{prefix}[mode:{mode_str}]")
        elif item is _OFF_ITEM:
            rows.append(f"{prefix}[off] roll again" if off_armed
                        else f"{prefix}[off] shutdown")
        else:
            text = f"{prefix}{item.name}:{_FMT[item.name](_value_for(state, item.name))}"
            if item.name == "sd" and not state.estim_ready:
                text += "!"        # module DAC not programmed yet (no ack)
            rows.append(text)

    if state.fault_latched:
        chip, inverted = "FAULT", True
    elif state.phase == "T":
        chip, inverted = "TRIG", True
    else:
        chip, inverted = "WAIT", False
    return tag, rows, chip, inverted


def render(panel: OledClient, state: State, selected: int,
           off_armed: bool = False, shutting_down: bool = False) -> None:
    tag, rows, chip, inverted = compose(state, selected, off_armed, shutting_down)
    if not panel.send_frame(tag, rows, chip, inverted):
        print("WARNING: oledd not reachable; will retry", file=sys.stderr)


# --------------------------------------------------------------- main loop

def main() -> int:
    sock = os.environ.get("LASERHAT_SOCK", DEFAULT_SOCKET)
    oled_sock = os.environ.get("LASERHAT_OLED_SOCK", DEFAULT_OLED_SOCKET)

    ui = {"selected": 0, "last_press": 0.0,
          "off_armed_at": 0.0, "off_dir": 0, "shutting_down": False}
    ui_lock = threading.Lock()

    def handle_button(edges: int, client: HatClient) -> None:
        st = client.get_state()
        items = (_items_for(st) if st is not None
                 else list(PARAMS) + [_MODE_ITEM, _OFF_ITEM])

        if edges & B2 and st is not None and st.fault_latched:
            client.clear_fault()        # wheel push acknowledges a module fault

        with ui_lock:
            ui["last_press"] = time.monotonic()
            if ui["shutting_down"]:
                return
            if edges & (B1 | B2):
                ui["off_armed_at"] = 0.0        # leaving the row disarms it
            if edges & B1:
                ui["selected"] = 0
            if edges & B2:
                ui["selected"] = (ui["selected"] + 1) % len(items)
            # Clamp in case mode just switched and shrunk the item list.
            selected = min(ui["selected"], len(items) - 1)
            ui["selected"] = selected

        direction = (-1 if edges & B3 else 0) + (1 if edges & B4 else 0)
        if direction and items[selected] is _OFF_ITEM:
            now = time.monotonic()
            with ui_lock:
                armed = (ui["off_armed_at"] and
                         now - ui["off_armed_at"] < OFF_ARM_S and
                         ui["off_dir"] == direction)
                if armed:
                    ui["off_armed_at"] = 0.0
                    ui["shutting_down"] = power.request("poweroff")
                    if not ui["shutting_down"]:
                        print("shutdown request failed (is laserhat-power.path "
                              "installed?)", file=sys.stderr)
                elif ui["off_armed_at"] and ui["off_dir"] != direction:
                    ui["off_armed_at"] = 0.0    # opposite roll cancels
                else:
                    ui["off_armed_at"] = now
                    ui["off_dir"] = direction
            return
        if direction and st is not None:
            item = items[selected]
            if item is _MODE_ITEM:
                # B4 = switch to ESTIM, B3 = switch to LASER.
                if edges & B4:
                    client.set_mode("estim")
                elif edges & B3:
                    client.set_mode("laser")
            else:
                cur = _value_for(st, item.name)
                new = max(item.minimum, min(item.maximum, cur + direction * item.step))
                if new != cur:
                    _set_for(client, item.name)(new)

    def on_update(msg: dict) -> None:
        if msg.get("type") == "event" and msg.get("event") == "button":
            handle_button(int(msg.get("edges", 0)), client)

    print(f"connecting to broker at {sock} …", file=sys.stderr)
    client = HatClient(sock, on_update=on_update)

    print(f"connecting to oledd at {oled_sock} …", file=sys.stderr)
    panel = OledClient(oled_sock)

    # Wait for the MCU indefinitely rather than exiting: a blank board (or
    # one mid-flash) would otherwise crash-loop this unit, and a unit caught
    # between restarts isn't brought back by laserhat-flash.  oledd keeps
    # showing its boot screen meanwhile.
    warn_at = time.monotonic() + 5.0
    state = client.get_state()
    while state is None:
        if warn_at and time.monotonic() >= warn_at:
            print("waiting for the MCU (is it flashed and powered? "
                  "sudo laserhat-flash)", file=sys.stderr)
            warn_at = 0.0
        time.sleep(0.05)
        state = client.get_state()

    with ui_lock:
        selected = ui["selected"]
    render(panel, state, selected)

    def ui_flags():
        """(off_armed, shutting_down) — the arm expires on its own."""
        with ui_lock:
            armed = bool(ui["off_armed_at"] and
                         time.monotonic() - ui["off_armed_at"] < OFF_ARM_S)
            if not armed:
                ui["off_armed_at"] = 0.0
            return armed, ui["shutting_down"]

    def paint_key(st: State, sel: int):
        return (st.intensity, st.ramp_ticks, st.hold_ticks, st.phase, sel,
                st.mode, st.estim_dur_ticks, st.estim_ipi_ticks,
                st.laser_dac, st.estim_dac, st.module) + ui_flags()

    last_painted_key = paint_key(state, selected)

    while True:
        now = time.monotonic()
        state = client.get_state()

        # Clamp selected to the current item list length (handles mode switch).
        if state is not None:
            items = _items_for(state)
            with ui_lock:
                if ui["selected"] >= len(items):
                    ui["selected"] = len(items) - 1
                selected = ui["selected"]
                last_press_at = ui["last_press"]
        else:
            with ui_lock:
                selected = ui["selected"]
                last_press_at = ui["last_press"]

        if state is None:
            time.sleep(POLL_INTERVAL)
            continue

        key = paint_key(state, selected)
        if key != last_painted_key and (now - last_press_at) >= SETTLE_GAP:
            off_armed, shutting_down = ui_flags()
            render(panel, state, selected, off_armed, shutting_down)
            last_painted_key = key

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(130)
