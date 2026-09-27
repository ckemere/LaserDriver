# LaserHAT Provisioning Reference

Everything the LaserHAT deployment changes on a stock Raspberry Pi OS
Lite system, and why.  This is the authoritative list: the Debian
package (`packaging/build-deb.sh`) and the image injector
(`packaging/inject-laserhat.sh`) implement it, the CI golden images are
built by running the injector against official Raspberry Pi OS Lite and
then apt-installing the package in a chroot.  If you change provisioning
behaviour, change this document in the same commit.

Undo notes are included for every change.

## 1. The `laserhat` Debian package

| Path | What | Why |
|---|---|---|
| `/usr/bin/laserhat-oledd` | Static C daemon owning the SSD1305 OLED | No Python graphics stack; works from early boot; see `oledd.c` |
| `/usr/bin/laserhat-brokerd` | Static C broker: UART, trigger GPIO, UDP triggers | Real-time trigger path; see `brokerd/README.md` |
| `/usr/bin/laserhat-flash` | Programs the MCU over SWD (manual, `sudo`) | Boards arrive blank; see §9 |
| `/usr/lib/laserhat/firmware/` | `laserhat-mcu.elf`/`.hex`, `pi-swd.cfg`, `VERSION` | MCU firmware built by CI from the same commit as the broker (shared `protocol.h`) |
| `/usr/lib/laserhat/*.py` (+`templates/`) | OLED GUI, web GUI, protocol, `broker.py` fallback | Single install location, no venv, imports via `WorkingDirectory` |
| `/usr/lib/systemd/system/laserhat-*.service`, `oled-gui.service` | Service units | `/usr/lib` (not `/lib`) because `/lib` is a merged-usr **symlink**; a package extracting a real `/lib` directory over it destroys the dynamic-loader path and bricks the OS. The injector refuses any package shipping top-level `/lib`, `/bin` or `/sbin`. |
| `/etc/NetworkManager/system-connections/laserhat-eth0.nmconnection` | Static wired IP (see §3) | conffile, mode 0600 (NetworkManager refuses looser modes) |
| `/etc/modules-load.d/laserhat.conf` | Loads `i2c-dev` at boot | The OLED daemon needs `/dev/i2c-1` without waiting for anything to modprobe it |

Declared dependencies (from apt, no pip): `python3`, `python3-serial`,
`python3-flask`, `python3-gpiozero`, `python3-lgpio`, `openocd` (for
`laserhat-flash`; the golden-image build fails if this OS release's
openocd lacks `target/ti_mspm0.cfg`).

**postinst** creates the `laserhat` system user (all four daemons share
it so their Unix sockets in `/run/laserhat*` need no cross-user
permissions), enables the units, and — only when a live systemd is
present, i.e. not in an image chroot — restarts services and reloads
NetworkManager.

Undo: `sudo apt purge laserhat`.

## 2. Services

| Unit | Starts at | Runs as | Groups | Why |
|---|---|---|---|---|
| `laserhat-oledd` | **sysinit.target** | laserhat | i2c, gpio | The display is the boot indicator: `DefaultDependencies=no`, ordered only after `local-fs.target` + `systemd-modules-load.service`, so hostname/IPs/heartbeat appear seconds after the kernel starts. The daemon retries `/dev/i2c-1` for ~30 s, so racing the module load/udev is harmless. |
| `laserhat-broker` | multi-user | laserhat | dialout, gpio | `/usr/bin/laserhat-brokerd`. Sole owner of `/dev/ttyS0` (MCU link) and the GPIO trigger (`/dev/gpiomem`); serves clients on `/run/laserhat/broker.sock`; UDP triggers on `192.168.17.10:17017` (trigger thread SCHED_FIFO 80 on CPU 3 via `LimitRTPRIO`/`LimitMEMLOCK`) |
| `oled-gui` | multi-user | laserhat | — | Broker client; sends body rows to oledd over `/run/laserhat-oled/oled.sock`; before it connects, oledd shows the boot screen (hostname + `E:`/`W:` addresses) |
| `laserhat-web` | multi-user | laserhat | — | Flask on `0.0.0.0:8080` — reachable on both the static wired address and wifi |

Undo any single unit: `sudo systemctl disable --now <unit>`.

## 3. Networking

- **eth0: static 192.168.17.10/24, no gateway** (`never-default=true`),
  via a NetworkManager keyfile.  The wired port is a lab point-to-point
  link to the recording rig; wifi keeps DHCP and the default
  route/internet.  IPv6 disabled on the wired profile.
- **UDP 17017, bound to the wired address:** the network trigger port
  (protocol in `brokerd/README.md`). Ordinary wifi clients can't reach
  it; add `--udp-allow <rig IP>` to the unit to accept only the rig.
- The OLED header alternates `LASERHAT` tag / `E:<wired>` / `W:<wifi>`
  every 3 s (`WAITING` until an interface has an address); the web page
  header and `/api/net` report both.

Undo: delete the keyfile and `sudo nmcli connection reload`, or edit the
address in it.

## 4. Boot partition (`config.txt` / `cmdline.txt`)

Applied by the injector (and therefore present in golden images):

| Change | Why | Undo |
|---|---|---|
| `dtparam=i2c_arm=on` | OLED bonnet is I2C (`0x3C` on `/dev/i2c-1`) | remove line |
| `enable_uart=1` | Broker's MCU link is the mini-UART `/dev/ttyS0`; without this the port doesn't exist and the GUIs never leave the boot screen | remove line |
| remove `console=serial0,…` from `cmdline.txt` | The kernel console would fight the broker for the UART | re-add, or `raspi-config` → Serial |
| `boot_delay=0` | Drop the firmware's default SD settle delay (~1 s) | remove line |
| `disable_splash=1` | Skip the rainbow splash (~0.5 s) | remove line |
| `camera_auto_detect=0`, `display_auto_detect=0` | No camera or DSI display on this instrument; skips firmware probing (~1 s) | set back to 1 |

Note: `enable_uart=1` selects the **mini-UART** (`/dev/ttyS0`), matching
the units and docs.  If you ever switch to the PL011
(`dtoverlay=disable-bt`), point the broker at `/dev/serial0` instead.

## 5. Masked stock services (boot-time tuning)

A fixed-function instrument doesn't need these; each is masked
(symlinked to `/dev/null` in `/etc/systemd/system/`) by the injector.
Approximate savings are from `systemd-analyze blame` on a Pi 4.

| Unit | Why it's safe to drop here | ~Saves |
|---|---|---|
| `ModemManager.service` | No cellular modem | 2–4 s |
| `bluetooth.service`, `hciuart.service` | No Bluetooth; hciuart probes the BT UART at boot | 2–5 s |
| `triggerhappy.service` + `.socket` | Hotkey daemon for input devices; there are none | <1 s |
| `rpi-eeprom-update.service` | Boot-time EEPROM check; run `rpi-eeprom-update` manually during maintenance | ~1 s |
| `dphys-swapfile.service` | Creates/validates swap; the whole stack fits in RAM, and an instrument shouldn't swap | 1–3 s |
| `NetworkManager-wait-online.service` | Nothing in the stack requires `network-online.target`; masking guarantees no future dependency can add its up-to-30 s wait | 0–30 s |

Deliberately **kept**: `avahi-daemon` (mDNS — `http://<hostname>.local:8080/`
discovery), `systemd-timesyncd` (sane log timestamps), the KMS/HDMI
stack (plug in a monitor for debugging).

Undo any mask: `sudo systemctl unmask <unit> && sudo systemctl start <unit>`.

## 6. System user

`laserhat` (system account, no home, `nologin`).  The package postinst
creates it with `adduser --system --group`; the injector appends
equivalent `passwd`/`group`/`shadow` entries directly (picking a free
system uid/gid) because it runs against a mounted image with no chroot.

## 7. First boot (inject path only)

The injector stages the `.deb` in `/var/cache/laserhat/` plus a one-shot
`laserhat-firstboot.service` that waits for network-online, apt-installs
the package (registering it with dpkg and pulling the `python3-*`
dependencies), then disables itself.  Until it completes, oledd (static,
no dependencies) already runs; broker/GUIs crash-retry and come up on
their own once the dependencies land.

The **golden images do not need this**: CI installs the package with apt
inside a qemu chroot at image-build time, so they are complete offline.
The firstboot unit is removed from them.

## 8. What first-boot looks like

1. ~5–10 s: firmware + kernel (not reducible from userspace).
2. Seconds later: OLED heartbeat dot + hostname + `E:192.168.17.10` /
   `W:WAITING` (oledd at sysinit).
3. Raspberry Pi OS first-boot machinery (filesystem expansion, SSH keys,
   Imager customisation) runs once; subsequent boots are much faster.
4. Broker connects to the MCU; the OLED GUI takes over the body rows
   (params + WAIT/TRIG chip); web GUI answers on both addresses.

If the display stays on the boot screen: `journalctl -u laserhat-broker
-u oled-gui -n 30` — almost always the MCU link (HAT unpowered, not
flashed, or UART config reverted).

## 9. MCU firmware (manual, once per board)

New boards arrive with a blank MCU, and nothing flashes automatically.
With the **laser unplugged**:

```bash
sudo laserhat-flash
```

The command stops the broker and GUIs, which frees GPIO 24 (the SWD data
line and also the trigger line). It then power-cycles the MCU into its boot
window, writes `/usr/lib/laserhat/firmware/laserhat-mcu.elf` with OpenOCD,
and restarts the services. A successful flash ends with the ~4 s boot blink on
STIM_MIRROR, and the OLED/web then show the MCU as alive.
`cat /usr/lib/laserhat/firmware/VERSION` shows which release the firmware
came from. Re-run the command after installing a new package version to keep
the firmware and broker matched.
