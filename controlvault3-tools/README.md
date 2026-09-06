# Broadcom ControlVault 3

Device:

Vendor: 0a5c
Product: 5843 (this Latitude 7400; older notes referenced 5842)

Objectives

- Enumerate USB interfaces
- Reverse engineer Interface 0
- Capture Windows traffic
- Document protocol
- Build Linux userspace driver

## Firmware controller

`cv3_firmware_controller.py` is a safe controller derived from reverse
engineering both Broadcom driver stacks. It can inventory the physical device,
validate the signed sensor-bundle structure, compare candidate AAI/SBI releases,
block downgrades, and send the Windows-compatible host timestamp request.

```sh
./cv3_firmware_controller.py device-info
sudo ./cv3_firmware_controller.py inspect /var/lib/fprint/fw
./cv3_firmware_controller.py plan drivers/extracted/16299/Drivers/cv/firmware
./cv3_firmware_controller.py sync-clock
```

Raw flashing is deliberately unavailable. Main firmware flashing reboots the
controller into SBI and writes signed data with commands 0x36/0x43/0x44/0x45;
sensor firmware uses command 0x99. A power loss, wrong customer image, or
downgrade can brick the embedded security controller. The installed 5.15.21.0
/ SBI 240 release is newer than Dell A33's 5.15.15.0 / SBI 234.
