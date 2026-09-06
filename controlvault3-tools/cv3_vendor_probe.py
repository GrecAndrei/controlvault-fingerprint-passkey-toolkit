#!/usr/bin/env python3
import argparse
import datetime as dt
import threading
import time
from pathlib import Path

import usb.core
import usb.util


VID = 0x0A5C
PID = 0x5842

IFACE = 0
BULK_IN = 0x81
INT_IN = 0x85

CAPTURE_DIR = Path("captures")
CAPTURE_DIR.mkdir(exist_ok=True)


def ts() -> str:
    return dt.datetime.now().isoformat(timespec="milliseconds")


def hx(data: bytes) -> str:
    return data.hex(" ")


def find_device():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        raise SystemExit("ControlVault 3 not found: 0a5c:5842")
    return dev


def listener(dev, ep, size, name, stop_event, logfile):
    while not stop_event.is_set():
        try:
            data = bytes(dev.read(ep, size, timeout=200))
            if data:
                line = f"{ts()} RX {name} ep=0x{ep:02x} len={len(data)} data={hx(data)}"
                print(line, flush=True)
                logfile.write(line + "\n")
                logfile.flush()
        except usb.core.USBTimeoutError:
            continue
        except usb.core.USBError as e:
            line = f"{ts()} RX {name} ep=0x{ep:02x} USBError {e}"
            print(line, flush=True)
            logfile.write(line + "\n")
            logfile.flush()
            time.sleep(0.25)


def probe_in(dev, bm_request_type, b_request, w_value, w_index, length, timeout_ms):
    try:
        data = bytes(
            dev.ctrl_transfer(
                bm_request_type,
                b_request,
                w_value,
                w_index,
                length,
                timeout=timeout_ms,
            )
        )
        return "OK", data, None
    except usb.core.USBTimeoutError as e:
        return "TIMEOUT", b"", str(e)
    except usb.core.USBError as e:
        # PIPE usually means STALL.
        return "USBERR", b"", str(e)


def main():
    ap = argparse.ArgumentParser(
        description="Conservative Broadcom ControlVault 3 vendor-control probe"
    )
    ap.add_argument("--start", type=lambda x: int(x, 0), default=0x00)
    ap.add_argument("--end", type=lambda x: int(x, 0), default=0x1F)
    ap.add_argument("--delay", type=float, default=0.25)
    ap.add_argument("--length", type=int, default=64)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument(
        "--bm",
        nargs="+",
        default=["0xc0", "0xc1", "0xc2"],
        help="bmRequestType values. Default: read/vendor-ish only: 0xc0 0xc1 0xc2",
    )
    args = ap.parse_args()

    bms = [int(x, 0) for x in args.bm]

    dev = find_device()
    print(f"{ts()} Found Broadcom ControlVault 3 0x{VID:04x}:0x{PID:04x}")

    cfg = dev.get_active_configuration()
    print(f"{ts()} Active configuration: {cfg.bConfigurationValue}")

    # Interface 0 has no kernel driver in your baseline, but handle it anyway.
    try:
        if dev.is_kernel_driver_active(IFACE):
            print(f"{ts()} Detaching kernel driver from interface {IFACE}")
            dev.detach_kernel_driver(IFACE)
    except (NotImplementedError, usb.core.USBError):
        pass

    usb.util.claim_interface(dev, IFACE)
    print(f"{ts()} Claimed interface {IFACE}")

    out_path = CAPTURE_DIR / f"cv3-vendor-probe-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

    stop_event = threading.Event()

    with out_path.open("w", encoding="utf-8") as log:
        log.write(f"{ts()} ControlVault 3 vendor probe\n")
        log.write(f"VID=0x{VID:04x} PID=0x{PID:04x} IFACE={IFACE}\n")
        log.write(f"bm={','.join(hex(x) for x in bms)} requests=0x{args.start:02x}..0x{args.end:02x}\n")
        log.flush()

        threads = [
            threading.Thread(
                target=listener,
                args=(dev, BULK_IN, 512, "bulk-in", stop_event, log),
                daemon=True,
            ),
            threading.Thread(
                target=listener,
                args=(dev, INT_IN, 64, "int-in", stop_event, log),
                daemon=True,
            ),
        ]

        for t in threads:
            t.start()

        print()
        print("Now touch/swipe the fingerprint sensor while this runs.")
        print("This only sends vendor IN control requests, no payload writes.")
        print("Ctrl+C to stop early.")
        print()

        try:
            for bm in bms:
                for req in range(args.start, args.end + 1):
                    # Try a few conservative index/value combinations.
                    combos = [
                        (0x0000, 0x0000),
                        (0x0000, IFACE),
                        (0x0001, IFACE),
                    ]

                    for w_value, w_index in combos:
                        status, data, err = probe_in(
                            dev,
                            bm,
                            req,
                            w_value,
                            w_index,
                            args.length,
                            args.timeout,
                        )

                        if status == "OK":
                            line = (
                                f"{ts()} CTRL_IN bm=0x{bm:02x} req=0x{req:02x} "
                                f"wValue=0x{w_value:04x} wIndex=0x{w_index:04x} "
                                f"len={len(data)} data={hx(data)}"
                            )
                        else:
                            line = (
                                f"{ts()} CTRL_IN bm=0x{bm:02x} req=0x{req:02x} "
                                f"wValue=0x{w_value:04x} wIndex=0x{w_index:04x} "
                                f"{status} {err}"
                            )

                        print(line, flush=True)
                        log.write(line + "\n")
                        log.flush()

                        time.sleep(args.delay)

        except KeyboardInterrupt:
            print(f"\n{ts()} Stopping...")

        finally:
            stop_event.set()
            time.sleep(0.5)
            usb.util.release_interface(dev, IFACE)
            print(f"{ts()} Released interface {IFACE}")
            print(f"{ts()} Log: {out_path}")


if __name__ == "__main__":
    main()
