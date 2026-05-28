"""
zabaged.py — reálné vektorové prvky z ČÚZK ZABAGED® Polohopis (ArcGIS REST; UC2 konektor, real-půlka).

Sourozenec dmr.py (NE kopie): dmr.py táhne reálný VÝŠKOPIS (DMR 5G, rastr/ImageServer),
zabaged.py táhne reálné POLOHOPISNÉ VEKTORY (ArcGIS REST query). Od cest (§4.9, Sez. 16) postupně
přibyly: voda (toky+plochy, 17), budovy (18), el. vedení + stožáry (24), železnice/tramvaj +
kolejiště (28+31), řopíky + státní hranice (27), skály/balvany (30), mosty/tunely/lávky (32-33).
Vše bere tentýž výsek přes sdílený dmr.build_bbox() → reálné prvky padnou bezešvě na tentýž terén
jako vrstevnice z DMR. Mapování ZABAGED→ISOM dělají `map_*_to_isom` funkce (po verify atributů).

Zdroj: ČÚZK ZABAGED Polohopis, ArcGIS REST MapServer `/query` (open data, CC BY 4.0 —
atribuce povinná). `f=geojson` → GeoJSON přímo (žádný GML parsing, izomorfní s contours.geojson).

Klíčová zjištění (Sez. 16 = WFS, Sez. 26 = přechod na REST):
  - REST: .../arcgis/rest/services/ZABAGED_POLOHOPIS/MapServer/<layer_id>/query
  - PROČ REST místo WFS (Sez. 26): WFS GetFeature tvrdě uřezával na 1000 obj/dotaz a
    startIndex paging byl rozbitý → velká města přicházela o objekty. REST query má strop
    2000 + spolehlivý resultOffset paging (viz _fetch_layer + LAYER_IDS).
  - vrstvy se adresují numerickým layer ID (LAYER_IDS), ne typeName; in/outSR=EPSG:5514.
  - geometrie LineString/Polygon (i Multi-); atributy v REST jsou MALÝMI písmeny (pozor:
    WFS měl `TYPUSKOM_K` velkými, REST `typuskom_k` — viz map_path_to_isom).

Pozn. k souřadnicím: S-JTSK (EPSG:5514) má v ČR záporné x i y (x ≈ -700 tis = easting,
y ≈ -1000 tis = northing). Axis order REST odpovědi (in/outSR=5514) se ověřuje regresí
(vizuál sedí na terén) i diagnostikou (main).
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

# Sdílený výsek s výškopisem (izomorfismus, bezešvost) — build_bbox je public (Sez. 8).
from dmr import build_bbox

# REST endpoint ZABAGED Polohopis MapServer (Sez. 26: přechod z WFS). WFS GetFeature tvrdě
# uřezával na 1000 obj/dotaz a startIndex paging byl rozbitý (Sez. 25); REST query má strop
# 2000 + SPOLEHLIVÝ resultOffset paging (ověřeno temp/probe_rest_paging.py: SV budovy 1078,
# dávky navazují, overlap 0) → města se stáhnou kompletní. Vrstvy se adresují numerickým
# layer ID (ne typeName).
_REST_SERVER = "https://ags.cuzk.gov.cz/arcgis/rest/services/ZABAGED_POLOHOPIS/MapServer"
_PAGE = 2000   # maxRecordCount REST query (ověřeno) — velikost dávky v paging smyčce

# WFS typeName → REST layer ID (ověřeno proti MapServer?f=json, Sez. 26; obnova: temp/probe_zabaged_rest.py).
LAYER_IDS = {
    "Cesta": 83, "Pěšina": 82, "Silnice__dálnice": 79,
    "Silnice_neevidovaná": 80, "Ulice": 84,
    "Lesní průsek": 16,                # (Sez. 36) REST jméno s MEZEROU (jako tramvaj/lávka), ne escape
    "Železniční_trať": 75, "Železniční_vlečka": 76, "Kolejiště": 122,
    "Tramvajová dráha": 71,            # (Sez. 31) jméno s MEZEROU, ne WFS escape s podtržítkem

    "Vodní_tok": 93, "Vodní_plocha": 132, "Pozemní_nádrž": 107,
    "Budova_jednotlivá_nebo_blok_budov__plocha_": 99,
    "Elektrické_vedení": 88, "Stožár_elektrického_vedení": 87,
    "Bunkr": 37, "Hranice_správní_jednotky": 1,
    # Skály a balvany (Sez. 30, ID ověřená přes MapServer ?f=json + temp/probe_rocks.py).
    # Osamělý_balvan… 10 = bodové „turisticky významné" balvany (na Hruboskalsku 6 prvků).
    # Skupina_balvanů… 12 = bodová pole drobných kamenů (168 na Hrubé Skále). Skalní_útvary
    # 130 = polygony skal (411 na Hrubé Skále, medián 1132 m², max 30 444 m²).
    "Osamělý_balvan__skála__skalní_suk": 10,
    "Skupina_balvanů__bod_": 12,
    "Skalní_útvary": 130,
    # Mosty / tunely / lávky (Sez. 32 znovu, spec-driven po rollbacku Sez. 31).
    # REST jména: Most + Tunel s podtržítky/bez (Most = jedno slovo, OK), Lávka má MEZERU
    # a závorky (`Lávka (linie)`/`Lávka (bod)`, NE WFS-styl `Lávka__linie_`).
    "Most": 73,
    "Tunel": 74,
    "Lávka (linie)": 67,
    "Lávka (bod)": 66,
}

# Feature typy komunikací relevantní pro OB (les). Turistická_trasa se vynechává — vede
# zpravidla PO existující cestě/pěšině → duplikovala by liniovou síť (rozhodnuto Sez. 16).
# (Silnice/Ulice jsou v lese vzácné, ale patří do sítě, kde výsek zasáhne okraj obce.)
# Silnice_neevidovaná = účelové/lesní asfaltky mimo silniční evidenci — v lese ČASTÉ a pro
# OB klíčové (Sez. 23: chyběla páteřní asfaltka Bedřichov→Nová louka). Most je samostatná
# liniová vrstva → ISOM 512 (BRIDGE_LAYERS, Sez. 32, NE bod jak dříve mylně uvedeno);
# Silnice_ve_výstavbě zatím vynechána (ve výsecích vzácná). Plný katalog 149 vrstev:
# docs/kb/zabaged-isom-catalog.md.
PATH_LAYERS = ("Cesta", "Pěšina", "Silnice__dálnice", "Silnice_neevidovaná", "Ulice")

# Lesní průseky (Sez. 36, real-půlka, liniová — izomorfní s cestami). ZABAGED `Lesní průsek`
# (id 16, REST jméno s MEZEROU jako tramvaj/lávka) → ISOM 508 Narrow ride = průhled lesem BEZ
# zřetelné vyšlapané cesty (odlišení od 503-506). KISS, vrstva → jeden symbol (vrstva nese jen
# nekategoriální atributy — verify SV: 46 prvků, žádný typ/šířka). Runnability pozadí (žlutá/zelená
# dle prostupnosti) se NEKRESLÍ: vegetace není v datech (gate Sez. 3), je to UC5 predikce ne projekce
# → ISOM varianta „without background". Mapování viz map_ride_to_isom.
RIDE_LAYERS = ("Lesní průsek",)

# Železnice + tramvaj (Sez. 28+31, real-půlka, liniová — izomorfní s cestami/vedením). ZABAGED:
# `Železniční_trať` (id 75) = osy hlavních tratí; `Železniční_vlečka` (76) = průmyslové/nádražní
# vlečky; **`Tramvajová dráha` (71) = městská tramvaj** (Sez. 31, oprava Sez. 28 vynechání:
# tramvajová točna LS chyběla, ISOM 509 nerozlišuje tramvaj od železnice — vše „Railway").
# Všechny tři → ISOM 509 (map_railway_to_isom, vždy 509, KISS jako budovy→521/vedení→510).
# Pozn.: jméno tramvajové vrstvy v REST je `Tramvajová dráha` s MEZEROU (ne WFS escape
# s podtržítky jako železnice — paralela Lávka Sez. 31; ČÚZK má historicky obě konvence).
# POZN.: „deset kolejí vedle sebe" u nádraží NEJSOU linie — ZABAGED je generalizuje do plochy
# `Kolejiště` (→ PAVED_AREA_LAYERS, 501). Katalog: docs/kb/zabaged-isom-catalog.md (sekce 3).
RAILWAY_LAYERS = ("Železniční_trať", "Železniční_vlečka", "Tramvajová dráha")

# Kolejiště / zpevněné plochy (Sez. 28, real-půlka, plošná — izomorfní s vodní plochou/budovou).
# ZABAGED `Kolejiště` (id 122, plocha) = nádražní kolejová plocha (Liberec hl. n. ~19 ha jako
# JEDEN polygon; jednotlivé koleje data nemodelují jako linie). → ISOM 501 Paved area (kombinovaný
# symbol: hnědá 50% výplň + obrysová linie). Mapování viz map_paved_to_isom. Vzor pro budoucí
# další zdroje 501 (parkoviště ap.). Jinde než u nádraží/zpevněných ploch = 0 prvků.
PAVED_AREA_LAYERS = ("Kolejiště",)

# Vodní feature typy (Sez. 17, real-půlka hydrografie). ZABAGED Polohopis dělí vodu na
# linie (Vodní_tok) a plochy (Vodní_plocha) — izomorfní s cesty=linie. Pramen
# (Zdroj_podzemních_vod) se NEtáhne: ve výsecích OB map je vzácný (ověřeno — v demo
# výřezu 0, nejbližší PS 1,9 km) a 312 Spring je real-only bez náhrady (rozhodnuto Sez. 17).
# Plochy: kromě Vodní_plocha (přírodní — rybníky/jezera) i Pozemní_nádrž (umělé nádrže vč.
# KOUPALIŠŤ/bazénů, podtypob_k='BA') — taky 301. Verify Sez. 27: Lesní koupaliště v LS je
# Pozemní_nádrž ~1934 m², NE Vodní_plocha → bez ní na mapě chybělo.
WATER_LINE_LAYERS = ("Vodní_tok",)
WATER_AREA_LAYERS = ("Vodní_plocha", "Pozemní_nádrž")

# Budovy/stavby (Sez. 18, real-půlka). ZABAGED dělí budovy na bodovou a plošnou vrstvu;
# bodová (`_bod_`) je v lesních OB výsecích prázdná (ověřeno — 0 features na Sovím vrchu),
# proto se táhne jen plošná (izomorfní s Vodní_plocha). Pramen-like vynechání bodové
# vrstvy = „nevymýšlet, co v datech není" (jako Zdroj_podzemních_vod, Sez. 17).
BUILDING_AREA_LAYERS = ("Budova_jednotlivá_nebo_blok_budov__plocha_",)

# El. vedení (Sez. 24, real-půlka). Liniová vrstva (ověřeno DescribeFeatureType: MultiLineString),
# izomorfní s komunikacemi. Stožáry (`Stožár_elektrického_vedení`) jsou bodová vrstva — nesou
# polohu SLOUPŮ, na něž ISOM symbol 510 kreslí kolmé příčky (běžci se jimi řídí, doménový fakt
# uživatele) → reálná data pro příčky (fáze 1, ne vymyšlené). Katalog: docs/kb/zabaged-isom-catalog.md.
POWERLINE_LAYERS = ("Elektrické_vedení",)
POWERLINE_MAST_LAYERS = ("Stožár_elektrického_vedení",)

# Řopíky / lehké opevnění (Sez. 27, fáze 1 = projekce reálných dat, NE dekorace). ZABAGED
# `Bunkr`, filtr typbunkr_k='LO37' (lehký objekt vz.37 čs. pohraničního opevnění); bodová vrstva.
# Na OB mapě = asset (NE prostý ISOM 521 — řopík ≠ běžná stavba), orientace dle linie řopíků +
# „ven" k nejbližší státní hranici. Vyskytují se jen u hranic → jinde 0 prvků (žádný šum).
BUNKER_LAYERS = ("Bunkr",)
BUNKER_TYPE_LO37 = "LO37"          # typbunkr_k řopíku (ostatní typy bunkru zatím vynecháváme)
# Státní hranice pro orientaci řopíku „ven" (Sez. 27). `Hranice správní jednotky` nese VŠECHNY
# správní hranice (KÚ/obec/okres…); vyzn_zsh_k='1' = státní (ověřeno: vyzn_zsh_p „Stát, Oblast, Kraj…").
STATE_BORDER_LAYERS = ("Hranice_správní_jednotky",)
STATE_BORDER_CODE = "1"            # vyzn_zsh_k hodnota pro státní hranici

# Skály a balvany (Sez. 30, real-půlka, MVP rozsah). Verify-against-source (probe_rocks.py
# na Hrubé Skále): vrstvy mají JEN atribut `jmeno` (žádné rozlišení typ/velikost/výška) →
# KISS, vrstva → jeden ISOM symbol (jako budovy→521, vedení→510, železnice→509). Hybridní
# 202 vs 206 u Skalní_útvary řeší až generator.py podle PLOCHY polygonu (žádný ZABAGED
# atribut). Skupina_balvanů__linie_ a Sesuv_půdy__suť odloženy (3 prvky / 0 prvků v probe).
BOULDER_LAYERS = ("Osamělý_balvan__skála__skalní_suk",)            # bodové „turisticky významné"
BOULDER_CLUSTER_LAYERS = ("Skupina_balvanů__bod_",)                # bodová pole drobných kamenů
ROCK_AREA_LAYERS = ("Skalní_útvary",)                              # polygony skalních útvarů

# Mosty / tunely / lávky (Sez. 32 znovu, spec-driven po rollbacku Sez. 31).
# Verify-against-source: foto reálných OB map (uživatel) + ISOM 2017-2 PDF str. 32 + Q&A.
# Klíčové rozhodnutí Sez. 32: most a tunel sdílí ISOM 512 ALE mají SHODNÝ LAYOUT (závorky
# JEN na koncích linie), liší se jen viditelností trati mezi závorkami:
#   Most  = trať PLNÁ mezi závorkami (silnice/železnice viditelná, jen závorky vymezují vstup/výstup)
#   Tunel = trať VYNECHANÁ mezi závorkami (terén skrz, jako bys trať „smazal" v daném úseku)
# Lávka = single dash (template 512.2, kolmá čárka 1,25 mm × 0,25 mm) — pro krátké lávky bez cesty.
# `Most` (id 73, LineString) a `Tunel` (id 74, LineString) jsou samostatné ZABAGED vrstvy
# (NE ve stejném balíku — Sez. 31 fail). `Lávka (linie)` (67) + `Lávka (bod)` (66) = 2 vrstvy
# stejného typu lávky podle geometrické reprezentace.
BRIDGE_LAYERS = ("Most",)                                # most → 512 (osa plná, závorky na koncích)
TUNNEL_LAYERS = ("Tunel",)                               # tunel → 512 (osa vynechaná, závorky na koncích)
FOOTBRIDGE_LINE_LAYERS = ("Lávka (linie)",)              # lávka linie → 512.2 (single dash)
FOOTBRIDGE_POINT_LAYERS = ("Lávka (bod)",)               # lávka bod → 512.2 (single dash)


def _fetch_layer(layer: str, bbox: tuple[float, float, float, float],
                 cache_dir: Path) -> dict:
    """Stáhne jednu vrstvu jako GeoJSON FeatureCollection (REST query + paging, cache na disk).

    `bbox` = (xmin, ymin, xmax, ymax) v S-JTSK (z build_bbox). REST `MapServer/<id>/query`
    s envelope filtrem vrátí prvky protínající výsek; `f=geojson` → tatáž struktura jako
    dřív WFS (parsery `_geom_to_*` beze změny). Server omezuje dávku na `_PAGE` (2000), proto
    **paging smyčka** přes `resultOffset` (Sez. 26: spolehlivý, na rozdíl od rozbitého WFS
    startIndex) — bez ní by velká města (LS) přišla o objekty nad strop.

    Cache key má prefix `zbg_rest_` (odlišení od staré WFS cache, která mohla být uříznutá
    na 1000); stejný výsek → stejný soubor (batch netáhne opakovaně). Izomorfní s dmr cache.
    """
    xmin, ymin, xmax, ymax = bbox
    # cache: souřadnice na celé metry stačí na jednoznačnost výseku
    key = f"zbg_rest_{layer}_{int(xmin)}_{int(ymin)}_{int(xmax)}_{int(ymax)}.geojson"
    cpath = cache_dir / key
    if cpath.exists():
        return json.loads(cpath.read_text(encoding="utf-8"))

    lid = LAYER_IDS.get(layer)
    if lid is None:
        raise ValueError(f"Vrstva {layer!r} nemá REST layer ID (doplň do LAYER_IDS).")
    base = {
        "geometry": f"{xmin},{ymin},{xmax},{ymax}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "5514", "outSR": "5514",
        "spatialRel": "esriSpatialRelIntersects",
        "where": "1=1", "outFields": "*", "f": "geojson",
    }
    # paging: stahuj dávky po _PAGE, dokud server vrací plnou dávku (poslední je kratší)
    features: list[dict] = []
    offset = 0
    while True:
        params = {**base, "resultOffset": str(offset), "resultRecordCount": str(_PAGE)}
        url = f"{_REST_SERVER}/{lid}/query?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "AzimutLab-generator/0.1"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            ctype = resp.headers.get("Content-Type", "")
            raw = resp.read()
        text = raw.decode("utf-8", "replace")
        # při chybě ArcGIS vrací JSON {"error": {...}} (ne GeoJSON FeatureCollection)
        if "json" not in ctype.lower() and not text.lstrip().startswith("{"):
            raise RuntimeError(
                f"ZABAGED REST nevrátil JSON pro vrstvu {layer!r} (id={lid}, "
                f"Content-Type={ctype!r}). Odpověď: {text[:400]}"
            )
        fc = json.loads(text)
        if isinstance(fc.get("error"), dict):
            raise RuntimeError(f"ZABAGED REST chyba pro {layer!r} (id={lid}): {fc['error']}")
        batch = fc.get("features", [])
        features.extend(batch)
        if len(batch) < _PAGE:        # neúplná dávka = poslední → konec
            break
        offset += _PAGE
    result = {"type": "FeatureCollection", "features": features}
    cache_dir.mkdir(parents=True, exist_ok=True)
    cpath.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def fetch_paths(lat: float, lon: float, gw: int, gh: int,
                tile_m: float = 1000.0,
                cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné komunikace pro výsek (lat, lon) jako seznam liniových features.

    Každý prvek: {"layer": název vrstvy, "props": atributy ZABAGED, "lines": [[(x,y)..]]}
    — `lines` je seznam polylinií v S-JTSK metrech (MultiLineString rozbalen na části).
    Mapování na ISOM symbol se dělá výš (po verify atributů, Sez. 16).

    Výsek je TENTÝŽ jako u dmr.fetch_elevation_grid (sdílený build_bbox) → cesty sednou
    na terén bez dalšího georef počítání.
    """
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[dict] = []
    for layer in PATH_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            geom = feat.get("geometry") or {}
            lines = _geom_to_lines(geom)
            if lines:
                out.append({"layer": layer, "props": feat.get("properties", {}),
                            "lines": lines})
    return out


def fetch_forest_rides(lat: float, lon: float, gw: int, gh: int,
                       tile_m: float = 1000.0,
                       cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné lesní průseky pro výsek (lat, lon) jako seznam liniových features.

    Každý prvek: {"layer", "props", "lines": [[(x,y)..]]} — polylinie v S-JTSK metrech
    (MultiLineString rozbalen). Mapování na ISOM (map_ride_to_isom → 508) se dělá výš (Sez. 36).
    Izomorfní s fetch_paths/fetch_railways (linie). Tentýž výsek (sdílený build_bbox) → průsek
    sedne na terén i k cestám. V bezlesém výseku = 0 prvků (žádný šum)."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[dict] = []
    for layer in RIDE_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            lines = _geom_to_lines(feat.get("geometry") or {})
            if lines:
                out.append({"layer": layer, "props": feat.get("properties", {}),
                            "lines": lines})
    return out


def fetch_railways(lat: float, lon: float, gw: int, gh: int,
                   tile_m: float = 1000.0,
                   cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné železniční tratě pro výsek (lat, lon) jako seznam liniových features.

    Každý prvek: {"layer", "props": atributy ZABAGED, "lines": [[(x,y)..]]} — `lines` je
    seznam polylinií v S-JTSK metrech (MultiLineString rozbalen). Mapování na ISOM
    (map_railway_to_isom → 509) se dělá výš, po verify atributů (Sez. 28).

    Izomorfní s fetch_paths/fetch_powerlines (linie). Tentýž výsek (sdílený build_bbox) →
    trať sedne na terén i k cestám/vodě. V lesních výsecích bez trati = 0 prvků (žádný šum).
    """
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[dict] = []
    for layer in RAILWAY_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            lines = _geom_to_lines(feat.get("geometry") or {})
            if lines:
                out.append({"layer": layer, "props": feat.get("properties", {}),
                            "lines": lines})
    return out


def fetch_paved_areas(lat: float, lon: float, gw: int, gh: int,
                      tile_m: float = 1000.0,
                      cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné zpevněné plochy (kolejiště) pro výsek (lat, lon) jako plošné features.

    Každý prvek: {"layer", "props", "rings": [[(x,y)..]]} — vnější obrysy ploch v S-JTSK
    metrech (MultiPolygon rozbalen). Mapování na ISOM (map_paved_to_isom → 501) se dělá výš
    (Sez. 28). Izomorfní s fetch_buildings/area-půlkou fetch_water (plochy mají rings).
    V lesních výsecích bez nádraží = 0 prvků (žádný šum). Tentýž výsek (sdílený build_bbox)."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[dict] = []
    for layer in PAVED_AREA_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            rings = _geom_to_polygons(feat.get("geometry") or {})
            if rings:
                out.append({"layer": layer, "props": feat.get("properties", {}),
                            "rings": rings})
    return out


def fetch_water(lat: float, lon: float, gw: int, gh: int,
                tile_m: float = 1000.0,
                cache_dir: str | Path | None = None) -> tuple[list[dict], list[dict]]:
    """Vrátí reálnou vodu pro výsek (lat, lon): (line_feats, area_feats).

    `line_feats` = vodní toky (Vodní_tok): [{"layer", "props", "lines": [[(x,y)..]]}]
    `area_feats` = vodní plochy (Vodní_plocha): [{"layer", "props", "rings": [[(x,y)..]]}]
    — `rings` jsou vnější obrysy ploch (díry ignorujeme; malé rybníky je nemají).
    Mapování na ISOM (map_water_to_isom) se dělá výš, po verify atributů (Sez. 17).

    Tentýž výsek jako dmr/cesty (sdílený build_bbox) → voda sedne na terén i k cestám.
    Izomorfní s fetch_paths; oddělené linie/plochy, protože render i ISOM symbol se liší.
    """
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    line_feats: list[dict] = []
    area_feats: list[dict] = []
    for layer in WATER_LINE_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            lines = _geom_to_lines(feat.get("geometry") or {})
            if lines:
                line_feats.append({"layer": layer, "props": feat.get("properties", {}),
                                   "lines": lines})
    for layer in WATER_AREA_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            rings = _geom_to_polygons(feat.get("geometry") or {})
            if rings:
                area_feats.append({"layer": layer, "props": feat.get("properties", {}),
                                   "rings": rings})
    return line_feats, area_feats


def fetch_buildings(lat: float, lon: float, gw: int, gh: int,
                    tile_m: float = 1000.0,
                    cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné budovy pro výsek (lat, lon) jako seznam plošných features.

    Každý prvek: {"layer", "props": atributy ZABAGED, "rings": [[(x,y)..]]} — `rings`
    jsou vnější obrysy budov v S-JTSK metrech (MultiPolygon rozbalen). Bodová vrstva
    budov se netáhne (v lesních výsecích prázdná, viz BUILDING_AREA_LAYERS). Mapování
    na ISOM (map_building_to_isom) se dělá výš, po verify atributů (Sez. 18).

    Izomorfní s area-půlkou fetch_water (plochy mají rings, ne lines). Tentýž výsek
    (sdílený build_bbox) → budovy sednou na terén i k cestám/vodě.
    """
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[dict] = []
    for layer in BUILDING_AREA_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            rings = _geom_to_polygons(feat.get("geometry") or {})
            if rings:
                out.append({"layer": layer, "props": feat.get("properties", {}),
                            "rings": rings})
    return out


def fetch_powerlines(lat: float, lon: float, gw: int, gh: int,
                     tile_m: float = 1000.0,
                     cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné el. vedení pro výsek (lat, lon) jako seznam liniových features.

    Každý prvek: {"layer", "props": atributy ZABAGED, "lines": [[(x,y)..]]} — `lines` je
    seznam polylinií v S-JTSK metrech (MultiLineString rozbalen). Mapování na ISOM
    (map_powerline_to_isom → 510) se dělá výš, po verify atributů (Sez. 24).

    Izomorfní s fetch_paths (linie). Tentýž výsek (sdílený build_bbox) → vedení sedne na
    terén i k cestám/vodě. Vzor pro budoucí doplňování dalších liniových vrstev z katalogu.
    """
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[dict] = []
    for layer in POWERLINE_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            lines = _geom_to_lines(feat.get("geometry") or {})
            if lines:
                out.append({"layer": layer, "props": feat.get("properties", {}),
                            "lines": lines})
    return out


def fetch_powerline_masts(lat: float, lon: float, gw: int, gh: int,
                          tile_m: float = 1000.0,
                          cache_dir: str | Path | None = None) -> list[tuple[float, float]]:
    """Vrátí polohy stožárů el. vedení pro výsek jako seznam bodů (x, y) v S-JTSK metrech.

    Stožáry (`Stožár_elektrického_vedení`, geom Point) nesou polohu SLOUPŮ → reálná data
    pro kolmé příčky symbolu ISOM 510 (fáze 1, Sez. 24; ověřeno: stožár leží na vrcholu
    linie vedení). Atributy (výška) jsou v datech prázdné → vracíme jen souřadnice.
    Tentýž výsek (sdílený build_bbox) jako linie vedení → příčky sednou na vedení."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[tuple[float, float]] = []
    for layer in POWERLINE_MAST_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            out.extend(_geom_to_points(feat.get("geometry") or {}))
    return out


def fetch_bunkers(lat: float, lon: float, gw: int, gh: int,
                  tile_m: float = 1000.0,
                  cache_dir: str | Path | None = None) -> list[tuple[float, float]]:
    """Vrátí polohy řopíků (lehkých opevnění LO37) pro výsek jako body (x, y) v S-JTSK metrech.

    ZABAGED `Bunkr` (bodová vrstva); filtr `typbunkr_k='LO37'` = lehký objekt vz.37 čs.
    pohraničního opevnění (= řopík). Ostatní typy bunkru (těžké, atypické) se zatím vynechávají.
    Na OB mapě se nekreslí jako prostý symbol, ale jako asset (řopík ≠ budova) — orientace
    + placement řeší generátor. Izomorfní s fetch_powerline_masts (body). Sez. 27."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[tuple[float, float]] = []
    for layer in BUNKER_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            if feat.get("properties", {}).get("typbunkr_k") == BUNKER_TYPE_LO37:
                out.extend(_geom_to_points(feat.get("geometry") or {}))
    return out


def fetch_state_border(lat: float, lon: float, gw: int, gh: int,
                       tile_m: float = 1000.0,
                       cache_dir: str | Path | None = None) -> list[list[tuple[float, float]]]:
    """Vrátí linie STÁTNÍ hranice protínající výsek jako polylinie (x, y) v S-JTSK metrech.

    ZABAGED `Hranice správní jednotky` nese všechny správní hranice; filtr `vyzn_zsh_k='1'`
    vybere státní (ostatní = obec/okres/KÚ, nezajímají). Slouží k orientaci řopíku „ven" =
    směr k nejbližší státní hranici (univerzální ČR — sever u SV, JV u Šumavy; Sez. 27).
    Prázdné, když výsek hranici neprotíná (vnitrozemí). Izomorfní s fetch_powerlines (linie)."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[list[tuple[float, float]]] = []
    for layer in STATE_BORDER_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            if str(feat.get("properties", {}).get("vyzn_zsh_k")) == STATE_BORDER_CODE:
                out.extend(_geom_to_lines(feat.get("geometry") or {}))
    return out


def fetch_boulders(lat: float, lon: float, gw: int, gh: int,
                   tile_m: float = 1000.0,
                   cache_dir: str | Path | None = None) -> list[tuple[float, float]]:
    """Vrátí polohy osamělých balvanů/skal/skalních suků pro výsek jako body (x, y) v S-JTSK.

    ZABAGED `Osamělý_balvan__skála__skalní_suk` (bodová vrstva, id 10). Ověřeno Sez. 30 na
    Hrubé Skále (6 prvků, jen `jmeno` jako atribut — žádný typ/velikost) → všechny mapujeme
    na 204 (KISS, jako řopíky/stožáry). Mapování na ISOM kód (map_boulder_to_isom → 204) se
    dělá výš. Izomorfní s fetch_powerline_masts/fetch_bunkers (body). Vzácné objekty
    (Hruboskalsko, klasická skalní oblast: 6/24 km² ≈ 0,25/km²) — atributy navíc nejsou."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[tuple[float, float]] = []
    for layer in BOULDER_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            out.extend(_geom_to_points(feat.get("geometry") or {}))
    return out


def fetch_boulder_clusters(lat: float, lon: float, gw: int, gh: int,
                           tile_m: float = 1000.0,
                           cache_dir: str | Path | None = None) -> list[tuple[float, float]]:
    """Vrátí polohy skupin balvanů (boulder clusters) pro výsek jako body (x, y) v S-JTSK.

    ZABAGED `Skupina_balvanů__bod_` (bodová vrstva, id 12). Bodová varianta — skupina je
    natolik těsná, že se nevykresluje per-balvan. Verify Sez. 30 (Hrubá Skála): 168 prvků
    (= 7/km², hojné), jen `jmeno` jako atribut → vše → 207 Boulder cluster (KISS). Liniová
    varianta `Skupina_balvanů__linie_` (id 13) odložena (3 prvky v probe, drobnost).
    Izomorfní s fetch_boulders."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[tuple[float, float]] = []
    for layer in BOULDER_CLUSTER_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            out.extend(_geom_to_points(feat.get("geometry") or {}))
    return out


def fetch_rock_areas(lat: float, lon: float, gw: int, gh: int,
                     tile_m: float = 1000.0,
                     cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné skalní útvary (plochy) pro výsek jako seznam plošných features.

    Každý prvek: {"layer", "props", "rings": [[(x,y)..]]} — vnější obrysy polygonů v S-JTSK
    metrech (MultiPolygon rozbalen). Mapování na ISOM (map_rock_area_to_isom) je hybridní
    podle plochy polygonu (řešeno v generator.py, ne tady) — žádný ZABAGED atribut velikost
    nenese. Verify Sez. 30 (Hrubá Skála): 411 polygonů, medián 1132 m², 304× > 500 m²,
    max 30 444 m² (Mariánská vyhlídka). Izomorfní s fetch_buildings/fetch_paved_areas."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[dict] = []
    for layer in ROCK_AREA_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            rings = _geom_to_polygons(feat.get("geometry") or {})
            if rings:
                out.append({"layer": layer, "props": feat.get("properties", {}),
                            "rings": rings})
    return out


def fetch_bridges(lat: float, lon: float, gw: int, gh: int,
                  tile_m: float = 1000.0,
                  cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné mosty (ZABAGED `Most` linie) pro výsek jako seznam liniových features.

    Each item: {"layer", "props", "lines": [[(x,y)..]]} — `lines` jsou polylinie v S-JTSK
    metrech (LineString → single-line list, MultiLineString rozbalen). Mapování na ISOM
    (`map_bridge_to_isom` → 512) řeší generator.py. Izomorfní s fetch_railways.
    Sez. 32: most a tunel jsou ODDĚLENÉ funkce (`fetch_bridges` vs `fetch_tunnels`), na
    rozdíl od Sez. 31 sloučení — render se liší (most = osa plná, tunel = osa vynechaná)."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[dict] = []
    for layer in BRIDGE_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            lines = _geom_to_lines(feat.get("geometry") or {})
            if lines:
                out.append({"layer": layer, "props": feat.get("properties", {}),
                            "lines": lines})
    return out


def fetch_tunnels(lat: float, lon: float, gw: int, gh: int,
                  tile_m: float = 1000.0,
                  cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné tunely (ZABAGED `Tunel` linie) pro výsek jako seznam liniových features.

    Izomorfní s fetch_bridges. Tunel a most sdílí ISOM 512, ale render se liší (most osa
    plná, tunel vynechaná) → konektor je dělí, aby generator.py znal který je který."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[dict] = []
    for layer in TUNNEL_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            lines = _geom_to_lines(feat.get("geometry") or {})
            if lines:
                out.append({"layer": layer, "props": feat.get("properties", {}),
                            "lines": lines})
    return out


def fetch_footbridges(lat: float, lon: float, gw: int, gh: int,
                      tile_m: float = 1000.0,
                      cache_dir: str | Path | None = None
                      ) -> tuple[list[dict], list[tuple[float, float]]]:
    """Vrátí reálné lávky (ZABAGED `Lávka (linie)` + `Lávka (bod)`) pro výsek.

    Vrací (line_feats, points):
      - line_feats = liniové lávky: [{"layer", "props", "lines": [[(x,y)..]]}]
      - points = bodové lávky: [(x, y), ...] v S-JTSK metrech
    Obě → ISOM 512.2 Footbridge (single dash, template id=127). Bodová lávka NEnese
    orientaci v atributech → render rotuje kolmo k nejbližšímu vodnímu toku."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    line_feats: list[dict] = []
    points: list[tuple[float, float]] = []
    for layer in FOOTBRIDGE_LINE_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            lines = _geom_to_lines(feat.get("geometry") or {})
            if lines:
                line_feats.append({"layer": layer, "props": feat.get("properties", {}),
                                   "lines": lines})
    for layer in FOOTBRIDGE_POINT_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            points.extend(_geom_to_points(feat.get("geometry") or {}))
    return line_feats, points


def map_path_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED komunikaci na ISOM 2017-2 liniový symbol (kód).

    Klíč = FYZICKÝ stav (sjízdnost / zřetelnost), ne správní třída — tak rozlišuje
    ISOM. Ověřeno proti reálným datům (verify-against-source, Sez. 16): `povrch_k`
    Z/T = zpevněná, None = nezpevněná; `typuskom_k` 026 = udržovaná pěšina, jinak
    neudržovaná (REST: atribut malými; WFS ho měl velkými — Sez. 26). Mapovací tabulka:
      Silnice/Ulice     → 502 Wide road     (evidovaná, ≥5 m, autodoprava)
      Silnice neevid.   → 503 Road          (účelová/lesní asfaltka, zpevněná <5 m)
      Cesta zpevněná    → 503 Road          (sjízdná autem)
      Cesta nezpevněná  → 504 Vehicle track (vozová, jen pomalu sjízdná)
      Pěšina udržovaná  → 505 Footpath
      Pěšina neudrž.    → 506 Small footpath

    Vrací holý ISOM kód (int) — konektor nezná render konstanty generátoru (žádný
    cyklický import; generator.py kód interpretuje přes PATH_STYLE). Mapování není
    1:1 (správní třída ZABAGED vs zřetelnost/sjízdnost ISOM) — vědomá aproximace.
    """
    if layer in ("Silnice__dálnice", "Ulice"):
        return 502
    if layer == "Silnice_neevidovaná":
        return 503   # neevidovaná účelová/lesní asfaltka (zpevněná, <5 m) → Road, ne 502
    if layer == "Cesta":
        return 503 if props.get("povrch_k") in ("Z", "T") else 504
    if layer == "Pěšina":
        # pozor: REST vrací atribut malými (`typuskom_k`); WFS ho měl velkými (Sez. 26)
        return 505 if props.get("typuskom_k") == "026" else 506
    return 503   # fallback (neočekávaná vrstva) → viditelná plná čára


def map_ride_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED lesní průsek na ISOM 2017-2 liniový symbol (kód).

    `Lesní průsek` → **508 Narrow ride** (vždy; KISS, jako vedení→510 / železnice→509). Verify
    Sez. 36 (Soví vrch): 46 prvků, vrstva bez kategoriálního atributu (typ/šířka) → jeden symbol.
    508 = průhled lesem bez vyšlapané cesty (ISOM odlišuje od 503-506). Runnability pozadí se
    nekreslí (vegetace = UC5 predikce, ne data). Konektor vrací holý ISOM kód (int)."""
    return 508


def map_railway_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED železniční trať / tramvaj na ISOM 2017-2 liniový symbol (kód).

    `Železniční_trať` / `Železniční_vlečka` / `Tramvajová dráha` → **509 Railway** (vždy; KISS,
    jako budovy→521 / vedení→510). ISOM nerozlišuje trať podle počtu kolejí / elektrizace /
    tramvaje vs vlaku → jeden symbol. Sez. 31: oprava Sez. 28, kde tramvaj byla vynechána jako
    „urbánní" — chybělo to na LS (točna Lidové sady).

    Pozor (verify-against-source, Sez. 28): symbol 509 je v template_classic.omap kombinovaný
    (type=16: černé čárky + bílý „pražcový" knockout), NE prostá linie jako vedení 510. Konektor
    vrací jen holý ISOM kód (int) — render/styl zná generator.py (žádný cyklický import)."""
    return 509


def map_paved_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED zpevněnou plochu na ISOM 2017-2 plošný symbol (kód).

    `Kolejiště` → **501 Paved area** (vždy; KISS, jako budovy→521). 501 je v template_classic.omap
    kombinovaný symbol (hnědá 50% výplň + obrysová linie). Volba symbolu 501 = rozhodnutí uživatele
    (Sez. 28): nádražní kolejiště se na OB mapě generalizuje na zpevněnou plochu, ne na jednotlivé
    koleje. Konektor vrací holý ISOM kód (int) — render zná generator.py (žádný cyklický import)."""
    return 501


def map_water_to_isom(layer: str, props: dict) -> int | None:
    """Mapuje ZABAGED vodní prvek na ISOM 2017-2 kód (int), nebo None = nekreslit.

    Klíč = FYZICKÝ stav (zřetelnost/charakter), ne správní třída — ISOM logika. Ověřeno
    proti reálným datům (verify-against-source, Sez. 17) na výřezu Svitávky:
      Vodní_tok podzemní (typtoku_k=004)   → None  (není na povrchu vidět → nekreslit)
      Vodní_tok občasný (vydattok_p)        → 306 Minor/seasonal water channel (čárkovaný)
      Vodní_tok stálý, pojmenovaný (hlavní) → 304 Crossable watercourse (silnější linie)
      Vodní_tok stálý, bezejmenný (přítok)  → 305 Small crossable watercourse (tenčí linie)
      Vodní_plocha                           → 301 Uncrossable body of water (výplň + břeh)
      Pozemní_nádrž (umělá vč. koupališť)    → 301 (Sez. 27; bazén/nádrž = vodní plocha na mapě)

    Hierarchie 304/305 podle pojmenovanosti toku (generalizovatelné — pojmenovaný tok je
    v ZABAGED evidovaný/významnější; ne hardcode konkrétní řeky). Vrací holý ISOM kód
    (int) nebo None; render konstanty zná generator.py (žádný cyklický import).
    """
    if layer == "Vodní_tok":
        if props.get("typtoku_k") == "004":       # podzemní tok → na povrchu neviditelný
            return None
        if props.get("vydattok_p") == "občasný":  # občasný (vysychající) tok
            return 306
        if props.get("jmeno"):                    # pojmenovaný stálý tok = hlavní
            return 304
        return 305                                 # bezejmenný stálý přítok
    if layer in ("Vodní_plocha", "Pozemní_nádrž"):  # Pozemní_nádrž = umělé nádrže/koupaliště (Sez. 27)
        return 301
    return None


def map_building_to_isom(layer: str, props: dict) -> int | None:
    """Mapuje ZABAGED budovu na ISOM 2017-2 kód (int), nebo None = nekreslit.

    Ověřeno proti reálným datům (verify-against-source, Sez. 18) na výřezu Soví vrch:
    `druhbud` = „budova blíže neurčená" (104×) / „vodojem zemní" (1×); `jmeno` None.
    Vodojem zemní mapuje uživatel (terénní mapér Soví vrchu) také na 521 — v rastru se
    chová jako malá budova (rozhodnutí Sez. 18). Mapování:
      Budova_..._plocha_ (jakýkoli druhbud) → 521 Building (plošný černý symbol)

    Bez rozlišení podle `druhbud` (KISS — jen jeden druh na výřezu navíc). Vrací holý
    ISOM kód (int) nebo None; render konstanty zná generator.py (žádný cyklický import).
    """
    if layer == "Budova_jednotlivá_nebo_blok_budov__plocha_":
        return 521
    return None


def map_powerline_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED el. vedení na ISOM 2017-2 liniový symbol (kód).

    Ověřeno proti reálným datům (verify-against-source, Sez. 24) na výřezech Soví vrch (7
    linií) a Český ráj (2): atribut `NAPETI` (napětí) i `NAZEV` jsou v datech **prázdné**
    (None) → podle napětí NELZE rozlišit VN/VVN, takže žádné dělení 510 vs 511 Major power
    line. Vše → **510 Power line, cableway or skilift** (KISS, jako budovy → vždy 521).

    Pozor (oprava zděděného předpokladu): el. vedení je ISOM **510**, NE 516 (516 = Fence/plot;
    verify proti template_classic.omap, Sez. 24). Vrací holý ISOM kód (int)."""
    return 510   # NAPETI prázdné → bez rozlišení; render konstanty zná generator.py


def map_boulder_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED osamělý balvan na ISOM 2017-2 bodový symbol (kód).

    `Osamělý_balvan__skála__skalní_suk` → **204 Boulder** (vždy; KISS, jako budovy→521).
    Verify Sez. 30 (Hrubá Skála): vrstva má JEN atribut `jmeno` (žádný typ/velikost/výška) →
    nelze rozlišit balvan (204) od velkého balvanu (205) ani od „skalního suku" (206 plocha).
    Bezpečnější KISS než hádat: jeden symbol = jedna vrstva. Vrací holý ISOM kód (int).
    Pokud by ZABAGED někdy doplnil atribut (např. výška), rozšířit zde."""
    return 204


def map_boulder_cluster_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED skupinu balvanů (bod) na ISOM 2017-2 symbol (kód).

    `Skupina_balvanů__bod_` → **207 Boulder cluster** (vždy; KISS). Vrstva má jen `jmeno`
    (Sez. 30). 207 = trojúhelník, plný černý, orientace na sever (ISOM template id 36)."""
    return 207


def map_rock_area_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED skalní útvar (plocha) na ISOM 2017-2 symbol (kód).

    `Skalní_útvary` → **206 Gigantic boulder** (vždy; KISS, jako budovy→521 / vedení→510).
    Verify Sez. 30 (Hrubá Skála): vrstva má JEN `jmeno` (žádný typ/výška/velikost) → KISS,
    vrstva = jeden symbol. Volba 206 = rozhodnutí uživatele (Sez. 30): plná černá plocha
    pro každý polygon (ne hybridní 202/206 podle plochy — drift v rozhodování bez datového
    podkladu). Pro malé výchozy 206 zhrubne, ale zachová izomorfismus s budovami/vodou."""
    return 206


def map_bridge_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED most (linie) na ISOM 2017-2 symbol (kód).

    `Most` → **512 Bridge/tunnel** (vždy; KISS). Sez. 32 spec-driven: ISOM 2017-2 PDF
    str. 32 + foto reálné OB mapy ukazují most jako symbol 512 s **závorkami JEN na
    koncích linie** (= start_symbol + end_symbol v line_symbol), trať mezi nimi viditelná."""
    return 512


def map_tunnel_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED tunel (linie) na ISOM 2017-2 symbol (kód).

    `Tunel` → **512 Bridge/tunnel** (vždy; KISS, stejný symbol jako most). Sez. 32 spec-
    driven: ISOM 2017-2 PDF str. 32 doslovně *„Bridges and tunnels are represented using
    the same basic symbols."* Foto reálné OB mapy: závorky na koncích, trať mezi nimi
    VYNECHANÁ (= úplně mizí, terén viditelný skrz; ne dashed). Generator vykreslí oba módy
    odlišně (most = osa plná, tunel = osa vynechaná), ZABAGED→ISOM kódování je shodné."""
    return 512


def map_footbridge_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED lávku (linie nebo bod) na ISOM 2017-2 symbol (kód).

    `Lávka (linie)` i `Lávka (bod)` → **512.2 Footbridge** (vždy; KISS). Template
    `template_classic.omap` id=127 = point_symbol rotatable, kolmá čárka 1,25 mm × 0,25 mm
    = spec-konformní single dash. Sez. 32: vrátí 5122 jako int alias (string „512.2" se
    sub-tečkou se převede v omap_export podle ROTATABLE_CODES)."""
    return 5122   # = ISOM kód 512.2 jako int (DRY s ostatními ints)


def _geom_to_lines(geom: dict) -> list[list[tuple[float, float]]]:
    """Rozbalí GeoJSON geometrii na seznam polylinií [(x,y), ...] (S-JTSK metry).

    ZABAGED komunikace jsou LineString nebo MultiLineString. Bod/plocha se ignorují.
    """
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "LineString":
        return [[(float(x), float(y)) for x, y, *_ in coords]] if coords else []
    if gtype == "MultiLineString":
        return [[(float(x), float(y)) for x, y, *_ in part] for part in coords if part]
    return []


def _geom_to_polygons(geom: dict) -> list[list[tuple[float, float]]]:
    """Rozbalí GeoJSON plochu na seznam vnějších prstenců [(x,y), ...] (S-JTSK metry).

    Vodní plochy ZABAGED jsou Polygon nebo MultiPolygon. Bereme jen vnější prstenec
    (coords[0]) každého polygonu; vnitřní díry (ostrovy) zatím ignorujeme — malé
    rybníky/tůně je nemají. Linie/bod se ignorují.
    """
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Polygon":
        return [[(float(x), float(y)) for x, y, *_ in coords[0]]] if coords else []
    if gtype == "MultiPolygon":
        return [[(float(x), float(y)) for x, y, *_ in poly[0]] for poly in coords if poly]
    return []


def _geom_to_points(geom: dict) -> list[tuple[float, float]]:
    """Rozbalí GeoJSON bodovou geometrii na seznam bodů [(x,y), ...] (S-JTSK metry).

    Stožáry el. vedení jsou Point (příp. MultiPoint). Linie/plocha se ignorují."""
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Point":
        return [(float(coords[0]), float(coords[1]))] if coords else []
    if gtype == "MultiPoint":
        return [(float(x), float(y)) for x, y, *_ in coords] if coords else []
    return []


def _diagnostics(lat: float, lon: float) -> None:
    """Verify-against-source: stáhne výsek a vypíše bbox, počty, vzorek souřadnic a
    unikátní hodnoty klíčových atributů (typ/povrch) — podklad pro mapování → ISOM."""
    from collections import Counter

    GW, GH, TILE_M = 170, 116, 1000.0
    bbox = build_bbox(lat, lon, GW, GH, TILE_M)
    print(f"Lokalita ({lat}, {lon})  bbox S-JTSK = {tuple(round(v, 1) for v in bbox)}")
    feats = fetch_paths(lat, lon, GW, GH, TILE_M)
    print(f"Celkem features: {len(feats)}\n")
    by_layer: Counter = Counter(f["layer"] for f in feats)
    for layer in PATH_LAYERS:
        layer_feats = [f for f in feats if f["layer"] == layer]
        print(f"=== {layer}: {by_layer[layer]} features ===")
        if not layer_feats:
            continue
        # vzorek souřadnic — ověří axis order (x ≈ -700k easting, y ≈ -1000k northing)
        sample = layer_feats[0]["lines"][0][0]
        print(f"  vzorek souřadnice prvního bodu: {sample}")
        # unikátní hodnoty každého atributu (krátké → kódové sloupce pro mapování)
        keys = layer_feats[0]["props"].keys()
        for k in keys:
            vals = Counter(str(f["props"].get(k)) for f in layer_feats)
            if len(vals) <= 12:   # jen kategoriální (kódy/typy), ne FID/délky
                print(f"  {k}: {dict(vals)}")
        print()


if __name__ == "__main__":
    import sys
    lat = float(sys.argv[1]) if len(sys.argv) > 1 else 50.8214458
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else 14.6712747
    _diagnostics(lat, lon)
