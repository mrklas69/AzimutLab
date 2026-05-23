"""
batch.py — dávkové generování mini datasetu + náhledová mozaika.

Volá generator.generate() s náhodně navzorkovanými parametry (rug, vd, wat) a
postupnými seedy. Celý dataset je reprodukovatelný z dvojice (--seed0, --n):
parametry losuje master-PRNG seedovaný --seed0, vnitřní šum každé mapy má vlastní seed.

Účel: ověřit, že generátor produkuje rozmanité mapy (ne one-off), a vyrobit
první trénovací sadu pro UC5 — každá instance = mapa + GT masky (viz spec §8).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

# Import ze sousedního modulu: Python přidá složku spouštěného skriptu na sys.path,
# takže `generator` je viditelný, když batch.py běží přímo.
from generator import generate, W, H


def build_montage(dirs: list[Path], out_path: Path, cols: int = 4,
                  scale: int = 3, pad: int = 4) -> None:
    """Složí náhledovou mozaiku z rgb.png jednotlivých map (jen vizuální kontrola).

    Každý náhled zmenší `scale`× a poskládá do mřížky o `cols` sloupcích.
    `divmod(i, cols)` vrátí (řádek, sloupec) pro i-tý náhled.
    """
    tw, th = W // scale, H // scale                 # rozměr jednoho náhledu
    rows = (len(dirs) + cols - 1) // cols            # počet řádků (zaokrouhlení nahoru)
    canvas = Image.new(
        "RGB",
        (cols * tw + (cols + 1) * pad, rows * th + (rows + 1) * pad),
        (230, 230, 230),                             # šedé pozadí mezi náhledy
    )
    for i, d in enumerate(dirs):
        thumb = Image.open(d / "rgb.png").resize((tw, th), Image.BILINEAR)
        r, c = divmod(i, cols)
        canvas.paste(thumb, (pad + c * (tw + pad), pad + r * (th + pad)))
    canvas.save(out_path)


def main() -> None:
    p = argparse.ArgumentParser(description="Dávkové generování mini datasetu OB map.")
    p.add_argument("--n", type=int, default=16, help="počet map")
    p.add_argument("--seed0", type=int, default=1000, help="výchozí seed (reprodukovatelnost celé sady)")
    p.add_argument("--out", default="output/dataset", help="výstupní složka datasetu")
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # master-PRNG losuje parametry → celá sada je daná dvojicí (seed0, n)
    master = np.random.default_rng(args.seed0)

    manifest = []
    dirs = []
    for i in range(args.n):
        seed = args.seed0 + i
        rug, vd, wat = (float(x) for x in master.random(3))   # tři parametry z [0,1)
        inst_dir = out / f"{i:03d}"
        generate(seed, rug, vd, wat, str(inst_dir))
        manifest.append({
            "id": i, "dir": f"{i:03d}", "seed": seed,
            "rug": round(rug, 3), "vd": round(vd, 3), "wat": round(wat, 3),
        })
        dirs.append(inst_dir)

    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    build_montage(dirs, out / "montage.png")
    print(f"Hotovo: {args.n} map -> {out.resolve()}")
    print(f"Mozaika: {(out / 'montage.png').resolve()}")


if __name__ == "__main__":
    main()
