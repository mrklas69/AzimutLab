import contextlib
import io
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "generator"))

from compare_isom import detect_version  # noqa: E402


class CompareIsomTest(unittest.TestCase):
    def test_ambiguous_version_defaults_with_warning(self) -> None:
        doc = (
            '<map><symbols><symbol id="1" code="101" name="Contour" type="2"/></symbols>'
            '<objects><object symbol="1"/></objects></map>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ambiguous.omap"
            path.write_text(doc, encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                version = detect_version(str(path))

        self.assertEqual(version, "2017-2")
        self.assertIn("VAROVÁNÍ", stderr.getvalue())
        self.assertIn("předpokládám 2017-2", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
