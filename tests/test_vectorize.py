"""Smoke testy vektorizace masky linií → polyline (model/vectorize.py, Sez. 132).

Čistě CPU/numpy (žádný model ani sken) — ověřuje geometrické jádro „.omap assembly" kroku:
RDP zjednodušení, trasování kostry na polyline a round-trip rasterizace (ztráta tvaru malá)."""
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "model"))

from vectorize import _rdp, mask_to_polylines, rasterize_polylines  # noqa: E402


class VectorizeTest(unittest.TestCase):
    def test_rdp_collapses_near_straight_run(self) -> None:
        # schodovitá kvazi-přímka → jen krajní body (kolmá odchylka < eps)
        pts = [(0, 0), (1, 0), (2, 1), (3, 1), (4, 2), (5, 2)]
        simp = _rdp(pts, eps=2.0)
        self.assertEqual(simp[0], (0, 0))
        self.assertEqual(simp[-1], (5, 2))
        self.assertLessEqual(len(simp), 3)

    def test_rdp_keeps_sharp_corner(self) -> None:
        # ostrý roh musí zůstat (odchylka >> eps)
        pts = [(0, 0), (5, 0), (10, 0), (10, 5), (10, 10)]
        simp = _rdp(pts, eps=1.0)
        self.assertIn((10, 0), simp)            # roh L-tvaru zachován

    def test_L_shape_traces_single_polyline(self) -> None:
        m = np.zeros((60, 80), dtype=bool)
        m[28:31, 5:60] = True                   # vodorovné rameno
        m[28:55, 57:60] = True                  # svislé rameno
        polys = mask_to_polylines(m, rdp_eps=2.0)
        self.assertEqual(len(polys), 1)         # L = jedna souvislá linie
        self.assertGreaterEqual(len(polys[0]), 3)   # aspoň start–roh–konec

    def test_empty_mask_returns_no_polylines(self) -> None:
        self.assertEqual(mask_to_polylines(np.zeros((40, 40), dtype=bool)), [])

    def test_polyline_covers_source_line(self) -> None:
        # vektorizovaná linie musí SLEDOVAT zdrojovou (completeness s bufferem — naše reálná metrika,
        # Wiedemann; robustní vůči PIL width kvirku, který strict IoU sráží i u dokonalého tvaru).
        from scipy.ndimage import binary_dilation
        m = np.zeros((60, 300), dtype=bool)
        m[28:31, 20:280] = True
        polys = mask_to_polylines(m, rdp_eps=2.0)
        rb = rasterize_polylines(polys, m.shape, width=3)
        rb_buf = binary_dilation(rb, iterations=2)            # toleranční buffer 2 px
        completeness = int((m & rb_buf).sum()) / int(m.sum())
        self.assertGreater(completeness, 0.9)                  # >90 % zdroje pokryto vektorem

    def test_polyline_coords_are_xy_within_bounds(self) -> None:
        # vrcholy = (x=sloupec, y=řádek) v mezích rastru
        m = np.zeros((30, 40), dtype=bool)
        m[14:17, 5:35] = True
        polys = mask_to_polylines(m, rdp_eps=2.0)
        for poly in polys:
            for x, y in poly:
                self.assertTrue(0 <= x < 40 and 0 <= y < 30)


if __name__ == "__main__":
    unittest.main()
