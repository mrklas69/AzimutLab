#!/usr/bin/env python3
"""Strojové porovnání generátoru s živě mapovanou OB mapou (verify-against-source, Sez. 37).

Vstup: generátorový výstup (rgb.png + rgb.pgw + meta.json) a reálná mapa (.png + .pgw + .omap)
z resources/. Funguje jen pro lokalitu, kde reálnou mapu máme — zatím Soví vrch (= terénně
mapováno uživatelem, autoritativní ground-truth).

Dvě statistiky:
  STAT 1 — symbolový crosswalk + pokrytí. Reálná mapa je v ISOM 2000 číslování, generátor v
           ISOM 2017-2 → naivní kód-na-kód selže. Crosswalk mapuje SÉMANTIKU (prvek), ne číslo.
  STAT 2 — prostorová shoda po ISOM barvách přes překryv (raster, gen rozlišení). Precision =
           kolik gen-kresby leží u reálné; recall = kolik reálné kresby pokryl gen; + IoU.

Záměrně dependency-light (jen numpy + PIL + stdlib XML) — scipy/shapely v prostředí nejsou.
"""
import math
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
sys.stdout.reconfigure(encoding="utf-8")   # Windows konzole je cp1250 → unicode (✓ ↔ m²) by padlo

REPO = Path(__file__).resolve().parents[1]          # generator/ je 1 pod kořenem LAB (Sez. 39)
# Pozn.: DEV_LOCATIONS["SV"] = "Soví Vrch" (Title-Case), resources má "Soví vrch.png" (malé v)
# — nekonzistence kapitalizace = otevřený carry-over úkol, ne sjednocovat tady. GEN_DIR musí
# sedět na to, co generátor vytvoří (maps/<lokalita> = "Soví Vrch").
GEN_DIR = REPO / "maps" / "Soví Vrch"                # generovaný výstup lokality (maps/<lokalita>)
REAL_PNG = REPO / "resources" / "Soví vrch.png"
REAL_PGW = REPO / "resources" / "Soví vrch.pgw"
REAL_OMAP = REPO / "resources" / "Soví vrch.omap"

# --- generátorové schopnosti (ISOM 2017-2): co dnes umíme vyrobit, seskupené po prvcích ---
# (kód → krátký popis); slouží k vyhodnocení pokrytí proti reálné mapě
GEN_CAPABILITIES = {
    "contour": ["101", "102", "103"],
    "knoll/depr": ["109", "110", "111"],
    "rock/boulder": ["204", "206", "207"],
    "water": ["301", "301.1", "304", "305", "306"],
    "paved": ["501"],
    "road/path": ["502", "503", "504", "505", "506"],
    "forest ride": ["508"],
    "railway": ["509"],
    "powerline": ["510"],
    "bridge/tunnel": ["512", "512.2"],
    "building": ["521"],
}

# --- sémantický crosswalk: prvek → reálné ISOM2000 kódy v Soví vrch.omap ---
# (skupina sdílů reálné mapy, kterou tatáž generátorová schopnost reprezentuje)
CROSSWALK = {
    "contour": ["101", "102", "103"],                        # vrstevnice: stejné číslování
    "knoll/depr": ["112", "113", "115", "116"],              # kupky/prohlubně (2017: 109/110/111)
    "rock/boulder": ["204", "206", "206.1", "207", "209", "209.1", "210", "210.1"],  # balvany/kamenitý povrch
    "water": ["301", "302", "305", "306", "307"],            # jezero/rybníček + toky/příkopy
    "paved": ["529", "529.1"],                               # dlážděná plocha
    "road/path": ["502", "503", "504", "505", "506", "507", "508"],  # silnice→pěšina (2017 posun!)
    "forest ride": ["509"],                                  # průsek (2017: 508 Narrow ride!)
    "railway": [],                                           # v této mapě žádná železnice
    "powerline": [],                                         # v této mapě žádné el. vedení
    "bridge/tunnel": ["512", "518"],                         # lávka + tunel
    "building": ["526", "526.1", "527"],                    # budova + sídliště
}


def _strip(tag: str) -> str:
    return tag.split("}")[-1]


def parse_real_omap(path: Path):
    """Vrátí (scale, {code: {kind,count,len_m,area_m2}}) z reálného .omap."""
    root = ET.parse(path).getroot()
    geo = next(e for e in root.iter() if _strip(e.tag) == "georeferencing")
    scale = int(geo.get("scale"))
    u2m = scale / 1e6  # 1/1000 mm papíru → metry terénu
    sp = next(e for e in root.iter() if _strip(e.tag) == "symbols")
    sym = []
    for s in sp:
        if _strip(s.tag) != "symbol":
            continue
        kind = next((_strip(c.tag).replace("_symbol", "") for c in s
                     if _strip(c.tag).endswith("symbol")), "?")
        sym.append((s.get("code"), kind))
    op = next(e for e in root.iter() if _strip(e.tag) == "objects")
    stat = defaultdict(lambda: {"kind": "", "count": 0, "len_m": 0.0, "area_m2": 0.0})
    for o in op.iter():
        if _strip(o.tag) != "object":
            continue
        si = int(o.get("symbol", -1))
        if not (0 <= si < len(sym)):
            continue
        code, kind = sym[si]
        c = next((x for x in o if _strip(x.tag) == "coords"), None)
        rec = stat[code]
        rec["kind"] = kind
        rec["count"] += 1
        if c is None or not c.text:
            continue
        pts = []
        for tok in c.text.strip().split(";"):
            nums = tok.split()
            if len(nums) >= 2:
                try:
                    pts.append((int(nums[0]), int(nums[1])))
                except ValueError:
                    pass
        if len(pts) >= 2:
            rec["len_m"] += sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                                for i in range(len(pts) - 1)) * u2m
            if kind == "area" and len(pts) >= 3:
                rec["area_m2"] += abs(sum(pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1]
                                          for i in range(-1, len(pts) - 1))) / 2 * u2m * u2m
    return scale, stat


def _read_pgw(path: Path):
    return [float(x) for x in path.read_text(encoding="utf-8").split()]


def forward_classify_real(real_rgb, real_pgw, gen_pgw, gen_shape):
    """Forward-map: KAŽDÝ reálný pixel → gen pixel (po blocích) → třída barvy do gen mřížky.

    Forward (ne backward) zachová tenké linie: gen pixel je dané barvy, pokud do něj padne
    aspoň jeden reálný pixel té barvy (jinak nearest-vzorkování ~23× downsample vrstevnice
    zahodí). Vrací (real_masks: {color: bool gen-grid}, coverage: kolik reálných px padlo do gen px).
    """
    H, W = gen_shape
    Ag, _, _, Eg, Cg, Fg = gen_pgw          # gen bez rotace
    A, D, B, E, C, F = real_pgw
    rh, rw = real_rgb.shape[:2]
    keys = list(ISOM_REF)
    refs = np.array([ISOM_REF[k] for k in keys], dtype=np.int32)
    grp_of = np.array([GROUP[k] for k in keys])
    colors = sorted(set(GROUP.values()))
    masks = {c: np.zeros((H, W), dtype=bool) for c in colors}
    coverage = np.zeros((H, W), dtype=np.int32)
    cols = np.arange(rw)
    for r0 in range(0, rh, 1000):           # bloky řádků (paměť)
        r1 = min(r0 + 1000, rh)
        rows = np.arange(r0, r1)
        cc, rr = np.meshgrid(cols, rows)
        X = A * cc + B * rr + C             # real px → world (s rotací)
        Y = D * cc + E * rr + F
        gc = np.round((X - Cg) / Ag).astype(np.int32)   # world → gen px (bez rotace)
        gr = np.round((Y - Fg) / Eg).astype(np.int32)
        ok = (gc >= 0) & (gc < W) & (gr >= 0) & (gr < H)
        block = real_rgb[r0:r1].reshape(-1, 3).astype(np.int32)   # int32: viz classify()
        d = ((block[:, None, :] - refs[None, :, :]) ** 2).sum(2)
        cls = grp_of[d.argmin(1)].reshape(r1 - r0, rw)
        gcf, grf, clsf, okf = gc[ok], gr[ok], cls[ok], ok[ok]
        np.add.at(coverage, (grf, gcf), 1)
        for c in colors:
            sel = clsf == c
            if sel.any():
                masks[c][grf[sel], gcf[sel]] = True
    return masks, coverage


# ISOM referenční barvy (RGB) pro klasifikaci pixelů nejbližší barvou
ISOM_REF = {
    "white": (255, 255, 255), "yellow": (252, 221, 118), "road": (240, 170, 120),
    "brown": (191, 105, 37), "blue": (50, 162, 222), "black": (30, 30, 30),
    "green_l": (200, 232, 200), "green_m": (120, 200, 140), "green_d": (40, 160, 90),
}
# sloučení jemných tříd do ISOM barevných skupin. road (oranžová výplň silnic) → open: na
# reálné mapě splývá s ISOM žlutou otevřené půdy (401/403), gen ji skoro nemá → čistší veg. mezera.
GROUP = {"white": "white", "yellow": "open", "road": "open", "brown": "brown",
         "blue": "blue", "black": "black", "green_l": "green", "green_m": "green",
         "green_d": "green"}


def classify(rgb):
    """Každý pixel → index ISOM barevné skupiny (nejbližší referenční barva)."""
    keys = list(ISOM_REF)
    refs = np.array([ISOM_REF[k] for k in keys], dtype=np.int32)
    flat = rgb.reshape(-1, 3).astype(np.int32)   # int32: (255²·3) přeteče int16!
    # vzdálenost k referencím (N×K), argmin
    d = ((flat[:, None, :] - refs[None, :, :]) ** 2).sum(2)
    idx = d.argmin(1)
    groups = np.array([GROUP[k] for k in keys])
    return groups[idx].reshape(rgb.shape[:2])


def dilate(mask, r):
    """Boolean dilatace o r px (OR posunů; bez scipy)."""
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def main():
    scale, real_stat = parse_real_omap(REAL_OMAP)
    gen_rgb = np.asarray(Image.open(GEN_DIR / "rgb.png").convert("RGB"))
    gen_pgw = _read_pgw(GEN_DIR / "rgb.pgw")
    real_rgb = np.asarray(Image.open(REAL_PNG).convert("RGB"))
    real_pgw = _read_pgw(REAL_PGW)
    real_masks, coverage = forward_classify_real(real_rgb, real_pgw, gen_pgw, gen_rgb.shape[:2])
    valid = coverage > 0
    px_area = abs(gen_pgw[0] * gen_pgw[3])  # m²/px
    foot_km2 = valid.sum() * px_area / 1e6

    print("=" * 78)
    print(f"POROVNÁNÍ: generátor (ISOM 2017-2) ↔ Soví vrch (živě mapováno, ISOM {scale and '2000'})")
    print(f"překryv (footprint reálné mapy uvnitř gen výseku): {foot_km2:.2f} km²,"
          f" {valid.sum()} px @ {math.sqrt(px_area):.2f} m/px")
    print("=" * 78)

    print("\nSTAT 1 — SYMBOLOVÝ CROSSWALK + POKRYTÍ (sémantika, ne číslo)")
    print(f"{'prvek':<15}{'gen 2017':<12}{'real 2000 (kódy)':<26}{'real ks':>8}{'real m/m²':>12}")
    print("-" * 78)
    covered_codes = set()
    for grp, gen_codes in GEN_CAPABILITIES.items():
        real_codes = CROSSWALK.get(grp, [])
        covered_codes.update(real_codes)
        n = sum(real_stat[c]["count"] for c in real_codes)
        kind_area = any(real_stat[c]["kind"] == "area" for c in real_codes)
        mag = (sum(real_stat[c]["area_m2"] for c in real_codes) if kind_area
               else sum(real_stat[c]["len_m"] for c in real_codes))
        unit = "m²" if kind_area else "m"
        rc = ",".join(real_codes) if real_codes else "—"
        status = "✓" if n else "○ (real 0)"
        print(f"{grp:<15}{('/'.join(gen_codes))[:11]:<12}{rc[:25]:<26}{n:>8}{mag:>10.0f}{unit:>2}  {status}")

    # co živý mapař nakreslil, ale generátor NEUMÍ (mezery)
    print("\nMEZERY — symboly v reálné mapě, které generátor zatím neprodukuje:")
    gap = defaultdict(lambda: {"count": 0, "mag": 0.0, "kind": ""})
    GAP_NAMES = {  # ISOM2000 kód → český název (z .omap), jen ty zajímavé skupiny
        "veg": ["401", "402", "403", "404", "405", "406", "407", "408", "409", "410", "410.1",
                "412", "415", "416", "418", "419", "420"],
        "rock-detail": ["106", "106.1", "106.2", "201", "201.1", "201.2", "202", "203", "203.1",
                        "205", "212"],
        "fence/wall": ["522", "523", "524"],
        "point-manmade": ["104", "532", "536", "537", "538", "540"],
        "water-point": ["312", "313", "314"],
    }
    for grp, codes in GAP_NAMES.items():
        n = sum(real_stat[c]["count"] for c in codes)
        a = sum(real_stat[c]["area_m2"] for c in codes)
        ln = sum(real_stat[c]["len_m"] for c in codes)
        mag = f"{a:.0f} m²" if a > ln else f"{ln:.0f} m"
        print(f"  {grp:<16} {n:>4} objektů  ({mag})")

    print("\nSTAT 2 — PROSTOROVÁ SHODA PO ISOM BARVÁCH (přes překryv, gen rozlišení, tol ~4 m)")
    gen_cls = classify(gen_rgb)
    tol = 2  # ~4,4 m tolerance při 2,18 m/px
    print(f"{'barva':<10}{'real %':>8}{'gen %':>8}{'precision':>11}{'recall':>9}{'IoU':>7}  pozn.")
    print("-" * 78)
    NOTE = {"brown": "vrstevnice+terén", "blue": "voda", "black": "cesty/stavby/skály",
            "green": "vegetace (gen nemá)", "open": "otevř. prostor (gen nemá)",
            "road": "silnice výplň", "white": "les/průběžný"}
    for color in ["brown", "blue", "black", "green", "open", "white"]:
        rm = real_masks[color] & valid
        gm = (gen_cls == color) & valid
        rp = 100 * rm.sum() / valid.sum()
        gp = 100 * gm.sum() / valid.sum()
        if gm.sum() and rm.sum():
            prec = 100 * (gm & dilate(rm, tol)).sum() / gm.sum()
            rec = 100 * (rm & dilate(gm, tol)).sum() / rm.sum()
            iou = 100 * (gm & rm).sum() / (gm | rm).sum()
            stats = f"{prec:>10.0f}%{rec:>8.0f}%{iou:>6.0f}%"
        else:
            stats = f"{'—':>11}{'—':>9}{'—':>7}"
        print(f"{color:<10}{rp:>7.1f}%{gp:>7.1f}%{stats}  {NOTE.get(color,'')}")


if __name__ == "__main__":
    main()
