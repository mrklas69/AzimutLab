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

Skládáme tedy jen <objects> (vrstevnice + cesty + voda + plochy + body + skály + mosty + landmarks
+ liniové/plošné pokryvy …); ÚPLNÝ výčet produkovaných ISOM kódů je `USED_CODES` níž (jediný zdroj
pravdy — nahradil dřívější taxativní seznam v docstringu, který zastarával po každé nové vrstvě).
Barvy/symboly/georef/view přebíráme z template beze změny. Symbol id parsujeme z template podle ISOM
kódu (robustní vůči re-uložení template v OOM — id NEjsou pořadová: 503→110, 505→112).

Georef: template má Local CRS (paper-space); jeho původní scale (1:15000) přepisujeme na
generátorové MAP_SCALE (1:10000, nález Sez. 26 — viz write_omap). Object coords jsou v µm na
PAPÍŘE; 1 m terénu = (1e6/scale) µm. Vycentrováno na (0,0), bez Y-flip (paper y i grid gy
rostou dolů — stejná konvence jako contours.geojson).

NEduplikuje Pic2Omap `db2omap` (ten jde z rastru přes .pgw/cv2; my z přesných polylinií).
"""

import math
import re
from pathlib import Path

# Čistý ISOM 2017-2 template (vyrobil uživatel v OOM: Sez. 14, přepsán Sez. 18; color-table
# rozšířena Sez. 54). Verzovaný vedle modulu v generator/ — je to FOUNDATION artefakt (symbol IDs,
# color-table s PRIORITAMI, georef), na němž stojí celý .omap export. NE generovaný kódem.
#
# !! K VÝROBĚ/REGENERACI NESTAČÍ uložit novou prázdnou mapu z OOM (File → New, ISOM 2017-2).
#    Template je ručně připravený a nese úpravy nad výchozí ISOM sadou (rozlišení Upper/Lower brown
#    50%, varianty symbolů 501.1 / 512.2, čistá <objects>/<templates>). Přesný postup výroby drží
#    uživatel (autor) — viz generator/README „template". Template needituj naslepo (jen s přesnými
#    kroky od uživatele, jako Sez. 54).
#
# PRŮLOM Sez. 54 (color-table priorita pro velkoplošnou base výplň): 501.1 „ostatní plocha v sídlech"
#    je první plošný symbol ležící POD velkým množstvím jiných ploch/linií/bodů (silnice, pěšiny,
#    budovy, body) přes celé sídlo. Default ISOM paleta NESTAČILA: 501.1 sdílel color „Upper brown 50%"
#    (11) se silnicemi a v color-table prioritě překrýval jejich černé okraje (14, pod 11) → silnice
#    mizely. Fix: přidána vlastní color „Dolní hnědá 50%" (priority 35 = ÚPLNĚ DOLE, pod silničními
#    okraji i pěšinami), 501.1 (id 106) přepojen 11→35. Lekce: base-layer plošný symbol potřebuje
#    VLASTNÍ color slot uspořádaný v prioritě pod vším, co přes něj leží — ne sdílet s nadřazeným.
TEMPLATE_PATH = Path(__file__).parent / "template_classic.omap"

# ISOM kódy, které generátor produkuje. Objekty se na symboly odkazují přes id z template.
# Cesty: proc větev dělá 503/505; reálná (ZABAGED REST, Sez. 16) i 502/504/506. Voda (Sez. 17):
# toky 304/305/306 (liniové) + plocha 301 (KOMBINOVANÝ: Blue 100% výplň + ČERNÁ břehová linie =
# neprůchodná hranice; Sez. 58 oprava z 301.1 bez okraje — mapaři kreslí vodní plochu s okrajem,
# rastr ho má od Sez. 18). „Combined nepřiřaditelný objektu" byl MYLNÝ předpoklad Sez. 18 —
# vyvrácen kolejištěm 501 (combined, Sez. 28). Budovy (Sez. 18): plocha 521 (plošný symbol, type 4).
# Všechny musí být v template (čistá ISOM 2017-2 je obsahuje).
USED_CODES = ("101", "102", "103", "502", "503", "504", "505", "506", "508",
              "304", "305", "306", "301", "521", "523", "510", "509", "501", "501.1", "109", "110", "111",
              "204", "206", "207", "208",  # skály/balvany Sez. 30+57 (204 bod, 207 bod, 206 plocha, 208 pole)
              "210.1",                   # Stony ground individual dot (type=1 point) — pseudo injekce bodů Sez. 107
              "512", "512.2",            # mosty/tunely/lávky Sez. 32 (512 linie, 512.2 bod)
              "401", "403", "520",       # plošný pokryv Sez. 41 (401 open land, 520 hřbitov/zákaz vstupu) + 403 rough open (separace Sez. 92)
              "412.1",                   # kultura Sez. 47 (pole = 401 + 412.1 černý pattern; sad/zahrada → 520, Sez. 49)
              "402", "402.1",            # park/okrasná zahrada + ostatní udržovaná zeleň Sez. 53 (402 bílé tečky, 402.1 zelené)
              "524", "526", "530", "417",  # bodové orient. prvky Sez. 43 (524 věž / 526 mohyla / 530 Prominent man-made feature [zdroj kříž] / 417 strom)
              "104", "107", "513", "516",  # liniové orient. prvky Sez. 43+58 (sráz/rokle 107/zeď) + plot 516 (Sez. 98)
              "519",                     # prostupy Sez. 52 (zábrana na zdi → Crossing point, rotatable bod)
              "312", "311", "203.2",     # bodové vodní/terénní Sez. 44 (pramen/nádrž/jeskyně)
              "308", "310", "406",       # mokřady Sez. 44 (308 Marsh) + 310 Indistinct (pseudo Sez. 99) + stromořadí Sez. 45 (406)
              "408", "410")              # věk porostu Sez. 62 (406/408/410 zeleň z AOPK porostních skupin, PROXY)
# 523 Ruin (Sez. 43): zřícenina jde v building_features jako uzavřený area_object se symbolem 523
# (line_symbol dashed v template) → OOM nakreslí čárkovaný obrys po obvodu (bez výplně; 523 nemá
# area component, proto NENÍ v AREA_CODES — close flag jen uzavře geometrii).
# Rotatable symboly (orientaci nese objekt). 110 elipsa je rotatable; 109/111 pevně k severu.
# Skály: 204 Boulder je kruh (rotace nemá smysl), 207 Boulder cluster je trojúhelník
# orientovaný na sever (template: „symbol is orientated to north") → ani jeden nerotuje.
# 512.2 Footbridge je point_symbol rotatable=true (kolmá čárka přes vodu, rotace = úhel kolmý k toku).
# 519 Crossing point je point_symbol rotatable=true (2 čárky „brány", rotace = úhel tangenty zdi, Sez. 52).
ROTATABLE_CODES = frozenset({"110", "512.2", "519"})

# Plošné (area) ISOM kódy generátoru — OOM vyplní plošný symbol JEN u uzavřeného path
# (poslední bod nese close flag). Liniové kódy (vrstevnice/cesty/vodní toky) zůstávají
# otevřené. Verify-against-source (Sez. 18): OOM po otevření flagless souboru sám doplnil
# na poslední bod ringu flag 18 → flagless plochy se nevyplnily.
# 206 Gigantic boulder + 208 Boulder field = area_symbol (type=4 v template) → patří do AREA_CODES.
AREA_CODES = frozenset({"301", "521", "501", "501.1", "206", "208", "401", "403", "402", "402.1", "520", "308", "310", "406", "408", "410", "412.1"})  # 301 combined voda Sez. 58 (z 301.1, přidán břeh); 206 Sez. 30; 401/520 pokryv Sez. 41; 308 mokřad Sez. 44 + 310 Indistinct pseudo Sez. 99; 406 stromořadí Sez. 45; 412.1 pole Sez. 47; 402/402.1 park/zeleň Sez. 53; 501.1 ostatní plocha v sídlech Sez. 54; 208 pole balvanů Sez. 57; 408/410 věk porostu Sez. 62 (zeleň PROXY); 403 rough open Sez. 92 (separace)
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


def _image_template_element(name: str, sx: float, sy: float) -> str:
    """Jeden OOM <template type="TemplateImage"> element (definice v <map>).

    Obraz vycentrovaný na origin (x=y=0, jako objekty paper()), scale_x/y = map-mm na pixel obrazu →
    img_w×img_h přesně pokryje výsek. Formát ověřen proti reálnému OOM 0.9.6 (uživatel připnul ručně →
    odečten XML, Sez. 26). Sdílí ortho_template (write_omap) i podkladové backgrounds (gen_backgrounds.py,
    Sez. 104) — DRY, 2. konzument = důkaz pro extrakci."""
    return (
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


def inject_image_templates(doc: str, templates: list[dict]) -> str:
    """Vloží N PODKLADOVÝCH (background) image templates do .omap s prázdnými <templates count="0"> bloky.

    templates = [{name, sx, sy, opacity}] (pořadí = z-order definice; všechny POD mapou). Dva prázdné
    bloky čistého template / gen .omap: (a) definice v <map> (count + first_front_template = N → všechny
    pod mapou), (b) ref ve <view> (count + N <ref> s opacitou). Vrací upravený doc; [] = beze změny.
    Raise když bloky nesedí (ochrana proti tichému no-op). Formát viz `_image_template_element`."""
    if not templates:
        return doc
    n = len(templates)
    defs = "".join(_image_template_element(t["name"], t["sx"], t["sy"]) for t in templates)
    refs = "".join(f'<ref template="{i}" visible="true" opacity="{t.get("opacity", 0.5):g}"/>'
                   for i, t in enumerate(templates))
    doc, n_def = re.subn(r'<templates count="0" first_front_template="0">',
                         f'<templates count="{n}" first_front_template="{n}">{defs}', doc, count=1)
    doc, n_ref = re.subn(r'<templates count="0"/>',
                         f'<templates count="{n}">{refs}</templates>', doc, count=1)
    if n_def != 1 or n_ref != 1:
        raise ValueError(f"Template nemá očekávané prázdné <templates> bloky "
                         f"(definice={n_def}, view ref={n_ref})")
    return doc


def write_omap(contour_features: list[tuple], path_features: list[tuple],
               point_symbols: list[dict], water_features: list[tuple],
               building_features: list[tuple], powerline_features: list[tuple],
               gw: int, gh: int,
               world_w_m: float, world_h_m: float, scale: float,
               out_path: str | Path,
               ortho_template: dict | None = None,
               ropik_features: list[tuple] | None = None,
               railway_features: list[tuple] | None = None,
               ride_features: list[tuple] | None = None,
               paved_features: list[tuple] | None = None,
               formline_features: list[tuple] | None = None,
               rock_point_features: list[tuple] | None = None,
               rock_area_features: list[tuple] | None = None,
               bridge_features: list[tuple] | None = None,
               tunnel_features: list[tuple] | None = None,
               footbridge_features: list[tuple] | None = None,
               surface_features: list[tuple] | None = None,
               landmark_features: list[tuple] | None = None,
               linefeature_features: list[tuple] | None = None,
               marsh_features: list[tuple] | None = None,
               treerow_features: list[tuple] | None = None,
               veg_area_features: list[tuple] | None = None,
               barrier_features: list[tuple] | None = None) -> dict:
    """Zapíše vrstevnice + cesty + vodu + budovy + el. vedení + železnice + body do `.omap` vložením do template.

    `contour_features` = [(line N×2 grid, code 101/102)], `path_features` =
    [(curve grid, code 502-506)] (proc dělá 503/505, reálná větev plnou hierarchii),
    `water_features` = [(line/ring grid, code 304/305/306/301)],
    `building_features` = [(ring grid, code 521)], `powerline_features` = [(line grid, code 510)]
    (liniový objekt, Sez. 24) — vše v souřadnicích MŘÍŽKY (gx∈0..gw-1, gy∈0..gh-1); voda i budovy
    jdou jako liniové objekty (type 1), OOM je vyplní podle typu symbolu (plošný 301/521).
    `railway_features` (volitelné, Sez. 28) = [(line grid, code 509)] — liniový objekt; 509 je
    v template kombinovaný symbol (čárky + bílý knockout), OOM ho vykreslí z definice symbolu.
    `paved_features` (volitelné, Sez. 28) = [(ring grid, code 501)] — plošný objekt (kolejiště);
    501 = kombinovaný symbol (hnědá výplň + OBRYSOVÁ linie), OOM vyplní uzavřený prstenec a
    nakreslí obrys (kolejiště = uzavřený prostor, bounding line významová — jako voda 301 od Sez. 58).
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

    def area_object(rings, code: str) -> str | None:
        """Plošný objekt (ISOM area symbol): uzavřený path s close flagem na posledním bodě.
        OOM vyplní area symbol jen u UZAVŘENÉHO path — flagless by zůstal jen obrysem/se
        nevykreslil. Flag uzavře poslední bod zpět na první (ZABAGED ring má first==last).

        `rings` = [vnější, díra1, …] (Sez. 54). Více prstenů (díry/výřezy) jde do JEDNOHO objektu:
        prsteny zřetězené, hranice mezi nimi nese `OOM_CLOSE_FLAG` (18 = 16 hole point + 2 close).
        Flag 16 značí „následuje další prsten" → OOM vykrojí vnitřní prsteny even-odd pravidlem.
        **POSLEDNÍ prsten končí jen close (2), BEZ hole bitu** — konvence z reálných OB map
        (verify-against-source: SampleMap/Blatná mají hole-bit jen na hranicích, ne na úplném konci).
        Jednoprstencový objekt (drtivá většina ploch) zachovává close+hole 18 jako dřív (OOM toleruje;
        precedent reálná Soví vrch.omap) → 0 regrese."""
        valid = [r for r in rings if len(r) >= 3]
        if not valid:
            return None
        parts: list[str] = []
        total = 0
        last = len(valid) - 1
        for ri, ring in enumerate(valid):
            coords = [paper(gx, gy) for gx, gy in ring]
            rp = [f"{x} {y}" for x, y in coords]
            if ri == last and last > 0:                 # poslední z VÍCE prstenů → jen close (2), bez hole bitu
                rp[-1] += " 2"
            else:                                       # vnitřní hranice / jediný prsten → close+hole (18)
                rp[-1] += f" {OOM_CLOSE_FLAG}"
            parts.extend(rp)
            total += len(coords)
        coord_str = ";".join(parts) + ";"
        return (f'<object type="1" symbol="{sym[code]}">'
                f'<coords count="{total}">{coord_str}</coords></object>')

    objs: list[str] = []
    n_contours = n_paths = n_water = n_buildings = n_powerlines = n_railways = n_paved = n_points = n_ropiky = 0
    n_formlines = n_rocks = n_bridges = n_rides = n_surfaces = n_landmarks = n_linefeatures = n_marsh = n_treerows = 0
    n_barriers = n_veg_area = 0
    # Liniové objekty (vrstevnice/cesty/vodní toky) = otevřený path; plošné (301 voda,
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
    # budovy (521 plná) + zříceniny (523 čárkovaný obrys, Sez. 43) = uzavřený area_object;
    # OOM vykreslí 521 plnou výplň / 523 dashed obrys ze symbolu (oba close-flag uzavřou ring)
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
    # lesní průseky (508) = liniový objekt (otevřený path); OOM vykreslí čárkování z definice
    # symbolu (dash 3,0 / break 0,375 mm). Bez runnability pozadí (Sez. 36)
    for line, code in (ride_features or []):
        o = line_object(line, str(code))
        if o:
            objs.append(o); n_rides += 1
    # zpevněné plochy / kolejiště (501 kombinovaný, výplň+obrys) = plošný objekt (uzavřený path
    # s close flagem); OOM vyplní area-část a nakreslí obrysovou linii (Sez. 28)
    for ring, code in (paved_features or []):
        o = area_object(ring, str(code))
        if o:
            objs.append(o); n_paved += 1
    # plošný pokryv (401 open land / 520 zákaz vstupu / 412 pole / 402 park / 402.1 ostatní zeleň) =
    # plošný objekt (uzavřený path s close flagem). 401/520/402/402.1 = JEDEN area objekt (OOM vyplní
    # ze symbolu — 402/402.1 jsou v template samostatné combined area symboly žlutá+tečky). Pole 412 je
    # v template type 16 combined (= 401 žlutá + 412.1 černý pattern), nepřiřaditelné objektu jako voda
    # 301 → rozbal na DVA objekty 401 + 412.1 (precedent most 1→2). Z-order řeší priorita barev. Sez. 41/47/53.
    for ring, code in (surface_features or []):
        code = str(code)
        emit = ("401", "412.1") if code == "412" else (code,)
        for c in emit:
            o = area_object(ring, c)
            if o:
                objs.append(o); n_surfaces += 1
    # mokřady (Sez. 44): 308 Marsh / 310 Indistinct (pseudo Sez. 99) = plošný objekt (uzavřený path
    # s close flagem; OOM vykreslí modrý pattern z definice symbolu — 308 plné čáry, 310 tečkovaný).
    for ring, code in (marsh_features or []):
        o = area_object(ring, str(code))
        if o:
            objs.append(o); n_marsh += 1
    # stromořadí / lineární les (Sez. 45): 406 Vegetation: slow running = plošný objekt (uzavřený
    # path s close flagem; OOM vyplní světle zelenou z definice symbolu). Prstenec = buffrovaný pás.
    for ring, code in (treerow_features or []):
        o = area_object(ring, str(code))
        if o:
            objs.append(o); n_treerows += 1
    # plošná predikční zeleň/open → 406 slow / 408 walk / 410 fight / 403 rough open = plošný objekt
    # (uzavřený path s close flagem; OOM vyplní barvu z definice symbolu). Zdroj = separace reálné mapy
    # (predict, Sez. 82/92; forest-age proxy archiv Sez. 102) — značeno v meta provenance.
    for ring, code in (veg_area_features or []):
        o = area_object(ring, str(code))
        if o:
            objs.append(o); n_veg_area += 1
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
    # bodové orientační prvky (Sez. 43): 524 věž / 526 mohyla / 530 kříž / 417 strom = bodový
    # objekt (type 0). Orientace k severu (template) → bez rotation (jako 109/111, skály).
    for gx, gy, code in (landmark_features or []):
        code = str(code)
        x, y = paper(gx, gy)
        objs.append(f'<object type="0" symbol="{sym[code]}">'
                    f'<coords count="1">{x} {y};</coords></object>')
        n_landmarks += 1
    # liniové orientační prvky (Sez. 43): 104 sráz / 513 zeď = liniový objekt (otevřený path);
    # OOM vykreslí symbol z definice (104 ticky, 513 plná). Stromořadí 406 jde plošně (výš, Sez. 45).
    for line, code in (linefeature_features or []):
        o = line_object(line, str(code))
        if o:
            objs.append(o); n_linefeatures += 1
    # Mosty (verify Most.png/Most.omap demo, Sez. 33): 1 ZABAGED Most linie → 2 PARALELNÍ
    # line objekty 512 lemující osu po stranách (rozestup 2 × BRIDGE_PARALLEL_OFFSET_UM).
    # Tunely (Sez. 33) se kreslí JINAK — 512 otočené o 90° na obou koncích = vjezdy (níže).
    BRIDGE_PARALLEL_OFFSET_UM = 750     # = 0,75 mm offset od centrální osy → 1,5 mm rozestup
    TUNNEL_PORTAL_HALF_UM = 750         # = 0,75 mm → kolmá závorka vjezdu tunelu dlouhá 1,5 mm

    def _offset_polyline_left(coords_um: list[tuple[int, int]],
                              offset_um: int) -> list[tuple[int, int]]:
        """Posune polyline o offset_um v levé normále k lokální tangenze (per-bod).
        Záporný offset_um → pravá normála."""
        if len(coords_um) < 2:
            return list(coords_um)
        out: list[tuple[int, int]] = []
        for i, (cx, cy) in enumerate(coords_um):
            if i == 0:
                dx = coords_um[1][0] - cx
                dy = coords_um[1][1] - cy
            elif i == len(coords_um) - 1:
                dx = cx - coords_um[-2][0]
                dy = cy - coords_um[-2][1]
            else:
                dx1 = cx - coords_um[i - 1][0]
                dy1 = cy - coords_um[i - 1][1]
                dx2 = coords_um[i + 1][0] - cx
                dy2 = coords_um[i + 1][1] - cy
                dx = (dx1 + dx2) / 2
                dy = (dy1 + dy2) / 2
            tlen = math.hypot(dx, dy) or 1.0
            # Levá normála ke (lokální) tangentě
            nx_perp, ny_perp = -dy / tlen, dx / tlen
            ox = cx + offset_um * nx_perp
            oy = cy + offset_um * ny_perp
            out.append((round(ox), round(oy)))
        return out

    def _bridge_parallels(center_coords_um: list[tuple[int, int]]
                          ) -> tuple[list, list]:
        """2 paralelní 512 linie lemující osu MOSTU, obě s nožičkami VEN od osy.
        Klíč (verify Most.png demo, Sez. 33): jedna linie reverzovaná (opačná tangenta) +
        offset na PRAVOU normálu (záporný). Tím start/end_symbol OOM vykreslí šikmé čárky
        symetricky ven na obě strany. Sez. 32 měla offset na levou (kladný) → nožičky
        dovnitř (= demo má levá strana osy reversed/pravá forward, kód to měl obráceně)."""
        off = -BRIDGE_PARALLEL_OFFSET_UM
        line_a = _offset_polyline_left(list(reversed(center_coords_um)), off)
        line_b = _offset_polyline_left(center_coords_um, off)
        return (line_a, line_b)

    def _tunnel_portals(center_coords_um: list[tuple[int, int]]) -> list[list]:
        """Tunel (uživatel Sez. 33): 512 se NEdělá jako paralely mostu, ale OTOČENÉ o 90°
        na OBOU koncích osy = vjezdy (vstup/výstup tunelu). Pro každý konec krátká 512 linie
        KOLMÁ k tangentě osy, centrovaná na koncovém bodě (délka 2× TUNNEL_PORTAL_HALF_UM)."""
        if len(center_coords_um) < 2:
            return []
        portals: list[list] = []
        for p_end, p_in in ((center_coords_um[0], center_coords_um[1]),
                            (center_coords_um[-1], center_coords_um[-2])):
            tx, ty = p_in[0] - p_end[0], p_in[1] - p_end[1]
            tlen = math.hypot(tx, ty) or 1.0
            nx, ny = -ty / tlen, tx / tlen                  # kolmice k ose tunelu
            a = (round(p_end[0] + nx * TUNNEL_PORTAL_HALF_UM),
                 round(p_end[1] + ny * TUNNEL_PORTAL_HALF_UM))
            b = (round(p_end[0] - nx * TUNNEL_PORTAL_HALF_UM),
                 round(p_end[1] - ny * TUNNEL_PORTAL_HALF_UM))
            portals.append([a, b])
        return portals

    def _emit_512_line(coords_um: list[tuple[int, int]], code) -> None:
        coord_str = ";".join(f"{x} {y}" for x, y in coords_um) + ";"
        objs.append(f'<object type="1" symbol="{sym[str(code)]}">'
                    f'<coords count="{len(coords_um)}">{coord_str}</coords></object>')

    # Most = 2 paralely podél osy; tunel = 2 kolmé závorky na vjezdech (otočené o 90°).
    for line, code in (bridge_features or []):
        center_coords_um = [paper(gx, gy) for gx, gy in line]
        if len(center_coords_um) < 2:
            continue
        for parallel in _bridge_parallels(center_coords_um):
            _emit_512_line(parallel, code)
            n_bridges += 1
    for line, code in (tunnel_features or []):
        center_coords_um = [paper(gx, gy) for gx, gy in line]
        if len(center_coords_um) < 2:
            continue
        for portal in _tunnel_portals(center_coords_um):
            _emit_512_line(portal, code)
            n_bridges += 1
    # Lávky (Sez. 32 zachováno): 512.2 Footbridge = bodový objekt (rotatable=true). Rotace
    # v RADIÁNECH (template ukládá v radiánech). Tuple (gx, gy, code, rot_rad).
    for gx, gy, code, rot in (footbridge_features or []):
        x, y = paper(gx, gy)
        objs.append(f'<object type="0" symbol="{sym[str(code)]}" rotation="{rot:.4f}">'
                    f'<coords count="1">{x} {y};</coords></object>')
        n_bridges += 1
    # Prostupy (Sez. 52): 519 Crossing point = bodový objekt (rotatable=true, jako lávka). Rotace
    # v RADIÁNECH = úhel tangenty nosné zdi. Tuple (gx, gy, code, rot_rad).
    for gx, gy, code, rot in (barrier_features or []):
        x, y = paper(gx, gy)
        objs.append(f'<object type="0" symbol="{sym[str(code)]}" rotation="{rot:.4f}">'
                    f'<coords count="1">{x} {y};</coords></object>')
        n_barriers += 1

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
        sx = pw / 1000.0 / iw                       # map mm na pixel obrazu (E-W)
        sy = ph / 1000.0 / ih                       # map mm na pixel obrazu (S-J)
        doc = inject_image_templates(doc, [{                # sdílený helper (Sez. 104 extrakce)
            "name": ortho_template.get("name", "ortofoto.png"),
            "sx": sx, "sy": sy, "opacity": ortho_template.get("opacity", 0.5)}])

    out_path.write_text(doc, encoding="utf-8")
    return {"contours": n_contours, "formlines": n_formlines, "paths": n_paths, "rides": n_rides,
            "water": n_water, "buildings": n_buildings, "powerlines": n_powerlines,
            "railways": n_railways, "paved": n_paved, "ropiky": n_ropiky, "rocks": n_rocks,
            "bridges": n_bridges, "surfaces": n_surfaces, "landmarks": n_landmarks,
            "linefeatures": n_linefeatures, "marsh": n_marsh, "treerows": n_treerows,
            "veg_area": n_veg_area, "barriers": n_barriers,
            "points": n_points, "objects": len(objs)}
