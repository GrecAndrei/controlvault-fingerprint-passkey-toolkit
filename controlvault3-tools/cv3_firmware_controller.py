#!/usr/bin/env python3
"""Safe ControlVault 3 firmware inventory and control utility.

The update transport was reconstructed from Broadcom's Linux and Windows
drivers.  This utility intentionally keeps flashing disabled: it validates and
plans signed updates, but will not turn a recoverable fingerprint problem into
an unrecoverable ControlVault brick.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


VID_PID = "0a5c:5843"
VERSION_FILE = "bcm_cv_current_version.txt"
SENSOR_BUNDLES = ("bcmDeviceFirmwareCitadel_1.bin", "bcmDeviceFirmwareCitadel_7.bin")
VERSION_RE = re.compile(r"version:\s*(\d+)\.(\d+)\.(\d+)\.(\d+)", re.I)
SBI_RE = re.compile(r"SBI_VERSION:\s*(\d+)", re.I)


class ControllerError(RuntimeError):
    pass


@dataclass(frozen=True)
class SensorImage:
    sensor_type: int
    version: str
    image_offset: int
    image_length: int
    signature_offset: int
    signature_length: int


def be32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise ControllerError(f"truncated u32 at 0x{offset:x}")
    return struct.unpack_from(">I", data, offset)[0]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_release(directory: Path) -> dict:
    path = directory / VERSION_FILE
    text = path.read_text(encoding="ascii").replace("\r", "")
    version_match = VERSION_RE.search(text)
    sbi_match = SBI_RE.search(text)
    if not version_match or not sbi_match:
        raise ControllerError(f"invalid version metadata: {path}")
    version = tuple(int(value) for value in version_match.groups())
    return {
        "directory": str(directory.resolve()),
        "aai": ".".join(str(value) for value in version),
        "aai_tuple": version,
        "sbi": int(sbi_match.group(1)),
        "metadata_sha256": sha256(path),
    }


def parse_sensor_bundle(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 24 or data[:16] != b"bcmSensorFirmwar":
        raise ControllerError(f"bad sensor bundle magic: {path}")
    declared_size = be32(data, 16)
    image_count = be32(data, 20)
    if declared_size != len(data):
        raise ControllerError(
            f"bundle size mismatch: header={declared_size}, file={len(data)}"
        )
    if not 1 <= image_count <= 128:
        raise ControllerError(f"implausible image count: {image_count}")

    cursor = 24
    images: list[SensorImage] = []
    for index in range(image_count):
        sensor_type = be32(data, cursor)
        version_length = be32(data, cursor + 4)
        cursor += 8
        if not 1 <= version_length <= 255 or cursor + version_length > len(data):
            raise ControllerError(f"invalid version length in record {index}")
        try:
            version = data[cursor : cursor + version_length].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ControllerError(f"non-ASCII version in record {index}") from exc
        cursor += version_length
        image_length = be32(data, cursor)
        signature_length = be32(data, cursor + 4)
        image_offset = be32(data, cursor + 8)
        signature_offset = be32(data, cursor + 12)
        cursor += 16
        if image_offset + image_length != signature_offset:
            raise ControllerError(f"non-contiguous image/signature in record {index}")
        if signature_offset + signature_length > len(data):
            raise ControllerError(f"record {index} extends past bundle")
        images.append(
            SensorImage(
                sensor_type,
                version,
                image_offset,
                image_length,
                signature_offset,
                signature_length,
            )
        )
    if images and cursor != min(image.image_offset for image in images):
        raise ControllerError(
            f"catalog ends at 0x{cursor:x}, first payload starts at "
            f"0x{min(image.image_offset for image in images):x}"
        )
    return {
        "path": str(path.resolve()),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "catalog_bytes": cursor,
        "images": [asdict(image) for image in images],
    }


def inspect_release(directory: Path) -> dict:
    release = parse_release(directory)
    files = {}
    for path in sorted(directory.iterdir()):
        if path.is_file():
            files[path.name] = {"size": path.stat().st_size, "sha256": sha256(path)}
    release["files"] = files
    release["sensor_bundles"] = [
        parse_sensor_bundle(directory / name)
        for name in SENSOR_BUNDLES
        if (directory / name).exists()
    ]
    return release


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=check)


def device_info() -> dict:
    usb = run(["lsusb", "-d", VID_PID], check=False).stdout.strip()
    if not usb:
        raise ControllerError(f"ControlVault {VID_PID} is not present")
    run(["sudo", "-n", "systemctl", "restart", "fprintd.service"])
    log = run(["journalctl", "-u", "fprintd.service", "-n", "180", "--no-pager"]).stdout

    def latest(pattern: str) -> str | None:
        matches = re.findall(pattern, log, re.I)
        return matches[-1] if matches else None

    aai = latest(r"Current AAI Version\s*=\s*([0-9.]+)")
    sbi = latest(r"Current SBI Version\s*=\s*(\d+)")
    sensor_type = latest(r"Sensor type\s*:\s*(\d+)")
    sensor_version = latest(r"Sensor firmware version on device:\s*(\S+)")
    if not aai or not sbi:
        raise ControllerError("fprintd probed the USB device but did not report firmware versions")
    return {
        "usb": usb,
        "vid_pid": VID_PID,
        "aai": aai,
        "sbi": int(sbi),
        "sensor_type": int(sensor_type) if sensor_type else None,
        "sensor_version": sensor_version,
        "service_active": run(["systemctl", "is-active", "fprintd.service"], check=False).stdout.strip()
        == "active",
    }


def version_tuple(text: str) -> tuple[int, ...]:
    values = tuple(int(value) for value in re.findall(r"\d+", text))
    if not values:
        raise ControllerError(f"invalid version: {text}")
    return values


def plan(directory: Path) -> dict:
    device = device_info()
    release = inspect_release(directory)
    candidate = tuple(release["aai_tuple"])
    installed = version_tuple(device["aai"])
    reasons = []
    if candidate < installed:
        decision = "BLOCKED_DOWNGRADE"
        reasons.append(f"candidate AAI {release['aai']} is older than device AAI {device['aai']}")
    elif release["sbi"] < device["sbi"]:
        decision = "BLOCKED_DOWNGRADE"
        reasons.append(f"candidate SBI {release['sbi']} is older than device SBI {device['sbi']}")
    elif candidate == installed and release["sbi"] == device["sbi"]:
        decision = "NO_UPDATE_NEEDED"
        reasons.append("AAI and SBI already match")
    else:
        decision = "CANDIDATE_REQUIRES_VENDOR_SIGNATURE_VERIFICATION"
        reasons.append("version is newer; flashing remains intentionally disabled")
    return {"decision": decision, "reasons": reasons, "device": device, "release": release}


def sync_clock(probe: Path) -> dict:
    if not probe.exists():
        raise ControllerError(f"timestamp probe not found: {probe}")
    stopped = False
    try:
        run(["sudo", "-n", "systemctl", "stop", "fprintd.service"])
        stopped = True
        result = run(["sudo", "-n", str(probe.resolve())])
        return {"status": "accepted", "probe_output": result.stdout.strip()}
    finally:
        if stopped:
            run(["sudo", "-n", "systemctl", "start", "fprintd.service"], check=False)


def printable(value):
    if isinstance(value, dict):
        return {key: printable(item) for key, item in value.items() if key != "aai_tuple"}
    if isinstance(value, list):
        return [printable(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe Broadcom ControlVault 3 firmware controller")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("device-info", help="probe and inventory the physical controller")
    inspect_parser = commands.add_parser("inspect", help="validate and describe a firmware release")
    inspect_parser.add_argument("directory", type=Path)
    plan_parser = commands.add_parser("plan", help="compare a release with the physical controller")
    plan_parser.add_argument("directory", type=Path)
    sync_parser = commands.add_parser("sync-clock", help="send the RE'd host timestamp request")
    sync_parser.add_argument(
        "--probe",
        type=Path,
        default=Path("/home/alex/broadcom-host-event-shim/tools/sync_probe"),
    )
    args = parser.parse_args()
    try:
        if args.command == "device-info":
            result = device_info()
        elif args.command == "inspect":
            result = inspect_release(args.directory)
        elif args.command == "plan":
            result = plan(args.directory)
        else:
            result = sync_clock(args.probe)
        result = printable(result)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(json.dumps(result, indent=2))
        return 0
    except (ControllerError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
