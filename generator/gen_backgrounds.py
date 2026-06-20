"""gen_backgrounds.py — přepínatelné OOM podklady do korpusového gen.omap (Sez. 104, zadání uživatele).

Vizuální pomůcka (NETRÉNINKOVÁ): warpne tři reálné podklady Livelox lokality do gen px gridu a připne
je jako PODKLADOVÉ (background) image templates do gen.omap, aby šlo v OOM vizuálně srovnat gen kresbu
s realitou:
  - bg_scan.png  ← map.png        (Livelox sken mapy, native rotovaný quad → _map_affine)
  - bg_mobile.png ← mobile_rectified.png (volitelné mobilní foto registrované do gridu map.png)
  - bg_ortho.png ← ortho.png      (ČÚZK ortofoto, S-JTSK grid → _georef_grid)
  - bg_gt.png    ← gt_semantic_grid_vis.png (GT ploch včetně vody a 520, týž S-JTSK grid)

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

from pyproj import Transformer  # noqa: E402
from livelox import _georef_grid, _map_affine  # noqa: E402
from omap_export import inject_image_templates, append_image_templates, image_template_names  # noqa: E402
from dmr import fetch_elevation_grid  # noqa: E402  (DMR 5G hillshade podklad)
from map_gt import IGNORE as _GT_IGNORE, SEMANTIC_LABEL_VIS as _GT_VIS  # noqa: E402

_SJTSK_TO_WGS84 = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)

_GT_IGNORE_RGB = _GT_VIS[_GT_IGNORE]   # (255,0,255) magenta = oblast mimo Livelox mapu v gt_grid_vis

Image.MAX_IMAGE_PIXELS = None
_CORPUS = _REPO_ROOT / "resources" / "livelox"
_BG_MAX_PX = 6000          # delší strana warpnutého podkladu. Gen grid bývá HRUBÝ (~2 m/px) → bez
                           # nadvzorkování je sken v OOM rozmazaný (Sez. 111, stížnost uživatele);
                           # supersamplujeme jemně ze zdroje (100+ Mpx skeny → pořád downsample).
_BG_OPACITY = 0.6          # výchozí průhlednost ref ve <view> (uživatel doladí v OOM)


def _read_pgw(path: pathlib.Path):
    """.pgw 6 řádků (world-file pořadí A,D,B,E,C,F) → afinní (col,row)→svět: x=A·col+B·row+C, y=D·col+E·row+F."""
    A, D, B, E, C, F = [float(x) for x in path.read_text().split()]
    return A, B, C, D, E, F


def _bg_out_size(gW: int, gH: int) -> tuple[int, int]:
    """Rozlišení warpnutého podkladu: delší strana = _BG_MAX_PX, aspekt = gen grid (warp resampluje
    do gen px frame). Záměrně SMÍ překročit gW×gH (supersampling) — gen grid je hrubý, jemné kroky
    vzorkují detail ze zdrojového skenu místo zmáčknutí na gen rozlišení (Sez. 111)."""
    f = _BG_MAX_PX / max(gW, gH, 1)
    return max(1, round(gW * f)), max(1, round(gH * f))


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


def _resolve_omap(map_dir: pathlib.Path, omap_name: str | None = None) -> pathlib.Path:
    """Najde .omap mapy ve složce: explicitní `omap_name` > `gen.omap` (Livelox pár) > `<složka>.omap`
    (DEV/KPI). Sdílené tří attach_* funkcemi (DRY) — všechny tři generační cesty pojmenovávají jinak."""
    if omap_name:
        return map_dir / omap_name
    if (map_dir / "gen.omap").exists():
        return map_dir / "gen.omap"
    return map_dir / f"{map_dir.name}.omap"


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
        scan_inv = _scan_inverse(g["quad"], Wm, Hm)
        sources.append(("bg_scan.png", cid_dir / "map.png", scan_inv, None))
        mobile = cid_dir / "mobile_rectified.png"
        if mobile.exists():
            with Image.open(mobile) as im:
                if im.size != (Wm, Hm):
                    raise ValueError(
                        f"{mobile}: rozměr {im.size} != map.png {(Wm, Hm)} "
                        "(mobilní foto musí být registrované do gridu map.png)"
                    )
            sources.append(("bg_mobile.png", mobile, scan_inv, None))
    if g is not None:
        for bg, src, recolor in (("bg_ortho.png", "ortho.png", None),
                                 ("bg_gt.png", "gt_semantic_grid_vis.png",
                                  {_GT_IGNORE_RGB: (255, 255, 255)})):
            if (cid_dir / src).exists():
                sources.append((bg, cid_dir / src, _grid_inverse(g), recolor))

    result = {"added": [], "skipped": []}
    for missing, why in ((not (cid_dir / "map.png").exists(), ("bg_scan.png", "chybí map.png")),
                         (g is None, ("podklady", "chybí cid meta.json → _georef_grid")),
                         (g is not None and not (cid_dir / "ortho.png").exists(),
                          ("bg_ortho.png", "chybí ortho.png (mimo GATE 1 běh)")),
                         (g is not None and not (cid_dir / "gt_semantic_grid_vis.png").exists(),
                          ("bg_gt.png", "chybí gt_semantic_grid_vis.png (spusť map_gt + GATE 1)"))):
        if missing:
            result["skipped"].append(why)

    out_w, out_h = _bg_out_size(gW, gH)
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
    out_w, out_h = _bg_out_size(gW, gH)
    warped = _warp_to_gen(src, inv, gpgw, gW, gH, out_w, out_h)
    Image.fromarray(warped).save(gen_dir / "bg_scan.png")

    templates = [{"name": "bg_scan.png", "sx": pw / 1000.0 / out_w,
                  "sy": ph / 1000.0 / out_h, "opacity": opacity}]
    # Resource sken se často doplňuje až po DMR/ortho podkladech, proto musí appendovat stejně
    # jako ostatní attach_* cesty. `inject_image_templates` je jen pro čerstvou mapu bez podkladů.
    doc = append_image_templates(omap.read_text(encoding="utf-8"), templates)
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


_DMR_BG_MPP = 2.5          # cílové rozlišení hillshade podkladu [m/px]; DMR 5G native ~2 m → jemnější = interpolace
_DMR_BG_MAX_PX = 4000      # strop strany fetche (ČÚZK exportImage limit + RAM); velké výseky downsamplují


def _hillshade(elev: np.ndarray, mpp: float,
               azimuth_deg: float = 315.0, altitude_deg: float = 45.0) -> np.ndarray:
    """Šedý hillshade (H×W×3 uint8) z výškového pole — standardní ESRI vzorec (Lambert + směr světla).

    `mpp` = m/px (izotropní), `azimuth_deg` = odkud svítí (315° = SZ, kartografická konvence — slunce
    vlevo nahoře, ať reliéf nevypadá invertovaně), `altitude_deg` = výška slunce nad obzorem.
    NaN (mimo ČR / DMR díra u hranic) → bílá (papír; v OOM neviditelné). Bez SciPy — jen np.gradient."""
    nan = ~np.isfinite(elev)
    if nan.all():                                          # celý výsek mimo DMR → samý papír
        return np.full(elev.shape + (3,), 255, np.uint8)
    e = np.where(nan, float(np.nanmedian(elev)), elev).astype(np.float64)  # NaN → medián (jen kvůli gradientu)
    dzdy, dzdx = np.gradient(e, mpp)                       # parciální derivace [m/m]; row = S-J, col = V-Z
    slope = np.arctan(np.hypot(dzdx, dzdy))                # sklon [rad]
    aspect = np.arctan2(dzdy, -dzdx)                       # orientace svahu [rad] (ESRI konvence)
    zenith = np.radians(90.0 - altitude_deg)              # zenitový úhel slunce
    az = np.radians(360.0 - azimuth_deg + 90.0)           # azimut → matematický úhel
    shaded = (np.cos(zenith) * np.cos(slope)
              + np.sin(zenith) * np.sin(slope) * np.cos(az - aspect))
    g = (np.clip(shaded, 0.0, 1.0) * 255).astype(np.uint8)
    rgb = np.dstack([g, g, g])
    rgb[nan] = 255                                         # mimo DMR → bílá
    return rgb


def _bbox_from_pgw(gpgw: tuple, gW: int, gH: int) -> tuple[float, float, float, float, float, float]:
    """Axis-aligned S-JTSK bbox výseku z rgb.pgw (A,B,C,D,E,F) + rozměru gridu. Vrací
    (xmin, ymin, xmax, ymax, cx, cy). Předpoklad: gen grid je osově zarovnaný (B=D=0) — platí pro
    všechny tři cesty (DEV/KPI/Buschdörfl kreslí osově, Livelox quad se jen ořezává, ne rotuje pgw)."""
    A, B, C, D, E, F = gpgw
    mpp_x, mpp_y = abs(A), abs(E)
    xmin = C - mpp_x / 2.0                                 # (C,F) = střed px (0,0) = SZ roh gridu
    xmax = C + (gW - 0.5) * mpp_x
    ymax = F + mpp_y / 2.0                                 # E < 0 (sever nahoře)
    ymin = F - (gH - 0.5) * mpp_y
    return xmin, ymin, xmax, ymax, (xmin + xmax) / 2.0, (ymin + ymax) / 2.0


def attach_dmr_hillshade(map_dir: str | pathlib.Path, omap_name: str | None = None,
                         opacity: float = _BG_OPACITY, target_mpp: float = _DMR_BG_MPP) -> dict:
    """Připne DMR 5G hillshade jako podkladový template do `.omap` mapy (DEV/KPI/Buschdörfl).

    Pracuje JEN z obsahu složky (`rgb.pgw` + `rgb.png` + `meta.json` + `.omap`) → společný jmenovatel
    všech tří generačních cest. Z pgw odvodí S-JTSK bbox, stáhne DMR (cache `.dmr_cache`), vyrenderuje
    hillshade a APPENDne ho k existujícím podkladům (`append_image_templates` — zachová ortofoto/sken).

    `omap_name` None → najde `gen.omap`, jinak `<složka>.omap`. No silent fallback: chybí-li vstup,
    raisuje (ne náhradní cesta). Vrací {"added": [...], "skipped": [...]}."""
    map_dir = pathlib.Path(map_dir)
    rgb = map_dir / "rgb.png"
    rgb_pgw = map_dir / "rgb.pgw"
    meta_p = map_dir / "meta.json"
    omap = _resolve_omap(map_dir, omap_name)
    for req in (rgb, rgb_pgw, meta_p, omap):
        if not req.exists():
            raise FileNotFoundError(f"{map_dir}: chybí {req.name} (mapa není hotová)")

    with Image.open(rgb) as im:
        gW, gH = im.size
    gpgw = _read_pgw(rgb_pgw)
    scale = int(json.loads(meta_p.read_text(encoding="utf-8"))["scale"].split(":")[1])
    mpp_x, mpp_y = abs(gpgw[0]), abs(gpgw[4])
    xmin, ymin, xmax, ymax, cx, cy = _bbox_from_pgw(gpgw, gW, gH)
    world_w, world_h = xmax - xmin, ymax - ymin
    lon, lat = _SJTSK_TO_WGS84.transform(cx, cy)           # střed výseku → WGS84 (fetch_elevation_grid čeká lat/lon)

    # jemný grid pro hillshade (≈target_mpp), strop _DMR_BG_MAX_PX; aspekt = world_w/world_h, ať bbox sedí
    gw_f = max(1, min(_DMR_BG_MAX_PX, round(world_w / target_mpp)))
    gh_f = max(1, min(_DMR_BG_MAX_PX, round(world_h / target_mpp)))
    eff_mpp = world_h / gh_f                               # skutečné m/px po stropu (pro hillshade gradient)
    elev = fetch_elevation_grid(lat, lon, gw_f, gh_f, tile_m=world_h)   # (gh_f, gw_f), sever nahoře
    hs = _hillshade(elev, eff_mpp)
    Image.fromarray(hs).save(map_dir / "bg_dmr.png")

    pw = gW * mpp_x * 1e6 / scale                          # paper µm výseku (mirror add_backgrounds)
    ph = gH * mpp_y * 1e6 / scale
    template = {"name": "bg_dmr.png", "sx": pw / 1000.0 / gw_f, "sy": ph / 1000.0 / gh_f, "opacity": opacity}
    doc = append_image_templates(omap.read_text(encoding="utf-8"), [template])
    omap.write_text(doc, encoding="utf-8")
    return {"added": ["bg_dmr.png"], "skipped": []}


_ORTHO_BG_MPP = 1.0        # rozlišení ortofoto podkladu [m/px]; 1 m stačí na verify (menší = ostřejší + větší)


def _existing_ortho_templates(doc: str) -> list[str]:
    """Najde ortofoto podklady bez ohledu na historický název (`ortofoto.png` vs `bg_ortho.png`).

    Důležité pro idempotenci: DEV mapy dostanou `ortofoto.png` už při `generate_map(ortho=True)`,
    zatímco dodatečný helper používá `bg_ortho.png`. Oba jsou stejný typ podkladu, takže stačí jeden.
    """
    return [
        name for name in image_template_names(doc)
        if any(token in name.lower() for token in ("ortho", "orto", "photo"))
    ]


def attach_ortho(map_dir: str | pathlib.Path, omap_name: str | None = None,
                 opacity: float = 0.5, target_mpp: float = _ORTHO_BG_MPP) -> dict:
    """Připne ČÚZK ortofoto obdélník jako podkladový template do `.omap` mapy (izomorf
    `attach_dmr_hillshade`). Pro mapy bez ortofota (KPI měřicí mapy — `measure_dod` je dělá s
    ortho=False); DEV mapy ho už mají z `--ortho`, Buschdörfl z `add_backgrounds`. APPEND (zachová
    sken/hillshade). No silent fallback: chybí-li vstup, raisuje. Vrací {"added":[...], "skipped":[...]}."""
    map_dir = pathlib.Path(map_dir)
    rgb, rgb_pgw, meta_p = map_dir / "rgb.png", map_dir / "rgb.pgw", map_dir / "meta.json"
    omap = _resolve_omap(map_dir, omap_name)
    for req in (rgb, rgb_pgw, meta_p, omap):
        if not req.exists():
            raise FileNotFoundError(f"{map_dir}: chybí {req.name} (mapa není hotová)")

    doc = omap.read_text(encoding="utf-8")
    existing = _existing_ortho_templates(doc)
    if existing:
        return {"added": [], "skipped": [("bg_ortho.png", f"ortofoto už existuje: {', '.join(existing)}")]}

    from ortofoto import fetch_ortofoto                    # lokální import (síťový konektor)
    with Image.open(rgb) as im:
        gW, gH = im.size
    gpgw = _read_pgw(rgb_pgw)
    scale = int(json.loads(meta_p.read_text(encoding="utf-8"))["scale"].split(":")[1])
    mpp_x, mpp_y = abs(gpgw[0]), abs(gpgw[4])
    _, _, _, _, cx, cy = _bbox_from_pgw(gpgw, gW, gH)
    world_w, world_h = gW * mpp_x, gH * mpp_y
    lon, lat = _SJTSK_TO_WGS84.transform(cx, cy)
    o_w = max(1, min(_DMR_BG_MAX_PX, round(world_w / target_mpp)))  # sdílí strop s DMR (ČÚZK + RAM)
    o_h = max(1, min(_DMR_BG_MAX_PX, round(world_h / target_mpp)))
    arr = fetch_ortofoto(lat, lon, gW, gH, world_h, o_w, o_h)       # bbox = build_bbox(...,tile_m=world_h)
    Image.fromarray(arr).save(map_dir / "bg_ortho.png")

    pw, ph = gW * mpp_x * 1e6 / scale, gH * mpp_y * 1e6 / scale     # paper µm
    template = {"name": "bg_ortho.png", "sx": pw / 1000.0 / o_w, "sy": ph / 1000.0 / o_h, "opacity": opacity}
    doc = append_image_templates(doc, [template])
    omap.write_text(doc, encoding="utf-8")
    return {"added": ["bg_ortho.png"], "skipped": []}


def attach_livelox_scan(map_dir: str | pathlib.Path, cid_dir: str | pathlib.Path,
                        omap_name: str | None = None, opacity: float = _BG_OPACITY) -> dict:
    """Připne ORIGINÁLNÍ Livelox sken (`<cid_dir>/map.png`) jako podkladový template do `.omap` mapy.

    Izomorf `attach_dmr_hillshade`/`attach_ortho`, ale zdroj = sken kartografovy mapy a georef = rotovaný
    Livelox quad (`_scan_inverse` z `<cid_dir>/meta.json`), ne axis-aligned bbox. Účel: vizuální verify —
    uživatel přepne sken přes vygenerovanou vektorovou mapu a vidí, kde se generátor trefil. APPEND
    (zachová ortofoto/hillshade). No silent fallback: chybí-li sken/meta, zaloguj a vrať bez připnutí
    (sken nemusí existovat u DEV `--location` map → orchestrátor ho jen vynechá, ne raise)."""
    map_dir = pathlib.Path(map_dir)
    cid_dir = pathlib.Path(cid_dir)
    rgb, rgb_pgw, meta_p = map_dir / "rgb.png", map_dir / "rgb.pgw", map_dir / "meta.json"
    omap = _resolve_omap(map_dir, omap_name)
    scan, cid_meta = cid_dir / "map.png", cid_dir / "meta.json"
    for req in (rgb, rgb_pgw, meta_p, omap, scan, cid_meta):
        if not req.exists():
            print(f"⚠ {map_dir.name}: chybí {req.name} → Livelox sken NEpřipnut", file=sys.stderr)
            return {"added": [], "skipped": [("bg_scan.png", f"chybí {req.name}")]}

    with Image.open(rgb) as im:
        gW, gH = im.size
    gpgw = _read_pgw(rgb_pgw)
    scale = int(json.loads(meta_p.read_text(encoding="utf-8"))["scale"].split(":")[1])
    mpp_x, mpp_y = abs(gpgw[0]), abs(gpgw[4])
    pw, ph = gW * mpp_x * 1e6 / scale, gH * mpp_y * 1e6 / scale     # paper µm (mirror add_backgrounds)

    g = _georef_grid(json.loads(cid_meta.read_text(encoding="utf-8")))
    with Image.open(scan) as im:
        Wm, Hm = im.size
        src = np.asarray(im.convert("RGB"), dtype=np.uint8)
    scan_inv = _scan_inverse(g["quad"], Wm, Hm)                     # S-JTSK → sken px (rotovaný quad)
    out_w, out_h = _bg_out_size(gW, gH)
    warped = _warp_to_gen(src, scan_inv, gpgw, gW, gH, out_w, out_h)
    Image.fromarray(warped).save(map_dir / "bg_scan.png")

    template = {"name": "bg_scan.png", "sx": pw / 1000.0 / out_w, "sy": ph / 1000.0 / out_h, "opacity": opacity}
    doc = append_image_templates(omap.read_text(encoding="utf-8"), [template])
    omap.write_text(doc, encoding="utf-8")
    return {"added": ["bg_scan.png"], "skipped": []}


def _bbox_area(bb: tuple[float, float, float, float]) -> float:
    """Plocha bboxu v m²; záporné/rozhozené průniky se seknou na nulu."""
    return max(0.0, bb[2] - bb[0]) * max(0.0, bb[3] - bb[1])


def _bbox_intersection_area(a: tuple[float, float, float, float],
                            b: tuple[float, float, float, float]) -> float:
    """Plocha průniku dvou S-JTSK bboxů v m²."""
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    return _bbox_area((x0, y0, x1, y1))


def _map_sjtsk_bbox(map_dir: pathlib.Path) -> tuple[float, float, float, float]:
    """Bbox hotové `maps/` mapy v S-JTSK podle `rgb.pgw`.

    Název mapy není spolehlivý klíč k Livelox korpusu. Souřadnice jsou pravda: podle nich jde najít
    i sken s úplně jiným názvem závodu/mapy.
    """
    with Image.open(map_dir / "rgb.png") as im:
        gW, gH = im.size
    xmin, ymin, xmax, ymax, *_ = _bbox_from_pgw(_read_pgw(map_dir / "rgb.pgw"), gW, gH)
    return xmin, ymin, xmax, ymax


def find_livelox_scan_candidates(map_dir: str | pathlib.Path,
                                 corpus: str | pathlib.Path = _CORPUS,
                                 limit: int = 10) -> list[dict]:
    """Najde lokální Livelox skeny podle překryvu souřadnic s hotovou `maps/` mapou.

    Vrací seřazené kandidáty s poměrem pokrytí mapového výseku (`map_coverage`) a pokrytí samotného
    skenu (`scan_coverage`). `map_coverage` je hlavní metrika: chceme co největší kus aktuální mapy.
    """
    map_dir = pathlib.Path(map_dir)
    corpus = pathlib.Path(corpus)
    mbb = _map_sjtsk_bbox(map_dir)
    ma = _bbox_area(mbb)
    rows: list[dict] = []
    for meta_p in sorted(corpus.glob("*/meta.json")):
        cid_dir = meta_p.parent
        if not (cid_dir / "map.png").exists():
            continue
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            g = _georef_grid(meta)
        except Exception as exc:
            rows.append({"cid_dir": cid_dir, "error": str(exc), "map_coverage": 0.0, "scan_coverage": 0.0})
            continue
        sbb = (g["xmin"], g["ymin"], g["xmax"], g["ymax"])
        inter = _bbox_intersection_area(mbb, sbb)
        if inter <= 0:
            continue
        sa = _bbox_area(sbb)
        rows.append({
            "cid_dir": cid_dir,
            "class_id": cid_dir.name,
            "name": meta.get("name") or "",
            "map_coverage": inter / ma if ma else 0.0,
            "scan_coverage": inter / sa if sa else 0.0,
        })
    rows.sort(key=lambda r: (r["map_coverage"], r["scan_coverage"]), reverse=True)
    return rows[:limit]


def attach_best_livelox_scan(map_dir: str | pathlib.Path, omap_name: str | None = None,
                             min_map_coverage: float = 0.01) -> dict:
    """Připne nejlepší lokální Livelox sken podle souřadnicového překryvu.

    Je to tolerantní post-process pro `maps/`: pokud už `bg_scan.png` existuje nebo žádný sken
    nepřekryje aspoň `min_map_coverage`, nic nepřipíná a výsledek zapíše do `skipped`.
    """
    map_dir = pathlib.Path(map_dir)
    omap = _resolve_omap(map_dir, omap_name)
    doc = omap.read_text(encoding="utf-8")
    if "bg_scan.png" in image_template_names(doc):
        return {"added": [], "skipped": [("bg_scan.png", "sken už existuje")], "candidate": None}

    candidates = find_livelox_scan_candidates(map_dir, limit=1)
    if not candidates or candidates[0]["map_coverage"] < min_map_coverage:
        return {"added": [], "skipped": [("bg_scan.png", "nenalezen Livelox překryv")], "candidate": None}

    best = candidates[0]
    res = attach_livelox_scan(map_dir, best["cid_dir"], omap_name=omap_name)
    res["candidate"] = best
    return res


def attach_verify_backgrounds(map_dir: str | pathlib.Path, cid_dir: str | pathlib.Path | None = None,
                              omap_name: str | None = None) -> dict:
    """Doplní k hotové `maps/` mapě verify podklady: DMR hillshade + (je-li `cid_dir`) Livelox sken.

    Volá se z generačních CLI cest (`generator.main` DEV `--location`, `pairs.py map`) po renderu —
    `maps/` = lidská prohlížecí mapa (verify), proto podklady; tréninkové páry v `resources/livelox/`
    je NEdostávají (model čte rgb+labels, ne podklady; Sez. 104 oddělení). Ortofoto NEřeší — to připíná
    `generate_map(ortho=True)` (default) už při renderu; tento orchestrátor doplňuje zbytek. `cid_dir`
    None = DEV mapa bez Livelox skenu (jen DMR). Slučuje výsledky obou attach_* (added/skipped)."""
    res = {"added": [], "skipped": []}
    r = attach_dmr_hillshade(map_dir, omap_name=omap_name)
    res["added"] += r["added"]; res["skipped"] += r["skipped"]
    if cid_dir is not None:
        r = attach_livelox_scan(map_dir, cid_dir, omap_name=omap_name)
        res["added"] += r["added"]; res["skipped"] += r["skipped"]
    return res


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    arg = sys.argv[1] if len(sys.argv) > 1 else "1088447"
    if arg == "batch":
        add_backgrounds_batch()
    elif arg == "dmr":
        # `dmr <maps/složka>` = připni DMR hillshade na jednu hotovou mapu (DEV/KPI/Buschdörfl)
        r = attach_dmr_hillshade(sys.argv[2])
        print(f"{sys.argv[2]}: DMR hillshade {r['added']}")
    elif arg == "ortho":
        # `ortho <maps/složka>` = připni ČÚZK ortofoto obdélník (mapy bez ortofota, např. KPI)
        r = attach_ortho(sys.argv[2])
        print(f"{sys.argv[2]}: ortofoto {r['added']}")
    elif arg == "scan":
        # `scan <maps/složka> <classId>` = připni originální Livelox sken (verify nad gen mapou)
        r = attach_livelox_scan(sys.argv[2], _CORPUS / sys.argv[3])
        print(f"{sys.argv[2]}: Livelox sken {r['added']} {r['skipped']}")
    elif arg == "scan-auto":
        # `scan-auto <maps/složka>` = najdi nejlepší Livelox sken podle souřadnicového překryvu
        r = attach_best_livelox_scan(sys.argv[2])
        cand = r.get("candidate")
        suffix = (f" · {cand['class_id']} {cand['name']} map={cand['map_coverage']:.1%} "
                  f"scan={cand['scan_coverage']:.1%}") if cand else ""
        print(f"{sys.argv[2]}: Livelox sken {r['added']} {r['skipped']}{suffix}")
    else:
        r = add_backgrounds(_CORPUS / arg / "gen")
        print(f"{arg}: přidáno {r['added']}, přeskočeno {r['skipped']}")
