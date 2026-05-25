"""
omap_export.py — zápis vrstevnic generátoru do OpenOrienteering Mapper (.omap).

Přístup (Sez. 8): TEMPLATE-BASED, stejně jako Pic2Omap `db2omap` — vezmeme funkční
`.omap` (víme, že se v OOM otevírá) a nahradíme jen sekci `<objects>` našimi
vrstevnicemi. Tím se nemusí od nuly skládat přísný OMAP obal (colors / symbols /
georeferencing / parts / view) — to vše zdědíme z template, který je ověřeně validní.

Proč ne Pic2Omap kód napřímo: `db2omap` jde z RASTRU (pixel → coord přes .pgw,
cv2, hrubá vektorizace). My máme vrstevnice rovnou jako přesné polylinie z contourpy
→ úplně jiný (jednodušší) vstup. Sdílíme jen FORMÁT (OMAP XML), ne kód. Žádná
duplikace logiky Pic2Omapu (CLAUDE.md: sourozenec, neduplikovat).

Georef: Local CRS (paper-space). OMAP object coords jsou v 1/1000 mm = µm na PAPÍŘE
mapy. Při měřítku 1:M je 1 m terénu = (1e6 / M) µm papíru (pro 1:10000 → 100 µm).
Souřadnice vycentrujeme na (0,0). Osa y v paper-space roste DOLŮ — stejně jako naše
souřadnice mřížky (gy=0 = horní řádek = sever), takže žádný extra Y-flip není potřeba
(ověřeno proti konvenci Pic2Omap db2omap: pixel 0 nahoře → nejmenší map_y).
"""

import re
from pathlib import Path


def _symbol_id_for_code(template: str, code: str) -> str:
    """Najde v template OMAP id symbolu pro daný ISOM `code` (např. "101").

    Objekty v OMAP se odkazují na symbol přes jeho ID (atribut `id`), NE přes ISOM
    `code`. Mapování id↔code se liší template od template (forest sample: 101→0,
    102→1), proto ho čteme ze souboru, nehardcodujeme. Pattern matchne i `.0` suffix
    konvenci (`101.0`), kterou některé knihovny používají.
    """
    # \b za code, ať "101" nematchne "1010"; (?:\.\d+)? povolí "101.0"
    m = re.search(rf'<symbol\b[^>]*\bid="(\d+)"[^>]*\bcode="{code}(?:\.\d+)?"', template)
    if m is None:
        raise RuntimeError(
            f"Template nemá symbol s ISOM code={code!r}. Použij OMAP s ISOM "
            f"contour symboly (101 Contour, 102 Index contour)."
        )
    return m.group(1)


def _scale_from_template(template: str) -> float:
    """Vytáhne měřítko z `<georeferencing scale="...">` (default 10000)."""
    m = re.search(r'<georeferencing\b[^>]*\bscale="([\d.]+)"', template)
    return float(m.group(1)) if m else 10000.0


def write_omap(features: list[tuple], gw: int, gh: int,
               world_w_m: float, world_h_m: float,
               template_path: str | Path, out_path: str | Path) -> int:
    """Zapíše vrstevnice do `.omap` přes template. Vrací počet zapsaných objektů.

    `features` = seznam (line, code), kde `line` je pole bodů (N×2) v souřadnicích
    MŘÍŽKY (gx∈0..gw-1, gy∈0..gh-1) a `code` je ISOM kód (101 / 102) — tentýž vstup,
    jaký sbírá generator.py pro GeoJSON. `world_w_m`/`world_h_m` = reálné rozměry
    výseku v metrech (kvůli paper-space měřítku).
    """
    template_path = Path(template_path)
    out_path = Path(out_path)
    tpl = template_path.read_text(encoding="utf-8")

    # template musí mít <objects>...</objects>, kterou nahradíme (re.S → . matchne i \n)
    if not re.search(r"<objects\b[^>]*>.*?</objects>", tpl, re.S):
        raise RuntimeError(f"Template {template_path} nemá <objects> sekci k nahrazení.")

    scale = _scale_from_template(tpl)
    sid = {101: _symbol_id_for_code(tpl, "101"), 102: _symbol_id_for_code(tpl, "102")}

    # paper-space rozměry výseku v µm: 1 m terénu = (1e6 / scale) µm papíru
    um_per_m = 1_000_000.0 / scale
    pw = world_w_m * um_per_m
    ph = world_h_m * um_per_m

    objs: list[str] = []
    for line, code in features:
        # mřížka → paper µm, vycentrované na (0,0). Bez extra Y-flip (gy roste dolů
        # = paper y roste dolů). round na celé µm (OMAP coords jsou celá čísla).
        coords = [
            (round((float(gx) / (gw - 1) - 0.5) * pw),
             round((float(gy) / (gh - 1) - 0.5) * ph))
            for gx, gy in line
        ]
        if len(coords) < 2:        # degenerátní linie přeskoč
            continue
        coord_str = ";".join(f"{x} {y}" for x, y in coords) + ";"
        objs.append(
            f'<object type="1" symbol="{sid[code]}">'
            f'<coords count="{len(coords)}">{coord_str}</coords></object>'
        )

    new_objects = f'<objects count="{len(objs)}">{"".join(objs)}</objects>'
    # nahraď PRVNÍ <objects>...</objects> (template má jednu mapovou část)
    out = re.sub(r"<objects\b[^>]*>.*?</objects>", new_objects, tpl, count=1, flags=re.S)
    out_path.write_text(out, encoding="utf-8")
    return len(objs)
