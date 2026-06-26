"""Testy diskriminátorů terrain bodů v points_common (Sez. 170): opening, ecc, kolinearita.

Diskriminátory jsou volitelné (default off) → ostatní detektory (water/vegetation/manmade)
zůstávají beze změny; testy to hlídají i u nových filtrů."""
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "isom_scan"))

from points_common import (  # noqa: E402
    Candidate,
    component_candidates,
    eccentricity,
    reject_collinear_runs,
)

_PARAMS = dict(min_size=2, max_size=15, min_area=3, max_area=400,
               min_fill=0.0, max_fill=1.0, close_px=0)


def _cand(code: str, x: float, y: float) -> Candidate:
    return Candidate(code=code, score=1.0, x=x, y=y, bbox=(x, y, x + 1, y + 1), area_px=9, fill=0.7)


class EccentricityTest(unittest.TestCase):
    def test_disk_is_round(self) -> None:
        yy, xx = np.ogrid[:21, :21]
        disk = (xx - 10) ** 2 + (yy - 10) ** 2 <= 36
        self.assertLess(eccentricity(disk), 0.3)

    def test_line_is_elongated(self) -> None:
        line = np.zeros((5, 20), bool)
        line[2, :] = True
        self.assertGreater(eccentricity(line), 0.95)

    def test_degenerate_returns_zero(self) -> None:
        self.assertEqual(eccentricity(np.zeros((4, 4), bool)), 0.0)


class OpeningTest(unittest.TestCase):
    """open_px odtrhne dvě tečky slité tenkým mostem (vzor: kupka 109 slitá s vrstevnicí)."""

    def _bridged_blobs(self) -> np.ndarray:
        mask = np.zeros((20, 30), bool)
        mask[6:11, 3:8] = True      # blob A 5x5
        mask[6:11, 22:27] = True     # blob B 5x5
        mask[8, 8:22] = True         # tenký 1px most
        return mask

    def test_without_opening_fused_blob_too_wide(self) -> None:
        # Slitá komponenta má šířku ~24 px > max_size 15 → vypadne.
        out = component_candidates(self._bridged_blobs(), **_PARAMS, open_px=0)
        self.assertEqual(len(out), 0)

    def test_opening_separates_into_two(self) -> None:
        out = component_candidates(self._bridged_blobs(), **_PARAMS, open_px=1)
        self.assertEqual(len(out), 2)

    def test_default_open_px_is_noop(self) -> None:
        # Bez mostu jedna kompaktní komponenta; open_px default nesmí nic změnit.
        mask = np.zeros((20, 20), bool)
        mask[6:11, 6:11] = True
        self.assertEqual(component_candidates(mask, **_PARAMS), [(slice(6, 11), slice(6, 11))])


class MaxEccentricityTest(unittest.TestCase):
    def _disk_and_line(self) -> np.ndarray:
        yy, xx = np.ogrid[:20, :20]
        disk = (xx - 5) ** 2 + (yy - 10) ** 2 <= 9
        line = np.zeros((20, 20), bool)
        line[9:11, 12:19] = True  # 2x7 — projde min_size, ale je protáhlá (vysoká ecc)
        return disk | line

    def test_filter_off_keeps_both(self) -> None:
        out = component_candidates(self._disk_and_line(), **_PARAMS, max_eccentricity=None)
        self.assertEqual(len(out), 2)

    def test_filter_drops_elongated(self) -> None:
        out = component_candidates(self._disk_and_line(), **_PARAMS, max_eccentricity=0.8)
        self.assertEqual(len(out), 1)


class CollinearTest(unittest.TestCase):
    _KW = dict(radius=25.0, min_neighbors=2, collinear_tol_deg=20.0)

    def test_middle_of_run_rejected(self) -> None:
        run = [_cand("109", 0, 0), _cand("109", 20, 0), _cand("109", 40, 0)]
        kept = reject_collinear_runs(run, **self._KW)
        self.assertEqual([c.x for c in kept], [0, 40])  # prostřední (2 kolineární sousedi) pryč

    def test_isolated_point_kept(self) -> None:
        solo = [_cand("109", 100, 100)]
        self.assertEqual(len(reject_collinear_runs(solo, **self._KW)), 1)

    def test_per_code_does_not_mix(self) -> None:
        # 109 body 0 a 40 jsou 40 px > radius → žádný nemá souseda; 111 mezi nimi se nepočítá.
        mixed = [_cand("109", 0, 0), _cand("111", 20, 0), _cand("109", 40, 0)]
        self.assertEqual(len(reject_collinear_runs(mixed, **self._KW)), 3)


if __name__ == "__main__":
    unittest.main()
