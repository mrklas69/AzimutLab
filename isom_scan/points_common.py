"""points_common.py — sdílená mašinérie scan-mining bodových detektorů (C1 dedup, Sez. 165 %AUDIT:CODE).

Před refaktorem žily `_load_font` / `_resize_for_processing` / `_resize_bool` / `_shape_f1` /
`_save_mask` / `Candidate` + kostra `component_candidates` / `classify` / `detections_payload` /
`draw_overlay` / `contact_sheet` ČTYŘIKRÁT zkopírované (water/terrain/vegetation/manmade) — 8 funkcí
bylo byte-identických. Tady jsou jednou; detektory zůstávají tenké configy (barevná maska + template
renderer + parametry). Sdíleno i s `points_review` / `points_omap` (schéma kandidáta).

ZÁMĚR REFAKTORU = čistě DRY, BEZ změny chování: `classify_simple` drží PŮVODNÍ full-crop komponentu
(`mask[sy, sx]`), aby výstup zůstal identický s předrefaktorovým. Známé vady auditu Sez. 165 —
component-leak (D2/D3) a hardcoded názvy vs SSoT (D4) — jsou ZMĚNY CHOVÁNÍ, vědomě ZDE NEPROVEDENÉ
(patří jako měřený opt-in, ne tichá součást úklidu).

Sys.path skript (fáze B), ne balík; importuje se jako sibling z `isom_scan/`.
"""
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

# Povolené verdikty ruční kurace (sdíleno s points_review/points_omap; dřív 3× zkopírované).
REVIEW_VALUES = ("unreviewed", "tp", "fp", "ignore")


# ---------------------------------------------------------------------------
# Obrázkové helpery (dřív byte-identické ve 4 detektorech)
# ---------------------------------------------------------------------------
def load_font(size: int) -> ImageFont.ImageFont:
    """Najde rozumný TTF font, jinak spadne na PIL default."""
    for name in ("arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def resize_for_processing(img: Image.Image, max_dim: int) -> tuple[Image.Image, float]:
    """Vrátí pracovní obraz a měřítko proc_px/orig_px (max_dim<=0 = beze změny)."""
    if max_dim <= 0 or max(img.size) <= max_dim:
        return img.copy(), 1.0
    scale = max_dim / max(img.size)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    return img.resize(size, Image.Resampling.BILINEAR), scale


def resize_bool(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Nearest-neighbour resize binární šablony přes PIL, bez OpenCV závislosti."""
    h, w = shape
    im = Image.fromarray(mask.astype(np.uint8) * 255, mode="L")
    return np.asarray(im.resize((w, h), Image.Resampling.NEAREST)) > 0


def shape_f1(component: np.ndarray, template: np.ndarray) -> float:
    """F1 překryvu komponenty se šablonou přetaženou na stejný bbox."""
    if not component.any():
        return 0.0
    tmpl = resize_bool(template, component.shape)
    overlap = component & tmpl
    tp = int(overlap.sum())
    if tp == 0:
        return 0.0
    precision = tp / int(component.sum())
    recall = tp / int(tmpl.sum())
    return 2 * precision * recall / (precision + recall)


def save_mask(mask: np.ndarray, out_path: Path) -> None:
    """Uloží bool masku jako 8-bit PNG (0/255)."""
    Image.fromarray(mask.astype(np.uint8) * 255, mode="L").save(out_path)


# ---------------------------------------------------------------------------
# Kandidát + detekce komponent
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Candidate:
    """Jedna izolovaná barevná komponenta klasifikovaná podle nejlepší šablony.

    `angle_deg` plní jen rotující detektor (water); ostatní nechávají default 0 a do payloadu
    ho neemitují (viz `detections_payload(..., include_angle=False)`)."""

    code: str
    score: float
    x: float
    y: float
    bbox: tuple[float, float, float, float]
    area_px: int
    fill: float
    angle_deg: int = 0


def component_candidates(
    mask: np.ndarray,
    *,
    min_size: int,
    max_size: int,
    min_area: int,
    max_area: int,
    min_fill: float,
    max_fill: float,
    close_px: int,
    max_aspect: float | None = None,
    return_idx: bool = False,
) -> list:
    """Vybere rozumně malé komponenty; dlouhé linie / plošné šrafy nechá mimo.

    Filtry (size bboxu, volitelně aspect, plocha, fill) jsou v původním pořadí, aby výsledná
    množina seděla 1:1 s předrefaktorovými detektory. `return_idx=True` (water) vrací i label
    index; jinak vrací jen (sy, sx) slices."""
    label_mask = mask
    if close_px > 0:
        structure = np.ones((3, 3), dtype=bool)
        label_mask = ndi.binary_closing(mask, structure=structure, iterations=close_px)
    labels, _ = ndi.label(label_mask)
    objects = ndi.find_objects(labels)

    out: list = []
    for idx, obj in enumerate(objects, start=1):
        if obj is None:
            continue
        sy, sx = obj
        h = sy.stop - sy.start
        w = sx.stop - sx.start
        if h < min_size or w < min_size or h > max_size or w > max_size:
            continue
        if max_aspect is not None:
            aspect = max(w, h) / max(1, min(w, h))
            if aspect > max_aspect:
                continue
        component = labels[sy, sx] == idx
        area = int(component.sum())
        if area < min_area or area > max_area:
            continue
        fill = area / (w * h)
        if fill < min_fill or fill > max_fill:
            continue
        out.append((idx, sy, sx) if return_idx else (sy, sx))
    return out


def classify_simple(
    mask: np.ndarray,
    scale: float,
    *,
    templates: dict[str, np.ndarray],
    target_codes: tuple[str, ...],
    code_order: dict[str, int],
    score_threshold: float,
    max_per_code: int,
    raw_components: list,
) -> tuple[list[Candidate], dict[str, object]]:
    """Klasifikace bez rotace (manmade/terrain/vegetation byly byte-identické).

    POZN. (audit Sez. 165 D2/D3): komponenta = `mask[sy, sx]` = celý výřez bboxu, do kterého
    můžou prosáknout sousední komponenty. Je to PŮVODNÍ chování — vědomě zachované, ať je refaktor
    bez změny výstupu. Label-izolovaná oprava je samostatný měřený opt-in."""
    candidates: list[Candidate] = []
    for sy, sx in raw_components:
        component = mask[sy, sx]
        scores = {code: shape_f1(component, tmpl) for code, tmpl in templates.items()}
        code, score = max(scores.items(), key=lambda item: (item[1], -code_order[item[0]]))
        if score < score_threshold:
            continue

        ys, xs = np.where(component)
        x0 = (sx.start + float(xs.min())) / scale
        y0 = (sy.start + float(ys.min())) / scale
        x1 = (sx.start + float(xs.max()) + 1.0) / scale
        y1 = (sy.start + float(ys.max()) + 1.0) / scale
        area = int(component.sum())
        candidates.append(Candidate(
            code=code,
            score=float(score),
            x=(x0 + x1) / 2.0,
            y=(y0 + y1) / 2.0,
            bbox=(x0, y0, x1, y1),
            area_px=area,
            fill=area / max(1, component.shape[0] * component.shape[1]),
        ))

    candidates.sort(key=lambda c: (c.code, -c.score, c.y, c.x))
    capped: list[Candidate] = []
    for code in target_codes:
        capped.extend([c for c in candidates if c.code == code][:max_per_code])

    stats = {
        "raw_components": len(raw_components),
        "kept_total": len(capped),
        "kept_by_code": {code: sum(1 for c in capped if c.code == code) for code in target_codes},
        "templates": {code: {"w": int(t.shape[1]), "h": int(t.shape[0]), "px": int(t.sum())}
                      for code, t in templates.items()},
    }
    return capped, stats


# ---------------------------------------------------------------------------
# Payload + vizualizace
# ---------------------------------------------------------------------------
def detections_payload(
    candidates: list[Candidate],
    image_path: Path,
    image_size: tuple[int, int],
    scale: float,
    *,
    target_codes: tuple[str, ...],
    code_names: dict[str, str],
    parameters: dict[str, object],
    status: str,
    doc: str,
    stats: dict[str, object],
    include_angle: bool = False,
    calibration: dict[str, object] | None = None,
) -> dict[str, object]:
    """Sestaví detections.json payload. `include_angle` (jen water) přidá `angle_deg` do bodu,
    `calibration` (jen water s markery) se přidá za `detections` — pořadí klíčů jako před refaktorem."""
    detections = []
    for code in target_codes:
        pts = []
        for c in candidates:
            if c.code != code:
                continue
            point: dict[str, object] = {"x": round(c.x, 1), "y": round(c.y, 1), "score": round(c.score, 3)}
            if include_angle:
                point["angle_deg"] = c.angle_deg
            point["bbox"] = [round(v, 1) for v in c.bbox]
            point["area_px_proc"] = c.area_px
            point["fill"] = round(c.fill, 3)
            pts.append(point)
        detections.append({
            "code": code,
            "name": code_names[code],
            "geom": "point",
            "count": len(pts),
            "points": pts,
            "confidence": round(float(np.mean([p["score"] for p in pts])) if pts else 0.0, 3),
        })

    payload: dict[str, object] = {
        "_status": status,
        "_doc": doc,
        "image": str(image_path),
        "image_size": {"w": image_size[0], "h": image_size[1]},
        "processing_scale": scale,
        "parameters": parameters,
        "stats": stats,
        "detections": detections,
    }
    if calibration is not None:
        payload["calibration"] = calibration
    return payload


def draw_overlay(
    img: Image.Image,
    candidates: list[Candidate],
    out_path: Path,
    *,
    colors: dict[str, tuple[int, int, int]],
    label_fn: Callable[[Candidate], str],
) -> None:
    """Nakreslí bboxy kandidátů + štítek; barvy a text štítku jsou per-detektor."""
    out = img.copy()
    draw = ImageDraw.Draw(out)
    font = load_font(16)
    for c in candidates:
        color = colors.get(c.code, (255, 0, 0))
        x0, y0, x1, y1 = c.bbox
        pad = 5
        draw.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], outline=color, width=3)
        label = label_fn(c)
        box = draw.textbbox((x1 + 6, y0 - 2), label, font=font)
        draw.rectangle([box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2], fill=(255, 255, 255))
        draw.text((x1 + 6, y0 - 2), label, fill=color, font=font)
    out.save(out_path)


def contact_sheet(
    img: Image.Image,
    candidates: list[Candidate],
    out_path: Path,
    *,
    limit: int,
    tile: int,
    label_h: int,
    font_size: int,
    half_min: float,
    half_extra: float,
    label_fn: Callable[[Candidate], str],
) -> None:
    """Mozaika výřezů nejlepších kandidátů; rozměry/limit/štítek jsou per-detektor."""
    if not candidates:
        Image.new("RGB", (420, 80), "white").save(out_path)
        return
    chosen = sorted(candidates, key=lambda c: -c.score)[:limit]
    cols = min(6, len(chosen))
    rows = math.ceil(len(chosen) / cols)
    sheet = Image.new("RGB", (cols * tile, rows * (tile + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    font = load_font(font_size)
    for i, c in enumerate(chosen):
        row, col = divmod(i, cols)
        x0, y0, x1, y1 = c.bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        half = max(half_min, (max(x1 - x0, y1 - y0) / 2) + half_extra)
        crop_box = (
            max(0, int(cx - half)),
            max(0, int(cy - half)),
            min(img.width, int(cx + half)),
            min(img.height, int(cy + half)),
        )
        crop = img.crop(crop_box).resize((tile, tile), Image.Resampling.BILINEAR)
        px = col * tile
        py = row * (tile + label_h)
        sheet.paste(crop, (px, py))
        draw.text((px + 4, py + tile + 4), label_fn(c), fill=(0, 0, 0), font=font)
    sheet.save(out_path)


def run_simple_detector(
    args,
    *,
    mask_fn: Callable[[np.ndarray], np.ndarray],
    mask_name: str,
    mask_stat_prefix: str,
    templates: dict[str, np.ndarray],
    target_codes: tuple[str, ...],
    code_names: dict[str, str],
    parameters: dict[str, object],
    status: str,
    doc: str,
    overlay_name: str,
    sheet_name: str,
    overlay_colors: dict[str, tuple[int, int, int]],
    sheet_kwargs: dict[str, object],
    component_kwargs: dict[str, object],
) -> int:
    """Společná main-pipeline pro NErotující detektory (manmade/terrain/vegetation).

    Otevře sken → resize → barevná maska → component_candidates → classify_simple → payload →
    zápis detections/stats/mask + overlay + contact sheet → print. Water má vlastní main
    (rotace + marker kalibrace)."""
    args.out_dir.mkdir(parents=True, exist_ok=True)
    original = Image.open(args.input).convert("RGB")
    proc, scale = resize_for_processing(original, args.max_dim)
    arr = np.asarray(proc)
    mask = mask_fn(arr)
    code_order = {code: i for i, code in enumerate(target_codes)}
    raw_components = component_candidates(mask, **component_kwargs)
    candidates, stats = classify_simple(
        mask, scale, templates=templates, target_codes=target_codes, code_order=code_order,
        score_threshold=args.score_threshold, max_per_code=args.max_per_code, raw_components=raw_components,
    )
    payload = detections_payload(
        candidates, args.input, original.size, scale, target_codes=target_codes,
        code_names=code_names, parameters=parameters, status=status, doc=doc, stats=stats,
    )

    (args.out_dir / "detections.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out_dir / "stats.json").write_text(
        json.dumps({f"{mask_stat_prefix}_px_proc": int(mask.sum()),
                    f"{mask_stat_prefix}_share_proc": float(mask.mean()), **stats},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    save_mask(mask, args.out_dir / mask_name)
    # NErotující detektory mají shodné štítky: overlay `kód skóre`, sheet `kód score=skóre`.
    draw_overlay(original, candidates, args.out_dir / overlay_name,
                 colors=overlay_colors, label_fn=lambda c: f"{c.code} {c.score:.2f}")
    contact_sheet(original, candidates, args.out_dir / sheet_name,
                  label_fn=lambda c: f"{c.code} score={c.score:.2f}", **sheet_kwargs)

    print(json.dumps(payload["stats"], ensure_ascii=False, indent=2))
    print(f"Výstupy: {args.out_dir}")
    return 0


# ---------------------------------------------------------------------------
# Schéma kandidáta pro kuraci (sdíleno points_review ↔ points_omap)
# ---------------------------------------------------------------------------
def candidate_id(code: str, x: float, y: float) -> str:
    """Stabilní id kandidáta z kódu a zaokrouhlené pozice (dřív 2× zkopírované)."""
    return f"{code}_x{round(x)}_y{round(y)}"


def sha256(path: Path) -> str:
    """SHA-256 souboru po blocích (otisk skenu do review manifestu)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    """Načte JSON, na rozbitém obsahu selže nahlas (no silent fallback)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON nejde nacist: {path}: {exc}") from exc


def resolve_existing_path(raw: str | Path, bases: list[Path]) -> Path:
    """Najde soubor z absolutní cesty nebo relativně vůči známým bázím; jinak selže nahlas."""
    path = Path(raw)
    candidates = [path]
    if not path.is_absolute():
        candidates.extend(base / path for base in bases)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise SystemExit(f"Chybi soubor: {raw}")


def crop_box(candidate: dict[str, Any], img: Image.Image, crop_px: int) -> tuple[int, int, int, int]:
    """Crop centrovaný na kandidátovi; bbox se vejde i s okolím (review crop sheet)."""
    cx = float(candidate["center"]["x"])
    cy = float(candidate["center"]["y"])
    bbox = candidate.get("bbox") or []
    if len(bbox) == 4:
        w = float(bbox[2]) - float(bbox[0])
        h = float(bbox[3]) - float(bbox[1])
        half = max(crop_px / 2.0, max(w, h) * 2.0)
    else:
        half = crop_px / 2.0
    return (
        max(0, round(cx - half)),
        max(0, round(cy - half)),
        min(img.width, round(cx + half)),
        min(img.height, round(cy + half)),
    )
