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
import math
import time
import urllib.error
import urllib.request
from pathlib import Path

# kořen repa (connectors/ je přímo v kořeni) → resources/livelox/ kotvíme sem
_REPO_ROOT = Path(__file__).resolve().parents[1]
_CORPUS_DIR = _REPO_ROOT / "resources" / "livelox"

# endpoint pro metadata třídy (závodní kategorie); vrací URL na Azure blob s mapou
_CLASS_INFO_URL = "https://www.livelox.com/Data/ClassInfo"
# endpoint pro vyhledání eventů (Knockout SPA volá POST JSON; reverzováno Sez. 70 z home.js)
_SEARCH_EVENTS_URL = "https://www.livelox.com/Home/SearchEvents"

# UA: server odpovídá i na náš identifikátor, ale na /Home/SearchEvents je spolehlivější
# vypadat jako prohlížeč (jinak občas transient drop) — proto Mozilla prefix.
_UA = "Mozilla/5.0 AzimutLab-generator/0.1"

# severní Čechy = GeoBox (jih/sever/západ/východ ve WGS84 stupních). Pokrývá Liberecko →
# zahrnuje oblasti našich resources map (Slovanka, Bedřichov, …). Volba uživatele Sez. 70:
# severní Čechy + historie téhož prostoru (cenná pro UC5 — opakované mapování = časová řada).
NORTH_BOHEMIA_BOX = {"south": 50.4, "north": 50.95, "west": 14.3, "east": 15.5}

# saské/lužické příhraničí (Žitavsko–Šluknovsko) — německá strana u Liberecka. Volba uživatele
# Sez. 70: německé OB podniky v příhraničí (vč. série SAXBO). country="Germany" v list/batch.
LUSATIA_BORDER_BOX = {"south": 50.7, "north": 51.05, "west": 14.4, "east": 15.05}


# trvalé HTTP chyby = nemá smysl opakovat (blob smazán/zakázán/pryč) → fail hned.
# Vše ostatní (timeout, conn reset, 5xx) = transient → backoff retry.
_PERMANENT_HTTP = {403, 404, 410}


def _ensure_connectors_on_path() -> None:
    """Přidá connectors/ na sys.path, ať jdou lazy-importovat sourozenci (ortofoto/map_gt).

    Lazy import drží těžké/volitelné závislosti (numpy/scipy/ortofoto) mimo čisté stahování;
    helper jen sjednocuje opakovaný sys.path boilerplate (DRY)."""
    import sys
    d = str(Path(__file__).parent)
    if d not in sys.path:
        sys.path.insert(0, d)


def _open_with_retry(req: urllib.request.Request, timeout: float, tries: int = 4) -> bytes:
    """urlopen + .read() s exponenciálním backoffem na transient chyby. Vrací bajty.

    Backoff 2→4→8 s je sebeškrtící: při zahlcení/výpadku serveru se sám zpomalí (prevence
    banu, nález Sez. 70 — `WinError 10060` byly transient, ne náš rate-limit). Trvalé HTTP
    kódy (404 blob smazán) NEopakuje — plýtvání a správně failnou hned.
    """
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code in _PERMANENT_HTTP or attempt == tries - 1:
                raise
        except Exception:   # URLError, socket timeout, conn reset = transient
            if attempt == tries - 1:
                raise
        time.sleep(2 ** (attempt + 1))   # 2, 4, 8 s


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
    return json.loads(_open_with_retry(req, timeout=60).decode("utf-8"))


def _get_json(url: str) -> dict:
    """GET libovolného JSON (Azure blob s mapou)."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    return json.loads(_open_with_retry(req, timeout=60).decode("utf-8"))


def _get_bytes(url: str) -> bytes:
    """GET surových bajtů (PNG mapy)."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    return _open_with_retry(req, timeout=120)


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


def _resolve_georef(m: dict, image: dict) -> tuple:
    """Vrátí (epsg, proj_quad_vertices [{x,y}], mpp_x, mpp_y, is_fallback).

    Preferuje projikovaný quad v metrickém CRS mapy (projectionEpsgCode). Když chybí
    (typ B, Sez. 70 — projectionEpsgCode None), fallback na WGS84 boundingQuadrilateral:
    CRS = 4326, quad jako {x:lon, y:lat} (konvence always_xy), mpp přes metrickou
    aproximaci stupňů (1° lat ≈ 111320 m, 1° lon ≈ ·cos(lat)). Georef tak sedí i bez
    projikované varianty (build_georef_blend transformuje 4326→S-JTSK stejně).
    """
    def _side(p, i, j):
        return ((p[i][0] - p[j][0]) ** 2 + (p[i][1] - p[j][1]) ** 2) ** 0.5

    proj = m.get("projectedBoundingQuadrilateral")
    if proj:
        pq = proj["vertices"]
        p = [(v["x"], v["y"]) for v in pq]   # už v metrech (CRS mapy)
        return (m.get("projectionEpsgCode"), pq,
                _side(p, 1, 0) / image["width"], _side(p, 3, 0) / image["height"], False)

    # WGS84 fallback — jen boundingQuadrilateral existuje
    wq = m["boundingQuadrilateral"]["vertices"]
    pq = [{"x": v["longitude"], "y": v["latitude"]} for v in wq]
    p = [(d["x"], d["y"]) for d in pq]       # (lon, lat) ve stupních
    lat0 = sum(v["latitude"] for v in wq) / len(wq)
    m_lat, m_lon = 111320.0, 111320.0 * math.cos(math.radians(lat0))
    # převeď strany ze stupňů na metry před dělením šířkou (mpp v metrech, konzistentní)
    pm = [(x * m_lon, y * m_lat) for x, y in p]
    return (4326, pq,
            _side(pm, 1, 0) / image["width"], _side(pm, 3, 0) / image["height"], True)


def _build_meta(class_id: int, blob: dict, image: dict) -> dict:
    """Sestaví meta.json — georef + provenance + spočtené rozlišení.

    Quad ukládáme v OBOU podobách: WGS84 (boundingQuadrilateral) i projikovaný v CRS
    mapy. epsg z dat — mezi mapami se liší (S-JTSK i UTM33/34). Když projikovaná varianta
    chybí (typ B), použije se WGS84 fallback (epsg=4326) — viz _resolve_georef.
    """
    m = blob["map"]
    epsg, proj_quad, mpp_x, mpp_y, fallback = _resolve_georef(m, image)
    return {
        "classId": class_id,
        "name": m.get("name"),
        "mapScale": m.get("mapScale"),
        "creationSoftware": m.get("creationSoftware"),
        "epsg": epsg,                                  # CRS mapy — ČÍST Z DAT
        "georefFallbackWgs84": fallback,               # True = typ B (jen WGS84 quad)
        "imageWidth": image["width"],
        "imageHeight": image["height"],
        "declaredResolutionMpp": m.get("resolution"),  # server-side nativní (nedostupné)
        "effectiveMppX": mpp_x,                         # skutečné stažené rozlišení
        "effectiveMppY": mpp_y,
        "boundingQuadrilateralWgs84": m["boundingQuadrilateral"]["vertices"],
        "projectedBoundingQuadrilateral": proj_quad,
        # provenance — odkud data jsou (pro pozdější legalizaci / atribuci)
        "source": "livelox",
        "imageUrl": image["url"],
        "license": "rights held by mapper/organiser; private non-commercial use (TDM)",
    }


def _georef_grid(meta: dict, mpp_target: float = 1.33) -> dict:
    """Geometrie axis-aligned S-JTSK gridu pro daný výsek (sdílí blend i pár, DRY).

    Reprojikuje 4-rohý quad z CRS mapy (`meta["epsg"]`) do S-JTSK 5514, spočte obalový
    obdélník (+50 m okraj) a rozlišení gridu. mpp je cíl ~1,33 m/px, ale zvedne se, aby
    se delší strana vešla do stropu ortofoto exportu (≤4000 px). Vrací vše, co warp i
    export potřebují — bez čtení rastru (ten je per-soubor).
    """
    from pyproj import Transformer

    epsg = meta["epsg"]
    pq = meta["projectedBoundingQuadrilateral"]
    to_sjtsk = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:5514", always_xy=True)
    quad = [to_sjtsk.transform(v["x"], v["y"]) for v in pq]   # 4 rohy S-JTSK

    xs = [q[0] for q in quad]; ys = [q[1] for q in quad]
    mgn = 50.0
    xmin, xmax = min(xs) - mgn, max(xs) + mgn
    ymin, ymax = min(ys) - mgn, max(ys) + mgn
    span = max(xmax - xmin, ymax - ymin)
    mpp = max(mpp_target, span / 4000.0)
    out_w = int((xmax - xmin) / mpp); out_h = int((ymax - ymin) / mpp)
    return {"quad": quad, "xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax,
            "mpp": mpp, "out_w": out_w, "out_h": out_h}


def _map_affine(quad: list, W: int, H: int):
    """Afinní matice image-px (rastr mapy W×H) → S-JTSK, z 4 rohů quadu.

    Páruje rohy obrázku (NW,NE,SE,SW) s quad vertices [3,2,1,0] (Livelox konvence
    boundingQuadrilateral = SW,SE,NE,NW; ověřeno probe Sez. 68 na 4 mapách).
    GT i RGB mapa mají TYTÉŽ rozměry (gt_labels vzniká z map.png) → stejná matice.
    """
    import numpy as np
    src = np.array([[0, 0], [W, 0], [W, H], [0, H]], float)
    dst = np.array([quad[3], quad[2], quad[1], quad[0]], float)
    return _fit_affine(src, dst)


def build_georef_blend(meta: dict, map_png: str | Path, out_dir: str | Path,
                       mpp_target: float = 1.33) -> Path:
    """Vykreslí blend.png = mapa warpnutá do S-JTSK přes ortofoto ČÚZK téhož výseku.

    Vizuální důkaz, že georef sedí (gate 2 Sez. 68). Reprojikuje quad z CRS mapy do
    S-JTSK 5514, afinně warpne mapu do axis-aligned S-JTSK gridu a smíchá s ortofotem.
    Lazy importy (numpy/pyproj/ortofoto), ať základní stahování na nich nezávisí.
    """
    import numpy as np
    from PIL import Image
    _ensure_connectors_on_path()        # ortofoto je sourozenec v connectors/
    from ortofoto import _export_tile

    Image.MAX_IMAGE_PIXELS = None
    out_dir = Path(out_dir)

    g = _georef_grid(meta, mpp_target)
    ortho = _export_tile(g["xmin"], g["ymin"], g["xmax"], g["ymax"],
                         g["out_w"], g["out_h"])           # (h,w,3) uint8
    img = np.asarray(Image.open(map_png).convert("RGB"), dtype=np.uint8)
    H, W = img.shape[:2]
    A = _map_affine(g["quad"], W, H)
    warped = _warp_to_grid(img, A, g["xmin"], g["ymax"], g["mpp"], g["out_w"], g["out_h"])

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


def _warp_to_grid(img, A, x0, y_top, mpp, out_w, out_h, fill: int = 255):
    """Inverzní vzorkování: pro každý S-JTSK px výstupního gridu najdi zdrojový px mapy.

    Funguje pro RGB (H,W,3) i jednokanálovou masku/labely (H,W). `fill` = hodnota mimo
    mapu (pro RGB 255 = bílá; pro GT labely 255 = IGNORE — shodná hodnota, jiný význam).
    Vzorkování je nearest (`np.round`) → bezpečné i pro labely (žádná interpolace tříd).
    """
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
    # tvar výstupu dle počtu kanálů zdroje (2D labely vs 3D RGB)
    out_shape = (out_h, out_w) if img.ndim == 2 else (out_h, out_w, img.shape[2])
    out = np.full(out_shape, fill, img.dtype)
    out[valid] = img[syi[valid], sxi[valid]]
    return out


def measure_georef_offset(ortho, warped, mpp: float, max_shift_m: float = 40.0) -> dict:
    """Změří reziduální posun mapy vůči ortofotu (GATE 1) phase correlation hran.

    Vstup: ortho (h,w,3) = ČÚZK pravda, warped (h,w,3) = mapa warpnutá do téhož gridu.
    Společný signál obou = HRANY (cesty, kraj lesa, vodní toky) — barvy se liší, hrany
    sedí. Phase correlation (FFT) najde globální translaci, kterou je třeba mapu posunout,
    aby hrany sedly na ortofoto. Výsledek v px × mpp = metry.

    Hledá peak JEN v okně ±max_shift_m (default 40 m). Reziduální georef offset je z
    principu malý (jednotky px); velký peak = artefakt periodicity (pravidelné šrafy
    žlutých ploch, mřížka polí) — nález Sez. 75: bez omezení dala mapa 1047807 falešných
    549 m, ač vizuálně sedí dokonale. Velký reálný posun stejně líp pozná vizuál (blend).

    Vrací {dx_m, dy_m, mag_m, dx_px, dy_px}. mag_m je velikost posunu; >~3-5 m systematicky
    napříč mapami = georef kartografa je šum a model by se učil nezarovnaný pár.
    Pozn.: měří jen GLOBÁLNÍ translaci (ne rotaci/lokální deformaci).
    """
    import numpy as np

    def _edges(rgb):
        # grayscale → gradientní magnituda (np.gradient = centrální diference, bez scipy).
        # Hrany jsou společný signál ortofota i mapy; samotná barva/jas se mezi nimi liší.
        g = rgb.astype(np.float32).mean(axis=2)
        gy, gx = np.gradient(g)
        return np.hypot(gx, gy)

    e1 = _edges(ortho)      # ortofoto
    e2 = _edges(warped)     # mapa

    # mapa má mimo svůj quad bílý fill (žádné hrany) — to phase correlation neruší.
    # 2D Hann okno potlačí umělé hrany na okraji obrazu (FFT předpokládá periodicitu).
    h, w = e1.shape
    win = np.outer(np.hanning(h), np.hanning(w))
    e1 = e1 * win; e2 = e2 * win

    # phase correlation: cross-power spektrum normované na jednotkovou magnitudu → ostrý peak
    F1 = np.fft.fft2(e1); F2 = np.fft.fft2(e2)
    R = F1 * np.conj(F2)
    R /= np.abs(R) + 1e-12
    r = np.fft.ifft2(R).real

    # fftfreq*N = znaménkové posuny [0,1,..,-2,-1] pro každý index → rovnou v px i pro masku
    sy = (np.fft.fftfreq(h) * h).astype(int)
    sx = (np.fft.fftfreq(w) * w).astype(int)
    SY, SX = np.meshgrid(sy, sx, indexing="ij")
    R_px = max(1, int(round(max_shift_m / mpp)))
    within = (np.abs(SY) <= R_px) & (np.abs(SX) <= R_px)   # jen malé posuny
    r = np.where(within, r, -np.inf)

    iy, ix = np.unravel_index(int(np.argmax(r)), r.shape)
    dy, dx = int(sy[iy]), int(sx[ix])

    dx_m = dx * mpp; dy_m = dy * mpp
    return {"dx_m": round(dx_m, 2), "dy_m": round(dy_m, 2),
            "mag_m": round((dx_m ** 2 + dy_m ** 2) ** 0.5, 2),
            "dx_px": int(dx), "dy_px": int(dy)}


def build_georef_pair(out_dir: str | Path, mpp_target: float = 1.33,
                      measure: bool = True) -> dict:
    """GATE 1 — z adresáře mapy vyrobí zarovnaný pár (X,Y) pro UC5 trénink.

    Vstup (musí existovat v out_dir): map.png + gt_labels.png + meta.json.
    Výstup do out_dir:
      - ortho.png       = X (ČÚZK ortofoto v S-JTSK gridu)
      - gt_grid.png     = Y (GT labely warpnuté do TÉHOŽ gridu, nearest, fill IGNORE)
      - gt_grid_vis.png = barevná vizualizace Y (verify okem)
      - blend.png       = ortofoto+mapa (vizuální důkaz georefu)
    X i Y procházejí identickou transformací do stejného gridu → pixel-na-pixel zarovnané.

    measure=True navíc změří georef offset (phase correlation) a vrátí ho v dict.
    Vrací {paths..., offset: {...}} (offset None, když measure=False).
    """
    import numpy as np
    from PIL import Image
    _ensure_connectors_on_path()
    from ortofoto import _export_tile
    from map_gt import IGNORE, _LABEL_VIS

    Image.MAX_IMAGE_PIXELS = None
    out_dir = Path(out_dir)
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))

    g = _georef_grid(meta, mpp_target)
    ortho = _export_tile(g["xmin"], g["ymin"], g["xmax"], g["ymax"],
                         g["out_w"], g["out_h"])              # X (h,w,3) uint8

    rgb = np.asarray(Image.open(out_dir / "map.png").convert("RGB"), dtype=np.uint8)
    gt = np.asarray(Image.open(out_dir / "gt_labels.png"), dtype=np.uint8)
    if gt.shape != rgb.shape[:2]:
        raise RuntimeError(f"gt_labels {gt.shape} != map.png {rgb.shape[:2]} v {out_dir}")

    H, W = rgb.shape[:2]
    A = _map_affine(g["quad"], W, H)
    warped_rgb = _warp_to_grid(rgb, A, g["xmin"], g["ymax"], g["mpp"],
                               g["out_w"], g["out_h"])         # pro blend + měření
    warped_gt = _warp_to_grid(gt, A, g["xmin"], g["ymax"], g["mpp"],
                              g["out_w"], g["out_h"], fill=IGNORE)   # Y, mimo mapu = ignore

    # ulož pár + verify artefakty
    Image.fromarray(ortho).save(out_dir / "ortho.png")
    Image.fromarray(warped_gt, mode="L").save(out_dir / "gt_grid.png")
    vis = np.zeros((*warped_gt.shape, 3), np.uint8)
    for lab, col in _LABEL_VIS.items():
        vis[warped_gt == lab] = col
    Image.fromarray(vis).save(out_dir / "gt_grid_vis.png")
    blend = (0.5 * ortho.astype(np.float32) +
             0.5 * warped_rgb.astype(np.float32)).astype(np.uint8)
    Image.fromarray(blend).save(out_dir / "blend.png")

    offset = measure_georef_offset(ortho, warped_rgb, g["mpp"]) if measure else None
    return {"ortho": out_dir / "ortho.png", "gt_grid": out_dir / "gt_grid.png",
            "gt_grid_vis": out_dir / "gt_grid_vis.png", "blend": out_dir / "blend.png",
            "mpp": round(g["mpp"], 3), "out_w": g["out_w"], "out_h": g["out_h"],
            "offset": offset}


def build_pairs(out_dirs, mpp_target: float = 1.33,
                skip_existing: bool = True, measure: bool = True) -> dict:
    """Hromadně vyrobí zarovnané páry (X,Y) pro seznam adresářů map (UC5 trénink, Sez. 76).

    Volá build_georef_pair na každý adresář. Vlastnosti dávky:
      - resumovatelné: skip_existing přeskočí mapy s hotovým ortho.png+gt_grid.png
        (re-běh po přerušení nestahuje znovu — ortofoto fetch je drahý),
      - tolerantní: chyba jedné mapy (síť/georef) dávku NEzastaví, jen se zaznamená,
      - QC: measure agreguje georef offset (phase correlation) přes celý set = GATE 1
        na 207 mapách (Sez. 75 měřil jen 25) → medián má zůstat ~1 px.

    Vrací souhrn {ok:[cid], skipped:[cid], failed:[(cid,err)], mags:[mag_m,...]}.
    """
    import logging
    log = logging.getLogger("livelox.pairs")
    summary = {"ok": [], "skipped": [], "failed": [], "mags": []}
    total = len(out_dirs)
    for i, d in enumerate(out_dirs, 1):
        d = Path(d)
        if skip_existing and (d / "ortho.png").exists() and (d / "gt_grid.png").exists():
            summary["skipped"].append(d.name)
            continue
        try:
            res = build_georef_pair(d, mpp_target, measure=measure)
            summary["ok"].append(d.name)
            if res["offset"]:
                summary["mags"].append(res["offset"]["mag_m"])
            log.info("[%d/%d] %s OK %dx%d @ %.2f m/px", i, total, d.name,
                     res["out_w"], res["out_h"], res["mpp"])
        except Exception as e:
            summary["failed"].append((d.name, f"{type(e).__name__}: {e}"))
            log.warning("[%d/%d] %s FAIL: %s", i, total, d.name, e)
    return summary


def download_map(class_id: int, out_dir: str | Path | None = None,
                 overwrite: bool = False, make_blend: bool = True) -> Path:
    """Stáhne mapu třídy do resources/livelox/<classId>/ (map.png + meta.json).

    Vrací cestu k adresáři mapy. Při overwrite=False a existující map.png se stažení
    přeskočí (idempotentní — korpus se nebuduje znovu při opakovaném běhu).
    make_blend=True navíc vykreslí blend.png (warp přes ortofoto = georef důkaz); pro
    velký batch lze vypnout (200× ortofoto fetch je drahé).
    """
    out_dir = Path(out_dir) if out_dir else _CORPUS_DIR / str(class_id)
    map_png = out_dir / "map.png"
    meta_json = out_dir / "meta.json"

    # idempotent check NEpotřebuje adresář existovat (jen path.exists())
    if map_png.exists() and meta_json.exists() and not overwrite:
        return out_dir

    # VŠECHNY chyby (blob smazán, chybí georef quad, neplatný PNG) musí padnout PŘED mkdir,
    # jinak staré/vadné eventy nechají prázdné adresáře v korpusu (bug Sez. 70). Proto si
    # data připravíme kompletně do paměti a teprve pak vytvoříme adresář + zapíšeme.
    blob = fetch_class_blob(class_id)
    image = _largest_full_image(blob["map"])
    meta = _build_meta(class_id, blob, image)   # typ B (chybí proj. quad) řeší WGS84 fallback

    # stáhni rastr a validuj, že je to obrázek (server jinak vrací JSON chybu)
    raw = _get_bytes(image["url"])
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img.load()
    except Exception as e:
        raise RuntimeError(f"Livelox nevrátil platný PNG pro classId={class_id}: {e}") from e

    # data jsou v ruce → teď je bezpečné vytvořit adresář a uložit
    out_dir.mkdir(parents=True, exist_ok=True)
    img.save(map_png)
    meta_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if make_blend:
        build_georef_blend(meta, map_png, out_dir)
    return out_dir


# ───────────────────────── batch: vyhledání eventů + korpus (Sez. 70) ─────────────────────
#
# Pipeline UC5 korpusu: SearchEvents (seznam classId v oblasti) → download_map → segment_gt.
# Reverzováno proti zdroji (home.js): /Home/SearchEvents je POST JSON, klíčová pole níže.


def _post_search_events(body: dict) -> list:
    """POST /Home/SearchEvents → seznam eventů. Backoff retry sdílí s ostatními HTTP volání.

    Tělo (ověřeno z home.js Sez. 70): `geoRectangle` je GeoBox {south,north,west,east},
    `timePeriod` enum řídí čas — `from`/`to` server čte JEN při 'customTimePeriod'
    (jinak default poslední týden). `maxNumberOfResults` má strop 500.
    """
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(_SEARCH_EVENTS_URL, data=data, method="POST", headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": _UA,
    })
    return json.loads(_open_with_retry(req, timeout=120).decode("utf-8"))


def search_events(date_from: str, date_to: str, geobox: dict = NORTH_BOHEMIA_BOX,
                  country: str = "Czechia", max_results: int = 500) -> list:
    """Vyhledá eventy v `geobox` a časovém okně [date_from, date_to] (YYYY-MM-DD).

    Filtruje na `country` (SearchEvents vrací i příhraniční zahraniční eventy). orderBy='time'
    → od nejnovějších; při zásahu stropu 500 zúžit okno (proto volající jede po rocích).
    """
    body = {
        "timePeriod": "customTimePeriod",       # nutné, jinak from/to ignorováno
        "from": date_from, "to": date_to,
        "text": "", "competitionsOnly": False,
        "geoRectangle": geobox, "geoCircle": None,
        "orderBy": "time", "maxNumberOfResults": max_results,
    }
    events = _post_search_events(body)
    return [e for e in events if e.get("countryName") == country]


def list_events_by_year(year_from: int, year_to: int, geobox: dict = NORTH_BOHEMIA_BOX,
                         country: str = "Czechia") -> list:
    """Posbírá unikátní eventy přes roční okna (obchází strop 500 na dotaz).

    Dedup podle event id (eventy se mezi okny nepřekrývají, ale jistota neuškodí).
    Vrací seznam seřazený od nejstarších (časová řada).
    """
    by_id: dict[int, dict] = {}
    for y in range(year_from, year_to + 1):
        for e in search_events(f"{y}-01-01", f"{y}-12-31", geobox, country):
            by_id[e["id"]] = e
        time.sleep(0.5)     # ohled na server mezi okny
    return sorted(by_id.values(), key=lambda e: e["timeInterval"]["start"])


def pick_class_id(event: dict) -> int | None:
    """Vybere 1 reprezentativní class eventu = nejvíc běžců (volba Sez. 70).

    Třídy téhož eventu (H21, D21, …) sdílí JEDNU mapu s různými tratěmi → pro runnability
    GT (kresba kartografa) jsou identické. Bereme class s max participantCount jako nejlépe
    zmapovanou. Historickou řadu téhož prostoru drží různé EVENTY, ne třídy jednoho eventu.
    """
    classes = event.get("classes") or []
    if not classes:
        return None
    return max(classes, key=lambda c: c.get("participantCount", 0))["id"]


def download_corpus(events: list, limit: int | None = None, sleep_s: float = 1.0,
                    segment: bool = True) -> dict:
    """Stáhne 1 mapu per event + (volitelně) GT segmentaci. Idempotentní, odolné vůči chybám.

    `limit` omezí počet eventů (měření vzorku Sez. 70). Vrací souhrn: počty ok/skip/fail +
    seznam chyb (classId → text). Jednotlivá chyba korpus nezboří (try/except per event).
    `make_blend=False` — ortofoto warp je pro 840 map příliš drahý (georef už ověřen Sez. 68).
    """
    # segment_gt je sourozenec v connectors/ — lazy import, ať čisté stahování nezávisí na scipy
    seg = None
    if segment:
        _ensure_connectors_on_path()
        from map_gt import segment_gt as seg

    todo = events[:limit] if limit else events
    ok = skip = fail = 0
    errors: dict[int, str] = {}
    t0 = time.time()
    for i, ev in enumerate(todo, 1):
        cid = pick_class_id(ev)
        if cid is None:
            skip += 1
            continue
        out = _CORPUS_DIR / str(cid)
        already = (out / "map.png").exists() and (out / "meta.json").exists()
        try:
            download_map(cid, overwrite=False, make_blend=False)
            if seg and not (out / "gt_labels.png").exists():
                seg(out / "map.png")
            if already:
                skip += 1
            else:
                ok += 1
            # progress každých 10 + ETA z dosavadní rychlosti
            if i % 10 == 0 or i == len(todo):
                rate = i / max(time.time() - t0, 1e-6)
                print(f"  [{i}/{len(todo)}] ok={ok} skip={skip} fail={fail} "
                      f"~{rate:.2f} ev/s")
        except Exception as e:
            fail += 1
            errors[cid] = f"{type(e).__name__}: {e}"
            print(f"  [{i}/{len(todo)}] FAIL classId={cid}: {errors[cid]}")
        time.sleep(sleep_s)     # rate-limit ohled

    elapsed = time.time() - t0
    print(f"hotovo: ok={ok} skip={skip} fail={fail} za {elapsed:.0f}s "
          f"({len(todo)/max(elapsed,1e-6):.2f} ev/s)")
    return {"ok": ok, "skip": skip, "fail": fail, "elapsed_s": round(elapsed, 1),
            "errors": errors}


if __name__ == "__main__":
    # CLI: bez argumentů = ruční test 1 mapy; "list" = vypíše počty; "batch [limit]" = korpus
    import sys
    # Windows konzole je cp1250 → padá na Unicode šipkách v printech (jako Sez. 74); UTF-8 výstup
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    def _collect_all() -> list:
        """Posbírá CZ severní Čechy + DE Žitavsko-Šluknovsko, seřazené od NEJNOVĚJŠÍCH.

        Od nejnovějších záměrně: Livelox staré bloky (≤2022) z velké části smazal
        (měření Sez. 70 — nejstarší vzorek 0/20), nedávné ~90 % ok. Cenná data tak jdou
        první a staré faily nezdrží začátek. Dedup podle classId (CZ/DE geoboxy se mírně
        překrývají u hranice).
        """
        cz = list_events_by_year(2018, 2026, NORTH_BOHEMIA_BOX, "Czechia")
        de = list_events_by_year(2018, 2026, LUSATIA_BORDER_BOX, "Germany")
        merged = {e["id"]: e for e in cz + de}
        return sorted(merged.values(), key=lambda e: e["timeInterval"]["start"], reverse=True)

    def _sjtsk_dirs() -> list:
        """Adresáře korpusu, které jsou v S-JTSK (epsg 5514) a mají GT — kandidáti GATE 1.

        Jen S-JTSK: ČÚZK ortofoto pokrývá ČR; DE/UTM/WGS84 mapy by daly prázdný podklad.
        """
        out = []
        for d in sorted(_CORPUS_DIR.iterdir()):
            if not (d / "gt_labels.png").exists() or not (d / "meta.json").exists():
                continue
            m = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            if m.get("epsg") == 5514:
                out.append(d)
        return out

    if arg == "list":
        # jen zmapuj oblast (počty eventů/tříd) bez stahování
        evs = _collect_all()
        ncls = sum(e.get("classCount", 0) for e in evs)
        print(f"CZ S.Čechy + DE příhraničí: {len(evs)} eventů, {ncls} tříd "
              f"(1 mapa/event = {len(evs)} map)")
    elif arg == "pair":
        # vyrob zarovnaný pár (X,Y) + změř offset pro JEDEN classId
        cid = sys.argv[2]
        res = build_georef_pair(_CORPUS_DIR / cid)
        o = res["offset"]
        print(f"{cid}: {res['out_w']}x{res['out_h']} @ {res['mpp']} m/px → "
              f"ortho.png + gt_grid.png + blend.png")
        print(f"  offset dx={o['dx_m']} dy={o['dy_m']} |posun|={o['mag_m']} m "
              f"({o['dx_px']},{o['dy_px']} px)")
    elif arg == "gate1":
        # GATE 1 měření na hrstce CZ S-JTSK map: pár + offset, tabulka + medián
        import statistics
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
        dirs = _sjtsk_dirs()[:n]
        print(f"GATE 1 — měření georef offsetu na {len(dirs)} CZ S-JTSK mapách:\n")
        mags = []
        for d in dirs:
            try:
                res = build_georef_pair(d)
                o = res["offset"]
                mags.append(o["mag_m"])
                print(f"  {d.name:>10}  dx={o['dx_m']:+7.2f}  dy={o['dy_m']:+7.2f}  "
                      f"|posun|={o['mag_m']:6.2f} m   ({res['mpp']} m/px)")
            except Exception as e:
                print(f"  {d.name:>10}  FAIL: {type(e).__name__}: {e}")
        if mags:
            print(f"\n  medián |posun| = {statistics.median(mags):.2f} m   "
                  f"(max {max(mags):.2f}, min {min(mags):.2f}, n={len(mags)})")
            print("  práh GATE 1: >~3-5 m systematicky = georef šum (model by se učil nezarovnání)")
    elif arg == "batch":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        evs = _collect_all()
        print(f"nalezeno {len(evs)} eventů (od nejnovějších); stahuji {limit or len(evs)}…")
        download_corpus(evs, limit=limit)
    elif arg == "pairs":
        # hromadná výroba párů (X,Y) pro celý ČR train/val/test set (split.cz_dirs)
        import logging
        import statistics
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        sys.path.insert(0, str(Path(__file__).parent))
        import split as _split
        dirs = _split.cz_dirs()
        print(f"hromadná výroba párů: {len(dirs)} ČR map…")
        s = build_pairs(dirs)
        print(f"\nhotovo: ok {len(s['ok'])}, skip {len(s['skipped'])}, fail {len(s['failed'])}")
        if s["mags"]:
            print(f"GATE 1 offset přes set: medián {statistics.median(s['mags']):.2f} m "
                  f"(max {max(s['mags']):.2f}, min {min(s['mags']):.2f}, n={len(s['mags'])})")
        for cid, err in s["failed"]:
            print(f"  FAIL {cid}: {err}")
    else:
        cid = int(arg) if arg else 1116300
        d = download_map(cid, overwrite=True)
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        print(f"stazeno -> {d}")
        print(f"  name={meta['name']!r} scale=1:{int(meta['mapScale'])} epsg={meta['epsg']}")
        print(f"  {meta['imageWidth']}x{meta['imageHeight']} "
              f"@ {meta['effectiveMppX']:.2f}x{meta['effectiveMppY']:.2f} m/px")
