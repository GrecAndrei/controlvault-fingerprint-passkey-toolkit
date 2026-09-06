# ControlVault 3 protocol findings

These findings cover the Latitude 7400's Broadcom BCM58200 (`0a5c:5843`).
They were reconstructed with radare2/r2ghidra from Dell's Windows A33 driver
5.15.15.8 and Broadcom's Linux TOD driver 5.15.021.0, then checked against the
physical controller where a non-destructive command was available.

## USB transport

- Interface 0 exposes bulk OUT, bulk IN, and interrupt IN endpoint `0x85`.
- Linux `processCommand` sends bulk OUT, waits for one interrupt, then always
  attempts bulk IN. It does not distinguish asynchronous host requests.
- Windows `cvusbdrv.sys` demultiplexes the interrupt type before completing the
  pending command.
- Windows maps interrupt types 1..4 to separate `HSREQ`, `HCREQ`, `FPREQ`, and
  `CLREQ` event objects; all other ordinary responses use `CV-CMD`. These are
  notification channels, not interchangeable success/error status codes.
- Interrupt type `5` is `CV_GET_HOST_TIMESTAMP_INTERRUPT`. Windows responds
  with vendor/device/OUT control request `bmRequestType=0x40`, `bRequest=0x0d`,
  no data stage. The packed timestamp is split across `wValue` and `wIndex`.
- Timestamp bits are day 0..4, month 5..8, year since 2000 9..14, hour 15..19,
  minute 20..25, second 26..31.
- The physical controller accepted this request with status zero. The host-event
  shim now answers it and resumes waiting for the real command completion.

## Main AAI/SBI update transport

The Linux `cv_firmware_upgrade` implementation exposes the on-wire command
sequence:

- `0x36`: send the 64 KiB SBI segment, in chunks of at most `0xF00` bytes.
- `0x43`: firmware-upgrade start; sends the first `0x2B0` bytes of the AAI area.
- `0x44`: update data; sends the remainder in chunks of at most `0xF00` bytes.
- `0x45`: complete; sends the final 256-byte signature.
- Accepted image offsets are `0`, `0x10000`, and `0x20000` at the lower API;
  the Citadel wrapper permits `0` or `0x20000`.

The wrapper may reboot from AAI into SBI before writing. This path is not safe
to exercise merely as a probe: a wrong customer ID, downgrade, invalid signing
chain, or power loss can make the embedded security controller unbootable.

## Sensor firmware bundle and update

The bundle is big-endian and begins with:

1. 16-byte magic `bcmSensorFirmwar`
2. 32-bit total file size
3. 32-bit image count
4. one variable-length catalog record per image

Each record contains sensor type, version length and ASCII version, image
length, signature length, image offset, and signature offset. Payload and
signature must be contiguous and inside the declared file size. Current bundles
contain 11 images with 256-byte signatures.

Sensor updates use command `0x99`: image chunks are at most `0x800` bytes, then
the signature is sent separately. The device is polled until completion. The
driver explicitly blocks upgrades for some Goodix sensor types and asks the
controller whether a candidate is upgradeable before sending it.

## This machine

- Device: AAI 5.15.21.0, SBI 240, Citadel A0 CID7
- Sensor: type 12, firmware `3088084-109-0-3473`
- Installed Linux release: AAI 5.15.21.0, SBI 240
- Dell A33 candidate: AAI 5.15.15.0, SBI 234

The Dell A33 package is older, so the controller blocks it as a downgrade.
The installed sensor bundle contains an exact match for the physical sensor;
there is no eligible sensor update.
