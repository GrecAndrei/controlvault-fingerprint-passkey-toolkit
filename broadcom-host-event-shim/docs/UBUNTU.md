# Ubuntu 26.04 LTS: Broadcom ControlVault 3 host-event shim

This guide describes an Ubuntu-specific build and manual installation of the
host-event shim for the Broadcom ControlVault 3 fingerprint reader. It keeps
Ubuntu's existing `fprintd` executable and systemd security settings intact.

## Tested configuration

| Component | Configuration |
| --- | --- |
| Laptop | Dell Latitude 5320 |
| Operating system | Ubuntu 26.04.1 LTS (resolute), amd64 |
| BIOS | 1.53.0 at diagnosis |
| USB ID | `0a5c:5843` |
| Sensor | Broadcom BCM58200 ControlVault 3 |
| AAI firmware | `5.15.21.0` |
| SBI firmware | `240` |
| Sensor firmware | `GF5288_GM188WNC_APP_10009` |
| Broadcom TOD package | `5.15.377-5.15.021.0-0ubuntu1~26.04.1~oem1` |
| libfprint TOD | `1:1.95.1+tod1-0ubuntu2` |
| fprintd | `1.94.5-4` |

The reporter observed successful physical fingerprint enrollment using a locally
adapted shim and a temporary systemd override. The subsequent cross-distribution
library lookup change passed the existing build and unit tests. Independent
hardware validation of that final revision, wrong-finger rejection, and
verification after reboot have not yet been documented. This is not a claim of
support for all Ubuntu releases or ControlVault devices.

## Symptoms

The USB reader is detected and the proprietary Broadcom driver initializes, but
fingerprint enrollment can fail after one or more successful capture stages:

```text
Enroll result: enroll-stage-passed
Enroll result: enroll-unknown-error
```

The journal may contain `Enrollment failed : Device status = (11)` or
`Device disabled to prevent overheating.` The latter is not by itself proof of
physical overheating. Do not override thermal protection. Stop testing if the
reader becomes unusually warm or reports a thermal error.

The shim targets a host-timestamp protocol omission described in the main shim
README. Similar symptoms can have other causes; this workaround is not a
universal fix for all enrollment errors.

## 1. Install dependencies and the matching TOD driver

Confirm the hardware first:

```sh
lsusb -d 0a5c:5843
```

Install the Ubuntu build and fingerprint packages:

```sh
sudo apt update
sudo apt install build-essential pkg-config libusb-1.0-0-dev \
  fprintd libpam-fprintd libfprint-2-tod1 software-properties-common
```

The reported test used the `medicalwei/dell-cv3-cv3plus` PPA. If the correct
Broadcom TOD driver is already installed, skip the repository setup. Otherwise,
review the [PPA](https://launchpad.net/~medicalwei/+archive/ubuntu/dell-cv3-cv3plus)
and its packages before adding this third-party package source:

```sh
sudo add-apt-repository ppa:medicalwei/dell-cv3-cv3plus
sudo apt update
apt-cache policy libfprint-2-tod1-broadcom
sudo apt install libfprint-2-tod1-broadcom
```

Ensure that the candidate is intended for the installed Ubuntu release. The
ControlVault 3 Plus and Goodix packages are not substitutes for the tested
ControlVault 3 sensor. Do not mix packages from older Ubuntu releases or downgrade
firmware for this workaround. The proprietary TOD package may include firmware;
its behavior is separate from the shim.

Check package versions and paths:

```sh
dpkg -l | grep -E 'fprint|broadcom'
dpkg -L libfprint-2-tod1-broadcom | grep '\.so'
systemctl cat fprintd.service
fprintd-list "$USER"
```

On the tested Ubuntu system, the driver and daemon are located at:

```text
/usr/lib/x86_64-linux-gnu/libfprint-2/tod-1/libfprint-2-tod-1-broadcom.so
/usr/libexec/fprintd
```

If the reader is not detected by `fprintd`, diagnose the driver first. This shim
is not a replacement for the Broadcom TOD driver.

## 2. Build and run tests

From the repository root, enter the shim directory:

```sh
cd broadcom-host-event-shim
make clean check
make tools/sync_probe
file libbcm-cv-host-event-shim.so
ldd libbcm-cv-host-event-shim.so
```

Run these build commands as an ordinary user, not root. Building the diagnostic
probe is optional; running it against the physical device is not required for
this procedure. The expected simulated unit-test result is:

```text
PASS: timestamp host event is synchronized and hidden from vendor blob
```

The portability changes retain the original driver path and add Ubuntu's
x86-64 multiarch path. They also explicitly consume the result of `write()` in
best-effort logging so the code builds with strict compiler warnings enabled.
Passing the existing unit test does not establish biometric security or hardware
compatibility.

## 3. Temporary, reversible test

**Security:** This is experimental third-party code loaded into an authentication
service. Review the source and the build before installing it. Keep password
authentication available. The procedure deliberately leaves PAM settings,
`ExecStart`, and systemd security restrictions unchanged. Do not use the shim as
an authentication dependency on a security-sensitive system without an
appropriate review.

Check for existing overrides before proceeding:

```sh
systemctl cat fprintd.service
systemctl show fprintd.service -p Environment -p ExecStart
```

Do not overwrite an existing `LD_PRELOAD` configuration or a file installed by
another shim. The following steps assume that the named files and directory do
not already exist and that no conflicting preload is active.

From the shim build directory:

```sh
sudo install -d -o root -g root -m 0755 /run/fprintd-host-event-shim
sudo install -o root -g root -m 0644 \
  libbcm-cv-host-event-shim.so \
  /run/fprintd-host-event-shim/libbcm-cv-host-event-shim.so
sudo mkdir -p /run/systemd/system/fprintd.service.d
sudo tee /run/systemd/system/fprintd.service.d/90-broadcom-shim.conf \
  >/dev/null <<'CONFIG'
[Service]
Environment=LD_PRELOAD=/run/fprintd-host-event-shim/libbcm-cv-host-event-shim.so
CONFIG
sudo systemctl daemon-reload
sudo systemctl restart fprintd
systemctl show fprintd.service -p Environment -p ExecStart
fprintd-list "$USER"
```

This override does not replace the original service executable. The files under
`/run` are normally cleared at reboot. If startup fails, use the rollback below.

To inspect the loaded library immediately after a successful device query:

```sh
pid=$(systemctl show fprintd.service -p MainPID --value)
if [ "$pid" -gt 0 ]; then
  sudo grep -F libbcm-cv-host-event-shim "/proc/$pid/maps"
fi
```

`fprintd` can stop automatically while idle. A zero PID is not by itself a crash.

## 4. Enroll and verify

Monitor the journal in one terminal:

```sh
sudo journalctl -fu fprintd -o short-precise
```

In another terminal, with the reader cool and unused by other clients:

```sh
fprintd-enroll -f right-index-finger "$USER"
```

Touch and lift the enrolled finger between captures. If the operation stalls,
fails, or triggers thermal protection, cancel it and do not immediately retry.
A successful enrollment reports `enroll-completed`. A journal entry such as
`BCM_CV: handled host timestamp interrupt, control status=0` indicates that the
shim handled the targeted event if it occurred during the operation.

Check the enrollment and verify:

```sh
fprintd-list "$USER"
fprintd-verify -f right-index-finger "$USER"
```

Test with the enrolled finger and separately with an unenrolled finger. The
registered finger should produce `verify-match`; an unregistered finger must
not be accepted. If the behavior is unexpected, roll back. Do not enable PAM
fingerprint authentication based on a successful enrollment alone.

## 5. Optional permanent configuration

The following procedure is proposed for systems where the temporary test and
positive and negative verification tests have succeeded. Reboot persistence
was not yet documented in the reported test. If the third-party shim is not
acceptable under your security requirements, retain password-only authentication
instead.

Make sure the destination library and override file do not already exist. Do
not overwrite unrelated configurations. From the successful temporary test:

```sh
sudo install -o root -g root -m 0644 \
  /run/fprintd-host-event-shim/libbcm-cv-host-event-shim.so \
  /usr/local/lib/libbcm-cv-host-event-shim.so
sudo mkdir -p /etc/systemd/system/fprintd.service.d
sudo tee /etc/systemd/system/fprintd.service.d/90-broadcom-shim.conf \
  >/dev/null <<'CONFIG'
[Service]
Environment=LD_PRELOAD=/usr/local/lib/libbcm-cv-host-event-shim.so
CONFIG
sudo rm -f /run/systemd/system/fprintd.service.d/90-broadcom-shim.conf
sudo systemctl daemon-reload
sudo systemctl restart fprintd
systemctl show fprintd.service -p Environment -p ExecStart
```

After reboot, repeat both verification tests. Keep password login available and
prefer password authentication for privileged operations. This guide does not
change PAM configuration. Recheck compatibility after updates to the Broadcom
package, `libfprint`, or `fprintd`.

## 6. Rollback

Remove only files created by this guide (not files managed by the upstream
installer or another configuration). If the daemon fails to restart, inspect
its journal and leave password authentication enabled.

```sh
sudo rm -f /run/systemd/system/fprintd.service.d/90-broadcom-shim.conf
sudo rm -f /etc/systemd/system/fprintd.service.d/90-broadcom-shim.conf
sudo systemctl daemon-reload
sudo systemctl restart fprintd
sudo rm -f /run/fprintd-host-event-shim/libbcm-cv-host-event-shim.so
sudo rm -f /usr/local/lib/libbcm-cv-host-event-shim.so
sudo rmdir /run/fprintd-host-event-shim 2>/dev/null || true
systemctl show fprintd.service -p Environment -p ExecStart
```

For a temporary-only installation, rebooting also removes the temporary files.
Rollback removes the shim, not enrolled fingerprints or the proprietary driver.
If desired, remove your own enrolled fingerprints through Ubuntu Settings or
`fprintd-delete "$USER"` while the driver is functional. This guide does not
change firmware, BIOS settings, or disk encryption.

## Reporting compatibility

When reporting results upstream, include the laptop model, Ubuntu release, USB
ID, relevant package versions, firmware versions, unit-test result, and whether
enrollment and positive/negative verification work before and after reboot.
Redact usernames, hostnames, device serial numbers, credentials, and any
biometric material from public reports.
