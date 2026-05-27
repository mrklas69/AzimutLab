"""omap_export.py — vloží výstup generátoru do uživatelova čistého ISOM 2017-2
template (.omap). Template-based (Sez. 14).

Sez. 13 šla OD NULY (minimální 7-symbolová sada), aby se zbavila bordelu děděného
z CIZÍCH .omap (101.1 LIDAR contour, 503 „Minor road", cizí podkladové obrázky). Sez. 14:
uživatel dodal VLASTNÍ čistý template `template_classic.omap` (169 ISOM 2017-2 symbolů,
35 barev, prázdné <objects>/<templates>) → návrat k template-based, ale nad čistým zdrojem.
Zisk oproti od-nuly:
  - věrná geometrie bodů: 109 = kruh, 110 = elipsa (area_symbol), 111 = oblouk „⌣"
    (line_symbol) — místo dřívějšího jednotného zjednodušeného kruhu;
  - plná ISOM symbolová knihovna jako reálná mapa z OOM → menší domain gap feederu UC5.

Skládáme tedy jen <objects> (vrstevnice 101/102, cesty 502-506, voda 304/305/306 + plocha
301.1, budovy 521, body 109/110/111); barvy/symboly/georef/view přebíráme z template beze
změny. Symbol id parsujeme z template podle ISOM kódu (robustní vůči re-uložení template
v OOM — id NEjsou pořadová: 503→110, 505→112).

Georef: template má Local CRS (paper-space), scale 1:10000. Object coords jsou v µm na
PAPÍŘE; 1 m terénu = (1e6/scale) µm. Vycentrováno na (0,0), bez Y-flip (paper y i grid gy
rostou dolů — stejná konvence jako contours.geojson).

NEduplikuje Pic2Omap `db2omap` (ten jde z rastru přes .pgw/cv2; my z přesných polylinií).
"""

import re
from pathlib import Path

# Čistý ISOM 2017-2 template (vyrobil uživatel v OOM: Sez. 14, naposled přepsán Sez. 18).
# Sebeobsažný v sandbox/.
TEMPLATE_PATH = Path(__file__).parent / "template_classic.omap"

# ISOM kódy, které generátor produkuje. Objekty se na symboly odkazují přes id z template.
# Cesty: proc větev dělá 503/505; reálná (ZABAGED WFS, Sez. 16) i 502/504/506. Voda (Sez. 17):
# toky 304/305/306 (liniové) + plocha 301.1 (plošný symbol — kombinovaný 301 s břehem je
# type 16, nepřiřaditelný objektu). Budovy (Sez. 18): plocha 521 (plošný symbol, type 4).
# Všechny musí být v template (čistá ISOM 2017-2 je obsahuje).
USED_CODES = ("101", "102", "502", "503", "504", "505", "506",
              "304", "305", "306", "301.1", "521", "510", "109", "110", "111")
# Rotatable symboly (orientaci nese objekt). 110 elipsa je rotatable; 109/111 pevně k severu.
ROTATABLE_CODES = frozenset({"110"})

# Plošné (area) ISOM kódy generátoru — OOM vyplní plošný symbol JEN u uzavřeného path
# (poslední bod nese close flag). Liniové kódy (vrstevnice/cesty/vodní toky) zůstávají
# otevřené. Verify-against-source (Sez. 18): OOM po otevření flagless souboru sám doplnil
# na poslední bod ringu flag 18 → flagless plochy se nevyplnily (uživatel „nevidím budovy/vodu").
AREA_CODES = frozenset({"301.1", "521"})
OOM_CLOSE_FLAG = 18   # OOM coord flag uzavřeného ringu (16 hole point + 2 close point)


def _parse_symbol_ids(template_xml: str) -> dict[str, int]:
    """Mapování ISOM kód → symbol id z <symbols> template (přesná shoda kódu: 101 ≠ 101.1).

    Id v OOM nejsou pořadová ani rovna kódu (503 má id 110, 505 id 112), proto se musí číst
    ze souboru, ne hádat. `setdefault` drží první výskyt (kód je v template unikátní).
    """
    ids: dict[str, int] = {}
    for m in re.finditer(r'<symbol\b[^>]*\bid="(\d+)"[^>]*\bcode="([^"]+)"', template_xml):
        ids.setdefault(m.group(2), int(m.group(1)))
    missing = [c for c in USED_CODES if c not in ids]
    if missing:
        raise ValueError(f"Template {TEMPLATE_PATH.name} postrádá ISOM symboly: {missing}")
    return ids


def write_omap(contour_features: list[tuple], path_features: list[tuple],
               point_symbols: list[dict], water_features: list[tuple],
               building_features: list[tuple], powerline_features: list[tuple],
               gw: int, gh: int,
               world_w_m: float, world_h_m: float, scale: float,
               out_path: str | Path) -> dict:
    """Zapíše vrstevnice + cesty + vodu + budovy + el. vedení + body do `.omap` vložením do template.

    `contour_features` = [(line N×2 grid, code 101/102)], `path_features` =
    [(curve grid, code 502-506)] (proc dělá 503/505, reálná větev plnou hierarchii),
    `water_features` = [(line/ring grid, code 304/305/306/301.1)],
    `building_features` = [(ring grid, code 521)], `powerline_features` = [(line grid, code 510)]
    (liniový objekt, Sez. 24) — vše v souřadnicích MŘÍŽKY (gx∈0..gw-1, gy∈0..gh-1); voda i budovy
    jdou jako liniové objekty (type 1), OOM je vyplní podle typu symbolu (plošný 301/521).
    `point_symbols` = [{symbol, gx, gy}] (ISOM 109/110/111). `scale` = jmenovatel měřítka.
    Návrat: {"contours", "paths", "water", "buildings", "powerlines", "points", "objects"}.
    """
    out_path = Path(out_path)
    template_xml = TEMPLATE_PATH.read_text(encoding="utf-8")
    sym = _parse_symbol_ids(template_xml)

    # paper-space: 1 m terénu = (1e6/scale) µm papíru; výsek vycentrován na (0,0)
    um_per_m = 1_000_000.0 / scale
    pw = world_w_m * um_per_m
    ph = world_h_m * um_per_m

    def paper(gx: float, gy: float) -> tuple[int, int]:
        # grid → paper µm; bez Y-flip (gy roste dolů = paper y roste dolů)
        return (round((float(gx) / (gw - 1) - 0.5) * pw),
                round((float(gy) / (gh - 1) - 0.5) * ph))

    def line_object(points, code: str) -> str | None:
        coords = [paper(gx, gy) for gx, gy in points]
        if len(coords) < 2:
            return None
        coord_str = ";".join(f"{x} {y}" for x, y in coords) + ";"
        return (f'<object type="1" symbol="{sym[code]}">'
                f'<coords count="{len(coords)}">{coord_str}</coords></object>')

    def area_object(ring, code: str) -> str | None:
        """Plošný objekt (ISOM area symbol): uzavřený path s close flagem na posledním bodě.
        OOM vyplní area symbol jen u UZAVŘENÉHO path — flagless by zůstal jen obrysem/se
        nevykreslil. Flag uzavře poslední bod zpět na první (ZABAGED ring má first==last)."""
        coords = [paper(gx, gy) for gx, gy in ring]
        if len(coords) < 3:
            return None
        parts = [f"{x} {y}" for x, y in coords]
        parts[-1] += f" {OOM_CLOSE_FLAG}"
        coord_str = ";".join(parts) + ";"
        return (f'<object type="1" symbol="{sym[code]}">'
                f'<coords count="{len(coords)}">{coord_str}</coords></object>')

    objs: list[str] = []
    n_contours = n_paths = n_water = n_buildings = n_powerlines = n_points = 0
    # Liniové objekty (vrstevnice/cesty/vodní toky) = otevřený path; plošné (301.1 voda,
    # 521 budova) = uzavřený path s close flagem (jinak OOM nevyplní — viz AREA_CODES).
    for line, code in contour_features:
        o = line_object(line, str(code))
        if o:
            objs.append(o); n_contours += 1
    for curve, code in path_features:
        o = line_object(curve, str(code))
        if o:
            objs.append(o); n_paths += 1
    for geom, code in water_features:
        code = str(code)
        o = area_object(geom, code) if code in AREA_CODES else line_object(geom, code)
        if o:
            objs.append(o); n_water += 1
    for ring, code in building_features:
        o = area_object(ring, str(code))
        if o:
            objs.append(o); n_buildings += 1
    # el. vedení (510) = liniový objekt (otevřený path), jako cesty/vrstevnice (Sez. 24)
    for line, code in powerline_features:
        o = line_object(line, str(code))
        if o:
            objs.append(o); n_powerlines += 1
    # bodové symboly extrémů = bodové objekty (type 0, 1 souřadnice); 110 rotatable → rotation
    for ps in point_symbols:
        code = str(ps["symbol"])
        x, y = paper(ps["gx"], ps["gy"])
        rot = ' rotation="0"' if code in ROTATABLE_CODES else ""
        objs.append(f'<object type="0" symbol="{sym[code]}"{rot}>'
                    f'<coords count="1">{x} {y};</coords></object>')
        n_points += 1

    # vložení objektů do prázdného <objects count="0"> template (jediný výskyt — ověřeno)
    objects_open = f'<objects count="{len(objs)}">{"".join(objs)}'
    doc, n_sub = re.subn(r'<objects count="0">', objects_open, template_xml, count=1)
    if n_sub != 1:
        raise ValueError('Template nemá očekávaný prázdný <objects count="0"> blok')

    out_path.write_text(doc, encoding="utf-8")
    return {"contours": n_contours, "paths": n_paths, "water": n_water,
            "buildings": n_buildings, "powerlines": n_powerlines,
            "points": n_points, "objects": len(objs)}
