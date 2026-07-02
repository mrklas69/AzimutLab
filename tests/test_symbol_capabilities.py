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
    SCAN_CANDIDATE,
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


def _area_zorder_from_omap_raster() -> tuple[str, ...]:
    generator_dir = _REPO_ROOT / "generator"
    if str(generator_dir) not in sys.path:
        sys.path.insert(0, str(generator_dir))
    module = importlib.import_module("omap_raster")
    return tuple(module.AREA_ZORDER)


# 523 Ruin je v registru geom="area", ale v template je to line_symbol s close-flag (dashed
# obrys bez vyplne) -> nema Y-rasterizacni tridu a zamerne NENI v AREA_ZORDER (viz omap_export.py
# komentar u AREA_CODES). Jedina zdokumentovana vyjimka; kazdy dalsi geom="area" kod BEZ zaznamu
# tady je potencialni Sez. 110 drift (capability rika "area", ale Y ho tise zahodi).
AREA_GEOM_WITHOUT_ZORDER = frozenset({"523"})


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
        self.assertEqual(capability_by_code("531").scanner_status, SCAN_LIVE_POINT)  # Sez. 158 povýšen (Png2Point)
        self.assertEqual(capability_by_code("525").scanner_status, SCAN_LIVE_POINT)  # Sez. 159 povýšen (Png2Point ⊤)
        self.assertEqual(capability_by_code("527").scanner_status, SCAN_LIVE_POINT)  # Sez. 159 povýšen (Png2Point Λ)
        self.assertEqual(capability_by_code("109").scanner_status, SCAN_LIVE_POINT)  # Sez. 161 povýšen (Png2Point hnědý disk)
        self.assertEqual(capability_by_code("111").scanner_status, SCAN_LIVE_POINT)  # Sez. 162 povýšen (Png2Point hnědý oblouk ∪)
        # 112 Pit je reconstructor-only (Png2Point scope, gen NEkreslí) → ZÁMĚRNĚ mimo capability registr:
        # generator_codes()==USED_CODES, přidání by udělalo falešnou KPI díru (orig>0/gen 0). Governance přes docs.
        # Živý Png2Line scope = JEN watercourse 304/305 (revert Sez. 156); 306/309/508 jsou kandidáti
        # (generátor je kreslí, reconstructor po revertu neumí) — registr nesmí tvrdit živý signál (anti-Goodhart).
        self.assertEqual(capability_by_code("304").scanner_status, SCAN_LIVE_LINE)
        self.assertEqual(capability_by_code("306").scanner_status, SCAN_CANDIDATE)
        self.assertEqual(capability_by_code("309").scanner_status, SCAN_CANDIDATE)
        self.assertEqual(capability_by_code("508.4").code, "508")
        self.assertEqual(capability_by_code("508").scanner_status, SCAN_CANDIDATE)

    def test_mapper_scan_wins_when_live_scanner_signal_exists(self) -> None:
        self.assertEqual(capability_by_code("204").preferred_kind, GEN_MAPPER_SCAN)
        self.assertEqual(preferred_kind_by_code("210"), GEN_MAPPER_SCAN)
        self.assertEqual(preferred_kind_by_code("419"), GEN_MAPPER_SCAN)
        self.assertEqual(preferred_kind_by_code("531"), GEN_MAPPER_SCAN)  # Sez. 158 live Png2Point signál
        self.assertEqual(preferred_kind_by_code("525"), GEN_MAPPER_SCAN)  # Sez. 159 live Png2Point signál
        self.assertEqual(preferred_kind_by_code("527"), GEN_MAPPER_SCAN)  # Sez. 159 live Png2Point signál
        self.assertEqual(preferred_kind_by_code("109"), GEN_MAPPER_SCAN)  # Sez. 161 live Png2Point signál
        self.assertEqual(preferred_kind_by_code("111"), GEN_MAPPER_SCAN)  # Sez. 162 live Png2Point signál
        self.assertEqual(capability_by_code("418").preferred_kind, GEN_PSEUDO)  # bez live signálu → pseudo
        self.assertEqual(capability_by_code("203").code, "203.2")

    def test_area_geom_capabilities_have_y_rasterization_class(self) -> None:
        """Kazdy capability zaznam s geom=="area" musi mit Y-rasterizacni tridu v
        omap_raster.AREA_ZORDER, jinak `omap_export` kod zapise, ale `omap_raster` ho tise
        vynecha z Y (presne trida bugu Sez. 110: AREA_ZORDER mel stale "301.1", generator uz
        psal "301"). Jedina zdokumentovana vyjimka je 523 Ruin (dashed obrys, zadna vyplna)."""
        area_zorder = set(_area_zorder_from_omap_raster())
        for record in CAPABILITIES:
            if record.geom != "area" or record.code in AREA_GEOM_WITHOUT_ZORDER:
                continue
            self.assertIn(record.code, area_zorder,
                          f"{record.code} ({record.name}) je geom=area v capability registru, "
                          "ale chybi v omap_raster.AREA_ZORDER -> Y ho tise zahodi")

    def test_summary_keeps_real_pseudo_mapper_split_visible(self) -> None:
        summary = summarize_by_kind()
        self.assertGreater(summary[GEN_REAL], summary[GEN_PSEUDO])
        self.assertGreaterEqual(summary[GEN_MAPPER_SCAN], 1)
        self.assertGreaterEqual(summary[GEN_MIXED], 1)
        self.assertEqual(sum(summary.values()), len(CAPABILITIES))


if __name__ == "__main__":
    unittest.main()
