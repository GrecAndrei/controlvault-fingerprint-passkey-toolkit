#!/bin/sh
set -eu

override=/etc/systemd/system/fprintd.service.d/override.conf
state_dir=/var/lib/bcm-cv-host-event-shim
backup=$state_dir/override.conf.before-shim

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -n "$0" "$@"
fi

if [ -f "$backup" ]; then
  install -m 0644 "$backup" "$override"
elif [ -f "$state_dir/no-previous-override" ]; then
  rm -f "$override"
else
  echo "Refusing rollback: installation state is missing" >&2
  exit 1
fi
systemctl daemon-reload
systemctl restart fprintd.service
echo "Restored the pre-shim fprintd configuration."
