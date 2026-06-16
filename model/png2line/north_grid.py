"""north_grid.py — filtr magnetických poledníků po vektorizaci Png2Line.

Png2Line rozpoznává modré liniové symboly. Na reálných skenech se do stejné barvy
mohou trefit i magnetické severní linie: jsou rovné, rovnoběžné a v pravidelné
soustavě. Osamělá rovná voda ale nesmí zmizet. Proto filtrujeme až po vektorizaci
a diskriminátor je členství v pravidelném gridu, ne samotná rovnost.
"""

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class NorthGridConfig:
    """Prahy v paper µm. Záměrně konzervativní; rozestup gridu se NEhardcoduje.

    Rozestup poledníků závisí na měřítku mapy (300 m v terénu = 30 mm @ 1:10000,
    20 mm @ 1:15000, 40 mm @ 1:7500). Pevná konstanta by tiše selhala na jiném
    měřítku, proto periodu odvozujeme z naměřených offsetů (medián mezer mezi
    clustery) a tolerujeme ji RELATIVNĚ (`spacing_rel_tol`). `min_spacing_um` je
    jen sanity floor proti degenerovanému mikro-gridu ze splývajících fragmentů.
    """

    seed_angle_tol_deg: float = 4.0
    seed_min_straightness: float = 0.97
    seed_min_len_um: float = 8_000.0
    offset_cluster_tol_um: float = 4_000.0
    spacing_rel_tol: float = 0.25      # mezera smí být ±25 % odvozené periody
    min_spacing_um: float = 4_000.0    # pod tímto rozestupem grid neuznáváme
    min_grid_lines: int = 3
    assign_offset_tol_um: float = 800.0
    assign_max_dev_um: float = 800.0
    assign_angle_tol_deg: float = 10.0
    assign_min_straightness: float = 0.995
    assign_min_len_um: float = 800.0


@dataclass(frozen=True)
class NorthGridStats:
    """Diagnostika pro log a testy; indexy odkazují na původní pořadí polylines."""

    target_angle_deg: float | None
    grid_centers_um: tuple[float, ...]
    spacing_median_um: float | None
    spacing_std_um: float | None
    seed_removed_ids: tuple[int, ...]
    removed_ids: tuple[int, ...]


@dataclass(frozen=True)
class _PolyStats:
    idx: int
    pts: np.ndarray
    length_um: float
    straightness: float
    angle_deg: float
    offset_um: float


def filter_north_grid(
    polylines: list[list[tuple[float, float]]],
    config: NorthGridConfig = NorthGridConfig(),
) -> tuple[list[list[tuple[float, float]]], NorthGridStats]:
    """Odstraň polylines, které patří do pravidelné soustavy magnetických poledníků.

    Postup má dvě fáze:
    1. dlouhé a velmi rovné fragmenty najdou pravidelný grid;
    2. teprve na potvrzeném gridu se přidají krátké přerušené fragmenty.

    Krátký fragment musí celý ležet v úzkém pásu kolem grid linie. Tím chráníme
    skutečné vody, které jen náhodou grid protínají nebo vedou poblíž něj.
    """
    if len(polylines) < config.min_grid_lines:
        return polylines, _empty_stats()

    arrays = [np.asarray(poly, dtype=float) for poly in polylines]
    rough = [_poly_stats(i, pts, None) for i, pts in enumerate(arrays)]
    target_angle = _dominant_straight_angle(rough)
    if target_angle is None:
        return polylines, _empty_stats()

    stats = [_poly_stats(i, pts, target_angle) for i, pts in enumerate(arrays)]
    seeds = [
        s for s in stats
        if s.length_um >= config.seed_min_len_um
        and s.straightness >= config.seed_min_straightness
        and _angle_delta(s.angle_deg, target_angle) <= config.seed_angle_tol_deg
    ]
    clusters = _cluster_offsets(seeds, config.offset_cluster_tol_um)
    centers = [_cluster_center(c) for c in clusters]
    runs = _spacing_runs(centers, config)
    grid_cluster_ids = {i for run in runs for i in run}
    if not grid_cluster_ids:
        return polylines, NorthGridStats(target_angle, (), None, None, (), ())

    grid_centers = tuple(centers[i] for i in sorted(grid_cluster_ids))
    seed_removed_ids = {s.idx for i, c in enumerate(clusters) if i in grid_cluster_ids for s in c}
    removed_ids = set(seed_removed_ids)

    # Druhý průchod: po potvrzení gridu přidej jen krátké, velmi rovné úseky,
    # které celé leží v úzkém pásu kolem jedné poledníkové přímky.
    for s in stats:
        if s.idx in removed_ids:
            continue
        if s.length_um < config.assign_min_len_um:
            continue
        if s.straightness < config.assign_min_straightness:
            continue
        if _angle_delta(s.angle_deg, target_angle) > config.assign_angle_tol_deg:
            continue
        if any(
            abs(s.offset_um - center) <= config.assign_offset_tol_um
            and _max_offset_dev(s.pts, center, target_angle) <= config.assign_max_dev_um
            for center in grid_centers
        ):
            removed_ids.add(s.idx)

    kept = [poly for i, poly in enumerate(polylines) if i not in removed_ids]
    gaps = [grid_centers[i] - grid_centers[i - 1] for i in range(1, len(grid_centers))]
    spacing_median = float(np.median(gaps)) if gaps else None
    spacing_std = float(np.std(gaps)) if gaps else None
    grid_stats = NorthGridStats(
        target_angle_deg=float(target_angle),
        grid_centers_um=tuple(float(c) for c in grid_centers),
        spacing_median_um=spacing_median,
        spacing_std_um=spacing_std,
        seed_removed_ids=tuple(sorted(seed_removed_ids)),
        removed_ids=tuple(sorted(removed_ids)),
    )
    return kept, grid_stats


def _empty_stats() -> NorthGridStats:
    return NorthGridStats(None, (), None, None, (), ())


def _poly_stats(idx: int, pts: np.ndarray, target_angle_deg: float | None) -> _PolyStats:
    diffs = np.diff(pts, axis=0)
    seg_lens = np.hypot(diffs[:, 0], diffs[:, 1])
    length = float(seg_lens.sum())
    dx, dy = pts[-1] - pts[0]
    endpoint = float(math.hypot(dx, dy))
    straightness = endpoint / length if length else 0.0
    angle = math.degrees(math.atan2(dy, dx)) % 180.0
    if target_angle_deg is None:
        offset = float(np.mean(pts[:, 0]))
    else:
        normal = _normal(target_angle_deg)
        offset = float((pts.mean(axis=0) * normal).sum())
    return _PolyStats(idx, pts, length, straightness, angle, offset)


def _dominant_straight_angle(stats: list[_PolyStats]) -> float | None:
    """Najdi dominantní rodinu dlouhých rovných úseků bez předpokladu, že je to 90°."""
    pool = [s for s in stats if s.length_um >= 8_000.0 and s.straightness >= 0.995]
    if not pool:
        return None
    bins: dict[int, list[_PolyStats]] = {}
    for s in pool:
        key = int(round(s.angle_deg / 2.0) * 2)
        bins.setdefault(key, []).append(s)
    _, best = max(bins.items(), key=lambda kv: (len(kv[1]), sum(s.length_um for s in kv[1])))
    return float(np.median([s.angle_deg for s in best]))


def _angle_delta(a: float, b: float) -> float:
    """Nejmenší rozdíl úhlů na modulo-180 ose."""
    return abs(((a - b + 90.0) % 180.0) - 90.0)


def _normal(angle_deg: float) -> np.ndarray:
    th = math.radians(angle_deg)
    return np.array([-math.sin(th), math.cos(th)], dtype=float)


def _max_offset_dev(pts: np.ndarray, center_um: float, target_angle_deg: float) -> float:
    offsets = pts @ _normal(target_angle_deg)
    return float(np.max(np.abs(offsets - center_um)))


def _cluster_offsets(items: list[_PolyStats], tolerance_um: float) -> list[list[_PolyStats]]:
    clusters: list[list[_PolyStats]] = []
    for item in sorted(items, key=lambda s: s.offset_um):
        if not clusters:
            clusters.append([item])
            continue
        center = float(np.mean([x.offset_um for x in clusters[-1]]))
        if abs(item.offset_um - center) <= tolerance_um:
            clusters[-1].append(item)
        else:
            clusters.append([item])
    return clusters


def _cluster_center(cluster: list[_PolyStats]) -> float:
    weights = np.asarray([x.length_um for x in cluster], dtype=float)
    vals = np.asarray([x.offset_um for x in cluster], dtype=float)
    return float((vals * weights).sum() / weights.sum())


def _spacing_runs(centers: list[float], config: NorthGridConfig) -> list[list[int]]:
    """Najdi nejdelší běhy clusterů s KONZISTENTNÍM rozestupem.

    Periodu neznáme předem — odvodíme ji z dat jako medián mezer mezi sousedními
    clustery (robustní proti občasné odlehlé mezeře). Pak hledáme souvislé běhy,
    kde každá mezera leží v relativním pásmu kolem té periody. Tím detektor
    funguje napříč měřítky map, místo aby tiše minul grid s jiným rozestupem.
    """
    if len(centers) < config.min_grid_lines:
        return []
    gaps = [centers[i] - centers[i - 1] for i in range(1, len(centers))]
    period = float(np.median(gaps))         # perioda z dat, ne z konstanty
    if period < config.min_spacing_um:
        return []
    tol = config.spacing_rel_tol * period
    runs: list[list[int]] = []
    current = [0]
    for i in range(1, len(centers)):
        gap = centers[i] - centers[i - 1]
        if abs(gap - period) <= tol:
            current.append(i)
        else:
            if len(current) >= config.min_grid_lines:
                runs.append(current)
            current = [i]
    if len(current) >= config.min_grid_lines:
        runs.append(current)
    return runs
