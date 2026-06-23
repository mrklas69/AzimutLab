"""Capability registry pro ISOM symboly produkovane generatorem.

Tenhle modul odpovida na praktickou otazku: co dnes generator kresli z
realneho zdroje, co je scan/mapar-derived signal a co je statisticka pseudo
vrstva. Neni to nahrada SVG indexu; SVG popisuje tvar symbolu, capability
registry popisuje puvod dat a konfliktni pravidlo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .symbol_index import normalize_code


CONFLICT_POLICY = "mapper_scan > external_geodata > pseudo"

GEN_REAL = "real"
GEN_MAPPER_SCAN = "mapper_scan"
GEN_MIXED = "mixed"
GEN_PSEUDO = "pseudo"

SCAN_LIVE_POINT = "live_png2point"
SCAN_LIVE_LINE = "live_png2line"
SCAN_AREA = "area_scan_or_separation"
SCAN_POC = "classic_cv_poc"
SCAN_CANDIDATE = "classic_cv_candidate"
SCAN_NONE = "not_started"
SCAN_REAL_STATUSES = frozenset({SCAN_LIVE_POINT, SCAN_LIVE_LINE, SCAN_AREA})


@dataclass(frozen=True)
class SymbolCapability:
    """Jedna radka pravdy o puvodu symbolu v generatoru.

    `generator_kind` je hlavni odpoved na "realne vs predstirane":
    real = tvrda geodata/vyskopis, mapper_scan = signal z realne mapy mapare,
    mixed = realny nosic + pseudo interpretace/doplneni, pseudo = ciste
    statisticke dosypani. `scanner_status` rika, jestli uz pro kod existuje
    zivy scan-mining/reconstructor signal, nebo jen budovatelny kandidat.
    """

    code: str
    name: str
    geom: str
    generator_kind: str
    generator_source: str
    scanner_status: str = SCAN_NONE
    note: str = ""
    variants: tuple[str, ...] = ()

    def to_json_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "code": self.code,
            "name": self.name,
            "geom": self.geom,
            "generator_kind": self.generator_kind,
            "preferred_kind": self.preferred_kind,
            "generator_source": self.generator_source,
            "scanner_status": self.scanner_status,
        }
        if self.note:
            out["note"] = self.note
        if self.variants:
            out["variants"] = list(self.variants)
        return out

    @property
    def preferred_kind(self) -> str:
        """Nejdulezitejsi dostupny zdroj pri konfliktu vice vrstev.

        `generator_kind` popisuje, co umi fallback generator bez konkretniho
        skenu. Jakmile ale existuje zivy mapper-scan signal, je to data od
        skutecneho mapare a ma vyssi duveru nez ZABAGED i pseudo dosyp.
        """
        if self.scanner_status in SCAN_REAL_STATUSES:
            return GEN_MAPPER_SCAN
        return self.generator_kind


def capability_by_code(code: str | int) -> SymbolCapability:
    key = _alias_code(normalize_code(str(code)))
    try:
        return _BY_CODE[key]
    except KeyError as exc:
        raise KeyError(f"ISOM capability {key} neni v registru generatoru") from exc


def preferred_kind_by_code(code: str | int) -> str:
    """Vrati konfliktne preferovany zdroj pro dany ISOM kod."""
    return capability_by_code(code).preferred_kind


def generator_codes() -> tuple[str, ...]:
    """Kody, ktere generator exportuje do `.omap` podle capability registru."""
    return tuple(record.code for record in CAPABILITIES)


def capabilities_for_kind(kind: str) -> tuple[SymbolCapability, ...]:
    return tuple(record for record in CAPABILITIES if record.generator_kind == kind)


def summarize_by_kind(records: Iterable[SymbolCapability] = ()) -> dict[str, int]:
    """Spocita registry podle real/pseudo/mixed/mapper_scan.

    Prazdny iterable znamena "vezmi cely registr"; je to pohodlne pro CLI i
    testy, ale porad bez globalniho mutable stavu.
    """
    items = tuple(records) or CAPABILITIES
    out: dict[str, int] = {}
    for record in items:
        out[record.generator_kind] = out.get(record.generator_kind, 0) + 1
    return dict(sorted(out.items()))


def _rec(code: str, name: str, geom: str, kind: str, source: str,
         scanner: str = SCAN_NONE, note: str = "",
         variants: tuple[str, ...] = ()) -> SymbolCapability:
    return SymbolCapability(
        code=normalize_code(code),
        name=name,
        geom=geom,
        generator_kind=kind,
        generator_source=source,
        scanner_status=scanner,
        note=note,
        variants=tuple(normalize_code(v) for v in variants),
    )


# Drzime poradi exportu `.omap`. `generator/omap_export.py::USED_CODES` se z
# tohoto registru odvozuje, aby se seznam kodu a jejich puvod nerozesly.
CAPABILITIES: tuple[SymbolCapability, ...] = (
    _rec("101", "Contour", "line", GEN_REAL, "DMR 5G terrain"),
    _rec("102", "Index contour", "line", GEN_REAL, "DMR 5G terrain"),
    _rec("103", "Form line", "line", GEN_REAL, "DMR 5G terrain heuristic"),
    _rec("502", "Wide road", "line", GEN_REAL, "ZABAGED roads"),
    _rec("503", "Road", "line", GEN_REAL, "ZABAGED roads"),
    _rec("504", "Vehicle track", "line", GEN_REAL, "ZABAGED roads"),
    _rec("505", "Footpath", "line", GEN_REAL, "ZABAGED paths"),
    _rec("506", "Small footpath", "line", GEN_REAL, "ZABAGED paths"),
    _rec(
        "508",
        "Narrow ride",
        "line",
        GEN_REAL,
        "sparse ZABAGED ride/Cesta fallback; mapper scan preferred for completeness",
        SCAN_CANDIDATE,  # Png2Line revert Sez. 156: kanonický scope jen 304/305 (508 doménový gap) → kandidát, ne živý
        # Generátor emituje holý 508. Reálné mapy ale často používají varianty s pozadím
        # běhatelnosti; Png2Line je slučuje do jedné vizuální třídy dashed narrow ride.
        # ZABAGED průseky jsou silně neúplné (hlavní/udržované linie), proto je to jen
        # fallback generátoru, ne zdroj pravdy pro kompletnost 508.
        note="ZABAGED 508 is undercomplete; prefer mapper-scan/Png2Line signal where available.",
        variants=("508.1", "508.2", "508.3", "508.4"),
    ),
    _rec("304", "Crossable watercourse", "line", GEN_REAL, "ZABAGED watercourses", SCAN_LIVE_LINE),
    _rec("305", "Small crossable watercourse", "line", GEN_REAL, "ZABAGED watercourses", SCAN_LIVE_LINE),
    _rec("306", "Minor seasonal waterchannel", "line", GEN_REAL, "ZABAGED watercourses", SCAN_CANDIDATE),  # Png2Line revert Sez. 156 (živý jen 304/305)
    _rec(
        "309",
        "Narrow marsh",
        "line",
        GEN_MAPPER_SCAN,
        "real mapper scan line labels (Png2Line); no ZABAGED line source yet",
        SCAN_CANDIDATE,  # Png2Line revert Sez. 156: 309 narrow_marsh kolaboval (F1 0,000) → kandidát, ne živý
        note="Scan/model scope only until a vectorizer/export step emits 309 geometry. "
             "POZN.: generator_kind=mapper_scan je aspirativní (generátor 309 z dat nekreslí, Png2Line ho neumí) — k revizi.",
    ),
    _rec("301", "Uncrossable body of water", "area", GEN_REAL, "ZABAGED water areas", SCAN_AREA),
    _rec("521", "Building", "area", GEN_REAL, "ZABAGED buildings"),
    _rec("523", "Ruin", "area", GEN_REAL, "ZABAGED ruins"),
    _rec("510", "Power line, cableway or skilift", "line", GEN_REAL, "ZABAGED powerlines/cableways"),
    _rec("509", "Railway", "line", GEN_REAL, "ZABAGED railways/tramways"),
    _rec("501", "Paved area", "area", GEN_REAL, "ZABAGED paved areas", SCAN_AREA),
    _rec("501.1", "Paved area without boundary", "area", GEN_REAL, "ZABAGED/RUIAN urban base fill", SCAN_AREA, variants=("501",)),
    _rec("109", "Small knoll", "point", GEN_REAL, "DMR 5G local contour extrema", SCAN_CANDIDATE),
    _rec("110", "Small elongated knoll", "point", GEN_REAL, "DMR 5G local contour extrema", SCAN_CANDIDATE),
    _rec("111", "Small depression", "point", GEN_REAL, "DMR 5G local contour extrema", SCAN_CANDIDATE),
    _rec("204", "Boulder", "point", GEN_MIXED, "ZABAGED rock points + pseudo fill from rock mask", SCAN_LIVE_POINT),
    _rec("206", "Gigantic boulder or rock pillar", "area", GEN_REAL, "DMR 5G slope-derived rock relief", SCAN_AREA),
    _rec("207", "Boulder cluster", "point", GEN_REAL, "ZABAGED rock points", SCAN_CANDIDATE),
    _rec("208", "Boulder field", "area", GEN_REAL, "ZABAGED rock lines buffered to area", SCAN_AREA),
    _rec("210.1", "Stony ground individual dot", "point", GEN_PSEUDO, "pseudo fields inside real rock mask", SCAN_LIVE_POINT, variants=("210",)),
    _rec("512", "Bridge or tunnel", "line", GEN_REAL, "ZABAGED bridges/tunnels"),
    _rec("512.2", "Footbridge", "point", GEN_REAL, "ZABAGED footbridges", SCAN_CANDIDATE, variants=("512",)),
    _rec("401", "Open land", "area", GEN_REAL, "ZABAGED/RUIAN land cover", SCAN_AREA),
    _rec("403", "Rough open land", "area", GEN_MAPPER_SCAN, "separation from real mapper scan", SCAN_AREA),
    _rec("404", "Rough open land with scattered trees", "area", GEN_MAPPER_SCAN, "pattern separation from real mapper scan", SCAN_AREA),
    _rec("520", "Area that shall not be entered", "area", GEN_REAL, "ZABAGED/RUIAN land cover", SCAN_AREA),
    _rec("412.1", "Cultivated land pattern", "area", GEN_REAL, "ZABAGED/RUIAN cultivated land", SCAN_AREA, variants=("412",)),
    _rec("402", "Open land with scattered trees", "area", GEN_REAL, "ZABAGED maintained green areas", SCAN_AREA),
    _rec("402.1", "Open land with scattered bushes", "area", GEN_REAL, "ZABAGED maintained green areas", SCAN_AREA, variants=("402",)),
    _rec("524", "High tower", "point", GEN_REAL, "ZABAGED landmarks", SCAN_CANDIDATE),
    _rec("526", "Cairn", "point", GEN_REAL, "ZABAGED landmarks", SCAN_CANDIDATE),
    _rec("530", "Prominent man-made feature: ring", "point", GEN_REAL, "ZABAGED landmarks", SCAN_CANDIDATE),
    _rec("417", "Prominent large tree", "point", GEN_MIXED, "ZABAGED significant trees + pseudo density fill", SCAN_LIVE_POINT),
    _rec("418", "Prominent bush or small tree", "point", GEN_PSEUDO, "pseudo vegetation point density", SCAN_CANDIDATE),
    _rec("419", "Prominent vegetation feature", "point", GEN_PSEUDO, "pseudo vegetation point density", SCAN_LIVE_POINT),
    _rec("527", "Fodder rack", "point", GEN_PSEUDO, "pseudo man-made point density", SCAN_POC),
    _rec("525", "Small tower", "point", GEN_PSEUDO, "pseudo man-made point density", SCAN_POC),
    _rec("531", "Prominent man-made feature: x", "point", GEN_PSEUDO, "pseudo man-made point density", SCAN_LIVE_POINT),
    _rec("104", "Earth bank", "line", GEN_REAL, "ZABAGED line features"),
    _rec("107", "Erosion gully", "line", GEN_REAL, "ZABAGED line features"),
    _rec("513", "Wall", "line", GEN_REAL, "ZABAGED walls/ramparts", variants=("513.1",)),
    _rec("516", "Fence", "line", GEN_MIXED, "RUIAN garden boundary + pseudo fence type", note="ZABAGED fence layer does not exist."),
    _rec("517", "Ruined fence", "line", GEN_MIXED, "RUIAN garden boundary + pseudo fence type", note="Fence type is statistical, not surveyed."),
    _rec("518", "Impassable fence", "line", GEN_MIXED, "RUIAN garden boundary + pseudo fence type", note="Fence type is statistical, not surveyed."),
    _rec("519", "Crossing point", "point", GEN_REAL, "ZABAGED barriers on walls", SCAN_CANDIDATE),
    _rec("312", "Spring", "point", GEN_REAL, "ZABAGED water landmarks", SCAN_CANDIDATE),
    _rec("311", "Small fountain or well", "point", GEN_REAL, "ZABAGED water tanks/wells", SCAN_CANDIDATE),
    _rec("203.2", "Dangerous pit / cave", "point", GEN_REAL, "ZABAGED caves/pits", SCAN_CANDIDATE, variants=("203",)),
    _rec("308", "Marsh", "area", GEN_REAL, "ZABAGED marshes/peat bogs", SCAN_AREA),
    _rec("310", "Indistinct marsh", "area", GEN_MIXED, "real marsh geometry + pseudo indistinct split", SCAN_AREA),
    _rec("406", "Vegetation: slow running", "area", GEN_MIXED, "ZABAGED tree rows + real mapper scan separation", SCAN_AREA),
    _rec("407", "Vegetation: slow running, good visibility", "area", GEN_MAPPER_SCAN, "pattern separation from real mapper scan", SCAN_AREA),
    _rec("408", "Vegetation: walk", "area", GEN_MAPPER_SCAN, "separation from real mapper scan", SCAN_AREA),
    _rec("409", "Vegetation: walk, good visibility", "area", GEN_MAPPER_SCAN, "pattern separation from real mapper scan", SCAN_AREA),
    _rec("410", "Vegetation: fight", "area", GEN_MAPPER_SCAN, "separation from real mapper scan", SCAN_AREA),
    _rec("416", "Distinct vegetation boundary", "line", GEN_MAPPER_SCAN, "boundaries from separated real mapper scan areas"),
    _rec("416.1", "Distinct vegetation boundary, green variant", "line", GEN_MAPPER_SCAN, "boundaries from separated real mapper scan areas", variants=("416",)),
)


def _alias_code(code: str) -> str:
    # 210 je domenska agregace; generator do .omap zapisuje point variantu 210.1.
    if code == "210":
        return "210.1"
    return code


_BY_CODE = {record.code: record for record in CAPABILITIES}
for record in CAPABILITIES:
    for variant in record.variants:
        _BY_CODE.setdefault(variant, record)
