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

Tři režimy (CLI):
  python generator/measure_dod.py          # BASELINE: separace-ze-skenu (forest_age=off) + analytický cut
  python generator/measure_dod.py --table  # KOMPAS: orig vs gen Σ objektů per ISOM kód, 3 kapitoly geom (Sez. 96)
  python generator/measure_dod.py --proxy  # doložení: forest_age proxy NADHODNOCUJE vs separace (fiktivní 410)

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
from compare_isom import (coverage, _load_crosswalk, _resolve_targets, detect_version,   # noqa: E402
                          isom_usage, used_geometry)   # crosswalk-aware Sez. 94; used_geom + tabulka Sez. 96
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


def run_table() -> None:
    """--table: KOMPAS pokrytí (Sez. 96). Tři kapitoly (Png2Area/Png2Line/Png2Point), řádky = ISOM
    2017-2 kódy, sloupce = Σ objektů ORIG (reálné `.omap`) vs GEN (separační gen `.omap`) přes MAPS.

    Proč nad rámec DoD %: DoD je binární (kreslí ≥1 objekt = pokryto), ale poměr orig:gen ukazuje
    PROPORCE — přibližujeme se k cíli ve správné četnosti, nebo přestřelujeme/podstřelujeme? Nálezy
    Sez. 96: gen PŘESTŘELUJE 520/521/cesty (hustá ČÚZK projekce na obal výseku) a PODSTŘELUJE
    vegetaci (403/406/408 — pattern třídy 402/404 splývají do base odstínů, separace pattern-slepá).
    Cíl generátoru = přiblížit gen k orig; symboly co data nedají → generovat věrohodně do statistické
    míry četnosti z této tabulky (volba uživatele Sez. 96). Geometrie z reálné mapy (`used_geom`)."""
    cw, v2000, v2017 = _load_crosswalk()
    orig, gen = Counter(), Counter()      # 2017 kód → Σ objektů (reálné / gen)
    geom_t, names = {}, {}                # 2017 kód → Counter(geom) z reálné mapy / jméno
    for name in MAPS:
        gen_omap = _gen_sep(name, REPO / "maps" / name)        # separační baseline (skip-existing)
        real_path = str(REPO / "resources" / f"{name}.omap")
        ver = detect_version(real_path)
        real, rnames = isom_usage(real_path)
        ug = used_geometry(real_path)                          # reálný kód → geom (point/area/line…)
        g, _ = isom_usage(str(gen_omap))                       # gen kódy = 2017-2 (identita)
        for c, n in g.items():
            gen[c] += n
        for c, n in real.items():                              # reálné kódy → 2017-2 cíl crosswalkem
            targets = _resolve_targets(c, ver, cw, v2000, v2017)
            if not targets:                                    # custom (None) nebo bez cíle → vyřaď
                continue
            key = sorted(targets)[0]                           # primární 2017 cíl (jako measure_dod main)
            orig[key] += n
            geom_t.setdefault(key, Counter())[ug.get(c, "?")] += n
            names.setdefault(key, rnames.get(c, ""))

    all_codes = set(orig) | set(gen)
    # geom: majorita z reálné mapy; kódy jen-v-gen (v reálných mapách nejsou) → '?'
    geom = {c: (geom_t[c].most_common(1)[0][0] if c in geom_t else "?") for c in all_codes}
    sections = [("Png2Area  (plocha)", "area"), ("Png2Line  (linie)", "line"),
                ("Png2Point (bod)", "point")]
    print(f"KOMPAS pokrytí — orig (reálné .omap) vs gen (separace) přes {len(MAPS)} mapy {MAPS}")
    print("legenda: ✓ orig i gen · · chybí v gen · + jen gen")
    for title, gkey in sections:
        codes = sorted([c for c in all_codes if geom[c] == gkey], key=lambda c: -orig[c])
        sum_o = sum(orig[c] for c in codes)
        sum_g = sum(gen[c] for c in codes)
        n_cov = sum(1 for c in codes if orig[c] > 0 and gen[c] > 0)
        n_orig = sum(1 for c in codes if orig[c] > 0)
        print(f"\n{'=' * 60}\n{title}   [pokryto {n_cov}/{n_orig} kódů, orig Σ{sum_o}  gen Σ{sum_g}]\n{'=' * 60}")
        print(f"  {'kód':>5} {'orig':>6} {'gen':>6}    jméno")
        for c in codes:
            o, gg = orig[c], gen[c]
            mark = "✓" if o > 0 and gg > 0 else ("+" if gg > 0 else "·")
            print(f"  {c:>5} {o:>6} {gg:>6}  {mark} {names.get(c, '')[:40]}")
    other = sorted([c for c in all_codes if geom[c] not in ("area", "line", "point")],
                   key=lambda c: -orig[c])
    if other:
        print(f"\n{'-' * 60}\nostatní (kombi/text/jen-gen): " +
              " ".join(f"{c}(o{orig[c]}/g{gen[c]})" for c in other))


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
    if "--proxy" in sys.argv:
        run_proxy()
    elif "--table" in sys.argv:
        run_table()
    else:
        main()
