"""cut.py — ořez gen výstupu (.omap + render) na reálné mapové pole (natočený quad / osový box).

generate_map kreslí grid-north-up na axis-aligned bbox; reálná mapa je natočený quad (~2× užší kvůli
grivaci). Přesahové rohy bboxu obsahují okolní sídla (Stráž n. Nisou u Bedřichovky) s kompletní ČÚZK
infrastrukturou (ulice/budovy), kterou závodní OB mapa nepokrývá → výsledná gen.omap je nečistá jako
produkt a tréninkové páry učí reconstructor hustou uliční síť mimo cílovou doménu. Ořez = geometrický řez
objektů na hranici quadu + maska renderu na bílou (Sez. 109/114, zadání uživatele).

ARCHITEKTURA (Sez. 114, IMPLEMENTOVÁNO; povýšeno z původního centroidu): geometrická primitiva `cut_line`
(přímá konstrukce + reuse jen `_interp_grid_at` — `_split_by_zones_interp` nestačil, ponechával konce linie →
neuměl in→out, Sez. 114) / `cut_area` (Sutherland-Hodgman) / `cut_point` (`_point_in_quad`) → JEDEN
orchestrátor `clip_omap(.omap, clip_poly)` (přepíše `<coords>` + flagy, ne jen maže bloky) → wrappery
`cut_box` (4 rohy papíru, CLI `--location`) + `clip_omap_to_quad` (Livelox quad). Geometrický řez = přesné
dělení dlouhých linií na hranici quadu (doložená vada „Nisa do Vesce", Sez. 113/114 Novina přesah ~20 km → 1,00×).

`.omap` se upravuje STRING manipulací (regex odstranění `<object>` bloků), NE ET round-tripem — ten
přeformátuje celý dokument a rozbije jak string-based `inject_image_templates` (podklady), tak riskuje
OOM kompatibilitu. Mirror přístupu `omap_export`/`gen_backgrounds` (string template fill / regex inject).

Post-process (mimo monolit generate_map, fáze B): volá orchestrátor (measure_dod/pairs) se znalostí quadu.
"""
import json
import math
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


# ─────────────────────────────────────────────────────────────────────────────
# Geometrická primitiva ořezu (Sez. 114, prostor-agnostická — pracují v té
# soustavě, ve které dostanou body; orchestrátor `clip_omap` jim předá coords +
# clip_poly v JEDNOM prostoru). clip_poly = jednoduchý polygon (box i quad konvexní).
# ─────────────────────────────────────────────────────────────────────────────

def cut_point(pt: tuple, clip_poly: list) -> bool:
    """Primitivum BOD: ponechat? = bod uvnitř clip_poly (reuse `_point_in_quad`)."""
    return _point_in_quad(pt[0], pt[1], clip_poly)


def _seg_seg_t(p0: tuple, p1: tuple, a: tuple, b: tuple) -> float | None:
    """Průsečík úsečky p0→p1 s úsečkou a→b: vrací parametr t∈[0,1] na p0→p1 (None = bez
    průsečíku / rovnoběžné). Standardní 2D segment-segment přes determinant."""
    x1, y1 = p0; x2, y2 = p1; x3, y3 = a; x4, y4 = b
    d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(d) < 1e-12:                       # rovnoběžné / degenerátní → bez jednoznačného průsečíku
        return None
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d
    u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / d
    return t if (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0) else None


def cut_line(pts: list, clip_poly: list) -> list:
    """Primitivum LINIE: ořež polyline na část(i) UVNITŘ clip_poly. Vrací list pod-polylinií
    (každá ≥2 body), s INTERPOLOVANÝMI body přesně na hraně clip_poly (řez nevykukuje).

    POZOR (nález mini-verify Sez. 114): generator `_split_by_zones_interp` reuse NESTAČÍ — ten
    je stavěn na vyřezávání děr UVNITŘ linie (mosty/tunely) a KONCOVÉ body linie vždy ponechá,
    takže neumí oříznout KONCE (in→out), které ořez na hranici typicky vyžaduje. Proto přímá
    konstrukce úseků; reuse zůstává na `_interp_grid_at` (interpolovaný bod na hraně = TÝŽ jako
    u mostů/tunelů → konzistentní). Lazy import (vzor codebase, žádný cyklus gen↔cut).

    Postup: kumulativní délka `cum` → cum-pozice průsečíků s hranicí clip_poly (`_seg_seg_t`) →
    intervaly mezi 0/průsečíky/total → každý otestuj středem (uvnitř/venku) → souvislé VNITŘNÍ
    intervaly slož do úseku (interp na hraně + originální vrcholy mezi)."""
    from generator import _interp_grid_at  # lazy: monolit už importován v měřicí/párovací cestě

    if len(pts) < 2:
        return []
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    total = cum[-1]
    if total < 1e-9:
        return []

    n = len(clip_poly)
    crossings: list[float] = []
    for i in range(1, len(pts)):
        seg_len = cum[i] - cum[i - 1]
        for j in range(n):
            t = _seg_seg_t(pts[i - 1], pts[i], clip_poly[j], clip_poly[(j + 1) % n])
            if t is not None:
                crossings.append(cum[i - 1] + t * seg_len)
    bps = sorted(b for b in set(round(c, 6) for c in crossings) if 1e-9 < b < total - 1e-9)
    bounds = [0.0] + bps + [total]

    # uvnitř/venku per interval (test středem); souvislé vnitřní intervaly → jeden úsek
    flags = []
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        mx, my = _interp_grid_at(pts, cum, (a + b) / 2.0)
        flags.append(_point_in_quad(mx, my, clip_poly))
    result: list = []
    k = 0
    while k < len(bounds) - 1:
        if not flags[k]:
            k += 1
            continue
        a = bounds[k]
        while k < len(bounds) - 1 and flags[k]:    # slij souvislé vnitřní intervaly
            b = bounds[k + 1]
            k += 1
        piece = [_interp_grid_at(pts, cum, a)]
        piece += [pts[idx] for idx in range(len(pts)) if a + 1e-9 < cum[idx] < b - 1e-9]
        piece.append(_interp_grid_at(pts, cum, b))
        clean = [piece[0]]                          # dedup splývajících bodů (interp == vrchol na hraně)
        for p in piece[1:]:
            if abs(p[0] - clean[-1][0]) > 1e-9 or abs(p[1] - clean[-1][1]) > 1e-9:
                clean.append(p)
        if len(clean) >= 2:
            result.append(clean)
    return result


def _signed_area(poly: list) -> float:
    """2× orientovaná plocha (shoelace); >0 = CCW, <0 = CW. Pro orientaci clip_poly."""
    s = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s


def _line_line_pt(p0: tuple, p1: tuple, a: tuple, b: tuple) -> tuple:
    """Průsečík PŘÍMEK p0p1 × ab (Sutherland-Hodgman kontext: úsečka subjektu vždy protíná
    hranu clip_poly, d≠0)."""
    x1, y1 = p0; x2, y2 = p1; x3, y3 = a; x4, y4 = b
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def cut_area(rings: list, clip_poly: list) -> list:
    """Primitivum PLOCHA: ořež plošný objekt (rings = [vnější, díra1, …]) na clip_poly přes
    Sutherland-Hodgman (clip_poly KONVEXNÍ — box i quad ✓). Každý prsten ořízne nezávisle proti
    všem hranám clip_poly; prsteny redukované pod 3 body (zcela mimo) vypadnou. Even-odd výplň
    zůstává konzistentní (díra ořezaná spolu s vnějškem). Vrací list ořezaných prstenů (≥3 body).

    Orientace: S-H „inside" testuje cross-produktem hrany — sjednotím clip_poly na CCW (`_signed_area`),
    pak inside = bod nalevo od hrany (cross ≥ 0). Subjekt orientaci zachovává."""
    cp = clip_poly if _signed_area(clip_poly) > 0 else list(reversed(clip_poly))
    out_rings: list = []
    for ring in rings:
        poly = ring[:-1] if (len(ring) >= 2 and ring[0] == ring[-1]) else list(ring)  # zahoď uzavírací duplikát
        if len(poly) < 3:
            continue
        n = len(cp)
        for j in range(n):
            a, b = cp[j], cp[(j + 1) % n]
            if not poly:
                break
            ex, ey = b[0] - a[0], b[1] - a[1]
            inside = lambda p: ex * (p[1] - a[1]) - ey * (p[0] - a[0]) >= -1e-9  # nalevo od CCW hrany
            new: list = []
            prev = poly[-1]
            prev_in = inside(prev)
            for cur in poly:
                cur_in = inside(cur)
                if cur_in:
                    if not prev_in:
                        new.append(_line_line_pt(prev, cur, a, b))
                    new.append(cur)
                elif prev_in:
                    new.append(_line_line_pt(prev, cur, a, b))
                prev, prev_in = cur, cur_in
            poly = new
        if len(poly) >= 3:
            out_rings.append(poly)
    return out_rings


_OBJECTS_RE = re.compile(r'(<objects count=")(\d+)(">)(.*?)(</objects>)', re.DOTALL)
_TYPE_RE = re.compile(r'<object type="(\d)"')


def _parse_coords(block: str):
    """Z `<object>` bloku → (tokeny coords jako list (x,y,flag), opening-tag atributy). None coords → (None, attrs)."""
    cm = _COORDS_RE.search(block)
    attrs = re.search(r'<object\b([^>]*)>', block).group(1)
    if cm is None:
        return None, attrs
    toks = []
    for t in cm.group(1).strip().split(";"):
        p = t.split()
        if len(p) >= 2:
            try:
                toks.append((int(p[0]), int(p[1]), int(p[2]) if len(p) > 2 else 0))
            except ValueError:
                pass
    return toks, attrs


def _emit_line(pts: list, attrs: str) -> str:
    """Liniový objekt (type=1, bez flagů) z bodů (paper µm, float→round)."""
    cs = ";".join(f"{round(x)} {round(y)}" for x, y in pts) + ";"
    return f'<object{attrs}><coords count="{len(pts)}">{cs}</coords></object>'


def _emit_area(rings: list, attrs: str) -> str:
    """Plošný objekt (type=1, close/hole flagy) z prstenů — mirror omap_export.area_object konvence:
    poslední bod prstenu nese 18 (16 hole + 2 close), poslední z VÍCE prstenů jen 2."""
    valid = [r for r in rings if len(r) >= 3]
    if not valid:
        return ""
    parts, total, last = [], 0, len(valid) - 1
    for ri, ring in enumerate(valid):
        rp = [f"{round(x)} {round(y)}" for x, y in ring]
        rp[-1] += " 2" if (ri == last and last > 0) else " 18"
        parts.extend(rp)
        total += len(ring)
    cs = ";".join(parts) + ";"
    return f'<object{attrs}><coords count="{total}">{cs}</coords></object>'


def clip_omap(omap_path: str | pathlib.Path, clip_poly: list) -> tuple:
    """Geometrický ořez VŠECH mapových objektů uvnitř `<objects>` bloku na clip_poly (v PAPER µm =
    native prostor `<coords>`; wrappery `cut_box`/`clip_omap_to_quad` ho do paper µm převedou).
    Vrací (kept, removed) = počty výsledných / odstraněných objektů.

    Routing dle typu: BOD (type=0) → `cut_point` (ponech/zahoď celý objekt) · LINIE (type=1 bez
    close flagu) → `cut_line` (1 objekt → N kusů = N bloků) · PLOCHA (type=1 s close flagem & 2) →
    rozdělit coords na prsteny (close bit) → `cut_area` → přepsat s flag konvencí. Objekty CELÉ uvnitř
    se NEpřepisují (zachová přesné originální µm = 0 drift). Sahá JEN na `<objects>` blok (knihovna
    `<symbols>` netknuta). String/regex, NE ET (rozbil by inject_image_templates — paměť omap-edit-string-not-et)."""
    omap_path = pathlib.Path(omap_path)
    doc = omap_path.read_text(encoding="utf-8")
    om = _OBJECTS_RE.search(doc)
    if om is None:
        return 0, 0
    stats = {"kept": 0, "removed": 0}

    def _filter(m: re.Match) -> str:
        block = m.group(0)
        toks, attrs = _parse_coords(block)
        if not toks:
            stats["kept"] += 1
            return block                                  # bez coords → ponech
        tm = _TYPE_RE.search(block)
        typ = tm.group(1) if tm else "1"
        pts_all = [(x, y) for x, y, _ in toks]
        # CELÝ uvnitř → ponech beze změny (0 drift)
        if all(_point_in_quad(x, y, clip_poly) for x, y in pts_all):
            stats["kept"] += 1
            return block
        if typ == "0":                                    # BOD: jediný coord, mimo → zahoď
            if cut_point(pts_all[0], clip_poly):
                stats["kept"] += 1
                return block
            stats["removed"] += 1
            return ""
        is_area = any(f & 2 for _, _, f in toks)
        if is_area:                                       # PLOCHA → prsteny → cut_area
            rings, cur = [], []
            for x, y, f in toks:
                cur.append((x, y))
                if f & 2:
                    rings.append(cur); cur = []
            if cur:
                rings.append(cur)
            clipped = cut_area(rings, clip_poly)
            out = _emit_area(clipped, attrs)
            if out:
                stats["kept"] += 1
                return out
            stats["removed"] += 1
            return ""
        # LINIE → N kusů
        pieces = cut_line(pts_all, clip_poly)
        if not pieces:
            stats["removed"] += 1
            return ""
        stats["kept"] += len(pieces)
        return "".join(_emit_line(p, attrs) for p in pieces)

    new_body = _OBJ_RE.sub(_filter, om.group(4))
    new_objects = f'{om.group(1)}{stats["kept"]}{om.group(3)}{new_body}{om.group(5)}'
    doc = doc[:om.start()] + new_objects + doc[om.end():]
    omap_path.write_text(doc, encoding="utf-8")
    return stats["kept"], stats["removed"]


def _paper_extent(meta: dict):
    """(to_px, W, H, pw, ph): rozměry papíru v µm. pw/ph zpětně z LINEÁRNÍ to_px
    (px=(x/pw+0.5)·W ⇒ pw=1e6/(to_px(1e6,0).x/W−0.5)) → bez duplikace parsování meta."""
    to_px, W, H = _paper_to_px(meta)
    pw = 1_000_000.0 / (to_px(1_000_000.0, 0.0)[0] / W - 0.5)
    ph = 1_000_000.0 / (to_px(0.0, 1_000_000.0)[1] / H - 0.5)
    return to_px, W, H, pw, ph


def cut_box(gen_dir: str | pathlib.Path, name: str) -> tuple:
    """Ořež `<name>.omap` na PAPÍROVÝ obdélník (CLI `--location`/real: ČÚZK vrací CELÉ features
    protínající bbox → objekty přesahují papír o desítky km — „Nisa do Vesce", Sez. 113/114).
    Papír = osový obdélník [±pw/2, ±ph/2] v paper µm (= degenerovaný quad). `rgb.png` je už ořezán
    canvasem (W×H = papír), maska netřeba. Vrací (kept, removed)."""
    gen_dir = pathlib.Path(gen_dir)
    meta = json.load(open(gen_dir / "meta.json", encoding="utf-8"))
    _, _, _, pw, ph = _paper_extent(meta)
    clip_paper = [(-pw / 2, -ph / 2), (pw / 2, -ph / 2), (pw / 2, ph / 2), (-pw / 2, ph / 2)]
    return clip_omap(gen_dir / f"{name}.omap", clip_paper)


def clip_omap_to_quad(gen_dir: str | pathlib.Path, name: str, quad_sjtsk: list) -> tuple:
    """Ořež `<name>.omap` + `rgb.png` na natočený reálný quad (4 rohy S-JTSK). Vrací (kept, removed).

    GEOMETRICKÝ ořez (Sez. 114, povýšeno z centroidu): quad px → paper µm (invert to_px) → `clip_omap`
    přepíše `<coords>` (řez dlouhých linií na hraně quadu, ne celé/nic dle středu). Render mimo quad →
    bílá. Zachovává <symbols>/<templates> i jejich formát."""
    gen_dir = pathlib.Path(gen_dir)
    omap_p = gen_dir / f"{name}.omap"
    meta = json.load(open(gen_dir / "meta.json", encoding="utf-8"))
    _, W, H, pw, ph = _paper_extent(meta)
    quad_px = _quad_to_genpx(quad_sjtsk, gen_dir / "rgb.pgw")
    quad_paper = [((cx / W - 0.5) * pw, (cy / H - 0.5) * ph) for cx, cy in quad_px]   # px → paper µm (invert to_px)

    # vektorový geometrický ořez objektů na quad
    kept, removed = clip_omap(omap_p, quad_paper)

    # maska renderu mimo quad → bílá (rastr; quad_px v px prostoru rgb.png)
    rgb_p = gen_dir / "rgb.png"
    im = Image.open(rgb_p).convert("RGB")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).polygon([(float(a), float(b)) for a, b in quad_px], fill=255)
    arr = np.asarray(im).copy()
    arr[np.asarray(mask) == 0] = 255
    Image.fromarray(arr).save(rgb_p)
    return kept, removed
