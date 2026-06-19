"""Rychly smoke/invariant test generatoru.

Spousteni:
    python tests/smoke.py

Test neni nahrada KPI/KOMPASu. Ma chytat zakladni rozbiti generatoru pred vetsimi
zasahy do `generator.py`: vystupy existuji, `.omap` je parsovatelny, zakladni ISOM
vrstvy nejsou prazdne a seed dava byte-identicky vysledek.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_GENERATOR_DIR = _REPO_ROOT / "generator"
sys.path.insert(0, str(_GENERATOR_DIR))

from generator import generate_map  # noqa: E402
from omap_export import TEMPLATE_PATH, _parse_symbol_ids  # noqa: E402


SMOKE_ROOT = _REPO_ROOT / "temp" / "smoke_generator"

# Lidove sady maji v malem vyseku vrstevnice, vodu/pokryv i sit cest. Rozmery
# drzi beh mensi nez dev mapa, ale ne tak maly, aby smoke nahodne minul zakladni vrstvy.
SMOKE_LAT = 50.7773244
SMOKE_LON = 15.0811114
SMOKE_WIDTH_KM = 1.8
SMOKE_HEIGHT_KM = 1.8
SMOKE_SEED = 260619

REQUIRED_FILES = (
    "rgb.png",
    "meta.json",
    "mask_contours.png",
    "mask_water.png",
    "mask_paths.png",
    "mask_surfaces.png",
)
REQUIRED_ISOM_CODES = ("101", "305", "401", "502")


def _sha256(path: Path) -> str:
    """Vrati SHA-256 souboru; cteme po blocich, aby to zustalo levne i pro vetsi PNG."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_omap_objects_by_code(omap_path: Path) -> dict[str, int]:
    """Secte objekty v `.omap` podle ISOM kodu, ne podle interniho OOM symbol id.

    OOM v objektu uklada `symbol="<id>"`, zatimco lidsky smysluplny kod je napr.
    `502`. Id proto prekladame pres template, stejne jako export generatoru.
    """
    template_xml = TEMPLATE_PATH.read_text(encoding="utf-8")
    id_by_code = _parse_symbol_ids(template_xml)
    code_by_id = {symbol_id: code for code, symbol_id in id_by_code.items()}

    counts = {code: 0 for code in REQUIRED_ISOM_CODES}
    omap_xml = omap_path.read_text(encoding="utf-8")
    for match in re.finditer(r"<object\b[^>]*\bsymbol=\"(\d+)\"", omap_xml):
        code = code_by_id.get(int(match.group(1)))
        if code in counts:
            counts[code] += 1
    return counts


def _omap_path(map_dir: Path) -> Path:
    """Generator pojmenovava `.omap` podle vystupni slozky."""
    return map_dir / f"{map_dir.name}.omap"


def _prepare_output_dir(name: str) -> Path:
    """Smaze jen vlastni scratch adresar testu pod `temp/smoke_generator`."""
    run_root = SMOKE_ROOT / name
    out_dir = run_root / "smoke"
    resolved_root = SMOKE_ROOT.resolve()
    resolved_run_root = run_root.resolve()
    if resolved_root not in (resolved_run_root, *resolved_run_root.parents):
        raise RuntimeError(f"Smoke vystup mimo temp/: {resolved_run_root}")
    shutil.rmtree(run_root, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _run_smoke_generation(name: str) -> Path:
    """Vygeneruje maly real-data vysek; tolerant=False znamena zadny tichy fallback."""
    out_dir = _prepare_output_dir(name)
    return generate_map(
        SMOKE_LAT,
        SMOKE_LON,
        SMOKE_WIDTH_KM,
        SMOKE_HEIGHT_KM,
        out_dir=str(out_dir),
        seed=SMOKE_SEED,
        terrain="real",
        paths="real",
        water="real",
        surfaces="real",
        tolerant=False,
        ortho=False,
    )


class GeneratorSmokeTest(unittest.TestCase):
    def test_small_real_bbox_has_core_outputs_and_is_deterministic(self) -> None:
        first = _run_smoke_generation("run_a")
        second = _run_smoke_generation("run_b")

        for map_dir in (first, second):
            for path in (_omap_path(map_dir), *(map_dir / filename for filename in REQUIRED_FILES)):
                with self.subTest(map=str(map_dir.relative_to(SMOKE_ROOT)), file=path.name):
                    self.assertTrue(path.exists(), f"Chybi vystup {path}")
                    self.assertGreater(path.stat().st_size, 0, f"Prazdny vystup {path}")

            meta = json.loads((map_dir / "meta.json").read_text(encoding="utf-8"))
            self.assertNotIn("layer_errors", meta)
            self.assertGreater(meta["contours_vector"]["n_lines"], 0)
            self.assertGreater(meta["paths"]["count"], 0)
            self.assertIn("305", meta["water"]["symbols"])
            self.assertIn("401", meta["surfaces"]["symbols"])
            self.assertIn("502", meta["paths"]["symbols"])

            object_counts = _count_omap_objects_by_code(_omap_path(map_dir))
            for code in REQUIRED_ISOM_CODES:
                with self.subTest(map=map_dir.name, code=code):
                    self.assertGreater(object_counts[code], 0, f"ISOM {code} nema objekt v .omap")

        self.assertEqual(_sha256(_omap_path(first)), _sha256(_omap_path(second)))
        for filename in ("meta.json", "mask_contours.png", "mask_water.png", "mask_paths.png"):
            with self.subTest(deterministic_file=filename):
                self.assertEqual(_sha256(first / filename), _sha256(second / filename))


if __name__ == "__main__":
    unittest.main()
