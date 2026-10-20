"""LaserHat binary UART transport (host side).

Speaks the magic-word framed binary protocol the MSPM0 firmware uses on
/dev/ttyS0 (115200 8N1).  See protocol.py for the wire format and
Firmware/protocol.h for the firmware mirror.

This module is the *single UART owner*: only the broker (broker.py)
instantiates LaserUART.  GUIs talk to the broker over its Unix socket
(see hat_client.py), never to the serial port directly.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

import serial

import protocol as proto


DEFAULT_DEVICE = "/dev/ttyS0"
DEFAULT_BAUD = 115200


@dataclass
class State:
    intensity: int          # 1..320
    ramp_ticks: int         # 100 kHz ticks
    hold_ticks: int
    button_mask: int        # 6 bits, bit n = button n+1 pressed (see protocol.py)
    phase: str              # 'W' (waiting) or 'T' (triggered)
    tick: int               # MSPM0 isr_ticks at the time of query
    mode: int = 0           # 0 = LASER, 1 = ESTIM
    estim_dur_ticks: int = proto.ESTIM_TICKS_MIN   # 100 kHz ticks (10–10000 µs)
    estim_ipi_ticks: int = proto.ESTIM_TICKS_MIN
    laser_dac: int = proto.LASER_DAC_DEFAULT       # DAC0 code (laser module current)
    estim_dac: int = proto.ESTIM_DAC_DEFAULT       # DAC60501 code (e-stim amplitude)
    module: int = 0         # MODULE_* flag bits (see protocol.py)
    adc_pd: int = 0         # photodiode ADC code (laser mode)
    adc_comp: int = 0       # compliance-rail ADC code (laser mode)
    # Firmware identity, probed once by the broker (CMD_GET_VERSION):
    #   fw_version  the MCU's build string, None = not probed yet / no reply
    #   fw_proto    its wire-protocol number (protocol.PROTO_VERSION expected)
    #   fw_expected the package's firmware version (VERSION file), None = unknown
    #   fw_ok       None until probed; False = no reply (firmware older than
    #               protocol 2, or blank), wrong proto, or != fw_expected
    fw_version: Optional[str] = None
    fw_proto: Optional[int] = None
    fw_expected: Optional[str] = None
    fw_ok: Optional[bool] = None

    def button(self, n: int) -> bool:
        """True if button n (1..6) is pressed."""
        return bool(self.button_mask & (1 << (n - 1)))

    @property
    def fault_latched(self) -> bool:
        return bool(self.module & proto.MODULE_FAULT_LATCHED)

    @property
    def fault_n_low(self) -> bool:
        return bool(self.module & proto.MODULE_FAULT_N_LOW)

    @property
    def estim_ready(self) -> bool:
        return bool(self.module & proto.MODULE_ESTIM_READY)

    @property
    def laser_ma(self) -> float:
        return proto.laser_dac_to_ma(self.laser_dac)

    @property
    def estim_ua(self) -> float:
        return proto.estim_dac_to_ua(self.estim_dac)

    @property
    def compliance_v(self) -> float:
        return proto.comp_to_volts(self.adc_comp)

    @classmethod
    def from_status_payload(cls, payload: bytes) -> "State":
        return cls(**proto.unpack_status(payload))

    @property
    def fw_label(self) -> str:
        """Human-readable firmware identity for GUIs."""
        if self.fw_version:
            return self.fw_version
        if self.fw_ok is False:
            return "unknown (older than 0.2.0-rc6, or blank)"
        return "probing"


class LaserUART:
    """Low-level binary transport over the serial port.

    Not thread-safe for concurrent senders; the broker serialises sends
    behind its own command lock and runs a single reader loop.
    """

    def __init__(
        self,
        device: str = DEFAULT_DEVICE,
        baud: int = DEFAULT_BAUD,
        timeout: float = 0.1,
    ):
        self._ser = serial.Serial(device, baud, timeout=timeout)
        self._dec = proto.StreamDecoder()
        self._write_lock = threading.Lock()
        self._ser.reset_input_buffer()

    def close(self) -> None:
        self._ser.close()

    def __enter__(self) -> "LaserUART":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def send(self, msg_type: int, payload: bytes = b"") -> None:
        """Encode and write one command frame."""
        wire = proto.encode_frame(msg_type, payload)
        with self._write_lock:
            self._ser.write(wire)
            self._ser.flush()

    def read_frames(self) -> Iterator[Tuple[int, bytes]]:
        """Block up to the serial timeout for bytes, yield decoded frames.

        Yields nothing on a timeout with no data; callers loop on it.
        """
        data = self._ser.read(256)
        if data:
            yield from self._dec.feed(data)


# --- tiny CLI for smoke-testing the raw link (no broker) ----------------
def _main() -> int:
    import argparse
    import time

    p = argparse.ArgumentParser(description="LaserHat binary UART smoke tool")
    p.add_argument("--device", default=DEFAULT_DEVICE)
    p.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("query")
    sub.add_parser("trigger")
    sub.add_parser("watch", help="print every frame until Ctrl-C")
    sp = sub.add_parser("config", help="set intensity ramp hold at once")
    sp.add_argument("intensity", type=int)
    sp.add_argument("ramp", type=int)
    sp.add_argument("hold", type=int)
    sp = sub.add_parser("mode", help="switch module mode")
    sp.add_argument("mode", choices=["laser", "estim"])
    sp = sub.add_parser("current", help="laser module current setpoint (DAC code, ~0.082 mA each)")
    sp.add_argument("dac", type=int)
    sp = sub.add_parser("estim-current", help="e-stim module amplitude (DAC code, ~0.12 µA each)")
    sp.add_argument("dac", type=int)
    sub.add_parser("clear-fault", help="clear a latched module fault")
    sub.add_parser("version", help="firmware protocol number + build version")

    args = p.parse_args()
    uart = LaserUART(args.device, args.baud)

    def wait_status(deadline=1.0):
        end = time.monotonic() + deadline
        while time.monotonic() < end:
            for mtype, payload in uart.read_frames():
                if mtype == proto.RSP_STATUS:
                    return State.from_status_payload(payload)
        return None

    if args.cmd == "query":
        uart.send(proto.CMD_QUERY)
        print(wait_status() or "no response")
    elif args.cmd == "trigger":
        uart.send(proto.CMD_TRIGGER)
        print(wait_status() or "no response")    # status echo is the ack
    elif args.cmd == "config":
        r = proto.avoid_magic(args.ramp)
        h = proto.avoid_magic(args.hold)
        uart.send(proto.CMD_CONFIG, proto._CONFIG.pack(args.intensity, r, h))
        print(wait_status() or "no response")
    elif args.cmd == "mode":
        uart.send(proto.CMD_SET_MODE, bytes([proto.MODE_ESTIM if args.mode == "estim"
                                             else proto.MODE_LASER]))
        print(wait_status() or "no response")
    elif args.cmd == "current":
        uart.send(proto.CMD_LASER_CURRENT, proto._DAC.pack(args.dac))
        print(wait_status() or "no response")
    elif args.cmd == "estim-current":
        uart.send(proto.CMD_ESTIM_CURRENT, proto._DAC.pack(args.dac))
        print(wait_status() or "no response")
    elif args.cmd == "clear-fault":
        uart.send(proto.CMD_CLEAR_FAULT)
        print(wait_status() or "no response")
    elif args.cmd == "version":
        uart.send(proto.CMD_GET_VERSION)
        end = time.monotonic() + 1.0
        reply = None
        while reply is None and time.monotonic() < end:
            for mtype, payload in uart.read_frames():
                if mtype == proto.RSP_VERSION:
                    reply = proto.unpack_version(payload)
                    break
        if reply is None:
            print("no response (firmware older than protocol 2, or no firmware)")
            return 1
        print(f"proto {reply[0]} (host {proto.PROTO_VERSION}) version {reply[1]}")
    elif args.cmd == "watch":
        names = {v: k for k, v in vars(proto).items()
                 if k.isupper() and isinstance(v, int)}
        try:
            while True:
                for mtype, payload in uart.read_frames():
                    print(names.get(mtype, hex(mtype)), payload.hex())
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
