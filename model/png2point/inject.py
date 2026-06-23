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
  417 Prominent large tree   — zelený PRSTENEC (kroužek), zeleň ISOM color 3 (Sez. 128, scope rozšířen).
  419 Prom. vegetation feat. — zelený X s bílou knockout svatozáří (Sez. 128).
  531 Prom. man-made x       — ČERNÝ X BEZ svatozáře (Sez. 158, template id 156 = 2 černé diagonály ±516 µm).
                          Plné rozměry/barvy = registr POINT_CLASSES níže (verify-against-source ISOM 2017-2).

Sys.path skript (fáze B, ne balík). Self-test (vizuál) dole: `python model/png2point/inject.py`.
"""
import sys
from dataclasses import dataclass
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
# Zelená vegetační kresba 417/419 (verify-against-source template_classic.omap: symboly nesou color 3
# "Green 100%"). Hodnota = palette `green3`/generator `C_GREEN3` (45,169,79), kterým generátor kreslí 417
# → injekce barevně konzistentní s reálným renderem. Lokální konstanta (jako _BLACK), inject.py je self-contained.
_GREEN = (45, 169, 79)
# Bílý knockout ("White over green", template color 22): 417/419 mají kolem zeleného symbolu bílou svatozář,
# která vyřízne zelený podklad (les) → symbol vynikne. Klíčové pro detekci i realismus (na lese by zelený
# symbol jinak splynul). Na bílém/žlutém podkladu je svatozář neviditelná (bílá na bílé) → realistické.
_WHITE = (255, 255, 255)
SIZE_JITTER = 0.25         # ± relativní jitter velikosti ikonky (různá měřítka korpusu + robustnost)


# ============================================================ registr bodových tříd
@dataclass
class PointClass:
    """Jedna bodová ISOM třída: jak ji nakreslit (stamp) a jak rozesít (sampler).

    code      — ISOM 2017-2 kód (string kvůli suffixům typu 210.1).
    name      — lidský název (do vizuálu/logu).
    radius_mm — poloměr ikonky v mm papíru (ze spec); px = radius_mm × PX_PER_MM.
                "dot": poloměr kruhu · "tree": poloměr zeleného prstence · "cross": polodélka ramene X.
    sigma_px  — sigma Gaussian peaku v GT heatmapě (~ velikost symbolu; malá ať se husté nesplynou).
    field     — True = symbol se kreslí jako POLE instancí (210 stony), False = jednotlivý bod (204/417/419).
    kind      — tvar ikonky: "dot" plný kruh (204/210) | "tree" zelený prstenec + bílá svatozář (417)
                | "cross" X + (volitelně) bílá svatozář (419 zelený / 531 černý).
    color     — barva kresby (204/210/531 černá, 417/419 zelená).
    halo      — bílý knockout (svatozář) kolem tree/cross. ANO u zelených 417/419 (template „white over
                green", color 22 — bez ní zelený symbol splyne s lesem); NE u černého 531 (template id 156 =
                2 čisté černé diagonály, žádný white element; černá je vidět nad vším). Verify-against-source.
    n_range   — (min,max) počtu instancí na dlaždici (single), resp. počtu POLÍ (field). Náhoda v rozsahu;
                u řídkých tříd ZÁMĚRNĚ vysoké kvůli focal balancu (nález Sez. 106, viz inject_tile docstring).
    peak_thr  — práh detekce peaku v predikované heatmapě PER TŘÍDA (sweep Sez. 129). Globální 0,30 byl vždy
                kompromis: zelené 417/419 soupeří s porostem o FP → chtějí VYŠŠÍ práh (417 přestřeloval P 0,38),
                černé 204/210 NIŽŠÍ. Jeden práh nešel sladit (posun pomohl jedněm, uškodil druhým) → per-class.
                Hodnoty z robustní (ploché) části F1 křivky, ne ostré in-sample optimum (3 skeny = malý vzorek).
    """
    code: str
    name: str
    radius_mm: float
    sigma_px: float
    field: bool = False
    kind: str = "dot"
    color: tuple = _BLACK
    n_range: tuple = (40, 120)
    peak_thr: float = 0.30
    halo: bool = True       # bílý knockout u tree/cross (zelené ANO, černý 531 NE — viz docstring)


# Pořadí = index kanálu heatmapy (0..N_POINT-1). Start 204+210 (největší díry kompasu Sez. 104:
# 204 7,8 pb / 210 7,3 pb); Sez. 128 přidány 417/419 (vrchol KPI žebříčku děr — Prominent large tree /
# Prominent vegetation feature). Registr je rozšiřitelný — přidat třídu = jeden řádek + případně stamp tvar.
# sigma_px (nález Sez. 105): peak ~1 px na full-res 512 NEJDE naučit (protichůdný gradient → model
# rozmaže globálně) → floor ~2,5. 204 řídký → 3,0 (širší peak, snadno se ostří). 210 husté POLE teček
# (rozestup ~9 px) → 2,0: dost velký na naučení, dost malý ať se sousední peaky nesplynou (< rozestup/2).
# 417/419 jsou VÝRAZNÉ zelené symboly (footprint 13,5 m) → širší peak (3,5 / 4,0; X 419 je rozměrnější).
# n_range 417 (Sez. 135): sníženo (20,60)→(10,30) na REÁLNOU hustotu (měřeno z eval_real GT/plocha:
# Velbloud ~20 / Blatná ~12 / Bedř ~12 stromů na dlaždici; staré ⌀40 = 2–3× nad realitou → model fíroval
# 417 na porost = přestřel FP). Umělá hustota kvůli focal balancu (jako 204) je dnes zbytečná: focal prior
# bias init (Sez. 125) drží řídké třídy bez nafouknutí. 419 ponecháno (transfer 0,67–0,76, funguje).
# peak_thr (sweep Sez. 129, agreg. 3 reálné skeny): 204→0,30 (= optimum), 210→0,20 (kolabuje, nižší práh
# vrátí pár teček), 417→0,45 (přestřel: 0,30 F1 0,46 → 0,45 F1 0,54, P 0,38→0,57), 419→0,40 (0,74→0,76).
# 531 Prom. man-made feature – x (Sez. 158): ČERNÝ X = mirror 419 zelený X, ale bez svatozáře (halo=False,
# template id 156 = 2 čisté černé diagonály ±516 µm color 2). Sázka A3(c): distinktivní tvar X přenáší
# (419 SILNÝ 0,67–0,76, Sez. 128) → černý X by měl taky. Měřitelný na realitě (probe Sez. 158: Velbloud 20 /
# Blatná 3 / Bedř 3 objektů crosswalk-aware). radius_mm 0,516 = template polodélka; sigma 3,5 (menší než 419
# 585 µm). n_range (10,30) jako 417 — reálně řidší (~1,3/km²), ale focal balance vedle hustého 210 chce dost
# pozitiv (Sez. 106); injekce = detektor IKONEK, počet nemusí být reálný. peak_thr 0,60 (sweep Sez. 158
# na eval_real, izomorf 417/419 Sez. 129): seed-0 měl recall vysoký / precision nízkou (FP) jako 417;
# Velbloud (20 GT, nejspolehlivější) plochá část křivky 0,55–0,70 → robustní 0,60 dalo F1 0,356→0,737
# (P0,78/R0,70) = SROVNATELNÉ s 419 0,74 → distinktivní černý X přenáší jako zelený. halo=False, color=_BLACK.
# 525 Small tower (⊤) + 527 Fodder rack (Λ+noha) — další DISTINKTIVNÍ černé man-made body (izomorf 531).
# Verify-against-source template id 150/152 (color 2, w 240 µm; nové kind "tower"/"fodder"). Měřitelné
# crosswalk-aware PŘED tréninkem (probe: 525 Bedř 24 / TOTAL 45, 527 Slovanka 7 / Bedř 6 / TOTAL 18 —
# anti-A1). Sázka stejná jako 531: distinktivní tvar přenáší. radius_mm = pološíře horního prvku (525
# příčka 750 µm, 527 stříška 615 µm). sigma/n_range z 531. peak_thr (sweep Sez. 159 na eval_real, izomorf
# 531): černá man-made kresba má hodně FP (cesty/text) → VYSOKÝ práh (525→0,70 Bedř plató F1 0,77;
# 527→0,65 mean max 0,71). Reálný transfer: 525 SILNÝ (Bedř 0,766, na úrovni 419), 527 STŘEDNÍ-DOBRÝ
# (seed0 Bedř 0,833 / Slovanka 0,667; medián 3 seedů 0,50 — seed-citlivý vedle hustého 210).
POINT_CLASSES: list[PointClass] = [
    PointClass(code="204", name="Boulder",                  radius_mm=0.40,  sigma_px=3.0, field=False, kind="dot",    color=_BLACK, n_range=(40, 120), peak_thr=0.30),
    PointClass(code="210", name="Stony ground",             radius_mm=0.15,  sigma_px=2.0, field=True,  kind="dot",    color=_BLACK, n_range=(0, 2),    peak_thr=0.20),
    PointClass(code="417", name="Prominent large tree",     radius_mm=0.45,  sigma_px=3.5, field=False, kind="tree",   color=_GREEN, n_range=(10, 30),  peak_thr=0.45),
    PointClass(code="419", name="Prominent veg. feature",   radius_mm=0.60,  sigma_px=4.0, field=False, kind="cross",  color=_GREEN, n_range=(15, 45),  peak_thr=0.40),
    PointClass(code="531", name="Prom. man-made x",         radius_mm=0.516, sigma_px=3.5, field=False, kind="cross",  color=_BLACK, n_range=(10, 30),  peak_thr=0.60, halo=False),
    PointClass(code="525", name="Small tower",              radius_mm=0.75,  sigma_px=3.5, field=False, kind="tower",  color=_BLACK, n_range=(10, 30),  peak_thr=0.70, halo=False),
    PointClass(code="527", name="Fodder rack",              radius_mm=0.615, sigma_px=3.5, field=False, kind="fodder", color=_BLACK, n_range=(10, 30),  peak_thr=0.65, halo=False),
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


def _stamp_tree(draw: ImageDraw.ImageDraw, cx: float, cy: float, r_px: float,
                color=_GREEN, halo: bool = True) -> None:
    """417 Prominent large tree: zelený PRSTENEC v bílé knockout svatozáři (verify-against-source template).

    Template: prstenec color 3 (Green) v bílém disku color 22 ("White over green", knockout zeleného
    podkladu). Svatozář ~1,65× poloměr prstence (template white disk 825 µm vs prstenec ~500 µm).
    Pořadí: nejdřív bílý disk (vyřízne les), pak zelený prstenec navrch.
    halo=False → prstenec bez bílého disku (pro případnou černou prstencovou třídu)."""
    r = max(1.2, r_px)
    if halo:
        hr = r * 1.65
        draw.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=_WHITE)       # bílý knockout
    w = max(1, int(round(r * 0.55)))                                          # tloušťka prstence
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=w)


def _stamp_cross(draw: ImageDraw.ImageDraw, cx: float, cy: float, r_px: float,
                 color=_GREEN, halo: bool = True) -> None:
    """X křížek. 419 Prom. veg. feature: ZELENÝ X v bílé svatozáři (halo=True).
    531 Prom. man-made feature – x: ČERNÝ X bez svatozáře (halo=False).

    Template 419 (id 104): 2 zelené diagonály (color 3, w 270) + 2 silnější bílé (color 22, w 540 = knockout).
    Template 531 (id 156): 2 čisté černé diagonály (color 2, w 240), žádný white element → halo=False.
    Pořadí (halo): nejdřív obě bílé diagonály (svatozář), pak barevné navrch. r_px = polodélka ramene X."""
    r = max(1.5, r_px)
    wg = max(1, int(round(r * 0.45)))            # tloušťka barevné diagonály
    a = [(cx - r, cy - r), (cx + r, cy + r)]     # diagonála ↘
    b = [(cx - r, cy + r), (cx + r, cy - r)]     # diagonála ↗
    if halo:
        wh = wg + max(2, int(round(r * 0.6)))    # bílá svatozář o ~r širší než barevná
        draw.line(a, fill=_WHITE, width=wh); draw.line(b, fill=_WHITE, width=wh)
    draw.line(a, fill=color, width=wg);  draw.line(b, fill=color, width=wg)


def _stamp_tower(draw: ImageDraw.ImageDraw, cx: float, cy: float, r_px: float,
                 color=_BLACK) -> None:
    """525 Small tower: vodorovná příčka nahoře + svislá noha dolů (⊤). Černý man-made bod (halo=False).

    Verify-against-source template id 150 (color 2, line_width 240 µm): příčka -750..750 v y=-462,
    noha 0,-462..0,903 (µm; osa y DOLŮ). Proporce vztažené k pološíři příčky r (=750 µm): příčka ve
    výšce -0,616r, noha od příčky až do +1,204r. r_px = pološíře příčky v px."""
    r = max(1.5, r_px)
    w = max(1, int(round(r * 0.32)))                       # 240/750 ≈ 0,32 = tloušťka linie
    y_bar = cy - 0.616 * r                                 # výška vodorovné příčky
    draw.line([(cx - r, y_bar), (cx + r, y_bar)], fill=color, width=w)      # ⊤ příčka
    draw.line([(cx, y_bar), (cx, cy + 1.204 * r)], fill=color, width=w)     # svislá noha


def _stamp_fodder(draw: ImageDraw.ImageDraw, cx: float, cy: float, r_px: float,
                  color=_BLACK) -> None:
    """527 Fodder rack: stříška Λ (obrácené V) nahoře + svislá noha dolů (krmelec). Černý (halo=False).

    Verify-against-source template id 152 (color 2, line_width 240 µm): stříška -615,-55→0,-411→615,-55,
    noha 0,-411..0,819 (µm; osa y DOLŮ). Proporce vztažené k pološíři stříšky r (=615 µm): vrchol -0,668r,
    kraje -0,089r, noha až do +1,332r. r_px = pološíře stříšky v px."""
    r = max(1.5, r_px)
    w = max(1, int(round(r * 0.39)))                       # 240/615 ≈ 0,39 = tloušťka linie
    apex = (cx, cy - 0.668 * r)                            # vrchol stříšky
    draw.line([(cx - r, cy - 0.089 * r), apex], fill=color, width=w)        # levé rameno Λ
    draw.line([apex, (cx + r, cy - 0.089 * r)], fill=color, width=w)        # pravé rameno Λ
    draw.line([apex, (cx, cy + 1.332 * r)], fill=color, width=w)            # svislá noha


def _stamp(draw: ImageDraw.ImageDraw, cx: float, cy: float, r_px: float, pc: "PointClass") -> None:
    """Dispatcher tvaru ikonky podle pc.kind (dot / tree / cross / tower / fodder). Sjednocuje kresbu pro oba samplery."""
    if pc.kind == "tree":
        _stamp_tree(draw, cx, cy, r_px, pc.color, pc.halo)
    elif pc.kind == "cross":
        _stamp_cross(draw, cx, cy, r_px, pc.color, pc.halo)
    elif pc.kind == "tower":
        _stamp_tower(draw, cx, cy, r_px, pc.color)
    elif pc.kind == "fodder":
        _stamp_fodder(draw, cx, cy, r_px, pc.color)
    else:
        _stamp_dot(draw, cx, cy, r_px, pc.color)


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
    """Rozeseje `n` jednotlivých bodů třídy (204 boulder / 417 strom / 419 veg. feature) náhodně. Vrací [(cx,cy,idx)]."""
    pts = []
    for _ in range(n):
        cx = rng.uniform(0, TILE)
        cy = rng.uniform(0, TILE)
        _stamp(draw, cx, cy, _rand_size_px(pc, rng), pc)
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
                    _stamp(draw, jx, jy, _rand_size_px(pc, rng), pc)
                    pts.append((jx, jy, idx))
                gx += spacing
            gy += spacing
    return pts


def inject_tile(rgb: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Injektuje bodové symboly do RGB dlaždice + vyrobí GT heatmapy. Hlavní vstup pro dataset.py.

    rgb  — (TILE,TILE,3) uint8 čistý gen render (podklad bez bodů, point_base.png, Sez. 106).
    seed — deterministická realizace (jiný seed každou epochu → injekce = nekonečná augmentace).

    Počty instancí jsou per-třída v PointClass.n_range (single = počet bodů, field = počet polí).
    n_range u 204 ZÁMĚRNĚ vysoké (40-120, Sez. 106): focal loss normalizuje gradient počtem pozitiv,
    a 204 řídký (~10/dlaždice) se vedle hustého 210 (~200 teček, 19×) VŮBEC nenaučil (gate+diag F1 0,00).
    Hustota 204 srovnatelná s 210 → 204 naskočí (diag F1 0→0,70). Reframe Sez. 79 to dovoluje: detektor
    IKONEK, počet/poloha nemusí být reálné — hustota slouží jen k balancu. 417/419 (Sez. 128) drží nižší
    rozsah (reálně řidší), ale dost vysoký, ať je focal nezdusí vedle hustého 210.

    Vrací:
      x_out — (TILE,TILE,3) uint8 RGB s vkreslenými symboly.
      heat  — (N_POINT,TILE,TILE) float32 [0,1] GT heatmapy (Gaussian peaky per třída).
    """
    rng = np.random.default_rng(seed)
    img = Image.fromarray(rgb.copy())          # kopie ať nešaháme na cache dlaždice
    draw = ImageDraw.Draw(img)

    all_pts: list[tuple[float, float, int]] = []
    for idx, pc in enumerate(POINT_CLASSES):
        n = int(rng.integers(pc.n_range[0], pc.n_range[1] + 1))
        if pc.field:
            all_pts += _sample_field(pc, idx, draw, rng, n)
        else:
            all_pts += _sample_single(pc, idx, draw, rng, n)

    # GT heatmapy — splat Gaussian peak za každý injektovaný bod do kanálu jeho třídy
    heat = np.zeros((N_POINT, TILE, TILE), dtype=np.float32)
    for cx, cy, idx in all_pts:
        _splat(heat[idx], cx, cy, POINT_CLASSES[idx].sigma_px)

    return np.asarray(img, dtype=np.uint8), heat


# ==================================================================== self-test / vizuál
def _heat_overlay(rgb: np.ndarray, heat: np.ndarray) -> Image.Image:
    """Vizuál: RGB s injekcí + barevné peaky heatmapy pro kontrolu zarovnání (204 červeně, 210 modře,
    417 azurově, 419 fialově, 531 oranžově). Barvy = kontrolní, nesouvisí s ISOM (izomorf eval_real._overlay)."""
    out = rgb.astype(np.float32).copy()
    colors = np.array([[230, 40, 40], [40, 90, 230], [20, 200, 200], [200, 40, 200], [255, 140, 0]],
                      dtype=np.float32)   # 204 / 210 / 417 / 419 / 531
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

    print(f"PX_PER_MM={PX_PER_MM:.2f}  "
          + "  ".join(f"{pc.code}({pc.kind}) r={pc.radius_mm*PX_PER_MM:.1f}px" for pc in POINT_CLASSES))
    print(f"tříd={N_POINT} {[pc.code for pc in POINT_CLASSES]}  podklad: {src}")

    x, heat = inject_tile(base, seed=7)
    n_per = [(POINT_CLASSES[i].code, int((heat[i] > 0.99).sum())) for i in range(N_POINT)]
    print(f"injekce hotova: x{x.shape} heat{heat.shape}  peaků(~max) per třída: {n_per}")

    out_dir = _REPO_ROOT / "temp"
    out_dir.mkdir(exist_ok=True)
    Image.fromarray(x).save(out_dir / "inject_x.png")
    _heat_overlay(x, heat).save(out_dir / "inject_overlay.png")
    print(f"vizuál → {out_dir/'inject_x.png'} , {out_dir/'inject_overlay.png'}")
