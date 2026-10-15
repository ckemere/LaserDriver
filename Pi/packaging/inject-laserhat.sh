#!/bin/bash
#
# inject-laserhat.sh — bake the laserhat package into a freshly flashed
# Raspberry Pi OS SD card or .img file, so the instrument works from the
# very first boot.
#
#   sudo ./inject-laserhat.sh /dev/sdX  laserhat_1.0_arm64.deb   # SD card
#   sudo ./inject-laserhat.sh raspios.img laserhat_1.0_arm64.deb # image file
#
# What it does to the target:
#   rootfs: extracts the .deb (oledd binary, Python app, systemd units,
#           static-IP NetworkManager profile, i2c-dev module config),
#           creates the 'laserhat' system user, enables the services,
#           and stages the .deb + a one-shot first-boot unit that
#           apt-installs it properly (registering the package and
#           pulling the python3-* dependencies from the network).
#   boot:   config.txt gets dtparam=i2c_arm=on
#
# The compiled OLED daemon is static and runs immediately at first boot
# (hostname + wired/wifi IPs + heartbeat); the broker/GUIs start
# crash-loop-retrying until the first-boot apt install provides their
# python3 dependencies, then come up on their own.  The CI "golden"
# images run the apt step at image-build time instead, so they are
# complete offline.

set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run with sudo (mounting partitions needs root)"
[ $# -eq 2 ] || die "usage: $0 <device-or-image> <laserhat .deb>"

TARGET=$1
DEB=$2

[ -e "$TARGET" ] || die "$TARGET not found"
[ -f "$DEB" ]    || die "package $DEB not found"

case "$(dpkg-deb -f "$DEB" Architecture 2>/dev/null || true)" in
    arm64|armhf) ;;
    *) die "$DEB is not an ARM laserhat package" ;;
esac

# --- attach image files to a loop device; use block devices as-is ----------
LOOPDEV=""
cleanup() {
    set +e
    [ -n "${ROOT_MNT:-}" ] && mountpoint -q "$ROOT_MNT" && umount "$ROOT_MNT"
    [ -n "${BOOT_MNT:-}" ] && mountpoint -q "$BOOT_MNT" && umount "$BOOT_MNT"
    [ -n "$LOOPDEV" ] && losetup -d "$LOOPDEV"
    [ -n "${WORK:-}" ] && rmdir "$WORK/boot" "$WORK/root" "$WORK" 2>/dev/null
}
trap cleanup EXIT

if [ -b "$TARGET" ]; then
    DEV=$TARGET
else
    LOOPDEV=$(losetup -fP --show "$TARGET")   # -P scans the partition table
    DEV=$LOOPDEV
    [ -b "${DEV}p1" ] || partx -a "$DEV" 2>/dev/null || true
fi

if [ -b "${DEV}p1" ]; then
    BOOT_PART=${DEV}p1 ROOT_PART=${DEV}p2
elif [ -b "${DEV}1" ]; then
    BOOT_PART=${DEV}1 ROOT_PART=${DEV}2
else
    die "cannot find partitions on $DEV — is this a flashed Raspberry Pi OS card?"
fi

WORK=$(mktemp -d)
BOOT_MNT=$WORK/boot ROOT_MNT=$WORK/root
mkdir -p "$BOOT_MNT" "$ROOT_MNT"
mount "$BOOT_PART" "$BOOT_MNT"
mount "$ROOT_PART" "$ROOT_MNT"

[ -d "$ROOT_MNT/etc/systemd/system" ] || die "$ROOT_PART doesn't look like a Linux rootfs"

# --- rootfs: unpack the package payload ------------------------------------
# Guard: on merged-usr Raspberry Pi OS, /lib /bin /sbin are symlinks into
# /usr.  Plain extraction of a package that ships those top-level paths
# would replace the symlink with a directory and brick every dynamic
# binary in the image.  The laserhat package must only ship /usr and /etc.
if dpkg-deb -c "$DEB" | awk '{print $6}' | grep -qE '^\./(lib|bin|sbin)/'; then
    die "$DEB ships /lib, /bin or /sbin paths — would clobber merged-usr symlinks"
fi
dpkg-deb -x "$DEB" "$ROOT_MNT"
chmod 600 "$ROOT_MNT/etc/NetworkManager/system-connections/laserhat-eth0.nmconnection"

# --- rootfs: 'laserhat' system user (postinst will find it already there) --
if ! grep -q '^laserhat:' "$ROOT_MNT/etc/passwd"; then
    ID=990
    while grep -q ":$ID:" "$ROOT_MNT/etc/passwd" "$ROOT_MNT/etc/group"; do
        ID=$((ID - 1))
        [ $ID -gt 900 ] || die "no free system uid/gid found"
    done
    echo "laserhat:x:$ID:$ID::/nonexistent:/usr/sbin/nologin" >> "$ROOT_MNT/etc/passwd"
    echo "laserhat:x:$ID:" >> "$ROOT_MNT/etc/group"
    echo 'laserhat:!:19000:0:99999:7:::' >> "$ROOT_MNT/etc/shadow"
fi

# --- rootfs: enable the services (symlinks; no systemd needed here) --------
# oledd starts at sysinit so the display is on early; the rest at multi-user.
mkdir -p "$ROOT_MNT/etc/systemd/system/sysinit.target.wants" \
         "$ROOT_MNT/etc/systemd/system/multi-user.target.wants"
ln -sf /usr/lib/systemd/system/laserhat-oledd.service \
       "$ROOT_MNT/etc/systemd/system/sysinit.target.wants/laserhat-oledd.service"
for unit in laserhat-broker oled-gui laserhat-web; do
    ln -sf "/usr/lib/systemd/system/$unit.service" \
           "$ROOT_MNT/etc/systemd/system/multi-user.target.wants/$unit.service"
done

# --- rootfs: stage the deb + one-shot installer for the apt dependencies ---
mkdir -p "$ROOT_MNT/var/cache/laserhat"
cp "$DEB" "$ROOT_MNT/var/cache/laserhat/"
cat > "$ROOT_MNT/etc/systemd/system/laserhat-firstboot.service" <<'EOF'
[Unit]
Description=LaserHAT first boot: register package and install dependencies
After=network-online.target
Wants=network-online.target
ConditionPathExistsGlob=/var/cache/laserhat/*.deb

[Service]
Type=oneshot
TimeoutStartSec=900
ExecStart=/bin/sh -c 'apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y /var/cache/laserhat/*.deb && \
    rm -rf /var/cache/laserhat && \
    systemctl disable laserhat-firstboot.service'

[Install]
WantedBy=multi-user.target
EOF
ln -sf /etc/systemd/system/laserhat-firstboot.service \
       "$ROOT_MNT/etc/systemd/system/multi-user.target.wants/laserhat-firstboot.service"

# --- boot partition: enable the I2C bus in config.txt ----------------------
CONFIG=$BOOT_MNT/config.txt
[ -f "$CONFIG" ] || die "no config.txt on the boot partition"
if grep -q '^#dtparam=i2c_arm=on' "$CONFIG"; then
    sed -i 's/^#dtparam=i2c_arm=on/dtparam=i2c_arm=on/' "$CONFIG"
elif ! grep -q '^dtparam=i2c_arm=on' "$CONFIG"; then
    printf '\ndtparam=i2c_arm=on\n' >> "$CONFIG"
fi

# --- boot partition: give the broker its UART ------------------------------
# The broker owns /dev/ttyS0 for the MCU link, so the UART must exist
# (enable_uart=1) and the kernel console must be off it (drop
# console=serial0,... from cmdline.txt).
if ! grep -q '^enable_uart=1' "$CONFIG"; then
    printf 'enable_uart=1\n' >> "$CONFIG"
fi
CMDLINE=$BOOT_MNT/cmdline.txt
if [ -f "$CMDLINE" ]; then
    sed -i 's/console=serial0,[0-9]* //g; s/console=ttyAMA0,[0-9]* //g' "$CMDLINE"
fi

# --- appliance tuning: faster boot ----------------------------------------
# LaserHAT is a fixed-function instrument, so skip firmware probing for
# hardware it doesn't have and mask stock services it doesn't use.
# Rationale for every entry is in Pi/PROVISIONING.md; each mask is undone
# with `sudo systemctl unmask <unit>`.

# config.txt: no boot delay, no rainbow splash, no camera/DSI probing.
for kv in boot_delay=0 disable_splash=1 camera_auto_detect=0 display_auto_detect=0; do
    key=${kv%%=*}
    if grep -q "^$key=" "$CONFIG"; then
        sed -i "s/^$key=.*/$kv/" "$CONFIG"
    else
        printf '%s\n' "$kv" >> "$CONFIG"
    fi
done

# Mask unused services (offline mask = symlink to /dev/null in /etc).
#   ModemManager        no modem; several seconds of D-Bus probing
#   bluetooth, hciuart  no Bluetooth; hciuart probes the BT UART for seconds
#   triggerhappy        input-device hotkey daemon; no input devices
#   rpi-eeprom-update   boot-time EEPROM check; run manually if ever needed
#   dphys-swapfile      swap creation/validation; the stack fits in RAM
#   NetworkManager-wait-online  nothing here needs network-online.target
for unit in ModemManager.service bluetooth.service hciuart.service \
            triggerhappy.service triggerhappy.socket \
            rpi-eeprom-update.service dphys-swapfile.service \
            NetworkManager-wait-online.service; do
    ln -sf /dev/null "$ROOT_MNT/etc/systemd/system/$unit"
done

sync
echo "done: laserhat installed and enabled."
echo "First boot: OLED shows hostname + IPs immediately; broker/web come up"
echo "after the one-shot apt install of the python3 dependencies completes"
echo "(needs a network route — wifi via Imager customisation, or the wired"
echo "port which is fixed at 192.168.17.10/24)."
