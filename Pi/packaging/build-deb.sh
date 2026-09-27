#!/bin/bash
#
# build-deb.sh — build the laserhat Debian package for one architecture.
#
#   ./build-deb.sh arm64  aarch64-linux-gnu-gcc      [version]
#   ./build-deb.sh armhf  arm-linux-gnueabihf-gcc    [version]
#   ./build-deb.sh native gcc                        [version]   (for testing)
#
# Produces laserhat_<version>_<arch>.deb in the current directory:
#
#   /usr/bin/laserhat-oledd                          compiled SSD1305 daemon
#   /usr/bin/laserhat-brokerd                        compiled broker (UART, GPIO,
#                                                    UDP triggers)
#   /usr/bin/laserhat-flash                          flash the MCU (manual; sudo)
#   /usr/lib/laserhat/                               Python app (GUIs; broker.py
#                                                    kept as a fallback)
#   /usr/lib/laserhat/firmware/                      MCU firmware built from the
#                                                    same commit + OpenOCD config
#   /usr/lib/systemd/system/laserhat-*.service, oled-gui.service
#   /etc/NetworkManager/system-connections/laserhat-eth0.nmconnection
#   /etc/modules-load.d/laserhat.conf                (i2c-dev)
#
# Python dependencies are declared as package Depends and come from apt —
# no pip, no venv.  The postinst creates the 'laserhat' system user and
# enables the services.  Building needs arm-none-eabi-gcc
# (gcc-arm-none-eabi) for the MCU firmware as well as the target C compiler.

set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }

[ $# -ge 2 ] || die "usage: $0 <arm64|armhf|native> <cc> [version]"

ARCH=$1
CC=$2
PI_DIR=$(cd "$(dirname "$0")/.." && pwd)
VERSION=${3:-$(git -C "$PI_DIR" describe --tags --always 2>/dev/null | sed 's/^v//;s/-/+/g' || echo 0.1.0)}

case "$ARCH" in
    arm64|armhf) DEB_ARCH=$ARCH ;;
    native)      DEB_ARCH=$(dpkg --print-architecture 2>/dev/null || echo amd64) ;;
    *)           die "arch must be arm64, armhf, or native" ;;
esac

command -v arm-none-eabi-gcc >/dev/null || \
    die "arm-none-eabi-gcc not found (apt install gcc-arm-none-eabi)"

PKG=$(mktemp -d)
FW_BUILD=$(mktemp -d)
chmod 755 "$PKG"        # mktemp makes 0700; don't ship that as the root dir
trap 'rm -rf "$PKG" "$FW_BUILD"' EXIT

# --- compiled OLED daemon ---------------------------------------------------
mkdir -p "$PKG/usr/bin"
"$CC" -O2 -Wall -Wextra -Werror -static -o "$PKG/usr/bin/laserhat-oledd" \
    "$PI_DIR/oledd.c"

# --- compiled broker ----------------------------------------------------------
# Static, like oledd, so the binary doesn't depend on the target's glibc.
"$CC" -O2 -Wall -Wextra -Werror -static -std=c11 -D_GNU_SOURCE -pthread \
    -I"$PI_DIR/../Firmware" -o "$PKG/usr/bin/laserhat-brokerd" \
    "$PI_DIR"/brokerd/*.c -lm

# --- MCU firmware + flashing tool --------------------------------------------
# Built from the same commit as the broker, so both sides share protocol.h.
# Flashing is manual (sudo laserhat-flash); nothing flashes at boot.
make -C "$PI_DIR/../Firmware" -f Makefile.gcc BUILD_DIR="$FW_BUILD" all
mkdir -p "$PKG/usr/lib/laserhat/firmware"
install -m 644 "$FW_BUILD/main.elf" "$PKG/usr/lib/laserhat/firmware/laserhat-mcu.elf"
install -m 644 "$FW_BUILD/main.hex" "$PKG/usr/lib/laserhat/firmware/laserhat-mcu.hex"
install -m 644 "$PI_DIR/../Firmware/openocd/pi-swd.cfg" "$PKG/usr/lib/laserhat/firmware/"
echo "$VERSION" > "$PKG/usr/lib/laserhat/firmware/VERSION"
install -m 755 "$PI_DIR/laserhat-flash" "$PKG/usr/bin/laserhat-flash"

# --- Python application -----------------------------------------------------
mkdir -p "$PKG/usr/lib/laserhat/templates"
install -m 644 "$PI_DIR"/*.py "$PKG/usr/lib/laserhat/"
install -m 644 "$PI_DIR"/templates/*.html "$PKG/usr/lib/laserhat/templates/"

# --- systemd units ----------------------------------------------------------
mkdir -p "$PKG/usr/lib/systemd/system"
install -m 644 "$PI_DIR"/systemd/*.service "$PKG/usr/lib/systemd/system/"

# --- static wired IP (192.168.17.10/24, no gateway) + i2c-dev module --------
mkdir -p "$PKG/etc/NetworkManager/system-connections" "$PKG/etc/modules-load.d"
install -m 600 "$PI_DIR/network/laserhat-eth0.nmconnection" \
    "$PKG/etc/NetworkManager/system-connections/"
cat > "$PKG/etc/modules-load.d/laserhat.conf" <<'MODS'
# Loaded at boot by systemd-modules-load so the OLED daemon does not
# have to wait for udev coldplug to discover the I2C bus mid-boot.
# i2c-bcm2835 is the bus controller on Pi 0-4 (a Pi 5's designware
# controller still arrives via udev; oledd retries until it does).
i2c-dev
i2c-bcm2835
MODS

# --- package metadata -------------------------------------------------------
mkdir -p "$PKG/DEBIAN"
cat > "$PKG/DEBIAN/control" <<EOF
Package: laserhat
Version: $VERSION
Architecture: $DEB_ARCH
Maintainer: Caleb Kemere <caleb.kemere@rice.edu>
Depends: python3, python3-serial, python3-flask, python3-gpiozero, python3-lgpio, openocd
Section: electronics
Priority: optional
Description: LaserHAT laser-diode driver control stack
 Broker daemon for the MSPM0-based LaserHAT (owns the UART and the
 trigger GPIO; low-latency UDP trigger listener), an OLED
 status/param GUI on the Adafruit SSD1305 bonnet driven by a compiled
 panel daemon, and a Flask web GUI.  Configures the wired interface
 with a static address (192.168.17.10/24, no gateway).  Includes the
 matching MCU firmware; program a board with 'sudo laserhat-flash'.
EOF

cat > "$PKG/DEBIAN/conffiles" <<EOF
/etc/NetworkManager/system-connections/laserhat-eth0.nmconnection
/etc/modules-load.d/laserhat.conf
EOF

UNITS="laserhat-oledd.service laserhat-broker.service oled-gui.service laserhat-web.service"

cat > "$PKG/DEBIAN/postinst" <<EOF
#!/bin/sh
set -e

# Service account shared by all four daemons (their Unix sockets live in
# /run/laserhat*, so a single user keeps the permissions trivial).
if ! getent passwd laserhat >/dev/null; then
    adduser --system --group --no-create-home \\
        --home /nonexistent --quiet laserhat
fi

# NetworkManager refuses keyfiles that are not 0600 root:root.
chmod 600 /etc/NetworkManager/system-connections/laserhat-eth0.nmconnection
chown root:root /etc/NetworkManager/system-connections/laserhat-eth0.nmconnection

for unit in $UNITS; do
    if command -v deb-systemd-helper >/dev/null; then
        deb-systemd-helper enable "\$unit" >/dev/null || true
    else
        # Fallback matches each unit's [Install] WantedBy target
        # (laserhat-oledd starts at sysinit for an early display).
        case "\$unit" in
            laserhat-oledd.service) tgt=sysinit.target ;;
            *)                      tgt=multi-user.target ;;
        esac
        mkdir -p "/etc/systemd/system/\$tgt.wants"
        ln -sf "/usr/lib/systemd/system/\$unit" \\
            "/etc/systemd/system/\$tgt.wants/\$unit"
    fi
done

# Only poke the live system when there is one (not in a chroot/image).
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload || true
    systemctl restart $UNITS || true
    nmcli connection reload 2>/dev/null || true
fi

exit 0
EOF
chmod 755 "$PKG/DEBIAN/postinst"

cat > "$PKG/DEBIAN/prerm" <<EOF
#!/bin/sh
set -e
if [ "\$1" = remove ] && [ -d /run/systemd/system ]; then
    systemctl stop $UNITS 2>/dev/null || true
fi
exit 0
EOF
chmod 755 "$PKG/DEBIAN/prerm"

OUT="laserhat_${VERSION}_${DEB_ARCH}.deb"
dpkg-deb --build --root-owner-group "$PKG" "$OUT"
echo "built $OUT"
