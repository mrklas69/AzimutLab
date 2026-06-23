"""Regresní testy kalibračního manifestu scan-transfer vrstvy."""
import copy
import json
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "isom_scan"))

from calibration_manifest import validate_manifest  # noqa: E402


class CalibrationManifestTest(unittest.TestCase):
    def test_committed_manifest_has_required_shape(self) -> None:
        manifest_path = _REPO_ROOT / "isom_scan" / "calibration_manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        errors, warnings = validate_manifest(data)

        self.assertEqual(errors, [])
        self.assertGreater(len(warnings), 0)  # Manifest jeste ceka na rucni review/marker recall.

    def test_validator_rejects_duplicate_codes(self) -> None:
        manifest_path = _REPO_ROOT / "isom_scan" / "calibration_manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        duplicate = copy.deepcopy(data["entries"][0])
        data["entries"].append(duplicate)

        errors, _ = validate_manifest(data)

        self.assertIn("duplicitni code 109", errors)


if __name__ == "__main__":
    unittest.main()
