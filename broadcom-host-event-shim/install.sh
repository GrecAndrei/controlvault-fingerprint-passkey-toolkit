#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -n "$0" "$@"
fi

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
state_dir=/var/lib/bcm-cv-host-event-shim
override_dir=/etc/systemd/system/fprintd.service.d
override=$override_dir/override.conf

test -f "$project_dir/libbcm-cv-host-event-shim.so" || {
  echo "Build first with: make clean check" >&2
  exit 1
}

install -d -m 0700 "$state_dir"
if [ -f "$override" ] && [ ! -f "$state_dir/override.conf.before-shim" ]; then
  install -m 0600 "$override" "$state_dir/override.conf.before-shim"
elif [ ! -f "$override" ]; then
  : > "$state_dir/no-previous-override"
fi

install -o root -g root -m 0755 \
  "$project_dir/libbcm-cv-host-event-shim.so" \
  /usr/local/lib/libbcm-cv-host-event-shim.so
install -d -m 0755 "$override_dir"
install -o root -g root -m 0644 \
  "$project_dir/fprintd-broadcom-host-event.conf" "$override"
systemctl daemon-reload
systemctl restart fprintd.service
systemctl is-active --quiet fprintd.service
echo "Installed Broadcom host-event shim; fprintd is active."

