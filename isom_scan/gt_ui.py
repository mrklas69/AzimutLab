#!/usr/bin/env python3
"""Část B nástroje ISOM GT factory: kurační UI nad SETem dlaždic (z `build_tile_set.py`).

Otevře v prohlížeči `tile_gt.json`, prochází dlaždice 512×512, předvyplněné detekce
ukáže jako kroužky a nechá kurátora rychle:
  - potvrdit / zamítnout detekci (TP / FP),
  - **doplnit přehlédnuté** symboly klikem do dlaždice (= FN; tady se měří recall),
  - vybrat ISOM kód z **celé palety** (SVG ikony jako v OOM) — paleta zároveň slouží
    jako **KOMPAS dashboard** (badge = kolik GT symbolů toho kódu už v setu je).
Kompletní GT (confirmed + added) se průběžně ukládá zpět do `tile_gt.json`.

Účel = doložit, že KOMPAS je oprávněný (umíme symbol najít na reálném skenu na 100 %).
Etapa 1 (vytěžení/měření), žádný trénink. Stdlib `http.server`, žádná nová závislost.

    .venv\\Scripts\\python.exe isom_scan/gt_ui.py --tileset temp/tileset_buschdorfl_green/tile_gt.json
"""

import argparse
import json
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
HTML_PATH = HERE / "gt_ui.html"
ISOM_DIR = REPO_ROOT / "resources" / "isom"
# filename katalogu: "417-Prominent-large-tree.svg" → kód 417, název "Prominent large tree"
_SVG_RE = re.compile(r"^([\d.]+)-(.+)\.svg$")

# První číslice kódu → kategorie (název, barva pozadí v paletě) — řazení/seskupení jako v OOM.
CATEGORIES = {
    "1": ("Terén", "#d8b384"),
    "2": ("Skály a kameny", "#bdbdbd"),
    "3": ("Voda a mokřady", "#86d7ea"),
    "4": ("Vegetace", "#9be86a"),
    "5": ("Umělé objekty", "#dedede"),
    "6": ("Technické", "#e3c6e3"),
    "7": ("Kurz závodu", "#f0a6f0"),
}


def _load_palette() -> list:
    """[{code, name, category, svg}] ze SVG katalogu. No-silent: katalog chybí → prázdná paleta + varování."""
    out = []
    if ISOM_DIR.is_dir():
        for svg in ISOM_DIR.glob("*.svg"):
            m = _SVG_RE.match(svg.name)
            if not m:
                continue
            out.append({"code": m.group(1), "name": m.group(2).replace("-", " "),
                        "category": m.group(1)[0], "svg": svg.name})
    else:
        print(f"[varovani] ISOM katalog {ISOM_DIR} chybi; paleta bude prazdna", flush=True)
    # numerické řazení dle kódu (417 < 419 < 501; 105.2 mezi 105 a 106)
    out.sort(key=lambda r: [int(p) for p in r["code"].split(".")])
    return out


class TilesetState:
    """Drží tile_gt.json + paletu; zápisy serializuje zámkem (ThreadingHTTPServer = víc vláken)."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path.resolve()
        self.root = self.manifest_path.parent  # dlaždice jsou relativně k manifestu
        self.lock = threading.Lock()
        self.palette = _load_palette()
        self._load()

    def _load(self) -> None:
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.by_id = {t["id"]: t for t in self.manifest.get("tiles", [])}

    def _flush(self) -> None:
        self.manifest_path.write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _gt_counts(self) -> dict:
        """KOMPAS odškrtávání: počet GT symbolů (confirmed + added) per ISOM kód napříč setem."""
        counts: dict = {}
        for t in self.manifest.get("tiles", []):
            for s in t.get("symbols", []):
                if s.get("status") in ("confirmed", "added"):
                    counts[s["code"]] = counts.get(s["code"], 0) + 1
        return counts

    def _n_reviewed(self) -> int:
        return sum(1 for t in self.manifest.get("tiles", []) if t.get("reviewed"))

    def tileset_payload(self) -> dict:
        return {
            "theme": self.manifest.get("theme"),
            "theme_codes": self.manifest.get("theme_codes", []),
            "source_map": self.manifest.get("source_map"),
            "tile_px": self.manifest.get("tile_px", 512),
            "palette": self.palette,
            "categories": CATEGORIES,
            "gt_counts": self._gt_counts(),
            "n_reviewed": self._n_reviewed(),
            "tiles": [
                {"id": t["id"], "green_frac": t.get("green_frac"),
                 "n_symbols": len(t.get("symbols", [])), "reviewed": t.get("reviewed", False)}
                for t in self.manifest.get("tiles", [])
            ],
        }

    def tile_detail(self, tid: str) -> dict | None:
        t = self.by_id.get(tid)
        if t is None:
            return None
        return {"id": t["id"], "file": t["file"], "w": t["w"], "h": t["h"],
                "reviewed": t.get("reviewed", False), "symbols": t.get("symbols", [])}

    def tile_png(self, tid: str) -> bytes | None:
        t = self.by_id.get(tid)
        if t is None:
            return None
        p = self.root / t["file"]
        return p.read_bytes() if p.exists() else None

    def icon_svg(self, name: str) -> bytes | None:
        # ochrana proti path traversal — name přichází z klienta
        if not name or "/" in name or "\\" in name or ".." in name:
            return None
        p = ISOM_DIR / name
        return p.read_bytes() if p.exists() else None

    def save_tile_gt(self, body: dict) -> dict:
        """Frontend posílá kompletní stav dlaždice (symbols + reviewed) → přepíšeme a uložíme."""
        tid = str(body.get("id", ""))
        with self.lock:
            t = self.by_id.get(tid)
            if t is None:
                return {"ok": False, "error": f"neznama dlazdice {tid!r}"}
            syms = body.get("symbols")
            if isinstance(syms, list):
                t["symbols"] = syms
            t["reviewed"] = bool(body.get("reviewed", t.get("reviewed", False)))
            self._flush()
            return {"ok": True, "gt_counts": self._gt_counts(), "n_reviewed": self._n_reviewed()}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        st = self.server.state
        if u.path in ("/", "/index.html"):
            self._bytes(HTML_PATH.read_bytes(), "text/html; charset=utf-8")
        elif u.path == "/api/tileset":
            self._json(st.tileset_payload())
        elif u.path == "/api/tile_detail":
            d = st.tile_detail(parse_qs(u.query).get("id", [""])[0])
            self._json(d) if d is not None else self.send_error(404, "neznama dlazdice")
        elif u.path == "/api/tile":
            png = st.tile_png(parse_qs(u.query).get("id", [""])[0])
            self._bytes(png, "image/png") if png else self.send_error(404)
        elif u.path == "/api/icon":
            svg = st.icon_svg(parse_qs(u.query).get("name", [""])[0])
            self._bytes(svg, "image/svg+xml") if svg else self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            self.send_error(400, "neplatny JSON")
            return
        if u.path == "/api/tile_gt":
            self._json(self.server.state.save_tile_gt(body))
        else:
            self.send_error(404)

    def _bytes(self, data: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: dict):
        self._bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8")

    def log_message(self, *args):
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tileset", type=Path, required=True, help="tile_gt.json z build_tile_set.py")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows cp1250 past
    except Exception:
        pass
    if not args.tileset.exists():
        raise SystemExit(f"Chybi tileset: {args.tileset}")
    if not HTML_PATH.exists():
        raise SystemExit(f"Chybi frontend: {HTML_PATH}")

    state = TilesetState(args.tileset)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.state = state

    url = f"http://127.0.0.1:{args.port}"
    p = state.tileset_payload()
    print(f"GT factory UI bezi na {url}", flush=True)
    print(f"  tileset: {args.tileset} | mapa: {p['source_map']} | tema: {p['theme']} {p['theme_codes']}", flush=True)
    print(f"  dlazdic: {len(p['tiles'])} (zkontrolovano {p['n_reviewed']}) | paleta: {len(p['palette'])} ISOM kodu", flush=True)
    print("  Ctrl+C pro ukonceni.", flush=True)
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nUkoncuji.", flush=True)
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
