"""pairs.py — per-classId továrna párů [render, .omap] z reálné Livelox mapy (UC5, Sez. 83).

Reframe (Sez. 79): generator() = továrna párů pro reconstructor(). Tahle orchestrace spojí pro
JEDEN Livelox classId dvě části do JEDNÉ georeferencované .omap:
  - REAL část: tvrdé ČÚZK vrstvy (cesty/voda/budovy/skály/…) z generate_map() pro výsek mapy,
  - PREDICT část: plošnou vegetaci SEPAROVANOU z té reálné mapy (separate.separate_areas, Sez. 82/83).
Render rgb.png (čistý) i .omap (Y-cíl) vyrobí generate_map; degradér fáze II (Sez. 86) z rgb.png
vyrobí scan.png (= X v páru, „sken"). Y páru (Sez. 87) = area_labels.png: rasterizace plošných ISOM
symbolů z .omap (omap_raster) → label rastr pro reconstructor model Png2Area. Provenance real/predict
je v meta.json (A3, Sez. 83). Pár pro trénink = [scan.png (X), area_labels.png (Y)].

Společný grid = Livelox _georef_grid (Sez. 75): axis-aligned S-JTSK obal quadu. Real vrstvy se
georefují přes build_bbox(lat,lon,…) z CENTROIDU obalu (Gate A Sez. 83: shoda s obalem medián ~1 px,
posun jen v šířce ze zaokrouhlení mřížky — pro GT-feeder OK), separace přes _map_affine(quad) —
obojí skončí v jednom S-JTSK → .omap je zarovnaná.

Spouštět z kořene přes .venv (sys.path skript, fáze B).
"""
import json
import sys
import pathlib

import numpy as np
from PIL import Image

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# connectors/ i generator/ na path PŘED importy (sys.path skript, fáze B — ne balík)
sys.path.insert(0, str(_REPO_ROOT / "connectors"))
sys.path.insert(0, str(_REPO_ROOT / "generator"))

from pyproj import Transformer            # noqa: E402
from livelox import _georef_grid, _map_affine  # noqa: E402
from map_gt import IGNORE                 # noqa: E402
from separate import separate_areas  # noqa: E402
from generator import generate_map        # noqa: E402
from omap_raster import rasterize_map_dir  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
_CORPUS = _REPO_ROOT / "resources" / "livelox"
_SJTSK_TO_WGS84 = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)


def _content_quad_sjtsk(cid_dir: pathlib.Path, quad: list) -> list[tuple[float, float]]:
    """Obdélník skutečného mapového obsahu z GT masky, transformovaný do S-JTSK.

    Livelox quad georeferencuje celý tiskový list, který může obsahovat velké bílé layoutové
    okraje. `segment_gt` je označí IGNORE; bbox všech ostatních pixelů proto dává konzervativní
    obdélník mapového pole. Vrací rohy ve stejném pořadí jako image bbox:
    top-left, top-right, bottom-right, bottom-left.
    """
    labels = np.asarray(Image.open(cid_dir / "gt_labels.png"), dtype=np.uint8)
    valid = labels != IGNORE
    rows, cols = np.nonzero(valid)
    if not len(cols):
        raise RuntimeError(f"{cid_dir}: gt_labels neobsahuje žádné mapové pixely")

    c0, c1 = float(cols.min()), float(cols.max() + 1)
    r0, r1 = float(rows.min()), float(rows.max() + 1)
    H, W = labels.shape
    A = _map_affine(quad, W, H)
    px = np.array([[c0, r0, 1.0], [c1, r0, 1.0],
                   [c1, r1, 1.0], [c0, r1, 1.0]], dtype=float).T
    xy = (A @ px).T
    return [(float(x), float(y)) for x, y in xy]


def _separate_to_sjtsk(cid_dir: pathlib.Path, quad: list, crop_bbox=None,
                       src_mpp: float | None = None) -> list:
    """gt_labels → separace plošných tříd → polygony v S-JTSK (image-px → _map_affine).

    Vrací [(poly [vnější,díra…] v S-JTSK, code:int)] — tvar, který generate_map čeká v
    `predict_areas_sjtsk`. `_map_affine(quad)` je 2×3 matice image-px (col,row) → S-JTSK (x,y).

    `crop_bbox` (xmin,ymin,xmax,ymax v S-JTSK; Sez. 84) ořízne gt na pixel-okno odpovídající výseku
    PŘED separací — nutné, protože separace husté vegetace je O(n² prstenců) a separovat celou obří
    mapu (43 km²) by trvalo desítky minut, zatímco generuje se jen výsek (max_km). None = plný gt.

    `src_mpp` (Sez. 85): rozlišení mapy [m/px] z meta → separace downscaluje gt na TARGET_MPP před
    vektorizací (31,6× zrychlení žroutu #1, věrnost zachována). Crop i downscale jsou komplementární:
    crop zmenší PLOCHU, downscale ROZLIŠENÍ — Branžež (rotovaná, 0,56 mpp) potřebuje obojí (Sez. 84)."""
    gt = np.asarray(Image.open(cid_dir / "gt_labels.png"))   # 0-4/255 (map_gt separace)
    rgb = np.asarray(Image.open(cid_dir / "map.png").convert("RGB"))  # sken (403 split žluté, Sez. 92)
    H, W = gt.shape
    A = _map_affine(quad, W, H)                              # (col,row) → S-JTSK
    c0 = r0 = 0
    if crop_bbox is not None:
        # inverz afinní (S-JTSK → col,row): 4 rohy crop bboxu → pixel-okno (clip na rozměr gt)
        M = np.vstack([A, [0.0, 0.0, 1.0]])                 # 3×3 homogenní
        Ainv = np.linalg.inv(M)[:2]                          # zpět 2×3
        xmin, ymin, xmax, ymax = crop_bbox
        corners = np.array([[xmin, xmin, xmax, xmax], [ymin, ymax, ymin, ymax], [1, 1, 1, 1]])
        cr = Ainv @ corners                                  # (2,4) col,row
        c0 = max(0, int(np.floor(cr[0].min()))); c1 = min(W, int(np.ceil(cr[0].max())))
        r0 = max(0, int(np.floor(cr[1].min()))); r1 = min(H, int(np.ceil(cr[1].max())))
        gt = gt[r0:r1, c0:c1]                                # ořez → menší rastr = méně prstenců
        rgb = rgb[r0:r1, c0:c1]                              # rgb ořez STEJNĚ jako gt (zarovnání 403 masky)

    polys = separate_areas(gt, rgb=rgb, src_mpp=src_mpp)     # downscale na TARGET_MPP (polygony zpět v image-px)
    out: list = []
    for code, polys_c in polys.items():                     # {ISOM kód: [polygony]}
        for poly in polys_c:                                # poly = [outer, díra…], prsten = (col,row)
            rings_sjtsk = []
            for ring in poly:
                pts = np.asarray(ring, dtype=float)          # (N,2) col,row v OŘÍZNUTÉM gridu
                pts[:, 0] += c0; pts[:, 1] += r0             # lokální px → globální px (offset okna)
                hom = np.vstack([pts.T, np.ones(len(pts))])  # (3,N) [col;row;1]
                xy = (A @ hom).T                             # (N,2) S-JTSK
                rings_sjtsk.append([(float(x), float(y)) for x, y in xy])
            out.append((rings_sjtsk, int(code)))
    return out


def build_pair(cid, out_dir: str | None = None, ortho: bool = False, max_km: float = 5.0,
               labels: bool = True, point_base: bool = False):
    """Vyrobí pár [čistý render rgb.png (X), area_labels.png (Y)] pro Livelox classId: real ČÚZK + separace.

    Odvodí výsek z Livelox _georef_grid (centroid → lat/lon, rozměry obalu → w_km/h_km), separuje
    vegetaci z mapy do S-JTSK a předá ji generate_map jako `predict_areas_sjtsk` (jediný zdroj
    predikční zeleně). Vrací cestu k výstupní složce. `out_dir` None → `resources/livelox/<cid>/gen`.

    X páru = ČISTÝ gen render `rgb.png` (generate_map). Fotometrická degradace (sken-vady) se NEzapéká
    do páru — generator() fáze I drží podklady věrné (Sez. 103, návrat k záměru Sez. 80); degradace je
    AUGMENTACE a aplikuje se on-the-fly v tréninkové pipeline dekonstruktoru (`model/png2area/dataset.py`).

    `labels` (Sez. 87): po renderu rasterizuje plošné ISOM symboly z .omap → area_labels.png (= Y v
    páru, reconstructor Png2Area). Odvozeno z .omap (NE z render masek) → pár self-konzistentní.

    `point_base=True` (Sez. 106): místo area páru vyrobí PODKLAD pro Png2Point — render BEZ bodových
    symbolů (generate_map point_base=True) do oddělené složky `gen_pointbase/`. Vegetační kontext se
    pořád separuje z mapy (realistický podklad), ale Y (area_labels) se NEdělá — Png2Point bere GT
    z injekce ikonek on-the-fly (inject.py), ne z .omap. rgb.png v gen_pointbase = čistý point_base.

    `max_km` (Sez. 84): strop strany výseku okolo centroidu — render skal/objektů roste nadlineárně
    s plochou, obří mapy (max 106 km²) by tažily noční běh na víkend. Pro trénink rozhoduje rozmanitost
    lokalit a počet dlaždic, ne aby pár pokryl celou obří mapu → centrální výsek 5×5 km stačí. Separace
    je v S-JTSK → na menší canvas se sama ořízne (_poly_to_grid_px). None/0 = bez stropu (plný obal)."""
    cid = str(cid)
    cid_dir = _CORPUS / cid
    meta = json.loads((cid_dir / "meta.json").read_text(encoding="utf-8"))
    g = _georef_grid(meta)
    content_quad = _content_quad_sjtsk(cid_dir, g["quad"])
    xs = [p[0] for p in content_quad]
    ys = [p[1] for p in content_quad]
    xmin, ymin, xmax, ymax = min(xs), min(ys), max(xs), max(ys)
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    lon, lat = _SJTSK_TO_WGS84.transform(cx, cy)             # centroid obalu → WGS84
    w_km, h_km = (xmax - xmin) / 1000.0, (ymax - ymin) / 1000.0
    if max_km:                                               # zastropuj stranu (centroid držím)
        w_km, h_km = min(w_km, max_km), min(h_km, max_km)

    # crop bbox v S-JTSK okolo centroidu (= výsek, co generate_map vykreslí) → ořez gt před separací
    hw, hh = w_km * 500.0, h_km * 500.0                       # km/2 → m
    crop_bbox = (cx - hw, cy - hh, cx + hw, cy + hh)
    predict_sjtsk = _separate_to_sjtsk(cid_dir, g["quad"], crop_bbox,
                                       src_mpp=meta.get("effectiveMppX"))
    out = out_dir or str(cid_dir / ("gen_pointbase" if point_base else "gen"))
    print(f"{cid} \"{meta.get('name', '?')}\"  výsek {w_km:.2f}×{h_km:.2f} km @ "
          f"({lat:.5f}, {lon:.5f})  separace {len(predict_sjtsk)} ploch"
          f"{'  [point_base]' if point_base else ''}")
    res = generate_map(lat, lon, w_km, h_km,
                       predict_areas_sjtsk=predict_sjtsk, point_base=point_base,
                       out_dir=out, ortho=ortho)
    # Ořež gen.omap + render na obdélník skutečného mapového obsahu, ne na celý tiskový list.
    # MUSÍ být PŘED rasterizací Y: X render i Y label se berou z TÉŽE ořezané .omap.
    from cut import clip_omap_to_quad
    kept, removed = clip_omap_to_quad(out, pathlib.Path(out).name, content_quad)
    print(f"  ořez na mapový obsah: {kept} objektů v poli, {removed} přesah odstraněn")
    if labels and not point_base:                           # Y páru: plošné symboly z .omap → label rastr
        lab = rasterize_map_dir(pathlib.Path(out))
        Image.fromarray(lab, mode="L").save(pathlib.Path(out) / "area_labels.png")
    return res


def make_map(cid, name: str) -> pathlib.Path:
    """Vyrobí PROHLÍŽECÍ OB mapu z Livelox classId do `maps/<name>/` se VŠEMI podklady (Sez. 140).

    Kompletní řetězec jedním krokem: stáhni Livelox sken → segmentuj GT → build_pair (real ČÚZK +
    separace vegetace ze skenu + ortofoto, ořez na quad) → doplň DMR hillshade + originální sken jako
    verify podklady. `maps/` = lidská prohlížecí mapa (verify), na rozdíl od tréninkových párů
    v `resources/livelox/<cid>/gen/` (ty podklady NEdostávají — model čte rgb+labels, Sez. 104).
    Idempotentní (download/segment přeskočí hotové). Vrací cestu k mapě."""
    from livelox import download_map          # noqa: E402 — connectors na path (ř. 28)
    from map_gt import segment_gt             # noqa: E402
    from generator import MAPS_DIR            # noqa: E402
    from gen_backgrounds import attach_verify_backgrounds  # noqa: E402
    cid = str(cid)
    cid_dir = download_map(int(cid))                          # map.png + meta.json (idempotentní)
    if not (cid_dir / "gt_labels.png").exists():
        segment_gt(cid_dir / "map.png")                      # runnability GT (separace vegetace ho čte)
    out_dir = str(MAPS_DIR / name)
    build_pair(cid, out_dir=out_dir, ortho=True, labels=True)
    r = attach_verify_backgrounds(out_dir, cid_dir=cid_dir)  # DMR hillshade + Livelox sken
    print(f"  podklady: {r['added']}" + (f"  (přeskočeno {r['skipped']})" if r["skipped"] else ""))
    return pathlib.Path(out_dir)


def _cr_keep_cids() -> list:
    """ČR keep mapy = klíče _split.json (split.py drží 207 ČR keep classic, geo-split train/val/test).

    Zdroj párů (Sez. 84): split místo curate.kept_dirs('classic') (=216) řeší DVĚ věci najednou —
    vyřadí 9 cizích keep map (real ČÚZK vrstvy fungují jen pro ČR; cizí pár by neměl real část)
    I outlier 1109655 (georef bug, vyřazen už geosplitem → není ve split). Foundations-čistý zdroj."""
    sys.path.insert(0, str(_REPO_ROOT / "connectors"))
    from split import load_split        # noqa: E402 — sys.path skript
    return sorted(load_split().keys())


def pointbase_subset(n: int = 40) -> list:
    """Vybere ~n Livelox classId napříč splity (train/val/test) pro Png2Point podklady (Sez. 106).

    Png2Point trénuje na INJEKCI ikonek do podkladu (point_base.png) — potřebuje podklady i pro
    val/test, aby F1 eval běžel na NEVIDĚNÝCH renderech. Výběr proporcionální k velikosti splitu
    (145/31/31) a DETERMINISTICKÝ (sorted + rovnoměrný krok) → reprodukovatelný a geograficky
    rozmanitý (split je geo-clusterovaný, krok přes seřazené cidy nevezme jen jeden region)."""
    sys.path.insert(0, str(_REPO_ROOT / "connectors"))
    from split import load_split        # noqa: E402 — sys.path skript
    s = load_split()
    by_split: dict = {"train": [], "val": [], "test": []}
    for cid, sp in s.items():
        by_split.setdefault(sp, []).append(cid)
    out: list = []
    for sp, cids in by_split.items():
        cids = sorted(cids)
        k = max(1, round(n * len(cids) / len(s)))    # proporční počet z tohoto splitu
        step = max(1, len(cids) // k)                # rovnoměrný krok přes seřazené (geo-rozptyl)
        out += cids[::step][:k]
    return sorted(out)


def build_pairs(cids=None, skip_existing: bool = True, ortho: bool = False,
                max_km: float = 5.0, labels: bool = True, point_base: bool = False) -> dict:
    """Hromadně vyrobí páry-zdroje [render, .omap] pro seznam Livelox classId (UC5 trénink, Sez. 84).

    Volá build_pair na každý cid. Vlastnosti dávky (mirror livelox.build_pairs):
      - resumovatelné: skip_existing přeskočí mapy s hotovým gen/rgb.png (re-běh po přerušení
        nestahuje ČÚZK znovu — fetch je drahý, ~204× = hodiny),
      - tolerantní: chyba jedné mapy (síť/georef/separace) dávku NEzastaví, jen se zaznamená.
    `point_base=True` (Sez. 106): režim podkladů pro Png2Point — render bez bodů do gen_pointbase/,
    bez area_labels (final artefakt = gen_pointbase/rgb.png).
    cids None → ČR keep ze split (_cr_keep_cids). Vrací souhrn {ok, skipped, failed:[(cid,err)]}.
    """
    cids = list(cids) if cids is not None else _cr_keep_cids()
    summary = {"ok": [], "skipped": [], "failed": []}
    total = len(cids)
    sub = "gen_pointbase" if point_base else "gen"
    for i, cid in enumerate(cids, 1):
        cid = str(cid)
        # finální artefakt dávky = POSLEDNÍ zapsaný krok (crash mezi kroky → re-běh dokončí):
        # area pár labels (area_labels.png, Y) > čistý render (rgb.png, X); point_base jen rgb.png.
        final = "rgb.png" if point_base else ("area_labels.png" if labels else "rgb.png")
        gen_out = _CORPUS / cid / sub / final
        if skip_existing and gen_out.exists():
            summary["skipped"].append(cid)
            print(f"[{i}/{total}] {cid} SKIP ({sub}/{final} hotovo)")
            continue
        try:
            build_pair(cid, ortho=ortho, max_km=max_km, labels=labels, point_base=point_base)
            summary["ok"].append(cid)
            print(f"[{i}/{total}] {cid} OK  (ok={len(summary['ok'])} "
                  f"skip={len(summary['skipped'])} fail={len(summary['failed'])})")
        except Exception as e:                       # tolerantní: 1 mapa nepoloží dávku
            summary["failed"].append((cid, f"{type(e).__name__}: {e}"))
            print(f"[{i}/{total}] {cid} FAIL: {type(e).__name__}: {e}")
    print(f"\nhotovo: ok {len(summary['ok'])}, skip {len(summary['skipped'])}, "
          f"fail {len(summary['failed'])}")
    if summary["failed"]:
        print("selhaly:", ", ".join(c for c, _ in summary["failed"]))
    return summary


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows cp1250 vs Unicode (Sez. 74)
    except Exception:
        pass
    arg = sys.argv[1] if len(sys.argv) > 1 else "1088447"
    if arg == "map":
        # `map <classId> <název>` = prohlížecí mapa do maps/<název> se všemi podklady (Sez. 140)
        path = make_map(sys.argv[2], sys.argv[3])
        print(f"prohlížecí mapa → {path}")
    elif arg == "batch":
        # `batch` = celý ČR keep set; `batch <N>` = jen prvních N (sanity vzorek před nočním během)
        cids = _cr_keep_cids()
        if len(sys.argv) > 2:
            cids = cids[: int(sys.argv[2])]
        build_pairs(cids)
    elif arg == "pointbase":
        # `pointbase [N]` = ~N podkladů pro Png2Point napříč splity (Sez. 106), default 40
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
        cids = pointbase_subset(n)
        print(f"point_base subset: {len(cids)} map napříč splity")
        build_pairs(cids, point_base=True)
    else:
        path = build_pair(arg)
        print(f"pár → {path}")
