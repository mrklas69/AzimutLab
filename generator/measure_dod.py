"""measure_dod.py — matched DoD driver: kolik ISOM symbolů vzorových map generátor SKUTEČNĚ nakreslí.

Operační půlka DoD brány (Sez. 94). `compare_isom.coverage()` sám potřebuje hotovou gen `.omap`;
tenhle driver ji matched VYROBÍ na obal každé reálné mapy z `resources/` a změří crosswalk-aware
pokrytí. DoD: fáze výroby `generator()` hotová až při ≥90 % ISOM (memory `generator-coverage-is-the-ceiling`).

  resources/<name>.pgw + .png  → 4 rohy skenu → S-JTSK axis-aligned obal → střed (WGS84) + rozměry
  generate_map(lat,lon,w_km,h_km, defaulty = vše real)  → maps/<name>/<name>.omap
  compare_isom.coverage(real, gen)  → crosswalk-aware X/Y matched (2000→2017, custom vyřazeno)

BASELINE = SEPARACE (Sez. 95, volba uživatele). `pairs.build_pair` vyrábí páry separací-ze-skenu
(`predict_areas_sjtsk`) → DoD baseline MUSÍ měřit reálnou produkční cestu párů. Zdroj predikční
vegetace je JEN separace (forest_age proxy archivován Sez. 102 jako slepá ulička). 403 Rough open
separace vrací věrně (odstín uvnitř open, Sez. 92).

KPI fáze generator() (Sez. 100, volba uživatele): PRIMÁRNÍ kvantifikátor = proporční podobnost
distribuce ISOM symbolů gen vs reálná mapa (histogram intersection Σ min(orig_share, gen_share)).
Jedno číslo 0–100 % = „kolik % symbolové hmoty gen mapy se proporčně překrývá s reálnou". Nahrazuje
binární DoD ≥90 % (archiv `--dod`): ten byl nedosažitelný (strop 54 %) a nezachytil inkrementální
práci (dissolve 520, marsh 310 ho nehnuly). Proporce ruší rozdíl plochy; penalizuje chybějící typ
(gen=0) i přestřel (min ukrojí přebytek).

PŘESAH-OŘEZ (Sez. 104, volba uživatele): gen kreslí OBDÉLNÍKOVÝ S-JTSK výsek, reálná OB mapa je
NEPRAVIDELNÝ blob → ČÚZK objekty (město/železnice/open) přesahují mimo mapovanou oblast →
NEROVNOMĚRNÝ přestřel, který proporční normalizace NEruší (je disproporční — proto KPI dřív
„obal-artefakt" jen ředilo, nemazalo). `_counts_for_map` proto gen objekty OŘEZÁVÁ na obal
nakreslených objektů reálné mapy (centroid → S-JTSK → sken px → maska, `_clipped_gen_counts`).
Dopad = obousměrné ZPŘESNĚNÍ (Bedř/Velb + ořez přestřelu, Blatná − odhalí maskovaný podstřel),
ne „vždy zvedne". Týká se KPI i KOMPASu (sdílí `_counts_for_map`).

Tři režimy (CLI):
  python generator/measure_dod.py          # PRIMÁRNÍ KPI: proporční podobnost distribuce + 3 sub + žebříček děr
  python generator/measure_dod.py --table  # KOMPAS: orig vs gen Σ objektů per ISOM kód, 3 kapitoly geom (Sez. 96)
  python generator/measure_dod.py --dod    # ARCHIV: binární DoD pokrytí typů + analytický cut (strop plošné fáze)

A3 (Sez. 94): Slovanka2016 (UTM33 — jiný transformer) + Soví vrch (domapováno ~1/4 → neúplná real
.omap zkreslí dolů) VYNECHÁNY z DoD → měří jen Bedřichovka/Blatná/Velbloud. Až bude UTM33 cesta /
Soví vrch domapováno, doplnit do MAPS. Spouštět z kořene přes .venv (sys.path skript, fáze B).
"""
import re
import sys
import json
import pathlib
from collections import Counter
from xml.etree import ElementTree as ET

import numpy as np
import scipy.ndimage as ndi
from scipy.spatial import ConvexHull
from PIL import Image, ImageDraw

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "connectors"))
sys.path.insert(0, str(REPO / "generator"))

from pyproj import Transformer            # noqa: E402
from isom.capabilities import CONFLICT_POLICY, SCAN_NONE, capability_by_code  # noqa: E402
from generator import generate_map        # noqa: E402
from compare_isom import (coverage, _load_crosswalk, _resolve_targets, detect_version,   # noqa: E402
                          isom_usage, used_geometry)   # crosswalk-aware Sez. 94; used_geom + tabulka Sez. 96
from separate import separate_areas, TARGET_MPP  # noqa: E402  (cesta b: separace-ze-skenu)
from map_gt import segment_gt, rasterize_map_field   # noqa: E402  (runnability GT + ruční mapfield, Sez. 173)
from omap_raster import _paper_to_px, _strip  # noqa: E402  (paper µm→gen px + strip namespace; ořez Sez. 104)

try:
    sys.stdout.reconfigure(encoding="utf-8")   # Windows cp1250 vs Unicode
except Exception:
    pass

Image.MAX_IMAGE_PIXELS = None
_SJTSK_TO_WGS84 = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)

MAPS = ["Bedřichovka", "Blatná", "Velbloud"]   # A3: Slovanka(UTM33)+Soví vrch(1/4) vynechány
# resources/ je gitignored a mezi stroji se liší (memory gitignored-availability-verify-not-assume):
# na ntbhej chybí Velbloud.pgw → DoD driver ho nezměří. Filtruj na mapy s dostupným .pgw + varuj
# (behavior-preserving na mrkla, kde je kompletní; jinde graceful degrade místo FileNotFoundError).
_missing_pgw = [m for m in MAPS if not (REPO / "resources" / f"{m}.pgw").exists()]
if _missing_pgw:
    print(f"⚠ chybí .pgw → vynecháno z měření: {_missing_pgw}", file=sys.stderr)
    MAPS = [m for m in MAPS if m not in _missing_pgw]


def _extent_from_pgw(name: str):
    """4 rohy skenu → S-JTSK axis-aligned obal (mirror pairs._georef_grid). Vrací (lat,lon,w_km,h_km).

    .pgw je 6-param afinní MĚŘÍTKO+ROTACE (sken natočený v S-JTSK): col,row → svět
    x = A*col + B*row + C,  y = D*col + E*row + F. Obal natočeného obdélníku = axis-aligned
    bbox 4 rohů; generate_map kreslí grid-north-up, compare_isom porovnává jen MNOŽINU kódů
    (ne geometrii), takže drobný přesah obalu přes natočenou mapu nevadí."""
    A, D, B, E, C, F = [float(x) for x in (REPO / "resources" / f"{name}.pgw").read_text().split()]
    with Image.open(REPO / "resources" / f"{name}.png") as im:
        W, H = im.size
    cols = np.array([0, W, 0, W], dtype=float)      # 4 rohy pixel-gridu
    rows = np.array([0, 0, H, H], dtype=float)
    xs = A * cols + B * rows + C
    ys = D * cols + E * rows + F
    xmin, xmax, ymin, ymax = xs.min(), xs.max(), ys.min(), ys.max()
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    lon, lat = _SJTSK_TO_WGS84.transform(cx, cy)     # centroid obalu → WGS84 (generate_map čeká lat/lon)
    return lat, lon, (xmax - xmin) / 1000.0, (ymax - ymin) / 1000.0


def _load_map_field(name: str) -> list | None:
    """Ruční crop polygon mapového pole (Sez. 173): resources/<name>_mapfield.json → [[col,row],…]
    v px PLNÉHO skenu, nebo None když chybí. Robustní náhrada auto detekce (detect_map_area /
    convex hull) tam, kde barevný layout (zelený banner/loga) selhává — viz tools/mark_mapfield.py."""
    p = REPO / "resources" / f"{name}_mapfield.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))["polygon_px"]


def _separate_resources_to_sjtsk(name: str, sep_dir: pathlib.Path) -> list:
    """resources sken → downscale → map_gt → separace → polygony v S-JTSK (přes .pgw afinní).

    Analog pairs._separate_to_sjtsk, ale pro resources mapu (georef = .pgw, ne Livelox quad).
    Sken downscaluje na ~TARGET_MPP PŘED map_gt — segment_gt načítá celý obrázek a resources
    skeny jsou obří (Bedřichovka 114 Mpx > ~100 Mpx strop, Sez. 90). Vrací [(rings_sjtsk, code:int)]
    pro generate_map predict_areas_sjtsk."""
    A, D, B, E, C, F = [float(x) for x in (REPO / "resources" / f"{name}.pgw").read_text().split()]
    mpp = (A * A + D * D) ** 0.5                     # m/px skenu (rotace → euklid. norma sloupce afinní)
    f = max(1.0, TARGET_MPP / mpp)                   # downscale faktor na ~1,33 m/px
    with Image.open(REPO / "resources" / f"{name}.png") as im:
        im = im.convert("RGB")
        W, H = im.size
        nW, nH = max(1, round(W / f)), max(1, round(H / f))
        small = im.resize((nW, nH), Image.BILINEAR)
    sep_dir.mkdir(parents=True, exist_ok=True)
    small.save(sep_dir / "map.png")
    mfield = _load_map_field(name)                        # ruční crop polygon (Sez. 173)
    if mfield is not None:
        mfmask = rasterize_map_field(mfield, (W, H), (nH, nW))   # full px polygon → downscaled maska
    else:
        mfmask = None
        print(f"⚠ {name}: bez ručního mapfield → auto detect_map_area (riziko: zelený layout banner/loga "
              f"jako falešný les)", file=sys.stderr)
    segment_gt(sep_dir / "map.png", out_dir=sep_dir, map_field_mask=mfmask)   # → gt_labels.png (0-4/255)
    gt = np.asarray(Image.open(sep_dir / "gt_labels.png"))
    polys = separate_areas(gt, rgb=np.asarray(small), src_mpp=None)   # už v target rozlišení

    fx, fy = W / nW, H / nH                          # skutečné downscale faktory (round → přesně zpět)
    out: list = []
    for code, polys_c in polys.items():
        ci = int(float(code))
        for poly in polys_c:                         # poly = [outer, díra…], ring = (col,row) downscaled px
            rings = []
            for ring in poly:
                pts = np.asarray(ring, dtype=float)
                col, row = pts[:, 0] * fx, pts[:, 1] * fy   # downscaled px → full-res px
                x = A * col + B * row + C            # full-res px → S-JTSK (.pgw afinní s rotací)
                y = D * col + E * row + F
                rings.append([(float(xx), float(yy)) for xx, yy in zip(x, y)])
            out.append((rings, ci))
    return out


def _code_mtime() -> float:
    """Nejnovější mtime zdrojového kódu (generator/ + connectors/), který ovlivňuje gen .omap.

    Klíč k invalidaci cache _gen_sep: cached matched .omap STARŠÍ než kód = stale → přegeneruj.
    Bez toho je kompas SLEPÝ ke změnám generátoru (měří cached geometrii a tvrdí „beze změny";
    past Sez. 99: skip-existing nechal kompas neviditelný k 310 mokřadům i 520 dissolve ze Sez. 98)."""
    return max(p.stat().st_mtime for d in ("generator", "connectors")
               for p in (REPO / d).glob("*.py"))


def _scan_grivation(name: str) -> float | None:
    """Grivace [°] z georef reálného skenu `resources/<name>.omap` (atribut `grivation`), nebo None.

    Reálné OB mapy jsou magnetic-north (grivace v georef); předáme ji do gen.omap, aby gen kresba
    orientačně lícovala se skenem připnutým jako bg podklad (Sez. 112; jinak rozjezd ~11° = konvergence
    S-JTSK ~7° + deklinace ~5°). No-silent: chybí-li atribut, vrať None (grid-north, nefabrikuj)."""
    scan = REPO / "resources" / f"{name}.omap"
    if not scan.exists():
        return None
    m = re.search(r'grivation="([^"]*)"', scan.read_text(encoding="utf-8"))
    return float(m.group(1)) if m else None


def _gen_sep(name: str, out: pathlib.Path) -> pathlib.Path:
    """Matched gen .omap SE SEPARACÍ-ZE-SKENU (Sez. 95 baseline = reálná produkční cesta párů).

    `pairs.build_pair` vyrábí páry separací (predict_areas_sjtsk) → DoD MUSÍ měřit separaci.
    Cache: skip JEN když je .omap novější než zdrojový kód (jinak by kompas měřil stale geometrii —
    Sez. 99). Drahá regenerace (map_gt na obřím skenu + separace) → cache se ruší jen při reálné
    změně kódu, ne při re-měření."""
    omap = out / f"{name}.omap"
    if omap.exists() and omap.stat().st_mtime >= _code_mtime():   # cache platná: novější než kód
        return omap
    lat, lon, w_km, h_km = _extent_from_pgw(name)
    griv = _scan_grivation(name)   # grivace ze skenu → gen.omap orientačně lícuje s reálným skenem (Sez. 112)
    print(f"\n{'=' * 70}\n{name}  výsek {w_km:.2f}×{h_km:.2f} km @ ({lat:.5f}, {lon:.5f}) — separace ze skenu"
          f"{f' · grivace {griv}°' if griv is not None else ''}\n{'=' * 70}")
    predict = _separate_resources_to_sjtsk(name, out / "sep")
    print(f"  {len(predict)} predikčních ploch → generate_map (predict_areas_sjtsk)")
    generate_map(lat, lon, w_km, h_km, out_dir=str(out), ortho=False, tolerant=True,
                 predict_areas_sjtsk=predict, grivation=griv)
    # Ořež výslednou gen.omap + render na reálné mapové pole (natočený quad ze skenu) — odstraní přesah
    # axis-aligned bboxu: okolní sídla mimo závodní mapu (Stráž n. Nisou u Bedřichovky; Sez. 109, zadání
    # uživatele). Centroid (KISS). Quad = 4 rohy skenu v S-JTSK (mirror _extent_from_pgw, ale rohy ne obal).
    from cut import clip_omap_to_quad
    sA, sB, sC, sD, sE, sF = _pgw(REPO / "resources" / f"{name}.pgw")
    with Image.open(REPO / "resources" / f"{name}.png") as sim:
        SW, SH = sim.size
    quad = [(sA * c + sB * r + sC, sD * c + sE * r + sF)
            for c, r in [(0, 0), (SW, 0), (SW, SH), (0, SH)]]
    kept, removed = clip_omap_to_quad(out, name, quad)
    print(f"  ořez na quad: {kept} objektů v poli, {removed} přesah odstraněn")
    # Připni reálný sken jako bg podklad: měřicí cesta jinak přepíše produkční gen.omap BEZ podkladů
    # (regrese „zase vypadly podklady", Sez. 109) → v OOM zmizí reálný sken pro verify gen kresby.
    from gen_backgrounds import add_resources_scan_background   # lokální import (livelox/map_gt deps)
    res = add_resources_scan_background(name, out)
    print(f"  podklad: {', '.join(res['added']) or 'nepřipnut'}")
    return omap


# --- OŘEZ na mapovanou oblast reálné mapy (Sez. 104, přesah-artefakt) ---
# generate_map kreslí OBDÉLNÍKOVÝ S-JTSK výsek; reálná OB mapa je NEPRAVIDELNÝ blob (bílé okraje =
# nemapováno) → ČÚZK objekty (město/železnice/open) PŘESAHUJÍ mimo mapovanou oblast → nerovnoměrný
# přestřel ZKRESLUJE KPI (proporční normalizace ho neruší, je disproporční). Řešení: ořez gen objektů
# na obal nakreslených objektů reálné mapy (volba uživatele Sez. 103/104). Prototyp temp/proto_clip.py.
_CLIP_DS = 8       # downscale skenu pro masku (rychlost; maska je hrubá silueta, jemnost netřeba)
_CLIP_CLOSE = 6    # iterace binary_closing (spojí roztroušené objekty do souvislé siluety)


def _pgw(path: pathlib.Path):
    """.pgw 6 parametrů (world-file pořadí A,D,B,E,C,F) → afinní (col,row)→svět: x=A·col+B·row+C, y=D·col+E·row+F."""
    A, D, B, E, C, F = [float(x) for x in path.read_text().split()]
    return A, B, C, D, E, F


def _mapped_area_mask(name: str) -> np.ndarray:
    """Maska mapované oblasti reálné mapy ze skenu (resources/<name>.png + .pgw), downscaled ×_CLIP_DS.

    non-white = nakreslený objekt (vrstevnice/zeleň/cesty); skoro-bílá = papír/bílý les. close spojí
    roztroušené objekty → největší komponenta zahodí loga/text MIMO mapu → CONVEX HULL = vnější silueta
    (pokryje světlé open / bílý les 401 uvnitř protkaný řídkými vrstevnicemi, nezávisle na řídkosti).
    Volba uživatele Sez. 103/104: pro ~konvexní DoD mapy věrné (konkávní by hull přestřelil)."""
    with Image.open(REPO / "resources" / f"{name}.png") as im:
        im = im.convert("RGB")
        Wf, Hf = im.size
        sm = np.asarray(im.resize((Wf // _CLIP_DS, Hf // _CLIP_DS), Image.BILINEAR))
    hs, ws = sm.shape[:2]
    mfield = _load_map_field(name)                     # ruční crop polygon (Sez. 173) přebíjí convex hull
    if mfield is not None:
        return rasterize_map_field(mfield, (Wf, Hf), (hs, ws))
    print(f"⚠ {name}: bez ručního mapfield → convex hull KPI ořezu (může přestřelit na loga/rohy "
          f"nekonvexní mapy → kontaminace counts)", file=sys.stderr)
    nonwhite = ~((sm[:, :, 0] > 245) & (sm[:, :, 1] > 245) & (sm[:, :, 2] > 245))
    mask = ndi.binary_fill_holes(ndi.binary_closing(nonwhite, iterations=_CLIP_CLOSE))
    lbl, nlab = ndi.label(mask)                       # největší souvislá komponenta = mapová silueta
    if nlab > 1:
        sizes = ndi.sum(mask, lbl, range(1, nlab + 1))
        mask = lbl == (int(np.argmax(sizes)) + 1)
    ys, xs = np.nonzero(mask)
    hull = ConvexHull(np.column_stack([xs, ys]))      # vrcholy obalu → PIL polygon fill (bez skimage)
    verts = [(float(xs[v]), float(ys[v])) for v in hull.vertices]
    himg = Image.new("L", (ws, hs), 0)
    ImageDraw.Draw(himg).polygon(verts, fill=1)
    return np.asarray(himg, dtype=bool)


def _gen_centroids(omap_path: pathlib.Path):
    """[(ci:int, cx_paper, cy_paper)] pro mapové objekty (kód 100-599) gen .omap + paper-µm centroid.

    Centroid = průměr coords bodů (reprezentativní poloha plochy/linie/bodu pro test do/ven masky).
    object symbol = pořadový index do <symbols> (gen export, id==index ověřeno Sez. 87). Bez ořezu
    reprodukuje isom_usage byte-přesně (Q1 verify Sez. 104) → „před ořezem" = dnešní baseline."""
    root = ET.parse(omap_path).getroot()
    sp = next(e for e in root.iter() if _strip(e.tag) == "symbols")
    codes = [s.get("code") for s in sp if _strip(s.tag) == "symbol"]
    op = next(e for e in root.iter() if _strip(e.tag) == "objects")
    out = []
    for o in op.iter():
        if _strip(o.tag) != "object":
            continue
        si = int(o.get("symbol", -1))
        if not (0 <= si < len(codes)):
            continue
        try:
            cc = int(float(codes[si]))                # integer prefix (415.0 → 415)
        except (ValueError, TypeError):
            continue
        if cc < 100 or cc >= 600:                     # jen mapové symboly (vyluč layout/control/overprint)
            continue
        c = next((x for x in o if _strip(x.tag) == "coords"), None)
        if c is None or not c.text:
            continue
        xs, ys = [], []
        for tok in c.text.strip().split(";"):
            nums = tok.split()
            if len(nums) >= 2:
                try:
                    xs.append(int(nums[0])); ys.append(int(nums[1]))
                except ValueError:
                    pass
        if xs:
            out.append((cc, sum(xs) / len(xs), sum(ys) / len(ys)))
    return out


def _clipped_gen_counts(name: str, gen_omap: pathlib.Path) -> Counter:
    """Gen counts (int kód → #objektů) OŘEZANÉ na mapovanou oblast reálné mapy (Sez. 104).

    Centroid každého gen objektu: paper µm → gen px (_paper_to_px) → S-JTSK (rgb.pgw) → sken px
    (inverz sken .pgw) → test proti masce. Objekty mimo masku (přesah obdélníkového výseku přes
    nepravidelný blob mapy) se NEpočítají. No silent fallback (CLAUDE.md): chybí-li sken/pgw/meta,
    VARUJ a vrať NEOŘEZANÉ isom_usage counts pro tu mapu (graceful jako _missing_pgw vzor)."""
    png = REPO / "resources" / f"{name}.png"
    spgw = REPO / "resources" / f"{name}.pgw"
    rpgw = REPO / "maps" / name / "rgb.pgw"
    meta_p = REPO / "maps" / name / "meta.json"
    if not (png.exists() and spgw.exists() and rpgw.exists() and meta_p.exists()):
        print(f"⚠ {name}: chybí sken/pgw/meta pro ořez → KPI BEZ ořezu pro tuto mapu "
              f"(přesah-artefakt nezohledněn)", file=sys.stderr)
        usage, _ = isom_usage(str(gen_omap))
        return usage
    mask = _mapped_area_mask(name)
    hs, ws = mask.shape
    sA, sB, sC, sD, sE, sF = _pgw(spgw)               # sken px → S-JTSK
    gA, gB, gC, gD, gE, gF = _pgw(rpgw)               # gen px → S-JTSK
    det = sA * sE - sB * sD                            # pro inverz sken afinní (S-JTSK → sken px)
    meta = json.load(open(meta_p, encoding="utf-8"))
    to_px, _, _ = _paper_to_px(meta)                  # paper µm → gen px
    clip = Counter()
    for cc, px, py in _gen_centroids(gen_omap):
        col, row = to_px(px, py)
        x = gA * col + gB * row + gC                  # gen px → S-JTSK
        y = gD * col + gE * row + gF
        scol = (sE * (x - sC) - sB * (y - sF)) / det  # S-JTSK → sken full-res px
        srow = (-sD * (x - sC) + sA * (y - sF)) / det
        mc, mr = int(scol / _CLIP_DS), int(srow / _CLIP_DS)   # → downscaled maska px
        if 0 <= mr < hs and 0 <= mc < ws and mask[mr, mc]:
            clip[cc] += 1
    return clip


def _counts_for_map(name, cw, v2000, v2017):
    """Σ objektů per 2017-2 ISOM kód pro JEDNU mapu: (orig, gen, geom_cnt, names).

    Sdílený sběr pro kompas (`--table`) i KPI (default). orig = reálná `.omap` crosswalkem na 2017-2
    cíl (custom/bez cíle vyřazen); gen = separační baseline (identita 2017-2) OŘEZANÁ na mapovanou
    oblast reálné mapy (Sez. 104 přesah-artefakt, `_clipped_gen_counts`); geom_cnt[kód] =
    Counter(geom REÁLNĚ POUŽITÉ varianty z `used_geometry`, vážená objekty); names[kód] = jméno z reálné."""
    gen_omap = _gen_sep(name, REPO / "maps" / name)            # separační baseline (cache dle mtime kódu)
    real_path = str(REPO / "resources" / f"{name}.omap")
    ver = detect_version(real_path)
    real, rnames = isom_usage(real_path)
    ug = used_geometry(real_path)                              # reálný kód → geom (point/area/line…)
    g = _clipped_gen_counts(name, gen_omap)                    # gen kódy 2017-2, OŘEZANÉ na mapovanou oblast (Sez. 104)
    orig, gen, geom_cnt, names = Counter(), Counter(), {}, {}
    for c, n in g.items():
        gen[c] += n
    for c, n in real.items():                                  # reálné kódy → 2017-2 cíl crosswalkem
        targets = _resolve_targets(c, ver, cw, v2000, v2017)
        if not targets:                                        # custom (None) nebo bez cíle → vyřaď
            continue
        key = sorted(targets)[0]                               # primární 2017 cíl
        orig[key] += n
        geom_cnt.setdefault(key, Counter())[ug.get(c, "?")] += n
        names.setdefault(key, rnames.get(c, ""))
    return orig, gen, geom_cnt, names


def _intersection(orig, gen) -> float:
    """Histogram intersection proporcí: Σ min(orig_share, gen_share) × 100 (KPI jádro, Sez. 100).

    Každý vektor normalizován na vlastní Σ → proporce ruší rozdíl plochy (obal-artefakt). Chybějící
    typ (gen=0) → člen 0; přestřel (gen_share > orig_share) → min ukrojí přebytek (okrade ostatní).
    Gen-only kódy (v gen, ne v orig) zvětší Σgen → naředí gen_share → penalizace falešných typů. 0 když prázdné."""
    so, sg = sum(orig.values()), sum(gen.values())
    if not so or not sg:
        return 0.0
    return 100.0 * sum(min(orig[c] / so, gen[c] / sg) for c in set(orig) | set(gen))


# --- KOMPAS sloupce zdroj · gen · scan (ROADMAP g2, Sez. 138/147) ---
# SSoT puvodu symbolu je `isom.capabilities`. Tenhle driver uz nedrzi vlastni
# kopii registru; jen prevadi integer kod po crosswalku na kratky radek tabulky.
def _shorten(value: str, limit: int) -> str:
    """Zkrati dlouhy popis zdroje, aby KOMPAS zustal citelny v terminalu."""
    return value if len(value) <= limit else value[:limit - 3] + "..."


def _kompas_source(code: int) -> tuple[str, str, str]:
    """Vrati (zdroj, fallback generator, scan signal) pro jeden ISOM kod.

    `generator_kind` je to, co dnes vyrobi samotny generator bez konkretniho
    skenu. `scanner_status` je oddeleny proto, ze mapper-scan signal je pri
    konfliktu silnejsi nez ZABAGED i pseudo, ale nema zpetne prepisovat popis
    fallback vrstvy.
    """
    try:
        cap = capability_by_code(str(code))
    except KeyError:
        return "–", "–", "–"
    scan = "–" if cap.scanner_status == SCAN_NONE else cap.scanner_status
    return _shorten(cap.generator_source, 24), cap.generator_kind, scan


def _provedeni(o: int, g: int, tot_o: int, tot_g: int) -> str:
    """AUTO provedení z PROPORČNÍHO poměru orig:gen (volba uživatele Sez. 138; share-based = Goodhart-aware,
    memory `kpi-overshoot-dilutes-not-counts` — absolutní Σ klame, gen globálně podstřeluje).

    Porovnává PODÍL symbolu (gen_share vs orig_share) přes celý měřený set, ne absolutní počty → globální
    rozdíl měřítka se vyruší. chybí = neumíme (gen 0) · jen gen = falešný typ (orig 0) · podstřel/přestřel =
    proporčně mimo (mimo pásmo 0,67–1,5×) · ok = proporčně sedí."""
    if g == 0:
        return "chybí" if o > 0 else "–"
    if o == 0:
        return "jen gen"
    r = (g / tot_g) / (o / tot_o) if tot_o and tot_g else 0.0
    if r >= 1.5:
        return "přestřel"
    if r <= 0.67:
        return "podstřel"
    return "ok"


def run_table() -> None:
    """--table: KOMPAS pokrytí (Sez. 96). Tři kapitoly (Png2Area/Png2Line/Png2Point), řádky = ISOM
    2017-2 kódy, sloupce = Σ objektů ORIG (reálné `.omap`) vs GEN (separační gen `.omap`) přes MAPS.

    Diagnostický doplněk KPI: poměr orig:gen ukazuje PROPORCE — přibližujeme se k cíli ve správné
    četnosti, nebo přestřelujeme/podstřelujeme? Nálezy Sez. 96: gen PŘESTŘELUJE 520/521/cesty (hustá
    ČÚZK projekce na obal výseku) a PODSTŘELUJE vegetaci (403/406/408 — pattern třídy 402/404 splývají
    do base odstínů, separace pattern-slepá). Cíl generátoru = přiblížit gen k orig; symboly co data
    nedají → generovat věrohodně do statistické míry četnosti (volba uživatele Sez. 96). Geometrie z
    reálné mapy (`used_geom`)."""
    cw, v2000, v2017 = _load_crosswalk()
    orig, gen = Counter(), Counter()      # 2017 kód → Σ objektů (reálné / gen)
    geom_t, names = {}, {}                # 2017 kód → Counter(geom) z reálné mapy / jméno
    for name in MAPS:
        o, g, gc, nm = _counts_for_map(name, cw, v2000, v2017)
        orig.update(o)
        gen.update(g)
        for c, cnt in gc.items():
            geom_t.setdefault(c, Counter()).update(cnt)
        for c, v in nm.items():
            names.setdefault(c, v)

    all_codes = set(orig) | set(gen)
    # geom: majorita z reálné mapy; kódy jen-v-gen (v reálných mapách nejsou) → '?'
    geom = {c: (geom_t[c].most_common(1)[0][0] if c in geom_t else "?") for c in all_codes}
    sections = [("Png2Area  (plocha)", "area"), ("Png2Line  (linie)", "line"),
                ("Png2Point (bod)", "point")]
    tot_o, tot_g = sum(orig.values()), sum(gen.values())   # globální Σ pro proporční provedení (share-based)
    print(f"KOMPAS pokrytí — orig (reálné .omap) vs gen (separace) přes {len(MAPS)} mapy {MAPS}")
    print("sloupce: orig/gen Σ objektů · zdroj fallback generátoru · gen real/mapper_scan/mixed/pseudo · "
          "scan signal · provedení AUTO z proporce orig:gen (ok/přestřel/podstřel/chybí/jen gen)")
    print(f"konflikt zdrojů: {CONFLICT_POLICY}")
    for title, gkey in sections:
        codes = sorted([c for c in all_codes if geom[c] == gkey], key=lambda c: -orig[c])
        sum_o = sum(orig[c] for c in codes)
        sum_g = sum(gen[c] for c in codes)
        n_cov = sum(1 for c in codes if orig[c] > 0 and gen[c] > 0)
        n_orig = sum(1 for c in codes if orig[c] > 0)
        print(f"\n{'=' * 78}\n{title}   [pokryto {n_cov}/{n_orig} kódů, orig Σ{sum_o}  gen Σ{sum_g}]\n{'=' * 78}")
        print(f"  {'kód':>5} {'orig':>6} {'gen':>6}  {'zdroj':<24} {'gen_kind':<11} {'scan':<19} {'proved.':<8} jméno")
        for c in codes:
            o, gg = orig[c], gen[c]
            zdroj, kind, scan = _kompas_source(c)
            prov = _provedeni(o, gg, tot_o, tot_g)
            print(f"  {c:>5} {o:>6} {gg:>6}  {zdroj:<24} {kind:<11} {scan:<19} {prov:<8} {names.get(c, '')[:26]}")
    other = sorted([c for c in all_codes if geom[c] not in ("area", "line", "point")],
                   key=lambda c: -orig[c])
    if other:
        print(f"\n{'-' * 60}\nostatní (kombi/text/jen-gen): " +
              " ".join(f"{c}(o{orig[c]}/g{gen[c]})" for c in other))


def run_kpi() -> None:
    """PRIMÁRNÍ KPI fáze generator() (Sez. 100, volba uživatele): proporční podobnost distribuce
    ISOM symbolů gen vs reálná mapa. Jedno číslo 0–100 % = histogram intersection Σ min(orig_share,
    gen_share), per-mapa pak průměr (jako DoD). Tři sub-skóre per geometrická kapitola (plocha/linie/
    bod, lokální normalizace) = diagnostika, NEsčítá se na headline. + žebříček největších proporčních
    děr (agregát) = kam směřovat práci.

    Proč nahrazuje DoD ≥90 %: binární pokrytí typů bylo nedosažitelné (strop 54 %) a slepé k
    inkrementálnímu progresu (dissolve 520 9×→1,3×, marsh 310 ho nehnuly). KPI dává partial credit
    za přibližování proporcí + je robustní vůči obal-artefaktu (proporce ruší rozdíl plochy)."""
    cw, v2000, v2017 = _load_crosswalk()
    per_map = []                                              # (name, kpi, sub{geom: kpi})
    agg_orig, agg_gen, agg_names = Counter(), Counter(), {}   # agregát pro žebříček děr
    for name in MAPS:
        orig, gen, geom_cnt, names = _counts_for_map(name, cw, v2000, v2017)
        geom = {c: cnt.most_common(1)[0][0] for c, cnt in geom_cnt.items()}   # majoritní geom reálné varianty
        sub = {}                                             # sub-skóre per kapitola (lokální normalizace)
        for gk in ("area", "line", "point"):
            o = Counter({c: v for c, v in orig.items() if geom.get(c) == gk})
            g = Counter({c: v for c, v in gen.items() if geom.get(c) == gk})
            sub[gk] = _intersection(o, g)
        per_map.append((name, _intersection(orig, gen), sub))
        agg_orig.update(orig)
        agg_gen.update(gen)
        for c, v in names.items():
            agg_names.setdefault(c, v)

    print(f"{'#' * 70}\nKPI generator() — proporční podobnost distribuce ISOM symbolů (Sez. 100)\n{'#' * 70}")
    print(f"  {'mapa':<14} {'KPI':>5}   {'plocha':>6} {'linie':>6} {'bod':>6}")
    for name, kpi, sub in per_map:
        print(f"  {name:<14} {kpi:>4.1f}%   {sub['area']:>5.1f}% {sub['line']:>5.1f}% {sub['point']:>5.1f}%")
    avg = sum(k for _, k, _ in per_map) / len(per_map)
    sub_avg = {gk: sum(s[gk] for _, _, s in per_map) / len(per_map) for gk in ("area", "line", "point")}
    print(f"  {'PRŮMĚR (KPI)':<14} {avg:>4.1f}%   {sub_avg['area']:>5.1f}% {sub_avg['line']:>5.1f}% {sub_avg['point']:>5.1f}%")
    print("  (headline = sloupec KPI; sub-skóre plocha/linie/bod = diagnostika, lokální normalizace, nesčítá se)")

    # žebříček největších proporčních děr (agregát): ztráta p.b. = orig_share − min(orig_share, gen_share)
    so, sg = sum(agg_orig.values()), sum(agg_gen.values())
    gaps = sorted(((agg_orig[c] / so - min(agg_orig[c] / so, agg_gen[c] / sg), c)
                   for c in set(agg_orig) | set(agg_gen)), reverse=True)
    print(f"\n  největší proporční díry (agregát, kam směřovat práci):")
    print(f"    {'kód':>5} {'orig':>6} {'gen':>6} {'ztráta':>7}  jméno")
    for loss, c in gaps[:10]:
        if loss <= 0:
            break
        print(f"    {c:>5} {agg_orig[c]:>6} {agg_gen[c]:>6} {loss * 100:>5.1f}pb  {agg_names.get(c, '')[:34]}")


def main() -> None:
    per_map = []          # (name, coverage-dict)
    for name in MAPS:
        gen_omap = _gen_sep(name, REPO / "maps" / name)        # SEPARAČNÍ baseline (Sez. 95)
        r = coverage(str(REPO / "resources" / f"{name}.omap"), str(gen_omap))
        print(f">>> {name}: ISOM {r['version']}, {len(r['covered'])}/{r['denom']} = {r['pct']:.0f}%"
              f"  (+{len(r['custom'])} custom vyřazeno)")
        per_map.append((name, r))

    # --- agregát ---
    print(f"\n{'#' * 70}\nMATCHED DoD BASELINE (crosswalk-aware, separace-ze-skenu)\n{'#' * 70}")
    pcts = []
    for name, r in per_map:
        pcts.append(r["pct"])
        print(f"  {name:<14} ISOM {r['version']:<7} {len(r['covered']):>2}/{r['denom']:<2} = {r['pct']:>3.0f}%")
    print(f"  {'PRŮMĚR':<14} {'':<13} {sum(pcts) / len(pcts):>9.0f}%")

    # union chybějících přes mapy, NORMALIZOVÁNO na 2017-2 cíl (konzistentní napříč 2000+2017 mapami)
    miss_maps = Counter()     # 2017 kód → v kolika mapách chybí
    miss_freq = Counter()     # 2017 kód → suma objektů v reálných mapách, kde chybí
    miss_name = {}
    miss_geom = {}            # 2017 kód → Counter(geom → Σobjektů) z REÁLNÉ mapy (Sez. 96 variant-aware)
    for name, r in per_map:
        seen_keys = set()                              # dedup per mapa (víc 2000 kódů → týž 2017 cíl)
        for real_c, targets, freq, nm in r["missing"]:
            key = targets[0] if targets else real_c    # primární 2017 cíl
            g = r["used_geom"].get(real_c, "?")        # geom REÁLNĚ POUŽITÉ varianty (ne template-primary)
            miss_freq[key] += freq
            miss_name.setdefault(key, nm)
            miss_geom.setdefault(key, Counter())[g] += freq   # vážená objekty → majoritní geom níž
            if key not in seen_keys:                    # #map = v kolika MAPÁCH cíl chybí (1× per mapa)
                miss_maps[key] += 1
                seen_keys.add(key)
    print(f"\nCHYBÍ napříč {len(MAPS)} mapami (2017-2 kód, dle #map pak Σobjektů):")
    print(f"  {'2017':>5} {'#map':>4} {'obj.Σ':>7}  jméno (z reálné mapy)")
    for c in sorted(miss_maps, key=lambda c: (-miss_maps[c], -miss_freq[c])):
        print(f"  {c:>5} {miss_maps[c]:>4} {miss_freq[c]:>7}  {miss_name.get(c, '')[:42]}")

    # --- ANALYTICKÝ CUT (Sez. 95; variant-aware Sez. 96): rozpad DoD podle geometrie symbolu ---
    # Cíl: kolik z 90 % DoD je dosažitelné PLOŠNÝM generátorem TEĎ (Png2Area existuje) vs co je
    # strukturálně mimo (body→Png2Point, linie→Png2Line — ani jeden zatím neexistuje).
    # Geometrie se bere z REÁLNÉ mapy (`used_geom`, co kartograf skutečně nakreslil), NE z
    # template-primary (Sez. 96 oprava): 210 má primary 'area', ale reálné mapy ho kreslí body
    # (210.0/210.1 point) → template-cut ho nadhodnocoval do plošného stropu.
    GEOM_CZ = {"area": "plocha", "line": "linie", "point": "bod",
               "combined": "kombi", "text": "text", "?": "neznámé"}
    RECON = {"area": "Png2Area ✓ (existuje)", "line": "Png2Line — (chybí)",
             "point": "Png2Point — (chybí)", "combined": "kombi → liniový", "text": "popisek",
             "?": "mimo template"}
    GEOM_ORDER = ["area", "line", "point", "combined", "text", "?"]
    # majoritní geom per 2017 cíl (přes všechny mapy, vážená objekty) — pro #kódů rozpad i strop
    key_geom = {c: cnt.most_common(1)[0][0] for c, cnt in miss_geom.items()}

    # (1) Plošný strop = per-mapa pokrytí, KDYBY gen dokreslil všechny chybějící PLOCHY; pak průměr.
    #     DoD je per-mapa průměr → strop počítám stejně (ne union), ať jsou čísla srovnatelná.
    #     „plocha" dle reálné varianty v TÉ mapě (used_geom), ne template.
    ceil_pcts = []
    for name, r in per_map:
        n_miss_area = sum(1 for rc, _, _, _ in r["missing"] if r["used_geom"].get(rc) == "area")
        ceil = 100 * (len(r["covered"]) + n_miss_area) / r["denom"] if r["denom"] else 0
        ceil_pcts.append(ceil)
    now_avg = sum(pcts) / len(pcts)
    ceil_avg = sum(ceil_pcts) / len(ceil_pcts)

    # (2) Gap podle geometrie: distinct chybějící 2017 cíle (union přes mapy) + Σobjektů.
    gap_codes, gap_freq = Counter(), Counter()        # geometrie → #kódů / Σobjektů
    for c in miss_maps:                               # miss_maps = union chybějících 2017 cílů
        g = key_geom.get(c, "?")
        gap_codes[g] += 1
        gap_freq[g] += miss_freq[c]

    print(f"\n{'#' * 70}\nANALYTICKÝ CUT — strop plošné fáze (Png2Area teď vs Png2Point/Line dluh)\n{'#' * 70}")
    print(f"  DoD teď: {now_avg:.0f}%   →   plošný strop (vše plochy dokresleno): {ceil_avg:.0f}%")
    print(f"  zbytek do 100 % = body + linie + kombi → čeká na Png2Point / Png2Line (neexistují)\n")
    print(f"  GAP podle geometrie (distinct chybějící 2017 cíle, union přes {len(MAPS)} mapy):")
    print(f"    {'geom':<8} {'#kódů':>5} {'obj.Σ':>7}  reconstructor")
    for g in GEOM_ORDER:
        if gap_codes.get(g):
            print(f"    {GEOM_CZ[g]:<8} {gap_codes[g]:>5} {gap_freq[g]:>7}  {RECON[g]}")


if __name__ == "__main__":
    if "--table" in sys.argv:
        run_table()
    elif "--dod" in sys.argv:        # ARCHIV: binární DoD pokrytí typů + analytický cut (Sez. 100)
        main()
    else:
        run_kpi()                    # PRIMÁRNÍ KPI (Sez. 100, volba uživatele)
