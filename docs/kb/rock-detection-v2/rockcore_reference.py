"""
rockcore.py - jadro pro detekci skalnich utvaru z CUZK DMR 5G.

Zadny Streamlit zde - cista logika, da se testovat samostatne.
Data: CUZK DMR 5G (lidar), ArcGIS ImageServer exportImage -> Float32 vyskovy rastr.
Licence dat: CC BY 4.0 (c) CUZK.
"""
import math
import json
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from rasterio.features import shapes, rasterize
from scipy.ndimage import (gaussian_filter, binary_opening, binary_closing,
                           binary_fill_holes, binary_erosion, label)
from shapely.geometry import shape, mapping, GeometryCollection, Polygon, MultiPolygon
from shapely.ops import unary_union, transform as shp_transform
from pyproj import Transformer

# CUZK ArcGIS ImageServer pro DMR 5G (dve domeny - starsi/novejsi)
HOSTS = ["https://ags.cuzk.cz", "https://ags.cuzk.gov.cz"]
SERVICE = "/arcgis2/rest/services/dmr5g/ImageServer/exportImage"

# DULEZITE: prah sklonu je svazany s rozlisenim (bilinearni prevzorkovani
# "rozmazava" steny -> cim hrubsi pixel, tim nizsi namereny sklon).
# Proto se analyza VZDY pocita na pevnem rozliseni; THR_FACE=46 je
# kalibrovan prave pro ANALYSIS_RES. Nemenit bez rekalibrace prahu!
ANALYSIS_RES = 0.5     # m/px - pevne analyticke rozliseni
MAX_SIZE = 2000        # px - strop velikosti rastru (server i pamet)

# Cesky narodni system; ZABAGED, ortofoto i OOM podklady jedou v nem.
CRS_SJTSK = 5514       # S-JTSK / Krovak East North


# ---------------------------------------------------------------- DEM fetch
def fetch_dem(lat, lon, half_m=360.0, res=ANALYSIS_RES, timeout=90):
    """Stahne ctvercovy vysek DMR 5G kolem (lat,lon) jako Float32 pole.
    Velikost rastru se odvozuje z half_m a pevneho rozliseni `res`.
    Vraci: (z[ndarray], Affine transform, crs_str). CRS vystupu = S-JTSK 5514."""
    size = min(int(round(2 * half_m / res)), MAX_SIZE)
    to_sjtsk = Transformer.from_crs("EPSG:4326", f"EPSG:{CRS_SJTSK}", always_xy=True).transform
    cx, cy = to_sjtsk(lon, lat)
    bbox = f"{cx - half_m},{cy - half_m},{cx + half_m},{cy + half_m}"
    params = dict(bbox=bbox, bboxSR=CRS_SJTSK, imageSR=CRS_SJTSK, size=f"{size},{size}",
                  format="tiff", pixelType="F32",
                  interpolation="RSP_BilinearInterpolation", f="image")
    q = urlencode(params)
    last = None
    for h in HOSTS:
        try:
            with urlopen(f"{h}{SERVICE}?{q}", timeout=timeout) as resp:
                data = resp.read()
            with MemoryFile(data) as mf, mf.open() as ds:
                if ds.dtypes[0] not in ("float32", "float64"):
                    raise RuntimeError(f"server vratil {ds.dtypes[0]}, ne vysky")
                # server vraci degradovany LOCAL_CS WKT -> CRS zname, prebijeme
                return ds.read(1).astype("float64"), ds.transform, f"EPSG:{CRS_SJTSK}"
        except Exception as e:  # noqa
            last = e
    raise RuntimeError(f"Stazeni DMR 5G selhalo: {last}")


# ---------------------------------------------------------------- terrain
def _disk(r):
    r = max(int(r), 0)
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r


def slope_and_shade(z, px, sigma=0.6, az=315.0, alt=45.0):
    """Vraci (slope_deg, hillshade[0..1]). Slope je smerove nezavisly => maska."""
    zs = gaussian_filter(z, sigma) if sigma > 0 else z
    gy, gx = np.gradient(zs, px, px)
    sl = np.arctan(np.hypot(gx, gy))
    slope_deg = np.degrees(sl)
    A = np.radians(360.0 - az + 90.0)
    Z = np.radians(90.0 - alt)
    asp = np.arctan2(gy, -gx)
    hs = np.clip(np.cos(Z) * np.cos(sl) + np.sin(Z) * np.sin(sl) * np.cos(A - asp), 0, 1)
    return slope_deg, hs


def rock_mask(slope_deg, px, thr=46.0, close_r=8, fill_max=250.0, min_area=60.0):
    """Dvoukrokova logika: vysoky prah sklonu = jiste skalni steny ->
    morfologicky scelit do bloku. Pure slope = zadne stinovani."""
    m = binary_opening(slope_deg >= thr, _disk(1))      # despeckle
    if close_r > 0:
        m = binary_closing(m, _disk(close_r))           # steny -> blok
    # vyplnit jen male diry (vrsky vezi), velke pruchody nechat otevrene
    filled = binary_fill_holes(m)
    holes = filled & ~m
    lab, n = label(holes)
    sz = np.bincount(lab.ravel())
    lim = fill_max / (px * px)
    for i in range(1, len(sz)):
        if sz[i] < lim:
            m[lab == i] = True
    # zahodit drobky
    lab, n = label(m)
    sz = np.bincount(lab.ravel())
    lim = min_area / (px * px)
    for i in range(1, len(sz)):
        if sz[i] < lim:
            m[lab == i] = False
    return m


# ---------------------------------------------------------------- vectorize
def _chaikin_ring(coords, iters):
    pts = np.asarray(coords, dtype=float)
    if len(pts) < 4:
        return pts
    for _ in range(iters):
        new = []
        for i in range(len(pts) - 1):
            p, q = pts[i], pts[i + 1]
            new.append(0.75 * p + 0.25 * q)
            new.append(0.25 * p + 0.75 * q)
        new.append(new[0])
        pts = np.array(new)
    return pts


def _smooth_poly(poly, iters):
    ext = _chaikin_ring(list(poly.exterior.coords), iters)
    ints = [_chaikin_ring(list(r.coords), iters) for r in poly.interiors]
    return Polygon(ext, ints)


def polygonize(mask, transform, simp=1.2, chaikin_iters=0):
    polys = [shape(g) for g, v in
             shapes(mask.astype("uint8"), mask=mask, transform=transform) if v == 1]
    if not polys:
        return GeometryCollection()
    geom = unary_union(polys)
    if simp > 0:
        geom = geom.simplify(simp, preserve_topology=True)
    if chaikin_iters > 0:
        parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        sm = [_smooth_poly(p, chaikin_iters) for p in parts if p.geom_type == "Polygon"]
        geom = unary_union(sm)
    return geom


def stats(geom):
    if geom.is_empty:
        return 0, 0.0
    parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    return len(parts), geom.area / 1e4  # pocet, hektary


# ---------------------------------------------------------------- render
def render_flat(geom, shape_hw, transform,
                bg=(188, 212, 158), rock=(150, 150, 150)):
    H, W = shape_hw
    img = np.empty((H, W, 3), "uint8")
    img[:] = bg
    if not geom.is_empty:
        fin = rasterize([(geom, 1)], out_shape=shape_hw, transform=transform, dtype="uint8")
        img[fin == 1] = rock
    return img


def render_overlay(geom, hs, shape_hw, transform, outline=(220, 40, 40)):
    g = (hs * 255).astype("uint8")
    ov = np.dstack([g, g, g])
    if not geom.is_empty:
        fin = rasterize([(geom, 1)], out_shape=shape_hw, transform=transform, dtype="uint8")
        edge = fin.astype(bool) ^ binary_erosion(fin.astype(bool), _disk(1))
        ov[edge] = outline
    return ov


def render_hillshade(hs):
    g = (hs * 255).astype("uint8")
    return np.dstack([g, g, g])


# ---------------------------------------------------------------- export
def to_geojson(geom, crs_str, target="EPSG:4326"):
    """Export do GeoJSON. target='EPSG:4326' (web/RFC7946) nebo 'EPSG:5514'
    (S-JTSK, metricky - pro QGIS/OOM s ceskymi podklady)."""
    if crs_str and target and crs_str != target:
        tr = Transformer.from_crs(crs_str, target, always_xy=True).transform
        geom = shp_transform(tr, geom)
    parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else ([] if geom.is_empty else [geom])
    return {"type": "FeatureCollection",
            "crs": ({"type": "name", "properties": {"name": f"urn:ogc:def:crs:EPSG::{target.split(':')[1]}"}}
                    if target != "EPSG:4326" else None),
            "features": [{"type": "Feature",
                          "properties": {"id": i, "kind": "rock"},
                          "geometry": mapping(p)} for i, p in enumerate(parts)]}


def dem_geotiff_bytes(z, transform, crs_str):
    with MemoryFile() as mf:
        with mf.open(driver="GTiff", height=z.shape[0], width=z.shape[1],
                     count=1, dtype="float32", crs=crs_str, transform=transform) as ds:
            ds.write(z.astype("float32"), 1)
        return mf.read()


# ---------------------------------------------------------------- self-test
if __name__ == "__main__":
    print("self-test: stahuji DMR 5G pro Sulcak / Ztracene udoli ...")
    z, T, crs = fetch_dem(50.5521339, 15.1582817, half_m=360)   # pevne ANALYSIS_RES
    px = abs(T.a)
    print(f"  DEM {z.shape}, px={px:.3f} m, vyska {z.min():.0f}-{z.max():.0f} m, crs={crs}")
    slope, hs = slope_and_shade(z, px)
    m = rock_mask(slope, px, thr=46, close_r=8, fill_max=250, min_area=60)
    g = polygonize(m, T, simp=1.2, chaikin_iters=2)
    n, ha = stats(g)
    print(f"  vysledek: {n} polygonu, {ha:.2f} ha")
    gj = to_geojson(g, crs)                       # WGS84
    gj_sjtsk = to_geojson(g, crs, target="EPSG:5514")
    print(f"  geojson features: {len(gj['features'])} (WGS84 i S-JTSK)")
    from PIL import Image
    Image.fromarray(render_flat(g, z.shape, T)).save("selftest_flat.png")
    print("  ulozeno selftest_flat.png  -> OK")
