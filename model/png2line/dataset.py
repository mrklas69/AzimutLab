"""
dataset.py — PyTorch loader nad dlaždicemi reconstructor modelu Png2Line (Sez. 130).

`model/png2line/tile.py` předkrájel páry (X=sken RGB, Y=line label 0..N_LINE-1) na 512×512 PNG dlaždice
do `resources/line_tiles/<split>/<cid>/`. Tenhle modul je čte za běhu, na train splitu přidává augmentaci
a vrací tensory pro `model/png2line/train.py`. Izomorfní s model/png2area/dataset.py — liší se JEN:
Y má N_LINE tříd (aktuálně pozadí + watercourse/306/309/508*), čte se z resources/line_tiles/.

Augmentace (jen train split) = TÁŽ jako Png2Area (záměrně sdílený koncept):
- D4 (8 dihedrálních symetrií): flip + rot90×k NEinterpolují → liniové labely zůstanou přesně 0..N_LINE-1.
- Fialový přetisk tratě (purple.overprint_course) JEN na X — trať není mapový obsah → Y se nemění, model
  se ji učí ignorovat (A2a, Sez. 117).
- Fotometrická degradace skenu (degrade) ON-THE-FLY na X — čistý gen render → realistický sken, jiná
  realizace každou epochu. Na label Y se NEsahá (Sez. 103, [[no-degradation-in-generator-phase]]).

Normalizace: ImageNet mean/std (encoder ResNet34 je ImageNet-pretrained).

Sys.path skript (fáze B, ne balík). Importuje se z `model/png2line/train.py`.
"""
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

_REPO_ROOT = Path(__file__).resolve().parents[2]   # model/png2line/ → o dvě úrovně hloub
_TILES_DIR = _REPO_ROOT / "resources" / "line_tiles"

# generator/ na path kvůli degrade.py; model/ kvůli purple.py (sdílený A2a fialový přetisk)
sys.path.insert(0, str(_REPO_ROOT / "generator"))
sys.path.insert(0, str(_REPO_ROOT / "model"))
from degrade import degrade   # noqa: E402
from purple import overprint_course   # noqa: E402  (fialový přetisk tratě do X — Sez. 117 audit A2a)
from omap_raster import N_LINE   # noqa: E402  (SSoT počtu line tříd — guard proti stale _tiles.json)

Image.MAX_IMAGE_PIXELS = None

# ImageNet statistika (RGB, rozsah 0-1) — encoder ResNet34 je na ní pretrained.
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class LineTileDataset(Dataset):
    """Dlaždice jednoho splitu (train/val/test) jako (x, y) tensory pro Png2Line.

    x = float32 (3, 512, 512), ImageNet-normalizovaný sken RGB.
    y = int64  (512, 512), line labely 0..N_LINE-1 (0 = pozadí, 1.. liniové třídy; BEZ IGNORE).

    Parametry:
      split   : 'train' | 'val' | 'test' — který podadresář resources/line_tiles/ číst.
      augment : zapnout D4 + fialový přetisk + degradace (jen train; val/test deterministické).
      limit_cids : volitelný seznam cid/lokalit — omezí dataset (overfit gate: 1-3 mapy)."""

    def __init__(self, split: str, *, augment: bool = False,
                 limit_cids: list[str] | None = None):
        self.split = split
        self.augment = augment
        split_dir = _TILES_DIR / split
        if not split_dir.exists():
            raise RuntimeError(f"chybí {split_dir} — spusť nejdřív `python model/png2line/tile.py`")

        xpaths = sorted(split_dir.glob("*/*_x.png"))
        if limit_cids is not None:
            keep = set(limit_cids)
            xpaths = [p for p in xpaths if p.parent.name in keep]
        if not xpaths:
            raise RuntimeError(f"žádné dlaždice v {split_dir}"
                               + (f" pro cid {limit_cids}" if limit_cids else ""))
        self.xpaths = xpaths

    def __len__(self) -> int:
        return len(self.xpaths)

    def _augment(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """D4 (flip + rot90×k) na OBĚ + fialový přetisk + fotometrická degradace skenu jen na X."""
        # --- D4: náhodný hflip + rotace o k×90° (geometrie beze ztráty, labely se nemíchají) ---
        if torch.rand(1).item() < 0.5:
            x = x[:, ::-1]
            y = y[:, ::-1]
        k = int(torch.randint(0, 4, (1,)).item())
        if k:
            x = np.rot90(x, k)
            y = np.rot90(y, k)

        x = np.ascontiguousarray(x)                          # rozbij negativní stride z D4 před degrade
        # fialový přetisk tratě jen na X (Y netknuté) — PŘED degrade, ať se rozmaže jako na skenu
        x = overprint_course(x, seed=int(torch.randint(0, 2 ** 31 - 1, (1,)).item()))
        # fotometrická degradace jen na X (čistý gen render → sken), label Y se nedotýká
        seed = int(torch.randint(0, 2 ** 31 - 1, (1,)).item())
        x = degrade(x, seed=seed)                            # (H,W,3) uint8 → uint8
        return x, np.ascontiguousarray(y)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        xp = self.xpaths[idx]
        yp = xp.with_name(xp.name.replace("_x.png", "_y.png"))
        x = np.asarray(Image.open(xp).convert("RGB"), dtype=np.uint8)
        y = np.asarray(Image.open(yp), dtype=np.uint8)

        if self.augment:
            x, y = self._augment(x, y)

        xf = x.astype(np.float32) / 255.0
        xf = (xf - _IMAGENET_MEAN) / _IMAGENET_STD
        xt = torch.from_numpy(xf.transpose(2, 0, 1)).contiguous()   # (3,H,W)
        yt = torch.from_numpy(y.astype(np.int64))                   # (H,W), 0..N_LINE-1
        return xt, yt


def class_weights() -> list[float]:
    """Median-freq váhy spočtené v tile.py (z TRAIN dlaždic) — čteme z _tiles.json (SSoT, DRY).

    Guard (no silent fallback, Sez. 110): _tiles.json může být STALE vůči aktuálnímu N_LINE
    (rozšíření scope linií) → mismatch délky vah / n_line by jinak prošel tiše do CrossEntropyLoss."""
    import json
    tpath = _TILES_DIR / "_tiles.json"
    data = json.loads(tpath.read_text(encoding="utf-8"))
    weights = data["class_weights_list"]
    meta_n = data.get("_meta", {}).get("n_line")
    if meta_n != N_LINE or len(weights) != N_LINE:
        raise RuntimeError(
            f"_tiles.json je STALE vůči aktuálnímu schématu: _meta.n_line={meta_n}, "
            f"len(class_weights_list)={len(weights)}, ale omap_raster.N_LINE={N_LINE}. "
            f"Přestav dlaždice: `python model/png2line/tile.py`. ({tpath})")
    return weights


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for s in ("train", "val", "test"):
        try:
            ds = LineTileDataset(s, augment=(s == "train"))
        except RuntimeError as e:
            print(f"{s:<6} —  ({e})")
            continue
        x, y = ds[0]
        labs = torch.unique(y).tolist()
        print(f"{s:<6} {len(ds):>5} dlaždic   x{tuple(x.shape)} {x.dtype} "
              f"[{x.min():.2f},{x.max():.2f}]   y{tuple(y.shape)} {y.dtype} labely={labs}")
    print("class_weights:", class_weights())
