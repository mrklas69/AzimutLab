"""Regrese mapování ZABAGED komunikací na ISOM liniové kanály."""

import sys
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "connectors"))

from zabaged import is_unmaintained_cesta_trace, map_path_to_isom  # noqa: E402


class ZabagedMappingTest(unittest.TestCase):
    def test_unmaintained_cesta_is_trace_not_path(self) -> None:
        props = {"typcesty_k": "025", "povrch_k": "O"}

        self.assertTrue(is_unmaintained_cesta_trace("Cesta", props))
        with self.assertRaisesRegex(ValueError, "typcesty_k=025"):
            map_path_to_isom("Cesta", props)

    def test_maintained_cesta_stays_path(self) -> None:
        props = {"typcesty_k": "026", "povrch_k": "T"}

        self.assertFalse(is_unmaintained_cesta_trace("Cesta", props))
        self.assertEqual(map_path_to_isom("Cesta", props), 503)


if __name__ == "__main__":
    unittest.main()
