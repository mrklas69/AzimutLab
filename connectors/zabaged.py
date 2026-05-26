"""
zabaged.py — reálné cesty z ČÚZK ZABAGED® Polohopis WFS (UC2 konektor, real-půlka §4.9).

Sourozenec dmr.py (NE kopie): dmr.py táhne reálný VÝŠKOPIS (DMR 5G, rastr/ImageServer),
zabaged.py táhne reálné KOMUNIKACE (vektor, WFS). Oba berou tentýž výsek přes sdílený
dmr.build_bbox() → reálné cesty padnou bezešvě na tentýž terén jako vrstevnice z DMR.

Zdroj: ČÚZK ZABAGED Polohopis WFS 2.0.0 (open data, CC BY 4.0 — atribuce povinná).
Endpoint vrací GeoJSON přímo (ne GML) → žádný GML parsing, izomorfní s contours.geojson.

Klíčová zjištění (ověřeno Sezení 16):
  - WFS 2.0.0: .../arcgis/services/ZABAGED_POLOHOPIS/MapServer/WFSServer
  - feature typy komunikací: Cesta, Pěšina, Silnice__dálnice, Ulice, Turistická_trasa
  - outputFormat=GEOJSON, srsName/bbox v EPSG:5514 (S-JTSK, shoda s dmr.py)
  - geometrie MultiLineString; atributy typu/povrchu nesou ISOM-relevantní rozlišení

Pozn. k souřadnicím: S-JTSK (EPSG:5514) má v ČR záporné x i y (x ≈ -700 tis = easting,
y ≈ -1000 tis = northing). Axis order WFS odpovědi se OVĚŘUJE diagnostikou (main), ne hádá.
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

# Sdílený výsek s výškopisem (izomorfismus, bezešvost) — build_bbox je public (Sez. 8).
from dmr import build_bbox

# WFS endpoint ZABAGED Polohopis (nové .gov.cz; cesta MUSÍ obsahovat /services/...WFSServer).
_WFS_SERVER = "https://ags.cuzk.gov.cz/arcgis/services/ZABAGED_POLOHOPIS/MapServer/WFSServer"

# Feature typy komunikací relevantní pro OB (les). Turistická_trasa se vynechává — vede
# zpravidla PO existující cestě/pěšině → duplikovala by liniovou síť (rozhodnuto Sez. 16).
# (Silnice/Ulice jsou v lese vzácné, ale patří do sítě, kde výsek zasáhne okraj obce.)
LAYERS = ("Cesta", "Pěšina", "Silnice__dálnice", "Ulice")


def _fetch_layer(layer: str, bbox: tuple[float, float, float, float],
                 cache_dir: Path) -> dict:
    """Stáhne jednu vrstvu komunikací jako GeoJSON FeatureCollection (cache na disk).

    `bbox` = (xmin, ymin, xmax, ymax) v S-JTSK (z build_bbox). WFS GetFeature s BBOX
    filtrem vrátí jen linie protínající výsek. Cache key = vrstva + bbox (stejný výsek
    → stejný soubor, batch netáhne opakovaně). Izomorfní s dmr cache.
    """
    xmin, ymin, xmax, ymax = bbox
    # cache: souřadnice na celé metry stačí na jednoznačnost výseku
    key = f"zbg_{layer}_{int(xmin)}_{int(ymin)}_{int(xmax)}_{int(ymax)}.geojson"
    cpath = cache_dir / key
    if cpath.exists():
        return json.loads(cpath.read_text(encoding="utf-8"))

    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": f"ZABAGED_POLOHOPIS:{layer}",
        "srsName": "EPSG:5514",
        # WFS 2.0.0 bbox: minx,miny,maxx,maxy + CRS; pořadí os ověřeno diagnostikou
        "bbox": f"{xmin},{ymin},{xmax},{ymax},EPSG:5514",
        "outputFormat": "GEOJSON",
    }
    url = f"{_WFS_SERVER}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "AzimutLab-generator/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        ctype = resp.headers.get("Content-Type", "")
        raw = resp.read()
    # server při chybě vrací XML ExceptionReport (text) místo JSON → srozumitelná výjimka
    text = raw.decode("utf-8", "replace")
    if "json" not in ctype.lower() and not text.lstrip().startswith("{"):
        raise RuntimeError(
            f"ZABAGED WFS nevrátil GeoJSON pro vrstvu {layer!r} "
            f"(Content-Type={ctype!r}). Odpověď: {text[:400]}"
        )
    fc = json.loads(text)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cpath.write_text(text, encoding="utf-8")
    return fc


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
    for layer in LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            geom = feat.get("geometry") or {}
            lines = _geom_to_lines(geom)
            if lines:
                out.append({"layer": layer, "props": feat.get("properties", {}),
                            "lines": lines})
    return out


def map_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED komunikaci na ISOM 2017-2 liniový symbol (kód).

    Klíč = FYZICKÝ stav (sjízdnost / zřetelnost), ne správní třída — tak rozlišuje
    ISOM. Ověřeno proti reálným datům (verify-against-source, Sez. 16): `povrch_k`
    Z/T = zpevněná, None = nezpevněná; `TYPUSKOM_K` 026 = udržovaná pěšina, jinak
    neudržovaná. Mapovací tabulka:
      Silnice/Ulice     → 502 Wide road     (zpevněná, autodoprava)
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
    if layer == "Cesta":
        return 503 if props.get("povrch_k") in ("Z", "T") else 504
    if layer == "Pěšina":
        return 505 if props.get("TYPUSKOM_K") == "026" else 506
    return 503   # fallback (neočekávaná vrstva) → viditelná plná čára


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
    for layer in LAYERS:
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
