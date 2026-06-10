"""gen_backgrounds.py — přepínatelné OOM podklady do korpusového gen.omap (Sez. 104, zadání uživatele).

Vizuální pomůcka (NETRÉNINKOVÁ): warpne tři reálné podklady Livelox lokality do gen px gridu a připne
je jako PODKLADOVÉ (background) image templates do gen.omap, aby šlo v OOM vizuálně srovnat gen kresbu
s realitou:
  - bg_scan.png  ← map.png        (Livelox sken mapy, native rotovaný quad → _map_affine)
  - bg_ortho.png ← ortho.png      (ČÚZK ortofoto, S-JTSK grid → _georef_grid)
  - bg_gt.png    ← gt_grid_vis.png (GT runnability barevná vizualizace, týž S-JTSK grid)

Každý podklad je v JINÉM gridu → resample do gen px gridu (rgb.pgw): pro každý gen px → S-JTSK →
zpět do zdrojového px → nearest sample. Warpnutý obraz W×H se pak připne identickým mechanismem jako
ortho_template (omap_export.inject_image_templates) — vycentrovaný na origin, all pod mapou.

Post-process: needituje render ani nestahuje data (Sez. 103 volba — „na 205 hotových bez re-fetch").
gen.omap z build_pair má dnes <templates count="0"> → vložíme count=N. Degradovaný sken záměrně NENÍ
podklad (neexistuje, degradace je augmentace; Sez. 103, [[no-degradation-in-generator-phase]]).

No silent fallback (CLAUDE.md): chybí-li zdroj (ortho/GT 212/268 — jen mapy z GATE 1 běhu), zaloguj a
PŘESKOČ ten podklad (ne fail); map.png je 268/268 → každý pár dostane aspoň sken.

Spouštět z kořene přes .venv (sys.path skript, fáze B).
"""
import sys
import json
import pathlib

import numpy as np
from PIL import Image

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "connectors"))
sys.path.insert(0, str(_REPO_ROOT / "generator"))

from livelox import _georef_grid, _map_affine  # noqa: E402
from omap_export import inject_image_templates  # noqa: E402
from map_gt import IGNORE as _GT_IGNORE, _LABEL_VIS as _GT_VIS  # noqa: E402  (GT IGNORE barva → bílá)

_GT_IGNORE_RGB = _GT_VIS[_GT_IGNORE]   # (255,0,255) magenta = oblast mimo Livelox mapu v gt_grid_vis

Image.MAX_IMAGE_PIXELS = None
_CORPUS = _REPO_ROOT / "resources" / "livelox"
_BG_MAX_PX = 1500          # downscale delší strany podkladu (vizuál nepotřebuje plné gen rozlišení)
_BG_OPACITY = 0.6          # výchozí průhlednost ref ve <view> (uživatel doladí v OOM)


def _read_pgw(path: pathlib.Path):
    """.pgw 6 řádků (world-file pořadí A,D,B,E,C,F) → afinní (col,row)→svět: x=A·col+B·row+C, y=D·col+E·row+F."""
    A, D, B, E, C, F = [float(x) for x in path.read_text().split()]
    return A, B, C, D, E, F


def _warp_to_gen(src: np.ndarray, sjtsk_to_src, gpgw, gW: int, gH: int, out_w: int, out_h: int) -> np.ndarray:
    """Resample zdrojový obraz do gen px gridu (downscaled out_w×out_h), nearest, OOB → bílá.

    Tok: downscaled gen px → full gen px → S-JTSK (gen rgb.pgw) → zdrojový px (`sjtsk_to_src`) → sample.
    `gpgw` = (A,B,C,D,E,F) rgb.pgw; `sjtsk_to_src(x, y)` vrací (col, row) ve zdrojovém rastru (vektorové)."""
    gA, gB, gC, gD, gE, gF = gpgw
    kx, ky = gW / out_w, gH / out_h                   # downscale faktor gen gridu
    cols, rows = np.meshgrid(np.arange(out_w) * kx, np.arange(out_h) * ky)  # full gen px
    x = gA * cols + gB * rows + gC                    # gen px → S-JTSK
    y = gD * cols + gE * rows + gF
    sc, sr = sjtsk_to_src(x, y)                       # S-JTSK → zdrojový px
    sc = np.round(sc).astype(int)
    sr = np.round(sr).astype(int)
    Hs, Ws = src.shape[:2]
    valid = (sc >= 0) & (sc < Ws) & (sr >= 0) & (sr < Hs)
    out = np.full((out_h, out_w, 3), 255, np.uint8)   # mimo zdroj = bílá (papír)
    out[valid] = src[sr[valid], sc[valid]]
    return out


def _scan_inverse(quad: list, Wm: int, Hm: int):
    """S-JTSK → map.png px (inverz _map_affine rotovaného quadu). Vrací funkci (x,y)→(col,row) vektorovou."""
    A = _map_affine(quad, Wm, Hm)                     # (col,row) → S-JTSK, 2×3
    Ainv = np.linalg.inv(np.vstack([A, [0.0, 0.0, 1.0]]))[:2]   # 3×3 inverz → zpět 2×3

    def f(x, y):
        col = Ainv[0, 0] * x + Ainv[0, 1] * y + Ainv[0, 2]
        row = Ainv[1, 0] * x + Ainv[1, 1] * y + Ainv[1, 2]
        return col, row
    return f


def _grid_inverse(g: dict):
    """S-JTSK → _georef_grid px (axis-aligned, ortho/GT). top-left=(xmin,ymax), mpp m/px. Vektorová."""
    xmin, ymax, mpp = g["xmin"], g["ymax"], g["mpp"]

    def f(x, y):
        return (x - xmin) / mpp, (ymax - y) / mpp
    return f


def _affine_inverse(pgw: tuple):
    """S-JTSK → sken px (inverz .pgw afinní). pgw=(A,B,C,D,E,F): x=A·col+B·row+C, y=D·col+E·row+F.

    Pro resources MĚŘICÍ mapy (sken georef = běžný world-file, NE Livelox rotovaný quad). Vektorová."""
    A, B, C, D, E, F = pgw
    det = A * E - B * D

    def f(x, y):
        col = (E * (x - C) - B * (y - F)) / det
        row = (-D * (x - C) + A * (y - F)) / det
        return col, row
    return f


def add_backgrounds(gen_dir: str | pathlib.Path, cid_dir: str | pathlib.Path | None = None,
                    opacity: float = _BG_OPACITY) -> dict:
    """Warpne dostupné podklady do gen gridu a vloží je jako background templates do gen.omap.

    `gen_dir` = složka páru (rgb.png/rgb.pgw/meta.json/gen.omap). `cid_dir` None → rodič gen_dir
    (build_pair píše do <cid>/gen). Vrací {"added": [jména], "skipped": [(zdroj, důvod)]}."""
    gen_dir = pathlib.Path(gen_dir)
    cid_dir = pathlib.Path(cid_dir) if cid_dir else gen_dir.parent
    omap = gen_dir / "gen.omap"
    rgb_pgw = gen_dir / "rgb.pgw"
    meta_p = gen_dir / "meta.json"
    for req in (omap, rgb_pgw, meta_p, gen_dir / "rgb.png"):
        if not req.exists():
            raise FileNotFoundError(f"{gen_dir}: chybí {req.name} (gen pár není hotový)")

    with Image.open(gen_dir / "rgb.png") as im:
        gW, gH = im.size                              # gen px grid
    gpgw = _read_pgw(rgb_pgw)
    scale = int(json.loads(meta_p.read_text(encoding="utf-8"))["scale"].split(":")[1])  # "1:10000" → 10000
    mpp_x, mpp_y = abs(gpgw[0]), abs(gpgw[4])         # m/px z rgb.pgw (axis-aligned gen grid)
    # paper µm celého výseku: world_m × (1e6/scale µm/m); sx = pw/1000/out_w = map-mm na px podkladu
    pw = gW * mpp_x * 1e6 / scale
    ph = gH * mpp_y * 1e6 / scale

    cid_meta = cid_dir / "meta.json"
    g = _georef_grid(json.loads(cid_meta.read_text(encoding="utf-8"))) if cid_meta.exists() else None

    # zdroje: (jméno_bg, zdrojový_soubor, inverzní_transformace, recolor). pořadí = z-order (sken vespod).
    # recolor {from_rgb: to_rgb} aplikováno na zdroj PŘED warpem; u GT: IGNORE magenta → bílá (mimo
    # Livelox mapu = papír, v OOM neviditelné), jinak by zaplnila celý čtverec rušivou růžovou.
    sources = []
    if (cid_dir / "map.png").exists() and g is not None:
        with Image.open(cid_dir / "map.png") as im:
            Wm, Hm = im.size
        sources.append(("bg_scan.png", cid_dir / "map.png", _scan_inverse(g["quad"], Wm, Hm), None))
    if g is not None:
        for bg, src, recolor in (("bg_ortho.png", "ortho.png", None),
                                 ("bg_gt.png", "gt_grid_vis.png", {_GT_IGNORE_RGB: (255, 255, 255)})):
            if (cid_dir / src).exists():
                sources.append((bg, cid_dir / src, _grid_inverse(g), recolor))

    result = {"added": [], "skipped": []}
    for missing, why in ((not (cid_dir / "map.png").exists(), ("bg_scan.png", "chybí map.png")),
                         (g is None, ("podklady", "chybí cid meta.json → _georef_grid")),
                         (g is not None and not (cid_dir / "ortho.png").exists(),
                          ("bg_ortho.png", "chybí ortho.png (mimo GATE 1 běh)")),
                         (g is not None and not (cid_dir / "gt_grid_vis.png").exists(),
                          ("bg_gt.png", "chybí gt_grid_vis.png (mimo GATE 1 běh)"))):
        if missing:
            result["skipped"].append(why)

    out_w = max(1, round(gW * min(1.0, _BG_MAX_PX / max(gW, gH))))   # downscale delší strany na _BG_MAX_PX
    out_h = max(1, round(gH * min(1.0, _BG_MAX_PX / max(gW, gH))))
    templates = []
    for bg_name, src_path, inv, recolor in sources:
        with Image.open(src_path) as im:
            src = np.asarray(im.convert("RGB"), dtype=np.uint8)
        if recolor:                                   # přemapuj barvy na zdroji (GT IGNORE → bílá)
            src = src.copy()
            for frm, to in recolor.items():
                src[np.all(src == np.array(frm, np.uint8), axis=-1)] = to
        warped = _warp_to_gen(src, inv, gpgw, gW, gH, out_w, out_h)
        Image.fromarray(warped).save(gen_dir / bg_name)
        templates.append({"name": bg_name, "sx": pw / 1000.0 / out_w,
                          "sy": ph / 1000.0 / out_h, "opacity": opacity})
        result["added"].append(bg_name)

    if templates:
        doc = omap.read_text(encoding="utf-8")
        doc = inject_image_templates(doc, templates)
        omap.write_text(doc, encoding="utf-8")
    return result


def add_resources_scan_background(name: str, gen_dir: str | pathlib.Path,
                                  opacity: float = _BG_OPACITY) -> dict:
    """Připne reálný resources sken (`resources/<name>.png` + `.pgw`) jako bg podklad do `<name>.omap`.

    Izomorf `add_backgrounds`, ale pro resources MĚŘICÍ mapy (Bedřichovka/Blatná/…, ne Livelox pár):
    omap = `<name>.omap` (ne gen.omap), sken georef = `.pgw` afinní (ne rotovaný quad). Účel: měřicí
    cesta (`measure_dod._gen_sep`) přepisuje produkční gen.omap → bez tohoto by smazala podklad, který
    si uživatel v OOM připnul pro verify (regrese „zase vypadly podklady", Sez. 109).

    No silent fallback (CLAUDE.md): chybí-li sken/pgw/omap, zaloguj a vrať bez připnutí (ne raise)."""
    gen_dir = pathlib.Path(gen_dir)
    omap = gen_dir / f"{name}.omap"
    rgb_pgw = gen_dir / "rgb.pgw"
    meta_p = gen_dir / "meta.json"
    scan = _REPO_ROOT / "resources" / f"{name}.png"
    scan_pgw = _REPO_ROOT / "resources" / f"{name}.pgw"
    for req in (omap, rgb_pgw, meta_p, gen_dir / "rgb.png", scan, scan_pgw):
        if not req.exists():
            print(f"⚠ {name}: chybí {req.name} → podklad sken NEpřipnut", file=sys.stderr)
            return {"added": [], "skipped": [("bg_scan.png", f"chybí {req.name}")]}

    with Image.open(gen_dir / "rgb.png") as im:
        gW, gH = im.size
    gpgw = _read_pgw(rgb_pgw)
    scale = int(json.loads(meta_p.read_text(encoding="utf-8"))["scale"].split(":")[1])
    mpp_x, mpp_y = abs(gpgw[0]), abs(gpgw[4])
    pw = gW * mpp_x * 1e6 / scale                     # paper µm výseku (mirror add_backgrounds)
    ph = gH * mpp_y * 1e6 / scale
    inv = _affine_inverse(_read_pgw(scan_pgw))        # S-JTSK → sken px

    with Image.open(scan) as im:
        src = np.asarray(im.convert("RGB"), dtype=np.uint8)
    out_w = max(1, round(gW * min(1.0, _BG_MAX_PX / max(gW, gH))))
    out_h = max(1, round(gH * min(1.0, _BG_MAX_PX / max(gW, gH))))
    warped = _warp_to_gen(src, inv, gpgw, gW, gH, out_w, out_h)
    Image.fromarray(warped).save(gen_dir / "bg_scan.png")

    templates = [{"name": "bg_scan.png", "sx": pw / 1000.0 / out_w,
                  "sy": ph / 1000.0 / out_h, "opacity": opacity}]
    doc = omap.read_text(encoding="utf-8")
    doc = inject_image_templates(doc, templates)      # raise když .omap nemá prázdné <templates> bloky
    omap.write_text(doc, encoding="utf-8")
    return {"added": ["bg_scan.png"], "skipped": []}


def add_backgrounds_batch(cids=None, skip_existing: bool = True) -> dict:
    """Hromadně přidá podklady na hotové gen páry korpusu (Sez. 104). cids None → všechny s gen/gen.omap.

    skip_existing: přeskočí páry, jejichž gen.omap už podklady má (<templates count="0"> chybí = hotovo).
    Tolerantní: chyba jednoho páru dávku NEzastaví (jen zaznamená). Vrací souhrn."""
    if cids is None:
        cids = sorted(d.parent.parent.name for d in _CORPUS.glob("*/gen/gen.omap"))
    summary = {"ok": [], "skipped": [], "failed": []}
    total = len(cids)
    for i, cid in enumerate(cids, 1):
        gen_dir = _CORPUS / str(cid) / "gen"
        omap = gen_dir / "gen.omap"
        if not omap.exists():
            summary["failed"].append((cid, "gen.omap chybí"))
            continue
        if skip_existing and '<templates count="0"' not in omap.read_text(encoding="utf-8"):
            summary["skipped"].append(cid)
            print(f"[{i}/{total}] {cid} SKIP (podklady už vloženy)")
            continue
        try:
            r = add_backgrounds(gen_dir)
            summary["ok"].append(cid)
            sk = f" skip:{[s[0] for s in r['skipped']]}" if r["skipped"] else ""
            print(f"[{i}/{total}] {cid} OK  +{r['added']}{sk}")
        except Exception as e:
            summary["failed"].append((cid, f"{type(e).__name__}: {e}"))
            print(f"[{i}/{total}] {cid} FAIL: {type(e).__name__}: {e}")
    print(f"\nhotovo: ok {len(summary['ok'])}, skip {len(summary['skipped'])}, fail {len(summary['failed'])}")
    if summary["failed"]:
        print("selhaly:", ", ".join(f"{c}({e})" for c, e in summary["failed"][:10]))
    return summary


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    arg = sys.argv[1] if len(sys.argv) > 1 else "1088447"
    if arg == "batch":
        add_backgrounds_batch()
    else:
        r = add_backgrounds(_CORPUS / arg / "gen")
        print(f"{arg}: přidáno {r['added']}, přeskočeno {r['skipped']}")
