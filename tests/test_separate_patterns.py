"""Regresní testy pattern separace plošných ISOM symbolů."""
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "generator"))

from separate import separate_areas  # noqa: E402

PALE_YELLOW = (254, 222, 154)
GREEN_LIGHT = (200, 232, 200)
GREEN_MID = (120, 200, 140)


def _striped_rgb(stripe_color: tuple[int, int, int], period: int = 5) -> np.ndarray:
    """Vyrobí světlý scan s pravidelným zeleným patternem pro 407/409 heuristiku."""
    rgb = np.full((200, 200, 3), PALE_YELLOW, dtype=np.uint8)
    rgb[:, ::period] = stripe_color
    return rgb


class SeparatePatternTest(unittest.TestCase):
    def test_open_scattered_green_does_not_become_407_or_409(self) -> None:
        # Regrese P1: řídká zelená kresba v open/404 ploše nesmí přes priority order ukrást masku
        # patternovým lesním třídám 407/409.
        label_map = np.full((200, 200), 4, dtype=np.uint8)
        polys = separate_areas(label_map, rgb=_striped_rgb(GREEN_LIGHT))

        self.assertEqual(len(polys.get("407", [])), 0)
        self.assertEqual(len(polys.get("409", [])), 0)
        self.assertGreater(len(polys.get("404", [])), 0)

    def test_light_green_pattern_can_split_406_into_407(self) -> None:
        # Pozitivní kontrola: brána přes label_map nesmí vypnout legitimní 407 uvnitř 406 třídy.
        label_map = np.full((200, 200), 1, dtype=np.uint8)
        polys = separate_areas(label_map, rgb=_striped_rgb(GREEN_LIGHT))

        self.assertGreater(len(polys.get("407", [])), 0)

    def test_middle_green_pattern_can_split_408_into_409(self) -> None:
        # Stejný invariant pro 409: pattern vzniká jen z odpovídající 408 GT třídy.
        label_map = np.full((200, 200), 2, dtype=np.uint8)
        polys = separate_areas(label_map, rgb=_striped_rgb(GREEN_MID))

        self.assertGreater(len(polys.get("409", [])), 0)


if __name__ == "__main__":
    unittest.main()
