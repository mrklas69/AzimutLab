#!/usr/bin/env python3
"""Část A nástroje ISOM GT factory: z reálné mapy vyrobí SET dlaždic 512×512 ke kuraci.

Mřížka 512×512 přes sken, ponechá jen dlaždice s dost zeleně (téma `green_points` →
417/418/419 jsou jen ve vegetaci, takže bílé/cestní dlaždice přeskočíme) NEBO dlaždice,
co obsahují detekci. Každou ponechanou dlaždici předvyplní detekcemi z `*_poc.py`.
Výstup = adresář se dlaždicemi PNG + `tile_gt.json` (kompletní GT se dokuruje v UI = Část B).

**Recall-first:** mřížka pokrývá CELOU relevantní plochu (ne jen okolí detekcí), aby šlo
doložit, že symbol umíme najít na 100 % — kurátor v UI doplní i přehlédnuté (= FN).

    .venv\\Scripts\\python.exe isom_scan/build_tile_set.py \\
        --detections temp/vegetation_points_buschdorfl_area60/detections.json \\
        --theme green_points --out temp/tileset_buschdorfl_green
"""

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

Image.MAX_IMAGE_PIXELS = None
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "model"))
from mpp import resample_to_mpp, CANONICAL_MPP  # noqa: E402  (sys.path util, ne balík)

# Téma = filtr ISOM kódů relevantních pro relaci (paleta v UI je CELÁ, tohle je jen fokus + filtr dlaždic).
THEMES = {
    "green_points": {"codes": ["417", "418", "419"], "filter": "green"},
}


def _resolve_scan(raw: str) -> Path:
    """Najde sken z detections.image; absolutní cesta z jiného stroje → zkus i relativně k repu."""
    p = Path(raw)
    for cand in (p, REPO_ROOT / p):
        if cand.exists():
            return cand.resolve()
    raise SystemExit(f"Chybi sken: {raw}")


def _green_fraction(tile_rgb: np.ndarray) -> float:
    """Podíl zeleně-dominujících pixelů = proxy pro vegetaci (kde mohou být 417/418/419).

    Volnější než bodový detektor (chytá i plošnou zeleň 405/406/408/410) — jde nám jen
    o to, jestli v dlaždici VŮBEC může zelený symbol být."""
    r = tile_rgb[:, :, 0].astype(int)
    g = tile_rgb[:, :, 1].astype(int)
    b = tile_rgb[:, :, 2].astype(int)
    mask = (g > r + 15) & (g > b + 15) & (g > 90)
    return float(mask.mean())


def _map_mask(arr: np.ndarray) -> np.ndarray:
    """Maska mapové oblasti (vs bílé okolí Livelox skenu).

    Past: bílá je i LES (405) → nesmíme ho vyhodit. Proto: vezmeme ne-bílé pixely,
    VYPLNÍME uzavřené díry (les obklopený mapou se započte) a necháme největší souvislou
    komponentu = vlastní mapa. Okolí (bílá otevřená k okraji skenu) zůstane mimo masku."""
    r = arr[:, :, 0]; g = arr[:, :, 1]; b = arr[:, :, 2]
    nonwhite = ~((r > 235) & (g > 235) & (b > 235))
    filled = ndi.binary_fill_holes(nonwhite)
    labels, n = ndi.label(filled)
    if n <= 1:
        return filled
    # největší komponenta (mimo pozadí 0) = mapové pole
    sizes = ndi.sum(np.ones_like(labels, dtype=np.int64), labels, index=range(1, n + 1))
    return labels == (int(np.argmax(sizes)) + 1)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _contact_sheet(tiles: list, out_dir: Path, thumb: int = 120, cols: int = 8) -> Path:
    """Montáž zmenšených ponechaných dlaždic pro rychlou vizuální kontrolu (oko = arbitr).

    Dlaždice s předvyplněnou detekcí dostanou zelený rámeček, ať je hned vidět záběr."""
    if not tiles:
        sheet = Image.new("RGB", (480, 80), "white")
        sheet.save(out_dir / "preview.png")
        return out_dir / "preview.png"
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (cols * thumb, rows * thumb), (40, 40, 40))
    from PIL import ImageDraw
    for i, t in enumerate(tiles):
        im = Image.open(out_dir / t["file"]).convert("RGB").resize((thumb, thumb), Image.Resampling.BILINEAR)
        if t["symbols"]:
            ImageDraw.Draw(im).rectangle([0, 0, thumb - 1, thumb - 1], outline=(0, 230, 0), width=3)
        sheet.paste(im, ((i % cols) * thumb, (i // cols) * thumb))
    sheet.save(out_dir / "preview.png")
    return out_dir / "preview.png"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--detections", type=Path, required=True, help="detections.json z *_poc.py")
    ap.add_argument("--scan", type=Path, default=None, help="Volitelně přepiš sken (jinak z detections.image).")
    ap.add_argument("--theme", default="green_points", choices=list(THEMES))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tile", type=int, default=512)
    ap.add_argument("--green-thr", type=float, default=0.04, help="Min. podíl zeleně, jinak dlaždici zahodíme.")
    ap.add_argument("--map-thr", type=float, default=0.6,
                    help="Min. podíl dlaždice uvnitř mapové oblasti (zahodí okrajové dlaždice s bílým okolím).")
    ap.add_argument("--src-mpp", type=float, default=None,
                    help="Zdrojové m/px skenu (z meta.json effectiveMppX). Resample na kanonické 1,33 m/px.")
    args = ap.parse_args()

    det = json.loads(args.detections.read_text(encoding="utf-8"))
    scan_path = args.scan.resolve() if args.scan else _resolve_scan(det.get("image", ""))
    theme = THEMES[args.theme]
    theme_codes = set(theme["codes"])

    img = Image.open(scan_path).convert("RGB")
    arr = np.asarray(img)
    H, W = arr.shape[:2]

    # detekce relevantní pro téma → ploché body se souřadnicemi ve skenu
    points = []
    for d in det.get("detections", []):
        code = str(d.get("code"))
        if code not in theme_codes:
            continue
        for p in d.get("points", []):
            points.append((code, float(p["x"]), float(p["y"]), float(p.get("score", 0.0))))

    # Resample na kanonické měřítko dlaždice: Livelox originál (~0,56 m/px) je jemnější než
    # CANONICAL_MPP 1,33 → downscale, ať tréninkové dlaždice lícují s reconstructory. Detekce
    # přepočítáme STEJNÝM faktorem (geometrie zůstane zarovnaná).
    if args.src_mpp:
        f = args.src_mpp / CANONICAL_MPP
        if abs(f - 1.0) >= 0.005:
            arr = resample_to_mpp(arr, args.src_mpp)
            H, W = arr.shape[:2]
            points = [(c, x * f, y * f, s) for (c, x, y, s) in points]
            print(f"resample {args.src_mpp:.3f} -> {CANONICAL_MPP} m/px (faktor {f:.3f}) -> {W}x{H}")

    out = args.out
    if (out / "tiles").exists():
        shutil.rmtree(out / "tiles")   # smaž dlaždice z předchozího běhu, ať nezůstanou sirotci
    (out / "tiles").mkdir(parents=True, exist_ok=True)
    map_mask = _map_mask(arr)   # mapová oblast vs bílé okolí skenu
    tiles = []
    total_cells = 0
    skipped_border = 0
    for row, y0 in enumerate(range(0, H, args.tile)):
        for col, x0 in enumerate(range(0, W, args.tile)):
            total_cells += 1
            y1 = min(y0 + args.tile, H)
            x1 = min(x0 + args.tile, W)
            # dlaždice převážně mimo mapu (bílé okolí) → zahodit (i kdyby měla zeleň/detekci = artefakt okraje)
            map_cov = float(map_mask[y0:y1, x0:x1].mean())
            if map_cov < args.map_thr:
                skipped_border += 1
                continue
            sub = arr[y0:y1, x0:x1]
            gf = _green_fraction(sub)
            # detekce uvnitř dlaždice → lokální souřadnice (0..tile)
            syms = [
                {"code": c, "x": round(x - x0, 1), "y": round(y - y0, 1),
                 "score": round(s, 3), "origin": "detected", "status": "unreviewed"}
                for (c, x, y, s) in points if x0 <= x < x1 and y0 <= y < y1
            ]
            # ponech dlaždici, když má dost zeleně NEBO obsahuje detekci (jinak tam zelený symbol nebude)
            if gf < args.green_thr and not syms:
                continue
            tid = f"r{row:02d}_c{col:02d}"
            Image.fromarray(sub).save(out / "tiles" / f"{tid}.png")
            tiles.append({
                "id": tid, "x0": x0, "y0": y0, "w": int(x1 - x0), "h": int(y1 - y0),
                "green_frac": round(gf, 4), "map_cov": round(map_cov, 3), "file": f"tiles/{tid}.png",
                "symbols": syms, "reviewed": False,
            })

    manifest = {
        "_status": "TILESET_BUILT; needs human GT review (Cast B UI)",
        "_doc": "GT set dlazdic pro KOMPAS validaci. symbols[].status: unreviewed/confirmed(TP)/"
                "rejected(FP); origin: detected/added(FN). GT = confirmed + added.",
        "theme": args.theme,
        "theme_codes": theme["codes"],
        "source_map": scan_path.parent.name,
        "image": str(scan_path),
        "image_sha256": _sha256(scan_path),
        "tile_px": args.tile,
        "green_thr": args.green_thr,
        "detector": {"detections": str(args.detections)},
        "tiles": tiles,
    }
    (out / "tile_gt.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    sheet = _contact_sheet(tiles, out)

    n_with = sum(1 for t in tiles if t["symbols"])
    n_sym = sum(len(t["symbols"]) for t in tiles)
    print(f"sken {scan_path.name} {W}x{H} -> mrizka {total_cells} bunek")
    print(f"dlazdic ponechano: {len(tiles)} (s detekci: {n_with}, jen zelen: {len(tiles)-n_with}; "
          f"zahozeno okraj/bila: {skipped_border})")
    print(f"predvyplnenych detekci: {n_sym} (temata {theme['codes']})")
    print(f"out: {out}/tile_gt.json | preview: {sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
