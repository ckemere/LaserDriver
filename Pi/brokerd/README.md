# laserhat-brokerd

The LaserHAT broker, in C. It replaces `Pi/broker.py` without changing
anything the GUIs can see. It uses the same UART protocol, the same
newline-JSON socket and the same trigger line. It also adds the
**low-latency network trigger path**: a remote experiment machine sends a UDP
datagram, and the broker raises the trigger line.

```
 experiment machine                      Raspberry Pi 4                        HAT
 ──────────────────     UDP :17017   ┌──────────────────────────────┐
 udp_trigger.py / your code ───────▶ │ trigger thread (SCHED_FIFO,  │ GPIO 24  MSPM0 PA19
        ◀─────── ACK (after edge) ── │ pinned CPU) ── GPSET0 store ─┼────────▶ edge ISR ─▶ pulse
                                     │                              │          (≤10 µs tick)
                                     │ UART reader / poller /       │ ttyS0
 oled_gui.py, web_app.py ──JSON────▶ │ JSON clients (normal prio)   │◀───────▶ status / events
   (Unix socket, unchanged)          └──────────────────────────────┘
```

The experiment logic (what to stimulate and when) runs on the remote machine.
The Pi only gets a trigger from the network to the laser as fast and as
predictably as it can.

## Build and run

`Pi/packaging/build-deb.sh` cross-compiles it statically to
`/usr/bin/laserhat-brokerd`, and `laserhat-broker.service` runs it with
`--udp 192.168.17.10:17017 --rt-prio 80 --cpu 3`. CI also builds it
natively with `-Werror` (`make -C Pi/brokerd`) before running the tests.

Options (`--help`):

| Option | Default | |
|---|---|---|
| `--device PATH` | `/dev/ttyS0` | MCU UART |
| `--socket PATH` | `/run/laserhat/broker.sock` | JSON socket for the GUIs |
| `--gpio gpiomem\|sim\|none` | `gpiomem` | `sim` = pretend (tests); `none` = no trigger line |
| `--gpio-pin N` | 24 | BCM pin wired to PA19 |
| `--pulse-us N` | 20 | trigger line high time. The MCU latches the edge, so this is not a timing parameter |
| `--udp IPV4:PORT` | off | enable the UDP trigger listener. Binds even if the address isn't up yet (`IP_FREEBIND`) |
| `--udp-allow IP` | any | accept triggers only from this IPv4 source |
| `--rt-prio N` | 0 | SCHED_FIFO priority for the trigger thread (also `mlockall`s) |
| `--cpu N` | — | pin the trigger thread to CPU N |
| `--spin` | off | busy-poll the socket (see tuning) |
| `--control-tcp IPV4:PORT` | off | also serve the JSON protocol over TCP (for remote parameter changes) |

## UDP trigger protocol

The full definition is in `udp_trigger.h`, mirrored in `Pi/udp_trigger.py`. All fields are
little-endian.

**Request** (20 B): `"LHTR" | ver=1 | type | flags=0 | seq u32 | client_ts u64`.
The type is `0x01` TRIGGER or `0x02` PING. PING is answered by the trigger thread
but never touches the GPIO, so you can measure latency with the laser idle.

**Reply** (36 B, sent *after* the edge):
`"LHTR" | ver | 0x81 | status | flags | seq | client_ts | rx_ns | edge_ns`

- `status`: `fired`, `duplicate`, `pong`, `bad_version`, `bad_type`, `no_gpio`.
- `rx_ns` is the kernel's receive timestamp and `edge_ns` is the time the line went
  high, both from the Pi's `CLOCK_REALTIME`. **`edge_ns - rx_ns` is the in-Pi
  latency.**
- `flags`:
  - `MCU_BUSY`: the broker's last status said the MCU was mid-pulse. **The
    firmware ignores triggers while a pulse is running.**
  - `MCU_DOWN`: the broker has had no MCU status for 1.5 s.
  - `GPIO_SIM`: the GPIO is simulated.
  - `RX_TS_USER`: no kernel timestamp was available.

**Delivery is at-most-once.** A trigger that arrives late is worse than one
that never arrives, so nothing is retransmitted automatically. The ACK tells
the sender whether the trigger fired, and the sender decides what to do about a
miss. A retry reuses the `seq`. The broker remembers the last fired `(peer, seq)`
for 1 s and answers `duplicate`, echoing the original `edge_ns`, instead of
firing again. `udp_trigger.TriggerClient` starts at a random `seq` so a
restarted sender can't hit that window.

The ACK confirms that the Pi raised the line. It doesn't prove that the laser
fired. For that, watch the `pulse_start` events on the JSON socket (they carry
the MCU tick), or put a scope on the output.

## JSON socket

The JSON socket works exactly like `broker.py`'s (see that file's docstring) with one
addition: `{"cmd": "stats"}` returns the trigger counters (`udp_rx`,
`udp_fired`, `udp_duplicate`, `udp_denied`, `latency_last_ns`,
`latency_max_ns`, …).

## Latency tuning checklist (Pi 4)

The code path from packet to edge is short. What's left is mostly kernel and
hardware behavior. Measure before and after each step with
`python3 Pi/udp_trigger.py <pi> ping -n 10000` (round trip) and
`… fire -n 200 --interval 0.5` (in-Pi `rx->edge`). Confirm end-to-end timing
with a scope on the network trigger source and GPIO 24.

1. **Isolate a core for the trigger thread.** Append `isolcpus=3` to
   `/boot/firmware/cmdline.txt`. The unit already runs `--cpu 3 --rt-prio 80`.
2. **Route the NIC's interrupts to that core.** Find the `eth0` lines in
   `/proc/interrupts`, then run `echo 8 | sudo tee /proc/irq/<n>/smp_affinity` for each. `8` is the
   mask for CPU 3. Receive processing and the trigger thread then share a
   warm cache and never wait on another core.
3. **Turn off interrupt coalescing and Energy-Efficient Ethernet.** Check
   `ethtool -c eth0` and minimise it, e.g. `sudo ethtool -C eth0 rx-frames 1`.
   Also run `sudo ethtool --set-eee eth0 eee off`, because EEE's link sleep adds wake-up latency to
   the first packet after idle.
4. **Fix the CPU clock:** `echo performance | sudo tee
   /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`.
5. **Use a direct cable or a dedicated switch.** Don't share the link with bulk
   traffic. The unit binds the static wired address (`192.168.17.10`), which
   ordinary wifi clients can't reach. Linux still accepts packets for that
   address on any interface, so for a hard guarantee add
   `--udp-allow <rig IP>`.
6. **Optional: `--spin`.** Busy-polling removes the scheduler wake-up entirely but uses 100%
   of the isolated core. With `--rt-prio` it also runs into the kernel's
   real-time throttling (by default, real-time tasks are limited to 95% of each second), so either set
   `kernel.sched_rt_runtime_us=-1` or run the spinner without `--rt-prio`.
   Use it only on an isolated core.
7. **Optional: a PREEMPT_RT kernel.** Try this only if the worst-case latency is still too high after the steps
   above.

Settings from steps 2–4 don't survive a reboot. Put them in a oneshot unit once you've
settled on values.

## Tests (off-hardware)

```bash
python3 -m pytest Pi/tests/    # test_integration + test_web run against both brokers;
                               # test_brokerd covers UDP + JSON edge cases
```
