#!/usr/bin/env python3
"""Lokální kurační UI pro scan-transfer ISOM kandidáty (human-in-the-loop).

Otevře v prohlížeči `review_manifest.json` (vyrobený `*_review.py`), ukáže každý
kandidát jako výřez skenu a nechá kurátora rychle KLÁVESAMI rozhodnout verdikt
(tp/fp/ignore), případně opravit ISOM kód, a po dokončení zapsat shrnutí
(`false_positive_count`, precision) do `calibration_manifest.json`. Tím se uzavírá
governance smyčka, kterou supervizní audit (A2/A4) vyžadoval: "kalibrace = změřený
recall/FP", ne null-ledger.

Záměrně KISS: jen Python **stdlib** `http.server` + jeden statický HTML soubor.
Žádný framework, žádný build, žádná nová závislost (Pillow už projekt má). Lokální,
jeden uživatel:

    .venv\\Scripts\\python.exe isom_scan/review_ui.py \\
        --manifest temp/manmade_points_buschdorfl/review/review_manifest.json

Skript se pokusí otevřít http://127.0.0.1:8765 sám. Sken i `temp/` jsou gitignored
(copyright) — UI je čte jen lokálně; verzovatelné jsou jen tenhle skript + HTML.
"""

import argparse
import io
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
HTML_PATH = HERE / "review_ui.html"
CALIBRATION_PATH = HERE / "calibration_manifest.json"

# Mapové skeny jsou velké, ale jsou to naše vstupy (ne nedůvěryhodný upload).
Image.MAX_IMAGE_PIXELS = None

# Povolené verdikty (zrcadlí REVIEW_VALUES v manmade_points_review.py = jeden zdroj pravdy konvence).
REVIEW_VALUES = ("unreviewed", "tp", "fp", "ignore")

# Základní velikost výřezu v px skenu, než se přizpůsobí bboxu kandidáta (jako _review.py).
BASE_CROP_PX = 180
# Výstupní crop nikdy nepošleme větší než tohle (zoom-out na velký kontext jinak nafoukne PNG).
MAX_CROP_OUT_PX = 1100


# ----------------------------------------------------------------------- ISOM kódy
def _load_isom_codes() -> dict:
    """{kód: název} z ISOM SVG katalogu pro našeptávač `true_code`.

    Best-effort: katalog `resources/isom/` je gitignored, na jiném stroji nemusí být.
    Když chybí, vrátíme {} a NAHLAS varujeme (no-silent-fallback) — UI pak nabídne
    jen kódy z aktuálního manifestu. Nikdy kvůli tomu nespadneme."""
    try:
        # isom je sys.path balík v kořeni repa (ne nainstalovaný) → přidáme kořen.
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from isom.symbol_index import load_symbol_index

        index = load_symbol_index()  # strict=False → discovery ze SVG, když chybí index.json
        return {rec.code: rec.display_name for rec in index.records}
    except Exception as exc:  # FileNotFoundError / SymbolIndexError / ImportError …
        print(f"[varovani] ISOM katalog nedostupny ({exc}); naseptavac bude jen z manifestu",
              flush=True)
        return {}


# ----------------------------------------------------------------------- crop geometrie
def _crop_box(center: dict, bbox: list, base_px: int) -> tuple:
    """Výřez centrovaný na kandidátovi; bbox se vejde i s okolím (kopie _review._crop_box).

    Vrací (left, top, right, bottom) v px skenu."""
    cx = float(center["x"])
    cy = float(center["y"])
    if bbox and len(bbox) == 4:
        w = float(bbox[2]) - float(bbox[0])
        h = float(bbox[3]) - float(bbox[1])
        half = max(base_px / 2.0, max(w, h) * 2.0)
    else:
        half = base_px / 2.0
    return (cx - half, cy - half, cx + half, cy + half)


# ----------------------------------------------------------------------- stav serveru
class ReviewState:
    """Drží načtený sken + manifest v paměti a serializuje zápisy zámkem.

    Jeden uživatel, ale POST verdict dělá read-modify-write souboru → zámek chrání
    před souběhem (ThreadingHTTPServer obsluhuje requesty ve více vláknech)."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path.resolve()
        self.lock = threading.Lock()
        self.isom_codes = _load_isom_codes()
        self._load_manifest()
        self.image = Image.open(self._resolve_image_path()).convert("RGB")

    # --- načtení / zápis manifestu ---
    def _load_manifest(self) -> None:
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        # index kandidátů podle stabilního id → rychlý lookup při verdiktu/cropu
        self.by_id = {str(c["id"]): c for c in self.manifest.get("candidates", [])}

    def _flush_manifest(self) -> None:
        # přepočítej souhrn, ať je v souboru konzistentní s verdikty
        self.manifest["review_summary"] = self._summary(self.manifest.get("candidates", []))
        self.manifest_path.write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _resolve_image_path(self) -> Path:
        """Najde sken z manifest.image; absolutní cesta z jiného stroje → zkus i relativně k repu."""
        raw = Path(str(self.manifest.get("image", "")))
        for candidate in (raw, REPO_ROOT / raw):
            if candidate.exists():
                return candidate.resolve()
        raise SystemExit(f"Chybi sken pro review UI: {raw}")  # no-silent: radši spadni nahlas

    @staticmethod
    def _summary(candidates: list) -> dict:
        counts = {value: 0 for value in REVIEW_VALUES}
        for cand in candidates:
            verdict = str(cand.get("review", {}).get("verdict", "unreviewed"))
            counts[verdict] = counts.get(verdict, 0) + 1
        return {"total": len(candidates), **counts}

    # --- data pro frontend ---
    def manifest_payload(self) -> dict:
        cands = []
        for cand in self.manifest.get("candidates", []):
            review = cand.get("review", {})
            cands.append({
                "id": str(cand["id"]),
                "pred_code": str(cand.get("pred_code", "")),
                "pred_name": str(cand.get("pred_name", "")),
                "score": cand.get("score"),
                "verdict": str(review.get("verdict", "unreviewed")),
                "true_code": review.get("true_code"),
                "note": review.get("note", ""),
            })
        return {
            "manifest_path": str(self.manifest_path),
            "image": str(self.manifest.get("image", "")),
            "codes": self.manifest.get("codes", []),
            "review_values": list(REVIEW_VALUES),
            "review_summary": self._summary(self.manifest.get("candidates", [])),
            "isom_codes": self.isom_codes,
            "candidates": cands,
        }

    # --- crop výřez ---
    def render_crop(self, cid: str) -> bytes | None:
        cand = self.by_id.get(cid)
        if cand is None:
            return None
        box = _crop_box(cand["center"], cand.get("bbox") or [], BASE_CROP_PX)
        left, top, right, bottom = (int(round(v)) for v in box)
        # ořízni na hranice obrázku (kandidát u kraje skenu)
        left = max(0, left); top = max(0, top)
        right = min(self.image.width, right); bottom = min(self.image.height, bottom)
        crop = self.image.crop((left, top, right, bottom)).convert("RGB")

        draw = ImageDraw.Draw(crop)
        # Kandidáta obkroužíme PRÁZDNOU kružnicí — střed zůstane volný, ať nezakrývá
        # pixely symbolu, podle kterých kurátor rozhoduje (kříž+obdélník je překrývaly,
        # nález uživatele). Poloměr z bboxu + rezerva, ať kružnice objekt obkrouží, ne přetne.
        cx = float(cand["center"]["x"]) - left
        cy = float(cand["center"]["y"]) - top
        bbox = cand.get("bbox") or []
        if len(bbox) == 4:
            w = float(bbox[2]) - float(bbox[0])
            h = float(bbox[3]) - float(bbox[1])
            radius = max(w, h) / 2.0 + 6.0
        else:
            radius = 14.0
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                     outline=(255, 0, 255), width=2)

        # zmenši, ať velký zoom-out nepošle obří PNG
        if max(crop.width, crop.height) > MAX_CROP_OUT_PX:
            crop.thumbnail((MAX_CROP_OUT_PX, MAX_CROP_OUT_PX), Image.Resampling.BILINEAR)

        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        return buf.getvalue()

    # --- zápis verdiktu ---
    def set_verdict(self, body: dict) -> dict:
        cid = str(body.get("id", ""))
        verdict = str(body.get("verdict", "unreviewed"))
        if verdict not in REVIEW_VALUES:
            return {"ok": False, "error": f"neplatny verdikt {verdict!r}"}
        with self.lock:
            cand = self.by_id.get(cid)
            if cand is None:
                return {"ok": False, "error": f"neznamy kandidat {cid!r}"}
            review = cand.setdefault("review", {})
            review["verdict"] = verdict
            # true_code: prázdné/None = predikce sedí (necháme null, jak chce _doc manifestu)
            true_code = body.get("true_code")
            review["true_code"] = str(true_code) if true_code else None
            if "note" in body:
                review["note"] = str(body.get("note", ""))
            self._flush_manifest()
            return {"ok": True, "review_summary": self.manifest["review_summary"]}

    # --- zápis do calibration_manifest (auto-recall/FP) ---
    def calibrate(self) -> dict:
        """Per pred_code dopočítá FP/summary z verdiktů a zapíše do calibration_manifest.json.

        marker_recall NEPOČÍTÁME, dokud entry nemá pozitivní markery se souřadnicemi —
        recall potřebuje GT (co detektor minul), ne jen verdikty kandidátů. Bez markerů
        necháme null + poznámku (no-silent: žádná falešná nula, audit A2)."""
        with self.lock:
            if not CALIBRATION_PATH.exists():
                return {"ok": False, "error": f"chybi {CALIBRATION_PATH}"}
            calib = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))

            # náš manifest relativně k repu (posix) — tak ho drží calibration entries
            try:
                our_rel = self.manifest_path.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                our_rel = self.manifest_path.as_posix()

            # verdikty seskupené podle predikovaného kódu
            per_code: dict[str, dict] = {}
            for cand in self.manifest.get("candidates", []):
                code = str(cand.get("pred_code", ""))
                verdict = str(cand.get("review", {}).get("verdict", "unreviewed"))
                bucket = per_code.setdefault(code, {v: 0 for v in REVIEW_VALUES})
                bucket[verdict] = bucket.get(verdict, 0) + 1

            updated = []
            for entry in calib.get("entries", []):
                entry_ref = str(entry.get("detector", {}).get("review_manifest", ""))
                if entry_ref.replace("\\", "/") != our_rel:
                    continue
                code = str(entry.get("code", ""))
                counts = per_code.get(code)
                if counts is None:
                    continue
                total = sum(counts.values())
                metrics = entry.setdefault("metrics", {})
                metrics["review_summary"] = {"total": total, **counts}
                metrics["false_positive_count"] = counts["fp"]
                has_markers = int(entry.get("positive_marker_count", 0) or 0) > 0
                if not has_markers:
                    metrics["marker_recall"] = None
                    entry.setdefault("review", {})["note"] = (
                        "Verdikty kurovany v review_ui; marker_recall=null = chybi pozitivni "
                        "602 markery (recall potrebuje GT, ne jen verdikty kandidatu)."
                    )
                reviewed = total - counts["unreviewed"]
                if reviewed == total and total > 0:
                    entry["status"] = "reviewed_no_markers" if not has_markers else "calibrated"
                updated.append({"code": code, "summary": metrics["review_summary"],
                                 "false_positive_count": counts["fp"]})

            if not updated:
                return {"ok": False,
                        "error": f"v calibration_manifest neni entry s review_manifest={our_rel}"}
            CALIBRATION_PATH.write_text(
                json.dumps(calib, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return {"ok": True, "updated": updated}


# ----------------------------------------------------------------------- HTTP handler
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send_bytes(HTML_PATH.read_bytes(), "text/html; charset=utf-8")
        elif parsed.path == "/api/manifest":
            self._send_json(self.server.state.manifest_payload())
        elif parsed.path == "/api/crop":
            qs = parse_qs(parsed.query)
            cid = qs.get("id", [""])[0]
            png = self.server.state.render_crop(cid)
            if png is None:
                self.send_error(404, "neznamy kandidat")
                return
            self._send_bytes(png, "image/png")
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_error(400, "neplatny JSON")
            return
        if parsed.path == "/api/verdict":
            self._send_json(self.server.state.set_verdict(body))
        elif parsed.path == "/api/calibrate":
            self._send_json(self.server.state.calibrate())
        else:
            self.send_error(404)

    # --- pomocné odpovědi ---
    def _send_bytes(self, data: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")  # crop se mění se zoomem
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict):
        self._send_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                         "application/json; charset=utf-8")

    def log_message(self, *args):
        pass  # tichý access log; chyby stejně jdou přes send_error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True,
                        help="Cesta k review_manifest.json (z *_review.py).")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true",
                        help="Neotvírej prohlížeč automaticky.")
    args = parser.parse_args()

    # Windows konzole je default cp1250 → diakritika v cestách/výpisech jinak spadne.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if not args.manifest.exists():
        raise SystemExit(f"Chybi manifest: {args.manifest}")
    if not HTML_PATH.exists():
        raise SystemExit(f"Chybi frontend: {HTML_PATH}")

    state = ReviewState(args.manifest)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.state = state  # handler čte stav přes self.server.state

    url = f"http://127.0.0.1:{args.port}"
    summary = state.manifest_payload()["review_summary"]
    print(f"Review UI bezi na {url}", flush=True)
    print(f"  manifest: {args.manifest}", flush=True)
    print(f"  kandidatu: {summary['total']} (unreviewed {summary['unreviewed']})", flush=True)
    print("  Ctrl+C pro ukonceni.", flush=True)
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass  # headless / žádný prohlížeč → nevadí, URL je vypsaná
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nUkoncuji.", flush=True)
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
