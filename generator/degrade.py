"""degrade.py — fáze II: degradace čistého renderu na „sken" (UC5, Sez. 86).

Vstup = `rgb.png` (čistý render z generate_map, X-zdroj páru), výstup = degradovaný „sken" PNG
= X v páru [sken, .omap]. Y (.omap) se NEmění → pár zůstává konzistentní. Reconstructor() se pak
učí číst reálně vypadající tištěnou/naskenovanou mapu, ne hladký rastr (doložený domain gap, Sez. 82).

Degradace je VÝHRADNĚ fotometrická (barva/šum/blur/komprese) — geometrii (rotace/warp) řeší
augmentace v model/png2area/dataset.py (D4, Sez. 78), kde se transformuje X i Y zároveň. Neduplikovat (DRY/SLAP).

Vrstvy v pořadí fyzikálního řetězce tisk → optika → médium → snímání → komprese:
  1. CMYK misregistrace — barevné desky tisku rozjeté o sub-px (spec §8.3),
  2. blur            — rozostření tiskového rastru + optiky skeneru,
  3. papír + věk     — papírová textura (multiplikativní jas) + teplý nádech stáří,
  4. senzorový šum   — aditivní šum snímače skeneru,
  5. JPEG            — kompresní artefakty (digitální, proto poslední).

Deterministické přes `seed` (jako generate_map) → reprodukovatelné + libovolně variant z jednoho renderu.
Spouštět z kořene přes .venv (sys.path skript, fáze B).
"""
import io
import sys
import pathlib

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, shift as ndi_shift

Image.MAX_IMAGE_PIXELS = None
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _misregister(x: np.ndarray, rng) -> np.ndarray:
    """CMYK desky tisknuté zvlášť → posun barev o sub-px. Aproximace na RGB: každý kanál
    posunut jiným malým vektorem (bilineárně). Drobné, ať zůstane mapa čitelná."""
    out = np.empty_like(x)
    for ch in range(3):
        dx, dy = rng.uniform(-1.1, 1.1, size=2)            # px posun desky
        out[..., ch] = ndi_shift(x[..., ch], (dy, dx), order=1, mode="nearest")
    return out


def _blur(x: np.ndarray, rng) -> np.ndarray:
    """Mírné rozostření — tiskový rastr + optika skeneru (sigma jen v rovině, ne přes kanály)."""
    sigma = rng.uniform(0.4, 0.9)
    return gaussian_filter(x, sigma=(sigma, sigma, 0))


def _paper(x: np.ndarray, rng) -> np.ndarray:
    """Papírová textura (nízkofrekvenční mapa jasu) + teplý nádech stáří (zažloutnutí)."""
    H, W = x.shape[:2]
    tex = gaussian_filter(rng.normal(0.0, 1.0, (H, W)), sigma=9.0)
    tex = (tex - tex.min()) / (np.ptp(tex) + 1e-6)         # 0-1 nízkofrekvenční pole
    bright = 0.93 + 0.07 * tex                              # multiplikativní jas 0,93-1,00
    out = x * bright[..., None]
    out *= np.array([1.015, 1.0, 0.955], dtype=np.float32)  # teplý tint: ↑R ↓B = zažloutnutí
    return np.clip(out, 0.0, 255.0)


def _noise(x: np.ndarray, rng) -> np.ndarray:
    """Aditivní gaussovský šum snímače skeneru."""
    sd = rng.uniform(2.0, 5.0)
    return np.clip(x + rng.normal(0.0, sd, x.shape), 0.0, 255.0)


def _jpeg(x: np.ndarray, rng) -> np.ndarray:
    """Kompresní artefakty — JPEG roundtrip přes paměť. Poslední (digitální vada po skenu)."""
    q = int(rng.integers(72, 89))
    buf = io.BytesIO()
    Image.fromarray(x.astype(np.uint8)).save(buf, format="JPEG", quality=q)
    buf.seek(0)
    return np.asarray(Image.open(buf).convert("RGB")).astype(np.float32)


def degrade(rgb, seed: int = 0) -> np.ndarray:
    """Čistý render (HxWx3 uint8) → degradovaný „sken" (HxWx3 uint8). Deterministické přes seed."""
    rng = np.random.default_rng(seed)
    x = np.asarray(rgb)[..., :3].astype(np.float32)
    x = _misregister(x, rng)
    x = _blur(x, rng)
    x = _paper(x, rng)
    x = _noise(x, rng)
    x = _jpeg(x, rng)                                       # JPEG poslední
    return x.astype(np.uint8)


def degrade_file(src: str | pathlib.Path, dst: str | pathlib.Path | None = None,
                 seed: int = 0) -> pathlib.Path:
    """Načte render PNG, degraduje, uloží `scan.png` vedle (nebo do `dst`). Vrací cestu."""
    src = pathlib.Path(src)
    rgb = np.asarray(Image.open(src).convert("RGB"))
    scan = degrade(rgb, seed=seed)
    out = pathlib.Path(dst) if dst else src.with_name("scan.png")
    Image.fromarray(scan).save(out)
    print(f"sken → {out}  ({scan.shape[1]}×{scan.shape[0]} px, seed {seed})")
    return out


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    src = sys.argv[1] if len(sys.argv) > 1 else str(_REPO_ROOT / "maps" / "Soví vrch" / "rgb.png")
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    degrade_file(src, seed=seed)
