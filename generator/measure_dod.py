"""measure_dod.py — matched DoD driver: kolik ISOM symbolů vzorových map generátor SKUTEČNĚ nakreslí.

Operační půlka DoD brány (Sez. 94). `compare_isom.coverage()` sám potřebuje hotovou gen `.omap`;
tenhle driver ji matched VYROBÍ na obal každé reálné mapy z `resources/` a změří crosswalk-aware
pokrytí. DoD: fáze výroby `generator()` hotová až při ≥90 % ISOM (memory `generator-coverage-is-the-ceiling`).

  resources/<name>.pgw + .png  → 4 rohy skenu → S-JTSK axis-aligned obal → střed (WGS84) + rozměry
  generate_map(lat,lon,w_km,h_km, defaulty = vše real)  → maps/<name>/<name>.omap
  compare_isom.coverage(real, gen)  → crosswalk-aware X/Y matched (2000→2017, custom vyřazeno)

Dvě cesty (CLI):
  python generator/measure_dod.py          # (a) baseline: vše real (forest_age proxy zeleň), bez separace
  python generator/measure_dod.py --sep     # (b) separace-ze-skenu (forest_age=off): NÁLEZ Sez. 94 =
                                            #     páka KVALITY ne pokrytí (+403 −410 = net nula vs proxy)

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
from compare_isom import coverage         # noqa: E402  (crosswalk-aware, Sez. 94)
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


def run_sep() -> None:
    """Cesta (b): regeneruj 3 mapy SE separací-ze-skenu (forest_age='off') → změř lift vs baseline (a).

    NÁLEZ Sez. 94: separace je páka KVALITY ne pokrytí — na metrice kód-presence net-nula
    (+403 věrné open, −410 ztracené proxy-fight, který forest_age='off' vypnul)."""
    print(f"\n{'#' * 70}\nCESTA (b): separace-ze-skenu → lift matched DoD\n{'#' * 70}")
    for name in MAPS:
        base = REPO / "maps" / name / f"{name}.omap"            # baseline (a) = bez separace
        sep_out = REPO / "maps" / f"{name}_sep"
        sep_omap = sep_out / f"{sep_out.name}.omap"             # generate_map jmenuje .omap dle SLOŽKY
        if not sep_omap.exists():                               # skip-existing (drahá regenerace)
            lat, lon, w_km, h_km = _extent_from_pgw(name)
            sep_dir = sep_out / "sep"
            print(f"\n=== {name} === separace ze skenu…")
            predict = _separate_resources_to_sjtsk(name, sep_dir)
            print(f"  {len(predict)} predikčních ploch → generate_map (forest_age=off)")
            generate_map(lat, lon, w_km, h_km, out_dir=str(sep_out), ortho=False, tolerant=True,
                         forest_age="off", predict_areas_sjtsk=predict)
        ra = coverage(str(REPO / "resources" / f"{name}.omap"), str(base))
        rb = coverage(str(REPO / "resources" / f"{name}.omap"), str(sep_omap))
        new = sorted(set(rb["covered"]) - set(ra["covered"]))
        lost = sorted(set(ra["covered"]) - set(rb["covered"]))
        print(f">>> {name}: (a) {len(ra['covered'])}/{ra['denom']}={ra['pct']:.0f}%  →  "
              f"(b) {len(rb['covered'])}/{rb['denom']}={rb['pct']:.0f}%   "
              f"nové: {new or '—'}  ztracené: {lost or '—'}")


def main() -> None:
    per_map = []          # (name, coverage-dict)
    for name in MAPS:
        out = REPO / "maps" / name
        gen_omap = out / f"{name}.omap"
        if not gen_omap.exists():          # skip regeneraci, je-li gen.omap hotová (rychlé re-měření)
            lat, lon, w_km, h_km = _extent_from_pgw(name)
            print(f"\n{'=' * 70}\n{name}  výsek {w_km:.2f}×{h_km:.2f} km @ ({lat:.5f}, {lon:.5f})\n{'=' * 70}")
            generate_map(lat, lon, w_km, h_km, out_dir=str(out), ortho=False, tolerant=True)
        r = coverage(str(REPO / "resources" / f"{name}.omap"), str(gen_omap))
        print(f">>> {name}: ISOM {r['version']}, {len(r['covered'])}/{r['denom']} = {r['pct']:.0f}%"
              f"  (+{len(r['custom'])} custom vyřazeno)")
        per_map.append((name, r))

    # --- agregát ---
    print(f"\n{'#' * 70}\nMATCHED DoD BASELINE (crosswalk-aware, bez separace-ze-skenu)\n{'#' * 70}")
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


if __name__ == "__main__":
    if "--sep" in sys.argv:
        run_sep()
    else:
        main()
