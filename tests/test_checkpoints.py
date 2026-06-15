"""CPU testy izolace, dokončení a explicitního povýšení checkpointu."""
import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

import torch

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "model"))

from checkpoints import finish_run, promote_run, save_best, start_run  # noqa: E402


class CheckpointWorkflowTest(unittest.TestCase):
    @staticmethod
    @contextmanager
    def _temporary_directory():
        """Vytvoří běžný workspace adresář; tempfile má na Pythonu 3.14 vadná ACL."""
        root = _REPO_ROOT / "tests" / f".tmp_checkpoints_{uuid.uuid4().hex}"
        root.mkdir()
        try:
            yield str(root)
        finally:
            shutil.rmtree(root)

    def test_training_does_not_touch_canonical_until_promote(self) -> None:
        with self._temporary_directory() as tmp:
            model_dir = Path(tmp) / "area_model"
            model_dir.mkdir()
            canonical = model_dir / "unet_best.pt"
            torch.save({"model": {"weight": torch.tensor([1.0])}}, canonical)

            run = start_run(
                model_dir,
                "png2area",
                {"seed": 7, "epochs": 2},
                "abc123",
                run_id="test-run",
            )
            save_best(
                run,
                {"weight": torch.tensor([2.0])},
                epoch=2,
                metric_name="miou",
                metric_value=0.75,
                model_metadata={"encoder": "resnet34"},
            )

            untouched = torch.load(canonical, weights_only=False)
            self.assertEqual(untouched["model"]["weight"].item(), 1.0)

            finish_run(run, "test_miou", 0.70)
            promoted = promote_run(model_dir, "test-run", "png2area")
            checkpoint = torch.load(promoted, weights_only=False)
            self.assertEqual(checkpoint["model"]["weight"].item(), 2.0)
            self.assertEqual(checkpoint["metadata"]["test_metric"]["value"], 0.70)

            promotion = json.loads((model_dir / "promoted.json").read_text(encoding="utf-8"))
            self.assertEqual(promotion["run_id"], "test-run")

    def test_existing_run_id_is_never_overwritten(self) -> None:
        with self._temporary_directory() as tmp:
            model_dir = Path(tmp) / "point_model"
            start_run(model_dir, "png2point", {}, "fingerprint", run_id="same-run")
            with self.assertRaises(FileExistsError):
                start_run(model_dir, "png2point", {}, "fingerprint", run_id="same-run")


if __name__ == "__main__":
    unittest.main()
