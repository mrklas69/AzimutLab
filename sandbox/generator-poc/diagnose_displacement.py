#!/usr/bin/env python3
"""Diagnostika rozsahu kolizí pro displacement (kartografická generalizace L2).

Verify nástroj L2 (verify-against-source): kolik párů budova↔cesta a budova↔budova
padne pod ISOM minimální čitelnou mezeru 0,4 mm (≈ 1,83 px) na reálných lokalitách.
- KROK 0 (Sez. 21): rozhodl „enabler, nebo záclona?" PŘED návrhem algoritmu — naměřeno
  ~28/99 budov v kolizi (Č. Švýcarsko), dominuje budova↔cesta, shluky budov ~0.
- Po implementaci displacementu: spustit znovu → kolize mají klesnout (důkaz, ne dojem).

Znovupoužívá PRODUKČNÍ transformace generátoru (_sjtsk_to_grid, _grid_to_px,
_generalize_building) i konektor (fetch_*) → měří přesně tu geometrii, kterou render
vykreslí, ne aproximaci. Nic nekreslí, nic neexportuje.

Caveat měření: vzdálenost budova↔cesta se počítá k OSE cesty (ne k jejímu okraji);
skutečná mezera je o půl šířky cesty menší → reportované počty jsou DOLNÍ MEZ kolizí.
"""
from __future__ import annotations

import generator as G          # spustí top-level: connectors na sys.path, palette import
from dmr import build_bbox
from zabaged import (fetch_buildings, map_building_to_isom,
                     fetch_paths, map_to_isom,
                     fetch_water, map_water_to_isom)

GAP_PX = round(0.4 * G.PX_PER_MM, 2)        # ISOM min. čitelná mezera 0,4 mm v px (≈ 1,83)
BINS = [0.0, 1.0, GAP_PX, 3.0, 5.0, float("inf")]   # hrany histogramu vzdáleností [px]
LOCS = [("Ceske Svycarsko", 50.821, 14.671), ("Cesky raj", 50.53, 15.18)]


def _seg_seg_dist(a, b, c, d) -> float:
    """Nejmenší vzdálenost mezi úsečkami a-b a c-d [px]. 0 = protnutí/dotyk."""
    def sub(p, q): return (p[0] - q[0], p[1] - q[1])
    def dot(p, q): return p[0] * q[0] + p[1] * q[1]
    u, v, w = sub(b, a), sub(d, c), sub(a, c)
    duu, dvv, duv = dot(u, u), dot(v, v), dot(u, v)
    duw, dvw = dot(u, w), dot(v, w)
    den = duu * dvv - duv * duv
    if den > 1e-9:                          # nerovnoběžné → parametry nejbližšího bodu
        s = max(0.0, min(1.0, (duv * dvw - dvv * duw) / den))
    else:
        s = 0.0
    t = (duv * s + dvw) / dvv if dvv > 1e-9 else 0.0
    t = max(0.0, min(1.0, t))
    s = max(0.0, min(1.0, (duv * t - duw) / duu)) if duu > 1e-9 else 0.0
    px = (a[0] + s * u[0] - (c[0] + t * v[0]), a[1] + s * u[1] - (c[1] + t * v[1]))
    return (px[0] ** 2 + px[1] ** 2) ** 0.5


def _edges(poly, closed):
    """Hrany polylinie/prstence jako dvojice bodů (uzavře prstenec)."""
    pts = list(poly) + ([poly[0]] if closed and poly[0] != poly[-1] else [])
    return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def _bbox(poly, margin=0.0):
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)


def _bbox_far(b1, b2, thr):
    """True když se bboxy (rozšířené o thr) nepřekrývají → objekty určitě dál než thr."""
    return (b1[2] + thr < b2[0] or b2[2] + thr < b1[0] or
            b1[3] + thr < b2[1] or b2[3] + thr < b1[1])


def _poly_poly_dist(p, q, ep, eq):
    return min(_seg_seg_dist(a, b, c, d) for a, b in ep for c, d in eq)


def _histogram(dists):
    h = [0] * (len(BINS) - 1)
    for x in dists:
        for i in range(len(BINS) - 1):
            if BINS[i] <= x < BINS[i + 1]:
                h[i] += 1
                break
    return h


def _to_px_rings(feats, geo_bbox, generalize):
    """Feature ringy → px polygony (sdílí produkční transformace + příp. L1 generalizaci)."""
    out = []
    for f in feats:
        for ring in f["rings"]:
            px = [G._grid_to_px(*G._sjtsk_to_grid(x, y, geo_bbox)) for x, y in ring]
            if len(px) < 3:
                continue
            if generalize:
                px = G._generalize_building(px)
            out.append(px)
    return out


def _to_px_lines(feats, geo_bbox, code_fn):
    out = []
    for f in feats:
        if code_fn(f["layer"], f["props"]) is None:
            continue
        for line in f["lines"]:
            px = [G._grid_to_px(*G._sjtsk_to_grid(x, y, geo_bbox)) for x, y in line]
            if len(px) >= 2:
                out.append(px)
    return out


def diagnose(name, lat, lon):
    geo_bbox = build_bbox(lat, lon, G.GW, G.GH, G.TILE_M)
    b_feats = [f for f in fetch_buildings(lat, lon, G.GW, G.GH, G.TILE_M)
               if map_building_to_isom(f["layer"], f["props"]) is not None]
    buildings = _to_px_rings(b_feats, geo_bbox, generalize=True)
    paths = _to_px_lines(fetch_paths(lat, lon, G.GW, G.GH, G.TILE_M), geo_bbox, map_to_isom)
    wl, wa = fetch_water(lat, lon, G.GW, G.GH, G.TILE_M)
    water_lines = _to_px_lines(wl, geo_bbox, map_water_to_isom)
    fixed = [(pl, _edges(pl, False), _bbox(pl)) for pl in paths + water_lines]   # pevná síť
    bld = [(b, _edges(b, True), _bbox(b)) for b in buildings]

    print(f"\n=== {name} ({lat}, {lon}) ===")
    print(f"  budovy (po L1): {len(bld)} · cesty+voda linie (pevné): {len(fixed)}")

    # Budova ↔ pevná síť (cesty + vodní linie): vzdálenost obrysu budovy k OSE linie.
    bc, bc_hit = [], 0
    for b, eb, bb in bld:
        dmin = float("inf")
        for pl, ep, pb in fixed:
            if _bbox_far(bb, pb, 5.0):
                continue
            dmin = min(dmin, _poly_poly_dist(b, pl, eb, ep))
        if dmin < float("inf"):
            bc.append(dmin)
            if dmin < GAP_PX:
                bc_hit += 1

    # Budova ↔ budova: nejmenší mezera mezi dvojicemi.
    bb_d, bb_hit = [], set()
    for i in range(len(bld)):
        for j in range(i + 1, len(bld)):
            if _bbox_far(bld[i][2], bld[j][2], 5.0):
                continue
            d = _poly_poly_dist(bld[i][0], bld[j][0], bld[i][1], bld[j][1])
            bb_d.append(d)
            if d < GAP_PX:
                bb_hit.add(i)
                bb_hit.add(j)

    labels = [f"[0,{1.0})", f"[1,{GAP_PX})", f"[{GAP_PX},3)", "[3,5)", "[5,∞)"]
    print(f"  GAP_PX (0,4 mm) = {GAP_PX}")
    print(f"  budova↔síť (k ose): hist {dict(zip(labels, _histogram(bc)))}")
    print(f"     → budov s kolizí <{GAP_PX}px: {bc_hit}/{len(bld)}")
    print(f"  budova↔budova: hist {dict(zip(labels, _histogram(bb_d)))}")
    print(f"     → budov v kolizní dvojici <{GAP_PX}px: {len(bb_hit)}/{len(bld)}"
          f" · dotyk/překryv (<0,3px): {sum(1 for d in bb_d if d < 0.3)} párů")


if __name__ == "__main__":
    for n, la, lo in LOCS:
        try:
            diagnose(n, la, lo)
        except Exception as e:
            print(f"\n=== {n} === SELHALO: {type(e).__name__}: {e}")
