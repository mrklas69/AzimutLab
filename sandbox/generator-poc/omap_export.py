"""omap_export.py — skládá výstup generátoru do OpenOrienteering Mapper (.omap) OD NULY.

Sezení 13: dřívější template-based přístup (vypůjčit cizí `.omap`, nahradit `<objects>`)
zahozen. Dědil bordel z cizích souborů — nestandardní symboly (101.1 „LIDAR contour",
503 „Minor road" místo ISOM Road), cizí podkladové obrázky s absolutními cestami — a
závisel na gitignored `resources/`. Teď skládáme VLASTNÍ čistou minimální ISOM 2017-2
sadu: jen symboly, které generátor produkuje. Sebeobsažné, deterministické, bez závislostí.

OMAP v9 struktura (ověřeno proti reálné mapě):
  <map version="9"> notes, georeferencing, colors,
    <barrier> symbols, parts(objects), templates, view </barrier>
  </map>

Georef: Local CRS (paper-space). Object coords jsou v µm na PAPÍŘE; 1 m terénu =
(1e6/scale) µm. Vycentrováno na (0,0). Osa y roste dolů = grid gy roste dolů → bez Y-flip
(stejná konvence jako contours.geojson a dřívější export).

NEduplikuje Pic2Omap `db2omap` (ten jde z rastru přes .pgw/cv2; my z přesných polylinií).
"""

from pathlib import Path

# ---------- Barvy (§5) — indexy do <colors>; ISOM Brown (výškopis) + Black (cesty) ----------
C_BROWN_IDX = 0
C_BLACK_IDX = 1

# ---------- Symbolová sada: ISOM kód → (symbol id v souboru, jméno) ----------
# id = pořadí v <symbols> (objekty se odkazují přes id, ne kód). Drží jen to, co
# generátor kreslí: vrstevnice (101/102), cesty (503/507), bodové extrémy (109/110/111).
# Kódy dle ISOM 2017-2 Rev 6 (109 Small knoll / 110 Small elongated knoll / 111 Small
# depression) — ověřeno proti oficiálnímu OOM symbol setu (Sez. 13).
SYMBOL_ID = {101: 0, 102: 1, 503: 2, 507: 3, 109: 4, 110: 5, 111: 6}

# Šířky čar / poloměry bodů v µm (1/1000 mm) na papíře — ISOM 2017-2 orientačně.
LW_CONTOUR = 140         # 101 základní vrstevnice (0,14 mm)
LW_INDEX = 250           # 102 zdůrazněná vrstevnice (silnější)
LW_ROAD = 300            # 503 Road (plná)
LW_PATH = 200            # 507 Less distinct small path (čárkovaná)
PT_RADIUS = 350          # poloměr bodového symbolu extrému (0,35 mm)


def _color_xml() -> str:
    """Dvě ISOM barvy: Brown (výškopis) a Black (cesty). RGB odvozeno z CMYK."""
    return (
        '<colors count="2">'
        '<color priority="0" name="Brown" c="0" m="0.56" y="1" k="0.18" opacity="1">'
        '<cmyk method="custom"/><rgb method="cmyk" r="0.82" g="0.361" b="0"/></color>'
        '<color priority="1" name="Black" c="0" m="0" y="0" k="1" opacity="1">'
        '<cmyk method="custom"/><rgb method="cmyk" r="0" g="0" b="0"/></color>'
        '</colors>'
    )


def _line_symbol(sid: int, code: str, name: str, color: int, width: int,
                 dashed: bool) -> str:
    """Definice liniového symbolu (type 2). `dashed` → čárkovaná (507), jinak plná."""
    dash = (
        'dashed="true" segment_length="4000" dash_length="2000" break_length="1600" '
        'dashes_in_group="2" in_group_break_length="510"'
        if dashed else
        'dashed="false" segment_length="0" dash_length="4000" break_length="1000" '
        'dashes_in_group="1" in_group_break_length="500"'
    )
    return (
        f'<symbol type="2" id="{sid}" code="{code}" name="{name}">'
        f'<line_symbol color="{color}" line_width="{width}" minimum_length="0" '
        f'join_style="2" cap_style="1" start_offset="0" end_offset="0" {dash} '
        f'show_at_least_one_symbol="true" minimum_mid_symbol_count="0" '
        f'minimum_mid_symbol_count_when_closed="0" mid_symbols_per_spot="1" '
        f'mid_symbol_distance="0"/></symbol>'
    )


def _point_symbol(sid: int, code: str, name: str, color: int, radius: int) -> str:
    """Definice bodového symbolu (type 1) jako plný kruh poloměru `radius` [µm].

    Zjednodušení (Sez. 13): 112/113/115 jsou prozatím stejný kruh. Věrná geometrie
    (113 elipsa, 115 oblouk „⌣") je rozšíření — v rastru rgb.png už správné tvary jsou.
    """
    return (
        f'<symbol type="1" id="{sid}" code="{code}" name="{name}">'
        f'<point_symbol inner_radius="{radius}" inner_color="{color}" '
        f'outer_width="0" outer_color="-1" elements="0"></point_symbol></symbol>'
    )


def _symbols_xml() -> str:
    """Celá <symbols> sekce — 7 symbolů, které generátor produkuje (ISOM 2017-2)."""
    syms = [
        _line_symbol(0, "101", "Contour", C_BROWN_IDX, LW_CONTOUR, dashed=False),
        _line_symbol(1, "102", "Index contour", C_BROWN_IDX, LW_INDEX, dashed=False),
        _line_symbol(2, "503", "Road", C_BLACK_IDX, LW_ROAD, dashed=False),
        _line_symbol(3, "507", "Less distinct small path", C_BLACK_IDX, LW_PATH, dashed=True),
        _point_symbol(4, "109", "Small knoll", C_BROWN_IDX, PT_RADIUS),
        _point_symbol(5, "110", "Small elongated knoll", C_BROWN_IDX, PT_RADIUS),
        _point_symbol(6, "111", "Small depression", C_BROWN_IDX, PT_RADIUS),
    ]
    return f'<symbols count="{len(syms)}" id="ISOM">{"".join(syms)}</symbols>'


def write_omap(contour_features: list[tuple], path_features: list[tuple],
               point_symbols: list[dict], gw: int, gh: int,
               world_w_m: float, world_h_m: float, scale: float,
               out_path: str | Path) -> dict:
    """Zapíše vrstevnice + cesty + body do `.omap` (vlastní ISOM sada). Vrací počty.

    `contour_features` = [(line N×2 grid, code 101/102)], `path_features` =
    [(curve grid, code 503/507)] — obojí v souřadnicích MŘÍŽKY (gx∈0..gw-1, gy∈0..gh-1).
    `point_symbols` = [{symbol, gx, gy}] (ISOM 112/113/115). `scale` = jmenovatel měřítka
    (10000). Návrat: {"contours", "paths", "points", "objects"}.
    """
    out_path = Path(out_path)
    # paper-space: 1 m terénu = (1e6/scale) µm papíru; výsek vycentrován na (0,0)
    um_per_m = 1_000_000.0 / scale
    pw = world_w_m * um_per_m
    ph = world_h_m * um_per_m

    def paper(gx: float, gy: float) -> tuple[int, int]:
        # grid → paper µm; bez Y-flip (gy roste dolů = paper y roste dolů)
        return (round((float(gx) / (gw - 1) - 0.5) * pw),
                round((float(gy) / (gh - 1) - 0.5) * ph))

    def path_object(points, code: str) -> str | None:
        coords = [paper(gx, gy) for gx, gy in points]
        if len(coords) < 2:
            return None
        coord_str = ";".join(f"{x} {y}" for x, y in coords) + ";"
        return (f'<object type="1" symbol="{SYMBOL_ID[code]}">'
                f'<coords count="{len(coords)}">{coord_str}</coords></object>')

    objs: list[str] = []
    n_contours = n_paths = n_points = 0
    # vrstevnice + cesty = liniové objekty (type 1)
    for line, code in contour_features:
        o = path_object(line, code)
        if o:
            objs.append(o); n_contours += 1
    for curve, code in path_features:
        o = path_object(curve, code)
        if o:
            objs.append(o); n_paths += 1
    # bodové symboly extrémů = bodové objekty (type 0, 1 souřadnice)
    for ps in point_symbols:
        x, y = paper(ps["gx"], ps["gy"])
        objs.append(f'<object type="0" symbol="{SYMBOL_ID[ps["symbol"]]}">'
                    f'<coords count="1">{x} {y};</coords></object>')
        n_points += 1

    parts = (f'<parts count="1" current="0"><part name="map">'
             f'<objects count="{len(objs)}">{"".join(objs)}</objects></part></parts>')
    view = ('<view><grid color="#80646464" display="0" alignment="0" '
            'additional_rotation="0" unit="1" h_spacing="10" v_spacing="10" h_offset="0" '
            'v_offset="0" snapping_enabled="true"/><map_view zoom="1" position_x="0" '
            'position_y="0"><map opacity="1" visible="true"/><templates count="0"/>'
            '</map_view></view>')
    templates = ('<templates count="0" first_front_template="0">'
                 '<defaults use_meters_per_pixel="true" meters_per_pixel="0" dpi="0" '
                 'scale="0"/></templates>')

    doc = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<map xmlns="http://openorienteering.org/apps/mapper/xml/v2" version="9">\n'
        '<notes></notes>\n'
        f'<georeferencing scale="{int(scale)}"></georeferencing>\n'
        f'{_color_xml()}\n'
        '<barrier version="6" required="0.6.0">\n'
        f'{_symbols_xml()}\n'
        f'{parts}\n'
        f'{templates}\n'
        f'{view}\n'
        '</barrier>\n'
        '</map>\n'
    )
    out_path.write_text(doc, encoding="utf-8")
    return {"contours": n_contours, "paths": n_paths, "points": n_points,
            "objects": len(objs)}
