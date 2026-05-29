"""
batch.py — dávkové generování mini datasetu + náhledová mozaika.

Dva režimy přes --terrain:
  - noise (default): fraktální šum, parametry (rug, det) losuje master-PRNG.
    Celá sada je reprodukovatelná z dvojice (--seed0, --n).
  - real: PLNÁ REALITA — reálný ČÚZK DMR 5G terén + reálné cesty/voda/budovy ze
    ZABAGED REST (Sez. 16-18) z různých lokalit ČR (CZ_LOCATIONS). Hlavní (a jediná)
    variace je LOKALITA: rug se u reálného terénu neuplatní a cesty jdou ze ZABAGED
    (ne procedurálně z `det`). Sada je daná seznamem lokalit a dvojicí (--seed0, --n).
    Robustnost: selhání REST u jedné vrstvy/lokality ji jen vynechá (generate
    tolerant=True), batch jede dál; manifest zaznamená skutečné počty + chyby.

Účel: ověřit, že generátor produkuje rozmanité mapy (ne one-off), a vyrobit
trénovací sadu pro UC5 — každá instance = mapa + GT masky (viz spec §8). Reálná
sada zmenšuje domain gap (skutečná geometrie terénu, cest, vody i budov z více míst ČR).
"""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Import ze sousedního modulu: Python přidá složku spouštěného skriptu na sys.path,
# takže `generator` je viditelný, když batch.py běží přímo. W/H jsou rozměry plátna na
# default výseku (batch jede na baseline extentu); DEF_* = výchozí výsek/lokalita.
from generator import (generate_map, MAPS_DIR, W, H,
                       DEF_WIDTH_KM, DEF_HEIGHT_KM, DEF_LAT, DEF_LON)

# ---------- Reálné lokality ČR pro --terrain real ----------
# Členité, OB-relevantní oblasti. Souřadnice = přibližné středy oblastí (WGS84),
# ověřené vizuálně přes montáž. Pořadí je STABILNÍ → seed sady je dán dvojicí
# (seed0, n) i u reálného terénu (i-tá mapa = i-tá lokalita, cyklicky).
CZ_LOCATIONS: list[tuple[str, float, float]] = [
    ("Ceske Svycarsko", 50.821, 14.671),   # pískovec (default i v generator.py)
    ("Cesky raj",       50.53,  15.18),     # pískovcové skály (Hruboskalsko)
    ("Adrspach",        50.61,  16.11),     # skalní město
    ("Jizerske hory",   50.84,  15.27),     # žula, balvany
    ("Zdarske vrchy",   49.67,  16.03),     # členitá vrchovina
    ("Brdy",            49.70,  13.85),     # zalesněné hřbety
    ("Moravsky kras",   49.37,  16.73),     # krasový reliéf
    ("Krusne hory",     50.50,  13.40),     # jižní svahy (hřeben = hranice → DMR 5G bez dat)
    ("Beskydy",         49.55,  18.45),     # hory, převýšení
    ("Sumava",          49.13,  13.23),     # hory (okolí Železné Rudy)
]


def build_montage(dirs: list[Path], out_path: Path, cols: int = 4,
                  scale: int = 3, pad: int = 4,
                  labels: list[str] | None = None) -> None:
    """Složí náhledovou mozaiku z rgb.png jednotlivých map (jen vizuální kontrola).

    Každý náhled zmenší `scale`× a poskládá do mřížky o `cols` sloupcích.
    `divmod(i, cols)` vrátí (řádek, sloupec) pro i-tý náhled.
    `labels` (volitelné, real sada) = popisek do rohu náhledu (název lokality),
    ať je při vizuální kontrole jasné, které místo je které.
    """
    tw, th = W // scale, H // scale                 # rozměr jednoho náhledu
    rows = (len(dirs) + cols - 1) // cols            # počet řádků (zaokrouhlení nahoru)
    canvas = Image.new(
        "RGB",
        (cols * tw + (cols + 1) * pad, rows * th + (rows + 1) * pad),
        (230, 230, 230),                             # šedé pozadí mezi náhledy
    )
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()                  # vestavěný bitmapový font (bez závislosti na systému)
    for i, d in enumerate(dirs):
        thumb = Image.open(d / "rgb.png").resize((tw, th), Image.BILINEAR)
        r, c = divmod(i, cols)
        x0, y0 = pad + c * (tw + pad), pad + r * (th + pad)
        canvas.paste(thumb, (x0, y0))
        if labels:
            # popisek: bílý podklad (mapa je převážně světlá, ale cesty jsou černé
            # čáry → bez podkladu by text místy splynul) + černý text vlevo nahoře
            tx, ty = x0 + 3, y0 + 3
            bb = draw.textbbox((tx, ty), labels[i], font=font)
            draw.rectangle([bb[0] - 2, bb[1] - 1, bb[2] + 2, bb[3] + 1], fill=(255, 255, 255))
            draw.text((tx, ty), labels[i], fill=(0, 0, 0), font=font)
    canvas.save(out_path)


def main() -> None:
    p = argparse.ArgumentParser(description="Dávkové generování mini datasetu OB map.")
    p.add_argument("--n", type=int, default=None,
                   help="počet map (default: noise=16, real=počet lokalit CZ_LOCATIONS)")
    p.add_argument("--seed0", type=int, default=1000, help="výchozí seed (reprodukovatelnost celé sady)")
    p.add_argument("--terrain", choices=["noise", "real"], default="noise",
                   help="noise = fraktální šum (default), real = ČÚZK DMR 5G z lokalit ČR")
    p.add_argument("--out", default=None,
                   help="výstupní složka (default: maps/dataset_<terrain>)")
    args = p.parse_args()

    real = args.terrain == "real"
    # default počtu map závisí na režimu: noise=16, real=projdi celý seznam lokalit
    n = args.n if args.n is not None else (len(CZ_LOCATIONS) if real else 16)
    # default dataset → maps/dataset_<terrain> v kořeni LAB (Sez. 39, kotveno přes MAPS_DIR)
    out = Path(args.out) if args.out else MAPS_DIR / f"dataset_{args.terrain}"
    out.mkdir(parents=True, exist_ok=True)
    # master-PRNG losuje parametry → celá sada je daná dvojicí (seed0, n)
    master = np.random.default_rng(args.seed0)

    manifest = []
    dirs = []
    labels: list[str] | None = [] if real else None   # popisky lokalit do montáže (jen real)
    for i in range(n):
        seed = args.seed0 + i
        inst_dir = out / f"{i:03d}"
        if real:
            # Reálný terén = PLNÁ REALITA: terén + cesty + voda + budovy ze ZABAGED.
            # Hlavní (a jediná) variace je LOKALITA; rug ani det se neuplatní (terén je
            # daný realitou, cesty jdou ze ZABAGED ne z det). Lokality cyklíme, když
            # n > počet lokalit. tolerant=True → selhavší REST vrstvu vynech, neshazuj sadu.
            name, lat, lon = CZ_LOCATIONS[i % len(CZ_LOCATIONS)]
            # batch jede na baseline výseku (DEF_WIDTH/HEIGHT_KM); rug/det u real nelosujeme
            # (variace = lokalita). Vedení (powerlines) batch zatím nedělá — viz docstring.
            # ortho=False: ortofoto je vizuální verify-podklad pro člověka, ne data pro UC5
            # feeder (ten se učí číst generovanou mapu) → dataset jím nezatěžujeme (Sez. 27).
            # Vedení, železnice, řopíky, skály i mosty/tunely batch zatím nedělá (dev-map vrstvy;
            # jako u powerlines — v lesních CZ_LOCATIONS vzácné, většinou 0 prvků). Vše explicitně
            # "off": rocks/bridges mají default "real" → bez vypnutí by noise větev padla na validaci
            # (terrain="noise") a real větev by je zbytečně stahovala.
            generate_map(
                lat, lon, DEF_WIDTH_KM, DEF_HEIGHT_KM, out_dir=str(inst_dir),
                seed=seed, rug=0.0, det=0.0, terrain="real",
                paths="real", rides="off", water="real", paved="off", buildings="real", powerlines="off",
                railways="off", ropiky="off", rocks="off", bridges="off",
                tolerant=True, ortho=False)
            # počty skutečně nakreslených vrstev (+ případné chyby) čteme z meta.json
            # = SSoT výsledku; rozliší prázdnou vrstvu (0 v datech) od selhání REST.
            meta = json.loads((inst_dir / "meta.json").read_text(encoding="utf-8"))
            entry = {
                "id": i, "dir": f"{i:03d}", "seed": seed,
                "location": name, "lat": lat, "lon": lon,
                "layers": {
                    "paths": meta["paths"]["count"],
                    "water": meta.get("water", {}).get("count", 0),
                    "buildings": meta.get("buildings", {}).get("count", 0),
                },
            }
            if "layer_errors" in meta:
                entry["layer_errors"] = meta["layer_errors"]
            manifest.append(entry)
            labels.append(name)
        else:
            # Noise sada: losujeme rug (členitost terénu) a det (počet cest).
            # Sada je reprodukovatelná z dvojice (seed0, n).
            rug, det = (float(x) for x in master.random(2))   # dva parametry z [0,1)
            # noise = procedurální Option 1 (baseline 65): default výsek + proc cesty, bez
            # real vrstev. lat/lon se u noise neuplatní (georef je lokální), předáváme DEF_*.
            generate_map(
                DEF_LAT, DEF_LON, DEF_WIDTH_KM, DEF_HEIGHT_KM, out_dir=str(inst_dir),
                seed=seed, rug=rug, det=det, terrain="noise", paths="proc", rides="off",
                water="off", paved="off", buildings="off", powerlines="off", railways="off",
                ropiky="off", rocks="off", bridges="off")
            manifest.append({
                "id": i, "dir": f"{i:03d}", "seed": seed,
                "rug": round(rug, 3), "det": round(det, 3),
            })
        dirs.append(inst_dir)

    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    build_montage(dirs, out / "montage.png", labels=labels)
    print(f"Hotovo: {n} map ({args.terrain}) -> {out.resolve()}")
    print(f"Mozaika: {(out / 'montage.png').resolve()}")


if __name__ == "__main__":
    main()
