"""Index ISOM symbolu nad lokalnim SVG katalogem.

Tenhle modul je zamerne nezavisly na `generator.py`: pracuje jen s katalogem
`resources/isom/` a vraci stabilni datove zaznamy, ktere muze pouzit generator,
tooling i budouci reconstructor. Barvy skenu sem nepatri; SVG je shape reference,
zatimco skutecna tiskova barva se tezi z konkretniho skenu.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from typing import Any


INDEX_VERSION = 1
DEFAULT_RESOURCE_DIR = Path("resources") / "isom"
GEOMETRIES = {"point", "line", "area", "unknown"}
_CODE_RE = re.compile(r"^(?P<code>\d+(?:[._]\d+)?)(?:[_ -]+(?P<name>.+))?$")
_HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}")


class SymbolIndexError(ValueError):
    """Chyba katalogu ISOM symbolu."""


@dataclass(frozen=True)
class SymbolRecord:
    """Jeden kanonicky ISOM symbol v katalogu.

    `files["svg"]` je cesta relativni k `resources/isom/`. `descriptor` je lehky,
    deterministicky pre-vypocet nad SVG, ne vysledek detekce ve skenu.
    """

    code: str
    canonical_name: str
    display_name: str
    geom: str
    color_role: str
    colors: tuple[str, ...]
    isom_version: str
    scale: int | None
    paper_size_mm: dict[str, float]
    stroke_width_mm: float | None
    source: dict[str, str]
    files: dict[str, str]
    aliases: dict[str, list[str]]
    descriptor: dict[str, Any]

    @property
    def terrain_footprint_m(self) -> dict[str, float] | None:
        """Prepocet papiru na teren; napr. 1 mm pri 1:10000 = 10 m."""
        if self.scale is None:
            return None
        width = self.paper_size_mm.get("width")
        height = self.paper_size_mm.get("height")
        if width is None or height is None:
            return None
        return {
            "width": width * self.scale / 1000.0,
            "height": height * self.scale / 1000.0,
        }

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "canonical_name": self.canonical_name,
            "display_name": self.display_name,
            "geom": self.geom,
            "color_role": self.color_role,
            "colors": list(self.colors),
            "isom_version": self.isom_version,
            "paper_size_mm": self.paper_size_mm,
            "source": self.source,
            "files": self.files,
            "aliases": self.aliases,
        }
        if self.scale is not None:
            out["scale"] = self.scale
        if self.stroke_width_mm is not None:
            out["stroke_width_mm"] = self.stroke_width_mm
        footprint = self.terrain_footprint_m
        if footprint is not None:
            out["terrain_footprint_m"] = footprint
        return out


class SymbolIndex:
    """Vyhledavaci fasada nad ISOM symboly."""

    def __init__(self, records: list[SymbolRecord], resource_dir: Path):
        self.records = tuple(records)
        self.resource_dir = Path(resource_dir)
        by_code: dict[str, SymbolRecord] = {}
        for record in records:
            if record.code in by_code:
                raise SymbolIndexError(f"duplicitni ISOM kod {record.code}")
            by_code[record.code] = record
        self._by_code = by_code

    def __len__(self) -> int:
        return len(self.records)

    def by_code(self, code: str | int) -> SymbolRecord:
        key = normalize_code(str(code))
        try:
            return self._by_code[key]
        except KeyError as exc:
            raise KeyError(f"ISOM symbol {key} neni v katalogu") from exc

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "$schema": "index.schema.json",
            "version": INDEX_VERSION,
            "symbols": [record.to_json_dict() for record in self.records],
        }


def normalize_code(raw: str) -> str:
    """Normalizuje zapis kodu: `512_2` ve jmenu souboru znamena `512.2`."""
    raw = raw.strip()
    if "_" in raw and raw.replace("_", "").isdigit():
        raw = raw.replace("_", ".", 1)
    return raw


def load_symbol_index(resource_dir: str | Path = DEFAULT_RESOURCE_DIR,
                      strict: bool = False) -> SymbolIndex:
    """Nacte `index.json`; kdyz chybi, zkusmo objevi SVG soubory.

    Draft discovery je uzitecny pro tools. Konzumenti typu generator/reconstructor
    maji volat `strict=True`, aby je nezaskocil nevyplneny zdroj/licence/geometrie.
    """
    return build_symbol_index(resource_dir, strict=strict)


def build_symbol_index(resource_dir: str | Path = DEFAULT_RESOURCE_DIR,
                       strict: bool = False) -> SymbolIndex:
    resource = Path(resource_dir)
    if not resource.exists():
        raise FileNotFoundError(f"ISOM resource adresar neexistuje: {resource}")
    if not resource.is_dir():
        raise NotADirectoryError(f"ISOM resource cesta neni adresar: {resource}")

    index_path = resource / "index.json"
    if index_path.exists():
        records = _records_from_index(index_path, resource)
    else:
        records = _records_from_svg_discovery(resource)

    _validate_records(records, strict=strict)
    return SymbolIndex(records, resource)


def write_symbol_index(index: SymbolIndex,
                       resource_dir: str | Path | None = None) -> Path:
    """Zapise stabilni `index.json` a samostatne descriptor JSON soubory."""
    resource = Path(resource_dir) if resource_dir is not None else index.resource_dir
    resource.mkdir(parents=True, exist_ok=True)
    descriptor_dir = resource / "descriptors"
    descriptor_dir.mkdir(parents=True, exist_ok=True)

    serializable_records = []
    for record in index.records:
        out = record.to_json_dict()
        descriptor_rel = out.setdefault("files", {}).get("descriptor")
        if descriptor_rel is None:
            descriptor_rel = f"descriptors/{record.code}_{record.canonical_name}.json"
            out["files"]["descriptor"] = descriptor_rel
        descriptor_path = resource / descriptor_rel
        descriptor_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor_path.write_text(
            json.dumps(record.descriptor, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        serializable_records.append(out)

    index_path = resource / "index.json"
    index_payload = {
        "$schema": "index.schema.json",
        "version": INDEX_VERSION,
        "symbols": serializable_records,
    }
    index_path.write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return index_path


def _records_from_index(index_path: Path, resource: Path) -> list[SymbolRecord]:
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SymbolIndexError(f"{index_path}: neplatny JSON: {exc}") from exc
    if payload.get("version") != INDEX_VERSION:
        raise SymbolIndexError(
            f"{index_path}: nepodporovana verze indexu {payload.get('version')!r}"
        )
    symbols = payload.get("symbols")
    if not isinstance(symbols, list):
        raise SymbolIndexError(f"{index_path}: chybi pole symbols")
    return [_record_from_json(item, resource, index_path) for item in symbols]


def _record_from_json(item: dict[str, Any], resource: Path, index_path: Path) -> SymbolRecord:
    if not isinstance(item, dict):
        raise SymbolIndexError(f"{index_path}: symbol musi byt objekt")
    files = _string_dict(item.get("files", {}), "files")
    descriptor = _load_descriptor(resource, files)
    svg_rel = files.get("svg")
    if svg_rel:
        svg_path = resource / svg_rel
        if svg_path.exists():
            descriptor = {**_svg_descriptor(svg_path), **descriptor}
    return SymbolRecord(
        code=normalize_code(_required_str(item, "code")),
        canonical_name=_slug(_required_str(item, "canonical_name")),
        display_name=_required_str(item, "display_name"),
        geom=_required_str(item, "geom"),
        color_role=str(item.get("color_role", "unknown")),
        colors=tuple(_normalize_colors(item.get("colors", []))),
        isom_version=str(item.get("isom_version", "unknown")),
        scale=_optional_int(item.get("scale")),
        paper_size_mm=_float_dict(item.get("paper_size_mm", {}), "paper_size_mm"),
        stroke_width_mm=_optional_float(item.get("stroke_width_mm")),
        source=_string_dict(item.get("source", {}), "source"),
        files=files,
        aliases=_aliases(item.get("aliases", {})),
        descriptor=descriptor,
    )


def _records_from_svg_discovery(resource: Path) -> list[SymbolRecord]:
    svg_files = sorted((resource / "svg").glob("*.svg")) if (resource / "svg").exists() else []
    svg_files += sorted(p for p in resource.glob("*.svg") if p.is_file())
    if not svg_files:
        raise SymbolIndexError(
            f"{resource}: chybi index.json a nebyly nalezeny zadne SVG v {resource / 'svg'}"
        )
    records = []
    for svg in svg_files:
        code, canonical = _infer_code_and_name(svg)
        descriptor = _svg_descriptor(svg)
        records.append(SymbolRecord(
            code=code,
            canonical_name=canonical,
            display_name=_display_name(canonical),
            geom="unknown",
            color_role="unknown",
            colors=tuple(descriptor.get("colors", [])),
            isom_version="unknown",
            scale=None,
            paper_size_mm={},
            stroke_width_mm=None,
            source={"kind": "unknown", "license": "unknown"},
            files={"svg": svg.relative_to(resource).as_posix()},
            aliases={},
            descriptor=descriptor,
        ))
    return records


def _infer_code_and_name(svg: Path) -> tuple[str, str]:
    match = _CODE_RE.match(svg.stem)
    if not match:
        raise SymbolIndexError(
            f"{svg}: jmeno SVG musi zacinat ISOM kodem, napr. 525_small_tower.svg"
        )
    code = normalize_code(match.group("code"))
    name = match.group("name") or f"isom_{code.replace('.', '_')}"
    return code, _slug(name)


def _svg_descriptor(svg_path: Path) -> dict[str, Any]:
    text = svg_path.read_text(encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise SymbolIndexError(f"{svg_path}: neplatne SVG/XML: {exc}") from exc
    width = _length_number(root.get("width"))
    height = _length_number(root.get("height"))
    view_box = _view_box(root.get("viewBox"))
    if view_box and (width is None or height is None):
        width, height = view_box[2], view_box[3]

    elements: dict[str, int] = {}
    colors: set[str] = set()
    for elem in root.iter():
        tag = _local_name(elem.tag)
        elements[tag] = elements.get(tag, 0) + 1
        colors.update(_element_colors(elem))

    descriptor: dict[str, Any] = {
        "sha256": sha,
        "elements": dict(sorted(elements.items())),
        "colors": sorted(colors),
    }
    if width is not None:
        descriptor["width"] = width
    if height is not None:
        descriptor["height"] = height
    if width and height:
        descriptor["aspect_ratio"] = width / height
    if view_box:
        descriptor["view_box"] = view_box
    return descriptor


def _validate_records(records: list[SymbolRecord], strict: bool) -> None:
    seen: set[str] = set()
    for record in records:
        if record.code in seen:
            raise SymbolIndexError(f"duplicitni ISOM kod {record.code}")
        seen.add(record.code)
        if record.geom not in GEOMETRIES:
            raise SymbolIndexError(f"{record.code}: neplatna geometrie {record.geom!r}")
        if not record.files.get("svg"):
            raise SymbolIndexError(f"{record.code}: chybi files.svg")
        if strict:
            if record.geom == "unknown":
                raise SymbolIndexError(f"{record.code}: strict vyzaduje vyplnenou geom")
            if record.source.get("license", "unknown") == "unknown":
                raise SymbolIndexError(f"{record.code}: strict vyzaduje znamou licenci")
            if record.isom_version == "unknown":
                raise SymbolIndexError(f"{record.code}: strict vyzaduje isom_version")


def _load_descriptor(resource: Path, files: dict[str, str]) -> dict[str, Any]:
    descriptor_rel = files.get("descriptor")
    if not descriptor_rel:
        return {}
    descriptor_path = resource / descriptor_rel
    if not descriptor_path.exists():
        return {}
    try:
        payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SymbolIndexError(f"{descriptor_path}: neplatny descriptor JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SymbolIndexError(f"{descriptor_path}: descriptor musi byt objekt")
    return payload


def _required_str(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SymbolIndexError(f"symbol: chybi povinne textove pole {key}")
    return value.strip()


def _string_dict(value: Any, name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SymbolIndexError(f"{name} musi byt objekt")
    out = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise SymbolIndexError(f"{name}: klic musi byt string")
        if isinstance(item, (str, int, float)):
            out[key] = str(item)
        elif item is None:
            continue
        else:
            raise SymbolIndexError(f"{name}.{key} musi byt scalar")
    return out


def _float_dict(value: Any, name: str) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SymbolIndexError(f"{name} musi byt objekt")
    out = {}
    for key, item in value.items():
        try:
            out[str(key)] = float(item)
        except (TypeError, ValueError) as exc:
            raise SymbolIndexError(f"{name}.{key} musi byt cislo") from exc
    return out


def _aliases(value: Any) -> dict[str, list[str]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SymbolIndexError("aliases musi byt objekt")
    out: dict[str, list[str]] = {}
    for key, items in value.items():
        if not isinstance(items, list):
            raise SymbolIndexError(f"aliases.{key} musi byt list")
        out[str(key)] = [str(item) for item in items]
    return out


def _normalize_colors(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SymbolIndexError("colors musi byt list")
    colors = []
    for color in value:
        if not isinstance(color, str) or not _HEX_COLOR_RE.fullmatch(color):
            raise SymbolIndexError(f"neplatna barva {color!r}")
        colors.append(color.lower())
    return sorted(set(colors))


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "_", value.strip()).strip("_").lower()
    return slug or "symbol"


def _display_name(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("_"))


def _length_number(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)", value)
    return float(match.group(1)) if match else None


def _view_box(value: str | None) -> list[float] | None:
    if not value:
        return None
    parts = re.split(r"[\s,]+", value.strip())
    if len(parts) != 4:
        return None
    try:
        return [float(part) for part in parts]
    except ValueError:
        return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _element_colors(elem: ET.Element) -> set[str]:
    values = [elem.get("stroke"), elem.get("fill"), elem.get("style")]
    colors: set[str] = set()
    for value in values:
        if not value:
            continue
        colors.update(color.lower() for color in _HEX_COLOR_RE.findall(value))
    return colors
