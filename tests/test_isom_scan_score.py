"""Regresní testy skórování ISOM-scan benchmarku."""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "isom_scan"))

from score import match_points  # noqa: E402


class IsomScanScoreTest(unittest.TestCase):
    def test_match_points_maximizes_true_positives_before_distance(self) -> None:
        # Nejbližší lokální hrana g0-p0 by greedy algoritmu zablokovala druhý validní pár.
        # Správná metrika musí nejdřív maximalizovat TP a až potom řešit součet vzdáleností.
        gt_pts = [{"x": 0, "y": 0}, {"x": 0, "y": 3}]
        pred_pts = [{"x": 0, "y": 1}, {"x": 0, "y": -2}]

        self.assertEqual(match_points(gt_pts, pred_pts, tol=3), (2, 0, 0))

    def test_match_points_handles_empty_sides(self) -> None:
        self.assertEqual(match_points([], [{"x": 1, "y": 1}], tol=3), (0, 1, 0))
        self.assertEqual(match_points([{"x": 1, "y": 1}], [], tol=3), (0, 0, 1))


if __name__ == "__main__":
    unittest.main()
