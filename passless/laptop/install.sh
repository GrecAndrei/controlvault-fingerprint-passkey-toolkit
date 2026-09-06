#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target_user=${SUDO_USER:-$(id -un)}
target_home=$(getent passwd "$target_user" | cut -d: -f6)
target_uid=$(id -u "$target_user")

if [ -z "$target_home" ] || [ ! -d "$target_home" ]; then
  echo "Unable to resolve home directory for $target_user" >&2
  exit 1
fi

# Non-interactive terminals may omit these even while the graphical user bus is
# active. They identify the same per-user bus systemctl and notifications use.
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$target_uid}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}

cd "$project_dir"
cargo build --release --locked --features tpm

sudo -n groupadd --system fido 2>/dev/null || true
sudo -n usermod -a -G fido,tss "$target_user"
sudo -n install -o root -g root -m 0755 target/release/passless /usr/local/bin/passless
sudo -n install -o root -g root -m 0644 laptop/90-hello-passkey.rules \
  /etc/udev/rules.d/90-hello-passkey.rules
sudo -n install -o root -g root -m 0644 laptop/../contrib/modules-load.d/fido.conf \
  /etc/modules-load.d/hello-passkey.conf
sudo -n modprobe uhid
sudo -n udevadm control --reload-rules
sudo -n udevadm trigger --action=change /sys/class/misc/uhid 2>/dev/null || true
sudo -n udevadm trigger --action=change /sys/class/tpmrm/tpmrm0 2>/dev/null || true

install -d -m 0700 "$target_home/.config/passless" \
  "$target_home/.local/share/passless/tpm" \
  "$target_home/.config/systemd/user"
install -m 0600 laptop/config.toml "$target_home/.config/passless/config.toml"
install -m 0644 laptop/passless.service \
  "$target_home/.config/systemd/user/passless.service"

# logind normally applies TAG+=uaccess immediately. These ACLs cover udev
# implementations which only apply it on a new session; the udev/group policy
# remains the persistent mechanism after reboot.
sudo -n setfacl -m "u:$target_user:rw" /dev/uhid /dev/tpmrm0

systemctl --user daemon-reload
systemctl --user enable --now passless.service
echo "Local passkey authenticator installed and started."
