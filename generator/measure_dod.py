"""measure_dod.py — matched DoD driver: kolik ISOM symbolů vzorových map generátor SKUTEČNĚ nakreslí.

Operační půlka DoD brány (Sez. 94). `compare_isom.coverage()` sám potřebuje hotovou gen `.omap`;
tenhle driver ji matched VYROBÍ na obal každé reálné mapy z `resources/` a změří crosswalk-aware
pokrytí. DoD: fáze výroby `generator()` hotová až při ≥90 % ISOM (memory `generator-coverage-is-the-ceiling`).

  resources/<name>.pgw + .png  → 4 rohy skenu → S-JTSK axis-aligned obal → střed (WGS84) + rozměry
  generate_map(lat,lon,w_km,h_km, defaulty = vše real)  → maps/<name>/<name>.omap
  compare_isom.coverage(real, gen)  → crosswalk-aware X/Y matched (2000→2017, custom vyřazeno)

BASELINE = SEPARACE (Sez. 95, volba uživatele). `pairs.build_pair` vyrábí páry separací-ze-skenu
(`predict_areas_sjtsk`), NE forest_age proxy → DoD baseline MUSÍ měřit reálnou produkční cestu, ne
fikci. forest_age proxy 410 byl FABRIKACE: měření Sez. 95 ukázalo, že souvislé 410 plochy v 5 mapách
NEJSOU (1000+ komponent o max <100 px = tmavě zelený antialiasing, ne mapovatelná fight plocha) →
separace ho poctivě nemá. 403 Rough open separace vrací věrně (odstín uvnitř open, Sez. 92).

Dva režimy (CLI):
  python generator/measure_dod.py          # BASELINE: separace-ze-skenu (forest_age=off) + analytický cut
  python generator/measure_dod.py --proxy   # doložení: forest_age proxy NADHODNOCUJE vs separace (fiktivní 410)

A3 (Sez. 94): Slovanka2016 (UTM33 — jiný transformer) + Soví vrch (domapováno ~1/4 → neúplná real
.omap zkreslí dolů) VYNECHÁNY z DoD → měří jen Bedřichovka/Blatná/Velbloud. Až bude UTM33 cesta /
Soví vrch domapováno, doplnit do MAPS. Spouštět z kořene přes .venv (sys.path skript, fáze B).
"""
import sys
import pathlib
from collections import Counter

import numpy as np
from PIL import Image

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "connectors"))
sys.path.insert(0, str(REPO / "generator"))

from pyproj import Transformer            # noqa: E402
from generator import generate_map        # noqa: E402
from compare_isom import coverage, symbol_geometry   # noqa: E402  (crosswalk-aware, Sez. 94; geom Sez. 95)
from separate import separate_areas, TARGET_MPP  # noqa: E402  (cesta b: separace-ze-skenu)
from map_gt import segment_gt             # noqa: E402  (runnability GT z resources skenu)

try:
    sys.stdout.reconfigure(encoding="utf-8")   # Windows cp1250 vs Unicode
except Exception:
    pass

Image.MAX_IMAGE_PIXELS = None
_SJTSK_TO_WGS84 = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)

MAPS = ["Bedřichovka", "Blatná", "Velbloud"]   # A3: Slovanka(UTM33)+Soví vrch(1/4) vynechány


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
    segment_gt(sep_dir / "map.png", out_dir=sep_dir)     # → gt_labels.png (runnability 0-4/255)
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


def _gen_sep(name: str, out: pathlib.Path) -> pathlib.Path:
    """Matched gen .omap SE SEPARACÍ-ZE-SKENU (Sez. 95 baseline = reálná produkční cesta párů).

    `pairs.build_pair` vyrábí páry separací (predict_areas_sjtsk), ne forest_age → DoD MUSÍ měřit
    separaci. forest_age='off' (proxy 410 = fabrikace, Sez. 95). Skip-existing (drahá regenerace:
    map_gt na obřím skenu + separace)."""
    omap = out / f"{name}.omap"
    if omap.exists():                                      # skip regeneraci (rychlé re-měření)
        return omap
    lat, lon, w_km, h_km = _extent_from_pgw(name)
    print(f"\n{'=' * 70}\n{name}  výsek {w_km:.2f}×{h_km:.2f} km @ ({lat:.5f}, {lon:.5f}) — separace ze skenu\n{'=' * 70}")
    predict = _separate_resources_to_sjtsk(name, out / "sep")
    print(f"  {len(predict)} predikčních ploch → generate_map (forest_age=off)")
    generate_map(lat, lon, w_km, h_km, out_dir=str(out), ortho=False, tolerant=True,
                 forest_age="off", predict_areas_sjtsk=predict)
    return omap


def run_proxy() -> None:
    """--proxy: doloží, že forest_age proxy NADHODNOCUJE pokrytí vs separační baseline (Sez. 95).

    Separace = pravdivý baseline (maps/<name>/). forest_age proxy (maps/<name>_proxy/) přidá FIKTIVNÍ
    410 (souvislé 410 plochy v mapách nejsou — Sez. 95 měření). Ukáže, které kódy proxy „pokrývá" jen
    fabrikací (jen proxy) vs co separace věrně přidá (jen separace). Opak orientace Sez. 94."""
    print(f"\n{'#' * 70}\n--proxy: forest_age proxy vs separační baseline (doložení nadhodnocení)\n{'#' * 70}")
    for name in MAPS:
        sep_omap = _gen_sep(name, REPO / "maps" / name)        # baseline = separace
        proxy_out = REPO / "maps" / f"{name}_proxy"
        proxy_omap = proxy_out / f"{proxy_out.name}.omap"      # generate_map jmenuje .omap dle SLOŽKY
        if not proxy_omap.exists():                            # forest_age cesta (a), default vše real
            lat, lon, w_km, h_km = _extent_from_pgw(name)
            generate_map(lat, lon, w_km, h_km, out_dir=str(proxy_out), ortho=False, tolerant=True)
        rs = coverage(str(REPO / "resources" / f"{name}.omap"), str(sep_omap))
        rp = coverage(str(REPO / "resources" / f"{name}.omap"), str(proxy_omap))
        only_proxy = sorted(set(rp["covered"]) - set(rs["covered"]))   # proxy „pokrývá" navíc = fikce
        only_sep = sorted(set(rs["covered"]) - set(rp["covered"]))     # separace přidává navíc = věrné
        print(f">>> {name}: separace {len(rs['covered'])}/{rs['denom']}={rs['pct']:.0f}%  "
              f"proxy {len(rp['covered'])}/{rp['denom']}={rp['pct']:.0f}%   "
              f"jen proxy (fikce): {only_proxy or '—'}  jen separace (věrné): {only_sep or '—'}")


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
    for name, r in per_map:
        seen_keys = set()                              # dedup per mapa (víc 2000 kódů → týž 2017 cíl)
        for real_c, targets, freq, nm in r["missing"]:
            key = targets[0] if targets else real_c    # primární 2017 cíl
            miss_freq[key] += freq
            miss_name.setdefault(key, nm)
            if key not in seen_keys:                    # #map = v kolika MAPÁCH cíl chybí (1× per mapa)
                miss_maps[key] += 1
                seen_keys.add(key)
    print(f"\nCHYBÍ napříč {len(MAPS)} mapami (2017-2 kód, dle #map pak Σobjektů):")
    print(f"  {'2017':>5} {'#map':>4} {'obj.Σ':>7}  jméno (z reálné mapy)")
    for c in sorted(miss_maps, key=lambda c: (-miss_maps[c], -miss_freq[c])):
        print(f"  {c:>5} {miss_maps[c]:>4} {miss_freq[c]:>7}  {miss_name.get(c, '')[:42]}")

    # --- ANALYTICKÝ CUT (Sez. 95): rozpad DoD podle geometrie symbolu ---
    # Cíl: kolik z 90 % DoD je dosažitelné PLOŠNÝM generátorem TEĎ (Png2Area existuje) vs co je
    # strukturálně mimo (body→Png2Point, linie→Png2Line — ani jeden zatím neexistuje).
    geom = symbol_geometry()                          # 2017-2 kód → 'area'/'line'/'point'/…
    GEOM_CZ = {"area": "plocha", "line": "linie", "point": "bod",
               "combined": "kombi", "text": "text", "?": "neznámé"}
    RECON = {"area": "Png2Area ✓ (existuje)", "line": "Png2Line — (chybí)",
             "point": "Png2Point — (chybí)", "combined": "kombi → liniový", "text": "popisek",
             "?": "mimo template"}
    GEOM_ORDER = ["area", "line", "point", "combined", "text", "?"]

    # (1) Plošný strop = per-mapa pokrytí, KDYBY gen dokreslil všechny chybějící PLOCHY; pak průměr.
    #     DoD je per-mapa průměr → strop počítám stejně (ne union), ať jsou čísla srovnatelná.
    ceil_pcts = []
    for name, r in per_map:
        n_miss_area = sum(1 for _, tg, _, _ in r["missing"] if tg and geom.get(tg[0]) == "area")
        ceil = 100 * (len(r["covered"]) + n_miss_area) / r["denom"] if r["denom"] else 0
        ceil_pcts.append(ceil)
    now_avg = sum(pcts) / len(pcts)
    ceil_avg = sum(ceil_pcts) / len(ceil_pcts)

    # (2) Gap podle geometrie: distinct chybějící 2017 cíle (union přes mapy) + Σobjektů.
    gap_codes, gap_freq = Counter(), Counter()        # geometrie → #kódů / Σobjektů
    for c in miss_maps:                               # miss_maps = union chybějících 2017 cílů
        g = geom.get(c, "?")
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
    if "--proxy" in sys.argv:
        run_proxy()
    else:
        main()
