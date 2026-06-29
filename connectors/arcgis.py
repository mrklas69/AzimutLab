"""
arcgis.py — sdílený nízkoúrovňový klient ČÚZK ArcGIS REST (UC2, společný základ konektorů, Sez. 42).

Sourozenci zabaged.py (topografie ZABAGED) i ruian.py (katastr/RÚIAN) berou data z TÉHOŽ
ArcGIS REST serveru ČÚZK (`ags.cuzk.gov.cz/arcgis/rest/services`) — liší se jen MapServer,
layer ID, velikostí dávky a případně `where` filtrem. Tahle utilita drží JEDNU paging+cache+
error smyčku (DRY, Sez. 42), aby ji oba sourozenci nemuseli duplikovat. Precedent shodný
s `dmr.build_bbox` — sdílený geo-základ žije v jednom modulu a sourozenci ho importují.

Dělicí čára: sem patří JEN obecný transport (REST query `f=geojson`, resultOffset paging,
disk cache, ArcGIS chybová odpověď). Mapování layer NAME→ID a ISOM crosswalk zůstávají
v doménových modulech (zabaged/ruian) — ty volají `fetch_geojson_layer` už s numerickým ID.

Souřadnice: in/outSR = EPSG:5514 (S-JTSK) — totéž jako zbytek konektorů (bezešvost s DMR).
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

from ssl_ctx import ssl_context  # sdílený certifi TLS kontext (ČÚZK Let's Encrypt, Sez. 175)

DEFAULT_PAGE = 2000   # typický maxRecordCount ArcGIS REST query (ZABAGED Polohopis); RÚIAN má víc


def _exceeded_transfer_limit(payload: dict) -> bool:
    """ArcGIS signalizuje další stránku přes `exceededTransferLimit`, ne jen délkou dávky."""
    if payload.get("exceededTransferLimit") is True:
        return True
    properties = payload.get("properties")
    return isinstance(properties, dict) and properties.get("exceededTransferLimit") is True


def fetch_geojson_layer(server: str, layer_id: int,
                        bbox: tuple[float, float, float, float],
                        cache_dir: Path, *,
                        page_size: int = DEFAULT_PAGE,
                        where: str = "1=1",
                        cache_key: str = "arcgis") -> dict:
    """Stáhne jednu ArcGIS REST vrstvu jako GeoJSON FeatureCollection (query + paging, cache na disk).

    `bbox` = (xmin, ymin, xmax, ymax) v S-JTSK (z dmr.build_bbox). `{server}/{layer_id}/query`
    s envelope filtrem vrátí prvky protínající výsek; `f=geojson` → tatáž struktura napříč
    konektory (parsery `geom_to_*` beze změny). Server omezuje dávku na `page_size`, proto
    **paging smyčka** přes `resultOffset` (spolehlivý, na rozdíl od rozbitého WFS startIndex,
    Sez. 26) — bez ní by velká území přišla o objekty nad strop.

    `where` filtruje na serveru (např. RÚIAN `druhpozemkukod IN (5,13)`); ZABAGED nechává `1=1`.
    `cache_key` je prefix souboru — volající ho volí tak, aby jednoznačně odrážel vrstvu
    (a případně `where`), stejný výsek → stejný soubor (batch netáhne opakovaně). Souřadnice
    v klíči na celé metry stačí na jednoznačnost výseku.
    """
    xmin, ymin, xmax, ymax = bbox
    key = f"{cache_key}_{int(xmin)}_{int(ymin)}_{int(xmax)}_{int(ymax)}.geojson"
    cpath = cache_dir / key
    if cpath.exists():
        return json.loads(cpath.read_text(encoding="utf-8"))

    base = {
        "geometry": f"{xmin},{ymin},{xmax},{ymax}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "5514", "outSR": "5514",
        "spatialRel": "esriSpatialRelIntersects",
        "where": where, "outFields": "*", "f": "geojson",
    }
    # paging: ArcGIS umí vrátit kratší dávku a přesto signalizovat pokračování přes
    # exceededTransferLimit. Offset proto posouváme o skutečně přijaté prvky, ne o requested page_size.
    features: list[dict] = []
    offset = 0
    while True:
        params = {**base, "resultOffset": str(offset), "resultRecordCount": str(page_size)}
        url = f"{server}/{layer_id}/query?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "AzimutLab-generator/0.1"})
        with urllib.request.urlopen(req, timeout=120, context=ssl_context()) as resp:
            ctype = resp.headers.get("Content-Type", "")
            raw = resp.read()
        text = raw.decode("utf-8", "replace")
        # při chybě ArcGIS vrací JSON {"error": {...}} (ne GeoJSON FeatureCollection)
        if "json" not in ctype.lower() and not text.lstrip().startswith("{"):
            raise RuntimeError(
                f"ArcGIS REST nevrátil JSON (server={server}, layer_id={layer_id}, "
                f"Content-Type={ctype!r}). Odpověď: {text[:400]}"
            )
        fc = json.loads(text)
        if isinstance(fc.get("error"), dict):
            raise RuntimeError(f"ArcGIS REST chyba (layer_id={layer_id}): {fc['error']}")
        batch = fc.get("features", [])
        if not isinstance(batch, list):
            raise RuntimeError(f"ArcGIS REST vrátil neplatné features (layer_id={layer_id}): {type(batch).__name__}")
        features.extend(batch)
        exceeded = _exceeded_transfer_limit(fc)
        if not batch:
            if exceeded:
                raise RuntimeError(
                    f"ArcGIS REST signalizuje další stránku bez features (layer_id={layer_id}, offset={offset})"
                )
            break
        offset += len(batch)
        if not exceeded and len(batch) < page_size:        # neúplná dávka bez serverového pokračování = konec
            break
    result = {"type": "FeatureCollection", "features": features}
    cache_dir.mkdir(parents=True, exist_ok=True)
    cpath.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def geom_to_lines(geom: dict) -> list[list[tuple[float, float]]]:
    """Rozbalí GeoJSON geometrii na seznam polylinií [(x,y), ...] (S-JTSK metry).

    LineString nebo MultiLineString (komunikace, vedení, …). Bod/plocha se ignorují.
    """
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "LineString":
        return [[(float(x), float(y)) for x, y, *_ in coords]] if coords else []
    if gtype == "MultiLineString":
        return [[(float(x), float(y)) for x, y, *_ in part] for part in coords if part]
    return []


def geom_to_polygons(geom: dict) -> list[list[list[tuple[float, float]]]]:
    """Rozbalí GeoJSON plochu na seznam POLYGONŮ, každý jako prsteny [vnější, díra1, …] (S-JTSK metry).

    Polygon nebo MultiPolygon (voda, budovy, pokryv, parcely). GeoJSON (RFC 7946) drží vnější
    obrys jako `coords[0]` a vnitřní DÍRY (výřezy/ostrovy) jako `coords[1:]`. Vracíme je VČETNĚ
    děr (Sez. 54): velké administrativní plochy (ZABAGED `Ostatní plocha v sídlech`) jsou ze
    70–80 % díry (budovy/zeleň/cesty vykrojené ven) — bez nich by vnější obrys zalil celé sídlo.

    Návratový tvar: `[[outer, hole1, …], …]` — list polygonů; polygon = list prstenů (první vnější,
    zbytek díry); prsten = list bodů. Konzument bere `poly[0]` vnější, `poly[1:]` díry. Linie/bod ignor.
    """
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Polygon":
        return [[[(float(x), float(y)) for x, y, *_ in ring] for ring in coords]] if coords else []
    if gtype == "MultiPolygon":
        return [[[(float(x), float(y)) for x, y, *_ in ring] for ring in poly]
                for poly in coords if poly]
    return []


def geom_to_points(geom: dict) -> list[tuple[float, float]]:
    """Rozbalí GeoJSON bodovou geometrii na seznam bodů [(x,y), ...] (S-JTSK metry).

    Point (příp. MultiPoint) — stožáry, body. Linie/plocha se ignorují."""
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Point":
        return [(float(coords[0]), float(coords[1]))] if coords else []
    if gtype == "MultiPoint":
        return [(float(x), float(y)) for x, y, *_ in coords] if coords else []
    return []
