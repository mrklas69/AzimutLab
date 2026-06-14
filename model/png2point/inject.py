"""
inject.py — injekce bodových ISOM symbolů + GT heatmapa (Png2Point, Sez. 105).

Druhý ze tří reconstructorů (dekompozice OOM podle geometrie, Sez. 80): Png2Area (plochy, hotovo
Sez. 88-91) | **Png2Point (body)** | Png2Line (linie). Úloha: mapový sken → lokalizace + klasifikace
bodových ISOM symbolů (204 Boulder, 210 Stony ground, …).

PROČ INJEKCE místo generátorových bodů (klíčový rozdíl vůči Png2Area):
Png2Area bral GT z ploch, které generátor reálně kreslí (separace). Png2Point to NEMŮŽE — generátor
body skoro nedělá (kompas Sez. 96: gen Σ149 vs orig 3960 ≈ 4 %; 204 gen 7/orig 1064, 210 gen 0/orig 975).
Místo toho (nápad uživatele, IDEAS „Png2Point trénink injektováním symbolů"): na ČISTÝ gen render se
přidá kanonický ISOM symbol na NÁHODNOU ZNÁMOU souřadnici → GT zdarma (poloha + třída), libovolně
instancí, vyvážené třídy. Obchází nedostatek bodů v gen I nutnost je věrně umisťovat. Poloha symbolu
NEMUSÍ být fyzicky pravdivá (uprostřed jezera) — pro detektor IKONEK je kontext podružný, model se učí
„tenhle tvar = tahle třída" (reframe Sez. 79: pár [render, GT] konzistentní stačí).

GT = HEATMAPA (CenterNet-style, Zhou 2019): pro každý injektovaný bod splat 2D Gaussian peak do kanálu
jeho třídy. Detekce = peak (local-max NMS + práh). Heatmapa řeší husté symboly (210 Stony = POLE teček,
ne jeden bod — kartograf kreslí kamenitou zem polem teček, nález Sez. 96) lépe než bbox detektor.

Geometrie ikonek = ze spec/template_classic.omap (verify-against-source Sez. 105):
  204 Boulder           — plný černý kruh, r 0,4 mm (template id=32, point_symbol; gen BOULDER_RADIUS_PX).
  210 Stony ground      — pole jednotlivých teček 210.1, r 0,15 mm, rozestup ~1,2 mm (template area pattern
                          id na ř. 419: inner_radius=150 µm, line/point_distance=1200 µm; reálné = type=point).

Sys.path skript (fáze B, ne balík). Self-test (vizuál) dole: `python model/png2point/inject.py`.
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "model"))   # mpp.py = sdílený util reconstructorů
from mpp import CANONICAL_MPP   # noqa: E402

# --- rozlišení dlaždice: SSoT = model/mpp.CANONICAL_MPP (Sez. 126, audit C1/K1 oprava) ---
# Dřív TARGET_MPP=1,33 mylně odkazoval na separate.TARGET_MPP (interní separační downscale, NE měřítko
# dlaždice) → symboly se kreslily v px pro 1,33, zatímco dlaždice byla 2,18 → 1,64× velké. Teď páry X+Y
# resamplujeme na CANONICAL_MPP PŘED injektem (dataset.py) a symboly počítáme z TÉHOŽ měřítka.
TILE = 512                 # strana dlaždice (px), shodně s model/png2area/tile.py
TARGET_MPP = CANONICAL_MPP # m/px finální dlaždice (SSoT v mpp.py)
MAP_SCALE = 10000          # referenční měřítko korpusu 1:10000 (i 1:15000 existuje → SIZE_JITTER níže)
# mm papíru → m terénu (×scale/1000) → px (÷mpp). 0,4 mm @ 1:10000 / 1,33 mpp = 3,0 px.
PX_PER_MM = (MAP_SCALE / 1000.0) / TARGET_MPP   # ≈ 7,52 px/mm

# Černá ISOM kresba (reálné skeny nejsou čistě 0; degradace v dataset.py ji pak rozmaže/zesvětlí).
_BLACK = (25, 25, 25)
SIZE_JITTER = 0.25         # ± relativní jitter velikosti ikonky (různá měřítka korpusu + robustnost)


# ============================================================ registr bodových tříd
@dataclass
class PointClass:
    """Jedna bodová ISOM třída: jak ji nakreslit (stamp) a jak rozesít (sampler).

    code      — ISOM 2017-2 kód (string kvůli suffixům typu 210.1).
    name      — lidský název (do vizuálu/logu).
    radius_mm — poloměr ikonky v mm papíru (ze spec); px = radius_mm × PX_PER_MM.
    sigma_px  — sigma Gaussian peaku v GT heatmapě (~ velikost symbolu; malá ať se husté nesplynou).
    field     — True = symbol se kreslí jako POLE instancí (210 stony), False = jednotlivý bod (204).
    """
    code: str
    name: str
    radius_mm: float
    sigma_px: float
    field: bool = False


# Pořadí = index kanálu heatmapy (0..N_POINT-1). Start 204+210 (největší díry kompasu Sez. 104:
# 204 7,8 pb / 210 7,3 pb). Registr je rozšiřitelný — přidat 417/419/109/111/… = jeden řádek + stamp.
# sigma_px (nález Sez. 105): peak ~1 px na full-res 512 NEJDE naučit (protichůdný gradient → model
# rozmaže globálně) → floor ~2,5. 204 řídký → 3,0 (širší peak, snadno se ostří). 210 husté POLE teček
# (rozestup ~9 px) → 2,0: dost velký na naučení, dost malý ať se sousední peaky nesplynou (< rozestup/2).
POINT_CLASSES: list[PointClass] = [
    PointClass(code="204", name="Boulder",       radius_mm=0.40, sigma_px=3.0, field=False),
    PointClass(code="210", name="Stony ground",  radius_mm=0.15, sigma_px=2.0, field=True),
]
N_POINT = len(POINT_CLASSES)
CODE_TO_IDX = {pc.code: i for i, pc in enumerate(POINT_CLASSES)}


# ==================================================================== stamp ikonek
def _stamp_dot(draw: ImageDraw.ImageDraw, cx: float, cy: float, r_px: float,
               color=_BLACK) -> None:
    """Plný kruh (boulder 204 / stony tečka 210.1) se středem (cx,cy), poloměr r_px.

    PIL ellipse bere bounding box [x0,y0,x1,y1]. r_px může být <1 (stony na 1,33 mpp je ~1 px) →
    clamp na minimum 0,7 px ať tečka nezmizí úplně (degradace ji pak ještě ztenčí)."""
    r = max(0.7, r_px)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


# ============================================================ Gaussian heatmap splat
def _gaussian2d(sigma: float) -> np.ndarray:
    """2D Gaussian kernel (exp(-(x²+y²)/(2σ²))), velikost (2·3σ+1)². Peak = 1,0 ve středu.

    CenterNet konvence: heatmapa nese pravděpodobnost „tady je střed symbolu". Poloměr 3σ pokryje
    ~99 % hmoty Gaussovky → menší ořez šetří práci a nerozmazává sousední peaky."""
    rad = int(3 * sigma)
    ys, xs = np.mgrid[-rad:rad + 1, -rad:rad + 1]
    g = np.exp(-(xs * xs + ys * ys) / (2.0 * sigma * sigma))
    return g.astype(np.float32)


def _splat(heat: np.ndarray, cx: float, cy: float, sigma: float) -> None:
    """Vkreslí Gaussian peak do heatmapy `heat` (H,W) na (cx,cy) přes element-wise MAX.

    MAX (ne součet): když se dva peaky překryjí (husté stony pole), výsledek zůstane ≤1 a oba středy
    jsou pořád rozlišitelné lokálním maximem — to je CenterNet draw_umich_gaussian (Zhou 2019)."""
    H, W = heat.shape
    g = _gaussian2d(sigma)
    rad = g.shape[0] // 2
    ix, iy = int(round(cx)), int(round(cy))
    # průnik kernelu s plátnem (ošetří peaky u okraje)
    x0, x1 = max(0, ix - rad), min(W, ix + rad + 1)
    y0, y1 = max(0, iy - rad), min(H, iy + rad + 1)
    if x0 >= x1 or y0 >= y1:
        return
    # odpovídající výřez kernelu
    gx0, gy0 = x0 - (ix - rad), y0 - (iy - rad)
    gsub = g[gy0:gy0 + (y1 - y0), gx0:gx0 + (x1 - x0)]
    np.maximum(heat[y0:y1, x0:x1], gsub, out=heat[y0:y1, x0:x1])


# ==================================================================== sampler bodů
def _rand_size_px(pc: PointClass, rng: np.random.Generator) -> float:
    """Poloměr ikonky v px s náhodným jitterem (různá měřítka korpusu + robustnost vůči velikosti)."""
    base = pc.radius_mm * PX_PER_MM
    return base * (1.0 + rng.uniform(-SIZE_JITTER, SIZE_JITTER))


def _sample_single(pc: PointClass, idx: int, draw: ImageDraw.ImageDraw,
                   rng: np.random.Generator, n: int) -> list[tuple[float, float, int]]:
    """Rozeseje `n` jednotlivých bodů třídy (204 boulder) náhodně po dlaždici. Vrací [(cx,cy,idx)]."""
    pts = []
    for _ in range(n):
        cx = rng.uniform(0, TILE)
        cy = rng.uniform(0, TILE)
        _stamp_dot(draw, cx, cy, _rand_size_px(pc, rng))
        pts.append((cx, cy, idx))
    return pts


def _sample_field(pc: PointClass, idx: int, draw: ImageDraw.ImageDraw,
                  rng: np.random.Generator, n_fields: int) -> list[tuple[float, float, int]]:
    """Rozeseje `n_fields` POLÍ teček (210 stony) — elipsovitá oblast vyplněná tečkami na jittered gridu.

    ISOM stony = oblast pokrytá tečkami (ne jeden bod) → každá tečka je samostatná bodová instance
    (GT peak). Rozestup ~1,2 mm (spec) s jitterem, ať to nevypadá strojově. Vrací [(cx,cy,idx)] všech teček."""
    pts = []
    spacing = 1.2 * PX_PER_MM          # ~9 px rozestup teček (template point_distance 1200 µm)
    for _ in range(n_fields):
        # náhodná elipsovitá oblast pole
        ox = rng.uniform(0.1 * TILE, 0.9 * TILE)
        oy = rng.uniform(0.1 * TILE, 0.9 * TILE)
        rx = rng.uniform(3, 12) * spacing    # poloosa pole (3–12 teček napříč)
        ry = rng.uniform(3, 12) * spacing
        # projdi grid uvnitř bbox pole, tečku polož jen je-li uvnitř elipsy (+ jitter polohy)
        gy = oy - ry
        while gy <= oy + ry:
            gx = ox - rx
            while gx <= ox + rx:
                jx = gx + rng.uniform(-0.3, 0.3) * spacing
                jy = gy + rng.uniform(-0.3, 0.3) * spacing
                if ((jx - ox) / rx) ** 2 + ((jy - oy) / ry) ** 2 <= 1.0 and 0 <= jx < TILE and 0 <= jy < TILE:
                    _stamp_dot(draw, jx, jy, _rand_size_px(pc, rng))
                    pts.append((jx, jy, idx))
                gx += spacing
            gy += spacing
    return pts


def inject_tile(rgb: np.ndarray, seed: int,
                *, n_boulder: tuple[int, int] = (40, 120),
                n_stony_fields: tuple[int, int] = (0, 2)
                ) -> tuple[np.ndarray, np.ndarray]:
    """Injektuje bodové symboly do RGB dlaždice + vyrobí GT heatmapy. Hlavní vstup pro dataset.py.

    rgb  — (TILE,TILE,3) uint8 čistý gen render (podklad bez bodů, point_base.png, Sez. 106).
    seed — deterministická realizace (jiný seed každou epochu → injekce = nekonečná augmentace).
    n_*  — (min,max) rozsah počtu instancí (boulder bodů / stony polí) na dlaždici; náhoda v rozsahu.
           n_boulder ZÁMĚRNĚ vysoké (40-120, Sez. 106): focal loss normalizuje gradient počtem pozitiv,
           a 204 řídký (~10/dlaždice) se vedle hustého 210 (~200 teček, 19×) VŮBEC nenaučil (gate+diag
           F1 0,00). Hustota 204 srovnatelná s 210 → 204 naskočí (diag F1 0→0,70). Reframe Sez. 79 to
           dovoluje: detektor IKONEK, počet/poloha nemusí být reálné — hustota slouží jen k balancu.

    Vrací:
      x_out — (TILE,TILE,3) uint8 RGB s vkreslenými symboly.
      heat  — (N_POINT,TILE,TILE) float32 [0,1] GT heatmapy (Gaussian peaky per třída).
    """
    rng = np.random.default_rng(seed)
    img = Image.fromarray(rgb.copy())          # kopie ať nešaháme na cache dlaždice
    draw = ImageDraw.Draw(img)

    all_pts: list[tuple[float, float, int]] = []
    for idx, pc in enumerate(POINT_CLASSES):
        if pc.field:
            nf = int(rng.integers(n_stony_fields[0], n_stony_fields[1] + 1))
            all_pts += _sample_field(pc, idx, draw, rng, nf)
        else:
            nb = int(rng.integers(n_boulder[0], n_boulder[1] + 1))
            all_pts += _sample_single(pc, idx, draw, rng, nb)

    # GT heatmapy — splat Gaussian peak za každý injektovaný bod do kanálu jeho třídy
    heat = np.zeros((N_POINT, TILE, TILE), dtype=np.float32)
    for cx, cy, idx in all_pts:
        _splat(heat[idx], cx, cy, POINT_CLASSES[idx].sigma_px)

    return np.asarray(img, dtype=np.uint8), heat


# ==================================================================== self-test / vizuál
def _heat_overlay(rgb: np.ndarray, heat: np.ndarray) -> Image.Image:
    """Vizuál: RGB s injekcí + barevné peaky heatmapy (204 červeně, 210 modře) pro kontrolu zarovnání."""
    out = rgb.astype(np.float32).copy()
    colors = np.array([[230, 40, 40], [40, 90, 230]], dtype=np.float32)   # 204 / 210
    for idx in range(min(N_POINT, len(colors))):
        a = heat[idx][..., None]                 # (H,W,1) alfa = síla peaku
        out = out * (1 - a) + colors[idx] * a
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # Podklad: zkus vzít reálnou dlaždici z area_tiles (mrkla), jinak bílý papír (smoke všude).
    tiles = sorted((_REPO_ROOT / "resources" / "area_tiles" / "train").glob("*/*_x.png"))
    if tiles:
        base = np.asarray(Image.open(tiles[len(tiles) // 2]).convert("RGB"), dtype=np.uint8)
        src = f"area_tile {tiles[len(tiles)//2].parent.name}"
    else:
        base = np.full((TILE, TILE, 3), 255, dtype=np.uint8)
        src = "bílý papír (žádné area_tiles)"

    print(f"PX_PER_MM={PX_PER_MM:.2f}  204 r={0.40*PX_PER_MM:.1f}px  210 r={0.15*PX_PER_MM:.1f}px")
    print(f"tříd={N_POINT} {[pc.code for pc in POINT_CLASSES]}  podklad: {src}")

    x, heat = inject_tile(base, seed=7)
    n_per = [(POINT_CLASSES[i].code, int((heat[i] > 0.99).sum())) for i in range(N_POINT)]
    print(f"injekce hotova: x{x.shape} heat{heat.shape}  peaků(~max) per třída: {n_per}")

    out_dir = _REPO_ROOT / "temp"
    out_dir.mkdir(exist_ok=True)
    Image.fromarray(x).save(out_dir / "inject_x.png")
    _heat_overlay(x, heat).save(out_dir / "inject_overlay.png")
    print(f"vizuál → {out_dir/'inject_x.png'} , {out_dir/'inject_overlay.png'}")
