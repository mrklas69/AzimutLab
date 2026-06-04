"""
dataset.py — PyTorch loader nad dlaždicemi reconstructor modelu Png2Area (Sez. 88).

`model/png2area/tile.py` předkrájel páry (X=sken RGB, Y=area label 0..15) na 512×512 PNG dlaždice do
`resources/area_tiles/<split>/<cid>/`. Tenhle modul je čte za běhu, na train splitu přidává augmentaci
a vrací tensory pro `model/png2area/train.py`. Izomorfní s archivovaným model/runnability/dataset.py —
liší se: X=sken (ne ortho), Y=16 area tříd (ne 5 runnability), BEZ IGNORE (Y z naší .omap je čisté,
žádný přetisk → každý px je validní třída včetně pozadí 0).

Augmentace = jen D4 (8 dihedrálních symetrií: hflip + rot90×k) + mírný jas/kontrast na X.
- D4 je bezpečná: flip a rotace o násobky 90° NEinterpolují → area labely zůstanou přesně 0..15
  (rotace o obecný úhel by mezi třídami vyrobila smíšené pixely → poškodí GT).
- OB mapy nemají preferovanou orientaci (grivace každé mapy jiná, Sez. 37) → rotace dává smysl.
- Jas/kontrast jen na vstup X (sken): simuluje variabilitu skenu/tisku; na label Y se NEsmí sáhnout.
  (Degradér fáze II už dělá fotometrické sken-vady deterministicky per-mapa, Sez. 86 — tohle je
  navíc levná za-běhu variabilita mezi epochami, DRY: geometrii dělá D4 tady, ne degradér.)

Normalizace: ImageNet mean/std — encoder (ResNet34) je ImageNet-pretrained (smp), musí dostat vstup
ve stejné statistice. (Vstup je teď mapový sken, ne ortofoto, ale pořád RGB 3 kanály → ImageNet
norma je správná pro pretrained encoder; doménový posun řeší fine-tuning.)

Sys.path skript (fáze B, ne balík). Importuje se z `model/png2area/train.py`.
"""
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

_REPO_ROOT = Path(__file__).resolve().parents[2]   # model/png2area/ → o dvě úrovně hloub
_TILES_DIR = _REPO_ROOT / "resources" / "area_tiles"

Image.MAX_IMAGE_PIXELS = None

# ImageNet statistika (RGB, rozsah 0-1) — encoder ResNet34 je na ní pretrained.
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class AreaTileDataset(Dataset):
    """Dlaždice jednoho splitu (train/val/test) jako (x, y) tensory pro Png2Area.

    x = float32 (3, 512, 512), ImageNet-normalizovaný sken RGB.
    y = int64  (512, 512), area labely 0..15 (0 = pozadí, 1..15 ISOM kódy; BEZ IGNORE).

    Parametry:
      split   : 'train' | 'val' | 'test' — který podadresář resources/area_tiles/ číst.
      augment : zapnout D4 + jas/kontrast (jen pro train; val/test deterministické).
      limit_cids : volitelný seznam cid/lokalit — omezí dataset (overfit gate: 1-3 mapy)."""

    def __init__(self, split: str, *, augment: bool = False,
                 limit_cids: list[str] | None = None):
        self.split = split
        self.augment = augment
        split_dir = _TILES_DIR / split
        if not split_dir.exists():
            raise RuntimeError(f"chybí {split_dir} — spusť nejdřív `python model/png2area/tile.py`")

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
        """D4 (flip + rot90×k) na OBĚ + jas/kontrast jen na X. Vrací nové (x, y).

        x je (H,W,3) uint8, y je (H,W) uint8. Random stav z torch (sdílí seed s loaderem)."""
        # --- D4: náhodný horizontální flip + rotace o k×90° (geometrie beze ztráty) ---
        if torch.rand(1).item() < 0.5:
            x = x[:, ::-1]            # hflip (numpy slice, view → .copy() až nakonec)
            y = y[:, ::-1]
        k = int(torch.randint(0, 4, (1,)).item())   # 0..3 rotace o 90°
        if k:
            x = np.rot90(x, k)
            y = np.rot90(y, k)

        # --- jas + kontrast jen na X (sken), label Y se nedotýká ---
        x = x.astype(np.float32)
        bright = 0.85 + 0.30 * torch.rand(1).item()
        contrast = 0.85 + 0.30 * torch.rand(1).item()
        x = (x * bright - 127.5) * contrast + 127.5
        x = np.clip(x, 0, 255).astype(np.uint8)
        # .copy() = rozbije negativní stride z [::-1]/rot90 (torch.from_numpy je nemá rád)
        return np.ascontiguousarray(x), np.ascontiguousarray(y)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        xp = self.xpaths[idx]
        yp = xp.with_name(xp.name.replace("_x.png", "_y.png"))
        x = np.asarray(Image.open(xp).convert("RGB"), dtype=np.uint8)
        y = np.asarray(Image.open(yp), dtype=np.uint8)

        if self.augment:
            x, y = self._augment(x, y)

        # X → float 0-1 → ImageNet normalizace → CHW tensor
        xf = x.astype(np.float32) / 255.0
        xf = (xf - _IMAGENET_MEAN) / _IMAGENET_STD
        xt = torch.from_numpy(xf.transpose(2, 0, 1)).contiguous()   # (3,H,W)
        yt = torch.from_numpy(y.astype(np.int64))                   # (H,W), 0..15
        return xt, yt


def class_weights() -> list[float]:
    """Median-freq váhy spočtené v tile.py (z TRAIN dlaždic) — čteme z _tiles.json.

    SSoT: váhy žijí v resources/area_tiles/_tiles.json (klíč class_weights_list, pořadí 0..15),
    ať se nepřepočítávají na dvou místech (DRY). CrossEntropyLoss(weight=) je bere přímo."""
    import json
    data = json.loads((_TILES_DIR / "_tiles.json").read_text(encoding="utf-8"))
    return data["class_weights_list"]


if __name__ == "__main__":
    # rychlý self-check: rozměry, typy, rozsah labelů, počet dlaždic na split
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for s in ("train", "val", "test"):
        try:
            ds = AreaTileDataset(s, augment=(s == "train"))
        except RuntimeError as e:
            print(f"{s:<6} —  ({e})")
            continue
        x, y = ds[0]
        labs = torch.unique(y).tolist()
        print(f"{s:<6} {len(ds):>5} dlaždic   x{tuple(x.shape)} {x.dtype} "
              f"[{x.min():.2f},{x.max():.2f}]   y{tuple(y.shape)} {y.dtype} labely={labs}")
    print("class_weights:", class_weights())
