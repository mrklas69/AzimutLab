"""Smoke testy sdileneho ISOM symbol indexu."""

import sys
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from isom.symbol_index import SymbolIndexError, build_symbol_index  # noqa: E402


FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "isom_symbol_index"


class SymbolIndexTest(unittest.TestCase):
    def test_draft_index_discovers_svg_by_filename(self) -> None:
        index = build_symbol_index(FIXTURES / "draft")

        self.assertEqual(len(index), 1)
        symbol = index.by_code("525")
        self.assertEqual(symbol.canonical_name, "small_tower")
        self.assertEqual(symbol.display_name, "Small Tower")
        self.assertEqual(symbol.geom, "unknown")
        self.assertEqual(symbol.colors, ("#000000",))
        self.assertEqual(symbol.descriptor["view_box"], [0.0, 0.0, 120.0, 160.0])
        self.assertAlmostEqual(symbol.descriptor["aspect_ratio"], 0.75)

    def test_strict_rejects_uncurated_draft(self) -> None:
        with self.assertRaises(SymbolIndexError):
            build_symbol_index(FIXTURES / "draft", strict=True)

    def test_curated_index_computes_terrain_footprint(self) -> None:
        index = build_symbol_index(FIXTURES / "curated", strict=True)
        symbol = index.by_code(525)

        self.assertEqual(symbol.geom, "point")
        self.assertEqual(symbol.terrain_footprint_m, {"width": 10.0, "height": 10.0})
        self.assertEqual(symbol.aliases["ocad"], ["536"])

    def test_json_projection_keeps_stable_contract(self) -> None:
        index = build_symbol_index(FIXTURES / "curated", strict=True)
        payload = index.to_json_dict()

        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["symbols"][0]["code"], "525")
        self.assertEqual(payload["symbols"][0]["files"]["svg"], "svg/525_small_tower.svg")
        # Footprint se pocita z paper size + scale, neni to dalsi rucne drzeny zdroj pravdy.
        self.assertEqual(
            payload["symbols"][0]["terrain_footprint_m"],
            {"width": 10.0, "height": 10.0},
        )


if __name__ == "__main__":
    unittest.main()
