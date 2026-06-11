"""magnetic.py — grivace (úhel grid S-JTSK → magnetický sever) pro bod a datum.

UC2 konektor (sourozenec dmr/zabaged): skládá DEKLINACI magnetického pole (WMM přes pygeomag,
vestavěné koeficienty → offline, žádný API key) a KONVERGENCI poledníků S-JTSK Křovák (pyproj)
do GRIVACE = orientace severníku OB mapy vůči mapovému gridu.

Vztah (OOM georef konvence, East kladně): `grivation = declination + grid_convergence`, kde
`grid_convergence` (grid−true) = −(pyproj `meridian_convergence`) — pyproj vrací OPAČNÉ znaménko
než OOM. Znaménko OVĚŘENO proti reálným skenům `resources/*.omap` (Sez. 112): grivace = decl −
pyproj_conv ≈ 11–13° v ČR (Bedřichovka sken 10,88°, dnešní výpočet 12,7° — rozdíl = rostoucí
deklinace ~0,13°/rok; trend potvrzuje znaménko). V ČR konvergence (~+7,4°) dominuje grivaci nad
deklinací (~+5°), proto je odchylka gen grid-north od reálných map velká.

Konzument: generator `--grivation-auto` / `--grivation-date` → zápis do `.omap` georef.
pygeomag WMM platí pro aktuální epochu (2024–2029); mimo rozsah VARUJE (no silent fallback).
"""
import warnings
from datetime import date

from pygeomag import GeoMag
from pyproj import Proj

_GEOMAG = GeoMag()                 # WMM s vestavěnými koeficienty (aktuální epocha)
_SJTSK = Proj("EPSG:5514")         # S-JTSK / Křovák East North
_WMM_MIN, _WMM_MAX = 2024.0, 2029.0   # platnost vestavěného WMM modelu


def _decimal_year(when: date | None) -> float:
    """`date` → desetinný rok (vstup pygeomag). None → dnešní datum."""
    d = when or date.today()
    start, end = date(d.year, 1, 1), date(d.year + 1, 1, 1)
    return d.year + (d - start).days / (end - start).days


def declination(lat: float, lon: float, when: date | None = None) -> float:
    """Magnetická deklinace (mag−true, East kladně) [°] z WMM pro bod a datum (default dnes)."""
    yr = _decimal_year(when)
    if not (_WMM_MIN <= yr <= _WMM_MAX):
        warnings.warn(f"rok {yr:.1f} mimo WMM platnost {_WMM_MIN:.0f}–{_WMM_MAX:.0f} "
                      f"→ deklinace extrapolovaná (nepřesná)")
    return _GEOMAG.calculate(glat=lat, glon=lon, alt=0, time=yr).d


def convergence(lat: float, lon: float) -> float:
    """Konvergence poledníků grid(S-JTSK)−true (East kladně, OOM konvence) [°].

    = −(pyproj `meridian_convergence`): pyproj vrací opačné znaménko než OOM `grid_convergence`
    (ověřeno Sez. 112 proti skenům). V ČR ~+7,3–7,6° — dominuje grivaci nad deklinací."""
    return -_SJTSK.get_factors(lon, lat).meridian_convergence


def grivation(lat: float, lon: float, when: date | None = None) -> float:
    """Grivace (úhel grid S-JTSK → magnetický sever, East kladně) [°] pro bod a datum (default dnes).

    `grivation = declination + convergence` (OOM vztah). Zapisuje se do `.omap` georef
    (generator `--grivation-auto`). V ČR ~11–13°. Verify: `resources/*.omap` skeny (Sez. 112)."""
    return declination(lat, lon, when) + convergence(lat, lon)


if __name__ == "__main__":   # rychlý self-check proti skenům resources/*.omap
    for nm, la, lo in [("Bedřichovka", 50.80696, 15.00645), ("Blatná", 50.80616, 15.16672),
                       ("Soví vrch", 50.83, 14.78), ("Velbloud", 49.0, 14.8)]:
        print(f"{nm:12s} grivace dnes = {grivation(la, lo):+.2f}°  "
              f"(decl {declination(la, lo):+.2f} + konv {convergence(la, lo):+.2f})")
