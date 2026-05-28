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

Georef: template má Local CRS (paper-space); jeho původní scale (1:15000) přepisujeme na
generátorové MAP_SCALE (1:10000, nález Sez. 26 — viz write_omap). Object coords jsou v µm na
PAPÍŘE; 1 m terénu = (1e6/scale) µm. Vycentrováno na (0,0), bez Y-flip (paper y i grid gy
rostou dolů — stejná konvence jako contours.geojson).

NEduplikuje Pic2Omap `db2omap` (ten jde z rastru přes .pgw/cv2; my z přesných polylinií).
"""

import math
import re
from pathlib import Path

# Čistý ISOM 2017-2 template (vyrobil uživatel v OOM: Sez. 14, naposled přepsán Sez. 18).
# Sebeobsažný v sandbox/.
TEMPLATE_PATH = Path(__file__).parent / "template_classic.omap"

# ISOM kódy, které generátor produkuje. Objekty se na symboly odkazují přes id z template.
# Cesty: proc větev dělá 503/505; reálná (ZABAGED REST, Sez. 16) i 502/504/506. Voda (Sez. 17):
# toky 304/305/306 (liniové) + plocha 301.1 (plošný symbol — kombinovaný 301 s břehem je
# type 16, nepřiřaditelný objektu). Budovy (Sez. 18): plocha 521 (plošný symbol, type 4).
# Všechny musí být v template (čistá ISOM 2017-2 je obsahuje).
USED_CODES = ("101", "102", "103", "502", "503", "504", "505", "506",
              "304", "305", "306", "301.1", "521", "510", "509", "501", "109", "110", "111",
              "204", "206", "207",       # skály/balvany Sez. 30 (204 bod, 207 bod, 206 plocha)
              "512", "512.2")            # mosty/tunely/lávky Sez. 32 (512 linie, 512.2 bod)
# Rotatable symboly (orientaci nese objekt). 110 elipsa je rotatable; 109/111 pevně k severu.
# Skály: 204 Boulder je kruh (rotace nemá smysl), 207 Boulder cluster je trojúhelník
# orientovaný na sever (template: „symbol is orientated to north") → ani jeden nerotuje.
# 512.2 Footbridge je point_symbol rotatable=true (kolmá čárka přes vodu, rotace = úhel kolmý k toku).
ROTATABLE_CODES = frozenset({"110", "512.2"})

# Plošné (area) ISOM kódy generátoru — OOM vyplní plošný symbol JEN u uzavřeného path
# (poslední bod nese close flag). Liniové kódy (vrstevnice/cesty/vodní toky) zůstávají
# otevřené. Verify-against-source (Sez. 18): OOM po otevření flagless souboru sám doplnil
# na poslední bod ringu flag 18 → flagless plochy se nevyplnily.
# 206 Gigantic boulder = area_symbol (type=4 v template) → patří do AREA_CODES.
AREA_CODES = frozenset({"301.1", "521", "501", "206"})  # 206 Gigantic boulder Sez. 30
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
               out_path: str | Path,
               ortho_template: dict | None = None,
               ropik_features: list[tuple] | None = None,
               railway_features: list[tuple] | None = None,
               paved_features: list[tuple] | None = None,
               formline_features: list[tuple] | None = None,
               rock_point_features: list[tuple] | None = None,
               rock_area_features: list[tuple] | None = None,
               bridge_features: list[tuple] | None = None,
               tunnel_features: list[tuple] | None = None,
               footbridge_features: list[tuple] | None = None) -> dict:
    """Zapíše vrstevnice + cesty + vodu + budovy + el. vedení + železnice + body do `.omap` vložením do template.

    `contour_features` = [(line N×2 grid, code 101/102)], `path_features` =
    [(curve grid, code 502-506)] (proc dělá 503/505, reálná větev plnou hierarchii),
    `water_features` = [(line/ring grid, code 304/305/306/301.1)],
    `building_features` = [(ring grid, code 521)], `powerline_features` = [(line grid, code 510)]
    (liniový objekt, Sez. 24) — vše v souřadnicích MŘÍŽKY (gx∈0..gw-1, gy∈0..gh-1); voda i budovy
    jdou jako liniové objekty (type 1), OOM je vyplní podle typu symbolu (plošný 301/521).
    `railway_features` (volitelné, Sez. 28) = [(line grid, code 509)] — liniový objekt; 509 je
    v template kombinovaný symbol (čárky + bílý knockout), OOM ho vykreslí z definice symbolu.
    `paved_features` (volitelné, Sez. 28) = [(ring grid, code 501)] — plošný objekt (kolejiště);
    501 = kombinovaný symbol (hnědá výplň + OBRYSOVÁ linie), OOM vyplní uzavřený prstenec a
    nakreslí obrys (kolejiště = uzavřený prostor, bounding line významová — ne jako voda 301.1).
    `formline_features` (volitelné, Sez. 29) = [(line grid, code 103)] — pomocná vrstevnice,
    liniový objekt jako 101/102; OOM vykreslí čárkování z definice symbolu 103.
    `rock_point_features` (volitelné, Sez. 30) = [(gx, gy, code)] — bodové skály (204 Boulder,
    207 Boulder cluster); emit jako point_symbols, ale samostatný kanál (paralela s ropíky).
    `rock_area_features` (volitelné, Sez. 30) = [(ring grid, code 206)] — plošné skalní útvary
    (206 Gigantic boulder); uzavřený path s close flagem jako budova/voda (type=4 area symbol).
    `point_symbols` = [{symbol, gx, gy}] (ISOM 109/110/111). `scale` = jmenovatel měřítka.
    `ortho_template` (volitelné, Sez. 26) = {name, img_w, img_h, opacity} → připne obrázek
    `name` jako PODKLADOVÝ (background) template: paper-space, vycentrovaný na origin (jako
    objekty), scale = map-mm na pixel tak, aby obraz img_w×img_h přesně pokryl výsek.
    Návrat: {"contours", "paths", "water", "buildings", "powerlines", "railways", "rocks", "points", "objects"}.
    """
    out_path = Path(out_path)
    template_xml = TEMPLATE_PATH.read_text(encoding="utf-8")
    # sjednoť georef měřítko s generátorovým: template_classic.omap nese scale 15000, ale
    # generátor sází objekty v `scale` (MAP_SCALE=10000) → bez opravy by OOM měřil vzdálenosti
    # i mřížku 1,5× špatně (nález Sez. 26). Přepíšeme jediný <georeferencing scale="...">.
    template_xml = re.sub(r'(<georeferencing\b[^>]*\bscale=")\d+(")',
                          rf'\g<1>{int(scale)}\g<2>', template_xml, count=1)
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
    n_contours = n_paths = n_water = n_buildings = n_powerlines = n_railways = n_paved = n_points = n_ropiky = 0
    n_formlines = n_rocks = n_bridges = 0
    # Liniové objekty (vrstevnice/cesty/vodní toky) = otevřený path; plošné (301.1 voda,
    # 521 budova) = uzavřený path s close flagem (jinak OOM nevyplní — viz AREA_CODES).
    for line, code in contour_features:
        o = line_object(line, str(code))
        if o:
            objs.append(o); n_contours += 1
    # pomocné vrstevnice (103) = liniový objekt jako 101/102; OOM vykreslí čárkování z definice
    # symbolu (dash 2,0 / break 0,2 mm). Samostatný seznam → vlastní počet v meta (Sez. 29).
    for line, code in (formline_features or []):
        o = line_object(line, str(code))
        if o:
            objs.append(o); n_formlines += 1
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
    # železnice (509) = liniový objekt (otevřený path); OOM vykreslí kombinovaný symbol (Sez. 28)
    for line, code in (railway_features or []):
        o = line_object(line, str(code))
        if o:
            objs.append(o); n_railways += 1
    # zpevněné plochy / kolejiště (501 kombinovaný, výplň+obrys) = plošný objekt (uzavřený path
    # s close flagem); OOM vyplní area-část a nakreslí obrysovou linii (Sez. 28)
    for ring, code in (paved_features or []):
        o = area_object(ring, str(code))
        if o:
            objs.append(o); n_paved += 1
    # řopíky (Sez. 27): asset = budova 521 (plocha) + vrstevnice náspu 101 (linie). Geometrie už
    # natočená/umístěná generátorem; emise jako ostatní (521 area s close flagem, 101 line).
    for geom, code in (ropik_features or []):
        code = str(code)
        o = area_object(geom, code) if code in AREA_CODES else line_object(geom, code)
        if o:
            objs.append(o); n_ropiky += 1
    # bodové symboly extrémů = bodové objekty (type 0, 1 souřadnice); 110 rotatable → rotation
    for ps in point_symbols:
        code = str(ps["symbol"])
        x, y = paper(ps["gx"], ps["gy"])
        rot = ' rotation="0"' if code in ROTATABLE_CODES else ""
        objs.append(f'<object type="0" symbol="{sym[code]}"{rot}>'
                    f'<coords count="1">{x} {y};</coords></object>')
        n_points += 1
    # skály bodové (Sez. 30): 204 Boulder, 207 Boulder cluster = bodový objekt (type 0).
    # Bez rotation (204 je kruh, 207 orientace „k severu" template) → izomorfní s 109/111.
    for gx, gy, code in (rock_point_features or []):
        code = str(code)
        x, y = paper(gx, gy)
        objs.append(f'<object type="0" symbol="{sym[code]}">'
                    f'<coords count="1">{x} {y};</coords></object>')
        n_rocks += 1
    # skály plošné (Sez. 30): 206 Gigantic boulder = plný area s close flagem (jako 521).
    for geom, code in (rock_area_features or []):
        o = area_object(geom, str(code))
        if o:
            objs.append(o); n_rocks += 1
    # Mosty (Sez. 32 5. iterace dle uživatelova Most.omap dema): 1 ZABAGED Most linie
    # → 2 PARALELNÍ line objekty 512, posunuté kolmo o ±BRIDGE_PARALLEL_OFFSET_UM (=0,75 mm)
    # od centrální osy mostu. Uživatel ručně kreslí mosty takto v OOM — každá z 2 paralelních
    # 512 linií vykreslí 1 šikmou čárku na konci (template id=125 standardní); 4 čárky
    # dohromady tvoří hranatou závorku `[ ]` na obou koncích mostu (E2). Vzdálenost paralel
    # = 1,5 mm = vizuální tloušťka mostu (Most.omap demo).
    BRIDGE_PARALLEL_OFFSET_UM = 750     # = 0,75 mm offset od centrální osy → 1,5 mm rozestup
    for line, code in (bridge_features or []):
        center_coords_um = [paper(gx, gy) for gx, gy in line]
        if len(center_coords_um) < 2:
            continue
        # Spočti normálu v každém bodě (= průměr normál sousedních segmentů) a posuň o offset.
        # Per-bod kolmá normála = robustní i pro zakřivené mosty (multi-segment).
        for side in (+1, -1):
            offset_coords = []
            for i, (cx, cy) in enumerate(center_coords_um):
                if i == 0:
                    dx = center_coords_um[1][0] - cx
                    dy = center_coords_um[1][1] - cy
                elif i == len(center_coords_um) - 1:
                    dx = cx - center_coords_um[-2][0]
                    dy = cy - center_coords_um[-2][1]
                else:
                    dx1 = cx - center_coords_um[i - 1][0]
                    dy1 = cy - center_coords_um[i - 1][1]
                    dx2 = center_coords_um[i + 1][0] - cx
                    dy2 = center_coords_um[i + 1][1] - cy
                    dx = (dx1 + dx2) / 2
                    dy = (dy1 + dy2) / 2
                tlen = math.hypot(dx, dy) or 1.0
                # Normála kolmá k tangentě (vlevo)
                nx_perp, ny_perp = -dy / tlen, dx / tlen
                ox = cx + side * BRIDGE_PARALLEL_OFFSET_UM * nx_perp
                oy = cy + side * BRIDGE_PARALLEL_OFFSET_UM * ny_perp
                offset_coords.append((round(ox), round(oy)))
            coord_str = ";".join(f"{x} {y}" for x, y in offset_coords) + ";"
            objs.append(f'<object type="1" symbol="{sym[str(code)]}">'
                        f'<coords count="{len(offset_coords)}">{coord_str}</coords></object>')
            n_bridges += 1
    # Tunely (uživatel Sez. 32: „512 tunel je OK" s upraveným template id=125): emit 1
    # line objekt 512 přímo (jako bridge_features, ale BEZ paralelizace = jen 1 osa).
    # Template kreslí osu + 1 šikmou čárku na konci linie → tunel má symetrický vstup/výstup.
    # Cropping železnice tunelem zajišťuje E4 (railway nekreslí v úseku tunelu).
    for line, code in (tunnel_features or []):
        o = line_object(line, str(code))
        if o:
            objs.append(o); n_bridges += 1
    # Lávky (Sez. 32 zachováno): 512.2 Footbridge = bodový objekt (rotatable=true). Rotace
    # v RADIÁNECH (template ukládá v radiánech). Tuple (gx, gy, code, rot_rad).
    for gx, gy, code, rot in (footbridge_features or []):
        x, y = paper(gx, gy)
        objs.append(f'<object type="0" symbol="{sym[str(code)]}" rotation="{rot:.4f}">'
                    f'<coords count="1">{x} {y};</coords></object>')
        n_bridges += 1

    # vložení objektů do prázdného <objects count="0"> template (jediný výskyt — ověřeno)
    objects_open = f'<objects count="{len(objs)}">{"".join(objs)}'
    doc, n_sub = re.subn(r'<objects count="0">', objects_open, template_xml, count=1)
    if n_sub != 1:
        raise ValueError('Template nemá očekávaný prázdný <objects count="0"> blok')

    # ortofoto podklad (Sez. 26): vlož TemplateImage do dvou prázdných <templates count="0">
    # bloků čistého template — (a) definice v <map> (poloha+scale), (b) ref v <view> (opacity).
    # Formát ověřen proti reálnému OOM 0.9.6 výstupu (uživatel připnul ručně → odečten XML).
    # Jednotky: OOM template_to_map matice mapuje px → MAP-mm (objekty jsou v µm = 1/1000 mm),
    # proto scale_x = pw[µm]/1000/img_w. x=y=0: obraz vycentrovaný na origin jako objekty
    # (paper() centruje na (0,0)) → sedne bez translace. first_front_template="1" = pod mapou.
    if ortho_template is not None:
        iw, ih = ortho_template["img_w"], ortho_template["img_h"]
        name = ortho_template.get("name", "ortofoto.png")
        opacity = ortho_template.get("opacity", 0.5)
        sx = pw / 1000.0 / iw                       # map mm na pixel obrazu (E-W)
        sy = ph / 1000.0 / ih                       # map mm na pixel obrazu (S-J)
        tmpl = (
            f'<template type="TemplateImage" open="true" name="{name}" '
            f'path="{name}" relpath="{name}">'
            f'<transformations adjustment_dirty="true" passpoints="0">'
            f'<transformation role="active" x="0" y="0" '
            f'scale_x="{sx:.7g}" scale_y="{sy:.7g}" rotation="0"/>'
            f'<transformation role="other" x="0" y="0" scale_x="1" scale_y="1" rotation="0"/>'
            f'<matrix role="map_to_template" n="3" m="3">'
            f'<element value="{1.0 / sx:.7g}"/><element value="0"/><element value="0"/>'
            f'<element value="0"/><element value="{1.0 / sy:.7g}"/><element value="0"/>'
            f'<element value="0"/><element value="0"/><element value="1"/></matrix>'
            f'<matrix role="template_to_map" n="3" m="3">'
            f'<element value="{sx:.7g}"/><element value="0"/><element value="0"/>'
            f'<element value="0"/><element value="{sy:.7g}"/><element value="0"/>'
            f'<element value="0"/><element value="0"/><element value="1"/></matrix>'
            f'<matrix role="template_to_map_other" n="0" m="0"/></transformations></template>'
        )
        doc, n_def = re.subn(r'<templates count="0" first_front_template="0">',
                             f'<templates count="1" first_front_template="1">{tmpl}',
                             doc, count=1)
        doc, n_ref = re.subn(
            r'<templates count="0"/>',
            f'<templates count="1"><ref template="0" visible="true" opacity="{opacity:g}"/>'
            f'</templates>', doc, count=1)
        if n_def != 1 or n_ref != 1:
            raise ValueError(f"Template nemá očekávané prázdné <templates> bloky "
                             f"(definice={n_def}, view ref={n_ref})")

    out_path.write_text(doc, encoding="utf-8")
    return {"contours": n_contours, "formlines": n_formlines, "paths": n_paths, "water": n_water,
            "buildings": n_buildings, "powerlines": n_powerlines, "railways": n_railways,
            "paved": n_paved, "ropiky": n_ropiky, "rocks": n_rocks, "bridges": n_bridges,
            "points": n_points, "objects": len(objs)}
