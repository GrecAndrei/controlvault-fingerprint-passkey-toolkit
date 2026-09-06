#!/usr/bin/env python3
import usb.core
import usb.util

VID = 0x0a5c
PID = 0x5842

dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    raise SystemExit("ControlVault not found")

def ctrl(name, bm, req, val, idx, length):
    try:
        data = bytes(dev.ctrl_transfer(bm, req, val, idx, length, timeout=1000))
        print(f"{name}: {data.hex(' ')}")
    except Exception as e:
        print(f"{name}: {type(e).__name__}: {e}")

print("Standard GET_DESCRIPTOR probes")

# Device descriptor
ctrl("device desc", 0x80, 0x06, 0x0100, 0x0000, 18)

# Config descriptor header
ctrl("config desc header", 0x80, 0x06, 0x0200, 0x0000, 9)

# Full config descriptor
ctrl("config desc full", 0x80, 0x06, 0x0200, 0x0000, 0x008b)

# String descriptors
for i in range(0, 8):
    ctrl(f"string {i}", 0x80, 0x06, (0x03 << 8) | i, 0x0409, 255)
