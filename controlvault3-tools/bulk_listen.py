#!/usr/bin/env python3
import time
from pathlib import Path
import usb.core
import usb.util

VID = 0x0a5c
PID = 0x5842
IFACE = 0
BULK_IN = 0x81

Path("captures").mkdir(exist_ok=True)
log = Path("captures/bulk-in-idle.log")

dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    raise SystemExit("ControlVault not found")

usb.util.claim_interface(dev, IFACE)

print("Listening on bulk IN 0x81. Ctrl+C to stop.")
try:
    with log.open("a") as f:
        while True:
            try:
                data = bytes(dev.read(BULK_IN, 512, timeout=1000))
                line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {data.hex(' ')}"
                print(line)
                f.write(line + "\n")
                f.flush()
            except usb.core.USBTimeoutError:
                pass
finally:
    usb.util.release_interface(dev, IFACE)
    print(f"Log written to {log}")
