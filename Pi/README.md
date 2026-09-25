# LaserHAT Pi-side

Code that runs on the Raspberry Pi (target: **Raspberry Pi 4**). A
**broker daemon owns the serial port** (`/dev/ttyS0`) and the GUIs are
clients of it over a Unix socket, so the OLED GUI and the web GUI run at
the same time.  The OLED panel itself
is owned by a small **compiled daemon** (`oledd.c`, in the style of
[pioled-ip](https://github.com/ckemere/pioled-ip)) so the display works
from first boot and needs no Python graphics stack.

**Network triggers:** `brokerd/` is a C drop-in replacement for
`broker.py` (same UART protocol and JSON socket) that adds a low-latency
UDP trigger listener for the remote experiment machine; see
[`brokerd/README.md`](brokerd/README.md). It is not packaged or enabled
yet — `laserhat-broker.service` still runs `broker.py`.

```
                 /dev/ttyS0 (binary protocol)
   MSPM0  <───────────────────────────────>  broker.py ── /run/laserhat/broker.sock
                                                  │              │ (newline-JSON, pub/sub)
                                          owns PiTrigger    ┌─────┴─────┐
                                          (GPIO 24)      oled_gui.py  web_app.py
                                                             │
                                          /run/laserhat-oled/oled.sock (text lines)
                                                             │
                                                          oledd (C) ── /dev/i2c-1 ── SSD1305
```

**No pip, no venv.** The Python daemons use only the standard library
plus apt packages (`python3-serial`, `python3-flask`, `python3-gpiozero`,
`python3-lgpio`); the OLED stack (adafruit-blinka / Pillow) is replaced
by `oledd.c`.

**[PROVISIONING.md](PROVISIONING.md)** is the authoritative reference
for every change the deployment makes to a stock Raspberry Pi OS system
(package contents, services, network, boot config, masked units) and
the rationale for each — keep it updated in the same commit as any
provisioning change.

## Networking

The Debian package fixes the **wired port at `192.168.17.10/24` with no
gateway** (NetworkManager keyfile `network/laserhat-eth0.nmconnection`) —
lab point-to-point style, so wifi keeps the default route and internet.
Wifi stays on DHCP.  The OLED header alternates between the mode tag,
`E:<wired ip>` and `W:<wifi ip>` (`WAITING` until an interface has an
address), with a 1 Hz heartbeat dot in the corner drawn by `oledd`
itself.  The web GUI binds `0.0.0.0:8080`, so it answers on both
addresses.

## Files

| File | Role |
|---|---|
| `protocol.py` | Binary wire protocol (magic framing, no CRC). Source of truth; mirror of `Firmware/protocol.h`. |
| `laser_hat.py` | `LaserUART` transport + `State` dataclass. Used by the broker; also a raw-link CLI. |
| `broker.py` | The daemon: owns `/dev/ttyS0` + the GPIO trigger, mirrors MCU state, serves clients (pub/sub). |
| `brokerd/` | C drop-in replacement for `broker.py` plus the UDP trigger listener (not yet packaged). |
| `udp_trigger.py` | Network trigger sender (library + latency CLI) for the experiment machine. |
| `hat_client.py` | `HatClient` — what the GUIs use to talk to the broker (cached state + update callback). |
| `params.py` | Shared knob step sizes / ranges (OLED + web read this). |
| `oledd.c` | Compiled SSD1305 panel daemon: owns I2C + the display, draws the header (IPs + heartbeat), serves a tiny text protocol on a Unix socket. |
| `oled_gui.py` | OLED GUI daemon (broker client; sends rows to `oledd`). |
| `web_app.py` | Flask web GUI (broker client). |
| `pi_trigger.py` | `PiTrigger` — gpiozero driver for GPIO 24 → MCU PA19, used by `broker.py` (brokerd drives the pin directly via `/dev/gpiomem`). |
| `power_cycle.py` | Power-cycles the MCU for `make flash` (called by the firmware Makefile). |
| `fake_mcu.py` | PTY that speaks the protocol, for off-hardware testing. |
| `network/laserhat-eth0.nmconnection` | Static wired IP (192.168.17.10/24, no gateway). |
| `packaging/build-deb.sh` | Builds `laserhat_<ver>_<arch>.deb` (cross-compiles `oledd`). |
| `packaging/inject-laserhat.sh` | Bakes the package into a flashed SD card / .img. |

## Services (`systemd/`)

| Unit | Runs | Notes |
|---|---|---|
| `laserhat-oledd.service` | `oledd` (C) | Owns the panel; starts at boot with no dependencies, shows hostname + IPs immediately. |
| `laserhat-broker.service` | `broker.py` | Owns the UART; `RuntimeDirectory=laserhat` creates `/run/laserhat`. |
| `oled-gui.service` | `oled_gui.py` | Broker client; sends body rows to `oledd`. |
| `laserhat-web.service` | `web_app.py` | Broker client; serves `http://192.168.17.10:8080/` (and the wifi address). |

All units run as the `laserhat` system user (created by the package
postinst) with `/usr/bin/python3` and `WorkingDirectory=/usr/lib/laserhat`
— no per-account paths to edit.

## Install

Three options, mirroring pioled-ip:

### Option A: Debian package on a running Pi

Grab `laserhat_<ver>_arm64.deb` from a GitHub release (or build it with
`Pi/packaging/build-deb.sh`), then:

```bash
sudo apt install ./laserhat_<ver>_arm64.deb   # pulls python3-* deps
sudo raspi-config nonint do_i2c 0             # enable I2C (OLED bonnet)
```

### Option B: bake into a flashed SD card / image

```bash
sudo ./inject-laserhat.sh /dev/sdX laserhat_<ver>_arm64.deb
```

Works on `.img` files too (loop-mounted automatically).  The display
works from the very first boot; the broker/GUIs come up once a one-shot
first-boot service has apt-installed the python3 dependencies (needs a
network route).

### Option C: golden image

Every tagged release includes ready-to-flash
`laserhat-raspios-lite-{arm64,armhf}.img.xz` — official Raspberry Pi OS
Lite with everything preinstalled, dependencies included (works fully
offline).  Point Raspberry Pi Imager at the release's `imager.json`
(Options → Content Repository) to get the full OS customisation flow
(hostname, wifi, user, SSH).

## CI

`.github/workflows/pi-deploy.yml`: every push runs the oledd render test
(framebuffer diffed against `tests/render-expected.txt`) and the Python
test suite; version tags (`git tag v1.0 && git push --tags`) publish the
debs, the inject script, and the golden images.

## Operating

**After flashing new firmware**, restart the stack so it reconnects to
the freshly-booted MCU:

```bash
sudo systemctl restart laserhat-broker.service oled-gui.service laserhat-web.service
```

(Use `restart`, not `enable --now` — only `restart` reloads changed code or
re-establishes the link.) Logs: `journalctl -u laserhat-broker.service -f`.

**Raw link / smoke tools** open `/dev/ttyS0` directly, so **stop the broker
first** (only one process may own the port):

```bash
sudo systemctl stop laserhat-broker.service
python3 /usr/lib/laserhat/laser_hat.py query
python3 /usr/lib/laserhat/laser_hat.py config 100 2000 500   # i r h
python3 /usr/lib/laserhat/laser_hat.py trigger
python3 /usr/lib/laserhat/laser_hat.py watch                 # print frames, Ctrl-C
sudo systemctl start laserhat-broker.service
```

### buttons

The OLED bonnet has no onboard buttons; these are LaserHAT's own,
reported by the MCU over the broker:

```
+------+
|  B1  |  trigger a pulse (firmware fires on release)
+------+
| OLED |   B2 : cycle selected parameter (i → r → h)
+------+   B3 / B4 : decrement / increment it
| B3 B4|
+------+
```

Step sizes and ranges live in `params.py` (shared with the web UI).

## Off-hardware testing

```bash
python3 -m pytest Pi/tests/       # codec + broker integration + web
gcc -O2 -Wall -Wextra -Werror -o render-test Pi/tests/render-test.c
./render-test | diff - Pi/tests/render-expected.txt
```

`fake_mcu.py` is a PTY that speaks the protocol; point the broker at it with
`--device <pts> --no-gpio --socket /tmp/lh.sock`.

## Wiring (OLED bonnet, Pi-only)

The Adafruit 4567 bonnet plugs onto the 40-pin header and talks I2C:

| Pi GPIO | Signal | | Pi GPIO | Signal |
|---|---|---|---|---|
| 2 (SDA) | `OLED_SDA` | | 4 | `OLED_RESET` |
| 3 (SCL) | `OLED_SCL` | | | |

SSD1305 at I2C address `0x3C`. Confirm with `i2cdetect -y 1`.

(GPIO 24 → MCU PA19 is the fast trigger; GPIO 23 → MCU power-enable for
flashing — both on the broker/firmware side, not the panel.)
