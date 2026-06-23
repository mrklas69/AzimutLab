"""
dataset.py — PyTorch loader pro Png2Point (Sez. 105, přepsán na point_base + random-crop Sez. 106).

Druhý reconstructor (body). NEMÁ vlastní předkrájené Y dlaždice — bere ČISTÝ podklad BEZ bodů
`gen_pointbase/rgb.png` (generate_map point_base=True, Sez. 106) a injektuje bodové symboly + GT
heatmapu ZA BĚHU (inject.py). Injekce je tím nekonečná augmentace: jiná realizace každou epochu →
řeší vzácnost bodů v gen i nevyváženost tříd (volně instancí).

PROČ point_base, ne sdílené area_tiles (změna Sez. 106): area dlaždice nesou VLASTNÍ gen body
(204/207, landmarks, extrémy) bez GT → nejednoznačná funkce („tenhle kruh = 204, tamten identický =
nic"), model selhal i na 1 dlaždici (diagnostika Sez. 105). point_base je render bez jediného bodu →
jediné body na dlaždici jsou ty injektované = jednoznačné GT.

PROČ random-crop, ne předkrájené dlaždice: injekce je stejně on-the-fly, takže pevné dlaždice nic
nepřinášejí — náhodný 512 crop z plného renderu je další augmentace zdarma (jiný výřez každou epochu).

Pipeline jednoho vzorku (train):
  plný point_base render → random-crop 512 → D4 (flip+rot90) → inject_tile (symboly + heatmapa)
  → degrade (sken-vady) → norm
Val/test: deterministický crop + injekce s FIXNÍM seedem (= idx) → reprodukovatelný eval set.
Overfit gate: augment=False → fixní crop+injekce každou epochu → čistá memorizace (sanity).

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
_CORPUS = _REPO_ROOT / "resources" / "livelox"   # point_base rendery: <cid>/gen_pointbase/rgb.png

sys.path.insert(0, str(_REPO_ROOT / "model" / "png2point"))
sys.path.insert(0, str(_REPO_ROOT / "model"))   # purple.py = sdílený s png2area (A2a fialový přetisk)
sys.path.insert(0, str(_REPO_ROOT / "generator"))
sys.path.insert(0, str(_REPO_ROOT / "connectors"))
from inject import inject_tile, N_POINT, TILE   # noqa: E402
from degrade import degrade                      # noqa: E402
from purple import overprint_course             # noqa: E402  (fialový přetisk tratě do X — Sez. 117 audit A2a)
from split import load_split                     # noqa: E402
from mpp import resample_to_mpp, read_src_mpp    # noqa: E402  (Sez. 126: render na kanonické měřítko)

Image.MAX_IMAGE_PIXELS = None

from norm import IMAGENET_MEAN as _IMAGENET_MEAN, IMAGENET_STD as _IMAGENET_STD  # noqa: E402  SSoT (audit D4, Sez. 158)

CROPS_PER_MAP = 16        # kolik 512 výřezů na mapu = 1 epocha (train náhodné, val/test deterministické)


def _pointbase_paths(split: str) -> list[Path]:
    """Cesty k point_base renderům daného splitu, které REÁLNĚ existují (gen_pointbase/rgb.png).

    Split příslušnost z split.load_split ({cid: split}); bereme jen cidy, co mají hotový podklad
    (subset ~40 z pairs.pointbase, ne celých 207) → dataset se přizpůsobí tomu, co je vyrobeno."""
    s = load_split()
    out = []
    for cid, sp in sorted(s.items()):
        if sp != split:
            continue
        p = _CORPUS / cid / "gen_pointbase" / "rgb.png"
        if p.exists():
            out.append(p)
    return out


class PointTileDataset(Dataset):
    """point_base rendery jednoho splitu jako (x, heat) pro Png2Point, random-crop 512 + injekce.

    x    = float32 (3,512,512), ImageNet-normalizovaný RGB sken s injektovanými body.
    heat = float32 (N_POINT,512,512), GT Gaussian heatmapy peaků per třída.

    Parametry:
      split      : 'train' | 'val' | 'test' — který split point_base renderů číst.
      augment    : random-crop + D4 + degradace + variabilní injekce (jen train; val/test deterministické).
      limit_cids : volitelný seznam cid/lokalit (overfit gate: 1-3 mapy)."""

    def __init__(self, split: str, *, augment: bool = False,
                 limit_cids: list[str] | None = None):
        self.split = split
        self.augment = augment
        paths = _pointbase_paths(split)
        if limit_cids is not None:
            keep = set(limit_cids)
            paths = [p for p in paths if p.parent.parent.name in keep]
        if not paths:
            raise RuntimeError(
                f"žádné point_base rendery pro split '{split}'"
                + (f" / cid {limit_cids}" if limit_cids else "")
                + f" v {_CORPUS}/<cid>/gen_pointbase/rgb.png — spusť `python generator/pairs.py pointbase 40`")
        # načti plné rendery do paměti jednou + resample na kanonické měřítko dlaždice (Sez. 126,
        # audit C1/K1): render je ~2,18 m/px, ale inject/purple kreslí symboly v CANONICAL_MPP (1,33)
        # → bez resamplu byly symboly 1,64× velké. Upsample 2,18→1,33 ≈ 1,64× (~40 map × 3760² × 3 B
        # ≈ 1,7 GB; HAL3000 utáhne). Random-crop za běhu je pak levný (bez re-dekódování PNG).
        self.maps = [resample_to_mpp(np.asarray(Image.open(p).convert("RGB"), dtype=np.uint8),
                                     read_src_mpp(p.parent))
                     for p in paths]
        self.cids = [p.parent.parent.name for p in paths]

    def __len__(self) -> int:
        return len(self.maps) * CROPS_PER_MAP

    def _crop(self, img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        """Vyřízne TILE×TILE výřez. Náhodná pozice (z rng) — pro train jiná každou epochu,
        pro val/test deterministická (rng=seed idx). Menší render dopaduj bílou (nemělo by nastat)."""
        H, W = img.shape[:2]
        if H < TILE or W < TILE:
            pad = np.full((max(TILE, H), max(TILE, W), 3), 255, dtype=np.uint8)
            pad[:H, :W] = img
            img = pad
            H, W = img.shape[:2]
        y0 = int(rng.integers(0, H - TILE + 1))
        x0 = int(rng.integers(0, W - TILE + 1))
        return img[y0:y0 + TILE, x0:x0 + TILE]

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        mi = idx % len(self.maps)           # která mapa (round-robin přes CROPS_PER_MAP epoch-bloků)
        img = self.maps[mi]

        if self.augment:
            rng = np.random.default_rng(int(torch.randint(0, 2 ** 31 - 1, (1,)).item()))
            rgb = self._crop(img, rng)
            # --- D4 na ČISTÉM podkladu (před injekcí — pak stačí transformovat jen rgb, ne heatmapu) ---
            if torch.rand(1).item() < 0.5:
                rgb = rgb[:, ::-1]
            k = int(torch.randint(0, 4, (1,)).item())
            if k:
                rgb = np.rot90(rgb, k)
            rgb = np.ascontiguousarray(rgb)
            seed = int(torch.randint(0, 2 ** 31 - 1, (1,)).item())   # variabilní injekce každou epochu
        else:
            # deterministický crop i injekce (val/test/overfit): seed = idx → fixní eval set / memorizace
            rgb = np.ascontiguousarray(self._crop(img, np.random.default_rng(idx)))
            seed = idx

        x, heat = inject_tile(rgb, seed=seed)      # (TILE,TILE,3) uint8 , (N_POINT,TILE,TILE) f32

        if self.augment:
            # fialový přetisk tratě (A2a, Sez. 117 audit) PO injekci (trať se tiskne přes mapu i body),
            # PŘED degrade (fialová se rozmaže jako na skenu). Kreslí JEN do X → heatmapa GT se nemění.
            x = overprint_course(x, seed=int(torch.randint(0, 2 ** 31 - 1, (1,)).item()))
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
        print(f"{s:<6} {len(ds.maps):>3} map → {len(ds):>4} vzorků   x{tuple(x.shape)} {x.dtype} "
              f"[{x.min():.2f},{x.max():.2f}]   heat{tuple(h.shape)} [{h.min():.2f},{h.max():.2f}] "
              f"peaků≈{peaks}")
