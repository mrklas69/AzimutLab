"""Regrese počtu kontrol generované fialové tratě."""
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "model"))

from purple import _course_points  # noqa: E402


class PurpleCourseTest(unittest.TestCase):
    def test_course_has_five_to_twelve_controls(self) -> None:
        counts = {
            len(_course_points(np.random.default_rng(seed), 512, 512)) - 2
            for seed in range(500)
        }
        self.assertEqual(min(counts), 5)
        self.assertEqual(max(counts), 12)


if __name__ == "__main__":
    unittest.main()
