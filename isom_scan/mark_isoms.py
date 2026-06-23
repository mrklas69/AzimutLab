#!/usr/bin/env python3
r"""Lokální canvas marker pro ruční značení ISOM bodů ve skenu.

Použití:
  python isom_scan/mark_isoms.py --image "maps/Buschdörfl/bg_scan.png" --codes 311,312,313

Tool ukládá ruční markery do JSON manifestu. Do `.omap` nezapisuje nic; `.omap` export má být až
odvozená kontrolní vrstva.
"""

from __future__ import annotations

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
CODE_LABELS = {
    "109": {"short": "kupka", "name": "Small knoll"},
    "111": {"short": "prohlubeň", "name": "Small depression"},
    "112": {"short": "jáma", "name": "Pit"},
    "115": {"short": "tvar terénu", "name": "Prominent landform feature"},
    "311": {"short": "studna/fontána/nádrž", "name": "Well / fountain / water tank"},
    "312": {"short": "pramen", "name": "Spring"},
    "313": {"short": "vodní objekt", "name": "Special water feature"},
    "417": {"short": "výrazný strom", "name": "Prominent large tree"},
    "418": {"short": "keř/strom", "name": "Prominent bush or tree"},
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


APP_HTML = r"""<!doctype html>
<html lang="cs">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ISOM marker</title>
  <style>
    :root {
      --ink: #151515;
      --paper: #f7f7f3;
      --panel: #ffffff;
      --line: #d8d8ce;
      --muted: #64645d;
      --blue: #0a6ebd;
      --green: #248a5b;
      --red: #c73b3b;
      --focus: #111111;
      font-family: "Segoe UI", system-ui, sans-serif;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; height: 100%; background: var(--paper); color: var(--ink); overflow: hidden; }
    body { display: grid; grid-template-rows: auto auto 1fr; }
    header {
      display: grid;
      grid-template-columns: minmax(160px, 1fr) auto auto;
      align-items: center;
      gap: 14px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      background: #fbfbf8;
    }
    h1 { margin: 0; font-size: 15px; font-weight: 650; letter-spacing: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .codes, .actions { display: flex; align-items: center; gap: 6px; }
    .tilebar {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 7px 12px;
      border-bottom: 1px solid var(--line);
      background: #f0f0e8;
      font-size: 13px;
    }
    .tilebar span { color: var(--muted); }
    button {
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      min-height: 34px;
      padding: 0 11px;
      font: inherit;
      font-size: 13px;
      border-radius: 6px;
      cursor: pointer;
    }
    button:hover { border-color: #a9a99f; }
    button:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
    button.active { color: #fff; background: var(--ink); border-color: var(--ink); }
    button.primary { color: #fff; background: var(--blue); border-color: var(--blue); }
    button.danger { color: #fff; background: var(--red); border-color: var(--red); }
    button.suggest { color: #fff; background: var(--green); border-color: var(--green); }
    .code-label { color: var(--muted); font-size: 12px; margin-left: 4px; }
    .status { min-width: 130px; text-align: right; font-size: 12px; color: var(--muted); }
    main { min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr) 300px; }
    #viewport { position: relative; min-width: 0; min-height: 0; background: #e8e8df; }
    canvas { display: block; width: 100%; height: 100%; cursor: crosshair; }
    aside {
      min-width: 0;
      border-left: 1px solid var(--line);
      background: var(--panel);
      display: grid;
      grid-template-rows: auto 1fr auto;
      min-height: 0;
    }
    .stats { padding: 12px; display: grid; gap: 8px; border-bottom: 1px solid var(--line); }
    .stat-row { display: flex; justify-content: space-between; gap: 10px; font-size: 13px; }
    .stat-row span:first-child { color: var(--muted); }
    #list { min-height: 0; overflow: auto; padding: 8px; }
    .marker-row {
      display: grid;
      grid-template-columns: 50px 1fr 28px;
      align-items: center;
      gap: 8px;
      padding: 7px 6px;
      border-bottom: 1px solid #eeeeea;
      font-size: 13px;
    }
    .marker-row button { min-height: 28px; padding: 0; }
    .code-chip {
      width: fit-content;
      min-width: 42px;
      padding: 3px 7px;
      border-radius: 999px;
      color: #fff;
      text-align: center;
      font-weight: 650;
    }
    .coords { color: var(--muted); font-variant-numeric: tabular-nums; }
    .footer { padding: 10px 12px; border-top: 1px solid var(--line); font-size: 12px; color: var(--muted); overflow-wrap: anywhere; }
    @media (max-width: 900px) {
      header { grid-template-columns: 1fr; align-items: stretch; }
      .status { text-align: left; }
      main { grid-template-columns: 1fr; grid-template-rows: minmax(0, 1fr) 180px; }
      aside { border-left: 0; border-top: 1px solid var(--line); }
    }
  </style>
</head>
<body>
  <header>
    <h1 id="title">ISOM marker</h1>
    <div class="codes" id="codes"></div>
    <div class="actions">
      <button id="fit" title="Vrátí zoom a posun tak, aby byla vidět celá aktuální dlaždice.">Fit tile</button>
      <button id="undo">Undo</button>
      <button id="save" class="primary">Save</button>
      <span class="status" id="status">Loading</span>
    </div>
  </header>
  <div class="tilebar" id="tilebar" hidden>
    <button id="prevTile">Prev</button>
    <button id="nextTile">Next</button>
    <button id="acceptTile" class="suggest">Accept suggestions</button>
    <button id="finishSet" class="primary">Finish set</button>
    <span id="tileLabel">Tile</span>
  </div>
  <main>
    <section id="viewport"><canvas id="canvas"></canvas></section>
    <aside>
      <div class="stats" id="stats"></div>
      <div id="list"></div>
      <div class="footer" id="path"></div>
    </aside>
  </main>
  <script>
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    const viewport = document.getElementById('viewport');
    const state = {
      image: new Image(),
      codes: [],
      activeCode: '',
      markers: [],
      suggestions: [],
      codeLabels: {},
      status: 'MARKER_DRAFT',
      tiles: [],
      tileIndex: 0,
      scale: 1,
      offsetX: 0,
      offsetY: 0,
      dragging: false,
      dragStart: null,
      dirty: false,
      palette: ['#0a6ebd', '#c73b3b', '#248a5b', '#7a4cc2', '#b06b00', '#007c89']
    };

    function setStatus(text) { document.getElementById('status').textContent = text; }
    function colorFor(code) {
      const i = Math.max(0, state.codes.indexOf(code));
      return state.palette[i % state.palette.length];
    }
    function labelFor(code) {
      const label = state.codeLabels[code] || {};
      return label.short || label.name || '';
    }
    function markerSourceId(marker) {
      return marker.source && marker.source.type === 'scanner_suggestion' ? marker.source.id : '';
    }
    function suggestionAccepted(suggestion) {
      return state.markers.some(marker => markerSourceId(marker) === suggestion.id);
    }
    function currentTile() {
      return state.tiles.length ? state.tiles[state.tileIndex] : null;
    }
    function markerInTile(marker, tile = currentTile()) {
      if (!tile) return true;
      return marker.x >= tile.x && marker.y >= tile.y && marker.x <= tile.x + tile.w && marker.y <= tile.y + tile.h;
    }
    function suggestionInTile(suggestion, tile = currentTile()) {
      if (!tile) return true;
      return suggestion.x >= tile.x && suggestion.y >= tile.y && suggestion.x <= tile.x + tile.w && suggestion.y <= tile.y + tile.h;
    }
    function resizeCanvas() {
      const rect = viewport.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw();
    }
    function fitImage() {
      const rect = viewport.getBoundingClientRect();
      const tile = currentTile();
      const targetW = tile ? tile.w : state.image.naturalWidth;
      const targetH = tile ? tile.h : state.image.naturalHeight;
      const sx = rect.width / targetW;
      const sy = rect.height / targetH;
      state.scale = Math.min(sx, sy) * 0.96;
      state.offsetX = (rect.width - targetW * state.scale) / 2;
      state.offsetY = (rect.height - targetH * state.scale) / 2;
      draw();
    }
    function screenToImage(x, y) {
      const tile = currentTile();
      return {
        x: (tile ? tile.x : 0) + (x - state.offsetX) / state.scale,
        y: (tile ? tile.y : 0) + (y - state.offsetY) / state.scale
      };
    }
    function imageToScreen(x, y) {
      const tile = currentTile();
      return {
        x: state.offsetX + (x - (tile ? tile.x : 0)) * state.scale,
        y: state.offsetY + (y - (tile ? tile.y : 0)) * state.scale
      };
    }
    function drawMarker(marker, index) {
      const p = imageToScreen(marker.x, marker.y);
      const color = colorFor(marker.code);
      ctx.save();
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#ffffff';
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.strokeStyle = '#111111';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(p.x - 12, p.y);
      ctx.lineTo(p.x + 12, p.y);
      ctx.moveTo(p.x, p.y - 12);
      ctx.lineTo(p.x, p.y + 12);
      ctx.stroke();
      ctx.font = '12px Segoe UI, sans-serif';
      ctx.textBaseline = 'bottom';
      ctx.lineWidth = 4;
      ctx.strokeStyle = '#ffffff';
      ctx.strokeText(`${marker.code}.${index + 1}`, p.x + 11, p.y - 9);
      ctx.fillStyle = '#111111';
      ctx.fillText(`${marker.code}.${index + 1}`, p.x + 11, p.y - 9);
      ctx.restore();
    }
    function drawSuggestion(suggestion) {
      if (suggestionAccepted(suggestion)) return;
      const p = imageToScreen(suggestion.x, suggestion.y);
      const color = colorFor(suggestion.code);
      ctx.save();
      ctx.setLineDash([5, 4]);
      ctx.lineWidth = 3;
      ctx.strokeStyle = color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 11, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.lineWidth = 1;
      ctx.strokeStyle = '#ffffff';
      ctx.strokeText(`${suggestion.code}?`, p.x + 12, p.y - 10);
      ctx.fillStyle = '#111111';
      ctx.fillText(`${suggestion.code}?`, p.x + 12, p.y - 10);
      ctx.restore();
    }
    function draw() {
      const rect = viewport.getBoundingClientRect();
      ctx.clearRect(0, 0, rect.width, rect.height);
      if (!state.image.complete) return;
      ctx.imageSmoothingEnabled = true;
      const tile = currentTile();
      if (tile) {
        ctx.drawImage(
          state.image,
          tile.x,
          tile.y,
          tile.w,
          tile.h,
          state.offsetX,
          state.offsetY,
          tile.w * state.scale,
          tile.h * state.scale
        );
      } else {
        ctx.drawImage(
          state.image,
          state.offsetX,
          state.offsetY,
          state.image.naturalWidth * state.scale,
          state.image.naturalHeight * state.scale
        );
      }
      state.markers.forEach((marker, index) => {
        if (markerInTile(marker, tile)) drawMarker(marker, index);
      });
      state.suggestions.forEach(suggestion => {
        if (suggestionInTile(suggestion, tile)) drawSuggestion(suggestion);
      });
    }
    function markDirty() {
      state.dirty = true;
      setStatus('Unsaved');
      renderSide();
    }
    function addMarker(x, y) {
      if (x < 0 || y < 0 || x > state.image.naturalWidth || y > state.image.naturalHeight) return;
      state.markers.push({
        id: `${state.activeCode}_x${Math.round(x)}_y${Math.round(y)}`,
        code: state.activeCode,
        x: Math.round(x * 10) / 10,
        y: Math.round(y * 10) / 10,
        tile: currentTile(),
        note: ''
      });
      markDirty();
      draw();
    }
    function acceptSuggestion(suggestion) {
      if (suggestionAccepted(suggestion)) return;
      state.markers.push({
        id: suggestion.id,
        code: suggestion.code,
        x: suggestion.x,
        y: suggestion.y,
        tile: currentTile(),
        note: '',
        source: {
          type: 'scanner_suggestion',
          id: suggestion.id,
          path: suggestion.path,
          score: suggestion.score,
          angle_deg: suggestion.angle_deg
        }
      });
      markDirty();
      draw();
    }
    function acceptVisibleSuggestions() {
      state.suggestions
        .filter(suggestion => suggestionInTile(suggestion) && !suggestionAccepted(suggestion))
        .forEach(acceptSuggestion);
    }
    function removeMarker(index) {
      state.markers.splice(index, 1);
      markDirty();
      draw();
    }
    function nearestMarker(x, y, maxPx = 14) {
      let best = -1;
      let bestDist = maxPx;
      state.markers.forEach((marker, index) => {
        if (!markerInTile(marker)) return;
        const p = imageToScreen(marker.x, marker.y);
        const dist = Math.hypot(p.x - x, p.y - y);
        if (dist < bestDist) {
          best = index;
          bestDist = dist;
        }
      });
      return best;
    }
    function nearestSuggestion(x, y, maxPx = 16) {
      let best = null;
      let bestDist = maxPx;
      state.suggestions.forEach(suggestion => {
        if (suggestionAccepted(suggestion) || !suggestionInTile(suggestion)) return;
        const p = imageToScreen(suggestion.x, suggestion.y);
        const dist = Math.hypot(p.x - x, p.y - y);
        if (dist < bestDist) {
          best = suggestion;
          bestDist = dist;
        }
      });
      return best;
    }
    function renderCodes() {
      const wrap = document.getElementById('codes');
      wrap.replaceChildren();
      state.codes.forEach(code => {
        const button = document.createElement('button');
        button.textContent = labelFor(code) ? `${code} · ${labelFor(code)}` : code;
        button.title = state.codeLabels[code] ? state.codeLabels[code].name : code;
        button.className = code === state.activeCode ? 'active' : '';
        button.style.borderColor = colorFor(code);
        button.addEventListener('click', () => {
          state.activeCode = code;
          renderCodes();
        });
        wrap.appendChild(button);
      });
    }
    function renderSide() {
      const stats = document.getElementById('stats');
      stats.replaceChildren();
      const rows = [['Total', state.markers.length]];
      if (state.tiles.length) {
        rows.push(['This tile', state.markers.filter(m => markerInTile(m)).length]);
      }
      rows.push(['Scanner suggestions', state.suggestions.filter(s => suggestionInTile(s) && !suggestionAccepted(s)).length]);
      state.codes.forEach(code => rows.push([code, state.markers.filter(m => m.code === code).length]));
      rows.forEach(([label, value]) => {
        const row = document.createElement('div');
        row.className = 'stat-row';
        row.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
        stats.appendChild(row);
      });

      const list = document.getElementById('list');
      list.replaceChildren();
      state.markers.forEach((marker, index) => {
        if (!markerInTile(marker)) return;
        const row = document.createElement('div');
        row.className = 'marker-row';
        const chip = document.createElement('span');
        chip.className = 'code-chip';
        chip.style.background = colorFor(marker.code);
        chip.textContent = marker.code;
        const coords = document.createElement('span');
        coords.className = 'coords';
        coords.textContent = `${marker.x.toFixed(1)}, ${marker.y.toFixed(1)}`;
        const del = document.createElement('button');
        del.textContent = '×';
        del.className = 'danger';
        del.addEventListener('click', () => removeMarker(index));
        row.addEventListener('click', event => {
          if (event.target === del) return;
          const tileIndex = state.tiles.findIndex(tile => markerInTile(marker, tile));
          if (tileIndex >= 0) state.tileIndex = tileIndex;
          const rect = viewport.getBoundingClientRect();
          const tile = currentTile();
          state.offsetX = rect.width / 2 - (marker.x - (tile ? tile.x : 0)) * state.scale;
          state.offsetY = rect.height / 2 - (marker.y - (tile ? tile.y : 0)) * state.scale;
          renderTile();
          draw();
        });
        row.append(chip, coords, del);
        list.appendChild(row);
      });
      state.suggestions
        .filter(suggestion => suggestionInTile(suggestion) && !suggestionAccepted(suggestion))
        .forEach(suggestion => {
          const row = document.createElement('div');
          row.className = 'marker-row';
          const chip = document.createElement('span');
          chip.className = 'code-chip';
          chip.style.background = colorFor(suggestion.code);
          chip.textContent = `${suggestion.code}?`;
          const coords = document.createElement('span');
          coords.className = 'coords';
          const score = suggestion.score == null ? '' : ` · ${Number(suggestion.score).toFixed(2)}`;
          const angle = suggestion.angle_deg == null ? '' : ` · ${Number(suggestion.angle_deg).toFixed(0)}°`;
          coords.textContent = `${labelFor(suggestion.code)} ${suggestion.x.toFixed(1)}, ${suggestion.y.toFixed(1)}${score}${angle}`;
          const accept = document.createElement('button');
          accept.textContent = '+';
          accept.className = 'suggest';
          accept.addEventListener('click', () => acceptSuggestion(suggestion));
          row.addEventListener('click', event => {
            if (event.target === accept) return;
            const rect = viewport.getBoundingClientRect();
            const tile = currentTile();
            state.offsetX = rect.width / 2 - (suggestion.x - (tile ? tile.x : 0)) * state.scale;
            state.offsetY = rect.height / 2 - (suggestion.y - (tile ? tile.y : 0)) * state.scale;
            draw();
          });
          row.append(chip, coords, accept);
          list.appendChild(row);
        });
    }
    function renderTile() {
      const bar = document.getElementById('tilebar');
      if (!state.tiles.length) {
        bar.hidden = true;
        return;
      }
      bar.hidden = false;
      const tile = currentTile();
      const ink = tile.ink_ratio == null ? '' : ` · ink ${(tile.ink_ratio * 100).toFixed(1)}%`;
      const suggestions = state.suggestions.filter(s => suggestionInTile(s) && !suggestionAccepted(s)).length;
      const candidateInfo = tile.candidate_count == null ? '' : ` · candidates ${tile.candidate_count}`;
      const codes = tile.codes && tile.codes.length ? ` · ${tile.codes.join('/')}` : '';
      const end = state.tileIndex === state.tiles.length - 1 ? ' · last tile' : '';
      const done = state.status === 'MARKER_DONE' ? ' · DONE' : '';
      document.getElementById('tileLabel').textContent =
        `Tile ${state.tileIndex + 1}/${state.tiles.length}${end}${done} · scan orientation · x=${tile.x} y=${tile.y} · ${tile.w}×${tile.h}${ink}${candidateInfo}${codes} · suggestions ${suggestions}`;
      document.getElementById('prevTile').disabled = state.tileIndex === 0;
      document.getElementById('nextTile').disabled = state.tileIndex === state.tiles.length - 1;
      renderSide();
      draw();
    }
    function moveTile(delta) {
      if (!state.tiles.length) return;
      state.tileIndex = Math.max(0, Math.min(state.tiles.length - 1, state.tileIndex + delta));
      renderTile();
      fitImage();
    }
    async function saveMarkers(endpoint = '/api/markers') {
      setStatus('Saving');
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({markers: state.markers})
      });
      if (!res.ok) {
        const text = await res.text();
        setStatus('Save failed');
        throw new Error(text);
      }
      const payload = await res.json();
      state.markers = payload.markers;
      state.status = payload._status || state.status;
      state.dirty = false;
      setStatus(state.status === 'MARKER_DONE' ? 'Set finished' : 'Saved');
      renderTile();
      draw();
    }
    function finishSet() {
      saveMarkers('/api/finish').catch(console.error);
    }
    function canvasPoint(event) {
      const rect = canvas.getBoundingClientRect();
      return {x: event.clientX - rect.left, y: event.clientY - rect.top};
    }

    canvas.addEventListener('pointerdown', event => {
      const p = canvasPoint(event);
      if (event.button === 1 || event.button === 2 || event.shiftKey || event.ctrlKey) {
        state.dragging = true;
        state.dragStart = {x: p.x, y: p.y, offsetX: state.offsetX, offsetY: state.offsetY};
        canvas.setPointerCapture(event.pointerId);
        return;
      }
      if (event.altKey) {
        const index = nearestMarker(p.x, p.y);
        if (index >= 0) removeMarker(index);
        return;
      }
      const suggestion = nearestSuggestion(p.x, p.y);
      if (suggestion) {
        acceptSuggestion(suggestion);
        return;
      }
      const img = screenToImage(p.x, p.y);
      addMarker(img.x, img.y);
    });
    canvas.addEventListener('pointermove', event => {
      if (!state.dragging) return;
      const p = canvasPoint(event);
      state.offsetX = state.dragStart.offsetX + p.x - state.dragStart.x;
      state.offsetY = state.dragStart.offsetY + p.y - state.dragStart.y;
      draw();
    });
    canvas.addEventListener('pointerup', event => {
      state.dragging = false;
      try { canvas.releasePointerCapture(event.pointerId); } catch (_) {}
    });
    canvas.addEventListener('contextmenu', event => event.preventDefault());
    canvas.addEventListener('wheel', event => {
      event.preventDefault();
      const p = canvasPoint(event);
      const before = screenToImage(p.x, p.y);
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      state.scale = Math.max(0.05, Math.min(20, state.scale * factor));
      state.offsetX = p.x - before.x * state.scale;
      state.offsetY = p.y - before.y * state.scale;
      draw();
    }, {passive: false});
    window.addEventListener('keydown', event => {
      if (event.key === 'Backspace' || (event.ctrlKey && event.key.toLowerCase() === 'z')) {
        event.preventDefault();
        if (state.markers.length) removeMarker(state.markers.length - 1);
      }
      if (event.ctrlKey && event.key.toLowerCase() === 's') {
        event.preventDefault();
        saveMarkers().catch(console.error);
      }
      const numeric = Number(event.key);
      if (Number.isInteger(numeric) && numeric >= 1 && numeric <= state.codes.length) {
        state.activeCode = state.codes[numeric - 1];
        renderCodes();
      }
      if (event.key === 'ArrowLeft') moveTile(-1);
      if (event.key === 'ArrowRight') moveTile(1);
    });
    document.getElementById('fit').addEventListener('click', fitImage);
    document.getElementById('undo').addEventListener('click', () => {
      if (state.markers.length) removeMarker(state.markers.length - 1);
    });
    document.getElementById('save').addEventListener('click', () => saveMarkers().catch(console.error));
    document.getElementById('prevTile').addEventListener('click', () => moveTile(-1));
    document.getElementById('nextTile').addEventListener('click', () => moveTile(1));
    document.getElementById('acceptTile').addEventListener('click', acceptVisibleSuggestions);
    document.getElementById('finishSet').addEventListener('click', finishSet);
    window.addEventListener('resize', resizeCanvas);
    window.addEventListener('beforeunload', event => {
      if (!state.dirty) return;
      event.preventDefault();
      event.returnValue = '';
    });

    async function boot() {
      const cfg = await (await fetch('/api/config')).json();
      document.getElementById('title').textContent = cfg.title;
      document.getElementById('path').textContent = cfg.markers_path;
      state.codes = cfg.ui_codes || cfg.codes;
      state.activeCode = cfg.codes[0];
      state.markers = cfg.markers || [];
      state.tiles = cfg.tiles || [];
      state.suggestions = cfg.suggestions || [];
      state.codeLabels = cfg.code_labels || {};
      state.status = cfg.status || 'MARKER_DRAFT';
      renderCodes();
      renderTile();
      renderSide();
      state.image.onload = () => {
        resizeCanvas();
        fitImage();
        setStatus(state.markers.length ? 'Loaded' : 'Ready');
      };
      state.image.src = cfg.image;
    }
    boot().catch(error => {
      console.error(error);
      setStatus('Load failed');
    });
  </script>
</body>
</html>
"""


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
