"""Testy poledníkového filtru Png2Line.

Testujeme čistou geometrii po vektorizaci, ne neuronový model: vstupem jsou
polyline v paper µm a výstupem seznam bez magnetických poledníků.
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "model" / "png2line"))

from north_grid import filter_north_grid  # noqa: E402


def _line(angle_deg: float, offset_um: float, t0: float, t1: float) -> list[tuple[float, float]]:
    """Přímka zadaná směrem a kolmým offsetem.

    `t` běží po ose linie, `offset_um` je vzdálenost v normálovém směru. Tím
    přesně skládáme pravidelný grid bez ruční trigonometrické algebry v testech.
    """
    import math

    th = math.radians(angle_deg)
    direction = (math.cos(th), math.sin(th))
    normal = (-math.sin(th), math.cos(th))
    return [
        (offset_um * normal[0] + t0 * direction[0], offset_um * normal[1] + t0 * direction[1]),
        (offset_um * normal[0] + t1 * direction[0], offset_um * normal[1] + t1 * direction[1]),
    ]


def _bend_near_axis(angle_deg: float, offset_um: float) -> list[tuple[float, float]]:
    """Krátká křivější voda poblíž poledníku: podobný směr nestačí k odstranění."""
    a = _line(angle_deg, offset_um, -2_000.0, 0.0)
    b = _line(angle_deg + 24.0, offset_um + 600.0, 0.0, 2_000.0)
    return [a[0], a[1], b[1]]


class NorthGridTest(unittest.TestCase):
    def test_regular_grid_removes_interrupted_fragments(self) -> None:
        angle = 77.0
        polylines = [
            _line(angle, -30_000.0, -20_000.0, 20_000.0),   # seed 0
            _line(angle, 0.0, -20_000.0, 20_000.0),         # seed 1
            _line(angle, 30_000.0, -20_000.0, 20_000.0),    # seed 2
            _line(angle, 0.0, 22_000.0, 23_200.0),          # krátký přerušený poledník
            _bend_near_axis(angle, 0.0),                    # skutečná voda poblíž osy
        ]

        kept, stats = filter_north_grid(polylines)

        self.assertEqual(stats.removed_ids, (0, 1, 2, 3))
        self.assertEqual(kept, [polylines[4]])
        self.assertEqual(len(stats.grid_centers_um), 3)
        self.assertAlmostEqual(stats.spacing_median_um, 30_000.0, delta=1.0)

    def test_single_straight_canal_is_not_removed(self) -> None:
        polylines = [_line(90.0, 0.0, -40_000.0, 40_000.0)]

        kept, stats = filter_north_grid(polylines)

        self.assertEqual(kept, polylines)
        self.assertEqual(stats.removed_ids, ())

    def test_grid_with_non_default_spacing_is_detected(self) -> None:
        """Rozestup 20 mm (≈ 1:15000) musí grid najít — periodu bereme z dat.

        Dřívější pevné okno 30 mm ±7 mm by tento grid tiše minulo. Test hlídá,
        že detektor funguje napříč měřítky, ne jen na měřeném Buschdörfl 30 mm.
        """
        angle = 88.0
        polylines = [
            _line(angle, -20_000.0, -20_000.0, 20_000.0),
            _line(angle, 0.0, -20_000.0, 20_000.0),
            _line(angle, 20_000.0, -20_000.0, 20_000.0),
            _line(angle, 40_000.0, -20_000.0, 20_000.0),
        ]

        kept, stats = filter_north_grid(polylines)

        self.assertEqual(stats.removed_ids, (0, 1, 2, 3))
        self.assertEqual(kept, [])
        self.assertAlmostEqual(stats.spacing_median_um, 20_000.0, delta=1.0)

    def test_parallel_lines_without_regular_spacing_are_kept(self) -> None:
        angle = 90.0
        polylines = [
            _line(angle, 0.0, -20_000.0, 20_000.0),
            _line(angle, 12_000.0, -20_000.0, 20_000.0),
            _line(angle, 41_000.0, -20_000.0, 20_000.0),
        ]

        kept, stats = filter_north_grid(polylines)

        self.assertEqual(kept, polylines)
        self.assertEqual(stats.removed_ids, ())

    def test_short_straight_fragment_must_lie_in_narrow_grid_band(self) -> None:
        angle = 77.0
        polylines = [
            _line(angle, -30_000.0, -20_000.0, 20_000.0),
            _line(angle, 0.0, -20_000.0, 20_000.0),
            _line(angle, 30_000.0, -20_000.0, 20_000.0),
            _line(angle, 1_500.0, 22_000.0, 23_200.0),      # rovné, ale moc daleko od osy
        ]

        kept, stats = filter_north_grid(polylines)

        self.assertEqual(stats.removed_ids, (0, 1, 2))
        self.assertEqual(kept, [polylines[3]])


if __name__ == "__main__":
    unittest.main()
