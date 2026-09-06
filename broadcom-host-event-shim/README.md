# Broadcom ControlVault host-event shim

This source-built libusb interposer fixes a protocol omission in Broadcom's
Linux TOD drivers for the `0a5c:5843` ControlVault 3 reader found in a Dell
Latitude 7400. It was validated with Broadcom TOD 5.15.021.0 and
libfprint-tod 1.95.2.

When endpoint `0x85` returns interrupt type `5`, Dell's Windows 5.15.15.8
driver identifies it as `CV_GET_HOST_TIMESTAMP_INTERRUPT`. It sends a vendor
device control request (`0x40`, request `0x0d`) containing the packed local
timestamp, then continues waiting for the real command response. Broadcom's
Linux 5.8.012.0 and 5.15.021.0 blobs do not demultiplex that event and instead
attempt a bulk read, which times out and aborts enrollment.

The shim changes only that event. It does not inspect or store fingerprint
payloads, remap device status values, or synthesize enrollment success.

Build and test:

```sh
make clean check
```

Install and restart `fprintd`:

```sh
make install
```

The installer saves the previous service override under
`/var/lib/bcm-cv-host-event-shim`, installs the shim under `/usr/local/lib`,
and verifies that `fprintd` comes back up. Roll back with:

```sh
make rollback
```

The installed systemd service loads the resulting shared library with
`LD_PRELOAD` only in the isolated fprintd daemon. The physical-device probe is:

```sh
make tools/sync_probe
sudo systemctl stop fprintd
sudo ./tools/sync_probe
sudo systemctl start fprintd
```

The shim also logs integer-only status metadata from enrollment and identify
API calls. It never reads, copies, or persists fingerprint images, templates,
or capture buffers.

## Validation

Enroll and verify using standard fprintd tools:

```sh
fprintd-enroll -f right-index-finger "$USER"
fprintd-verify -f right-index-finger "$USER"
```

A successful verification produces `identify returned status=0`, `result=1`,
and `verify-match` in the fprintd journal. Three consecutive matches were
observed on the reference Latitude after restarting the service.

## Scope

This is a narrow compatibility shim, not replacement firmware. Firmware writes
remain intentionally out of scope because the controller accepts only signed,
customer-matched images and a failed update can brick the security controller.
