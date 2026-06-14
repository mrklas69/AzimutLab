"""
mpp.py — kanonické rozlišení tréninkové dlaždice reconstructorů (SSoT) + resample na něj.

Proč existuje (Sez. 126, audit ChatGPT C1/K1): gen render `rgb.png` vzniká na ~2,18 m/px
(`generator.py`: pixel_size_m = bbox_šířka_m / W; daný velikostí rastru renderu), ALE `inject.py`
i `purple.py` počítaly velikosti symbolů z 1,33 m/px (= `separate.TARGET_MPP`, který je ovšem jen
INTERNÍ separační downscale, ne měřítko dlaždice — polygony se ze separace škálují zpět do orig px).
Důsledek: dlaždice byla 2,18 m/px, ale symboly se kreslily v px pro 1,33 → byly 2,18/1,33 = 1,64×
velké, a `eval_real` reálný sken downscaloval na 1,33 = jiné měřítko než trénink (2,18). Pravděpodobný
spoluviník kolapsu 210 na reálu (A1.b, Sez. 121).

Oprava (var. a1, volba uživatele Sez. 126): zavést JEDNO kanonické MPP dlaždice = SSoT a páry X+Y
na něj resamplovat PŘED tilingem / cropem. Symboly inject/purple pak počítají px z téhož CANONICAL_MPP
→ měřítko sedí napříč syntézou i `eval_real`. Volba 1,33 (ne 2,18) měřením podložená: tečka 210
(0,4 mm @ 1:10000) je na 1,33 ~4,5 px (čitelná) vs na 2,18 ~2,75 px (splývá s rastrem); reálné skeny
jsou 0,15–0,32 m/px (med. ~0,21), takže oba downscalují, ale 1,33 zahodí méně drobného detailu.

POZOR na koncepční rozdíl (conceptual integrity): `separate.TARGET_MPP` = interní rozlišení
vektorizace (rychlost + konzistence MIN_AREA_PX); `CANONICAL_MPP` zde = měřítko tréninkové dlaždice.
DNES mají stejnou hodnotu (1,33), ale jsou to DVA různé koncepty — nesjednocovat do jedné konstanty,
jinak by změna jednoho tiše rozbila druhý.

Sys.path util (fáze B, ne balík). Importují: model/png2{area/tile,point/dataset}.py, inject.py, purple.py.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

# --- SSoT: kanonické rozlišení tréninkové dlaždice reconstructorů [m/px] ---
# Měřítko, na kterém trénují i inferují Png2Area / Png2Point. Symboly (inject/purple), páry X+Y
# i `eval_real` downscale reálného skenu MUSÍ lícovat s touto hodnotou. Změna = rebuild datasetů
# + retrain obou modelů (+ aktualizace _tiles.json / checkpoint metadata).
CANONICAL_MPP = 1.33


def resample_to_mpp(arr: np.ndarray, src_mpp: float,
                    target_mpp: float = CANONICAL_MPP, *, label: bool = False) -> np.ndarray:
    """Převzorkuje rastr ze `src_mpp` na `target_mpp` [m/px]. Vrací nové pole (uint8).

    arr     : (H,W) label nebo (H,W,3) RGB, uint8.
    src_mpp : rozlišení vstupu [m/px] — z meta.json páru (`pixel_size_m`).
    label   : True = nearest (zachová celočíselné labely beze záměny); False = bilineární (RGB).

    Faktor f = src_mpp / target_mpp: f>1 = upsample (jemnější cíl → víc px, gen 2,18→1,33 ≈ 1,64×),
    f<1 = downsample. Při f≈1 (|f−1|<0,5 %) no-op (žádná interpolace na renderech, co už sedí).
    Geometrie zůstává zarovnaná — RGB i label resamplujeme STEJNÝM faktorem z téhož src_mpp."""
    if not src_mpp or src_mpp <= 0:
        # no silent fallback: bez platného src_mpp neumíme dlaždici přepočítat na kanonické měřítko
        raise ValueError(f"resample_to_mpp: neplatné src_mpp={src_mpp!r} (čekán m/px > 0 z meta.json)")
    f = src_mpp / target_mpp
    if abs(f - 1.0) < 0.005:        # už na cílovém měřítku (tolerance 0,5 %) → neinterpoluj
        return arr
    H, W = arr.shape[:2]
    new_w = max(1, round(W * f))
    new_h = max(1, round(H * f))
    # PIL.resize bere (W,H); resample filtr: NEAREST pro label (bez míchání tříd), BILINEAR pro RGB
    resample = Image.NEAREST if label else Image.BILINEAR
    mode_arr = arr if not label else arr            # uint8 (H,W) i (H,W,3) zvládne PIL přímo
    out = Image.fromarray(mode_arr).resize((new_w, new_h), resample)
    return np.asarray(out, dtype=np.uint8)


def read_src_mpp(meta_dir: Path) -> float:
    """Rozlišení renderu [m/px] z `meta_dir/meta.json` (`pixel_size_m`). Sdíleno tile.py + dataset.py.

    No silent fallback (Sez. 110): chybí meta / klíč → SELŽI — bez něj nelze dlaždici přepočítat
    na kanonické měřítko (Sez. 126)."""
    meta_p = Path(meta_dir) / "meta.json"
    if not meta_p.exists():
        raise RuntimeError(f"read_src_mpp: chybí {meta_p} — nelze určit src_mpp pro resample na "
                           f"CANONICAL_MPP (no silent fallback, Sez. 126)")
    # pixel_size_m žije v sekci georef (generator.py: meta["georef"]["pixel_size_m"])
    mpp = json.loads(meta_p.read_text(encoding="utf-8")).get("georef", {}).get("pixel_size_m")
    if not mpp:
        raise RuntimeError(f"read_src_mpp: {meta_p} nemá klíč georef.pixel_size_m (Sez. 126)")
    return float(mpp)


if __name__ == "__main__":
    # self-check: upsample 2,18→1,33 zvětší rozměr ~1,64×, label nearest nezavede nové hodnoty
    rgb = np.random.randint(0, 256, (100, 120, 3), dtype=np.uint8)
    lbl = np.random.randint(0, 18, (100, 120), dtype=np.uint8)
    r = resample_to_mpp(rgb, 2.18)
    l = resample_to_mpp(lbl, 2.18, label=True)
    print(f"CANONICAL_MPP={CANONICAL_MPP}")
    print(f"RGB   {rgb.shape} -> {r.shape}  (f={2.18/CANONICAL_MPP:.3f})")
    print(f"label {lbl.shape} -> {l.shape}  unikátní labely podmnožina vstupu: "
          f"{set(np.unique(l).tolist()) <= set(np.unique(lbl).tolist())}")
    assert set(np.unique(l).tolist()) <= set(np.unique(lbl).tolist()), "nearest zavedl nový label!"
    print("OK")
