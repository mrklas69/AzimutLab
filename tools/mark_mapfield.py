"""Ruční crop polygon mapového pole (Sez. 173) — klikací nástroj.

Auto detekce mapového území (`map_gt._detect_map_area` connected-component / `measure_dod`
convex hull) selhává na barevném layoutu: zelený banner/loga MAJÍ mapovou barvu a jsou spojené
s mapou → separace z nich dělá falešný les a KPI hull je obalí (kontaminace counts). Řešení:
naklikat polygon skutečného mapového pole ručně, jednou per sken.

Použití (lokálně s GUI):
    python tools/mark_mapfield.py <name>          # <name> = resources/<name>.png

Klikej rohy mapového pole po obvodu (libovolný počet bodů, nepravidelný mnohoúhelník).
  - levý klik = přidat bod
  - pravý klik / Backspace = smazat poslední bod
  - Enter = uložit a skončit
Uloží resources/<name>_mapfield.json: {"scan_size":[W,H], "polygon_px":[[col,row],…]} v px
PLNÉHO skenu. Konzumuje measure_dod._load_map_field (separace i KPI ořez). Existující JSON se
načte jako počáteční polygon (lze doladit)."""
import sys
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
_PREVIEW_MAX = 1400          # delší strana náhledu [px] — klik souřadnice škálujeme zpět na full-res


def main(name: str) -> None:
    import numpy as np
    import matplotlib.pyplot as plt
    from PIL import Image

    png = REPO / "resources" / f"{name}.png"
    if not png.exists():
        sys.exit(f"chybí sken: {png}")
    with Image.open(png) as im:
        im = im.convert("RGB")
        W, H = im.size
        f = max(1.0, max(W, H) / _PREVIEW_MAX)
        prev = im.resize((round(W / f), round(H / f)), Image.BILINEAR)
    out = REPO / "resources" / f"{name}_mapfield.json"
    pts: list[list[float]] = []                      # v PREVIEW px
    if out.exists():                                  # předvyplň existující polygon (doladění)
        d = json.loads(out.read_text(encoding="utf-8"))
        pts = [[c / f, r / f] for c, r in d["polygon_px"]]
        print(f"načten existující polygon ({len(pts)} bodů) — dolaď a Enter")

    fig, ax = plt.subplots(figsize=(10, 10 * prev.height / prev.width))
    ax.imshow(np.asarray(prev))
    ax.set_title(f"{name}: klikej rohy mapového pole · pravý klik=smaž · Enter=uložit")
    line, = ax.plot([], [], "m-o", lw=1.5, ms=5)

    def redraw():
        if pts:
            xs = [p[0] for p in pts] + [pts[0][0]]
            ys = [p[1] for p in pts] + [pts[0][1]]
            line.set_data(xs, ys)
        else:
            line.set_data([], [])
        fig.canvas.draw_idle()

    def on_click(ev):
        if ev.inaxes != ax:
            return
        if ev.button == 1:
            pts.append([ev.xdata, ev.ydata])
        elif ev.button == 3 and pts:
            pts.pop()
        redraw()

    def on_key(ev):
        if ev.key == "enter":
            plt.close(fig)
        elif ev.key == "backspace" and pts:
            pts.pop()
            redraw()

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    redraw()
    plt.show()

    if len(pts) < 3:
        sys.exit("méně než 3 body → neukládám")
    poly_full = [[round(p[0] * f, 1), round(p[1] * f, 1)] for p in pts]
    out.write_text(json.dumps({"scan_size": [W, H], "polygon_px": poly_full},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"uloženo {out} ({len(poly_full)} bodů, sken {W}×{H})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("použití: python tools/mark_mapfield.py <name>")
    main(sys.argv[1])
