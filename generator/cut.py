"""cut.py — ořez gen výstupu (.omap + render) na reálné mapové pole (natočený quad / osový box).

generate_map kreslí grid-north-up na axis-aligned bbox; reálná mapa je natočený quad (~2× užší kvůli
grivaci). Přesahové rohy bboxu obsahují okolní sídla (Stráž n. Nisou u Bedřichovky) s kompletní ČÚZK
infrastrukturou (ulice/budovy), kterou závodní OB mapa nepokrývá → výsledná gen.omap je nečistá jako
produkt a tréninkové páry učí reconstructor hustou uliční síť mimo cílovou doménu. Ořez = vynech
objekty s CENTROIDEM mimo quad + maska renderu na bílou (Sez. 109, zadání uživatele).

PLÁN sjednocení (Sez. 113, schváleno uživatelem — DRY, zatím NEimplementováno; viz TODO bod ořez):
geometrická primitiva `cut_line` (reuse generator `_split_by_zones_interp`) / `cut_area` (Sutherland-Hodgman) /
`cut_point` (`_point_in_quad`) → JEDEN orchestrátor `clip_omap(.omap, clip_poly)` (přepíše `<coords>`, ne jen
maže bloky) → wrappery `cut_box` (4 rohy papíru, CLI `--location`) + `clip_omap_to_quad` (Livelox quad). Tím
clip_quad povýší z centroidu na geometrický (přesný řez dlouhých linií — „Nisa do Vesce", Sez. 113 Novina).

Centroid (KISS, hrubé na hranici — dlouhá linie protínající hranici se ponechá/zahodí dle středu);
geometrický ořez na hranici quadu = výše uvedený PLÁN (důkaz vady doložen Sez. 113: Novina přesah ~20 km).

`.omap` se upravuje STRING manipulací (regex odstranění `<object>` bloků), NE ET round-tripem — ten
přeformátuje celý dokument a rozbije jak string-based `inject_image_templates` (podklady), tak riskuje
OOM kompatibilitu. Mirror přístupu `omap_export`/`gen_backgrounds` (string template fill / regex inject).

Post-process (mimo monolit generate_map, fáze B): volá orchestrátor (measure_dod/pairs) se znalostí quadu.
"""
import json
import pathlib
import re

import numpy as np
from PIL import Image, ImageDraw

from omap_raster import _paper_to_px

Image.MAX_IMAGE_PIXELS = None
_OBJ_RE = re.compile(r"<object\b.*?</object>", re.DOTALL)       # párový objekt (s coords); self-closing nematchne → ponechán
_COORDS_RE = re.compile(r"<coords[^>]*>(.*?)</coords>", re.DOTALL)


def _pgw(path: pathlib.Path):
    """.pgw world-file (řádky A,D,B,E,C,F) → (A,B,C,D,E,F): x=A·col+B·row+C, y=D·col+E·row+F."""
    A, D, B, E, C, F = [float(x) for x in pathlib.Path(path).read_text().split()]
    return A, B, C, D, E, F


def _quad_to_genpx(quad_sjtsk: list, rgb_pgw: pathlib.Path) -> list:
    """4 rohy quadu v S-JTSK → gen px (inverz rgb.pgw afinní)."""
    gA, gB, gC, gD, gE, gF = _pgw(rgb_pgw)
    gdet = gA * gE - gB * gD
    out = []
    for x, y in quad_sjtsk:
        col = (gE * (x - gC) - gB * (y - gF)) / gdet
        row = (-gD * (x - gC) + gA * (y - gF)) / gdet
        out.append((col, row))
    return out


def _point_in_quad(x: float, y: float, poly: list) -> bool:
    """Point-in-polygon (ray-casting / crossing number) — nahradil matplotlib.path.contains_point.

    matplotlib je trénink-only závislost (requirements.txt: křivky učení, jen mrkla); clip_quad
    běží v produkční separační cestě (ntbhej). Pro test centroidu objektu vůči 4 rohům quadu stačí
    pár řádků numpy-free crossing-number (Sez. 112). `poly` = list (col,row); libovolný jednoduchý polygon."""
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def clip_omap_to_quad(gen_dir: str | pathlib.Path, name: str, quad_sjtsk: list) -> tuple:
    """Ořež `<name>.omap` + `rgb.png` na natočený reálný quad (4 rohy S-JTSK). Vrací (kept, removed).

    .omap objekt s centroidem (průměr coords, paper µm → gen px) mimo quad → odstraněn (string regex,
    formát zachován). Render mimo quad → bílá. Zachovává <symbols>/<templates> i jejich formát."""
    gen_dir = pathlib.Path(gen_dir)
    omap_p = gen_dir / f"{name}.omap"
    meta = json.load(open(gen_dir / "meta.json", encoding="utf-8"))
    to_px, W, H = _paper_to_px(meta)
    quad_px = _quad_to_genpx(quad_sjtsk, gen_dir / "rgb.pgw")

    # --- ořez .omap objektů dle centroidu (string regex) ---
    doc = omap_p.read_text(encoding="utf-8")
    stats = {"kept": 0, "removed": 0}

    def _filter(m: re.Match) -> str:
        block = m.group(0)
        cm = _COORDS_RE.search(block)
        if cm is None:
            stats["kept"] += 1
            return block                                  # objekt bez coords → ponech
        xs, ys = [], []
        for tok in cm.group(1).strip().split(";"):
            nums = tok.split()
            if len(nums) >= 2:
                try:
                    xs.append(int(nums[0])); ys.append(int(nums[1]))
                except ValueError:
                    pass
        if not xs:
            stats["kept"] += 1
            return block
        col, row = to_px(sum(xs) / len(xs), sum(ys) / len(ys))   # paper-µm centroid → gen px
        if _point_in_quad(col, row, quad_px):
            stats["kept"] += 1
            return block
        stats["removed"] += 1
        return ""                                          # mimo quad → odstraň blok

    doc = _OBJ_RE.sub(_filter, doc)
    # aktualizuj <objects count="N"> (gen.omap má 1 objects blok; OOM jinak varuje na nesoulad počtu)
    doc = re.sub(r'(<objects count=")\d+(")', lambda m: f'{m.group(1)}{stats["kept"]}{m.group(2)}',
                 doc, count=1)
    omap_p.write_text(doc, encoding="utf-8")

    # --- maska renderu mimo quad → bílá ---
    rgb_p = gen_dir / "rgb.png"
    im = Image.open(rgb_p).convert("RGB")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).polygon([(float(a), float(b)) for a, b in quad_px], fill=255)
    arr = np.asarray(im).copy()
    arr[np.asarray(mask) == 0] = 255
    Image.fromarray(arr).save(rgb_p)
    return stats["kept"], stats["removed"]
