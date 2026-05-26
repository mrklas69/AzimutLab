"""
generator.py — procedurální generátor výseku mapy pro orientační běh.

Implementuje řez specifikace docs/kb/generator-procedural.md:
  vrstevnice (§4.5) + bodové symboly lokálních extrémů (§4.10, knoll/depression
  z malých uzavřených vrstevnic) + cesty (§4.9 + §9, Dijkstra least-cost vázaná
  na terén + Catmull-Rom vyhlazení) + ground-truth masky (§8.1) + vektorový export
  vrstevnic (§9, GeoJSON s ISOM symboly 101/102; real = georef S-JTSK).

Hlavní myšlenka (§0): mapa NENÍ sada nakreslených čar, ale vrstvy odvozené ze
skalárního pole. Vrstevnice jsou izolinie spojitého výškového pole → z definice
se nikdy nekříží a nikdy nekončí ve vzduchu. Protože si vrstvy počítáme sami,
máme ke každé mapě ground-truth zdarma — každá vrstva je zároveň segmentační maska.

Stav (Sezení 11): generátor přestavujeme „znovu a lépe" — vrstvu po vrstvě, s
důrazem na vizuální věrnost. Dřívější plošné vrstvy (vegetace, paseky, bažiny,
balvany) byly vědomě zahozeny (vypadaly uměle → kazily by domain gap feederu pro
UC5); historie je v gitu (commit Sezení 10). Stavíme: vrstevnice → cesty → ...
"""

import argparse
import heapq  # binární halda pro Dijkstra least-cost trasování cest (§9)
import json
import math  # math.hypot: délka segmentu při čárkování cest + vzdálenost sousedů v Dijkstra
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import contourpy

# Konektory reálných dat (UC2 enabler) žijí ve sdíleném `connectors/` v kořeni LAB
# (Sez. 16) — ne v sandboxu, protože nejsou specifické pro generátor (zrcadlí UC2 v DAGu).
# Generátor je zatím jediný konzument; jejich složku přidáme na sys.path (fáze B, KISS —
# produkční balík/instalace až s monorepem, fáze A). Lazy importy `dmr`/`zabaged` níže pak
# fungují, ať generator.py běží přímo, nebo ho importuje batch.py.
_CONNECTORS_DIR = Path(__file__).resolve().parent.parent.parent / "connectors"
if str(_CONNECTORS_DIR) not in sys.path:
    sys.path.insert(0, str(_CONNECTORS_DIR))

# Barevná paleta (§5) — jediný zdroj pravdy je palette.py (DRY). Sousední modul:
# Python má složku spouštěného skriptu na sys.path, takže `palette` je viditelný,
# ať generator.py běží přímo, nebo ho importuje batch.py. Po řezu (Sez. 11) zbyly
# tři barvy: bílá (pozadí/les), hnědá (vrstevnice + body), černá (cesty).
from palette import C_WHITE, C_BROWN, C_BLACK, C_BLUE

# ---------- Rozměry mřížky a plátna, měřítko (§1) ----------
GW, GH = 170, 116        # výpočetní mřížka v buňkách: šířka × výška (poměr ≈ 1,466)
W, H = 672, 458          # výstupní plátno v pixelech
CONTOUR_STEP = 5         # ekvidistance vrstevnic [m]
CONTOUR_INDEX = 25       # zvýrazněná (hlavní) vrstevnice každých 25 m
BASE_ELEV = 700          # bazální nadmořská výška [m] — jen pro terrain="noise"
TILE_M = 1000.0          # reálný rozměr výseku [m] po kratší straně (S-J); delší se
                         # dopočítá v poměru GW/GH. Sjednoceno s dmr.fetch (tile_m)
                         # → georef vektoru sedí s výškopisem.
WORLD_W_M = TILE_M * (GW / GH)  # delší strana výseku (E-W) [m] — jedna pravda pro geo_bbox i .omap
MAP_SCALE = 10000        # měřítko mapy 1:MAP_SCALE — paper-space přepočet v .omap exportu (§9)

# ISOM symboly vrstevnic (§4.5, ověřeno O-Map Wiki) — pro vektorový export (§9).
# 103 Form line generátor zatím nedělá (rozšíření věrnosti).
ISOM_CONTOUR = 101       # základní vrstevnice (Contour)
ISOM_INDEX_CONTOUR = 102 # zvýrazněná každá pátá (Index contour)

# Bodové symboly lokálních extrémů (§4.10) — generalizace malých uzavřených
# vrstevnic. V ISOM se příliš malý kopeček/prohlubeň nekreslí prstencem vrstevnice,
# ale bodovou značkou. Detekce: uzavřená smyčka + plocha pod prahem + výška uvnitř.
# Kódy dle ISOM 2017-2 (Rev 6, 2024 — ověřeno proti oficiálnímu OOM symbol setu):
# 109/110/111. (Staré ISOM 2017 mělo 112/113/115; Rev 6 přečíslovalo — Sez. 13.)
ISOM_SMALL_KNOLL = 109        # lokální max, zhruba kulatý → hnědá tečka
ISOM_ELONGATED_KNOLL = 110    # lokální max, protáhlý → hnědá elipsa (Small elongated knoll)
ISOM_SMALL_DEPRESSION = 111   # lokální min → hnědý oblouk „⌣"
KNOLL_MAX_AREA_M2 = 600.0     # plocha smyčky pod tímto prahem → bodový symbol (laděno vizuálně)
KNOLL_ELONGATED_RATIO = 2.5   # poměr stran bbox smyčky nad tímto → 110 místo 109
SYMBOL_R = 3                  # základní poloměr bodového symbolu [px]
# ISOM kód → třída v GT masce mask_symbols.png (0 = pozadí) + lidský název
SYM_CLASS = {ISOM_SMALL_KNOLL: 1, ISOM_ELONGATED_KNOLL: 2, ISOM_SMALL_DEPRESSION: 3}
SYM_NAME = {ISOM_SMALL_KNOLL: "Small knoll", ISOM_ELONGATED_KNOLL: "Small elongated knoll",
            ISOM_SMALL_DEPRESSION: "Small depression"}

# Cesty (§4.9) — ISOM 2017-2 liniová hierarchie komunikací (ověřeno proti
# template_classic.omap). Dvě větve sdílejí render i symboly (izomorfismus):
#   --paths proc (default) = procedurální Dijkstra, jen 503/505 (hlavní/vedlejší);
#   --paths real           = reálné komunikace ze ZABAGED WFS (real-půlka §4.9, Sez. 16),
#                            plná hierarchie 502-506 dle ZABAGED→ISOM (viz zabaged.map_to_isom).
# Mapování kód↔kresba (Sez. 15): plná → 503 Road, pravidelná čárka → 505 Footpath
# (505 JE v ISOM čárkovaná; Sez. 13 zde mylně volila 507 s argumentem „505 je plná").
ISOM_WIDE_ROAD = 502          # silnice/ulice (zpevněná, autodoprava) → dvojitá linie (casing)
ISOM_ROAD = 503               # zpevněná cesta sjízdná autem → plná černá čára
ISOM_VEHICLE_TRACK = 504      # vozová (nezpevněná) cesta → čárkovaná silnější
ISOM_FOOTPATH = 505           # pěšina (udržovaná) → čárkovaná černá
ISOM_SMALL_FOOTPATH = 506     # malá/neudržovaná pěšina → jemně čárkovaná
PATH_NAME = {ISOM_WIDE_ROAD: "Wide road", ISOM_ROAD: "Road", ISOM_VEHICLE_TRACK: "Vehicle track",
             ISOM_FOOTPATH: "Footpath", ISOM_SMALL_FOOTPATH: "Small footpath"}
# ISOM kód → třída v mask_paths.png (0 = pozadí). 503=1 / 505=2 drží baseline proc
# větve (Sez. 8-15); 502/504/506 přidává reálná větev (Sez. 16) → zpětně kompatibilní.
PATH_CLASS = {ISOM_ROAD: 1, ISOM_FOOTPATH: 2,
              ISOM_WIDE_ROAD: 3, ISOM_VEHICLE_TRACK: 4, ISOM_SMALL_FOOTPATH: 5}
# ISOM kód → render styl: (mode, width [px], (dash, gap) | None). mode ∈ solid/dashed/casing.
# Tloušťky/čárkování laděné vizuálně (PIL bez antialiasingu → celočíselné šířky).
PATH_STYLE = {
    ISOM_WIDE_ROAD:      ("casing", 4, None),         # dvě černé hrany se světlou výplní (PoC aprox. silnice na šířku)
    ISOM_ROAD:           ("solid", 2, None),          # plná (≈ 1,5 px dle §4.9, PIL bere int)
    ISOM_VEHICLE_TRACK:  ("dashed", 2, (10.0, 4.0)),  # vozová: delší čárka, silnější
    ISOM_FOOTPATH:       ("dashed", 1, (7.0, 4.0)),   # pěšina: standardní čárka
    ISOM_SMALL_FOOTPATH: ("dashed", 1, (4.0, 4.0)),   # malá pěšina: kratší/jemnější čárka
}
# Terénně vázané vedení (§9): cesta = least-cost trasa mřížkou (Dijkstra), ne přímý
# splajn. Cena hrany = horizontální vzdálenost [m] + PATH_SLOPE_PENALTY·|Δvýška| [m]
# → pohyb podél vrstevnice levný, stoupání drahé → cesta traverzuje svah, nešplhá
# přes vrchol. Konstanta laděná vizuálně (vyšší = úzkostlivější vyhýbání stoupání).
# Cena hrany = vzdálenost × (1 + LIN·sklon + SQ·sklon²). Kvadratický člen tvrdě trestá
# srázy (cesta nešplhá přímo do svahu, ani když ji odpuzování tlačí jinam), lineární
# drží mírnou traverz-preferenci. (Sez. 13, oprava #3: čistě lineární penalty nechávala
# krátký sráz levnější než objížďka → jedna cesta vedla nejprudším stoupáním na mapě.)
PATH_SLOPE_LIN = 4.0          # lineární váha sklonu hrany (preference traverzu)
PATH_SLOPE_SQ = 45.0          # kvadratická váha (anti-sráz)
PATH_MAX_SLOPE = 0.5          # hrana strmější (>50 %) je pro cestu nepřekonatelná (tvrdý strop)
# Odpuzování cest (Sez. 13, #2): least-cost najde mezi blízkými konci JEDNU optimální
# trasu → dvě cesty by splynuly. Po nakreslení cesty zvýšíme cenu v jejím okolí, takže
# další cesta hledá jinudy → cesty se rozprostřou po terénu.
PATH_REPULSION = 60.0         # přičtená cena hrany v okolí už nakreslené cesty
PATH_REPULSION_R = 4          # poloměr odpuzování [buňky mřížky]
PATH_SIMPLIFY = 7             # zředění least-cost trasy: každý N-tý uzel → kontrolní body Catmull-Rom
PATH_EDGE_FRAC = (0.15, 0.85) # rozsah náhodného konce cesty na okraji mřížky (jako dřív)

# Voda (§4.x hydrografie) — ISOM 2017-2 (ověřeno proti template_classic.omap). Zatím jen
# reálná půlka (ZABAGED Polohopis WFS, Sez. 17, izomorfní s reálnými cestami): toky (linie)
# + plochy (polygon). Procedurální hydro jádro (D8) = budoucí noise-půlka. Mapování
# ZABAGED→ISOM viz zabaged.map_water_to_isom. Barva = modrá (C_BLUE z palety).
ISOM_CROSSABLE_WATERCOURSE = 304   # stálý pojmenovaný tok (hlavní) → plná modrá silnější
ISOM_SMALL_WATERCOURSE = 305       # stálý bezejmenný přítok → plná modrá tenčí
ISOM_SEASONAL_CHANNEL = 306        # občasný tok → čárkovaná modrá
ISOM_UNCROSSABLE_WATER = 301       # vodní plocha (rybník/tůň) → modrá výplň + břehová linie
WATER_NAME = {ISOM_CROSSABLE_WATERCOURSE: "Crossable watercourse",
              ISOM_SMALL_WATERCOURSE: "Small crossable watercourse",
              ISOM_SEASONAL_CHANNEL: "Minor/seasonal water channel",
              ISOM_UNCROSSABLE_WATER: "Uncrossable body of water"}
# ISOM kód → třída v mask_water.png (0 = pozadí). Toky 1-3, plocha 4.
WATER_CLASS = {ISOM_CROSSABLE_WATERCOURSE: 1, ISOM_SMALL_WATERCOURSE: 2,
               ISOM_SEASONAL_CHANNEL: 3, ISOM_UNCROSSABLE_WATER: 4}
# Render styl vodních LINIÍ: (mode, width [px], (dash, gap) | None). Izomorfní s PATH_STYLE.
WATER_LINE_STYLE = {
    ISOM_CROSSABLE_WATERCOURSE: ("solid", 2, None),       # hlavní tok plný silnější
    ISOM_SMALL_WATERCOURSE:     ("solid", 1, None),       # přítok plný tenčí
    ISOM_SEASONAL_CHANNEL:      ("dashed", 1, (6.0, 4.0)),# občasný čárkovaný
}

# ---------- Reálný terén (§8.5, Option 2): výchozí souřadnice dlaždice ----------
# Soví vrch (Lužické hory, povodí Svitávky) — vlastní terénně mapovaná oblast uživatele
# (proto výchozí lokalita; zná tu ground-truth). Členitý terén vhodný pro OB.
DEF_LAT, DEF_LON = 50.8214458, 14.6712747

# =====================================================================
#  Skalární pole (§2-3)
# =====================================================================
def _smooth_resize(grid: np.ndarray, w: int, h: int) -> np.ndarray:
    """Roztáhne hrubou mřížku `grid` na rozměr (h, w) bilineárně se smoothstep.

    Smoothstep 3t²−2t³ změkčí přechody mezi buňkami — bez něj by šum vypadal
    kostičkovaně. Celé je to vektorizované přes numpy (žádná Python smyčka přes pixely):
    `np.ix_(y, x)` vyrobí 2D výběr (h×w) ze čtyř rohových hodnot každé buňky.
    """
    gh0, gw0 = grid.shape
    # spojité souřadnice výstupních bodů přepočtené do soustavy hrubé mřížky
    xs = np.linspace(0, gw0 - 1, w)
    ys = np.linspace(0, gh0 - 1, h)
    x0 = np.floor(xs).astype(int)
    x1 = np.minimum(x0 + 1, gw0 - 1)
    y0 = np.floor(ys).astype(int)
    y1 = np.minimum(y0 + 1, gh0 - 1)
    tx = xs - x0
    ty = ys - y0
    sx = tx * tx * (3 - 2 * tx)   # smoothstep ve směru x (vektor délky w)
    sy = ty * ty * (3 - 2 * ty)   # smoothstep ve směru y (vektor délky h)
    g00 = grid[np.ix_(y0, x0)]
    g01 = grid[np.ix_(y0, x1)]
    g10 = grid[np.ix_(y1, x0)]
    g11 = grid[np.ix_(y1, x1)]
    # bilineární interpolace: nejdřív blend ve směru x (horní a dolní hrana), pak y
    top = g00 * (1 - sx)[None, :] + g01 * sx[None, :]
    bot = g10 * (1 - sx)[None, :] + g11 * sx[None, :]
    return top * (1 - sy)[:, None] + bot * sy[:, None]


def fractal(rng: np.random.Generator, base_scale: float, octaves: int) -> np.ndarray:
    """Fraktální value noise v [0,1] na mřížce (GH, GW) — §2.

    Sčítá několik oktáv šumu: každá další oktáva má jemnější mřížku (víc buněk)
    a poloviční amplitudu. Výsledek se min-max normalizuje do [0,1].
    """
    out = np.zeros((GH, GW), dtype=np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        c = max(2, round(base_scale * 1.9 ** o))           # počet buněk hrubé mřížky oktávy
        coarse = rng.random((c + 1, c + 1)).astype(np.float32)
        out += _smooth_resize(coarse, GW, GH) * amp
        total += amp
        amp *= 0.5
    out /= total
    return (out - out.min()) / (out.max() - out.min() + 1e-9)


# =====================================================================
#  Terénně vázané trasování (§9)
# =====================================================================
def _dijkstra_path(elev: np.ndarray, start: tuple[int, int], goal: tuple[int, int],
                   cell_w_m: float, cell_h_m: float, lin: float, sq: float,
                   extra_cost: np.ndarray, max_slope: float = float("inf")) -> list[tuple[int, int]]:
    """Least-cost trasa mřížkou z `start` do `goal` (8-sousedství), cena ~ sklon hrany.

    Cena hrany a→b = vzdálenost [m] × (1 + `lin`·sklon + `sq`·sklon²) + `extra_cost[b]`,
    kde sklon = |Δvýška|/vzdálenost. Pohyb podél vrstevnice (sklon≈0) levný; kvadratický
    člen činí srázy neúměrně drahé → trasa traverzuje svah a nešplhá přímo přes vrchol
    (§9, vylepšení přímého splajnu §4.9). `extra_cost` (GH×GW) je odpuzování od už
    nakreslených cest (#2), aby další cesta nesplynula s předchozí. Dijkstra přes binární
    haldu (heapq ze stdlib — žádný scipy). Halda drží `(vzdálenost, pořadí, uzel)`; monotónní
    pořadí je tie-break při shodné ceně → deterministická trasa. `max_slope` zakáže hrany
    strmější než strop (cesta nikdy nepřekročí sráz); při nedosažení goalu se strop zruší
    (fallback). Uzel = `gy*GW+gx`; `start`/`goal` i návratová trasa jsou (gx, gy) v mřížce.
    """
    gh, gw = elev.shape
    flat = elev.astype(np.float64).ravel()      # rychlý přístup elev[idx] bez 2D indexace
    extra = extra_cost.ravel()
    dist = np.full(gh * gw, np.inf)
    prev = np.full(gh * gw, -1, dtype=np.int64)
    s_idx = start[1] * gw + start[0]
    g_idx = goal[1] * gw + goal[0]
    dist[s_idx] = 0.0
    # 8 směrů + jejich horizontální vzdálenost [m] (ortogonální vs diagonální buňka)
    neigh = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    step_m = [math.hypot(dx * cell_w_m, dy * cell_h_m) for dx, dy in neigh]
    counter = 0
    heap: list[tuple[float, int, int]] = [(0.0, 0, s_idx)]
    while heap:
        d, _, u = heapq.heappop(heap)
        if u == g_idx:
            break
        if d > dist[u]:
            continue                            # zastaralý záznam (uzel už uzavřen levněji)
        uy, ux = divmod(u, gw)
        zu = flat[u]
        for (dx, dy), sm in zip(neigh, step_m):
            vx, vy = ux + dx, uy + dy
            if not (0 <= vx < gw and 0 <= vy < gh):
                continue
            v = vy * gw + vx
            slope = abs(flat[v] - zu) / sm            # sklon hrany = převýšení / vzdálenost
            if slope > max_slope:
                continue                              # nepřekonatelně strmá hrana — cesta tudy nejde
            nd = d + sm * (1.0 + lin * slope + sq * slope * slope) + extra[v]
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                counter += 1
                heapq.heappush(heap, (nd, counter, v))
    # goal nedosažen pod stropem sklonu (vzácné: oddělen souvislým srázem) → povol vše
    if prev[g_idx] == -1 and g_idx != s_idx and max_slope != float("inf"):
        return _dijkstra_path(elev, start, goal, cell_w_m, cell_h_m, lin, sq, extra_cost)
    # rekonstrukce trasy goal→start přes `prev`, pak obrátit na start→goal
    path: list[tuple[int, int]] = []
    cur = g_idx
    while cur != -1:
        cy, cx = divmod(cur, gw)
        path.append((cx, cy))
        if cur == s_idx:
            break
        cur = int(prev[cur])
    path.reverse()
    return path


def _add_repulsion(field: np.ndarray, cells: list[tuple[int, int]],
                   radius: int, amount: float) -> None:
    """Zvýší cenu v okolí buněk `cells` (čtvercové okno ±`radius`) o `amount`.

    Odpuzování cest (#2): po nakreslení cesty se její koridor „zdraží", takže
    Dijkstra další cestu vede jinudy. Hrubé čtvercové okno stačí — nejde o přesný
    profil, jen o roztlačení tras od sebe. Modifikuje `field` in-place.
    """
    gh, gw = field.shape
    for gx, gy in cells:
        y0, y1 = max(0, gy - radius), min(gh, gy + radius + 1)
        x0, x1 = max(0, gx - radius), min(gw, gx + radius + 1)
        field[y0:y1, x0:x1] += amount


# =====================================================================
#  Kreslicí helpery
# =====================================================================
def _catmull_rom(pts: list[tuple[float, float]], samples: int = 18) -> list[tuple[float, float]]:
    """Uniform Catmull-Rom splajn přes kontrolní body `pts` → hustá hladká polyčára.

    Catmull-Rom prokládá body hladkou křivkou, která jimi VŠEMI prochází (na rozdíl
    od Bézieru). Pro každou čtveřici sousedních bodů (p0,p1,p2,p3) generuje úsek
    mezi p1 a p2; tečna v p1/p2 je dána směrem (p2−p0)/(p3−p1). Krajní body
    zdvojíme (clamp), aby splajn prošel i prvním a posledním waypointem.
    `samples` = počet vzorků na úsek (víc = hladší).
    """
    if len(pts) < 3:
        return list(pts)   # na splajn je potřeba aspoň 3 body, jinak vrať přímku
    P = [pts[0]] + list(pts) + [pts[-1]]   # zdvojení krajních pro tečny na koncích
    out: list[tuple[float, float]] = []
    # iterujeme čtveřice (i..i+3); úsek se kreslí mezi prostředními dvěma (p1,p2)
    for i in range(len(P) - 3):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            # bazická matice Catmull-Rom (tension 0,5) zvlášť pro x a y
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(pts[-1])   # dokresli poslední bod (smyčka končí na t<1 posledního úseku)
    return out


def _draw_dashed(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                 pts: list[tuple[float, float]], color: tuple, cls: int,
                 dash: float = 7.0, gap: float = 4.0, width: int = 1) -> None:
    """Vykreslí čárkovanou linii podél polyčáry `pts` na mapu i do GT masky.

    PIL nemá nativní čárkovanou čáru. Jdeme po polyčáře a podle DÉLKY OBLOUKU
    střídáme čárku (`dash`) a mezeru (`gap`) — vzor je tak rovnoměrný bez ohledu
    na hustotu bodů splajnu. `pos` = celková ujetá vzdálenost; fáze ve vzoru
    (`pos % pattern`) určí, jestli jsme v čárce, nebo v mezeře. Kreslí se zároveň
    barvou `color` na mapu (`draw`) a hodnotou třídy `cls` do masky (`mdraw`).
    """
    if len(pts) < 2:
        return
    pattern = dash + gap
    pos = 0.0
    # zip(pts, pts[1:]) iteruje dvojice sousedních bodů = jednotlivé úsečky polyčáry
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg == 0.0:
            continue
        d = 0.0
        while d < seg:
            phase = pos % pattern
            in_dash = phase < dash
            # zbývající délka aktuální fáze (čárky nebo mezery)
            remain = (dash - phase) if in_dash else (pattern - phase)
            step = min(remain, seg - d)
            if in_dash:
                t0, t1 = d / seg, (d + step) / seg
                ax, ay = x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0
                bx, by = x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1
                draw.line([ax, ay, bx, by], fill=color, width=width)
                mdraw.line([ax, ay, bx, by], fill=cls, width=width)
            d += step
            pos += step


def _draw_line_symbol(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                      curve_px: list[tuple[float, float]], color: tuple,
                      mode: str, width: int, dash: tuple | None, cls: int) -> None:
    """Generický liniový symbol na mapu (`draw`) + třída do GT masky (`mdraw`).

    Jediná kreslicí logika pro VŠECHNY liniové symboly (izomorfismus / DRY): cesty
    (černá, PATH_STYLE) i vodní toky (modrá, WATER_LINE_STYLE) přes ni jdou stejně,
    liší se jen `color`/`mode`/`dash`. `solid` = plná, `dashed` = čárkovaná (dle
    dash/gap), `casing` = silná barva + tenčí bílá výplň (jen silnice 502 — PoC
    aproximace dvojité linie „na šířku"). Maska dostává `cls` místo barvy.
    """
    if len(curve_px) < 2:
        return
    if mode == "solid":
        draw.line(curve_px, fill=color, width=width)
        mdraw.line(curve_px, fill=cls, width=width)
    elif mode == "dashed":
        d, g = dash
        _draw_dashed(draw, mdraw, curve_px, color, cls, dash=d, gap=g, width=width)
    else:  # casing: silná barva, přes ni tenčí bílá → dojem dvou paralelních hran
        draw.line(curve_px, fill=color, width=width)
        draw.line(curve_px, fill=C_WHITE, width=max(1, width - 2))
        mdraw.line(curve_px, fill=cls, width=width)


def _draw_path(draw: ImageDraw.ImageDraw, pdraw: ImageDraw.ImageDraw,
               curve_px: list[tuple[float, float]], code: int) -> None:
    """Cesta (černá) dle ISOM render stylu (PATH_STYLE) — tenký wrapper nad _draw_line_symbol."""
    mode, width, dash = PATH_STYLE[code]
    _draw_line_symbol(draw, pdraw, curve_px, C_BLACK, mode, width, dash, PATH_CLASS[code])


def _draw_water_line(draw: ImageDraw.ImageDraw, wdraw: ImageDraw.ImageDraw,
                     curve_px: list[tuple[float, float]], code: int) -> None:
    """Vodní tok (modrá) dle WATER_LINE_STYLE — wrapper nad _draw_line_symbol (izomorfní s cestou)."""
    mode, width, dash = WATER_LINE_STYLE[code]
    _draw_line_symbol(draw, wdraw, curve_px, C_BLUE, mode, width, dash, WATER_CLASS[code])


def _draw_water_area(draw: ImageDraw.ImageDraw, wdraw: ImageDraw.ImageDraw,
                     ring_px: list[tuple[float, float]], code: int) -> None:
    """Vodní plocha (ISOM 301): modrá výplň + černá břehová linie na mapu + třída do masky.

    PIL polygon vyplní uzavřený prstenec; `outline` dá břehovou linii (ISOM 301 = výplň
    s bank line). Maska dostane plnou výplň třídou WATER_CLASS (plošná GT, ne jen obrys).
    """
    if len(ring_px) < 3:
        return
    draw.polygon(ring_px, fill=C_BLUE, outline=C_BLACK)
    wdraw.polygon(ring_px, fill=WATER_CLASS[code])   # maska = plná šířka silnice


def _write_contours_geojson(features: list[tuple], bbox: tuple, crs_epsg: int | None,
                            out_path: Path) -> int:
    """Zapíše vrstevnice jako GeoJSON FeatureCollection (vektor, §9). Vrací počet linií.

    Klíčová myšlenka: vrstevnice z contourpy UŽ JSOU polylinie (ne pixely) — jen je
    místo rasterizace do PNG zapíšeme jako vektor s ISOM symbolem. Žádná vektorizace
    rastru (AutoTrace) tu netřeba; jdeme z přesného zdroje.

    `features` = seznam (line, symbol_code); `line` je pole bodů (N×2) v souřadnicích
    MŘÍŽKY (gx∈0..GW-1, gy∈0..GH-1, sever nahoře). `bbox`=(xmin,ymin,xmax,ymax) ve
    world metrech → lineární přepočet mřížka→svět. Osa Y se PŘEVRACÍ: gy=0 je horní
    řádek = sever = ymax. `crs_epsg` (real=5514) nebo None pro lokální metry (noise).
    """
    xmin, ymin, xmax, ymax = bbox
    sx = (xmax - xmin) / (GW - 1)   # metrů na buňku mřížky, osa x
    sy = (ymax - ymin) / (GH - 1)   # metrů na buňku mřížky, osa y
    names = {ISOM_CONTOUR: "Contour", ISOM_INDEX_CONTOUR: "Index contour"}
    geo_features = []
    for line, code in features:
        # mřížka → world metry; round na cm stačí (zdrojový grid je 2 m nativně)
        coords = [[round(xmin + float(gx) * sx, 2), round(ymax - float(gy) * sy, 2)]
                  for gx, gy in line]
        if len(coords) < 2:          # degenerátní linie (0-1 bod) přeskoč
            continue
        geo_features.append({
            "type": "Feature",
            "properties": {"symbol": code, "symbol_name": names[code]},
            "geometry": {"type": "LineString", "coordinates": coords},
        })
    fc: dict = {"type": "FeatureCollection", "features": geo_features}
    # CRS member: GeoJSON-2008 rozšíření (mimo RFC 7946, ale OOM / QGIS / OCAD ho čtou)
    # — u reálného terénu nese S-JTSK, ať mapa sedí na správné místo při importu.
    if crs_epsg is not None:
        fc["crs"] = {"type": "name",
                     "properties": {"name": f"urn:ogc:def:crs:EPSG::{crs_epsg}"}}
    out_path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    return len(geo_features)


def _polygon_area(pts: np.ndarray) -> float:
    """Plocha uzavřeného polygonu (shoelace), absolutní, v jednotkách vstupu na druhou.

    Shoelace (Gaussova) formule: 0,5·|Σ (xᵢ·yᵢ₊₁ − xᵢ₊₁·yᵢ)|. `np.roll(.., -1)`
    posune pole o jeden prvek (cyklicky) → spáruje sousední vrcholy. Uzavřený
    prstenec z contourpy má první bod == poslední; duplicitní hrana má nulovou plochu.
    """
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _classify_loop(line: np.ndarray, level: float, elev: np.ndarray,
                   cell_w_m: float, cell_h_m: float) -> dict | None:
    """Rozhodne, zda uzavřená malá smyčka vrstevnice je bodový extrém (§4.10).

    Vrací záznam symbolu `{symbol, gx, gy, horiz}` (souřadnice mřížky), nebo None,
    pokud se má `line` kreslit jako normální vrstevnice. Metoda: uzavřenost
    + plocha pod ISOM prahem + výška uvnitř smyčky vs úroveň vrstevnice.
    """
    # uzavřenost: contourpy vrací vnitřní smyčky s prvním bodem == poslední. Linie
    # dotýkající se okraje plátna mají různé konce → nejsou smyčka → normální vrstevnice.
    if not np.allclose(line[0], line[-1]):
        return None
    # plocha smyčky shoelace (souřadnice mřížky) → m² přes velikost buňky
    area_m2 = _polygon_area(line) * cell_w_m * cell_h_m
    if area_m2 >= KNOLL_MAX_AREA_M2:
        return None                            # dost velká → kreslit jako vrstevnici
    # centroid (průměr vrcholů stačí pro malou ~konvexní smyčku); výška v nejbližší buňce
    cx, cy = float(line[:, 0].mean()), float(line[:, 1].mean())
    ix = int(np.clip(round(cx), 0, GW - 1))    # gx = sloupec, gy = řádek
    iy = int(np.clip(round(cy), 0, GH - 1))
    if float(elev[iy, ix]) > level:
        # lokální maximum → kopeček. Protáhlý? poměr stran bounding boxu smyčky
        w = float(line[:, 0].max() - line[:, 0].min())
        h = float(line[:, 1].max() - line[:, 1].min())
        if max(w, h) / (min(w, h) + 1e-9) >= KNOLL_ELONGATED_RATIO:
            return {"symbol": ISOM_ELONGATED_KNOLL, "gx": cx, "gy": cy, "horiz": w >= h}
        return {"symbol": ISOM_SMALL_KNOLL, "gx": cx, "gy": cy, "horiz": True}
    return {"symbol": ISOM_SMALL_DEPRESSION, "gx": cx, "gy": cy, "horiz": True}   # lokální min


def _draw_point_symbol(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                       ps: dict) -> None:
    """Nakreslí jeden bodový symbol extrému na mapu (`draw`) i do GT masky (`mdraw`).

    Maska dostává místo barvy ID třídy (SYM_CLASS) — z mask_symbols.png je tak rovnou
    multi-class segmentační GT. Mřížka → pixely stejným přepočtem jako vrstevnice.
    """
    px = ps["gx"] / (GW - 1) * W
    py = ps["gy"] / (GH - 1) * H
    code = ps["symbol"]
    cls = SYM_CLASS[code]
    r = SYMBOL_R
    if code == ISOM_SMALL_KNOLL:
        box = [px - r, py - r, px + r, py + r]          # hnědá vyplněná tečka
        draw.ellipse(box, fill=C_BROWN)
        mdraw.ellipse(box, fill=cls)
    elif code == ISOM_ELONGATED_KNOLL:
        # protáhlá elipsa podél delší osy smyčky (vodorovně, nebo svisle)
        box = ([px - 2 * r, py - r, px + 2 * r, py + r] if ps["horiz"]
               else [px - r, py - 2 * r, px + r, py + 2 * r])
        draw.ellipse(box, fill=C_BROWN)
        mdraw.ellipse(box, fill=cls)
    else:  # ISOM_SMALL_DEPRESSION — hnědý oblouk „⌣" otevřený nahoru (spodní půlkruh)
        box = [px - r, py - r, px + r, py + r]
        # PIL arc: úhly po směru hodin od 3 hodin; 0..180 = spodní půlkruh (y roste dolů)
        draw.arc(box, 0, 180, fill=C_BROWN, width=2)
        mdraw.arc(box, 0, 180, fill=cls, width=2)


def _build_meta(seed: int, rug: float, det: float, terrain: str, paths_mode: str,
                water_mode: str, lat: float, lon: float, elev: np.ndarray, crs_epsg: int | None,
                n_contours: int, n_paths: int, paths_info: list[dict],
                point_symbols: list[dict], water_info: list[dict], omap_info: dict) -> dict:
    """Sestaví obsah meta.json: parametry, původ terénu, legendu GT tříd, info o exportech.

    Vyčleněno z generate() (SLAP, Sez. 15): orchestrace kreslení vrstev a deklarativní
    sestavení metadat jsou dvě úrovně abstrakce. Vysoký počet parametrů je daň za to, že
    meta agreguje výstupy všech vrstev — alternativou byl 45řádkový inline dict v generate().
    """
    # cesty: legendu symbolů/tříd stavíme dynamicky ze SKUTEČNĚ použitých ISOM kódů
    # (proc dělá 503/505; real 502-506 dle ZABAGED→ISOM) — jeden zdroj pravdy PATH_NAME/PATH_CLASS.
    used_path_codes = sorted({p["symbol"] for p in paths_info})
    used_water_codes = sorted({w["symbol"] for w in water_info})
    return {
        "seed": seed,
        "params": {"rug": rug, "det": det},
        # původ výškopisu — pro reprodukovatelnost a atribuci (real = ČÚZK DMR 5G)
        "terrain": ({"source": "noise"} if terrain != "real" else {
            "source": "cuzk_dmr5g", "lat": lat, "lon": lon,
            "elev_min_m": round(float(elev.min()), 2),
            "elev_max_m": round(float(elev.max()), 2),
            "licence": "CC BY 4.0 (ČÚZK)",
        }),
        "grid": [GW, GH],
        "canvas": [W, H],
        "scale": "1:10000",
        "contour_step_m": CONTOUR_STEP,
        "contour_index_m": CONTOUR_INDEX,
        # vektorový export vrstevnic (§9): formát, CRS, počet linií, ISOM symboly
        "contours_vector": {
            "file": "contours.geojson",
            "crs": ("EPSG:5514" if crs_epsg else "local_m"),
            "n_lines": n_contours,
            "symbols": {"101": "Contour", "102": "Index contour"},
        },
        # cesty (§4.9): počet, GT maska, zdroj, ISOM symboly + třídy masky (dynamicky)
        "paths": {
            "count": n_paths,
            "mask": "mask_paths.png",
            # proc = Dijkstra least-cost (§9, cena ~ sklon); real = reálné komunikace ZABAGED WFS
            "source": ("cuzk_zabaged" if paths_mode == "real" else "procedural_dijkstra"),
            "symbols": {str(c): PATH_NAME[c] for c in used_path_codes},
            "classes": {"0": "pozadí",
                        **{str(PATH_CLASS[c]): f"{c} {PATH_NAME[c]}" for c in used_path_codes}},
            "items": paths_info,
            # reálné cesty = ČÚZK open data → atribuce povinná (CC BY 4.0)
            **({"licence": "CC BY 4.0 (ČÚZK ZABAGED)"} if paths_mode == "real" else {}),
        },
        # voda (hydrografie): toky + plochy ze ZABAGED WFS (real-půlka, Sez. 17). Sekce
        # jen když water_mode != off; symboly/třídy dynamicky ze SKUTEČNĚ použitých kódů.
        **({"water": {
            "count": len(water_info),
            "mask": "mask_water.png",
            "source": "cuzk_zabaged",
            "symbols": {str(c): WATER_NAME[c] for c in used_water_codes},
            "classes": {"0": "pozadí",
                        **{str(WATER_CLASS[c]): f"{c} {WATER_NAME[c]}" for c in used_water_codes}},
            "items": water_info,
            "licence": "CC BY 4.0 (ČÚZK ZABAGED)",
        }} if water_mode == "real" else {}),
        # bodové symboly lokálních extrémů (§4.10) z malých uzavřených vrstevnic —
        # detekční anotace (COCO/YOLO styl): symbol, název, pozice (mřížka i pixely).
        # GT maska = mask_symbols.png (třídy viz symbol_classes).
        "point_symbols": [
            {"symbol": ps["symbol"], "symbol_name": SYM_NAME[ps["symbol"]],
             "grid": [round(ps["gx"], 2), round(ps["gy"], 2)],
             "px": [round(ps["gx"] / (GW - 1) * W, 1), round(ps["gy"] / (GH - 1) * H, 1)]}
            for ps in point_symbols
        ],
        "symbol_classes": {"0": "pozadí", "1": "109 Small knoll",
                           "2": "110 Small elongated knoll", "3": "111 Small depression"},
        # .omap export (§9): vrstevnice + cesty + body, template-based (vlastní čistý ISOM template)
        "omap": omap_info,
    }


# =====================================================================
#  Cesty (§4.9): procedurální (Dijkstra) | reálné (ZABAGED WFS)
# =====================================================================
def _generate_proc_paths(rng: np.random.Generator, elev: np.ndarray,
                         draw: ImageDraw.ImageDraw, pdraw: ImageDraw.ImageDraw,
                         cell_w_m: float, cell_h_m: float, det: float) -> tuple[list, list]:
    """Procedurální cesty (§4.9 + §9): Dijkstra least-cost trasa terénem + Catmull-Rom.

    Konce na protilehlých okrajích; mezi nimi least-cost trasa s cenou ~ sklon (traverz,
    nešplhá přes vrchol). Surová 8-směrová trasa se zředí a vyhladí splajnem. Hlavní cesta
    503 (plná), vedlejší 505 (čárkovaná). Vrací (path_features grid, paths_info); kreslí
    na `draw`/`pdraw`. `det` řídí počet cest.
    """
    n_paths = 1 + round(det * 1.6)
    lo_f, hi_f = PATH_EDGE_FRAC
    paths_info: list[dict] = []
    path_features: list[tuple] = []                 # (curve grid, ISOM kód) pro vektor/OMAP
    path_repulsion = np.zeros((GH, GW))             # rostoucí cena kolem nakreslených cest (#2)
    for k in range(n_paths):
        horizontal = bool(rng.integers(0, 2))       # orientace: vodorovná (L→P) nebo svislá (H→D)
        if horizontal:                              # konce na levém a pravém okraji mřížky
            start = (0, int(round(float(rng.uniform(lo_f, hi_f)) * (GH - 1))))
            goal = (GW - 1, int(round(float(rng.uniform(lo_f, hi_f)) * (GH - 1))))
        else:                                       # konce na horním a dolním okraji
            start = (int(round(float(rng.uniform(lo_f, hi_f)) * (GW - 1))), 0)
            goal = (int(round(float(rng.uniform(lo_f, hi_f)) * (GW - 1))), GH - 1)
        cells = _dijkstra_path(elev, start, goal, cell_w_m, cell_h_m,
                               PATH_SLOPE_LIN, PATH_SLOPE_SQ, path_repulsion, PATH_MAX_SLOPE)
        _add_repulsion(path_repulsion, cells, PATH_REPULSION_R, PATH_REPULSION)  # odpuzuj další cesty
        # zředění (každý N-tý uzel + poslední) → kontrolní body; Catmull-Rom vyhladí
        # 8-směrová zalomení. Křivku držíme v souřadnicích MŘÍŽKY → stejný zdroj pro
        # render (px) i vektorový/OMAP export.
        ctrl = cells[::PATH_SIMPLIFY]
        if ctrl[-1] != cells[-1]:
            ctrl.append(cells[-1])
        curve_grid = _catmull_rom([(float(gx), float(gy)) for gx, gy in ctrl])
        curve_px = [(gx / (GW - 1) * W, gy / (GH - 1) * H) for gx, gy in curve_grid]
        code = ISOM_ROAD if k == 0 else ISOM_FOOTPATH    # hlavní plná / vedlejší čárkovaná
        _draw_path(draw, pdraw, curve_px, code)
        path_features.append((curve_grid, code))
        paths_info.append({"symbol": code, "symbol_name": PATH_NAME[code],
                           "orientation": "H" if horizontal else "V"})
    return path_features, paths_info


def _generate_real_paths(draw: ImageDraw.ImageDraw, pdraw: ImageDraw.ImageDraw,
                         lat: float, lon: float, geo_bbox: tuple) -> tuple[list, list]:
    """Reálné cesty (real-půlka §4.9): komunikace ze ZABAGED WFS pro tentýž výsek.

    Stáhne komunikace (zabaged.fetch_paths), mapuje na ISOM (zabaged.map_to_isom),
    transformuje S-JTSK → grid (inverze _write_contours_geojson: Y-flip, sever = ymax =
    gy 0) → px a kreslí dle ISOM stylu. Reálné linie jsou už hladké (vektor z reality) →
    žádný splajn. Výsek je TENTÝŽ jako u DMR vrstevnic (sdílený build_bbox) → cesty sednou
    na terén. Vrací (path_features grid, paths_info).
    """
    from zabaged import fetch_paths, map_to_isom
    xmin, ymin, xmax, ymax = geo_bbox
    feats = fetch_paths(lat, lon, GW, GH, TILE_M)
    paths_info: list[dict] = []
    path_features: list[tuple] = []
    for f in feats:
        code = map_to_isom(f["layer"], f["props"])
        for line in f["lines"]:
            curve_grid = [((x - xmin) / (xmax - xmin) * (GW - 1),
                           (ymax - y) / (ymax - ymin) * (GH - 1)) for x, y in line]
            curve_px = [(gx / (GW - 1) * W, gy / (GH - 1) * H) for gx, gy in curve_grid]
            if len(curve_px) < 2:
                continue
            _draw_path(draw, pdraw, curve_px, code)
            path_features.append((curve_grid, code))
            paths_info.append({"symbol": code, "symbol_name": PATH_NAME[code],
                               "layer": f["layer"]})
    return path_features, paths_info


def _generate_real_water(draw: ImageDraw.ImageDraw, wdraw: ImageDraw.ImageDraw,
                         lat: float, lon: float, geo_bbox: tuple) -> tuple[list, list, list]:
    """Reálná voda (real-půlka hydrografie, Sez. 17): toky + plochy ze ZABAGED WFS.

    Mirror _generate_real_paths: stáhne vodu (zabaged.fetch_water), mapuje na ISOM
    (map_water_to_isom; None = podzemní tok → přeskočit), transformuje S-JTSK → grid
    (Y-flip, sever = ymax) → px a kreslí (toky linie 304/305/306, plochy polygon 301).
    Tentýž výsek jako DMR/cesty (sdílený build_bbox) → voda sedne na terén. Reálné linie
    jsou hladké (vektor z reality) → žádný splajn. Vrací (line_features, area_features,
    water_info) v souřadnicích MŘÍŽKY (zdroj pro vektor/OMAP).
    """
    from zabaged import fetch_water, map_water_to_isom
    xmin, ymin, xmax, ymax = geo_bbox
    line_feats, area_feats = fetch_water(lat, lon, GW, GH, TILE_M)

    def to_grid(x: float, y: float) -> tuple[float, float]:
        return ((x - xmin) / (xmax - xmin) * (GW - 1), (ymax - y) / (ymax - ymin) * (GH - 1))

    line_features: list[tuple] = []
    area_features: list[tuple] = []
    water_info: list[dict] = []
    for f in line_feats:
        code = map_water_to_isom(f["layer"], f["props"])
        if code is None:                       # podzemní tok → nekreslit
            continue
        for line in f["lines"]:
            grid = [to_grid(x, y) for x, y in line]
            px = [(gx / (GW - 1) * W, gy / (GH - 1) * H) for gx, gy in grid]
            if len(px) < 2:
                continue
            _draw_water_line(draw, wdraw, px, code)
            line_features.append((grid, code))
            water_info.append({"symbol": code, "symbol_name": WATER_NAME[code], "kind": "line",
                               "layer": f["layer"], "name": f["props"].get("jmeno")})
    for f in area_feats:
        code = map_water_to_isom(f["layer"], f["props"])
        if code is None:
            continue
        for ring in f["rings"]:
            grid = [to_grid(x, y) for x, y in ring]
            px = [(gx / (GW - 1) * W, gy / (GH - 1) * H) for gx, gy in grid]
            if len(px) < 3:
                continue
            _draw_water_area(draw, wdraw, px, code)
            area_features.append((grid, code))
            water_info.append({"symbol": code, "symbol_name": WATER_NAME[code], "kind": "area",
                               "layer": f["layer"]})
    return line_features, area_features, water_info


# =====================================================================
#  Hlavní generování
# =====================================================================
def generate(seed: int, rug: float, det: float, out_dir: str,
             terrain: str = "noise", paths: str = "proc", water: str = "off",
             lat: float = DEF_LAT, lon: float = DEF_LON) -> Path:
    """Vygeneruje jednu instanci mapy + GT masky + vektor vrstevnic do `out_dir`.

    Vrací cestu k složce. `terrain="noise"` (default) = fraktální šum (Option 1).
    `terrain="real"` = reálný výškopis ČÚZK DMR 5G pro (lat, lon) místo šumu
    (Option 2, §8.5). U reálného terénu se `rug` na výškopis neuplatní (terén je
    daný realitou).

    `paths="proc"` (default) = procedurální Dijkstra cesty (§9); `paths="real"` =
    reálné komunikace ze ZABAGED WFS (real-půlka §4.9). `real` VYŽADUJE `terrain="real"`
    — reálné cesty mají S-JTSK souřadnice a párují se přes sdílený výsek; noise výsek
    je v lokálních metrech bez georef → spárovat nelze.

    Vrstvy (z-order): vrstevnice (§4.5) → cesty (§4.9) → bodové symboly extrémů
    (§4.10). `rug` řídí členitost terénu (jen noise), `det` počet proc cest.

    Malé uzavřené vrstevnice (lokální extrémy) se generalizují na bodové symboly
    (§4.10): kopeček 109/110, prohlubeň 111 — místo prstence se kreslí značka a GT
    se zapíše do `mask_symbols.png` + seznam `point_symbols` v meta.json.

    Vedle rastru (rgb.png + GT masky) zapisuje `contours.geojson` — vrstevnice jako
    vektorové linie s ISOM symbolem (101/102), georeferencované v S-JTSK pro real
    terén (§9). To je „skutečný vektor", ne pixely: contourpy dává polylinie přímo.
    """
    if paths == "real" and terrain != "real":
        raise ValueError("--paths real vyžaduje --terrain real (reálné cesty potřebují "
                         "S-JTSK georef výseku; noise terén je v lokálních metrech).")
    if water == "real" and terrain != "real":
        raise ValueError("--water real vyžaduje --terrain real (reálná voda potřebuje "
                         "S-JTSK georef výseku; noise terén je v lokálních metrech).")
    # Požadavek je jen DETERMINISMUS (stejný seed + parametry → stejná mapa), proto
    # stačí korektní numpy generátor (PCG64); bitová shoda s JS referencí netřeba.
    rng = np.random.default_rng(seed)

    # --- výškopis: reálný (DMR 5G) nebo syntetický šum ---
    if terrain == "real":
        # Lazy import: pyproj je závislost jen pro Option 2; Option 1 zůstává offline.
        from dmr import fetch_elevation_grid, build_bbox
        elev = fetch_elevation_grid(lat, lon, GW, GH, tile_m=TILE_M)  # reálné metry (GH, GW), sever nahoře
        # georef pro vektorový export: skutečný S-JTSK bbox výseku (stejný TILE_M jako fetch)
        geo_bbox = build_bbox(lat, lon, GW, GH, TILE_M)
        crs_epsg: int | None = 5514                              # S-JTSK / Křovák
    else:
        hbase = fractal(rng, 1.6 + rug * 2.6, 3 + round(rug * 2))  # výškopis (členitost = rug)
        vrange = 25 + rug * 90                                    # převýšení: víc členitosti → víc vrstevnic
        elev = BASE_ELEV + hbase * vrange                         # nadmořská výška [m]
        # georef šumu: skutečné umístění neznáme → lokální metry od (0,0), stejná
        # geometrie výseku jako real (TILE_M × poměr GW/GH). crs=None.
        geo_bbox = (0.0, 0.0, WORLD_W_M, TILE_M)
        crs_epsg = None

    # --- plátno: bílá = průběžný les (§4.1) ---
    rgb = np.full((H, W, 3), C_WHITE, dtype=np.uint8)
    img = Image.fromarray(rgb, mode="RGB")
    draw = ImageDraw.Draw(img)

    # --- vrstevnice (§4.5): izolinie pole `elev` přes contourpy (marching squares) ---
    cmask_img = Image.new("L", (W, H), 0)           # samostatná GT maska vrstevnic
    cdraw = ImageDraw.Draw(cmask_img)
    # LineType.Separate → .lines(level) vrátí prostý seznam polí bodů (N×2) v souřadnicích mřížky
    cont = contourpy.contour_generator(z=elev, line_type=contourpy.LineType.Separate)
    lo = int(np.ceil(elev.min() / CONTOUR_STEP) * CONTOUR_STEP)
    hi = int(elev.max())
    contour_features: list[tuple] = []   # (linie v souřadnicích mřížky, ISOM symbol) pro vektor §9
    point_symbols: list[dict] = []       # bodové symboly extrémů (§4.10) z malých smyček
    # velikost buňky mřížky v metrech — pro práh plochy malé smyčky (knoll/depression)
    cell_w_m = WORLD_W_M / (GW - 1)
    cell_h_m = TILE_M / (GH - 1)
    for level in range(lo, hi + 1, CONTOUR_STEP):
        # hlavní vrstevnice na absolutních násobcích CONTOUR_INDEX (25 m) — platí
        # pro reálné výšky i pro šum (BASE_ELEV=700 je násobek 25, chování stejné)
        is_main = level % CONTOUR_INDEX == 0
        symbol = ISOM_INDEX_CONTOUR if is_main else ISOM_CONTOUR   # 102 / 101 pro vektor
        # hlavní vrstevnice výrazně silnější (3 px vs 1 px). Reálně ~0,65 mm při
        # 1:10000 — mírně nad ISOM normou (0,5 mm), ale (a) PIL nemá antialiasing,
        # takže 2 px ještě splývá s normální, (b) jasnější odlišení index/normal
        # pomáhá i modelu (UC5) tyto dvě třídy rozlišit.
        width = 3 if is_main else 1
        for line in cont.lines(level):
            # generalizace (§4.10): malá uzavřená smyčka = lokální extrém → bodový
            # symbol místo vrstevnice. Nekreslí se jako linie (vypadne i z masky
            # vrstevnic a vektoru) — kreslí se až po vrstevnicích, viz níže.
            ps = _classify_loop(line, level, elev, cell_w_m, cell_h_m)
            if ps is not None:
                point_symbols.append(ps)
                continue
            # přepočet souřadnic mřížky (x∈0..GW-1, y∈0..GH-1) na pixely plátna
            pts = [(float(x) / (GW - 1) * W, float(y) / (GH - 1) * H) for x, y in line]
            if len(pts) >= 2:
                draw.line(pts, fill=C_BROWN, width=width)
                cdraw.line(pts, fill=255, width=width)
                contour_features.append((line, symbol))   # grid souřadnice → georef ve vektor exportu

    # --- voda (hydrografie): reálná ze ZABAGED WFS (real-půlka, Sez. 17) ---
    # Kreslí se PO vrstevnicích, PŘED cestami (z-order): modré toky/plochy leží na hnědém
    # terénu, černé cesty (mosty/lávky) je překryjí nahoře. Jen --water real (proc D8 = příště).
    water_line_features: list[tuple] = []
    water_area_features: list[tuple] = []
    water_info: list[dict] = []
    water_mask_img: Image.Image | None = None
    if water == "real":
        water_mask_img = Image.new("L", (W, H), 0)      # GT maska vody (§8.1), multi-class
        wdraw = ImageDraw.Draw(water_mask_img)
        water_line_features, water_area_features, water_info = _generate_real_water(
            draw, wdraw, lat, lon, geo_bbox)

    # --- cesty (§4.9): procedurální (Dijkstra least-cost) nebo reálné (ZABAGED WFS) ---
    # Kreslí se PO vodě, PŘED bodovými symboly (z-order). Obě větve sdílí render
    # (_draw_path) i GT masku — liší se jen zdrojem geometrie (proc Dijkstra / real WFS).
    path_mask_img = Image.new("L", (W, H), 0)       # GT maska cest (§8.1), multi-class
    pdraw = ImageDraw.Draw(path_mask_img)
    if paths == "real":
        path_features, paths_info = _generate_real_paths(draw, pdraw, lat, lon, geo_bbox)
    else:
        path_features, paths_info = _generate_proc_paths(rng, elev, draw, pdraw,
                                                         cell_w_m, cell_h_m, det)
    n_paths = len(paths_info)

    # --- bodové symboly lokálních extrémů (§4.10): kreslí se NAHORU (po cestách) ---
    sym_mask_img = Image.new("L", (W, H), 0)        # GT maska bodových symbolů (§8.1)
    sdraw = ImageDraw.Draw(sym_mask_img)
    for ps in point_symbols:
        _draw_point_symbol(draw, sdraw, ps)

    # --- zápis výstupů (§8.1): finální mapa + masky + meta ---
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    img.save(out / "rgb.png")
    cmask_img.save(out / "mask_contours.png")
    path_mask_img.save(out / "mask_paths.png")                              # cesty (GT, multi-class)
    sym_mask_img.save(out / "mask_symbols.png")                             # bodové symboly (GT, §8.1)
    if water_mask_img is not None:
        water_mask_img.save(out / "mask_water.png")                         # voda (GT, multi-class)
    # vektorový export vrstevnic (§9): ISOM 101/102 linie, georef (real = S-JTSK)
    n_contours = _write_contours_geojson(contour_features, geo_bbox, crs_epsg,
                                         out / "contours.geojson")
    # .omap export (§9): vrstevnice + cesty + voda + body do uživatelova čistého ISOM 2017-2
    # template (template_classic.omap, Sez. 14). Vodní toky 304/305/306 = liniové objekty;
    # plochy → 301.1 (plošný symbol, jistě přiřaditelný objektu; kombinovaný 301 s břehem
    # je rozšíření). Vše type-1 objekt (OOM rozlišuje linie/plochu podle typu symbolu).
    water_omap_features = ([(g, c) for g, c in water_line_features]
                           + [(g, "301.1") for g, _ in water_area_features])
    from omap_export import write_omap
    omap_counts = write_omap(contour_features, path_features, point_symbols,
                             water_omap_features, GW, GH, WORLD_W_M, TILE_M, MAP_SCALE,
                             out / "map.omap")
    omap_info = {"file": "map.omap", **omap_counts}
    meta = _build_meta(seed, rug, det, terrain, paths, water, lat, lon, elev, crs_epsg,
                       n_contours, n_paths, paths_info, point_symbols, water_info, omap_info)
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Procedurální generátor výseku OB mapy.")
    p.add_argument("--seed", type=int, default=1, help="seed PRNG (determinismus)")
    p.add_argument("--rug", type=float, default=0.5, help="členitost terénu 0-1 (jen --terrain noise)")
    p.add_argument("--det", type=float, default=0.5, help="hustota detailů 0-1 (počet cest)")
    p.add_argument("--terrain", choices=["noise", "real"], default="noise",
                   help="noise = fraktální šum (default), real = ČÚZK DMR 5G (§8.5)")
    p.add_argument("--paths", choices=["proc", "real"], default="proc",
                   help="proc = procedurální Dijkstra (default), real = ČÚZK ZABAGED WFS "
                        "(vyžaduje --terrain real)")
    p.add_argument("--water", choices=["off", "real"], default="off",
                   help="off = bez vody (default), real = ČÚZK ZABAGED WFS toky+plochy "
                        "(vyžaduje --terrain real; proc hydro D8 = budoucí)")
    p.add_argument("--lat", type=float, default=DEF_LAT, help="zeměpisná šířka WGS84 (jen --terrain real)")
    p.add_argument("--lon", type=float, default=DEF_LON, help="zeměpisná délka WGS84 (jen --terrain real)")
    p.add_argument("--out", default="output", help="výstupní složka")
    args = p.parse_args()
    out = generate(args.seed, args.rug, args.det, args.out, terrain=args.terrain,
                   paths=args.paths, water=args.water, lat=args.lat, lon=args.lon)
    print(f"Hotovo -> {out.resolve()}")


if __name__ == "__main__":
    main()
