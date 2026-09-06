#!/usr/bin/env python3
import struct
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cv3_firmware_controller import ControllerError, parse_release, parse_sensor_bundle


class FirmwareControllerTests(unittest.TestCase):
    def test_release_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bcm_cv_current_version.txt").write_text(
                "01020000_515021_0\nversion: 5.15.021.0\nSBI_VERSION: 240\n",
                encoding="ascii",
            )
            release = parse_release(root)
            self.assertEqual(release["aai_tuple"], (5, 15, 21, 0))
            self.assertEqual(release["sbi"], 240)

    def test_sensor_catalog(self):
        version = b"1.2.3"
        catalog_end = 24 + 8 + len(version) + 16
        payload = b"IMAGE"
        signature = b"SIG!"
        total = catalog_end + len(payload) + len(signature)
        blob = (
            b"bcmSensorFirmwar"
            + struct.pack(">II", total, 1)
            + struct.pack(">II", 12, len(version))
            + version
            + struct.pack(">IIII", len(payload), len(signature), catalog_end, catalog_end + len(payload))
            + payload
            + signature
        )
        with tempfile.NamedTemporaryFile() as stream:
            stream.write(blob)
            stream.flush()
            result = parse_sensor_bundle(Path(stream.name))
        self.assertEqual(result["images"][0]["sensor_type"], 12)
        self.assertEqual(result["images"][0]["version"], "1.2.3")

    def test_rejects_bad_magic(self):
        with tempfile.NamedTemporaryFile() as stream:
            stream.write(b"not firmware")
            stream.flush()
            with self.assertRaises(ControllerError):
                parse_sensor_bundle(Path(stream.name))


if __name__ == "__main__":
    unittest.main()
