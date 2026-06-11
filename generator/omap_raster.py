"""omap_raster.py — rasterizace plošných (Area) ISOM symbolů z .omap → label rastr (Y pro Png2Area, Sez. 87).

Role v pipeline (reframe Sez. 79/80): reconstructor() se učí na párech [scan.png, .omap]. X = degradovaný
render (degrade.py, Sez. 86); Y = TENHLE label rastr, vyrobený rasterizací plošných symbolů z téže .omap.
Y je odvozeno z .omap (NE z render masek `mask_*.png`) záměrně — .omap je jediná pravda, kterou má model
rekonstruovat → pár je self-konzistentní (Y nezávisí na render artefaktech). První ze tří CV úloh dekompozice
podle OOM geometrie (Sez. 80): Png2Area (type=4 plochy) | Png2Point (type=1 body) | Png2Line (type=2 linie).

Co dělá: .omap → label rastr (H×W, STEJNÝ grid jako scan.png/rgb.png), každý px nese ISOM area třídu
(0 = pozadí/bez plochy, 1..N = jednotlivé area kódy). Per-ISOM-kód (volba Sez. 87): GT nese plnou informaci,
seskupení tříd je modelové rozhodnutí NAD rasterizací (DRY), ne věc Y-pipeline — izomorfní s model/png2area/tile.py.

Transformace paper µm → px (měřeno Sez. 87, robustní z meta.json): omap_export.paper() sází objekty jako
paper_x = (gx/(gw-1) - 0.5)·pw, pw = world_w_m·1e6/scale; render mapuje grid↔px lineárně → po dosazení
px_x = (paper_x/pw + 0.5)·W (NEZÁVISLÉ na gridu, jen pw/ph/W/H). pw/ph z meta georef bbox + scale.

Parser: object symbol="N" = N-tý symbol v <symbols> (pořadový index; ověřeno Sez. 87: v naší template
id == index). Díry: ring-split na hole-flagu (bit 16) — konvence omap_export (flag 18 = hranice ringu, 2 =
poslední close). DRY pozn.: even-odd scanline existuje i v generator._fill_rings_scanline (monolit) — tady
vlastní bbox-lokální PIL rasterizace (KISS, bez těžkého generator importu); extrakce až 3. konzument.

Sys.path skript (fáze B, ne balík). Spouštět z kořene: `python generator/omap_raster.py [lokalita]`.
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

_REPO_ROOT = Path(__file__).resolve().parents[1]
Image.MAX_IMAGE_PIXELS = None

# Z-order plošných ISOM kódů (zdola nahoru) → label index (1..N; 0 = pozadí/bez plochy). Pořadí = render
# z-order (501.1 administrativní base DOLE … 521 budovy NAHOŘE); překryv řeší pozdější kresba (ověř vizuálně).
# Kódy = SKUTEČNÉ kódy symbolů v generované .omap (pole=412.1, kolejiště 501 je v template `combined` ale plošné).
# Voda = 301 (combined type=16, se břehovou linií; Sez. 58 změna z 301.1 — generátor `generator.py:3968` ji od
# té doby zapisuje jako 301, NE 301.1). Drift opraven Sez. 110: AREA_ZORDER mělo stale 301.1 → omap_raster vodu
# tiše zahazoval z Y (Lidové sady 58/0, měřeno; conceptual-integrity bug, ChatGPT %AUDIT:CODE).
# Statický (NE per-soubor): třídy MUSÍ být konzistentní napříč korpusem, jinak by se modelu rozhodily.
# Tohle je SSoT area schématu: omap_export.AREA_CODES (close-flag membership) se z TOHOTO seznamu odvozuje
# (`frozenset(AREA_ZORDER)`) → nemůžou se znovu rozejít. Z-order navíc = raster-specifický (export ho nepotřebuje).
AREA_ZORDER = [
    "501.1",  # Paved area bez obrysu (administrativní výplň sídel) — base vespod
    "520",    # Out-of-bounds (olivová: hřbitov/privátní/sad/lom)
    "401",    # Open land (žlutá)
    "403",    # Rough open land (bledá žlutá, separace Sez. 92)
    "402",    # Open land se stromy (park)
    "402.1",  # Open land s keři (ostatní udržovaná zeleň)
    "412.1",  # Cultivated land (pole) — combined složka 401+412.1
    "301",    # Vodní plocha (combined se břehovou linií, Sez. 58; BYLO 301.1 → drift Sez. 110)
    "308",    # Marsh (mokřad)
    "310",    # Indistinct marsh (nezřetelná bažina, pseudo Sez. 99)
    "406",    # Forest: slow running (světlá zeleň)
    "408",    # Forest: walk (střední zeleň)
    "410",    # Forest: fight (tmavá zeleň)
    "206",    # Gigantic boulder / rock area
    "208",    # Boulder field
    "501",    # Paved area s obrysem (kolejiště)
    "521",    # Building (budovy) — nahoře
]
CODE_TO_LABEL = {code: i + 1 for i, code in enumerate(AREA_ZORDER)}
LABEL_NAME = {0: "pozadí", **{i + 1: code for i, code in enumerate(AREA_ZORDER)}}
N_AREA = len(AREA_ZORDER) + 1   # + pozadí (label 0)

# Vizualizační barvy (RGB) pro verify overlay — přibližná ISOM paleta (ne render, jen kontrola zarovnání/z-order).
LABEL_VIS = {
    0: (255, 255, 255),
    CODE_TO_LABEL["501.1"]: (200, 170, 140), CODE_TO_LABEL["520"]: (160, 150, 60),
    CODE_TO_LABEL["401"]: (252, 221, 118), CODE_TO_LABEL["403"]: (254, 235, 175),
    CODE_TO_LABEL["402"]: (250, 235, 160),
    CODE_TO_LABEL["402.1"]: (210, 225, 130), CODE_TO_LABEL["412.1"]: (245, 215, 140),
    CODE_TO_LABEL["301"]: (50, 162, 222), CODE_TO_LABEL["308"]: (120, 200, 230),
    CODE_TO_LABEL["310"]: (165, 215, 235),   # Indistinct marsh — světlejší modrá (řidší pattern)
    CODE_TO_LABEL["406"]: (181, 230, 181), CODE_TO_LABEL["408"]: (120, 200, 140),
    CODE_TO_LABEL["410"]: (40, 160, 90), CODE_TO_LABEL["206"]: (120, 120, 120),
    CODE_TO_LABEL["208"]: (150, 150, 150), CODE_TO_LABEL["501"]: (180, 140, 110),
    CODE_TO_LABEL["521"]: (30, 30, 30),
}


def _strip(tag: str) -> str:
    return tag.split("}")[-1]


def _split_rings(text: str) -> list[list[tuple[int, int]]]:
    """coords text → [outer, díra…], prsten = [(x,y) paper µm]. Split na hole-flagu (bit 16).

    OOM coord flag: bit 16 = „hole point" (konec prstenu, následuje vnitřní prsten), bit 2 = close,
    bit 1 = bezier control. Konvence omap_export.area_object: hranice mezi prsteny nese flag 18 (16|2),
    POSLEDNÍ prsten končí jen 2 (bez bitu 16). Jednoprstencový objekt má poslední bod 18 → split ukončí
    a trailing prázdný prsten se zahodí (filtr len ≥ 3). Bezier control body bereme jako vrcholy
    (aproximace polygonem — naše plochy jsou vektorizované polygony, ne bezier; pro foundation OK)."""
    rings: list[list[tuple[int, int]]] = []
    cur: list[tuple[int, int]] = []
    for tok in text.strip().split(";"):
        nums = tok.split()
        if len(nums) < 2:
            continue
        try:
            x, y = int(nums[0]), int(nums[1])
        except ValueError:
            continue
        flag = int(nums[2]) if len(nums) >= 3 else 0
        cur.append((x, y))
        if flag & 16:                       # hole point = konec prstenu, následuje vnitřní
            rings.append(cur)
            cur = []
    if cur:
        rings.append(cur)
    return [r for r in rings if len(r) >= 3]


def parse_area_objects(omap_path: Path) -> list[tuple[list, str]]:
    """Vrátí [(rings, code)] plošných objektů z .omap — rings = [outer, díra…] v paper µm.

    Bere JEN objekty, jejichž ISOM kód je v CODE_TO_LABEL (plošné symboly Png2Area); liniové/bodové
    se přeskočí. `object symbol="N"` = index do <symbols> (pořadový; ověřeno Sez. 87 id==index)."""
    root = ET.parse(omap_path).getroot()
    sp = next(e for e in root.iter() if _strip(e.tag) == "symbols")
    codes = [s.get("code") for s in sp if _strip(s.tag) == "symbol"]
    op = next(e for e in root.iter() if _strip(e.tag) == "objects")
    out: list[tuple[list, str]] = []
    for o in op.iter():
        if _strip(o.tag) != "object":
            continue
        si = int(o.get("symbol", -1))
        if not (0 <= si < len(codes)):
            continue
        code = codes[si]
        if code not in CODE_TO_LABEL:        # ne-plošný symbol → přeskoč
            continue
        c = next((x for x in o if _strip(x.tag) == "coords"), None)
        if c is None or not c.text:
            continue
        rings = _split_rings(c.text)
        if rings:
            out.append((rings, code))
    return out


def _paper_to_px(meta: dict):
    """Vrátí funkci paper µm → px (col,row) pro grid scan.png/rgb.png (transformace měřená Sez. 87).

    px_x = (paper_x/pw + 0.5)·W, pw = world_w_m·1e6/scale. world_w/h_m z georef bbox (S-JTSK),
    W,H z canvas, scale z isom. Bez Y-flip (paper y roste dolů = px row roste dolů, jako omap_export)."""
    W, H = meta["canvas"]
    xmin, ymin, xmax, ymax = meta["georef"]["bbox_sjtsk"]
    scale = float(meta.get("isom", {}).get("scale") or str(meta["scale"]).split(":")[-1])
    um_per_m = 1_000_000.0 / scale
    pw = (xmax - xmin) * um_per_m
    ph = (ymax - ymin) * um_per_m

    def to_px(x: float, y: float) -> tuple[float, float]:
        return (x / pw + 0.5) * W, (y / ph + 0.5) * H

    return to_px, W, H


def rasterize(omap_path: Path, meta: dict) -> np.ndarray:
    """.omap → label rastr (H,W) uint8: plošné ISOM symboly per-kód, z-order zdola nahoru.

    Objekty se třídí podle CODE_TO_LABEL (= z-order) a kreslí od spodu — pozdější (vyšší vrstva)
    přepíše. Díry se vyříznou jen v rámci OBJEKTU (per-objekt bbox-lokální maska: outer=1, díry=0 →
    label se v dírách NEmění → odhalí plochu pod ní z nižší z-order vrstvy). Bbox-lokální = O(Σ ploch
    objektů), ne O(N_objektů × H×W)."""
    to_px, W, H = _paper_to_px(meta)
    label = np.zeros((H, W), dtype=np.uint8)
    objs = parse_area_objects(omap_path)
    objs.sort(key=lambda o: CODE_TO_LABEL[o[1]])     # z-order: nižší label = dřív (dole)
    for rings, code in objs:
        cls = CODE_TO_LABEL[code]
        rings_px = [[to_px(x, y) for x, y in r] for r in rings]
        xs = [p[0] for r in rings_px for p in r]
        ys = [p[1] for r in rings_px for p in r]
        x0 = max(0, int(np.floor(min(xs)))); x1 = min(W, int(np.ceil(max(xs))))
        y0 = max(0, int(np.floor(min(ys)))); y1 = min(H, int(np.ceil(max(ys))))
        if x1 <= x0 or y1 <= y0:                     # mimo canvas (separace v S-JTSK může přesah)
            continue
        m = Image.new("L", (x1 - x0, y1 - y0), 0)
        d = ImageDraw.Draw(m)
        d.polygon([(x - x0, y - y0) for x, y in rings_px[0]], fill=1)
        for hole in rings_px[1:]:                    # díry zpět na 0 → label v nich nezměním
            d.polygon([(x - x0, y - y0) for x, y in hole], fill=0)
        sub = label[y0:y1, x0:x1]
        sub[np.asarray(m, dtype=bool)] = cls
    return label


def colorize(label: np.ndarray) -> Image.Image:
    """Label rastr → barevný RGB obrázek (LABEL_VIS) pro vizuální verify."""
    vis = np.zeros((*label.shape, 3), dtype=np.uint8)
    for lab, col in LABEL_VIS.items():
        vis[label == lab] = col
    return Image.fromarray(vis)


def rasterize_map_dir(map_dir: Path) -> np.ndarray:
    """Pohodlný wrapper: <map_dir>/<*.omap> + <map_dir>/meta.json → label rastr.

    .omap se hledá podle názvu složky (generate_map ho pojmenuje po lokalitě/cid)."""
    meta = json.loads((map_dir / "meta.json").read_text(encoding="utf-8"))
    omap = map_dir / f"{map_dir.name}.omap"
    if not omap.exists():                            # build_pair píše gen/<cid>.omap? fallback na první .omap
        cands = sorted(map_dir.glob("*.omap"))
        if not cands:
            raise FileNotFoundError(f"žádná .omap v {map_dir}")
        omap = cands[0]
    return rasterize(omap, meta)


def main(name: str) -> None:
    """Verify běh na jedné vygenerované mapě: label PNG + barevný overlay přes rgb.png (oko = source)."""
    map_dir = _REPO_ROOT / "maps" / name
    label = rasterize_map_dir(map_dir)
    H, W = label.shape
    v, n = np.unique(label, return_counts=True)
    print(f"{name}  {W}×{H}  area pokrytí {100 * (label > 0).mean():.1f} %")
    for lab, cnt in sorted(zip(v.tolist(), n.tolist()), key=lambda x: -x[1]):
        if lab == 0:
            continue
        print(f"  label {lab:2} {LABEL_NAME[lab]:7} {100 * cnt / label.size:5.1f} %  ({cnt} px)")

    # ulož label (grayscale) + overlay (label barva přes ztlumený render)
    Image.fromarray(label, mode="L").save(map_dir / "area_labels.png")
    colorize(label).save(map_dir / "area_labels_vis.png")
    rgb = np.asarray(Image.open(map_dir / "rgb.png").convert("RGB"))
    if rgb.shape[:2] == label.shape:
        base = (rgb.astype(np.float32) * 0.45 + 255 * 0.55).astype(np.uint8)
        ov = Image.fromarray(base)
        cov = colorize(label).convert("RGBA")
        cov.putalpha(Image.fromarray(((label > 0) * 150).astype(np.uint8)))
        ov = ov.convert("RGBA")
        ov.alpha_composite(cov)
        ov.convert("RGB").save(map_dir / "area_labels_overlay.png")
        print(f"  overlay → {map_dir / 'area_labels_overlay.png'}")
    print(f"  label   → {map_dir / 'area_labels.png'}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")     # Windows cp1250 vs Unicode (Sez. 74)
    except Exception:
        pass
    main(sys.argv[1] if len(sys.argv) > 1 else "Soví vrch")
