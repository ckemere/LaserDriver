#!/usr/bin/env python3
"""LaserHAT network trigger — sender side (runs on the experiment machine).

Python mirror of Pi/brokerd/udp_trigger.h; keep them in sync.  The broker
(laserhat-brokerd --udp HOST:PORT) raises Pi GPIO 24 -> MCU PA19 as soon
as a trigger datagram arrives, then ACKs.

Delivery is at-most-once: nothing is retransmitted automatically, because
a late pulse is worse than a missing one.  If an ACK doesn't come back in
time, *you* decide whether to retry; a retry reuses the seq, so the broker
answers DUPLICATE instead of firing twice.

Library:

    from udp_trigger import TriggerClient
    with TriggerClient("192.168.17.10") as t:
        ack = t.fire()                  # Ack, or None if no reply in time
        if ack and ack.status == "fired": ...

CLI:

    python3 udp_trigger.py HOST fire              # one pulse
    python3 udp_trigger.py HOST ping -n 1000      # latency, no laser
    python3 udp_trigger.py HOST fire -n 20 --interval 0.5
"""

from __future__ import annotations

import random
import socket
import struct
import time
from dataclasses import dataclass
from typing import Optional

MAGIC = 0x5254484C          # b"LHTR"
VERSION = 1
DEFAULT_PORT = 17017

TRIGGER = 0x01
PING = 0x02
ACK = 0x81

STATUS = {0: "fired", 1: "duplicate", 2: "pong", 3: "bad_version",
          4: "bad_type", 5: "no_gpio"}

F_MCU_BUSY = 0x01           # MCU was mid-pulse: it ignores this edge
F_MCU_DOWN = 0x02           # broker has no recent MCU status
F_GPIO_SIM = 0x04           # simulated GPIO (off-hardware testing)
F_RX_TS_USER = 0x08         # rx_ns is a userspace, not kernel, timestamp

_REQ = struct.Struct("<IBBHIQ")         # magic ver type flags seq client_ts
_REP = struct.Struct("<IBBBBIQQQ")      # ... status flags seq client_ts rx edge
assert _REQ.size == 20 and _REP.size == 36


@dataclass
class Ack:
    seq: int
    status: str
    flags: int
    client_ts: int      # echoed from the request
    rx_ns: int          # Pi CLOCK_REALTIME: datagram arrived (kernel stamp)
    edge_ns: int        # Pi CLOCK_REALTIME: GPIO went high (0 if not fired)
    rtt_ns: int         # sender-side round trip

    @property
    def pi_latency_ns(self) -> Optional[int]:
        """Time inside the Pi from packet arrival to GPIO edge."""
        if self.status != "fired":
            return None
        return self.edge_ns - self.rx_ns


def pack_request(msg_type: int, seq: int, client_ts: int = 0) -> bytes:
    return _REQ.pack(MAGIC, VERSION, msg_type, 0, seq & 0xFFFFFFFF,
                     client_ts & 0xFFFFFFFFFFFFFFFF)


def unpack_reply(data: bytes):
    if len(data) < _REP.size:
        return None
    magic, ver, mtype, status, flags, seq, cts, rx, edge = _REP.unpack_from(data)
    if magic != MAGIC or mtype != ACK:
        return None
    return seq, STATUS.get(status, str(status)), flags, cts, rx, edge


class TriggerClient:
    def __init__(self, host: str, port: int = DEFAULT_PORT):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.connect((host, port))
        # Random start so a restarted sender never collides with the
        # broker's duplicate-suppression memory of our previous run.
        self._seq = random.getrandbits(32)

    def next_seq(self) -> int:
        self._seq = (self._seq + 1) & 0xFFFFFFFF
        return self._seq

    def _request(self, msg_type: int, seq: int, timeout: float) -> Optional[Ack]:
        t0 = time.monotonic_ns()
        self._sock.send(pack_request(msg_type, seq, t0))
        deadline = t0 + int(timeout * 1e9)
        while True:
            left = (deadline - time.monotonic_ns()) / 1e9
            if left <= 0:
                return None
            self._sock.settimeout(left)
            try:
                data = self._sock.recv(64)
            except socket.timeout:
                return None
            except ConnectionRefusedError:      # ICMP port unreachable
                return None
            r = unpack_reply(data)
            if r is None or r[0] != seq:
                continue                        # stale reply to an older seq
            rseq, status, flags, cts, rx, edge = r
            return Ack(rseq, status, flags, cts, rx, edge,
                       time.monotonic_ns() - t0)

    def fire(self, timeout: float = 0.005, seq: Optional[int] = None) -> Optional[Ack]:
        """Send one trigger and wait up to `timeout` s for its ACK.

        Pass the seq of an unacknowledged trigger to retry it without
        risking a double pulse (the broker replies "duplicate")."""
        return self._request(TRIGGER, self.next_seq() if seq is None else seq,
                             timeout)

    def ping(self, timeout: float = 0.005) -> Optional[Ack]:
        """Round trip through the trigger thread without touching the GPIO."""
        return self._request(PING, self.next_seq(), timeout)

    def close(self) -> None:
        self._sock.close()

    def __enter__(self) -> "TriggerClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# --- CLI -------------------------------------------------------------------
def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


def _summary(name, ns):
    if not ns:
        return
    us = [x / 1000 for x in ns]
    print(f"  {name:<14} min {min(us):8.1f}  p50 {_pct(us, 50):8.1f}  "
          f"p99 {_pct(us, 99):8.1f}  max {max(us):8.1f}  us")


def _main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="LaserHAT UDP trigger sender")
    p.add_argument("host")
    p.add_argument("action", choices=["fire", "ping"])
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("-n", type=int, default=1, help="number of requests")
    p.add_argument("--interval", type=float, default=0.01,
                   help="seconds between requests (fire: allow for the pulse)")
    p.add_argument("--timeout", type=float, default=0.05)
    args = p.parse_args()

    rtt, pi_lat, lost, other = [], [], 0, {}
    with TriggerClient(args.host, args.port) as t:
        for k in range(args.n):
            ack = (t.fire if args.action == "fire" else t.ping)(args.timeout)
            if ack is None:
                lost += 1
            else:
                rtt.append(ack.rtt_ns)
                if ack.pi_latency_ns is not None:
                    pi_lat.append(ack.pi_latency_ns)
                key = ack.status + ("+busy" if ack.flags & F_MCU_BUSY else "")
                other[key] = other.get(key, 0) + 1
                if args.n == 1:
                    print(ack)
            if k + 1 < args.n:
                time.sleep(args.interval)

    print(f"{args.n} sent, {args.n - lost} acked, {lost} lost; {other}")
    _summary("round trip", rtt)
    _summary("in-Pi rx->edge", pi_lat)
    return 0 if lost == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_main())
