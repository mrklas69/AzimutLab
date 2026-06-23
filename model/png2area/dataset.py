"""
dataset.py — PyTorch loader nad dlaždicemi reconstructor modelu Png2Area (Sez. 88).

`model/png2area/tile.py` předkrájel páry (X=sken RGB, Y=area label 0..N_AREA-1) na 512×512 PNG dlaždice
do `resources/area_tiles/<split>/<cid>/`. Tenhle modul je čte za běhu, na train splitu přidává augmentaci
a vrací tensory pro `model/png2area/train.py`. Izomorfní s archivovaným model/runnability/dataset.py —
liší se: X=sken (ne ortho), Y=N_AREA area tříd (21 od Sez. 152: 20 ISOM kódů + pozadí; ne 5 runnability),
BEZ IGNORE (Y z naší .omap je čisté, žádný přetisk → každý px je validní třída včetně pozadí 0).

Augmentace (jen train split): D4 (8 dihedrálních symetrií) + fotometrická degradace skenu.
- D4 je bezpečná: flip a rotace o násobky 90° NEinterpolují → area labely zůstanou přesně 0..N_AREA-1
  (rotace o obecný úhel by mezi třídami vyrobila smíšené pixely → poškodí GT).
- OB mapy nemají preferovanou orientaci (grivace každé mapy jiná, Sez. 37) → rotace dává smysl.
- Fotometrická degradace (generator/degrade.py: CMYK misregistrace/blur/papír/šum/JPEG) se aplikuje
  ON-THE-FLY na vstup X — čistý gen render → realistický sken, JINÁ realizace každou epochu (variabilní
  seed) → bohatší trénink z téhož páru. Sem patří (fáze II/III dekonstruktor), NE do build_pair:
  generator() drží render věrný/čistý (Sez. 103, návrat k záměru Sez. 80). Na label Y se NEsahá.

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

# generator/ na path kvůli degrade.py (fotometrická augmentace skenu, přesun z build_pair Sez. 103)
sys.path.insert(0, str(_REPO_ROOT / "generator"))
sys.path.insert(0, str(_REPO_ROOT / "model"))   # purple.py = sdílený s png2point (A2a fialový přetisk)
from degrade import degrade   # noqa: E402
from purple import overprint_course   # noqa: E402  (fialový přetisk tratě do X — Sez. 117 audit A2a)
from omap_raster import N_AREA   # noqa: E402  (SSoT počtu area tříd — guard proti stale _tiles.json, Sez. 110)

Image.MAX_IMAGE_PIXELS = None

# ImageNet statistika (RGB, rozsah 0-1) — encoder ResNet34 je na ní pretrained.
from norm import IMAGENET_MEAN as _IMAGENET_MEAN, IMAGENET_STD as _IMAGENET_STD  # SSoT (audit D4, Sez. 158)


class AreaTileDataset(Dataset):
    """Dlaždice jednoho splitu (train/val/test) jako (x, y) tensory pro Png2Area.

    x = float32 (3, 512, 512), ImageNet-normalizovaný sken RGB.
    y = int64  (512, 512), area labely 0..N_AREA-1 (0 = pozadí, 1.. ISOM kódy; BEZ IGNORE).

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
        """D4 (flip + rot90×k) na OBĚ + fotometrická degradace skenu jen na X. Vrací nové (x, y).

        x je (H,W,3) uint8, y je (H,W) uint8. Random stav z torch (sdílí seed s loaderem)."""
        # --- D4: náhodný horizontální flip + rotace o k×90° (geometrie beze ztráty) ---
        if torch.rand(1).item() < 0.5:
            x = x[:, ::-1]            # hflip (numpy slice, view → .copy() až nakonec)
            y = y[:, ::-1]
        k = int(torch.randint(0, 4, (1,)).item())   # 0..3 rotace o 90°
        if k:
            x = np.rot90(x, k)
            y = np.rot90(y, k)

        x = np.ascontiguousarray(x)                          # rozbij negativní stride z D4 před degrade
        # --- fialový přetisk tratě jen na X (A2a, Sez. 117 audit): trať NENÍ mapový obsah → label Y
        # se NEMĚNÍ; model se ji má naučit ignorovat (reálná závodní mapa ji nese, trénink ji nikdy
        # neviděl). Kreslí se PŘED degrade, ať se fialová rozmaže/posune jako na reálném skenu. ---
        x = overprint_course(x, seed=int(torch.randint(0, 2 ** 31 - 1, (1,)).item()))
        # --- fotometrická degradace jen na X (čistý gen render → sken), label Y se nedotýká ---
        # degrade() = CMYK misregistrace/blur/papír/šum/JPEG (generator/degrade.py). Variabilní seed
        # → jiná sken-realizace každou epochu (Sez. 103: degradace = augmentace tady, ne v build_pair).
        seed = int(torch.randint(0, 2 ** 31 - 1, (1,)).item())
        x = degrade(x, seed=seed)                            # (H,W,3) uint8 → uint8
        # .copy() y: rozbije negativní stride z [::-1]/rot90 (torch.from_numpy je nemá rád)
        return x, np.ascontiguousarray(y)

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
        yt = torch.from_numpy(y.astype(np.int64))                   # (H,W), 0..N_AREA-1
        return xt, yt


def class_weights() -> list[float]:
    """Median-freq váhy spočtené v tile.py (z TRAIN dlaždic) — čteme z _tiles.json.

    SSoT: váhy žijí v resources/area_tiles/_tiles.json (klíč class_weights_list, pořadí 0..N_AREA-1),
    ať se nepřepočítávají na dvou místech (DRY). CrossEntropyLoss(weight=) je bere přímo.

    Guard (no silent fallback, Sez. 110): _tiles.json může být STALE vůči aktuálnímu schématu
    (změna N_AREA: 16→18 Sez. 99/103, 18→21 Sez. 152, drift 301/301.1 Sez. 110).
    Mismatch délky vah / n_area by
    jinak prošel tiše do CrossEntropyLoss s nesprávnými vahami → selži nahlas s instrukcí na rebuild."""
    import json
    tpath = _TILES_DIR / "_tiles.json"
    data = json.loads(tpath.read_text(encoding="utf-8"))
    weights = data["class_weights_list"]
    meta_n = data.get("_meta", {}).get("n_area")
    if meta_n != N_AREA or len(weights) != N_AREA:
        raise RuntimeError(
            f"_tiles.json je STALE vůči aktuálnímu schématu: _meta.n_area={meta_n}, "
            f"len(class_weights_list)={len(weights)}, ale omap_raster.N_AREA={N_AREA}. "
            f"Přestav dlaždice: `python model/png2area/tile.py` (build_tiles / build_tiles_dev). "
            f"({tpath})")
    return weights


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
