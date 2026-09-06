#!/usr/bin/env python3
import usb.core
import usb.util
import time

VID = 0x0a5c
PID = 0x5842

dev = usb.core.find(idVendor=VID, idProduct=PID)

if dev is None:
    raise SystemExit("ControlVault not found")

print(f"Found: {hex(VID)}:{hex(PID)}")
print(f"Manufacturer: {usb.util.get_string(dev, dev.iManufacturer)}")
print(f"Product:      {usb.util.get_string(dev, dev.iProduct)}")
print(f"Serial:       {usb.util.get_string(dev, dev.iSerialNumber)}")

cfg = dev.get_active_configuration()
print(f"Configuration: {cfg.bConfigurationValue}")

for intf in cfg:
    print()
    print(f"Interface {intf.bInterfaceNumber}")
    print(f"  Class:    {hex(intf.bInterfaceClass)}")
    print(f"  Subclass: {hex(intf.bInterfaceSubClass)}")
    print(f"  Protocol: {hex(intf.bInterfaceProtocol)}")

    for ep in intf:
        direction = "IN" if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT"
        transfer = usb.util.endpoint_type(ep.bmAttributes)
        print(f"  Endpoint {hex(ep.bEndpointAddress)} {direction}")
        print(f"    Type: {transfer}")
        print(f"    Max packet: {ep.wMaxPacketSize}")

print("\nTrying to claim ControlVault interface 0...")

if dev.is_kernel_driver_active(0):
    print("Kernel driver active on interface 0, detaching")
    dev.detach_kernel_driver(0)

usb.util.claim_interface(dev, 0)
print("Claimed interface 0")

ep_interrupt = 0x85

print("Listening briefly on interrupt endpoint 0x85...")
for i in range(10):
    try:
        data = dev.read(ep_interrupt, 64, timeout=500)
        print(f"INT IN: {bytes(data).hex(' ')}")
    except usb.core.USBTimeoutError:
        print("timeout")
    time.sleep(0.2)

usb.util.release_interface(dev, 0)
print("Released interface 0")
