# LaserHAT Pi-side

Pi-side Python that talks to the LaserHAT. A **broker daemon owns the
serial port** and every GUI is a client of it over a Unix socket, so the
eink GUI and web GUI run at the same time.

- `protocol.py` — the binary wire protocol (COBS + CRC16). Single
  Python source of truth; mirror of `Firmware/laserHatFirmware/protocol.h`.
- `laser_hat.py` — the binary UART transport (`LaserUART`) plus the
  shared `State` dataclass. Used **only by the broker** (it is the lone
  serial-port owner). Also a small CLI smoke tool for the raw link.
- `broker.py` — the daemon. Owns `/dev/ttyS0` and the GPIO trigger pin,
  mirrors MCU state, and broadcasts state + button/pulse events to
  clients over `/run/laserhat/broker.sock`. Clients publish commands up;
  the broker broadcasts down (pub/sub).
- `hat_client.py` — `HatClient`, the thin client GUIs use: connects to
  the broker, caches the latest broadcast `State`, fires a callback on
  every update, and exposes `set_*` / `trigger` / `trigger_gpio` / `arm`.
- `eink_panel.py` — slim self-contained SSD1680 / GDEY0213B74 driver
  on `spidev` + `gpiozero` + Pillow.
- `pi_trigger.py` — `PiTrigger` class + CLI. Drives Pi GPIO 24 high
  briefly so the MCU's PA19 edge ISR fires a pulse directly, bypassing
  UART entirely (~50–100 µs, low jitter). Owned by the broker at runtime.
- `eink_gui.py` — long-running eink GUI; a broker client, event-driven
  (no polling), runs the button-driven UI and repaints the panel.
- `web_app.py` — Flask web GUI; a broker client. Same controls plus
  *two* trigger buttons (UART path and GPIO path).
- `fake_mcu.py` — a PTY that speaks the protocol, for testing the broker
  and GUIs off-hardware (no board needed).

```
Pi/
  protocol.py            binary wire protocol (COBS + CRC16)
  laser_hat.py           LaserUART transport + State + CLI smoke tool
  broker.py              UART-owning broker daemon (Unix socket, pub/sub)
  hat_client.py          HatClient — GUI-facing broker client
  eink_panel.py          SSD1680 driver (full + partial refresh)
  pi_trigger.py          PiTrigger class + CLI (GPIO-path trigger)
  fake_mcu.py            PTY MCU simulator for off-hardware tests
  eink_ip.py             one-shot: render IP + hostname, exit
  eink_gui.py            long-running eink GUI daemon (broker client)
  web_app.py             Flask web GUI (broker client)
  templates/
    index.html           single-page browser UI (vanilla JS)
  requirements.txt       Python deps
  tests/                 pytest: protocol codec + broker integration
  systemd/
    laserhat-broker.service  owns /dev/ttyS0, serves the Unix socket
    eink-ip.service      runs eink_ip.py once on boot + each timer fire
    eink-ip.timer        re-render every 5 min so DHCP changes show up
    eink-gui.service     runs eink_gui.py until killed
    laserhat-web.service runs web_app.py until killed
```

**The broker owns the UART; GUIs are clients.** Start
`laserhat-broker.service` first; `eink-gui.service` and
`laserhat-web.service` both connect to it over `/run/laserhat/broker.sock`
and can run together. Only the broker opens `/dev/ttyS0` — don't run the
`laser_hat.py` CLI against the port while the broker is up.

`eink-ip.timer` and `eink-gui.service` both drive the panel — enable
one or the other, not both.

## Testing off-hardware

```bash
~/.venvs/laserhat/bin/python -m pytest Pi/tests/      # codec + integration
# or drive the broker by hand against a simulated MCU:
DEV=$(~/.venvs/laserhat/bin/python Pi/fake_mcu.py &  sleep 0.3) # prints a /dev/pts/N
```

The cross-toolchain codec agreement is checked by
`Firmware/laserHatFirmware/host_tools/proto_crosscheck.py`.

---

## One-time install

```bash
sudo apt install python3-venv python3-pil python3-spidev \
                 python3-gpiozero python3-lgpio

python3 -m venv --system-site-packages ~/.venvs/laserhat
~/.venvs/laserhat/bin/pip install -r ~/Code/LaserDriver/Pi/requirements.txt
```

`--system-site-packages` lets the venv see Pi OS's pre-installed
`gpiozero` / Pillow / spidev / lgpio. Pip only installs what's
missing (Flask and pyserial, typically). **`python3-lgpio` matters:**
without it `gpiozero` falls back to `RPi.GPIO`, which is broken on
recent Pi OS kernels. Installing it via pip needs `swig` and a C
build — don't bother, the apt package is prebuilt and fine.

Make sure SPI is enabled (it has to be, for both the eink and any future
sensor work):

```bash
sudo raspi-config nonint do_spi 0    # or via the menu: Interface → SPI → Enable
```

User needs to be in the `spi` and `gpio` groups (default on Pi OS):

```bash
groups | tr ' ' '\n' | grep -E '^(spi|gpio)$'
# If either is missing:
#   sudo usermod -aG spi,gpio $USER && newgrp spi
```

---

## Manual run (sanity check)

```bash
cd ~/Code/LaserDriver/Pi
~/.venvs/laserhat/bin/python eink_ip.py
```

The display should clear to white, then show `LaserHAT` at the top,
`IP: 192.168.x.x` below it, the hostname underneath, and a thin red
rule across the bottom. Full refresh takes ~3 seconds.

If the script raises a SPI-busy or device-not-found error, double-check
`/dev/spidev0.0` exists (`ls /dev/spi*`) and that nothing else is
holding it.

---

## Deploy as a service

```bash
sudo cp ~/Code/LaserDriver/Pi/systemd/eink-ip.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now eink-ip.timer
```

The timer starts the service 30 seconds after boot and re-runs it
every 5 minutes — short enough that DHCP changes show up promptly,
long enough that the panel sees only a few hundred refreshes per day.

**Edit the two paths in `eink-ip.service` before installing if your
account name isn't `kemerelab`** — `User=`, `Group=`, `WorkingDirectory=`,
and the `ExecStart=` python prefix all point at the default home.

### Operating it

```bash
# Force a refresh now:
sudo systemctl start eink-ip.service

# See the last few runs:
journalctl -u eink-ip.service --since '10 minutes ago'

# Stop the periodic refresh:
sudo systemctl disable --now eink-ip.timer

# Watch live (useful when debugging):
journalctl -u eink-ip.service -f
```

---

## The broker

`broker.py` owns `/dev/ttyS0` and serves the GUIs. Run it first.

```bash
cd ~/Code/LaserDriver/Pi
~/.venvs/laserhat/bin/python broker.py
# → broker: serving on /run/laserhat/broker.sock
```

Deploy as a service (the GUIs `Requires=` it, so it starts on demand,
but enabling it is tidier):

```bash
sudo cp ~/Code/LaserDriver/Pi/systemd/laserhat-broker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now laserhat-broker.service
journalctl -u laserhat-broker.service -f
```

The unit uses `RuntimeDirectory=laserhat` so systemd creates
`/run/laserhat` (mode 0750, owned by the service user); the socket lives
inside it. Override the socket path with the `LASERHAT_SOCK` env var if
needed — all three units honour it.

## The eink GUI

`eink_gui.py` is a long-running daemon. Run it manually first to
confirm it works (the broker must already be running):

```bash
cd ~/Code/LaserDriver/Pi
~/.venvs/laserhat/bin/python eink_gui.py
# Ctrl-C to stop.
```

### Button mapping

Per the LaserHAT mechanical layout — B1 / B2 on the left edge of the
display, B3 / B4 below it:

```
+--------+
|   B1   |  trigger pulse  (firmware fires on release, no UART needed)
+--------+
|        |
|  EINK  |
|        |
+--------+
|   B2   |  cycle selected parameter (i → r → h → i …)
+--------+
+---+----+
|B3 | B4 |  decrement / increment the selected parameter
+---+----+
```

Step sizes are coarse for usability (`i`: 8, `r`: 200 ticks, `h`: 500
ticks). Edit `PARAMS` in `eink_gui.py` to tune them.

Refresh: routine UI updates use the panel's partial-refresh mode
(~300 ms). Every 30th update we silently do a full refresh to clear
ghosting; the first paint after boot is always full. After a button
press, the GUI waits `SETTLE_GAP` (default 300 ms) of quiet before
repainting, so a burst of B4 presses coalesces to a single refresh
at the final value.

### LaserHat CLI

`laser_hat.py` doubles as a quick CLI when you want to poke the
firmware over the raw binary link. It opens `/dev/ttyS0` directly, so
**stop the broker first** (only one process may own the port):

```bash
sudo systemctl stop laserhat-broker.service
~/.venvs/laserhat/bin/python laser_hat.py query
~/.venvs/laserhat/bin/python laser_hat.py set i 100
~/.venvs/laserhat/bin/python laser_hat.py trigger
~/.venvs/laserhat/bin/python laser_hat.py watch     # print every frame, Ctrl-C
```

### Deploy as a service

If `eink-ip.timer` is currently enabled, disable it first — both
services drive the same panel:

```bash
sudo systemctl disable --now eink-ip.timer

sudo cp ~/Code/LaserDriver/Pi/systemd/eink-gui.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now eink-gui.service
journalctl -u eink-gui.service -f
```

Same paths-to-edit caveat as `eink-ip.service`: `User=`, `Group=`,
`WorkingDirectory=`, and the python prefix in `ExecStart=` assume
the user's `kemerelab` account.

---

## The web GUI

`web_app.py` is a Flask app that serves the same controls as the eink
GUI from a browser, plus a big trigger button. Single-page, vanilla
JS; the page polls `/api/state`, which now returns the broker's cached
state (no UART round-trip per poll). The broker must be running.

```bash
cd ~/Code/LaserDriver/Pi
~/.venvs/laserhat/bin/python web_app.py
# → serving on 0.0.0.0:8080 (http://<pi-ip>:8080/)
```

Open `http://<pi-ip>:8080/` from any device on the LAN. Each parameter
has a step input (preset to 8 / 200 / 500 ticks; edit freely) and ±
buttons. Trigger button is disabled while a pulse is running so you
can't fire `t` and get back `ERR busy`.

### Deploy as a service

```bash
sudo cp ~/Code/LaserDriver/Pi/systemd/laserhat-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now laserhat-web.service
journalctl -u laserhat-web.service -f
```

The unit `Requires=laserhat-broker.service`, so the broker starts first.
The web GUI and `eink-gui.service` can both run at once — they're both
broker clients.

### Port override

`PORT` env var picks the bind port; the service unit sets 8080. To
run on 5000:

```bash
PORT=5000 ~/.venvs/laserhat/bin/python web_app.py
```

---

## Wiring (for reference)

Per the LaserHAT schematic (`LaserHAT/gpio_design.md`), the SSD1680Z is
connected to the Pi only — the MSPM0 does not have access:

| Pi GPIO       | HAT signal     | adafruit_epd pin     |
| ------------- | -------------- | -------------------- |
| GPIO 8 (CE0)  | `EINK_CS`      | `board.CE0`          |
| GPIO 9 (MISO) | `EINK_CIPO`    | `board.MISO`         |
| GPIO 10 (MOSI)| `EINK_COPI`    | `board.MOSI`         |
| GPIO 11 (SCLK)| `EINK_SCK`     | `board.SCK`          |
| GPIO 17       | `EINK_BUSY`    | `board.D17`          |
| GPIO 22       | `EINK_DC`      | `board.D22`          |
| GPIO 27       | `EINK_RESET`   | `board.D27`          |
