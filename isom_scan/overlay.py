#!/usr/bin/env python3
"""Anotační overlay: vykreslí 'points' z GT (nebo z run výstupu) na sken.

Slouží kartografovi ke korekci GT očima místo čtení JSONu (always-show-visual-output).
Funguje i na libovolný `runs/*.json` výstup modelu — vizuální diff proti skenu.

Barvy dle geom: bod = červená kolečko, plocha = modrý čtvereček, linie = zelený trojúhelník.
U bodových symbolů je každé kolečko jeden výskyt; u ploch/linií jsou body jen reprezentativní.

Použití:
  python overlay.py                       # GT → gt/gt_overlay.png
  python overlay.py --in runs/x.json --out runs/x_overlay.png
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

for _s in (sys.stdout, sys.stderr):  # Windows cp1250 → šipky v printu padají; vynuť UTF-8
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(__file__)
GEOM_STYLE = {  # geom: (barva, marker)
    "point": ((220, 20, 60), "circle"),
    "area": ((30, 90, 220), "square"),
    "line": ((20, 150, 40), "triangle"),
}


def load_detections(path):
    d = json.load(open(path, encoding="utf-8"))
    out = d.get("output", d)
    return d, out.get("detections", [])


def get_font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_marker(draw, x, y, color, marker, r=8):
    if marker == "circle":
        draw.ellipse([x - r, y - r, x + r, y + r], outline=color, width=3)
    elif marker == "square":
        draw.rectangle([x - r, y - r, x + r, y + r], outline=color, width=3)
    else:  # triangle
        draw.polygon([(x, y - r), (x - r, y + r), (x + r, y + r)], outline=color, width=3)


def draw_label(draw, x, y, text, color, font):
    tx, ty = x + 9, y - 7
    box = draw.textbbox((tx, ty), text, font=font)
    draw.rectangle([box[0] - 1, box[1] - 1, box[2] + 1, box[3] + 1], fill=(255, 255, 255))
    draw.text((tx, ty), text, fill=color, font=font)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", default=os.path.join(HERE, "gt", "ground_truth.json"))
    ap.add_argument("--img", default=os.path.join(HERE, "task_isom_scan.png"))
    ap.add_argument("--out", default=os.path.join(HERE, "gt", "gt_overlay.png"))
    args = ap.parse_args()

    meta, dets = load_detections(args.inp)
    im = Image.open(args.img).convert("RGB")
    draw = ImageDraw.Draw(im)
    font = get_font(15)

    n_markers = 0
    for d in dets:
        color, marker = GEOM_STYLE.get(d.get("geom", "point"), GEOM_STYLE["point"])
        code = str(d.get("code", "?"))
        for p in d.get("points", []):
            x, y = int(p["x"]), int(p["y"])
            draw_marker(draw, x, y, color, marker)
            draw_label(draw, x, y, code, color, font)
            n_markers += 1

    status = str(meta.get("_status", ""))[:60]
    draw.text((10, 10), f"{os.path.basename(args.inp)}  |  {status}", fill=(0, 0, 0), font=font)
    im.save(args.out)
    print(f"Vykresleno {n_markers} značek → {args.out}", file=sys.stderr)
    print(args.out)


if __name__ == "__main__":
    main()
