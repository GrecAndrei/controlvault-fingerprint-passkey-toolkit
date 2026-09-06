#!/usr/bin/env python3
import usb.core

VID = 0x0a5c
PID = 0x5842

dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    raise SystemExit("ControlVault not found")

def req(name, bm, bReq, wVal, wIdx, length):
    try:
        data = bytes(dev.ctrl_transfer(bm, bReq, wVal, wIdx, length, timeout=500))
        print(f"{name}: {data.hex(' ')}")
    except Exception as e:
        print(f"{name}: {type(e).__name__}: {e}")

print("String descriptors 0..20")
for i in range(0, 21):
    req(f"str {i}", 0x80, 0x06, (0x03 << 8) | i, 0x0409, 255)

print("\nMicrosoft OS string descriptor 0xEE")
req("str 0xEE", 0x80, 0x06, (0x03 << 8) | 0xEE, 0x0000, 255)

print("\nDescriptor type 0x25 indexes 0..7")
for i in range(0, 8):
    req(f"desc25 idx {i}", 0x80, 0x06, (0x25 << 8) | i, 0x0000, 255)
