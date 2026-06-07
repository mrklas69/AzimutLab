"""separate.py — separace predikčních PLOŠNÝCH ISOM symbolů (Area) z reálné OB mapy → vektor → .omap.

ZÁRODEK MODULU (povýšeno z PoC, Sez. 82; zobecněno Sez. 83). Hlavní tah reframe (Sez. 79/80):
predikční vrstvy generátoru NEbrat z dat (forest-age ARCHIVOVÁN Sez. 82 — pokrytí jen 33 %
korpusu, IoU 0,12 s kresbou kartografa, přestřel zelené 3,3×), ale SEPAROVAT z reálné Livelox
mapy. Mapař = ground truth (nakreslil, co v terénu viděl), univerzální (každá keep mapa nese
barvu k separaci), a pár [render, .omap] je z definice KONZISTENTNÍ.

Role v pipeline (Sez. 80, A2): tahle algoritmická separace = LEVNÝ GT-FEEDER pro budoucí model
`Png2Area` (OOM area symbol = plošný = jedna ze tří CV úloh Png2Point/Png2Line/Png2Area). NEMÁ být
věrná na 100 % (PoC ~90 %) — kvalitu dotáhne model trénovaný na množství párů, ne leštění prahu
(zásada Sez. 82: „separace = feeder, neleštit"). Pod konstrukcí páru ze Sez. 80 (X = degradovaný
export z NAŠÍ .omap) nemusí být dokonce ani věrná původní mapě — jen půjčuje realistické tvary, aby
.omap nevypadala jako náhodné kaňky.

SCOPE (Sez. 83): separujeme JEN to, co generátor neumí z tvrdých ČÚZK dat — dnes plošná vegetace
(406/408/410), do budoucna paseky / podrost / hustník (až je map_gt klasifikuje rozšířením
referenčních barev). Voda / skály / budovy / cesty NEseparovat — ty jsou „real" část integrované
.omap (ZABAGED + DMR rock-relief); separace navíc = dvojí zdroj téhož symbolu + konflikt + porušení
DRY. Dekompozice dle OOM geometrie (type 1/2/4): tenhle modul dělá PLOCHY (Area, type=4); body
(posed/pramen) a linie (potok) by měly vlastní separaci (Png2Point/Png2Line) — dnes mimo.

Tok: map_gt separace (gt_labels 0-4/255; zelené 1/2/3 = 406/408/410) → per-třída maska → contourpy
vektorizace (REUSE rock_relief: _contour_rings/_group_holes/_rdp/_chaikin) → polygony [outer, díra…]
v image-px → omap_export.write_omap (image-px = grid, .omap nese podklad map.png pro OOM verify).

DALŠÍ KROK (Sez. 83 Příště): integrace do generate_map() — real ČÚZK vrstvy + tahle predikční
separace v JEDNÉ .omap (provenance real/predict) přes Livelox _georef_grid; per-classId orchestrátor.

Spouštět z kořene přes .venv (sys.path skript, fáze B).
"""
import json
import sys
import pathlib

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_closing, label, distance_transform_edt

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# connectors/ MUSÍ na path PŘED importem rock_relief — ten táhne `from dmr import …` (sourozenec
# v connectors/). generator/ je sys.path[0] při přímém spuštění; connectors/ doplníme my (sys.path
# skript, fáze B — ne balík).
sys.path.insert(0, str(_REPO_ROOT / "connectors"))
sys.path.insert(0, str(_REPO_ROOT / "generator"))

# rock_relief (vektorizační pipeline) i omap_export jsou sourozenci v generator/
from rock_relief import _contour_rings, _group_holes, _rdp, _chaikin  # noqa: E402
from omap_export import write_omap  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
_CORPUS_DIR = _REPO_ROOT / "resources" / "livelox"

# Registr plošných predikčních tříd: ISOM kód → {gt: map_gt label, vis: overlay barva, [pale_yellow]}.
# Zelené 3 úrovně jedou přímo z map_gt runnability labelu (1=406 slow, 2=408 walk, 3=410 fight).
# 403 (Sez. 92) = rozštěp žluté UVNITŘ open (gt label 4): map_gt 401 i 403 řadí do „open", odstínem
# je nerozliší → separace si je rozliší sama (`pale_yellow` → maska bledé žluté přes YELLOW_REFS).
# Staví na OČIŠTĚNÉM gt (map_gt: median + ignore přetisku + layout crop), jen v rámci open oddělí
# bledou (403) od syté (401, ta je real část — neseparujeme, scope Sez. 83).
#
# POZOR (nález Sez. 90): odstínová separace funguje JEN pro třídy odlišené ODSTÍNEM (401 sytá vs 403
# bledá — doloženo Sez. 92 bimodalitou žluté na 5 mapách + 3-way clusteringem oddělujícím i road).
# Pro třídy odlišené PATTERNEM (404 tečky, 407/409 pruhy, 412 mřížka) je nearest-color PRINCIPIÁLNĚ
# slepý — pattern vidí jen model s receptive fieldem (Png2Area CNN), ne separace. vectorize_level je agnostická.
AREA_CLASSES = {
    "406": {"gt": 1, "vis": (181, 230, 181)},
    "408": {"gt": 2, "vis": (120, 200, 140)},
    "410": {"gt": 3, "vis": (40, 160, 90)},
    "403": {"gt": 4, "pale_yellow": True, "vis": (254, 228, 139)},  # rough open (bledá žlutá uvnitř open)
}

# Reálné SCAN reference žlutooranžových odstínů (RGB), DOLOŽENÉ k-means na 5 vzorových mapách (Sez. 92).
# POZOR: tohle jsou barvy SKENU (jako map_gt.ISOM_REF), NE render palette (palette.py je generátorová,
# sytější). 403 se klasifikuje z reálné Livelox map.png, takže potřebuje scan barvy. Pořadí v poli =
# index: 0 = 403 bledá (Yellow 50 %), 1 = 401 sytá (Yellow 100 %), 2 = oranžová cesta (NE area — jen
# rozlišovač, aby cesta nepadla na 403), 3 = BÍLÁ papír (záchyt, viz níže). Bledá žlutá = nearest == 0.
#
# Bílá je tu kvůli nálezu Sez. 92 (vizuál 1088447): _fill_ignore zaplní velký okrajový IGNORE (papír
# mimo mapu, který _detect_map_area nezachytil) nejbližším labelem = open (4). Bílý papír je BLÍŽ
# bledé žluté než syté (403 má nejvyšší B z trojice) → falešné 403 na papíru. Čtvrtá reference (bílá)
# papír zachytí (nearest == 3, ne 0) → 403 zůstane jen na skutečně bledě žlutých plochách.
YELLOW_REFS = np.array([(254, 222, 154), (255, 200, 58), (227, 168, 118), (255, 255, 255)], dtype=np.int32)


def _is_pale_yellow(rgb: np.ndarray) -> np.ndarray:
    """Bool maska (H,W): pixel je bledá žlutá (403), tj. nejbližší z YELLOW_REFS je index 0.

    Nearest-color mezi žlutooranžovými odstíny + bílou — předpokládá, že volající už zúžil na „open"
    plochu (gt == 4), takže zeleň/modř sem nepřijdou; rozhoduje se bledá vs sytá vs cesta vs papír.
    Sytá (401)/cesta jsou real část → nevektorizují se, bílá = papír (záchyt), slouží jen k odlišení."""
    flat = rgb.reshape(-1, 3).astype(np.int32)
    d = ((flat[:, None, :] - YELLOW_REFS[None, :, :]) ** 2).sum(2)
    return (d.argmin(1) == 0).reshape(rgb.shape[:2])

# Cílové rozlišení separace (Sez. 85): downscale vstupu na ~1,33 m/px PŘED vektorizací. Dva důvody:
#   1) VÝKON — separace je O(n² prstenců); na jemném skenu (Branžež 0,56 mpp = 93 Mpx) trvá minuty.
#      Měřeno (Sez. 85, stand-in Soví vrch): downscale 0,56→1,33 = 31,6× zrychlení @ 5,6× méně px
#      (žrout #1 je super-lineární), věrnost velkých ploch zachována (GT-feeder ~90 %).
#   2) KONZISTENCE — MIN_AREA_PX/SIMPLIFY_PX jsou laděné na ~1,33 mpp; na jiném vstupním rozlišení
#      by znamenaly jinou fyzickou plochu. Sjednocením vstupu na 1,33 platí stejně napříč korpusem.
TARGET_MPP = 1.33

# čištění masky před vektorizací (image-px ~1,33 m/px): malý uzávěr scelí roztřepený okraj, min.
# plocha zahodí pixelový šum. ISOM min. mapovatelná plocha ~1 mm² = (10 m)² ≈ 56 px @ 1,33 m;
# bereme konzervativně 120 px (~2 mm²) — PoC neřeší drobky. RDP/Chaikin de-pixelují obrys.
CLOSE_ITERS = 1
MIN_AREA_PX = 120
SIMPLIFY_PX = 1.5
CHAIKIN_ITERS = 2


def _fill_ignore(label_map: np.ndarray, ignore: int = 255) -> np.ndarray:
    """„Prohlédne" fialový přetisk tratě: IGNORE pixel → nejbližší NE-ignore label (Sez. 83).

    map_gt dal fialovému přetisku (kroužky kontrol = symbol 704, spojnice = 705) label 255
    (Sez. 72 — dávalo smysl pro archivovaný ortofoto→runnability trénink, ignore = nepočítat loss).
    Pro SEPARACI ale ty pixely tvoří díry v zelené ploše → vykousnuté kroužky/linie (nález Sez. 83).
    Vegetace pod přetiskem reálně JE — `distance_transform_edt(return_indices)` přiřadí každý ignore
    pixel nejbližšímu skutečnému labelu: kroužek uvnitř zeleně → zelená, mimo zeleň → tamní label.
    Specifické pro separaci (nedělat v map_gt — tam ignore má vlastní smysl pro runnability GT)."""
    mask = label_map == ignore
    if not mask.any():
        return label_map
    # indices nejbližšího NE-ignore pixelu pro každý ignore pixel (EDT přes masku ignore)
    ri, ci = distance_transform_edt(mask, return_distances=False, return_indices=True)
    out = label_map.copy()
    out[mask] = label_map[ri[mask], ci[mask]]
    return out


def vectorize_level(mask: np.ndarray) -> list:
    """Boolean maska jedné třídy → polygony [outer, díra…] v image-px (REUSE rock_relief).

    Vrací list polygonů, každý = [vnější prsten, díra1, …]; prsten = np.array (col, row).
    Týž tvar jako rock_relief.detect_rock_areas / zabaged.geom_to_polygons → zapadne do
    omap_export.write_omap (area_object) i kreslení beze změny. Agnostická k třídě (žádné
    „veg") → unese i budoucí paseky/podrost beze změny."""
    m = binary_closing(mask, iterations=CLOSE_ITERS)
    # zahoď malé komponenty (pixelový šum)
    lab, n = label(m)
    if n:
        sizes = np.bincount(lab.ravel())
        for i in range(1, len(sizes)):
            if sizes[i] < MIN_AREA_PX:
                m[lab == i] = False
    if not m.any():
        return []
    rings = _contour_rings(m)                 # (col,row) prstence
    if not rings:
        return []
    out = []
    for poly in _group_holes(rings):          # [[outer, díra…], …]
        cleaned = [_chaikin(_rdp(r, SIMPLIFY_PX), CHAIKIN_ITERS) for r in poly if len(r) >= 4]
        if cleaned and len(cleaned[0]) >= 4:
            out.append(cleaned)
    return out


def _downscale_mask(mask: np.ndarray, f: float) -> np.ndarray:
    """Bool maska → downscale faktorem f NEAREST (ne bilineár — mezitřídní px by maska rozmazala)."""
    nw, nh = max(1, round(mask.shape[1] / f)), max(1, round(mask.shape[0] / f))
    return np.asarray(
        Image.fromarray(mask.astype(np.uint8) * 255, "L").resize((nw, nh), Image.NEAREST)) > 0


def separate_areas(label_map: np.ndarray, rgb: np.ndarray | None = None,
                   src_mpp: float | None = None, target_mpp: float = TARGET_MPP) -> dict:
    """Z GT labelů (map_gt: 0-4/255) [+ rgb skenu] → {ISOM kód: [polygony]} pro třídy AREA_CLASSES.

    Jádro GT-feederu: vstup = runnability segmentace mapy (map_gt.segment_gt), výstup = vektorové
    PLOCHY predikčních ISOM symbolů per ISOM kód (zelené 406/408/410 + 403 rough open), v image-px
    VSTUPNÍHO gridu. Konzument: write_omap / overlay / (Sez. 83) generate_map per-classId orchestrátor.

    `rgb` (Sez. 92): reálný sken (map.png) ve STEJNÉM rozměru jako label_map. Potřeba jen pro třídy
    s `pale_yellow` (403): map_gt 401 i 403 řadí do open (label 4), odstínem je rozliší až _is_pale_yellow
    nad rgb. Bez rgb se pale_yellow třídy přeskočí (PoC/izolovaný režim = jen zeleň, behavior-preserving).

    `src_mpp` (Sez. 85): rozlišení vstupního gridu [m/px]. Je-li dané a jemnější než `target_mpp`,
    se per-kód masky PŘED vektorizací downscalují NEAREST faktorem f=target_mpp/src_mpp; polygony se
    pak vynásobí f ZPĚT na původní grid, takže výstupní souřadnice zůstávají v image-px vstupu
    (volající _map_affine/write_omap se nemění). Bez `src_mpp` = no-op. Důvod + měření: viz TARGET_MPP.

    Nejdřív „prohlédne" fialový přetisk tratě (_fill_ignore) — jinak kroužky/spojnice kontrol
    vykousnou díry do zelených ploch (nález Sez. 83)."""
    label_map = _fill_ignore(label_map)
    # per-ISOM-kód bool maska ve vstupním rozlišení (403 = open ∩ bledá žlutá; zeleň = přímo gt label)
    masks: dict[str, np.ndarray] = {}
    for code, spec in AREA_CLASSES.items():
        m = label_map == spec["gt"]
        if spec.get("pale_yellow"):
            if rgb is None:                   # bez skenu 403 nelze určit → přeskoč (PoC)
                continue
            m = m & _is_pale_yellow(rgb)
        masks[code] = m
    f = 1.0
    if src_mpp and target_mpp and target_mpp > src_mpp:
        f = target_mpp / src_mpp
        masks = {c: _downscale_mask(m, f) for c, m in masks.items()}
    polys = {c: vectorize_level(m) for c, m in masks.items()}
    if f != 1.0:                          # prstence (col,row) zpět na PŮVODNÍ grid → výstup v image-px vstupu
        polys = {c: [[np.asarray(r, float) * f for r in poly] for poly in ps]
                 for c, ps in polys.items()}
    return polys


def _render_overlay(rgb: np.ndarray, level_polys: dict, out_path: pathlib.Path) -> None:
    """Verify: ztlumená původní mapa + vektorové plochy přes ni (vizuální důkaz věrnosti)."""
    base = (rgb.astype(np.float32) * 0.35 + 255 * 0.65).astype(np.uint8)
    ov = Image.fromarray(base).convert("RGB")
    d = ImageDraw.Draw(ov, "RGBA")
    for code, spec in AREA_CLASSES.items():
        col = spec["vis"]
        for poly in level_polys[code]:
            outer = [(float(x), float(y)) for x, y in poly[0]]
            if len(outer) >= 3:
                d.polygon(outer, fill=(*col, 170), outline=(0, 0, 0, 120))
            for hole in poly[1:]:                 # díry zpět na podklad
                hp = [(float(x), float(y)) for x, y in hole]
                if len(hp) >= 3:
                    d.polygon(hp, fill=(255, 255, 255, 0))
    ov.save(out_path)


def main(cid: str) -> None:
    """PoC běh na jedné mapě korpusu: separace → overlay (verify) + .omap (OOM verify).

    Izolovaný test SAMOTNÉ separace (bez real ČÚZK vrstev) — integrovaný pár vyrobí per-classId
    orchestrátor (Sez. 83). Zachováno pro ladění separace na jedné mapě."""
    map_dir = _CORPUS_DIR / cid
    meta = json.loads((map_dir / "meta.json").read_text(encoding="utf-8"))
    rgb = np.asarray(Image.open(map_dir / "map.png").convert("RGB"))
    gt = np.asarray(Image.open(map_dir / "gt_labels.png"))   # 0-4/255 (map_gt separace)
    H, W = gt.shape
    print(f"{cid} {W}x{H}  scale 1:{int(meta['mapScale'])}  mpp {meta['effectiveMppX']:.2f}")

    level_polys = separate_areas(gt, rgb=rgb)
    for code, spec in AREA_CLASSES.items():
        # px count v plné gt: zeleň = label, 403 = open ∩ bledá žlutá (potřebuje rgb)
        m = gt == spec["gt"]
        if spec.get("pale_yellow"):
            m = m & _is_pale_yellow(rgb)
        px = int(m.sum())
        print(f"  {code} (gt label {spec['gt']}{', pale' if spec.get('pale_yellow') else ''}): "
              f"{px:>8} px = {100*px/gt.size:4.1f}%  → {len(level_polys[code]):4d} polygonů")

    _render_overlay(rgb, level_polys, map_dir / "separate_overlay.png")
    print(f"overlay → {map_dir/'separate_overlay.png'}")

    # .omap: plochy jako veg_area_features (image-px = grid), map.png podklad pro OOM verify
    feats = [([[(float(x), float(y)) for x, y in r] for r in poly], code)
             for code in AREA_CLASSES for poly in level_polys[code]]
    counts = write_omap(
        contour_features=[], path_features=[], point_symbols=[], water_features=[],
        building_features=[], powerline_features=[],
        gw=W, gh=H, world_w_m=meta["effectiveMppX"] * W, world_h_m=meta["effectiveMppY"] * H,
        scale=float(meta["mapScale"]), out_path=map_dir / "separate_areas.omap",
        ortho_template={"name": "map.png", "img_w": W, "img_h": H, "opacity": 1.0},
        veg_area_features=feats,
    )
    print(f".omap  → {map_dir/'separate_areas.omap'}  (objektů {counts['objects']}, "
          f"plochy {counts['veg_area']}, podklad map.png)")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows cp1250 vs Unicode (Sez. 74)
    except Exception:
        pass
    main(sys.argv[1] if len(sys.argv) > 1 else "1088447")
