"""Regresní testy JSON kontraktu ručního ISOM markeru."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "isom_scan"))

from mark_isoms import (  # noqa: E402
    _default_markers_path,
    _make_tiles,
    _make_candidate_tiles,
    _manifest,
    _normalize_marker,
    _parse_codes,
    _parse_tile_size,
    _slugify,
    _atomic_write_json,
)


class MarkIsomsTest(unittest.TestCase):
    def test_parse_codes_accepts_isom_aliases(self) -> None:
        self.assertEqual(_parse_codes("311, 312,203.2"), ["311", "312", "203.2"])

    def test_parse_codes_rejects_duplicates(self) -> None:
        with self.assertRaisesRegex(ValueError, "opakovat"):
            _parse_codes("311,311")

    def test_default_marker_path_uses_map_folder_for_bg_scan(self) -> None:
        path = _default_markers_path(
            Path("maps/Buschdörfl/bg_scan.png"),
            ["311", "312", "313"],
            Path("isom_scan/markers"),
        )
        self.assertEqual(path.as_posix(), "isom_scan/markers/buschdorfl_311_312_313.json")

    def test_parse_tile_size_accepts_square_and_rectangular_values(self) -> None:
        self.assertEqual(_parse_tile_size("900"), (900, 900))
        self.assertEqual(_parse_tile_size("1200x800"), (1200, 800))

    def test_make_tiles_covers_bottom_right_edge(self) -> None:
        tiles = _make_tiles((2500, 1800), (1000, 1000), (1000, 1000))

        self.assertEqual(tiles[0], {"index": 0, "x": 0, "y": 0, "w": 1000, "h": 1000})
        self.assertEqual(tiles[-1]["x"] + tiles[-1]["w"], 2500)
        self.assertEqual(tiles[-1]["y"] + tiles[-1]["h"], 1800)

    def test_make_candidate_tiles_centers_on_symbol_candidates(self) -> None:
        tiles = _make_candidate_tiles(
            (5000, 6000),
            (900, 900),
            [
                {"code": "312", "x": 100, "y": 100},
                {"code": "311", "x": 2388, "y": 5157},
            ],
        )

        self.assertEqual(len(tiles), 2)
        self.assertEqual(tiles[0]["x"], 0)
        self.assertEqual(tiles[0]["y"], 0)
        self.assertIn("312", tiles[0]["codes"])
        self.assertLessEqual(tiles[1]["x"], 2388)
        self.assertGreaterEqual(tiles[1]["x"] + tiles[1]["w"], 2388)

    def test_normalize_marker_rejects_unknown_code(self) -> None:
        with self.assertRaisesRegex(ValueError, "nepovoleny"):
            _normalize_marker({"code": "999", "x": 10, "y": 20}, ["311"], (100, 100))

    def test_normalize_marker_keeps_tile_metadata(self) -> None:
        marker = _normalize_marker(
            {
                "code": "311",
                "x": 150,
                "y": 160,
                "tile": {"index": 2, "x": 100, "y": 100, "w": 500, "h": 500},
            },
            ["311"],
            (1000, 1000),
        )

        self.assertEqual(marker["tile"]["index"], 2)
        self.assertEqual(marker["x"], 150.0)

    def test_manifest_summary_counts_by_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "scan.png"
            image.write_bytes(b"fake image bytes")
            markers = [
                {"id": "a", "code": "311", "x": 1.0, "y": 2.0, "note": ""},
                {"id": "b", "code": "312", "x": 3.0, "y": 4.0, "note": ""},
                {"id": "c", "code": "312", "x": 5.0, "y": 6.0, "note": ""},
            ]
            payload = _manifest(image, (100, 100), ["311", "312"], markers, title="test")

        self.assertEqual(payload["summary"]["total"], 3)
        self.assertEqual(payload["summary"]["by_code"], {"311": 1, "312": 2})

    def test_atomic_write_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "markers.json"
            _atomic_write_json(path, {"markers": [{"code": "311", "x": 1.0, "y": 2.0}]})
            loaded = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(loaded["markers"][0]["code"], "311")

    def test_slugify_strips_diacritics(self) -> None:
        self.assertEqual(_slugify("Hamr na Jezeře"), "hamr_na_jezere")


if __name__ == "__main__":
    unittest.main()
