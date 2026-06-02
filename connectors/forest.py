"""
forest.py — věk lesního porostu (porostní skupiny) z AOPK jako PROXY plochy hustníku (UC2/UC5, Sez. 62).

Sourozenec zabaged.py / ruian.py (NE kopie). Zatímco ty táhnou tvrdou geometrii ČÚZK a mapují ji
PROJEKCÍ na ISOM (geometrie = pravda), tenhle konektor je první **PREDIKČNÍ** střípek UC5:
data jsou tvrdá (reálné porostní skupiny LHP/LHO), ale interpretace **věk → běhatelnost (zelená
ISOM)** je proxy — patří do druhé, pseudorealistické půlky generátoru („realisticky vyhlížející
mapa, mimo real jistoty", rozhodnutí Sez. 62). Proto se vrstva všude značí jako PROXY a NEsmí
se vydávat za věrnou runnability (paměť pseudorealistic-phases, vegetace gate Sez. 59).

Zdroj: AOPK ČR, ArcGIS REST `gis.nature.cz/.../Aplikace/Les_Mapy_20nn/MapServer`, vrstva 19
„Porostní skupiny 2022" (esriPolygon, 371 236 polygonů celostátně, z LHP+LHO Lesy ČR + ÚHÚL;
veřejná otevřená data dle zák. 106/1999 Sb.). Souřadnice S-JTSK (EPSG:5514) — bezešvé se ZABAGED/DMR.
Sdílí nízkoúrovňový transport `arcgis.fetch_geojson_layer` + `dmr.build_bbox` (DRY, mirror ruian).

VERIFY-AGAINST-SOURCE (Sez. 62, doloženo standardem KSLH `KSLH021114.pdf` + měřením na NL/LS/NV):
  - Atribut `BARVA` (Integer) = **ordinální kódování věku**, směr **nízká hodnota = mladý porost**
    (lesnická konvence + KSLH Tab. 4 vzorec `Min((A+19),179) div 20` je v věku monotónně rostoucí;
    sanity: nejmladší třídy jsou v datech vzácné — `BARVA 2` jen ~3 %, staré dominují).
  - `BARVA = 15` = **bezlesí / „žádná etáž"** (KSLH Tab. 5 „Obraz BZL → barva 15"), NE starý les
    → bílá (neporostní plocha). Stejně tak velmi vysoké hodnoty = staré/neaplikovatelné → bílá.
  - `ZNACKA` (zakmenění) je ve službě vždy 1 (nedekódováno) → nepoužitelné, jedeme jen `BARVA`.
  - AOPK nezveřejňuje tabulku `BARVA`→přesný rok (KSLH kóduje věk do 5místné kartografické značky,
    ne do `BARVA`; AOPK má vlastní schéma; žádná vrstva služby není klasifikovaná podle věku).
    → roční hranice NELZE odvodit ze zdroje; řezy `BARVA`→ISOM jsou proto **laditelné konstanty**
    níže (kalibrace proxy, ne věrnost) a ověřují se vizuálně.

Pokrytí: jen 3/5 DEV lokalit (NL/LS/NV); SV (terénní flagship) i HS data nemají — sada je sešitá
z LHP/LHO různých roků platnosti, libovolný snímek má díry (mirror řídkých vrstev Sez. 43).
"""
from pathlib import Path

# Sdílený výsek (bezešvost s DMR/ZABAGED) + sdílený ArcGIS REST transport + GeoJSON polygon parser.
from dmr import build_bbox
from arcgis import fetch_geojson_layer, geom_to_polygons

# AOPK ArcGIS REST (JINÝ server než ČÚZK — gis.nature.cz). Vrstva 19 = „Porostní skupiny 2022".
_REST_SERVER = "https://gis.nature.cz/arcgis/rest/services/Aplikace/Les_Mapy_20nn/MapServer"
POROSTNI_SKUPINY_LAYER_ID = 19
# maxRecordCount služby = 1000 (ověřeno, aopk_root.json). MUSÍ se předat do fetch_geojson_layer,
# jinak default 2000 přestřelí strop → server vrátí <2000 → paging smyčka si myslí, že skončila,
# a velká území podtrhne (LS má >1000 prvků → bez tohohle by chyběly).
_PAGE_SIZE = 1000

# ISOM 2017-2 zelené (běhatelnost vegetace): 406 slow running (nejsvětlejší) < 408 walk <
# 410 fight (nejtmavší, nejhustší). Mladý porost = nejhustší → nejtmavší zelená.
ISOM_VEG_FIGHT = 410   # mlazina (nejmladší, nejhustší)
ISOM_VEG_WALK = 408    # tyčkovina (mladý zapojený porost)
ISOM_VEG_SLOW = 406    # mladší kmenovina (řidší)

# Řezy `BARVA` → ISOM zelená. LADITELNÉ (proxy kalibrace, NE věrnost — roční hranice ze zdroje
# nejsou, viz docstring). Pásmo je horní mez (exkluzivně). Cokoli >= FIGHT_MAX a < SLOW_MAX → daná
# zelená; >= SLOW_MAX (vč. bezlesí 15) → bílá (žádný symbol, běhatelný les / neporostní plocha).
# Default kalibrován na NL/LS/NV tak, aby v lese byly všechny 3 odstíny a bílá zůstala převažující
# (realisticky vyhlížející mapa, rozhodnutí Sez. 62); čísla ověř vizuálně a dolaď.
BARVA_FIGHT_MAX = 5    # BARVA  <5    → 410 fight   (nejmladší; v datech 2..4)
BARVA_WALK_MAX = 8     # BARVA  5..7  → 408 walk
BARVA_SLOW_MAX = 11    # BARVA  8..10 → 406 slow
#                        BARVA >=11   → bílá (staré / bezlesí 15)


def fetch_forest_age(lat: float, lon: float, gw: int, gh: int,
                     tile_m: float = 1000.0,
                     cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí porostní skupiny pro výsek jako plochy (jen ty, co padnou na zelenou — viz mapování).

    Každý prvek: {"layer": "Porostní skupiny", "props": {...}, "rings": [[(x,y)..], díra..]} v S-JTSK
    metrech (MultiPolygon rozbalen, díry zachovány — mirror ruian.fetch_private_land). Filtrování na
    zelenou (vyřazení starých/bezlesí) NEdělá konektor — vrací VŠECHNY skupiny s plochou; o symbolu
    (či jeho vynechání = bílá) rozhoduje map_forest_age_to_isom v generátoru (SLAP: konektor = data,
    mapper = ISOM). Bez lesa ve výseku / mimo pokrytí AOPK = 0 prvků."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".forest_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    fc = fetch_geojson_layer(_REST_SERVER, POROSTNI_SKUPINY_LAYER_ID, bbox, cache_dir,
                             page_size=_PAGE_SIZE, cache_key="forest_psk")
    out: list[dict] = []
    for feat in fc.get("features", []):
        rings = geom_to_polygons(feat.get("geometry") or {})
        if rings:
            out.append({"layer": "Porostní skupiny", "props": feat.get("properties", {}),
                        "rings": rings})
    return out


def map_forest_age_to_isom(props: dict) -> int | None:
    """Mapuje porostní skupinu (atribut `BARVA` = ordinální věk) na ISOM zelenou — nebo None (bílá).

    PROXY: věk ≠ skutečná běhatelnost (mladý = hustý drží těsně, starší je nejisté) — vědomě
    přijato, vrstva je predikční (Sez. 62). Řezy `BARVA_*_MAX` jsou laditelné konstanty výše.
    Vrací ISOM kód (410/408/406) nebo None pro běhatelný les / bezlesí (žádný symbol = bílá).
    `BARVA` chybí / není int → None (nehádat)."""
    barva = props.get("BARVA")
    if not isinstance(barva, int):
        return None
    if barva < BARVA_FIGHT_MAX:
        return ISOM_VEG_FIGHT
    if barva < BARVA_WALK_MAX:
        return ISOM_VEG_WALK
    if barva < BARVA_SLOW_MAX:
        return ISOM_VEG_SLOW
    return None   # staré / bezlesí (BARVA 15) → bílá


def _diagnostics(lat: float, lon: float, gw: int = 6, gh: int = 4, tile_m: float = 4000.0) -> None:
    """Verify-against-source: stáhne porostní skupiny výseku, vypíše histogram `BARVA` + ISOM rozpad."""
    from collections import Counter
    feats = fetch_forest_age(lat, lon, gw, gh, tile_m)
    barva = Counter(f["props"].get("BARVA") for f in feats)
    isom = Counter(map_forest_age_to_isom(f["props"]) for f in feats)
    n = len(feats) or 1
    print(f"porostní skupiny: {len(feats)}")
    print("  BARVA :", dict(sorted(barva.items(), key=lambda kv: (kv[0] is None, kv[0]))))
    name = {410: "410 fight", 408: "408 walk", 406: "406 slow", None: "bílá (les/bezlesí)"}
    for code in (410, 408, 406, None):
        c = isom[code]
        print(f"  {name[code]:22}: {c:5d}  ({100*c/n:4.1f} %)")


if __name__ == "__main__":
    # Nová Louka (Jizerské hory) — pokrytá DEV lokalita, verify dostupnosti + kalibrace řezů.
    _diagnostics(50.8140386, 15.1579069)
