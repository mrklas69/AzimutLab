"""
dataset.py — PyTorch loader nad tréninkovými dlaždicemi UC5 runnability modelu (Sez. 78, krok 4).

⟲ ARCHIVOVÁNO (Sez. 79) — směr `ortofoto → 4 runnability barvy` je DOLOŽENÁ slepá ulička
(val mIoU strop ~0,25, Sez. 78: podrost pod korunami z ortofota shora nevidět). Kód NEMAZÁN
(je to doložený nález „tudy ne"). Aktuální směr Laboratoře = `reconstructor()` (sken → `.omap`),
viz GLOSSARY `generator()`/`reconstructor()` + docs/TODO. Loader/augmentace je ale
znovupoužitelná pro budoucí modely (Png2Polygon aj.).

`model/tile.py` (Sez. 77) předkrájel páry (X=ortho RGB, Y=label 0-4/255) na 512×512 PNG
dlaždice do `resources/tiles/<split>/<cid>/`. Tenhle modul je čte za běhu, na train splitu
přidává augmentaci a vrací tensory pro `model/train.py`.

Proč augmentace AŽ tady (a ne při pre-tilingu): pre-tiling je deterministický (vizuálně
zkontrolovatelný, Sez. 77), rozmanitost se levně dotvoří náhodnou transformací za běhu —
každá epocha vidí jiné natočení/jas téže dlaždice (volba Sez. 77).

Augmentace = jen D4 (8 dihedrálních symetrií: hflip + rot90×k) + mírný jas/kontrast na X.
- D4 je bezpečná: flip a rotace o násobky 90° NEinterpolují → labely zůstanou přesně 0-4/255
  (rotace o obecný úhel by mezi třídami vyrobila smíšené pixely → poškodí GT).
- OB mapy nemají preferovanou orientaci (grivace každé mapy jiná, Sez. 37) → rotace dává smysl.
- Jas/kontrast jen na vstup X (ortofoto): simuluje různé osvětlení/sezónu náletu; na label Y
  se NEsmí sáhnout.

Normalizace: ImageNet mean/std, protože encoder (ResNet34) je ImageNet-pretrained (smp) —
musí dostat vstup ve stejné statistice, na jakou byl trénovaný.

Sys.path skript (fáze B, ne balík). Importuje se z `model/train.py`.
"""
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TILES_DIR = _REPO_ROOT / "resources" / "tiles"

# connectors na path (IGNORE label = 255, sdílená konstanta s map_gt/tile)
sys.path.insert(0, str(_REPO_ROOT / "connectors"))
from map_gt import IGNORE   # noqa: E402

Image.MAX_IMAGE_PIXELS = None

# ImageNet statistika (RGB, rozsah 0-1) — encoder ResNet34 je na ní pretrained.
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class TileDataset(Dataset):
    """Dlaždice jednoho splitu (train/val/test) jako (x, y) tensory.

    x = float32 (3, 512, 512), ImageNet-normalizované RGB.
    y = int64  (512, 512), labely 0-4 a IGNORE(255) — loss je přeskočí přes ignore_index.

    Parametry:
      split   : 'train' | 'val' | 'test' — který podadresář resources/tiles/ číst.
      augment : zapnout D4 + jas/kontrast (jen pro train; val/test deterministické).
      limit_cids : volitelný seznam cid (názvů map) — omezí dataset jen na tyhle mapy
                   (pro overfit gate: trénuj na 1-3 mapách a sleduj, jestli se síť naučí).
    """

    def __init__(self, split: str, *, augment: bool = False,
                 limit_cids: list[str] | None = None):
        self.split = split
        self.augment = augment
        split_dir = _TILES_DIR / split
        if not split_dir.exists():
            raise RuntimeError(f"chybí {split_dir} — spusť nejdřív `python model/tile.py`")

        # posbírej všechny X dlaždice (Y dohledáme přejmenováním _x→_y)
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

        x je (H,W,3) uint8, y je (H,W) uint8. Random stav z torch (sdílí seed s loaderem).
        """
        # --- D4: náhodný horizontální flip + rotace o k×90° (geometrie beze ztráty) ---
        if torch.rand(1).item() < 0.5:
            x = x[:, ::-1]            # hflip (numpy slice, vrací view → .copy() až nakonec)
            y = y[:, ::-1]
        k = int(torch.randint(0, 4, (1,)).item())   # 0..3 rotace o 90°
        if k:
            x = np.rot90(x, k)
            y = np.rot90(y, k)

        # --- jas + kontrast jen na X (ortofoto), label Y se nedotýká ---
        x = x.astype(np.float32)
        # jas: násobitel ~U(0.85, 1.15); kontrast: roztažení kolem střední šedi 127,5
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
        # Y → long tensor (IGNORE=255 zůstane, loss ho odfiltruje ignore_index)
        yt = torch.from_numpy(y.astype(np.int64))                   # (H,W)
        return xt, yt


def class_weights() -> list[float]:
    """Median-freq váhy spočtené v tile.py (z TRAIN dlaždic) — čteme z _tiles.json.

    SSoT: váhy žijí v resources/tiles/_tiles.json (klíč class_weights_list, pořadí 0..4),
    ať se nepřepočítávají na dvou místech (DRY). CrossEntropyLoss(weight=) je bere přímo.
    """
    import json
    data = json.loads((_TILES_DIR / "_tiles.json").read_text(encoding="utf-8"))
    return data["class_weights_list"]


if __name__ == "__main__":
    # rychlý self-check: rozměry, typy, rozsah labelů, počet dlaždic na split
    for s in ("train", "val", "test"):
        ds = TileDataset(s, augment=(s == "train"))
        x, y = ds[0]
        labs = torch.unique(y).tolist()
        print(f"{s:<6} {len(ds):>5} dlaždic   x{tuple(x.shape)} {x.dtype} "
              f"[{x.min():.2f},{x.max():.2f}]   y{tuple(y.shape)} {y.dtype} labely={labs}")
    print("class_weights:", class_weights())
