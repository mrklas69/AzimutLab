"""Regrese no-silent-fallback kontraktu stringového `.omap` ořezu."""
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "generator"))

from cut import OmapFormatError, clip_omap  # noqa: E402

_CLIP = [(-10, -10), (10, -10), (10, 10), (-10, 10)]


class CutFormatTest(unittest.TestCase):
    @staticmethod
    @contextmanager
    def _workspace():
        root = _REPO_ROOT / "tests" / f".tmp_cut_{uuid.uuid4().hex}"
        root.mkdir()
        try:
            yield root
        finally:
            shutil.rmtree(root)

    def test_missing_objects_block_fails_loudly(self) -> None:
        with self._workspace() as root:
            path = root / "broken.omap"
            original = "<map></map>"
            path.write_text(original, encoding="utf-8")
            with self.assertRaisesRegex(OmapFormatError, "chybí podporovaný"):
                clip_omap(path, _CLIP)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_non_numeric_coordinate_fails_without_rewriting_file(self) -> None:
        with self._workspace() as root:
            path = root / "broken.omap"
            original = (
                '<map><objects count="1"><object type="0" symbol="1">'
                '<coords count="1">x 2;</coords></object></objects></map>'
            )
            path.write_text(original, encoding="utf-8")
            with self.assertRaisesRegex(OmapFormatError, "nečíselná souřadnice"):
                clip_omap(path, _CLIP)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_paired_object_without_coords_fails_loudly(self) -> None:
        with self._workspace() as root:
            path = root / "broken.omap"
            path.write_text(
                '<map><objects count="1"><object type="0" symbol="1">'
                "<text>bez souřadnic</text></object></objects></map>",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(OmapFormatError, "nemá párový <coords>"):
                clip_omap(path, _CLIP)

    def test_declared_count_must_match_supported_objects(self) -> None:
        with self._workspace() as root:
            path = root / "broken.omap"
            path.write_text(
                '<map><objects count="1"><object type="0" symbol="1"/></objects></map>',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(OmapFormatError, "deklaruje 1 objektů"):
                clip_omap(path, _CLIP)

    def test_valid_inside_point_is_preserved(self) -> None:
        with self._workspace() as root:
            path = root / "valid.omap"
            original = (
                '<map><objects count="1"><object type="0" symbol="1">'
                '<coords count="1">1 2;</coords></object></objects></map>'
            )
            path.write_text(original, encoding="utf-8")
            self.assertEqual(clip_omap(path, _CLIP), (1, 0))
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_bordered_area_split_requires_fill_and_border_symbols(self) -> None:
        with self._workspace() as root:
            path = root / "broken.omap"
            original = (
                '<map><symbols><symbol code="301" id="7"/></symbols>'
                '<objects count="0"></objects></map>'
            )
            path.write_text(original, encoding="utf-8")
            with self.assertRaisesRegex(OmapFormatError, "chybí symboly"):
                clip_omap(path, _CLIP)
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
