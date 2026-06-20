"""Testy capability registru ISOM symbolu generatoru."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from isom.capabilities import (  # noqa: E402
    CAPABILITIES,
    GEN_MAPPER_SCAN,
    GEN_MIXED,
    GEN_PSEUDO,
    GEN_REAL,
    SCAN_LIVE_LINE,
    SCAN_LIVE_POINT,
    SCAN_POC,
    capability_by_code,
    generator_codes,
    preferred_kind_by_code,
    summarize_by_kind,
)


def _used_codes_from_omap_export() -> tuple[str, ...]:
    """Nacte `USED_CODES` z exportu s minimalnim sys.path setupem.

    Tohle uz je zamerne import: `omap_export.USED_CODES` ma byt odvozeny z
    `isom.capabilities.generator_codes()`. Test tak hlida, ze export skutecne
    pouziva novy SSoT a nevratil se k vlastni kopii seznamu.
    """
    generator_dir = _REPO_ROOT / "generator"
    if str(generator_dir) not in sys.path:
        sys.path.insert(0, str(generator_dir))
    module = importlib.import_module("omap_export")
    return tuple(module.USED_CODES)


class SymbolCapabilitiesTest(unittest.TestCase):
    def test_registry_matches_generator_used_codes(self) -> None:
        self.assertEqual(generator_codes(), _used_codes_from_omap_export())

    def test_codes_are_unique(self) -> None:
        codes = generator_codes()
        self.assertEqual(len(codes), len(set(codes)))

    def test_key_point_capabilities_are_classified(self) -> None:
        self.assertEqual(capability_by_code("204").generator_kind, GEN_MIXED)
        self.assertEqual(capability_by_code("210").code, "210.1")
        self.assertEqual(capability_by_code("210").generator_kind, GEN_PSEUDO)
        self.assertEqual(capability_by_code("513.1").code, "513")
        self.assertEqual(capability_by_code("417").scanner_status, SCAN_LIVE_POINT)
        self.assertEqual(capability_by_code("419").generator_kind, GEN_PSEUDO)
        self.assertEqual(capability_by_code("527").scanner_status, SCAN_POC)
        self.assertEqual(capability_by_code("306").scanner_status, SCAN_LIVE_LINE)
        self.assertEqual(capability_by_code("309").scanner_status, SCAN_LIVE_LINE)
        self.assertEqual(capability_by_code("508.4").code, "508")
        self.assertEqual(capability_by_code("508").scanner_status, SCAN_LIVE_LINE)

    def test_mapper_scan_wins_when_live_scanner_signal_exists(self) -> None:
        self.assertEqual(capability_by_code("204").preferred_kind, GEN_MAPPER_SCAN)
        self.assertEqual(preferred_kind_by_code("210"), GEN_MAPPER_SCAN)
        self.assertEqual(preferred_kind_by_code("419"), GEN_MAPPER_SCAN)
        self.assertEqual(capability_by_code("418").preferred_kind, GEN_PSEUDO)
        self.assertEqual(capability_by_code("527").preferred_kind, GEN_PSEUDO)
        self.assertEqual(capability_by_code("203").code, "203.2")

    def test_summary_keeps_real_pseudo_mapper_split_visible(self) -> None:
        summary = summarize_by_kind()
        self.assertGreater(summary[GEN_REAL], summary[GEN_PSEUDO])
        self.assertGreaterEqual(summary[GEN_MAPPER_SCAN], 1)
        self.assertGreaterEqual(summary[GEN_MIXED], 1)
        self.assertEqual(sum(summary.values()), len(CAPABILITIES))


if __name__ == "__main__":
    unittest.main()
