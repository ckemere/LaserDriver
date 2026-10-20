# LaserHAT Pi-side

Code that runs on the Raspberry Pi (target: **Raspberry Pi 4**). A
**broker daemon owns the serial port** (`/dev/ttyS0`) and the GUIs are
clients of it over a Unix socket, so the OLED GUI and the web GUI run at
the same time.  The OLED panel itself
is owned by a small **compiled daemon** (`oledd.c`, in the style of
[pioled-ip](https://github.com/ckemere/pioled-ip)) so the display works
from first boot and needs no Python graphics stack.

**Network triggers:** the broker is `laserhat-brokerd` (`brokerd/`, C), a
drop-in replacement for `broker.py` (same UART protocol and JSON socket)
that adds a low-latency UDP trigger listener on the wired port
(`192.168.17.10:17017`) for the remote experiment machine; see
[`brokerd/README.md`](brokerd/README.md). `broker.py` is still shipped as
a fallback.

```
                 /dev/ttyS0 (binary protocol)
   MSPM0  <───────────────────────────────>  broker.py ── /run/laserhat/broker.sock
                                                  │              │ (newline-JSON, pub/sub)
                                          owns PiTrigger    ┌─────┴─────┐
                                          (GPIO 26)      oled_gui.py  web_app.py
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
| `brokerd/` | **The daemon (C):** owns `/dev/ttyS0` + the GPIO trigger, mirrors MCU state, serves clients (pub/sub), UDP trigger listener. |
| `broker.py` | Python original of the daemon (no UDP triggers); shipped as a fallback. |
| `udp_trigger.py` | Network trigger sender (library + latency CLI) for the experiment machine. |
| `hat_client.py` | `HatClient` — what the GUIs use to talk to the broker (cached state + update callback). |
| `params.py` | Shared knob step sizes / ranges (OLED + web read this). |
| `oledd.c` | Compiled SSD1305 panel daemon: owns I2C + the display, draws the header (IPs + heartbeat), serves a tiny text protocol on a Unix socket. |
| `oled_gui.py` | OLED GUI daemon (broker client; sends rows to `oledd`). |
| `web_app.py` | Flask web GUI (broker client). |
| `pi_trigger.py` | `PiTrigger` — gpiozero driver for GPIO 26 → MCU PA27 (Rev 2 HAT), used by `broker.py` (brokerd drives the pin directly via `/dev/gpiomem`). |
| `laserhat-flash` | Flashes the packaged MCU firmware over SWD (`sudo`; manual). |
| `power_cycle.py` | Power-cycles the MCU for flashing (called by `laserhat-flash` and the firmware Makefile). |
| `fake_mcu.py` | PTY that speaks the protocol, for off-hardware testing. |
| `network/laserhat-eth0.nmconnection` | Static wired IP (192.168.17.10/24, no gateway). |
| `packaging/build-deb.sh` | Builds `laserhat_<ver>_<arch>.deb` (cross-compiles `oledd` and `brokerd`, builds the MCU firmware). |
| `packaging/inject-laserhat.sh` | Bakes the package into a flashed SD card / .img. |

## Services (`systemd/`)

| Unit | Runs | Notes |
|---|---|---|
| `laserhat-oledd.service` | `oledd` (C) | Owns the panel; starts at boot with no dependencies, shows hostname + IPs immediately. |
| `laserhat-broker.service` | `laserhat-brokerd` (C) | Owns the UART + trigger GPIO; UDP triggers on `192.168.17.10:17017`; `RuntimeDirectory=laserhat` creates `/run/laserhat`. |
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

**New board: flash the MCU first.** Boards arrive blank. The package
ships the firmware built from the same commit as the broker, and nothing
flashes it automatically. With the **laser unplugged**:

```bash
sudo laserhat-flash        # stops/restarts the broker + GUIs around the flash
```

Re-run it after upgrading the package so the firmware and broker stay
matched (`/usr/lib/laserhat/firmware/VERSION`).  The broker checks this
itself: once the MCU is alive it asks for the firmware's version
(`CMD_GET_VERSION`) and compares it with the VERSION file — the web page
shows a red "MCU firmware" banner and the OLED chip reads `FW!` until they
match (an MCU on a build older than v0.2.0-rc6, or a blank one, never
answers and counts as a mismatch).  `laserhat-flash` runs the same check
after writing and ends with `MCU firmware <version> ... OK`, or exits 3/4
with the reason.  Developers flashing their own
build can use `sudo laserhat-flash path/to/main.elf` (reported, not judged
against the package), or `make flash` from
`Firmware/`. After a `make flash`, restart the stack yourself so it
reconnects to the freshly booted MCU:

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
python3 /usr/lib/laserhat/laser_hat.py current 1216          # laser DAC code (~100 mA)
python3 /usr/lib/laserhat/laser_hat.py mode estim            # or: laser
python3 /usr/lib/laserhat/laser_hat.py estim-current 820     # e-stim DAC code (~100 µA)
python3 /usr/lib/laserhat/laser_hat.py clear-fault
python3 /usr/lib/laserhat/laser_hat.py trigger
python3 /usr/lib/laserhat/laser_hat.py watch                 # print frames, Ctrl-C
sudo systemctl start laserhat-broker.service
```

**Modules.** With the laser module in J8/J9 the laser rows are intensity /
ramp / hold / **current** (DAC code; the GUIs show mA; it reaches the module only while a pulse runs) and the web page shows
the module's compliance rail and photodiode readings.  In e-stim mode the rows
are pulse dur / IPI / **amplitude** (DAC code; shown in µA); the amplitude is
written to the module's DAC between trains and the row shows `!` until the
module has acknowledged it.  A FAULT_n edge from the module locks the outputs
and shows **FAULT** on the OLED chip and the web header; the wheel push or the
web "clear fault" button clears it.

### buttons

The OLED bonnet has no onboard buttons; these are the Rev 2 HAT's edge
controls, reported by the MCU over the broker (`EVT_BUTTON` bits):

```
         +--------------------------+
 wheel   |                          |  B5 FIRE (SW9, east edge):
 (SW7)  B3/B4 roll : -/+ value      |     fires a pulse (firmware, on press)
   west  B2 push   : next row       |
   edge           (clears a fault)  |
   edge  |                          |
         +--------------------------+
          B1 BACK (SW8, south edge): back to the first row
```

Bit 5 of the mask is the BSL switch SW6 (bring-up only; it is a reset-time
switch for the ROM bootloader and does nothing while the firmware runs).

Step sizes and ranges live in `params.py` (shared with the web UI).

### shutting down

Cutting 5 V while Linux is writing corrupts the SD card, and a Pi fed
through the HAT's USB-C goes down with every HAT power cycle.  Halt first:

- **OLED:** push the wheel to the last row, `[off] shutdown`; roll once
  (the row reads `[off] roll again`) and roll the same way again within
  5 s.  The other direction, BACK or waiting cancels.
- **Web:** the "shut down" / "reboot" buttons in the *system* card (with a
  confirm).  `POST /api/power {"action": "poweroff"|"reboot"}` for scripts.
- **Shell:** `sudo poweroff`.

The display shows SHUTTING DOWN, then goes blank when oledd stops; wait
for the Pi's green ACT LED to stop (it blinks ten times, then stays off)
before unplugging.  The GUIs run as the unprivileged `laserhat` user, so
they only drop a request file in `/run/laserhat/`; the root-owned
`laserhat-power.path` unit sees it and runs `systemctl poweroff` /
`reboot` (`power.py`, `laserhat-power`).  For bench work on the modules,
power the Pi from its own supply so the HAT can be cycled on its own.

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

(Rev 2 HAT: GPIO 26 → MCU PA27 is the fast trigger; GPIO 18 → MCU power-enable
and GPIO 23 → NRST for flashing; GPIO 24/25 = SWCLK/SWDIO; GPIO 14/15 = the
MCU's UART1 — all on the broker/firmware side, not the panel.)
