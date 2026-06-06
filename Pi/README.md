# LaserHAT Pi-side

Python that runs on the Raspberry Pi. A **broker daemon owns the serial
port** (`/dev/ttyS0`) and the GUIs are clients of it over a Unix socket, so
the eink GUI and the web GUI run at the same time.

```
                 /dev/ttyS0 (binary protocol)
   MSPM0  <───────────────────────────────>  broker.py ── /run/laserhat/broker.sock
                                                  │              │ (newline-JSON, pub/sub)
                                          owns PiTrigger    ┌─────┴─────┐
                                          (GPIO 24)      eink_gui.py  web_app.py
```

Clients publish commands up (`set` / `trigger` / `trigger_gpio`); the broker
broadcasts state + button/pulse events down. Only the broker touches the
UART; everything else talks to the broker.

## Files

| File | Role |
|---|---|
| `protocol.py` | Binary wire protocol (magic framing, no CRC). Source of truth; mirror of `Firmware/protocol.h`. |
| `laser_hat.py` | `LaserUART` transport + `State` dataclass. Used by the broker; also a raw-link CLI. |
| `broker.py` | The daemon: owns `/dev/ttyS0` + the GPIO trigger, mirrors MCU state, serves clients (pub/sub). |
| `hat_client.py` | `HatClient` — what the GUIs use to talk to the broker (cached state + update callback). |
| `params.py` | Shared knob step sizes / ranges (eink + web read this). |
| `eink_panel.py` | SSD1680 / GDEY0213B74 panel driver (spidev + gpiozero + Pillow). |
| `eink_gui.py` | eink GUI daemon (broker client). |
| `web_app.py` | Flask web GUI (broker client). |
| `pi_trigger.py` | `PiTrigger` — drives GPIO 24 → MCU PA19 for the fast (~50–100 µs) trigger. Owned by the broker. |
| `power_cycle.py` | Power-cycles the MCU for `make flash` (called by the firmware Makefile). |
| `fake_mcu.py` | PTY that speaks the protocol, for off-hardware testing. |

## Services (`systemd/`)

| Unit | Runs | Notes |
|---|---|---|
| `laserhat-broker.service` | `broker.py` | Owns the UART; `RuntimeDirectory=laserhat` creates `/run/laserhat`. Start first. |
| `eink-gui.service` | `eink_gui.py` | Broker client; `Requires=` the broker. |
| `laserhat-web.service` | `web_app.py` | Broker client; `Requires=` the broker. Serves `http://<pi>:8080/`. |

The GUI units `Requires=laserhat-broker.service`, so the broker is pulled up
first and all three run together. Each unit assumes the `kemerelab` account
and `~/.venvs/laserhat` — edit `User=` / `Group=` / `WorkingDirectory=` /
`ExecStart=` if yours differ. All three honour `LASERHAT_SOCK` (default
`/run/laserhat/broker.sock`).

## Install (one-time)

```bash
sudo apt install python3-venv python3-pil python3-spidev python3-gpiozero python3-lgpio
python3 -m venv --system-site-packages ~/.venvs/laserhat
~/.venvs/laserhat/bin/pip install -r ~/Code/LaserDriver/Pi/requirements.txt
sudo raspi-config nonint do_spi 0          # enable SPI (eink panel)
```

`--system-site-packages` lets the venv see the apt-installed `gpiozero` /
Pillow / spidev / **lgpio** (without `python3-lgpio`, gpiozero falls back to
the broken `RPi.GPIO` on recent Pi OS). You also need to be in the `spi` and
`gpio` groups (default on Pi OS).

Deploy the services:

```bash
sudo cp ~/Code/LaserDriver/Pi/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now laserhat-broker.service eink-gui.service laserhat-web.service
```

## Operating

**After flashing new firmware**, restart all three so they reconnect to the
freshly-booted MCU:

```bash
sudo systemctl restart laserhat-broker.service eink-gui.service laserhat-web.service
```

(Use `restart`, not `enable --now` — only `restart` reloads changed code or
re-establishes the link.) Logs: `journalctl -u laserhat-broker.service -f`.

**Raw link / smoke tools** open `/dev/ttyS0` directly, so **stop the broker
first** (only one process may own the port):

```bash
sudo systemctl stop laserhat-broker.service
~/.venvs/laserhat/bin/python laser_hat.py query
~/.venvs/laserhat/bin/python laser_hat.py config 100 2000 500   # i r h
~/.venvs/laserhat/bin/python laser_hat.py trigger
~/.venvs/laserhat/bin/python laser_hat.py watch                 # print frames, Ctrl-C
sudo systemctl start laserhat-broker.service
```

### eink buttons

```
+------+
|  B1  |  trigger a pulse (firmware fires on release)
+------+
| EINK |   B2 : cycle selected parameter (i → r → h)
+------+   B3 / B4 : decrement / increment it
| B3 B4|
+------+
```

Step sizes and ranges live in `params.py` (shared with the web UI).

## Off-hardware testing

```bash
~/.venvs/laserhat/bin/python -m pytest Pi/tests/    # codec + broker integration + web
```

`fake_mcu.py` is a PTY that speaks the protocol; point the broker at it with
`--device <pts> --no-gpio --socket /tmp/lh.sock`. The C↔Python framing/struct
agreement is checked by `Firmware/host_tools/proto_crosscheck.py`.

## Wiring (eink panel, Pi-only)

Per `LaserHAT/gpio_design.md`:

| Pi GPIO | Signal | | Pi GPIO | Signal |
|---|---|---|---|---|
| 8 (CE0) | `EINK_CS` | | 17 | `EINK_BUSY` |
| 9 (MISO) | `EINK_CIPO` | | 22 | `EINK_DC` |
| 10 (MOSI) | `EINK_COPI` | | 27 | `EINK_RESET` |
| 11 (SCLK) | `EINK_SCK` | | | |

(GPIO 24 → MCU PA19 is the fast trigger; GPIO 23 → MCU power-enable for
flashing — both on the broker/firmware side, not the panel.)
