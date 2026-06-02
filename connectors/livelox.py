"""
livelox.py — stažení reálné OB mapy z Livelox jako rastr + georef pro UC5 korpus.

Účel (UC5 runnability korpus, Sez. 67/68): UC5 model predikce zelené/žluté běhatelnosti
je supervised → potřebuje ground-truth = co kartograf nakreslil na reálné mapě. Livelox
je nejdostupnější zdroj reálných OB map ČR (deep research Sez. 67). Tento konektor stáhne
mapu jako georeferencovaný rastr; segmentace zelená/žlutá na GT masku je samostatný krok.

Sourozenec dmr.py / zabaged.py / ortofoto.py, ale JINÝ zdroj (ne ČÚZK):
  - endpoint `https://www.livelox.com/Data/ClassInfo` (POST classId → URL na blob)
  - request tvar ověřen ze zdroje (yoav28/livelox-map-downloader-extension, MIT) + probe Sez. 68

Klíčová zjištění z probe (Sez. 68, 4 mapy):
  - Stažitelné maximum = `map.images[0]` (největší ne-thumbnail) = ~1,33 m/px. `map.tiles`
    jsou jen rozřezaný tentýž obraz, NE vyšší rozlišení. Nativní 0,75 m/px je server-side
    nedostupné. Pro PLOŠNOU runnability GT (zelená/žlutá) 1,33 m/px stačí.
  - CRS mapy se LIŠÍ mezi mapami (viděno S-JTSK 5514 i UTM33 32633) a NEZÁVISÍ na poloze
    (Slezsko 18,8°E bylo v S-JTSK, ne UTM34) → epsg MUSÍ číst z dat (`projectionEpsgCode`),
    nikdy hardcode.
  - Georef = `projectedBoundingQuadrilateral` (4 rohy v epsg mapy) sedne na ortofoto BEZ
    feature-fitu (gate 2 prošel na 4 mapách) → žádný fitter/ORIS lookup není potřeba.

Licence / právní režim: mapy nestahovat ke sdílení — práva drží kartograf/pořadatel/federace.
Privátní nekomerční experiment (TDM výjimka, AutZ ČR / EU DSM 2019/790); legalizace (ČSOS) až
pokud model funguje. Korpus žije v `resources/livelox/` (gitignored).

Spouštět z kořene repa (sys.path skript, fáze B — ne balík).
"""

import io
import json
import urllib.request
from pathlib import Path

# kořen repa (connectors/ je přímo v kořeni) → resources/livelox/ kotvíme sem
_REPO_ROOT = Path(__file__).resolve().parents[1]
_CORPUS_DIR = _REPO_ROOT / "resources" / "livelox"

# endpoint pro metadata třídy (závodní kategorie); vrací URL na Azure blob s mapou
_CLASS_INFO_URL = "https://www.livelox.com/Data/ClassInfo"

_UA = "AzimutLab-generator/0.1"


def _post_class_info(class_id: int) -> dict:
    """POST /Data/ClassInfo — vrátí JSON; general.classBlobUrl ukazuje na blob s mapou.

    Body tvar přesně dle zdrojového extension (fetchClassBlobUrl): jen classIds je
    podstatné, ostatní pole prázdná. Hlavička X-Requested-With je nutná (jinak 400).
    """
    body = json.dumps({
        "eventId": None,
        "courseIds": [],
        "relayLegs": [],
        "relayLegGroupIds": [],
        "classIds": [int(class_id)],
    }).encode("utf-8")
    req = urllib.request.Request(_CLASS_INFO_URL, data=body, method="POST", headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": _UA,
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str) -> dict:
    """GET libovolného JSON (Azure blob s mapou)."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_bytes(url: str) -> bytes:
    """GET surových bajtů (PNG mapy)."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def fetch_class_blob(class_id: int) -> dict:
    """Vrátí celý blob JSON třídy (obsahuje 'map' s images + georef quad).

    Dvoukrokově: ClassInfo → classBlobUrl → GET blob. Oddělené od stahování mapy,
    ať lze metadata zkoumat bez stažení rastru (mapScale, epsg, rozměry).
    """
    info = _post_class_info(class_id)
    blob_url = info.get("general", {}).get("classBlobUrl")
    if not blob_url:
        raise RuntimeError(f"Livelox ClassInfo nevrátil classBlobUrl pro classId={class_id}")
    return _get_json(blob_url)


def _largest_full_image(blob_map: dict) -> dict:
    """Vybere největší NE-thumbnail image (= stažitelné maximum, ~1,33 m/px)."""
    images = blob_map["images"]
    full = [im for im in images if not im.get("isThumbnail")]
    if not full:
        raise RuntimeError("Livelox blob nemá žádný ne-thumbnail image")
    return max(full, key=lambda x: x["width"] * x["height"])


def _build_meta(class_id: int, blob: dict, image: dict) -> dict:
    """Sestaví meta.json — georef + provenance + spočtené rozlišení.

    Quad ukládáme v OBOU podobách: WGS84 (boundingQuadrilateral) i projikovaný v CRS
    mapy (projectedBoundingQuadrilateral). epsg bereme z dat (projectionEpsgCode) —
    klíčové, mezi mapami se liší (S-JTSK i UTM33/34).
    """
    m = blob["map"]
    # m/px podél obou stran rovnoběžníku (mapa bývá rotovaná = grivace)
    pq = m["projectedBoundingQuadrilateral"]["vertices"]
    p = [(v["x"], v["y"]) for v in pq]
    side_a = ((p[1][0] - p[0][0]) ** 2 + (p[1][1] - p[0][1]) ** 2) ** 0.5
    side_b = ((p[3][0] - p[0][0]) ** 2 + (p[3][1] - p[0][1]) ** 2) ** 0.5
    return {
        "classId": class_id,
        "name": m.get("name"),
        "mapScale": m.get("mapScale"),
        "creationSoftware": m.get("creationSoftware"),
        "epsg": m.get("projectionEpsgCode"),          # CRS mapy — ČÍST Z DAT
        "imageWidth": image["width"],
        "imageHeight": image["height"],
        "declaredResolutionMpp": m.get("resolution"),  # server-side nativní (nedostupné)
        "effectiveMppX": side_a / image["width"],       # skutečné stažené rozlišení
        "effectiveMppY": side_b / image["height"],
        "boundingQuadrilateralWgs84": m["boundingQuadrilateral"]["vertices"],
        "projectedBoundingQuadrilateral": m["projectedBoundingQuadrilateral"]["vertices"],
        # provenance — odkud data jsou (pro pozdější legalizaci / atribuci)
        "source": "livelox",
        "imageUrl": image["url"],
        "license": "rights held by mapper/organiser; private non-commercial use (TDM)",
    }


def build_georef_blend(meta: dict, map_png: str | Path, out_dir: str | Path,
                       mpp_target: float = 1.33) -> Path:
    """Vykreslí blend.png = mapa warpnutá do S-JTSK přes ortofoto ČÚZK téhož výseku.

    Vizuální důkaz, že georef sedí (gate 2 Sez. 68). Reprojikuje quad z CRS mapy do
    S-JTSK 5514, afinně warpne mapu do axis-aligned S-JTSK gridu a smíchá s ortofotem.
    Lazy importy (numpy/pyproj/ortofoto), ať základní stahování na nich nezávisí.
    """
    import numpy as np
    from PIL import Image
    from pyproj import Transformer
    # ortofoto je sourozenec v connectors/ — přidej na sys.path, pokud chybí
    import sys
    if str(Path(__file__).parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).parent))
    from ortofoto import _export_tile

    Image.MAX_IMAGE_PIXELS = None
    out_dir = Path(out_dir)

    # quad z meta (v CRS mapy) → S-JTSK
    epsg = meta["epsg"]
    pq = meta["projectedBoundingQuadrilateral"]
    to_sjtsk = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:5514", always_xy=True)
    quad = [to_sjtsk.transform(v["x"], v["y"]) for v in pq]   # 4 rohy S-JTSK

    xs = [q[0] for q in quad]; ys = [q[1] for q in quad]
    mgn = 50.0
    xmin, xmax = min(xs) - mgn, max(xs) + mgn
    ymin, ymax = min(ys) - mgn, max(ys) + mgn
    # rozlišení gridu: cíl ~1,33 m/px, ale vejít se do stropu ortofoto exportu (4096 px/strana)
    span = max(xmax - xmin, ymax - ymin)
    mpp = max(mpp_target, span / 4000.0)
    out_w = int((xmax - xmin) / mpp); out_h = int((ymax - ymin) / mpp)

    ortho = _export_tile(xmin, ymin, xmax, ymax, out_w, out_h)   # (h,w,3) uint8

    # warp mapy: páruj image rohy (NW,NE,SE,SW) s quad vertices [3,2,1,0] (Livelox konvence
    # boundingQuadrilateral = SW,SE,NE,NW; ověřeno probe Sez. 68 na 4 mapách)
    img = np.asarray(Image.open(map_png).convert("RGB"), dtype=np.uint8)
    H, W = img.shape[:2]
    src = np.array([[0, 0], [W, 0], [W, H], [0, H]], float)
    dst = np.array([quad[3], quad[2], quad[1], quad[0]], float)
    A = _fit_affine(src, dst)
    warped = _warp_to_grid(img, A, xmin, ymax, mpp, out_w, out_h)

    blend = (0.5 * ortho.astype(np.float32) + 0.5 * warped.astype(np.float32)).astype(np.uint8)
    blend_path = out_dir / "blend.png"
    Image.fromarray(blend).save(blend_path)
    return blend_path


def _fit_affine(src, dst):
    """Least-squares afinní transformace src(px)->dst(S-JTSK). Vrací 2x3 matici."""
    import numpy as np
    M = np.hstack([src, np.ones((src.shape[0], 1))])
    cx, *_ = np.linalg.lstsq(M, dst[:, 0], rcond=None)
    cy, *_ = np.linalg.lstsq(M, dst[:, 1], rcond=None)
    return np.vstack([cx, cy])


def _warp_to_grid(img, A, x0, y_top, mpp, out_w, out_h):
    """Inverzní vzorkování: pro každý S-JTSK px výstupního gridu najdi zdrojový px mapy."""
    import numpy as np
    sh, sw = img.shape[:2]
    gx = x0 + (np.arange(out_w) + 0.5) * mpp
    gy = y_top - (np.arange(out_h) + 0.5) * mpp     # row0 = sever nahoře
    GX, GY = np.meshgrid(gx, gy)
    Ainv = np.linalg.inv(np.vstack([A, [0, 0, 1]]))
    sx = Ainv[0, 0] * GX + Ainv[0, 1] * GY + Ainv[0, 2]
    sy = Ainv[1, 0] * GX + Ainv[1, 1] * GY + Ainv[1, 2]
    sxi = np.round(sx).astype(int); syi = np.round(sy).astype(int)
    valid = (sxi >= 0) & (sxi < sw) & (syi >= 0) & (syi < sh)
    out = np.full((out_h, out_w, 3), 255, np.uint8)
    out[valid] = img[syi[valid], sxi[valid]]
    return out


def download_map(class_id: int, out_dir: str | Path | None = None,
                 overwrite: bool = False, make_blend: bool = True) -> Path:
    """Stáhne mapu třídy do resources/livelox/<classId>/ (map.png + meta.json).

    Vrací cestu k adresáři mapy. Při overwrite=False a existující map.png se stažení
    přeskočí (idempotentní — korpus se nebuduje znovu při opakovaném běhu).
    make_blend=True navíc vykreslí blend.png (warp přes ortofoto = georef důkaz); pro
    velký batch lze vypnout (200× ortofoto fetch je drahé).
    """
    out_dir = Path(out_dir) if out_dir else _CORPUS_DIR / str(class_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    map_png = out_dir / "map.png"
    meta_json = out_dir / "meta.json"

    if map_png.exists() and meta_json.exists() and not overwrite:
        return out_dir

    blob = fetch_class_blob(class_id)
    image = _largest_full_image(blob["map"])

    # stáhni a ulož rastr (validuj, že je to obrázek — server jinak vrací JSON chybu)
    raw = _get_bytes(image["url"])
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img.load()
    except Exception as e:
        raise RuntimeError(f"Livelox nevrátil platný PNG pro classId={class_id}: {e}") from e
    img.save(map_png)

    meta = _build_meta(class_id, blob, image)
    meta_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if make_blend:
        build_georef_blend(meta, map_png, out_dir)
    return out_dir


if __name__ == "__main__":
    # ruční test: python connectors/livelox.py <classId>
    import sys
    cid = int(sys.argv[1]) if len(sys.argv) > 1 else 1116300
    d = download_map(cid, overwrite=True)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    print(f"stazeno -> {d}")
    print(f"  name={meta['name']!r} scale=1:{int(meta['mapScale'])} epsg={meta['epsg']}")
    print(f"  {meta['imageWidth']}x{meta['imageHeight']} "
          f"@ {meta['effectiveMppX']:.2f}x{meta['effectiveMppY']:.2f} m/px")
