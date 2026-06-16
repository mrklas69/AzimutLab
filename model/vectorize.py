"""vectorize.py — sdílený postprocess reconstructorů: maska linií → polyline (Sez. 132).

Role v pipeline (rozhodnuto Sez. 130, IDEAS „Png2Line — segmentace + odložená vektorizace"):
neuronový Png2Line vrací jen SEGMENTACI (dilatovanou masku linií, jako Png2Area vrací area rastr).
Převod masky na vektorové polyline = tenhle samostatný „.omap assembly" krok, sdílený mezi reconstructory
(line → polyline; area → polygon a point → hotovo přijdou později). Záměrně MIMO model (KISS, čistá
geometrie numpy/skimage, žádná torch závislost).

Pipeline (crude první verze, dle IDEAS):
  1. skeletonize — dilatovaná maska (GT_LINE_WIDTH_PX ~3 px) → 1px kostra (izomorf Png2Point: nafouklý
     bod → peak; tady nafouklá linie → kostra). Branžový standard (Zhang-Suen/Lee, skimage).
  2. kostra → graf → trasy: pixel se stupněm (počet 8-sousedů) ≠ 2 je UZEL (endpoint=1, junkce≥3);
     mezi uzly vedou řetězce deg-2 pixelů = jednotlivé polyline. Čisté smyčky (samé deg-2) trasujeme zvlášť.
  3. RDP (Ramer–Douglas–Peucker) — zjednoduší řetězec pixelů na pár vrcholů (standard pro polyline; OOM
     `.omap` ukládá lomené body, ne každý pixel).

Známá omezení (MĚŘENÁ, ne skrytá — IDEAS): dashed linie (508 = krok 2) se rozpadnou na úseky (chybí
gap-bridging); křížení/junkce řešíme hrubě (rozseknutím na uzlu), ne dopojením průběžné linie.
"""
import numpy as np
from scipy.ndimage import convolve
from skimage.morphology import skeletonize


# 3×3 jádro pro počítání 8-sousedů (střed 0 = pixel sám se nepočítá)
_NB8 = np.array([[1, 1, 1],
                 [1, 0, 1],
                 [1, 1, 1]], dtype=np.uint8)


def _rdp(points: list[tuple[float, float]], eps: float) -> list[tuple[float, float]]:
    """Ramer–Douglas–Peucker: zjednoduš polyline tak, aby žádný vypuštěný bod neležel dál než `eps`
    od úsečky mezi ponechanými body. Iterativní (zásobník místo rekurze — dlouhé toky by rekurzi přetekly).

    Vrací podseznam `points` (vždy se zachová první a poslední bod). eps v px (jako tolerance v rastru)."""
    n = len(points)
    if n < 3:
        return list(points)
    keep = [False] * n
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]                       # úseky (start, end) k prozkoumání
    while stack:
        i0, i1 = stack.pop()
        if i1 <= i0 + 1:
            continue
        x0, y0 = points[i0]
        x1, y1 = points[i1]
        dx, dy = x1 - x0, y1 - y0
        seg = (dx * dx + dy * dy) ** 0.5
        # největší kolmá vzdálenost bodu uvnitř úseku od přímky (x0,y0)-(x1,y1)
        dmax, idx = -1.0, -1
        for i in range(i0 + 1, i1):
            px, py = points[i]
            if seg < 1e-9:                     # degenerovaný úsek (start=end) → vzdálenost = euklidovská
                d = ((px - x0) ** 2 + (py - y0) ** 2) ** 0.5
            else:                              # |kříž. součin| / délka = kolmá vzdálenost
                d = abs(dx * (y0 - py) - (x0 - px) * dy) / seg
            if d > dmax:
                dmax, idx = d, i
        if dmax > eps:                         # bod dost daleko → ponech a rozděl úsek na dvě půlky
            keep[idx] = True
            stack.append((i0, idx))
            stack.append((idx, i1))
    return [points[i] for i in range(n) if keep[i]]


def _trace_chains(skel: np.ndarray) -> list[list[tuple[int, int]]]:
    """Kostru (bool 1px) rozloží na řetězce pixelů mezi uzly. Vrací seznam cest [(row,col), ...].

    Stupeň pixelu = počet 8-sousedů na kostře. Uzel = stupeň ≠ 2 (endpoint=1, junkce≥3, izolovaný=0).
    Od každého uzlu vyjdeme do každého sousedního pixelu a jdeme po deg-2 řetězci, dokud nedorazíme
    k dalšímu uzlu — tím vznikne jedna polyline. Hrany značíme jako navštívené (množina párů pixelů),
    ať se každý segment trasuje právě jednou (z obou konců by jinak vznikl duplikát)."""
    sk = skel.astype(bool)
    deg = convolve(sk.astype(np.uint8), _NB8, mode="constant", cval=0) * sk   # stupeň jen na kostře
    H, W = sk.shape

    def neighbors(r, c):
        # 8-okolí na kostře (ošetř okraje rastru)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = r + dr, c + dc
                if 0 <= rr < H and 0 <= cc < W and sk[rr, cc]:
                    yield rr, cc

    nodes = (deg != 2) & sk                    # uzly: endpointy + junkce + izolované
    visited_edges = set()                      # nasměrovaná hrana značíme oběma orientacemi
    chains = []

    def walk(start, first):
        """Sleduj řetězec od uzlu `start` přes souseda `first` až k dalšímu uzlu. Vrátí cestu nebo None,
        je-li první hrana už navštívená."""
        if (start, first) in visited_edges:
            return None
        path = [start, first]
        visited_edges.add((start, first))
        visited_edges.add((first, start))
        prev, cur = start, first
        while not nodes[cur]:                  # dokud jsme na deg-2 pixelu, pokračuj
            nxt = next((p for p in neighbors(*cur) if p != prev), None)
            if nxt is None:                    # slepá ulička (nemělo by u deg-2 nastat) → konec
                break
            visited_edges.add((cur, nxt))
            visited_edges.add((nxt, cur))
            path.append(nxt)
            prev, cur = cur, nxt
        return path

    # 1) řetězce vycházející z uzlů
    node_coords = list(zip(*np.where(nodes)))
    for r, c in node_coords:
        if deg[r, c] == 0:                     # izolovaný pixel = nic k trasování
            continue
        for nb in neighbors(r, c):
            p = walk((r, c), nb)
            if p is not None and len(p) >= 2:
                chains.append(p)

    # 2) čisté smyčky bez uzlů (každý pixel deg-2) — nezachytí je krok 1; projdi zbylé nenavštívené
    loop_pixels = (deg == 2) & sk
    for r, c in zip(*np.where(loop_pixels)):
        for nb in neighbors(r, c):
            if ((r, c), nb) not in visited_edges:
                p = walk((r, c), nb)
                if p is not None and len(p) >= 2:
                    chains.append(p)
    return chains


def mask_to_polylines(mask: np.ndarray, rdp_eps: float = 2.0,
                      min_len_px: float = 3.0) -> list[list[tuple[float, float]]]:
    """Binární maska linií → seznam polyline [(x,y), ...] v px (x=sloupec, y=řádek).

    mask        — bool/uint8 maska JEDNÉ liniové třídy (foreground > 0).
    rdp_eps     — tolerance RDP zjednodušení [px]. 2 px = drží tvar, ořeže pixelové schody.
    min_len_px  — kratší výsledné polyline (součet délek segmentů) zahoď jako šum skeletonu (ostruhy).

    Souřadnice vrací jako (x, y) = (col, row) — připraveno pro geo transform (col,row jsou osy rastru)."""
    sk = skeletonize(mask > 0)
    chains = _trace_chains(sk)
    out = []
    for ch in chains:
        pts_xy = [(float(c), float(r)) for r, c in ch]      # (row,col) → (x=col, y=row)
        simp = _rdp(pts_xy, rdp_eps)
        # délka polyline (suma euklidovských úseků) — krátké ostruhy skeletonu pryč
        length = sum(((simp[i][0] - simp[i-1][0]) ** 2 + (simp[i][1] - simp[i-1][1]) ** 2) ** 0.5
                     for i in range(1, len(simp)))
        if len(simp) >= 2 and length >= min_len_px:
            out.append(simp)
    return out


def rasterize_polylines(polylines: list[list[tuple[float, float]]], shape: tuple[int, int],
                        width: int = 3) -> np.ndarray:
    """Polyline zpět na masku (H,W) bool — pro měření ztráty vektorizace vs raster baseline (Sez. 132).

    Kreslí stejně jako trénink/GT (PIL line + kulaté spoje na vrcholech, width = GT_LINE_WIDTH_PX), aby
    rasterizovaná vektorová predikce byla srovnatelná s holou masku stejnou metrikou (IoU/completeness)."""
    from PIL import Image, ImageDraw
    H, W = shape
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    r = width / 2.0
    for poly in polylines:
        if len(poly) >= 2:
            d.line(poly, fill=1, width=width)
        for cx, cy in poly:                                 # kulaté spoje (PIL line nemá round join)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=1)
    return np.asarray(img, dtype=bool)
