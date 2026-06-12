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
import logging
import math

import numpy as np
import contourpy
from scipy.ndimage import (gaussian_filter, binary_opening, binary_closing,
                           binary_fill_holes, label)

from dmr import fetch_elevation_grid   # connectors/ je na sys.path (zařídí generator.py)
from pyproj import Transformer

# inverze dmr._TF_WGS84_TO_SJTSK — sub-tile střed (S-JTSK) → (lat, lon) pro fetch_elevation_grid.
# Tiling drží fetch ČÚZK přes existující fetch_elevation_grid (cache/validace sdílené, dmr.py netknut).
_TF_SJTSK_TO_WGS84 = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)

# --- laditelné parametry (metry / stupně; kalibrace = zlatý vzorek Šulcák, docs/kb/rock-detection-v2) ---
# v2 (Sez. 110, handoff §4a): práh sklonu je SVÁZANÝ s rozlišením (bilineární převzorkování rozmazává stěny
# → hrubší pixel = nižší naměřený sklon na téže stěně). 46° platí JEN pro 0,5 m/px → analýza běží na PEVNÉM
# rozlišení (NE TARGET_PX_M dle výseku jako v1; ten poddetekoval o 43 %: golden 2,53 ha vs v1@1,5m 1,29 ha,
# měřeno temp/probe_rock_v2). Velký výsek se tiluje (fetch po dlaždicích, seamless assembled grid → morfologie
# JEDNOU; čistší než handoff §7 per-dlaždice). NEMĚNIT ANALYSIS_RES bez rekalibrace prahu + golden regrese.
ANALYSIS_RES = 0.5         # PEVNÉ analytické rozlišení [m/buňka] — práh 46° je na něj kalibrovaný (handoff §4a)
# ImageServer exportImage vrací HTTP 500 nad ~7 Mpx (F32 tiff) — empiricky práh 6,8 (OK)–8,2 (Sez. 65) →
# fetch jednoho tile ≤ MAX_FETCH_PX. Celý assembled grid ≤ MAX_TOTAL_PX (paměť ntbhej; nad to zhrubne + VARUJE).
MAX_FETCH_PX = 6_500_000   # plošný strop JEDNOHO fetch tile (proti HTTP 500)
MAX_TOTAL_PX = 50_000_000  # strop assembled gridu (paměť) — typická OB mapa ~5 km² @ 0,5 m = 20 Mpx (projde
#                            plně); 6×4 km DEV = 96 Mpx → zhrubne na ~0,7 m/px s HLASITÝM varováním (no silent
#                            fallback: handoff §4a — hrubší rastr mění kalibraci detekce, NEzamlčet)
SLOPE_THR_DEG = 46.0       # práh sklonu „jistá skalní stěna" @ ANALYSIS_RES (nižší nabírá strmé lesní svahy — chyba A)
GAUSS_SIGMA = 0.6          # vyhlazení DMR před gradientem (potlačí pixelový šum sklonu)
OPEN_M = 0.5               # despeckle (binary_opening) → disk r=1px @ 0,5 m/px (golden; v1 měl 1,0 = r=2px → maže
#                            tenké stěny, −27 % plochy: 1,85 vs golden 2,53 ha, měřeno temp/probe_rock_despeckle)
CLOSE_M = 4.0              # uzávěr (binary_closing) — stěny + vršek scelí do bloku (jádro algoritmu)
FILL_MAX_M2 = 250.0        # vyplnit jen díry menší než tohle (vrcholové plošiny); větší = průchody → nechat
MIN_AREA_M2 = 60.0         # zahodit fragmenty pod tuhle plochu (drobky, ne skalní blok)
# Per-mapa density gate (Sez. 116): rozlišuje SKALNATOU oblast od mikroreliéfu strmých lesních svahů.
# Měření probe_rock_overdetect: skalnaté mapy mají >=0,16 % px nad prahem (SV 0,158 / HS 2,22 / golden Šulcák
# 3,72 %), ne-skalnaté jen ~0,04 % (Bedřichovka 0,042 / Blatná 0,037 — rozptýlený mikroreliéf: zářezy cest,
# břehy, terénní stupně). Práh 0,08 % odděluje s ~2× marginem na obě strany. Pod práh → vrstva 206 VYPNUTA
# pro celou mapu (no silent: hlasitý INFO log). Plošný 206 = skalnatá OBLAST; osamělé skály jdou přes body
# 204/207 (ZABAGED). Důvod: rock v2 (Sez. 110, ANALYSIS_RES 0,5 m) nabírá mikroreliéf → falešné 206 →
# 210 Stony přestřel → KPI −3,25 pb (diagnostika Sez. 115). Golden Šulcák zůstává beze změny (3,72 % >> práh).
DENSITY_GATE_PCT = 0.08    # min. podíl px nad SLOPE_THR_DEG [%], aby se vrstva 206 na mapě vůbec kreslila
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
    padded = np.pad(mask.astype(np.float32), 1, constant_values=0.0)  # f32 (level 0.5 přesný i ve f32)
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


def _fetch_assembled_grid(geo_bbox: tuple, gw_hi: int, gh_hi: int,
                          cache_dir=None) -> np.ndarray:
    """Stáhne DMR výškopis pro `geo_bbox` na grid (gh_hi, gw_hi) — tiluje fetch, slije do JEDNOHO pole.

    Velký výsek @ 0,5 m/px přesáhne MAX_FETCH_PX (HTTP 500) → rozřeže grid na dlaždice ≤ MAX_FETCH_PX,
    každou stáhne přes fetch_elevation_grid (cache/validace sdílené s dmr.py, ten netknut) a poskládá do
    seamless pole. Morfologie + kontury pak běží JEDNOU na celku → žádné per-dlaždice okrajové artefakty
    (handoff §7 řeší overlap+merge masek; assembled grid to obchází — sklon je spojitý, šev v z je < 0,5 m).
    Bilineární převzorkování na okraji dlaždice je korektní (server vzorkuje nativní 2m grid i za bbox).

    Border noData (Sez. 115): dlaždice u hranice ČR (SV Soví vrch) zasáhne za pokrytí DMR 5G →
    fetch_elevation_grid raise (neúplný TIFF / podezřelé výšky). Takovou dlaždici NEpropadáme (celý
    rock regen by spadl), ale vyplníme NaN + VAROVÁNÍ NAHLAS (no silent fallback): NaN propadne do
    sklonu → maska `slope >= 46` = False → bez skal v té oblasti (správně — za hranicí data nejsou).
    NEvyplňujeme konstantou (rovina): umělý skok výšky na švu s reálným terénem = falešná stěna."""
    xmin, ymin, xmax, ymax = geo_bbox
    side = int(MAX_FETCH_PX ** 0.5)                       # max strana jedné dlaždice (čtverec ≤ MAX_FETCH_PX)
    z = np.empty((gh_hi, gw_hi), dtype=np.float32)
    n_nodata = 0
    for r0 in range(0, gh_hi, side):
        r1 = min(r0 + side, gh_hi)
        for c0 in range(0, gw_hi, side):
            c1 = min(c0 + side, gw_hi)
            tw, th = c1 - c0, r1 - r0
            # S-JTSK obal dlaždice (col 0 = západ xmin; row 0 = sever ymax)
            sx0 = xmin + (c0 / gw_hi) * (xmax - xmin)
            sx1 = xmin + (c1 / gw_hi) * (xmax - xmin)
            sy_top = ymax - (r0 / gh_hi) * (ymax - ymin)
            sy_bot = ymax - (r1 / gh_hi) * (ymax - ymin)
            cx, cy = (sx0 + sx1) / 2, (sy_top + sy_bot) / 2
            lon_c, lat_c = _TF_SJTSK_TO_WGS84.transform(cx, cy)
            tile_m_t = sy_top - sy_bot                     # N-J strana dlaždice [m]
            # fetch staví bbox z (lat,lon,tw,th,tile_m_t): E-W = tile_m_t·(tw/th) = (sx1-sx0) ✓, centrováno
            try:
                z[r0:r1, c0:c1] = fetch_elevation_grid(lat_c, lon_c, tw, th, tile_m_t, cache_dir)
            except RuntimeError as e:
                z[r0:r1, c0:c1] = np.nan                    # mimo pokrytí (za hranicí ČR) → bez skal
                n_nodata += 1
                logging.getLogger("rock_relief").warning(
                    "rock dlazdice @ (%.5f, %.5f) mimo pokryti DMR 5G → NaN (bez skal): %s",
                    lat_c, lon_c, str(e).split(" — ")[0])
    if n_nodata:
        logging.getLogger("rock_relief").warning(
            "rock_relief: %d dlazdic mimo pokryti DMR (za hranici CR) → bez skal v tech oblastech "
            "(no silent fallback).", n_nodata)
    return z


def detect_rock_areas(lat: float, lon: float, geo_bbox: tuple,
                      gw: int, gh: int, tile_m: float,
                      cache_dir=None) -> list[list[list[tuple[float, float]]]]:
    """Detekuje skalní bloky z DMR 5G sklonu → polygony [outer, díra…] v S-JTSK metrech.

    `geo_bbox` = (xmin, ymin, xmax, ymax) S-JTSK mapového výseku; `gw/gh/tile_m` = rozměrové globály
    generátoru (zachovány pro kompat, rozlišení už z nich NEvychází). v2 (Sez. 110): analýza běží na PEVNÉM
    ANALYSIS_RES (0,5 m/px) — práh 46° je na něj kalibrovaný (handoff §4a; v1@1,5m poddetekoval o 43 %, golden
    2,53 vs 1,29 ha). Velký výsek > MAX_TOTAL_PX zhrubne (paměť) s VAROVÁNÍM; fetch se tiluje (_fetch_assembled_grid).
    Vrací list polygonů, každý = [vnější prsten, díra1, …]; prsten = list (x, y) S-JTSK. Bez skal
    (rovina / mimo data) = []. Konzument: _poly_to_grid_px + _draw_gigantic_boulder + omap (ISOM 206)."""
    xmin, ymin, xmax, ymax = geo_bbox
    # hi-res grid pro TENTÝŽ bbox: gh_hi z cílového rozlišení, gw_hi z poměru gw/gh (isotropní buňka).
    # fetch_elevation_grid staví bbox z (lat,lon,gw_hi,gh_hi,tile_m) — poměr gw/gh + tile_m drží bbox.
    w_m, h_m = xmax - xmin, ymax - ymin
    px_m = ANALYSIS_RES                             # PEVNÉ rozlišení (práh 46° na něj kalibrovaný, handoff §4a)
    gw_hi = max(2, int(round(w_m / px_m)))
    gh_hi = max(2, int(round(h_m / px_m)))
    if gw_hi * gh_hi > MAX_TOTAL_PX:                # paměťový strop assembled gridu → zhrubni + VARUJ NAHLAS
        s = (MAX_TOTAL_PX / (gw_hi * gh_hi)) ** 0.5
        gw_hi, gh_hi = max(2, int(gw_hi * s)), max(2, int(gh_hi * s))
        px_m = h_m / gh_hi                          # skutečné (zhrubené) rozlišení — práh 46° už nesedí přesně
        logging.getLogger("rock_relief").warning(
            "vysek %.1f×%.1f km > %d Mpx @ %.2f m/px → detekce skal ZHRUBLA na %.2f m/px "
            "(prah sklonu kalibrovany na %.1f m → poddetekce; handoff §4a, no silent fallback).",
            w_m / 1000, h_m / 1000, MAX_TOTAL_PX // 1_000_000, ANALYSIS_RES, px_m, ANALYSIS_RES)
    z = _fetch_assembled_grid(geo_bbox, gw_hi, gh_hi, cache_dir)   # (gh_hi, gw_hi), sever nahoře (tiluje fetch)

    # sklon (směrově nezávislý — žádné stínování, handoff chyba C). errstate: NaN dlaždice (noData za
    # hranicí ČR, Sez. 115) → sklon NaN → `slope >= 46` = False (bez skal), bez RuntimeWarning spamu.
    # `del` mezivýsledků PŘED contour: na zhrubeném 50 Mpx gridu drží f64 pipeline ~3,3 GB → OOM ntbhej;
    # uvolnění zs/gy/gx/slope sráží peak na ~1,9 GB (měřeno temp/probe_rock_oom, Sez. 115). Peak je ve
    # `_rock_mask` (label int32), ne ve sklonu → float32 sklonu nepomohl, f64 zachován (přesnost prahu 46°).
    with np.errstate(invalid="ignore"):
        zs = gaussian_filter(z.astype(float), GAUSS_SIGMA)
        gy, gx = np.gradient(zs, px_m, px_m)
        slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))
        # density gate (Sez. 116): podíl strmých px (NaN dlaždice za hranicí → False = not-rocky). Pod práh
        # je celá mapa mikroreliéf, ne skalnatá oblast → 0 ploch 206 (zachová golden, smaže falešné Bedř/Blatná).
        density_pct = 100.0 * float(np.mean(slope_deg >= SLOPE_THR_DEG))
        if density_pct < DENSITY_GATE_PCT:
            del z, zs, gy, gx, slope_deg
            logging.getLogger("rock_relief").info(
                "skalnatost mapy %.3f %% px >= %.0f deg < prah %.2f %% → 0 ploch 206 "
                "(mikrorelief, ne skalnata oblast; Sez. 116 density gate).",
                density_pct, SLOPE_THR_DEG, DENSITY_GATE_PCT)
            return []
        mask = _rock_mask(slope_deg, px_m)
    del z, zs, gy, gx, slope_deg                                   # uvolni ~1,4 GB před _contour_rings
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
