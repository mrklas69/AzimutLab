"""
dataset.py — PyTorch loader pro Png2Point (Sez. 105).

Druhý reconstructor (body). Na rozdíl od Png2Area NEMÁ vlastní předkrájené Y dlaždice — bere ČISTÉ
gen rendery `*_x.png` z `resources/area_tiles/` (sdílené s Png2Area, tile.py je už vyrobil) jako PODKLAD
a injektuje bodové symboly + GT heatmapu ZA BĚHU (inject.py). Injekce je tím nekonečná augmentace:
jiná realizace každou epochu → řeší vzácnost bodů v gen i nevyváženost tříd (volně instancí).

Pipeline jednoho vzorku (train):
  čistý podklad *_x.png → D4 (flip+rot90) → inject_tile (symboly + heatmapa) → degrade (sken-vady) → norm
Val/test: bez D4, bez degradace, injekce s FIXNÍM seedem (= idx) → deterministický eval set.
Overfit gate: augment=False → fixní injekce každou epochu → čistá memorizace (sanity).

X = ImageNet-normalizovaný RGB sken (3,512,512). Y = GT heatmapy (N_POINT,512,512) float32 [0,1].
Degradace (generator/degrade.py) je čistě fotometrická (Y/poloha se nemění) → heatmapa zůstává zarovnaná.

Sys.path skript (fáze B). Importuje se z model/png2point/train.py. Self-check dole.
"""
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TILES_DIR = _REPO_ROOT / "resources" / "area_tiles"   # sdílené podklady s Png2Area

sys.path.insert(0, str(_REPO_ROOT / "model" / "png2point"))
sys.path.insert(0, str(_REPO_ROOT / "generator"))
from inject import inject_tile, N_POINT, TILE   # noqa: E402
from degrade import degrade                      # noqa: E402

Image.MAX_IMAGE_PIXELS = None

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class PointTileDataset(Dataset):
    """Dlaždice jednoho splitu jako (x, heat) pro Png2Point.

    x    = float32 (3,512,512), ImageNet-normalizovaný RGB sken s injektovanými body.
    heat = float32 (N_POINT,512,512), GT Gaussian heatmapy peaků per třída.

    Parametry:
      split      : 'train' | 'val' | 'test' — který podadresář area_tiles/ číst (podklad).
      augment    : D4 + degradace + variabilní injekce (jen train; val/test deterministické).
      limit_cids : volitelný seznam cid/lokalit (overfit gate: 1-3 mapy)."""

    def __init__(self, split: str, *, augment: bool = False,
                 limit_cids: list[str] | None = None):
        self.split = split
        self.augment = augment
        split_dir = _TILES_DIR / split
        if not split_dir.exists():
            raise RuntimeError(f"chybí {split_dir} — spusť nejdřív `python model/png2area/tile.py` "
                               f"(Png2Point sdílí podklady *_x.png s Png2Area)")
        xpaths = sorted(split_dir.glob("*/*_x.png"))
        if limit_cids is not None:
            keep = set(limit_cids)
            xpaths = [p for p in xpaths if p.parent.name in keep]
        if not xpaths:
            raise RuntimeError(f"žádné podklady v {split_dir}"
                               + (f" pro cid {limit_cids}" if limit_cids else ""))
        self.xpaths = xpaths

    def __len__(self) -> int:
        return len(self.xpaths)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        xp = self.xpaths[idx]
        rgb = np.asarray(Image.open(xp).convert("RGB"), dtype=np.uint8)
        # podklad menší než TILE (okrajová dlaždice) by rozbil inject_tile — dopaduj na TILE×TILE
        if rgb.shape[:2] != (TILE, TILE):
            pad = np.full((TILE, TILE, 3), 255, dtype=np.uint8)
            h, w = min(TILE, rgb.shape[0]), min(TILE, rgb.shape[1])
            pad[:h, :w] = rgb[:h, :w]
            rgb = pad

        if self.augment:
            # --- D4 na ČISTÉM podkladu (před injekcí — pak stačí transformovat jen rgb, ne heatmapu) ---
            if torch.rand(1).item() < 0.5:
                rgb = rgb[:, ::-1]
            k = int(torch.randint(0, 4, (1,)).item())
            if k:
                rgb = np.rot90(rgb, k)
            rgb = np.ascontiguousarray(rgb)
            # variabilní seed → jiná injekce každou epochu (nekonečná augmentace)
            seed = int(torch.randint(0, 2 ** 31 - 1, (1,)).item())
        else:
            # deterministická injekce (val/test/overfit): seed = idx → fixní eval set / memorizace
            seed = idx

        x, heat = inject_tile(rgb, seed=seed)      # (TILE,TILE,3) uint8 , (N_POINT,TILE,TILE) f32

        if self.augment:
            # degradace AŽ po injekci (symboly se degradují jako na reálném skenu); fotometrická → heat OK
            dseed = int(torch.randint(0, 2 ** 31 - 1, (1,)).item())
            x = degrade(x, seed=dseed)

        # X → 0-1 → ImageNet norma → CHW
        xf = x.astype(np.float32) / 255.0
        xf = (xf - _IMAGENET_MEAN) / _IMAGENET_STD
        xt = torch.from_numpy(xf.transpose(2, 0, 1)).contiguous()      # (3,H,W)
        ht = torch.from_numpy(heat).contiguous()                       # (N_POINT,H,W) f32
        return xt, ht


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for s in ("train", "val", "test"):
        try:
            ds = PointTileDataset(s, augment=(s == "train"))
        except RuntimeError as e:
            print(f"{s:<6} —  ({e})")
            continue
        x, h = ds[0]
        peaks = [(i, int((h[i] > 0.99).sum().item())) for i in range(N_POINT)]
        print(f"{s:<6} {len(ds):>5} dlaždic   x{tuple(x.shape)} {x.dtype} "
              f"[{x.min():.2f},{x.max():.2f}]   heat{tuple(h.shape)} [{h.min():.2f},{h.max():.2f}] "
              f"peaků≈{peaks}")
