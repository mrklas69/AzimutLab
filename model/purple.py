"""
purple.py — augmentace fialovým přetiskem tratě (ISOM course overprint) pro OBA reconstructory (A2a).

PROČ (Fable5 audit A1, Sez. 117): vrcholová reálná úloha je sken POUŽITÉ závodní mapy — ta nese
fialový přetisk tratě (start, kontrolní kroužky, spojnice, čísla). Náš trénink vidí jen čistý gen
render → model fialovou nikdy nepotkal jako vstup. A1 benchmark (Sez. 120-121) běžel na ČISTÝCH
kartografových skenech bez tratě → fialovou nemohl změřit, ale na reálné závodní mapě se vyskytuje.
Tahle augmentace ji kreslí ON-THE-FLY jen do X (vstupu); GT (area label / point heatmapa) se NEMĚNÍ —
trať není mapový obsah, model se ji má naučit ignorovat / vidět skrz ni.

Sdílený util obou modelů (DRY, izomorfně s degrade.py): kreslí jen do X, fotometricky neutrální vůči Y.
Patří do AUGMENTACE (dataset.py), NE do build_pair (generator() drží render čistý — viz paměť
[[no-degradation-in-generator-phase]]; stejný princip jako degrade).

Rozměry jsou verify-against-source z ISOM 2000 spec §4.7 Overprinting symbols (docs/kb/isom-2000-spec.pdf,
papír 1:15 000): 701 Start = rovnostranný △ strana 7,0 mm / čára 0,35 mm; 702 Control = kruh ⌀ 6,0 mm /
0,35 mm; 703 Control number = výška číslice 4,0 mm; 704 Line = spojnice 0,35 mm. Barvy purple_a/b =
přetiskové fialové z map_gt.ISOM_REF (Sez. 72). Převod mm→px sdílí konvenci s inject.py (PX_PER_MM).

Sys.path skript (fáze B). Importují model/png2area/dataset.py i model/png2point/dataset.py.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))   # mpp.py = sourozenec (model/)
from mpp import CANONICAL_MPP   # noqa: E402

# --- převod mm papíru → px dlaždice (SSoT měřítka = mpp.CANONICAL_MPP, Sez. 126 audit C1/K1) ---
# mm papíru → m terénu (× scale/1000) → px (÷ mpp). Korpus 1:10000, dlaždice 1,33 m/px → ≈ 7,52 px/mm.
# Dřív TARGET_MPP=1,33 hardcoded (= „separate.TARGET_MPP") → symboly 1,64× velké vůči dlaždici 2,18.
# Páry se teď resamplují na CANONICAL_MPP před injektem (dataset.py) → měřítko sedí.
MAP_SCALE = 10000
TARGET_MPP = CANONICAL_MPP
PX_PER_MM = (MAP_SCALE / 1000.0) / TARGET_MPP   # ≈ 7,52 px/mm

# Fialové přetiskové barvy (= map_gt.ISOM_REF purple_a/b, Sez. 72; verify-against-source proti zdroji).
# Lehce zašuměné jako _BLACK v inject.py — reálný tisk/sken není čistě saturovaný; degradace v dataset.py
# je pak ještě rozmaže/posune. purple_a = start+kroužky+čísla, purple_b = varianta (náhodně per trať).
_PURPLE_A = (178, 24, 148)
_PURPLE_B = (176, 8, 230)

SIZE_JITTER = 0.20          # ± relativní jitter velikosti symbolů (různá měřítka korpusu + robustnost)
APPLY_PROB = 0.5            # pravděpodobnost, že se na dlaždici vůbec kreslí trať (polovina vzorků čistá)

# ISOM rozměry [mm papíru] → px přes PX_PER_MM (zaokrouhleno až při kreslení s jitterem).
_CIRCLE_DIAM_MM = 6.0       # 702 Control point ⌀
_START_SIDE_MM = 7.0        # 701 Start strana rovnostranného △
_FINISH_OUTER_MM = 7.0      # 706 Finish vnější kruh ⌀
_FINISH_INNER_MM = 5.0      # 706 Finish vnitřní kruh ⌀
_NUMBER_H_MM = 4.0          # 703 Control number výška číslice
_LINE_W_MM = 0.35           # 701-704 tloušťka čáry


def _number_font(size_px: int) -> ImageFont.ImageFont:
    """Font pro kontrolní čísla (703, výška 4 mm ≈ 30 px). load_default(size=) je v Pillow ≥ 10.1;
    na starší verzi spadne na default bitmap font (drobný — nevadí, čísla nejsou kritická pro augmentaci)."""
    try:
        return ImageFont.load_default(size=size_px)
    except TypeError:
        return ImageFont.load_default()


def _jit(value: float, rng: np.random.Generator) -> float:
    """Náhodný multiplikativní jitter ±SIZE_JITTER kolem hodnoty (robustnost na měřítko/styl)."""
    return value * (1.0 + rng.uniform(-SIZE_JITTER, SIZE_JITTER))


def _noisy(color: tuple[int, int, int], rng: np.random.Generator) -> tuple[int, int, int]:
    """Lehký šum na barvu (±12 na kanál) — tiskový/skenovací rozptyl, ne čistá konstanta."""
    return tuple(int(np.clip(c + rng.integers(-12, 13), 0, 255)) for c in color)


def _course_points(rng: np.random.Generator, height: int, width: int) -> list[tuple[int, int]]:
    """Vylosuje start, 5–12 kontrol a cíl; vrací tedy 7–14 bodů tratě."""
    margin = round(_CIRCLE_DIAM_MM * PX_PER_MM)
    n_controls = int(rng.integers(5, 13))
    # Náhodné body seřadíme podle x, aby spojnice připomínaly plynulou reálnou trať.
    # Když je dlaždice menší než dvojnásobný okraj, rozsah se zúží na jeden pixel.
    lo, hi = margin, max(margin + 1, width - margin)
    loy, hiy = margin, max(margin + 1, height - margin)
    xs = np.sort(rng.integers(lo, hi, size=n_controls + 2))
    ys = rng.integers(loy, hiy, size=n_controls + 2)
    return list(zip(xs.tolist(), ys.tolist()))


def _draw_triangle(draw: ImageDraw.ImageDraw, cx: float, cy: float, side: float,
                   angle: float, color, width: int) -> None:
    """Rovnostranný △ (701 Start) se středem (cx,cy), stranou `side`, natočený o `angle` rad.

    Vrcholy rovnostranného trojúhelníka leží na kružnici o poloměru R = side/√3 od středu, po 120°.
    `angle` = směr jednoho vrcholu (= „špička k první kontrole"); kreslí se jen obrys (přetisk je dutý)."""
    R = side / np.sqrt(3.0)
    pts = [(cx + R * np.cos(angle + k * 2 * np.pi / 3),
            cy + R * np.sin(angle + k * 2 * np.pi / 3)) for k in range(3)]
    draw.line(pts + [pts[0]], fill=color, width=width, joint="curve")


def _draw_circle(draw: ImageDraw.ImageDraw, cx: float, cy: float, diam: float,
                 color, width: int) -> None:
    """Dutý kroužek (702 Control / 706 Finish) — jen obrys, střed = přesná poloha prvku."""
    r = diam / 2.0
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=width)


def overprint_course(rgb: np.ndarray, seed: int) -> np.ndarray:
    """Nakreslí náhodnou ISOM trať (fialový přetisk 701-704/706) do KOPIE `rgb`. Vrací (H,W,3) uint8.

    `rgb`  — dlaždice (H,W,3) uint8 (gen render, případně s injektovanými body / po D4).
    `seed` — deterministický seed (reprodukovatelnost val/test, variabilita train).

    Kreslí JEN do X (vstupu): trať není mapový obsah → GT se nikde nemění. S pravděpodobností
    1-APPLY_PROB vrátí vstup beze změny (část vzorků zůstane bez tratě = model vidí obojí).
    """
    rng = np.random.default_rng(seed)
    if rng.random() >= APPLY_PROB:
        return rgb                                   # část dlaždic necháme čistou (bez tratě)

    H, W = rgb.shape[:2]
    img = Image.fromarray(np.ascontiguousarray(rgb), mode="RGB")
    draw = ImageDraw.Draw(img)
    color = _noisy(_PURPLE_A if rng.random() < 0.5 else _PURPLE_B, rng)
    lw = max(1, round(_LINE_W_MM * PX_PER_MM))       # tloušťka čáry v px (~3 px)
    font = _number_font(round(_NUMBER_H_MM * PX_PER_MM))   # výška číslice 4 mm ≈ 30 px

    # --- start + 5–12 kontrol + cíl, vše uvnitř bezpečného okraje dlaždice ---
    pts = _course_points(rng, H, W)

    # --- 704 Line: spojnice mezi po sobě jdoucími body (start → 1 → 2 → … → poslední) ---
    draw.line(pts, fill=color, width=lw, joint="curve")

    # --- 701 Start: rovnostranný △ na prvním bodě, špička směřuje k druhému bodu (k 1. kontrole) ---
    sx, sy = pts[0]
    nx, ny = pts[1]
    start_angle = float(np.arctan2(ny - sy, nx - sx))
    _draw_triangle(draw, sx, sy, _jit(_START_SIDE_MM * PX_PER_MM, rng), start_angle, color, lw)

    # --- 702 Control + 703 Control number: kroužek na každé kontrole + číslo vedle (1..n) ---
    for i, (cx, cy) in enumerate(pts[1:-1], start=1):     # vnitřní body = kontroly (bez startu/cíle)
        _draw_circle(draw, cx, cy, _jit(_CIRCLE_DIAM_MM * PX_PER_MM, rng), color, lw)
        # číslo posuň o ~poloměr kroužku diagonálně, ať neobsazuje střed (ISOM: blízko, nezakrývá detail)
        off = _CIRCLE_DIAM_MM * PX_PER_MM * 0.6
        draw.text((cx + off, cy - off), str(i), fill=color, font=font)

    # --- 706 Finish: dvojitý soustředný kruh na posledním bodě ---
    fx, fy = pts[-1]
    _draw_circle(draw, fx, fy, _jit(_FINISH_OUTER_MM * PX_PER_MM, rng), color, lw)
    _draw_circle(draw, fx, fy, _jit(_FINISH_INNER_MM * PX_PER_MM, rng), color, lw)

    return np.asarray(img, dtype=np.uint8)


if __name__ == "__main__":
    # self-check: nakresli trať na bílou i na šedý podklad, ulož vizuál do temp/ (proaktivní vizuál)
    import sys
    from pathlib import Path
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    out = Path(__file__).resolve().parents[1] / "temp"
    out.mkdir(exist_ok=True)
    for seed in range(4):
        base = np.full((512, 512, 3), 245, dtype=np.uint8)      # skoro bílý papír
        res = overprint_course(base, seed=seed)
        changed = int((res != base).any(axis=2).sum())
        Image.fromarray(res).save(out / f"purple_selfcheck_{seed}.png")
        print(f"seed {seed}: změněno {changed:6d} px ({100*changed/(512*512):.1f} %)  → "
              f"temp/purple_selfcheck_{seed}.png")
    print(f"PX_PER_MM={PX_PER_MM:.2f}  kruh⌀={_CIRCLE_DIAM_MM*PX_PER_MM:.0f}px  "
          f"start={_START_SIDE_MM*PX_PER_MM:.0f}px  čára={max(1, round(_LINE_W_MM*PX_PER_MM))}px")
