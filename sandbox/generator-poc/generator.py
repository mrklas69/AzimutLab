"""
generator.py — procedurální generátor výseku mapy pro orientační běh (MVP).

Implementuje řez specifikace docs/kb/generator-procedural.md:
  vrstevnice (§4.5) + vegetace (§4.2-4.3) + bažiny (§4.4, výplň + tečkovaný obrys)
  + balvany (§4.11) + ground-truth masky (§8.1) + vektorový export vrstevnic
  (§9, GeoJSON s ISOM symboly 101/102; real = georef S-JTSK).

Hlavní myšlenka (§0): mapa NENÍ sada nakreslených čar, ale vrstvy odvozené ze
skalárních polí. Vrstevnice jsou izolinie spojitého výškového pole → z definice
se nikdy nekříží a nikdy nekončí ve vzduchu. Vegetace a bažiny jsou prahované
šumové masky. Protože si všechny vrstvy počítáme sami, máme ke každé mapě
ground-truth zdarma — každá vrstva je zároveň segmentační maska.
"""

import argparse
import json
import math  # math.hypot pro délku segmentu při tečkování (§4.4)
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import contourpy

# Barevná paleta (§5) — jediný zdroj pravdy je palette.py (DRY). Sousední modul:
# Python má složku spouštěného skriptu na sys.path, takže `palette` je viditelný,
# ať generator.py běží přímo, nebo ho importuje batch.py.
from palette import C_WHITE, C_YELLOW, C_GREEN1, C_GREEN2, C_GREEN3, C_BROWN, C_BLUE, C_BLACK

# ---------- Rozměry mřížky a plátna, měřítko (§1) ----------
GW, GH = 170, 116        # výpočetní mřížka v buňkách: šířka × výška (poměr ≈ 1,466)
W, H = 672, 458          # výstupní plátno v pixelech
CONTOUR_STEP = 5         # ekvidistance vrstevnic [m]
CONTOUR_INDEX = 25       # zvýrazněná (hlavní) vrstevnice každých 25 m
BASE_ELEV = 700          # bazální nadmořská výška [m] — jen pro terrain="noise"
TILE_M = 1000.0          # reálný rozměr výseku [m] po kratší straně (S-J); delší se
                         # dopočítá v poměru GW/GH. Sjednoceno s dmr.fetch (tile_m)
                         # → georef vektoru sedí s výškopisem.
WORLD_W_M = TILE_M * (GW / GH)  # delší strana výseku (E-W) [m] — jedna pravda pro geo_bbox i .omap

# ISOM symboly vrstevnic (§4.5, ověřeno O-Map Wiki) — pro vektorový export (§9).
# 103 Form line generátor zatím nedělá (rozšíření věrnosti).
ISOM_CONTOUR = 101       # základní vrstevnice (Contour)
ISOM_INDEX_CONTOUR = 102 # zvýrazněná každá pátá (Index contour)

# ---------- Reálný terén (§8.5, Option 2): výchozí souřadnice dlaždice ----------
# Okolí Děčínska / Českého Švýcarska — členitý pískovcový terén vhodný pro OB.
DEF_LAT, DEF_LON = 50.8214458, 14.6712747

# =====================================================================
#  Skalární pole (§2-3)
# =====================================================================
def _smooth_resize(grid: np.ndarray, w: int, h: int) -> np.ndarray:
    """Roztáhne hrubou mřížku `grid` na rozměr (h, w) bilineárně se smoothstep.

    Smoothstep 3t²−2t³ změkčí přechody mezi buňkami — bez něj by šum vypadal
    kostičkovaně. Celé je to vektorizované přes numpy (žádná Python smyčka přes pixely):
    `np.ix_(y, x)` vyrobí 2D výběr (h×w) ze čtyř rohových hodnot každé buňky.
    """
    gh0, gw0 = grid.shape
    # spojité souřadnice výstupních bodů přepočtené do soustavy hrubé mřížky
    xs = np.linspace(0, gw0 - 1, w)
    ys = np.linspace(0, gh0 - 1, h)
    x0 = np.floor(xs).astype(int)
    x1 = np.minimum(x0 + 1, gw0 - 1)
    y0 = np.floor(ys).astype(int)
    y1 = np.minimum(y0 + 1, gh0 - 1)
    tx = xs - x0
    ty = ys - y0
    sx = tx * tx * (3 - 2 * tx)   # smoothstep ve směru x (vektor délky w)
    sy = ty * ty * (3 - 2 * ty)   # smoothstep ve směru y (vektor délky h)
    g00 = grid[np.ix_(y0, x0)]
    g01 = grid[np.ix_(y0, x1)]
    g10 = grid[np.ix_(y1, x0)]
    g11 = grid[np.ix_(y1, x1)]
    # bilineární interpolace: nejdřív blend ve směru x (horní a dolní hrana), pak y
    top = g00 * (1 - sx)[None, :] + g01 * sx[None, :]
    bot = g10 * (1 - sx)[None, :] + g11 * sx[None, :]
    return top * (1 - sy)[:, None] + bot * sy[:, None]


def fractal(rng: np.random.Generator, base_scale: float, octaves: int) -> np.ndarray:
    """Fraktální value noise v [0,1] na mřížce (GH, GW) — §2.

    Sčítá několik oktáv šumu: každá další oktáva má jemnější mřížku (víc buněk)
    a poloviční amplitudu. Výsledek se min-max normalizuje do [0,1].
    """
    out = np.zeros((GH, GW), dtype=np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        c = max(2, round(base_scale * 1.9 ** o))           # počet buněk hrubé mřížky oktávy
        coarse = rng.random((c + 1, c + 1)).astype(np.float32)
        out += _smooth_resize(coarse, GW, GH) * amp
        total += amp
        amp *= 0.5
    out /= total
    return (out - out.min()) / (out.max() - out.min() + 1e-9)


def box_blur(field: np.ndarray, radius: int = 2) -> np.ndarray:
    """Jednoduchý box blur (průměr v okně (2r+1)²).

    Použito 2× na `hbase` → vyhlazený výškopis `eb`, ze kterého počítáme sklon.
    `np.pad(..., mode="edge")` rozšíří okraje opakováním krajních hodnot, ať se
    okno nedostane mimo pole.
    """
    k = 2 * radius + 1
    padded = np.pad(field, radius, mode="edge")
    acc = np.zeros_like(field)
    for dy in range(k):
        for dx in range(k):
            acc += padded[dy:dy + field.shape[0], dx:dx + field.shape[1]]
    return acc / (k * k)


def _to_pixels(field: np.ndarray) -> np.ndarray:
    """Bilineárně roztáhne pole z mřížky (GH, GW) na plátno (H, W).

    Mód "F" = 32bitový float obraz; PIL umí takto převzorkovat spojitou hodnotu
    (ne jen 0-255), takže prahování na pixelech sedí s mřížkou.
    """
    im = Image.fromarray(field.astype(np.float32), mode="F").resize((W, H), Image.BILINEAR)
    return np.asarray(im, dtype=np.float32)


def _draw_dotted(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]],
                 color: tuple, spacing: float = 5.0, radius: int = 1) -> None:
    """Vykreslí tečkovanou linii podél polyčáry `pts` (seznam bodů (x, y)).

    PIL nemá nativní čárkovanou čáru, takže tečky klademe ručně: jdeme po
    polyčáře a každých `spacing` px položíme vyplněný kroužek o poloměru `radius`.
    Vzorkujeme podle DÉLKY OBLOUKU (arc length), ne podle indexu bodů — tečky
    jsou tak rovnoměrné bez ohledu na to, jak hustě za sebou body polyčáry leží.
    """
    if len(pts) < 2:
        return
    next_dot = 0.0  # zbývající vzdálenost do položení další tečky (přenáší se mezi segmenty)
    # zip(pts, pts[1:]) iteruje dvojice sousedních bodů = jednotlivé úsečky polyčáry
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        seg = math.hypot(dx, dy)        # délka úsečky
        if seg == 0.0:
            continue
        d = next_dot
        while d <= seg:                 # kladď tečky, dokud se vejdou do úsečky
            t = d / seg                 # parametr 0..1 podél úsečky
            cx, cy = x0 + dx * t, y0 + dy * t
            draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=color)
            d += spacing
        next_dot = d - seg              # zbytek (přesah) přenes do další úsečky


def _write_contours_geojson(features: list[tuple], bbox: tuple, crs_epsg: int | None,
                            out_path: Path) -> int:
    """Zapíše vrstevnice jako GeoJSON FeatureCollection (vektor, §9). Vrací počet linií.

    Klíčová myšlenka: vrstevnice z contourpy UŽ JSOU polylinie (ne pixely) — jen je
    místo rasterizace do PNG zapíšeme jako vektor s ISOM symbolem. Žádná vektorizace
    rastru (AutoTrace) tu netřeba; jdeme z přesného zdroje.

    `features` = seznam (line, symbol_code); `line` je pole bodů (N×2) v souřadnicích
    MŘÍŽKY (gx∈0..GW-1, gy∈0..GH-1, sever nahoře). `bbox`=(xmin,ymin,xmax,ymax) ve
    world metrech → lineární přepočet mřížka→svět. Osa Y se PŘEVRACÍ: gy=0 je horní
    řádek = sever = ymax. `crs_epsg` (real=5514) nebo None pro lokální metry (noise).
    """
    xmin, ymin, xmax, ymax = bbox
    sx = (xmax - xmin) / (GW - 1)   # metrů na buňku mřížky, osa x
    sy = (ymax - ymin) / (GH - 1)   # metrů na buňku mřížky, osa y
    names = {ISOM_CONTOUR: "Contour", ISOM_INDEX_CONTOUR: "Index contour"}
    geo_features = []
    for line, code in features:
        # mřížka → world metry; round na cm stačí (zdrojový grid je 2 m nativně)
        coords = [[round(xmin + float(gx) * sx, 2), round(ymax - float(gy) * sy, 2)]
                  for gx, gy in line]
        if len(coords) < 2:          # degenerátní linie (0-1 bod) přeskoč
            continue
        geo_features.append({
            "type": "Feature",
            "properties": {"symbol": code, "symbol_name": names[code]},
            "geometry": {"type": "LineString", "coordinates": coords},
        })
    fc: dict = {"type": "FeatureCollection", "features": geo_features}
    # CRS member: GeoJSON-2008 rozšíření (mimo RFC 7946, ale OOM / QGIS / OCAD ho čtou)
    # — u reálného terénu nese S-JTSK, ať mapa sedí na správné místo při importu.
    if crs_epsg is not None:
        fc["crs"] = {"type": "name",
                     "properties": {"name": f"urn:ogc:def:crs:EPSG::{crs_epsg}"}}
    out_path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    return len(geo_features)


# =====================================================================
#  Hlavní generování
# =====================================================================
def generate(seed: int, rug: float, vd: float, wat: float, out_dir: str,
             rock: float = 0.5, terrain: str = "noise",
             lat: float = DEF_LAT, lon: float = DEF_LON,
             omap_template: str | None = None) -> Path:
    """Vygeneruje jednu instanci mapy + GT masky + vektor vrstevnic do `out_dir`.

    Vrací cestu k složce. `terrain="noise"` (default) = fraktální šum (Option 1).
    `terrain="real"` = reálný výškopis ČÚZK DMR 5G pro (lat, lon) místo šumu
    (Option 2, §8.5). U reálného terénu se `rug` na výškopis neuplatní (terén je
    daný realitou) — `vd`/`wat` (vegetace/bažiny) platí dál.

    Vedle rastru (rgb.png + GT masky) zapisuje `contours.geojson` — vrstevnice jako
    vektorové linie s ISOM symbolem (101/102), georeferencované v S-JTSK pro real
    terén (§9). To je „skutečný vektor", ne pixely: contourpy dává polylinie přímo.
    """
    # Pozn.: spec doporučuje PRNG mulberry32, ale požadavek je jen DETERMINISMUS
    # (stejný seed + parametry → stejná mapa), ne bitová shoda s JS referencí.
    # Proto volíme jednodušší a korektní numpy generátor (PCG64).
    rng = np.random.default_rng(seed)

    # --- výškopis: reálný (DMR 5G) nebo syntetický šum ---
    if terrain == "real":
        # Lazy import: pyproj je závislost jen pro Option 2; Option 1 zůstává offline.
        from dmr import fetch_elevation_grid, build_bbox
        elev = fetch_elevation_grid(lat, lon, GW, GH, tile_m=TILE_M)  # reálné metry (GH, GW), sever nahoře
        # normalizace do [0,1]: zbytek pipeline (bažiny přes prahy) počítá s hbase
        hbase = (elev - elev.min()) / (elev.max() - elev.min() + 1e-9)
        # georef pro vektorový export: skutečný S-JTSK bbox výseku (stejný TILE_M jako fetch)
        geo_bbox = build_bbox(lat, lon, GW, GH, TILE_M)
        crs_epsg: int | None = 5514                              # S-JTSK / Křovák
    else:
        hbase = fractal(rng, 1.6 + rug * 2.6, 3 + round(rug * 2))  # výškopis (členitost = rug)
        vrange = 25 + rug * 90                                    # převýšení: víc členitosti → víc vrstevnic
        elev = BASE_ELEV + hbase * vrange                         # nadmořská výška [m]
        # georef šumu: skutečné umístění neznáme → lokální metry od (0,0), stejná
        # geometrie výseku jako real (TILE_M × poměr GW/GH). crs=None.
        geo_bbox = (0.0, 0.0, WORLD_W_M, TILE_M)
        crs_epsg = None

    # --- ostatní skalární pole (§2-3) — vždy syntetická (DMR nedává vegetaci) ---
    veg = fractal(rng, 3.2 + vd * 1.5, 3)                       # hustota porostu
    clear = fractal(rng, 2.4, 2)                                # paseky / otevřené plochy
    eb = box_blur(box_blur(hbase))                              # vyhlazený výškopis pro sklon
    gy, gx = np.gradient(eb)                                    # centrální diference (§3)
    slope = np.sqrt(gx ** 2 + gy ** 2)
    slope = slope / (slope.max() + 1e-9)                        # sklon normalizovaný do [0,1]

    # --- převzorkování polí na pixely (pro plošné vrstvy) ---
    veg_px = _to_pixels(veg)
    clear_px = _to_pixels(clear)
    hbase_px = _to_pixels(hbase)
    slope_px = _to_pixels(slope)

    # --- plátno + GT maska vegetace ---
    rgb = np.full((H, W, 3), C_WHITE, dtype=np.uint8)   # bílá (palette: white) = průběžný les (§4.1)
    veg_mask = np.zeros((H, W), dtype=np.uint8)     # třídy: 0 les, 1-3 zeleň, 4 paseka

    # vegetace (§4.2): tři prahy, malujeme odspodu (světlá → tmavá), vyšší vd = víc zeleně
    a = float(np.clip(0.82 - vd * 0.5, 0.0, 1.0))
    b = a + 0.13
    c = a + 0.23
    for thr, color, cls in [(a, C_GREEN1, 1), (b, C_GREEN2, 2), (c, C_GREEN3, 3)]:
        m = veg_px >= thr
        rgb[m] = color
        veg_mask[m] = cls

    # paseky (§4.3): otevřená plocha žlutě
    clear_thr = 0.70 + vd * 0.22
    open_m = clear_px >= clear_thr
    rgb[open_m] = C_YELLOW
    veg_mask[open_m] = 4

    # bažina / mokřad (§4.4): nízko (malá výška) a ploše (malý sklon)
    marsh = (hbase_px < (0.10 + wat * 0.16)) & (slope_px < 0.16)
    hatch = np.zeros((H, W), dtype=bool)
    hatch[::4, :] = True                            # vodorovná šrafa: každý 4. řádek pixelů
    rgb[marsh & hatch] = C_BLUE

    # --- vrstevnice (§4.5): izolinie pole `elev` přes contourpy (marching squares) ---
    img = Image.fromarray(rgb, mode="RGB")
    draw = ImageDraw.Draw(img)
    cmask_img = Image.new("L", (W, H), 0)           # samostatná GT maska vrstevnic
    cdraw = ImageDraw.Draw(cmask_img)

    # obrys bažin (§4.4): izolinie binární masky bažin na úrovni 0,5. Maska je
    # už v pixelech (H, W) → contourpy vrací rovnou pixelové souřadnice (žádný
    # přepočet mřížka→plátno), takže obrys přesně kopíruje vyplněnou oblast.
    # Kreslíme PŘED vrstevnicemi (z-order §4: bažina 4.4 leží pod vrstevnicemi 4.5).
    marsh_cont = contourpy.contour_generator(
        z=marsh.astype(np.float32), line_type=contourpy.LineType.Separate)
    for line in marsh_cont.lines(0.5):
        _draw_dotted(draw, [(float(x), float(y)) for x, y in line], C_BLUE)

    # LineType.Separate → .lines(level) vrátí prostý seznam polí bodů (N×2) v souřadnicích mřížky
    cont = contourpy.contour_generator(z=elev, line_type=contourpy.LineType.Separate)
    lo = int(np.ceil(elev.min() / CONTOUR_STEP) * CONTOUR_STEP)
    hi = int(elev.max())
    contour_features: list[tuple] = []   # (linie v souřadnicích mřížky, ISOM symbol) pro vektor §9
    for level in range(lo, hi + 1, CONTOUR_STEP):
        # hlavní vrstevnice na absolutních násobcích CONTOUR_INDEX (25 m) — platí
        # pro reálné výšky i pro šum (BASE_ELEV=700 je násobek 25, chování stejné)
        is_main = level % CONTOUR_INDEX == 0
        symbol = ISOM_INDEX_CONTOUR if is_main else ISOM_CONTOUR   # 102 / 101 pro vektor
        # hlavní vrstevnice výrazně silnější (3 px vs 1 px). Reálně ~0,65 mm při
        # 1:10000 — mírně nad ISOM normou (0,5 mm), ale (a) PIL nemá antialiasing,
        # takže 2 px ještě splývá s normální, (b) jasnější odlišení index/normal
        # pomáhá i modelu (UC5) tyto dvě třídy rozlišit. Spec §8.2 počítá s variací
        # tlouštěk čar pro diverzitu datasetu, takže je to v intencích metodiky.
        width = 3 if is_main else 1
        for line in cont.lines(level):
            # přepočet souřadnic mřížky (x∈0..GW-1, y∈0..GH-1) na pixely plátna
            pts = [(float(x) / (GW - 1) * W, float(y) / (GH - 1) * H) for x, y in line]
            if len(pts) >= 2:
                draw.line(pts, fill=C_BROWN, width=width)
                cdraw.line(pts, fill=255, width=width)
                contour_features.append((line, symbol))   # grid souřadnice → georef ve vektor exportu

    # --- balvany (§4.11): černé tečky, hustěji ve strmém terénu ---
    # Fyzikální smysl (CLAUDE.md): skály/balvany jsou častější ve strmém členitém
    # terénu. Proto bodový proces vážený sklonem — nikoli rovnoměrný posyp.
    # Kreslíme NAHORU (z-order §4.11 nad plošnými vrstvami i vrstevnicemi).
    rock_mask_img = Image.new("L", (W, H), 0)       # GT maska balvanů (§8.1)
    rdraw = ImageDraw.Draw(rock_mask_img)
    n_boulders = round(rock * 120)                  # počet pokusů o balvan (§4.11)
    BOULDER_R = 2                                   # poloměr tečky balvanu [px]
    for _ in range(n_boulders):
        bx = int(rng.integers(0, W))                # náhodná pozice na plátně
        by = int(rng.integers(0, H))
        # přijetí roste se sklonem: ~0,25 v rovině → ~1,15 v nejstrmějším bodě
        if rng.random() < 0.25 + float(slope_px[by, bx]) * 0.9:
            box = [bx - BOULDER_R, by - BOULDER_R, bx + BOULDER_R, by + BOULDER_R]
            draw.ellipse(box, fill=C_BLACK)         # balvan černě na mapu
            rdraw.ellipse(box, fill=255)            # stejná geometrie do GT masky

    # --- zápis výstupů (§8.1): finální mapa + masky + meta ---
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    img.save(out / "rgb.png")
    cmask_img.save(out / "mask_contours.png")
    Image.fromarray(veg_mask, mode="L").save(out / "mask_veg.png")          # třídy 0-4
    Image.fromarray((marsh * 255).astype(np.uint8), mode="L").save(out / "mask_water.png")
    rock_mask_img.save(out / "mask_rock.png")                               # balvany (GT)
    # vektorový export vrstevnic (§9): ISOM 101/102 linie, georef (real = S-JTSK)
    n_contours = _write_contours_geojson(contour_features, geo_bbox, crs_epsg,
                                         out / "contours.geojson")
    # volitelně .omap (template-based, Local CRS) — jen když uživatel dodá ISOM template
    omap_info = None
    if omap_template:
        from omap_export import write_omap
        n_omap = write_omap(contour_features, GW, GH, WORLD_W_M, TILE_M,
                            omap_template, out / "map.omap")
        omap_info = {"file": "map.omap", "n_objects": n_omap, "template": str(omap_template)}
    meta = {
        "seed": seed,
        "params": {"rug": rug, "vd": vd, "wat": wat, "rock": rock},
        # původ výškopisu — pro reprodukovatelnost a atribuci (real = ČÚZK DMR 5G)
        "terrain": ({"source": "noise"} if terrain != "real" else {
            "source": "cuzk_dmr5g", "lat": lat, "lon": lon,
            "elev_min_m": round(float(elev.min()), 2),
            "elev_max_m": round(float(elev.max()), 2),
            "licence": "CC BY 4.0 (ČÚZK)",
        }),
        "grid": [GW, GH],
        "canvas": [W, H],
        "scale": "1:10000",
        "contour_step_m": CONTOUR_STEP,
        "contour_index_m": CONTOUR_INDEX,
        # vektorový export vrstevnic (§9): formát, CRS, počet linií, ISOM symboly
        "contours_vector": {
            "file": "contours.geojson",
            "crs": ("EPSG:5514" if crs_epsg else "local_m"),
            "n_lines": n_contours,
            "symbols": {"101": "Contour", "102": "Index contour"},
        },
        # .omap export (jen když --omap-template); jinak klíč chybí
        **({"omap": omap_info} if omap_info else {}),
        "veg_classes": {
            "0": "les/bílá", "1": "světle zelená", "2": "středně zelená",
            "3": "tmavě zelená", "4": "paseka/žlutá",
        },
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Procedurální generátor výseku OB mapy (MVP).")
    p.add_argument("--seed", type=int, default=1, help="seed PRNG (determinismus)")
    p.add_argument("--rug", type=float, default=0.5, help="členitost terénu 0-1")
    p.add_argument("--vd", type=float, default=0.5, help="hustota vegetace 0-1")
    p.add_argument("--wat", type=float, default=0.4, help="vodní prvky / velikost bažin 0-1")
    p.add_argument("--rock", type=float, default=0.5, help="skály a balvany 0-1")
    p.add_argument("--terrain", choices=["noise", "real"], default="noise",
                   help="noise = fraktální šum (default), real = ČÚZK DMR 5G (§8.5)")
    p.add_argument("--lat", type=float, default=DEF_LAT, help="zeměpisná šířka WGS84 (jen --terrain real)")
    p.add_argument("--lon", type=float, default=DEF_LON, help="zeměpisná délka WGS84 (jen --terrain real)")
    p.add_argument("--out", default="output", help="výstupní složka")
    p.add_argument("--omap-template", default=None,
                   help="cesta k ISOM .omap template → zapíše i map.omap (vrstevnice 101/102, Local CRS)")
    args = p.parse_args()
    out = generate(args.seed, args.rug, args.vd, args.wat, args.out,
                   rock=args.rock, terrain=args.terrain, lat=args.lat, lon=args.lon,
                   omap_template=args.omap_template)
    print(f"Hotovo -> {out.resolve()}")


if __name__ == "__main__":
    main()
