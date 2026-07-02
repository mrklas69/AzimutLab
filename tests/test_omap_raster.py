"""Unit testy omap_raster — staticky AREA_ZORDER guard + Y-fixture (audit 260702-B1, Sez. 175 A5 (5)).

AREA_ZORDER je SSoT Y-schematu (Png2Area) a zdroj omap_export.AREA_CODES. Sez. 110 bug:
generator uz tehdy psal vodu jako "301", ale AREA_ZORDER mel stale "301.1" -> voda se tise
ztracela z Y (drift mezi rasterizacnim schematem a skutecne zapisovanymi kody), odhaleno az
vizualne na realnych datech, ne testem. Tenhle soubor drzi tri veci OFFLINE (bez CUDA, bez
realneho korpusu/build_pair), aby se stejna trida driftu nemohla vratit potichu:

1. kazdy kod v AREA_ZORDER musi jit rozresit na symbol id v `template_classic.omap` (jinak
   `omap_export` na kodu spadne az pri psani konkretniho objektu, ne staticky pri importu);
2. "301.1" je jen ALIAS na vodni label (fill-only varianta z `cut._emit_bordered_area`), nesmi
   se stat druhym prvkem AREA_ZORDER (dvoji zapocteni / rozjeti od omap_export.AREA_CODES);
3. mini fixture .omap (2 plosne objekty, bez korpusu/site) -> `rasterize()` musi dat nenulove
   px pro KAZDY area kod v nem pritomny (dynamicky doplnek bodu 1-2: staticka shoda kodu jeste
   nezarucuje, ze rasterizace geometrii skutecne vykresli).

Spoustet z korene: python tests/test_omap_raster.py
"""
import pathlib
import sys
import tempfile
import unittest

_GEN = pathlib.Path(__file__).resolve().parents[1] / "generator"
if str(_GEN) not in sys.path:
    sys.path.insert(0, str(_GEN))

from omap_raster import AREA_ZORDER, CODE_TO_LABEL, rasterize  # noqa: E402
from omap_symbols import parse_symbol_ids  # noqa: E402

TEMPLATE_PATH = _GEN / "template_classic.omap"


class AreaZorderTemplateGuardTest(unittest.TestCase):
    def test_all_area_zorder_codes_resolve_in_template(self) -> None:
        doc = TEMPLATE_PATH.read_text(encoding="utf-8")
        # parse_symbol_ids sam hlasite selze (ValueError), kdyz nejaky kod v template chybi —
        # test jen overuje, ze k tomu na aktualnim template + AREA_ZORDER nedochazi.
        ids = parse_symbol_ids(doc, set(AREA_ZORDER), source=TEMPLATE_PATH.name)
        self.assertEqual(set(ids), set(AREA_ZORDER))


class Water301AliasGuardTest(unittest.TestCase):
    def test_301_1_is_alias_not_separate_zorder_entry(self) -> None:
        self.assertNotIn("301.1", AREA_ZORDER)
        self.assertIn("301", AREA_ZORDER)
        self.assertEqual(CODE_TO_LABEL["301.1"], CODE_TO_LABEL["301"])


def _rect(x0: int, y0: int, x1: int, y1: int) -> str:
    """4-bodovy uzavreny prsten (paper mikrom), posledni bod flag 18 = close (izomorf omap_export)."""
    return f"{x0} {y0} 0;{x1} {y0} 0;{x1} {y1} 0;{x0} {y1} 18;"


def _mini_omap(tmp_dir: pathlib.Path) -> pathlib.Path:
    """Synteticky .omap se 2 plosnymi objekty (521 budova, 301 voda) v ruznych ctvrtinach
    platna — zadna zavislost na Livelox korpusu/build_pair/site."""
    doc = (
        '<map version="9">'
        '<symbols>'
        '<symbol code="521" id="0" type="4"/>'
        '<symbol code="301" id="1" type="16"/>'
        '</symbols>'
        '<objects count="2">'
        f'<object type="0" symbol="0"><coords count="4">{_rect(4062, 4062, 5937, 5937)}</coords></object>'
        f'<object type="0" symbol="1"><coords count="4">{_rect(-5937, -5937, -4062, -4062)}</coords></object>'
        '</objects>'
        '</map>'
    )
    path = tmp_dir / "mini.omap"
    path.write_text(doc, encoding="utf-8")
    return path


class MiniRasterizeYFixtureTest(unittest.TestCase):
    """Mini build_pair-Y fixture (Sez. 175 A5 recept bod 5): kazdy area kod pritomny v .omap
    musi mit nenulove px v Y — dynamicky doplnek staticke kontroly vyse (ta chyta chybejici
    symbol v template, tahle chyta i geometrii, ktera se z nejakeho duvodu nevykresli)."""

    def test_every_area_code_in_omap_has_nonzero_y_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            omap_path = _mini_omap(pathlib.Path(tmp))
            meta = {"canvas": (64, 64), "georef": {"bbox_sjtsk": (0.0, 0.0, 200.0, 200.0)}, "scale": 10000}
            label = rasterize(omap_path, meta)
            for code in ("521", "301"):
                cls = CODE_TO_LABEL[code]
                self.assertGreater(int((label == cls).sum()), 0, f"kod {code} v .omap, ale 0 px v Y")


if __name__ == "__main__":
    unittest.main(verbosity=2)
