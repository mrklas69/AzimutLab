#!/usr/bin/env python3
r"""Lokální canvas marker pro ruční značení ISOM bodů ve skenu.

Použití:
  python isom_scan/mark_isoms.py --image "maps/Buschdörfl/bg_scan.png" --codes 311,312,313

Tool ukládá ruční markery do JSON manifestu. Do `.omap` nezapisuje nic; `.omap` export má být až
odvozená kontrolní vrstva.
"""

import argparse
import hashlib
import json
import mimetypes
import re
import tempfile
import time
import unicodedata
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DEFAULT_IMAGE = REPO_ROOT / "maps" / "Buschdörfl" / "bg_scan.png"
DEFAULT_CODES = "311,312,313"
DEFAULT_MARKERS_DIR = HERE / "markers"
DEFAULT_TILE_SIZE = "1200"
DEFAULT_MIN_INK_RATIO = 0.003
# Anglické `name` = SSoT `isom/capabilities.py` (sync ručně, dokud se negeneruje); české `short`
# je lokální popisek pro UI. Audit Sez. 165 (D2/D3): 311/418 se rozcházely s capabilities → sladěno.
CODE_LABELS = {
    "109": {"short": "kupka", "name": "Small knoll"},
    "111": {"short": "prohlubeň", "name": "Small depression"},
    "112": {"short": "jáma", "name": "Pit"},
    "115": {"short": "tvar terénu", "name": "Prominent landform feature"},
    "311": {"short": "studna/fontána/nádrž", "name": "Small fountain or well"},
    "312": {"short": "pramen", "name": "Spring"},
    "313": {"short": "vodní objekt", "name": "Special water feature"},
    "417": {"short": "výrazný strom", "name": "Prominent large tree"},
    "418": {"short": "keř/strom", "name": "Prominent bush or small tree"},
    "525": {"short": "věžička", "name": "Small tower"},
    "527": {"short": "krmelec", "name": "Fodder rack"},
    "531": {"short": "umělý objekt X", "name": "Prominent man-made feature: x"},
    "unknown": {"short": "neznámý", "name": "Unknown symbol"},
}

# Lokální skeny jsou naše pracovní data; PIL limit by tady jen maskoval legitimní velké mapy.
Image.MAX_IMAGE_PIXELS = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slugify(text: str) -> str:
    """Převede název mapy na stabilní ASCII slug pro název marker manifestu."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text).strip("_").lower()
    return slug or "scan"


def _parse_codes(raw: str) -> list[str]:
    """CLI přijímá `311,312,313`; v JSON držíme kódy jako stringy kvůli ISOM aliasům typu 203.2."""
    codes = [part.strip() for part in raw.split(",") if part.strip()]
    if not codes:
        raise ValueError("Musis zadat aspon jeden ISOM kod")
    invalid = [code for code in codes if not re.fullmatch(r"\d{3}(?:\.\d+)?", code)]
    if invalid:
        raise ValueError(f"Neplatne ISOM kody: {', '.join(invalid)}")
    if len(set(codes)) != len(codes):
        raise ValueError("ISOM kody se nesmi opakovat")
    return codes


def _parse_tile_size(raw: str) -> tuple[int, int]:
    """Přijme `1200` nebo `1200x900`; výstup je velikost dlaždice v pixelech skenu."""
    text = raw.lower().replace("×", "x").strip()
    if "x" in text:
        left, right = text.split("x", 1)
    else:
        left = right = text
    try:
        width = int(left)
        height = int(right)
    except ValueError as exc:
        raise ValueError(f"Neplatna velikost dlazdice: {raw!r}") from exc
    if width <= 0 or height <= 0:
        raise ValueError("Velikost dlazdice musi byt kladne cislo")
    return width, height


def _parse_stride(raw: str | None, tile_size: tuple[int, int]) -> tuple[int, int]:
    """Stride je krok mezi dlaždicemi; menší než tile-size znamená překryv."""
    if raw is None:
        return tile_size
    return _parse_tile_size(raw)


def _axis_starts(total: int, window: int, stride: int) -> list[int]:
    """Vygeneruje začátky dlaždic tak, aby poslední dlaždice dosáhla na konec skenu."""
    if total <= window:
        return [0]
    starts: list[int] = []
    value = 0
    while value < total - window:
        starts.append(value)
        value += stride
    starts.append(total - window)
    return sorted(set(starts))


def _make_tiles(image_size: tuple[int, int], tile_size: tuple[int, int],
                stride: tuple[int, int]) -> list[dict[str, int]]:
    """Rozseká sken na stabilní dlaždice v absolutních scan-px souřadnicích."""
    width, height = image_size
    tile_w, tile_h = tile_size
    stride_x, stride_y = stride
    if stride_x <= 0 or stride_y <= 0:
        raise ValueError("Stride musi byt kladne cislo")

    tiles: list[dict[str, int]] = []
    for y in _axis_starts(height, tile_h, stride_y):
        for x in _axis_starts(width, tile_w, stride_x):
            tiles.append({
                "index": len(tiles),
                "x": x,
                "y": y,
                "w": min(tile_w, width - x),
                "h": min(tile_h, height - y),
            })
    return tiles


def _tile_ink_ratio(image: Image.Image, tile: dict[str, int], sample_px: int = 220) -> float:
    """Odhadne, kolik dlaždice obsahuje mapovou kresbu místo prázdného papíru."""
    crop = image.crop((tile["x"], tile["y"], tile["x"] + tile["w"], tile["y"] + tile["h"])).convert("RGB")
    crop.thumbnail((sample_px, sample_px), Image.Resampling.BILINEAR)
    pixels = list(crop.getdata())
    if not pixels:
        return 0.0

    ink = 0
    for r, g, b in pixels:
        # Prázdný okraj skenu je skoro bílý/šedý. Mapa má tmavé linie nebo syté ISOM barvy.
        spread = max(r, g, b) - min(r, g, b)
        if min(r, g, b) < 238 or spread > 18:
            ink += 1
    return ink / len(pixels)


def _filter_empty_tiles(image_path: Path, tiles: list[dict[str, Any]], min_ink_ratio: float) -> list[dict[str, Any]]:
    """Vyřadí dlaždice bez mapové kresby; nechává nízký práh, aby nezmizely bílé lesní části."""
    if min_ink_ratio <= 0:
        return tiles
    with Image.open(image_path) as image:
        kept: list[dict[str, Any]] = []
        for tile in tiles:
            ratio = _tile_ink_ratio(image, tile)
            if ratio < min_ink_ratio:
                continue
            updated = dict(tile)
            updated["ink_ratio"] = round(ratio, 4)
            kept.append(updated)

    for index, tile in enumerate(kept):
        tile["index"] = index
    return kept


def _point_tile(image_size: tuple[int, int], tile_size: tuple[int, int], x: float, y: float) -> dict[str, Any]:
    """Vyrobí dlaždici centrovanou okolo kandidáta; okraje se zarovnají dovnitř skenu."""
    width, height = image_size
    tile_w = min(tile_size[0], width)
    tile_h = min(tile_size[1], height)
    max_x = max(0, width - tile_w)
    max_y = max(0, height - tile_h)
    left = max(0, min(max_x, round(x - tile_w / 2)))
    top = max(0, min(max_y, round(y - tile_h / 2)))
    return {"index": -1, "x": int(left), "y": int(top), "w": int(tile_w), "h": int(tile_h)}


def _make_candidate_tiles(image_size: tuple[int, int], tile_size: tuple[int, int],
                          anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sestaví dlaždice z kandidátů/markerů a sloučí blízké kotvy do stejné dlaždice.

    Tohle je jiný režim než pravidelná mřížka: primárně chceme ukázat místa, kde
    scanner něco vidí nebo kde už existuje ruční marker. Prázdný okraj bez
    kandidáta v tomhle režimu vůbec nevznikne.
    """
    tiles: list[dict[str, Any]] = []
    for anchor in anchors:
        try:
            x = float(anchor["x"])
            y = float(anchor["y"])
        except (KeyError, TypeError, ValueError):
            continue
        current = next(
            (
                tile for tile in tiles
                if tile["x"] <= x <= tile["x"] + tile["w"] and tile["y"] <= y <= tile["y"] + tile["h"]
            ),
            None,
        )
        if current is None:
            current = {**_point_tile(image_size, tile_size, x, y), "candidate_count": 0, "codes": []}
            tiles.append(current)
        current["candidate_count"] = int(current.get("candidate_count", 0)) + 1
        code = str(anchor.get("code", ""))
        if code and code not in current["codes"]:
            current["codes"].append(code)

    tiles.sort(key=lambda tile: (tile["y"], tile["x"]))
    for index, tile in enumerate(tiles):
        tile["index"] = index
        tile["codes"] = sorted(tile.get("codes", []))
    return tiles


def _ensure_tiles_cover_anchors(image_size: tuple[int, int], tiles: list[dict[str, Any]],
                                tile_size: tuple[int, int], anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Doplní dlaždice okolo kandidátů, které by jinak vypadly ink filtrem."""
    out = [dict(tile) for tile in tiles]
    seen = {(tile["x"], tile["y"], tile["w"], tile["h"]) for tile in out}

    for anchor in anchors:
        try:
            x = float(anchor["x"])
            y = float(anchor["y"])
        except (KeyError, TypeError, ValueError):
            continue
        if any(tile["x"] <= x <= tile["x"] + tile["w"] and tile["y"] <= y <= tile["y"] + tile["h"] for tile in out):
            continue
        tile = _point_tile(image_size, tile_size, x, y)
        key = (tile["x"], tile["y"], tile["w"], tile["h"])
        if key in seen:
            continue
        tile["candidate_count"] = 1
        tile["codes"] = [str(anchor.get("code", ""))]
        tile["forced_by_candidate"] = True
        out.append(tile)
        seen.add(key)

    out.sort(key=lambda tile: (tile["y"], tile["x"]))
    for index, tile in enumerate(out):
        tile["index"] = index
    return out


def _normalize_tile(raw: Any, image_size: tuple[int, int]) -> dict[str, int] | None:
    """Volitelná stopa, ze které dlaždice marker vznikl; marker drží absolutní x/y."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("Marker tile metadata musi byt objekt")
    try:
        tile = {
            "index": int(raw.get("index", -1)),
            "x": int(raw["x"]),
            "y": int(raw["y"]),
            "w": int(raw["w"]),
            "h": int(raw["h"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Marker tile metadata ma neplatny tvar") from exc

    width, height = image_size
    if tile["w"] <= 0 or tile["h"] <= 0:
        raise ValueError("Marker tile metadata ma nulovou velikost")
    if tile["x"] < 0 or tile["y"] < 0 or tile["x"] + tile["w"] > width or tile["y"] + tile["h"] > height:
        raise ValueError("Marker tile metadata je mimo sken")
    return tile


def _resolve_image(raw: Path) -> Path:
    """Najde vstupní sken absolutně nebo relativně vůči repo rootu."""
    candidates = [raw]
    if not raw.is_absolute():
        candidates.append(REPO_ROOT / raw)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"Chybi vstupni sken: {raw}")


def _default_markers_path(image_path: Path, codes: list[str], markers_dir: Path) -> Path:
    """Výchozí manifest pojmenuje podle složky mapy, ne podle obecného `bg_scan.png`."""
    image_stem = image_path.stem
    map_name = image_path.parent.name if image_stem in {"bg_scan", "rgb", "source_livelox"} else image_stem
    code_part = "_".join(codes)
    return markers_dir / f"{_slugify(map_name)}_{code_part}.json"


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _marker_id(code: str, x: float, y: float) -> str:
    return f"{code}_x{round(x)}_y{round(y)}"


def _normalize_marker(raw: dict[str, Any], codes: list[str], image_size: tuple[int, int]) -> dict[str, Any]:
    """Zvaliduje jeden marker z browseru a vrátí kanonický JSON tvar."""
    code = str(raw.get("code", "")).strip()
    if code not in {*codes, "unknown"}:
        raise ValueError(f"Marker ma nepovoleny kod {code!r}")

    try:
        x = float(raw["x"])
        y = float(raw["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Marker musi mit ciselne x/y") from exc

    width, height = image_size
    if not (0 <= x <= width and 0 <= y <= height):
        raise ValueError(f"Marker {code} mimo sken: x={x}, y={y}, size={width}x{height}")

    note = str(raw.get("note", "")).strip()
    marker = {
        "id": str(raw.get("id") or _marker_id(code, x, y)),
        "code": code,
        "x": round(x, 1),
        "y": round(y, 1),
        "note": note,
    }
    tile = _normalize_tile(raw.get("tile"), image_size)
    if tile is not None:
        marker["tile"] = tile
    source = raw.get("source")
    if isinstance(source, dict):
        marker["source"] = {
            "type": str(source.get("type", "")),
            "id": str(source.get("id", "")),
            "path": str(source.get("path", "")),
            "score": source.get("score"),
            "angle_deg": source.get("angle_deg"),
        }
    return marker


def _same_image_path(left: str, image_path: Path) -> bool:
    """Porovná cestu v detekčním JSONu vůči aktuálnímu skenu bez závislosti na slashích."""
    normalized = left.replace("\\", "/")
    candidates = {
        image_path.as_posix(),
        image_path.resolve().as_posix(),
        image_path.relative_to(REPO_ROOT).as_posix() if image_path.is_relative_to(REPO_ROOT) else image_path.as_posix(),
    }
    return normalized in candidates


def _load_detection_suggestions(paths: list[Path], codes: list[str], image_path: Path) -> list[dict[str, Any]]:
    """Načte scanner návrhy z `detections.json`; zůstávají návrhy, ne uložené markery."""
    suggestions: list[dict[str, Any]] = []
    allowed = set(codes)
    seen: set[tuple[str, int, int, str]] = set()
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"Detekce nejde nacist: {path}: {exc}") from exc
        image_ref = str(payload.get("image", ""))
        if image_ref and not _same_image_path(image_ref, image_path):
            continue
        for group in payload.get("detections", []):
            if not isinstance(group, dict):
                continue
            code = str(group.get("code", ""))
            if code not in allowed:
                continue
            name = str(group.get("name", CODE_LABELS.get(code, {}).get("name", "")))
            for point in group.get("points", []):
                if not isinstance(point, dict):
                    continue
                try:
                    x = float(point["x"])
                    y = float(point["y"])
                except (KeyError, TypeError, ValueError):
                    continue
                key = (code, round(x), round(y), str(path))
                if key in seen:
                    continue
                seen.add(key)
                suggestions.append({
                    "id": f"{path.as_posix()}:{code}:{round(x)}:{round(y)}",
                    "code": code,
                    "name": name,
                    "x": round(x, 1),
                    "y": round(y, 1),
                    "score": point.get("score"),
                    "angle_deg": point.get("angle_deg"),
                    "bbox": point.get("bbox"),
                    "path": path.as_posix(),
                })
    return suggestions


def _discover_detection_paths(image_path: Path) -> list[Path]:
    """Najde existující scanner výstupy pro stejný sken v `temp/**/detections.json`."""
    temp_dir = REPO_ROOT / "temp"
    if not temp_dir.exists():
        return []
    paths: list[Path] = []
    for path in temp_dir.rglob("detections.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        image_ref = str(payload.get("image", ""))
        if image_ref and _same_image_path(image_ref, image_path):
            paths.append(path)
    return paths


def _manifest(image_path: Path, image_size: tuple[int, int], codes: list[str],
              markers: list[dict[str, Any]], *, title: str,
              tiles: list[dict[str, Any]] | None = None,
              status: str = "MARKER_DRAFT") -> dict[str, Any]:
    """Sestaví durable marker manifest; JSON je zdroj pravdy pro další metriky."""
    summary_codes = list(codes)
    if any(marker["code"] == "unknown" for marker in markers):
        summary_codes.append("unknown")
    return {
        "_status": status,
        "_doc": "Rucni point markery ve scan px souradnicich; zdroj pravdy pro kalibraci, ne .omap overlay.",
        "schema_version": 1,
        "updated": _now_iso(),
        "title": title,
        "image": str(image_path),
        "image_sha256": _sha256(image_path),
        "image_size": {"w": image_size[0], "h": image_size[1]},
        "codes": codes,
        "tiles": {
            "enabled": bool(tiles),
            "count": len(tiles or []),
        },
        "markers": markers,
        "summary": {
            "total": len(markers),
            "by_code": {code: sum(1 for marker in markers if marker["code"] == code) for code in summary_codes},
        },
    }


def _load_existing_markers(path: Path, codes: list[str], image_size: tuple[int, int]) -> list[dict[str, Any]]:
    """Načte existující manifest; rozbitý JSON selže nahlas, aby se neztrácela ruční práce."""
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Marker manifest nejde nacist: {path}: {exc}") from exc
    raw_markers = payload.get("markers", [])
    if not isinstance(raw_markers, list):
        raise SystemExit(f"Marker manifest nema seznam `markers`: {path}")
    return [_normalize_marker(marker, codes, image_size) for marker in raw_markers]


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


class MarkerState:
    """Sdílený stav serveru; malý objekt drží konfiguraci a cestu pro save endpoint."""

    def __init__(self, image_path: Path, codes: list[str], markers_path: Path, title: str,
                 tiles: list[dict[str, Any]] | None = None,
                 suggestions: list[dict[str, Any]] | None = None):
        self.image_path = image_path
        self.codes = codes
        self.markers_path = markers_path
        self.title = title
        self.image_size = _image_size(image_path)
        self.tiles = tiles or []
        self.suggestions = suggestions or []
        self.markers = _load_existing_markers(markers_path, codes, self.image_size)
        self.status = "MARKER_DRAFT"
        if markers_path.exists():
            try:
                payload = json.loads(markers_path.read_text(encoding="utf-8"))
                self.status = str(payload.get("_status") or self.status)
            except json.JSONDecodeError:
                self.status = "MARKER_DRAFT"

    def config(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "codes": self.codes,
            "image": "/image",
            "image_size": {"w": self.image_size[0], "h": self.image_size[1]},
            "markers_path": str(self.markers_path),
            "markers": self.markers,
            "tiles": self.tiles,
            "suggestions": self.suggestions,
            "status": self.status,
            "ui_codes": [*self.codes, "unknown"],
            "code_labels": {code: CODE_LABELS.get(code, {"short": "", "name": ""}) for code in [*self.codes, "unknown"]},
        }

    def save(self, raw_markers: Any, *, status: str | None = None) -> dict[str, Any]:
        if not isinstance(raw_markers, list):
            raise ValueError("POST payload musi obsahovat seznam `markers`")
        if status is not None:
            self.status = status
        self.markers = [_normalize_marker(marker, self.codes, self.image_size) for marker in raw_markers]
        payload = _manifest(
            self.image_path,
            self.image_size,
            self.codes,
            self.markers,
            title=self.title,
            tiles=self.tiles,
            status=self.status,
        )
        _atomic_write_json(self.markers_path, payload)
        return payload


APP_HTML = (Path(__file__).resolve().parent / "mark_isoms.html").read_text(encoding="utf-8")


class MarkerHandler(BaseHTTPRequestHandler):
    server_version = "AzimutMarker/1.0"

    @property
    def state(self) -> MarkerState:
        return self.server.marker_state  # type: ignore[attr-defined]

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            data = APP_HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/config":
            self._send_json(self.state.config())
            return
        if path == "/api/markers":
            payload = _manifest(
                self.state.image_path,
                self.state.image_size,
                self.state.codes,
                self.state.markers,
                title=self.state.title,
                tiles=self.state.tiles,
                status=self.state.status,
            )
            self._send_json(payload)
            return
        if path == "/image":
            content = self.state.image_path.read_bytes()
            mime = mimetypes.guess_type(self.state.image_path.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        self._send_text("Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in {"/api/markers", "/api/finish"}:
            self._send_text("Not found", HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            status = "MARKER_DONE" if path == "/api/finish" else None
            saved = self.state.save(payload.get("markers"), status=status)
        except (json.JSONDecodeError, ValueError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json(saved)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def _make_server(host: str, port: int, state: MarkerState) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), MarkerHandler)
    server.marker_state = state  # type: ignore[attr-defined]
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--codes", default=DEFAULT_CODES)
    parser.add_argument("--markers", type=Path, default=None,
                        help="Cesta k JSON marker manifestu. Default: isom_scan/markers/<map>_<codes>.json")
    parser.add_argument("--markers-dir", type=Path, default=DEFAULT_MARKERS_DIR)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--tile-size", default=None,
                        help=f"Zapni dlazdicovy rezim; napr. {DEFAULT_TILE_SIZE} nebo 1200x900.")
    parser.add_argument("--stride", default=None,
                        help="Krok mezi dlazdicemi. Default = tile-size; mensi hodnota da prekryv.")
    parser.add_argument("--min-ink-ratio", type=float, default=DEFAULT_MIN_INK_RATIO,
                        help="Minimalni podil ne-papirových px v dlazdici; prazdne okraje se preskoci.")
    parser.add_argument("--include-empty-tiles", action="store_true",
                        help="V dlazdicovem rezimu nabizej i prazdne okraje skenu.")
    parser.add_argument("--candidate-tiles", action="store_true",
                        help="V dlazdicovem rezimu nabizej jen dlazdice okolo scanner navrhu a existujicich markeru.")
    parser.add_argument("--detections", type=Path, action="append", default=[],
                        help="Cesta k detections.json se scanner navrhy. Lze zadat vicekrat.")
    parser.add_argument("--no-auto-detections", action="store_true",
                        help="Nevyhledavej automaticky temp/**/detections.json pro stejny sken.")
    parser.add_argument("--open", action="store_true", help="Otevri default browser.")
    args = parser.parse_args(argv)

    try:
        codes = _parse_codes(args.codes)
        image_path = _resolve_image(args.image)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from exc

    markers_path = args.markers or _default_markers_path(image_path, codes, args.markers_dir)
    title = f"{image_path.parent.name} · {'/'.join(codes)}"
    image_size = _image_size(image_path)
    detection_paths = list(args.detections)
    if not args.no_auto_detections:
        detection_paths.extend(path for path in _discover_detection_paths(image_path) if path not in detection_paths)
    suggestions = _load_detection_suggestions(detection_paths, codes, image_path)
    existing_markers = _load_existing_markers(markers_path, codes, image_size)

    tiles = None
    if args.tile_size:
        try:
            tile_size = _parse_tile_size(args.tile_size)
            anchors = [*suggestions, *existing_markers]
            if args.candidate_tiles and anchors:
                tiles = _make_candidate_tiles(image_size, tile_size, anchors)
            else:
                stride = _parse_stride(args.stride, tile_size)
                tiles = _make_tiles(image_size, tile_size, stride)
                if not args.include_empty_tiles:
                    tiles = _filter_empty_tiles(image_path, tiles, args.min_ink_ratio)
                if anchors:
                    tiles = _ensure_tiles_cover_anchors(image_size, tiles, tile_size, anchors)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        tile_mode = "candidate tiles" if args.candidate_tiles else "tiles"
        title = f"{title} · {tile_mode} {args.tile_size}"

    state = MarkerState(image_path, codes, markers_path, title, tiles=tiles, suggestions=suggestions)
    server = _make_server(args.host, args.port, state)
    url = f"http://{server.server_address[0]}:{server.server_address[1]}/"
    print(f"ISOM marker: {url}")
    print(f"image: {image_path}")
    print(f"markers: {markers_path}")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nUkonceno.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
