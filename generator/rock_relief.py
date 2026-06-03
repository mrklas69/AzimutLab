"""
rock_relief.py — detekce skalních útvarů (ploch) z DMR 5G sklonu (real-půlka, projekce, Sez. 63).

Náhrada generalizované ZABAGED `Skalní_útvary` (jeden blob přes celý masiv) věrnou geometrií
z výškopisu: skalní stěna je strmá → vysoký práh sklonu → morfologické scelení stěn do BLOKU →
vektorové polygony jednotlivých věží/bloků s otevřenými průchody. Stejná kategorie jako vrstevnice
a form lines = DETERMINISTICKÁ PROJEKCE z DMR (NE proxy). Algoritmus převzat z `temp/rockcore/`
(předchozí session, laděno na pískovcovém skalním městě Šulcák/Český ráj).

Klíčové (z handoffu, neopakovat chyby):
  - Maska se staví na SKLONU (směrově nezávislý), NE na tmavosti hillshade (ta je směrově závislá →
    odvrácené svahy vypadají skalnaté, ač skálou nejsou).
  - Vysoký práh (~46°) = jen jisté skalní stěny; ploché vršky věží mají sklon ~0° → samotný práh dá
    jen tenké slivery podél hran. Proto morfologický UZÁVĚR (closing) stěny + vršek scelí do plochy.
  - Velké díry (průchody mezi věžemi) NECHAT otevřené; vyplnit jen malé (vrcholové plošiny).

Závislosti: numpy + scipy.ndimage (morfologie + connected-components) + contourpy (vektorizace masky
na úrovni 0.5 — týž nástroj jako vrstevnice; NE rasterio/shapely, ty v projektu nejsou). Fetch DMR
přes sdílený `dmr.py` (S-JTSK, ne UTM jako rockcore). Vrací polygony [outer, díra…] v S-JTSK metrech
— TÝŽ tvar jako zabaged.geom_to_polygons → zapadne beze změny do kreslení/omapu pro ISOM 206.
"""
import math

import numpy as np
import contourpy
from scipy.ndimage import (gaussian_filter, binary_opening, binary_closing,
                           binary_fill_holes, label)

from dmr import fetch_elevation_grid   # connectors/ je na sys.path (zařídí generator.py)

# --- laditelné parametry (metry / stupně; převzato z rockcore, laděno na Šulcáku) ---
TARGET_PX_M = 1.5          # cílové rozlišení hi-res DMR fetchu [m/buňka] (rockcore ~0,7; my výš kvůli
#                            větším výsekům + limitu ImageServeru). Menší = jemnější věže, větší fetch.
#                            1,5 m drží jen u menších výseků; velké landscape (6×4 km) zhrubne plošný cap níž.
# ImageServer exportImage vrací HTTP 500 nad ~7 Mpx (F32 tiff) — empiricky práh mezi 6,8 (OK) a 8,2 Mpx
# (Sez. 65). Limitujeme PLOCHU (ne stranu — 6×4 km @ 1,5 m = 4000×2667 = 10,7 Mpx mělo stranu < MAX_PX,
# přesto 500). Cap 6,5 Mpx = pod prahem, doložené HS 6,3 Mpx prochází opakovaně; 6×4 km → ~1,9 m/px.
MAX_AREA_PX = 6_500_000    # plošný strop hi-res gridu (gw_hi*gh_hi) — primární ochrana proti 500
MAX_PX = 4000              # sekundární strop strany (limit ArcGIS exportImage na stranu) → u velkých výseků zhrubne
SLOPE_THR_DEG = 46.0       # práh sklonu „jistá skalní stěna" (nižší nabírá strmé lesní svahy — chyba A)
GAUSS_SIGMA = 0.6          # vyhlazení DMR před gradientem (potlačí pixelový šum sklonu)
OPEN_M = 1.0               # despeckle (binary_opening) — odstraní izolované pixely sklonu
CLOSE_M = 4.0              # uzávěr (binary_closing) — stěny + vršek scelí do bloku (jádro algoritmu)
FILL_MAX_M2 = 250.0        # vyplnit jen díry menší než tohle (vrcholové plošiny); větší = průchody → nechat
MIN_AREA_M2 = 60.0         # zahodit fragmenty pod tuhle plochu (drobky, ne skalní blok)
SIMPLIFY_M = 1.2           # Douglas-Peucker tolerance [m] (odstraní pixelové schody)
CHAIKIN_ITERS = 2          # Chaikinovo vyhlazení obrysu (organický tvar; legitimní — de-pixeluje RASTER
#                            masku, NE už-čisté vektory jako ZABAGED Sez. 30)


def _disk(r: int) -> np.ndarray:
    """Boolean kruhový strukturní element o poloměru r (pro morfologii)."""
    r = max(int(r), 0)
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r


def _rock_mask(slope_deg: np.ndarray, px_m: float) -> np.ndarray:
    """Sklon → boolean maska skalních bloků. Dvoukrok: práh stěn → closing do plochy (handoff §4)."""
    m = slope_deg >= SLOPE_THR_DEG
    m = binary_opening(m, _disk(max(1, round(OPEN_M / px_m))))      # despeckle
    m = binary_closing(m, _disk(max(1, round(CLOSE_M / px_m))))     # stěny → blok
    # vyplnit jen MALÉ díry (vršky věží); velké průchody mezi věžemi nechat otevřené
    filled = binary_fill_holes(m)
    holes = filled & ~m
    lab, _ = label(holes)
    sizes = np.bincount(lab.ravel())
    lim = FILL_MAX_M2 / (px_m * px_m)
    for i in range(1, len(sizes)):
        if sizes[i] < lim:
            m[lab == i] = True
    # zahodit drobné fragmenty (ne skalní blok)
    lab, _ = label(m)
    sizes = np.bincount(lab.ravel())
    lim = MIN_AREA_M2 / (px_m * px_m)
    for i in range(1, len(sizes)):
        if sizes[i] < lim:
            m[lab == i] = False
    return m


def _contour_rings(mask: np.ndarray) -> list[np.ndarray]:
    """Boolean maska → uzavřené prstence hranice (úroveň 0.5) v souřadnicích (col, row).

    Maska se obloží False okrajem (1 px) → i bloky u kraje výseku dají UZAVŘENOU smyčku (jinak by
    contourpy vrátil otevřenou linii podél okraje). Souřadnice contourpy = (x=sloupec, y=řádek);
    odečtením paddingu zpět na původní grid. Týž nástroj jako vrstevnice (marching squares)."""
    padded = np.pad(mask.astype(float), 1, constant_values=0.0)
    cg = contourpy.contour_generator(z=padded, line_type=contourpy.LineType.Separate)
    rings: list[np.ndarray] = []
    for line in cg.lines(0.5):
        if len(line) < 4:
            continue
        ring = np.asarray(line, dtype=float) - 1.0     # zruš padding offset → (col, row) v gridu
        if not np.allclose(ring[0], ring[-1]):         # zajisti uzavřenost
            ring = np.vstack([ring, ring[0]])
        rings.append(ring)
    return rings


def _signed_area(ring: np.ndarray) -> float:
    """Orientovaná plocha prstence (shoelace) — absolutní hodnota = velikost, znaménko = orientace."""
    x, y = ring[:, 0], ring[:, 1]
    return 0.5 * float(np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]))


def _point_in_ring(pt, ring: np.ndarray) -> bool:
    """Leží bod uvnitř prstence? Ray-casting (even-odd). Pro vnoření díra↔outer."""
    x, y = pt
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            if x < xj + (xi - xj) * (y - yj) / (yi - yj):
                inside = not inside
        j = i
    return inside


def _group_holes(rings: list[np.ndarray]) -> list[list[np.ndarray]]:
    """Seskup prstence do polygonů [outer, díra…] podle vnoření (even-odd hloubka).

    Hloubka = počet jiných prstenů, které daný obsahují. Sudá = vnější obrys (výplň), lichá = díra
    (průchod). Díra patří k bezprostřednímu rodiči (obsahující prsten o hloubku menší). Mirror struktury
    zabaged.geom_to_polygons → konzument (_poly_to_grid_px / _draw_area_symbol / omap) beze změny."""
    n = len(rings)
    areas = [abs(_signed_area(r)) for r in rings]
    # bbox každého prstence + testovací bod každého prstence (jeho první vrchol) → levný
    # ODMÍTACÍ filtr před drahým _point_in_ring (čistý Python O(vrcholy)). Bez něj je smyčka
    # O(n² × vrcholy); u husté vegetace (tisíce prstenců, Sez. 84) to explodovalo na desítky
    # minut. bbox-test je exaktní: leží-li bod mimo bbox prstence j, nemůže být ani uvnitř j.
    bx0 = np.array([r[:, 0].min() for r in rings]); bx1 = np.array([r[:, 0].max() for r in rings])
    by0 = np.array([r[:, 1].min() for r in rings]); by1 = np.array([r[:, 1].max() for r in rings])
    pts = np.array([r[0] for r in rings])                   # (n,2) testovací body
    contains = [[False] * n for _ in range(n)]
    for i in range(n):
        px, py = pts[i]
        # bbox-test naráz přes všechny prstence (vektorově); drahý _point_in_ring jen na kandidáty
        in_box = (bx0 <= px) & (px <= bx1) & (by0 <= py) & (py <= by1)
        for j in np.where(in_box)[0]:
            if i != j and areas[j] > areas[i] and _point_in_ring((px, py), rings[j]):
                contains[i][j] = True
    depth = [sum(contains[i]) for i in range(n)]
    polys: dict[int, list[np.ndarray]] = {i: [rings[i]] for i in range(n) if depth[i] % 2 == 0}
    for i in range(n):
        if depth[i] % 2 == 1:                                   # díra
            parents = [j for j in range(n) if contains[i][j] and depth[j] == depth[i] - 1]
            if parents:
                p = min(parents, key=lambda j: areas[j])        # nejtěsnější rodič (nejmenší obsahující)
                polys.setdefault(p, [rings[p]])
                polys[p].append(rings[i])
    return list(polys.values())


def _rdp(ring: np.ndarray, eps: float) -> np.ndarray:
    """Douglas-Peucker zjednodušení uzavřeného prstence (odstraní pixelové schody, tol. eps px).
    Aplikuje se na otevřenou polylinii (bez duplicitního posledního bodu), pak znovu uzavře."""
    pts = ring[:-1] if np.allclose(ring[0], ring[-1]) else ring
    if len(pts) < 4:
        return ring
    keep = np.zeros(len(pts), dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        p0, p1 = pts[a], pts[b]
        seg = p1 - p0
        seglen = math.hypot(seg[0], seg[1]) or 1.0
        # kolmá vzdálenost bodů a<i<b od úsečky p0-p1
        d = np.abs((pts[a + 1:b, 0] - p0[0]) * seg[1] - (pts[a + 1:b, 1] - p0[1]) * seg[0]) / seglen
        if len(d) and d.max() > eps:
            k = a + 1 + int(d.argmax())
            keep[k] = True
            stack.append((a, k))
            stack.append((k, b))
    out = pts[keep]
    return np.vstack([out, out[0]])                              # znovu uzavři


def _chaikin(ring: np.ndarray, iters: int) -> np.ndarray:
    """Chaikinovo vyhlazení uzavřeného prstence (organický obrys). Port z rockcore._chaikin_ring."""
    pts = ring
    if len(pts) < 4 or iters <= 0:
        return pts
    for _ in range(iters):
        new = []
        for i in range(len(pts) - 1):
            p, q = pts[i], pts[i + 1]
            new.append(0.75 * p + 0.25 * q)
            new.append(0.25 * p + 0.75 * q)
        new.append(new[0])
        pts = np.array(new)
    return pts


def detect_rock_areas(lat: float, lon: float, geo_bbox: tuple,
                      gw: int, gh: int, tile_m: float,
                      cache_dir=None) -> list[list[list[tuple[float, float]]]]:
    """Detekuje skalní bloky z DMR 5G sklonu → polygony [outer, díra…] v S-JTSK metrech.

    `geo_bbox` = (xmin, ymin, xmax, ymax) S-JTSK mapového výseku; `gw/gh/tile_m` = rozměrové globály
    generátoru (poměr stran + N-J strana v m). Stáhne SAMOSTATNÝ hi-res DMR (TARGET_PX_M = 1,5 m, u velkých
    výseků zhrubne plošný cap — render grid generátoru je ~8 m/buňka, na to věže nejdou) pro TENTÝŽ bbox,
    spočítá sklon→masku→polygony.
    Vrací list polygonů, každý = [vnější prsten, díra1, …]; prsten = list (x, y) S-JTSK. Bez skal
    (rovina / mimo data) = []. Konzument: _poly_to_grid_px + _draw_gigantic_boulder + omap (ISOM 206)."""
    xmin, ymin, xmax, ymax = geo_bbox
    # hi-res grid pro TENTÝŽ bbox: gh_hi z cílového rozlišení, gw_hi z poměru gw/gh (isotropní buňka).
    # fetch_elevation_grid staví bbox z (lat,lon,gw_hi,gh_hi,tile_m) — poměr gw/gh + tile_m drží bbox.
    gh_hi = int(round(tile_m / TARGET_PX_M)) + 1
    gw_hi = int(round(gh_hi * gw / gh))
    if gw_hi * gh_hi > MAX_AREA_PX:                 # plošný strop (HTTP 500 nad ~7 Mpx) → zhrubni (poměr drží)
        s = (MAX_AREA_PX / (gw_hi * gh_hi)) ** 0.5  # odmocnina: škáluje obě strany rovnoměrně
        gw_hi, gh_hi = max(2, int(gw_hi * s)), max(2, int(gh_hi * s))
    if max(gw_hi, gh_hi) > MAX_PX:                  # sekundární stranová pojistka (extrémní poměry)
        s = MAX_PX / max(gw_hi, gh_hi)
        gw_hi, gh_hi = max(2, int(gw_hi * s)), max(2, int(gh_hi * s))
    z = fetch_elevation_grid(lat, lon, gw_hi, gh_hi, tile_m, cache_dir)   # (gh_hi, gw_hi), sever nahoře
    px_m = tile_m / (gh_hi - 1)                     # skutečná velikost buňky [m]

    # sklon (směrově nezávislý — žádné stínování, handoff chyba C)
    zs = gaussian_filter(z.astype(float), GAUSS_SIGMA)
    gy, gx = np.gradient(zs, px_m, px_m)
    slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))
    mask = _rock_mask(slope_deg, px_m)
    if not mask.any():
        return []

    rings = _contour_rings(mask)
    if not rings:
        return []
    polys = _group_holes(rings)

    # (col, row) hi-res grid → S-JTSK. col 0 = západ (xmin); row 0 = sever (ymax, DMR má sever nahoře).
    def to_sjtsk(ring: np.ndarray) -> list[tuple[float, float]]:
        out = []
        for col, row in ring:
            x = xmin + (col / (gw_hi - 1)) * (xmax - xmin)
            y = ymax - (row / (gh_hi - 1)) * (ymax - ymin)
            out.append((x, y))
        return out

    result: list[list[list[tuple[float, float]]]] = []
    for poly in polys:
        sjtsk_poly = []
        for ring in poly:
            simp = _rdp(ring, SIMPLIFY_M / px_m)
            smooth = _chaikin(simp, CHAIKIN_ITERS)
            sjtsk_poly.append(to_sjtsk(smooth))
        result.append(sjtsk_poly)
    return result
