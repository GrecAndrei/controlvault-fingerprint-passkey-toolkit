#!/usr/bin/env python3
import time
from pathlib import Path
import usb.core
import usb.util

VID = 0x0a5c
PID = 0x5842
IFACE = 0
INT_EP = 0x85

Path("captures").mkdir(exist_ok=True)
log = Path("captures/interrupt-events.log")

dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    raise SystemExit("ControlVault not found")

usb.util.claim_interface(dev, IFACE)

print("Listening on ControlVault interrupt endpoint 0x85.")
print("Touch fingerprint sensor, insert/remove smartcard, then Ctrl+C.")
try:
    with log.open("a") as f:
        while True:
            try:
                data = bytes(dev.read(INT_EP, 64, timeout=1000))
                line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {data.hex(' ')}"
                print(line)
                f.write(line + "\n")
                f.flush()
            except usb.core.USBTimeoutError:
                pass
finally:
    usb.util.release_interface(dev, IFACE)
    print(f"Log written to {log}")
