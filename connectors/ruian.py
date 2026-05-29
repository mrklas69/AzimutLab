"""
ruian.py — reálné katastrální parcely z ČÚZK RÚIAN (ArcGIS REST; UC2 konektor, real-půlka, Sez. 42).

Sourozenec zabaged.py (NE kopie): zabaged.py táhne TOPOGRAFII (ZABAGED Polohopis), ruian.py táhne
KATASTR (RÚIAN — Registr územní identifikace, adres a nemovitostí). Oba běží na témže ČÚZK ArcGIS
serveru a sdílí nízkoúrovňový transport `arcgis.fetch_geojson_layer` + `dmr.build_bbox` (DRY, Sez. 42).

Motivace (Sez. 42, %THINK olivová 520): živý OB mapař maluje olivovou „Area which shall not be
entered" (ISOM 520) tam, kam běžci nesmí — typicky soukromé zahrady a dvory u domů. Tohle je
deterministicky odvoditelné z katastru: parcela podle DRUHU POZEMKU. RÚIAN vrstva `Parcela`
(layer 5) nese pole `druhpozemkukod` s codedValue doménou (ověřeno ze serveru, Sez. 42):
  2 orná půda · 3 chmelnice · 4 vinice · 5 ZAHRADA · 6 ovocný sad · 7,8 trvalý travní porost
  · 10 lesní pozemek · 11 vodní plocha · 13 ZASTAVĚNÁ PLOCHA A NÁDVOŘÍ · 14 ostatní plocha
→ olivová 520 = parcely druhu {5 zahrada, 13 zastavěná plocha a nádvoří} (privátní pozemek
u domu). Proximita k zástavbě je nesena IMPLICITNĚ druhem pozemku — pole/louka daleko od domů
mají jiný druh (2/7) a olivové nejsou (rozhodnuto Sez. 42).

Zdroj: ČÚZK RÚIAN, ArcGIS REST MapServer `/RUIAN/MapServer` (veřejná otevřená data dle zák.
111/2009 Sb. o základních registrech, poskytovaná bezúplatně; copyrightText = ČÚZK, atribuce).
`f=geojson` → tatáž struktura jako ZABAGED (žádný nový parser). Souřadnice S-JTSK (EPSG:5514).

Pozn. k dostupnosti (verify Sez. 42): vrstva 5 `Parcela` má maxRecordCount 1 000 000 (žádný
strop jako ZABAGED 2000), `where` filtr `druhpozemkukod IN (5,13)` běží na serveru → stahuje se
rovnou jen privátní pozemek.
"""

from pathlib import Path

# Sdílený výsek s výškopisem i topografií (bezešvost — totéž bbox jako DMR/ZABAGED) a sdílený
# ArcGIS REST transport (paging+cache+error) + GeoJSON polygon parser.
from dmr import build_bbox
from arcgis import fetch_geojson_layer, geom_to_polygons

# RÚIAN ArcGIS REST MapServer (týž server jako ZABAGED, jiný service). Vrstva 5 = `Parcela`
# (polygon). ID ověřeno ?f=json (Sez. 42).
_REST_SERVER = "https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer"
PARCELA_LAYER_ID = 5

# Číselník druhu pozemku (codedValue doména `druhpozemkukod`, ověřeno ze serveru, Sez. 42).
# Drženo pro dokumentaci + budoucí druhou vlnu (sad 6 → 413, pole 2 → 412 apod.).
DRUH_POZEMKU = {
    2: "orná půda", 3: "chmelnice", 4: "vinice", 5: "zahrada", 6: "ovocný sad",
    7: "trvalý travní porost", 8: "trvalý travní porost", 10: "lesní pozemek",
    11: "vodní plocha", 13: "zastavěná plocha a nádvoří", 14: "ostatní plocha",
}
# Privátní pozemek u domu → olivová 520 (Sez. 42). Zahrada (5) + zastavěná plocha a nádvoří (13).
PRIVATE_LAND_CODES = (5, 13)


def fetch_private_land(lat: float, lon: float, gw: int, gh: int,
                       tile_m: float = 1000.0,
                       cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné privátní parcely (zahrada + zastavěná plocha a nádvoří) pro výsek jako plochy.

    Každý prvek: {"layer", "props", "rings": [[(x,y)..]]} — vnější obrysy parcel v S-JTSK
    metrech (MultiPolygon rozbalen). Mapování na ISOM (map_private_land_to_isom → 520) níž.
    Izomorfní se zabaged.fetch_cemeteries/fetch_open_land (plošný pokryv) — generátor je sype
    do téže olivové třídy 520. `where` filtr `druhpozemkukod IN (5,13)` běží na serveru, takže
    se táhne rovnou jen privátní pozemek (ne celý katastr). Bez zástavby ve výseku = 0 prvků."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".ruian_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    where = "druhpozemkukod IN (" + ",".join(str(c) for c in PRIVATE_LAND_CODES) + ")"
    fc = fetch_geojson_layer(_REST_SERVER, PARCELA_LAYER_ID, bbox, cache_dir,
                             where=where, cache_key="ruian_parcela_privatni")
    out: list[dict] = []
    for feat in fc.get("features", []):
        rings = geom_to_polygons(feat.get("geometry") or {})
        if rings:
            out.append({"layer": "Parcela", "props": feat.get("properties", {}),
                        "rings": rings})
    return out


def map_private_land_to_isom(layer: str, props: dict) -> int:
    """Mapuje RÚIAN privátní parcelu na ISOM 2017-2 plošný symbol (kód).

    Zahrada (druhpozemkukod 5) i zastavěná plocha a nádvoří (13) → **520 Area which shall not
    be entered** (vždy; KISS jako hřbitov→520, budovy→521). Olivová out-of-bounds plocha =
    soukromý pozemek u domu, kam běžci nesmí (Sez. 42). Konektor vrací holý ISOM kód (int)."""
    return 520


def _diagnostics(lat: float, lon: float) -> None:
    """Verify-against-source: stáhne privátní parcely výseku a vypíše počet + rozpad podle druhu."""
    feats = fetch_private_land(lat, lon, 6, 4, 4000.0)
    by_druh: dict = {}
    for f in feats:
        kod = f["props"].get("druhpozemkukod")
        by_druh[kod] = by_druh.get(kod, 0) + 1
    print(f"RÚIAN privátní parcely: {len(feats)}")
    for kod, cnt in sorted(by_druh.items()):
        print(f"  druh {kod} ({DRUH_POZEMKU.get(kod, '?')}): {cnt}")


if __name__ == "__main__":
    # Soví vrch (default dev lokalita) — verify dostupnosti a rozpadu druhů.
    _diagnostics(50.8214458, 14.6712747)
