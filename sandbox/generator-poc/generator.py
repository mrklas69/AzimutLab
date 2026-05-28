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
import logging  # průběžný + souhrnný výstup synthesize (úroveň INFO; CLI zapíná, batch tichý)
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
from palette import C_WHITE, C_BROWN, C_BLACK, C_BLUE, C_ROAD

# Logger generátoru — synthesize loguje průběh (INFO). Knihovna NEkonfiguruje root handler
# (žádný side-effect při importu): CLI (main) zapne basicConfig(INFO) → uvidí se; batch.py
# basicConfig nevolá → INFO se nezobrazí (tichý při dávce). Úroveň DEBUG = budoucí detail.
_log = logging.getLogger("generator")

# ---------- Rozměry výseku, mřížky a plátna, měřítko (§1) ----------
# Velikost výseku je PARAMETR (lokalita + rozměry → cíl synthesize_pseudorealistic_map);
# grid/plátno/svět se z ní odvodí (_apply_extent). Rozlišení (PX_PER_MM, M_PER_CELL) a
# měřítko jsou JEDNA PRAVDA — drží konstantní, takže mm-odvozené prahy (příčky vedení
# POWERLINE_TICK_* …) platí nezávisle na velikosti výseku (0,5 mm na papíře je 0,5 mm vždy).
MAP_SCALE = 10000        # měřítko mapy 1:MAP_SCALE — paper-space přepočet v .omap exportu (§9)
PX_PER_MM = 4.5855       # cílová hustota rastru na papíře [px/mm] (historicky 672 px / 146,55 mm)
M_PER_CELL = 1000.0 / 116  # rozteč výpočetní mřížky [m/buňku] (historicky 116 buněk na 1 km S-J)
CONTOUR_STEP = 5         # ekvidistance vrstevnic [m]
CONTOUR_INDEX = 25       # zvýrazněná (hlavní) vrstevnice každých 25 m
BASE_ELEV = 700          # bazální nadmořská výška [m] — jen pro terrain="noise"
DEF_WIDTH_KM = 1.4655    # default šířka výseku E-W [km] = historický baseline (170:116 na 1 km S-J)
DEF_HEIGHT_KM = 1.0      # default výška výseku S-J [km]

# Rozměrové globály (grid GW×GH buněk, plátno W×H px, svět WORLD_W_M×TILE_M metrů) NASTAVÍ
# _apply_extent z velikosti výseku — deklarace zde jen pro čitelnost; reálné hodnoty přiřadí
# volání níže (default) nebo main() (z --width-km/--height-km).
GW = GH = W = H = 0
TILE_M = WORLD_W_M = 0.0


def _apply_extent(w_km: float, h_km: float) -> None:
    """Odvodí rozměrové globály z velikosti výseku [km] při konstantním rozlišení.

    `w_km` = východ-západ (osa x), `h_km` = sever-jih (osa y). WORLD_W_M/TILE_M jsou metry
    světa, W/H pixely plátna (PX_PER_MM × papír), GW/GH buňky mřížky (M_PER_CELL). TILE_M =
    S-J strana — jméno zděděné connectory (dmr/zabaged build_bbox: tile_m = osa y, delší se
    dopočítá v poměru GW/GH). Rozlišení se nemění → PX_PER_MM a mm-prahy zůstávají platné.
    """
    global GW, GH, W, H, TILE_M, WORLD_W_M
    TILE_M = h_km * 1000.0                           # kratší strana (S-J) [m] — pro connectory
    GH = round(TILE_M / M_PER_CELL)
    GW = round(w_km * 1000.0 / M_PER_CELL)
    # E-W šířku odvozuji z poměru gridu (TILE_M·GW/GH), NE přímo z w_km — sjednoceno s
    # dmr/zabaged build_bbox (tytéž GW/GH), jinak by zaokrouhlení mřížky rozešlo reálnou
    # geometrii a omap georef. Jedna pravda pro geo_bbox (noise i real) i .omap.
    WORLD_W_M = TILE_M * (GW / GH)
    px_per_m = PX_PER_MM * 1000.0 / MAP_SCALE        # px rastru na metr terénu (měřítko fixní)
    W = round(WORLD_W_M * px_per_m)
    H = round(TILE_M * px_per_m)


_apply_extent(DEF_WIDTH_KM, DEF_HEIGHT_KM)   # inicializace globálů na default výsek

# ISOM symboly vrstevnic (§4.5, ověřeno O-Map Wiki) — pro vektorový export (§9).
ISOM_CONTOUR = 101       # základní vrstevnice (Contour)
ISOM_INDEX_CONTOUR = 102 # zvýrazněná každá pátá (Index contour)
ISOM_FORMLINE = 103      # pomocná (čárkovaná) vrstevnice na poloviční ekvidistanci (Form line)

# --- pomocné vrstevnice (form lines, ISOM 103) — heuristika z DMR (Sez. 29) ---
# Form line = doplňková vrstevnice na POLOVIČNÍ ekvidistanci (CONTOUR_STEP/2 = 2,5 m). ISOM ji
# povoluje JEN tam, kde běžné vrstevnice nezachytí tvar, a ZAKAZUJE jako "intermediate contour"
# (plošné zahuštění). Proto dvě podmínky současně (návrh uživatele):
#   (1) mírný svah  — rozestup sousedních vrstevnic > FORMLINE_SPACING_LIMIT_M (jinak se nevejde);
#       rozestup = CONTOUR_STEP / sklon  ⟺  sklon < CONTOUR_STEP / FORMLINE_SPACING_LIMIT_M
#   (2) zakřivený terén — |Laplacián výšky| > FORMLINE_CURV_MIN; na rovnoměrném (lineárním) svahu
#       je Laplacián ≈ 0 → form line by jen kopírovala vrstevnici = zbytečná rovnoběžka.
FORMLINE_SPACING_LIMIT_M = 40.0  # CONST_LIMIT_103: práh rozestupu vrstevnic [m] (víc = méně form lines)
FORMLINE_CURV_MIN = 0.004        # min |křivost terénu| [1/m] — odfiltruje rovnoměrný svah (podmínka 2);
                                 #   laděno na NL (Sez. 29): 0,0015 dalo 1466 (plošný šum); nižší práh =
                                 #   víc tvarů (uživatel chtěl hustší), drobné fousky řeší MIN_LEN níže
FORMLINE_SMOOTH_PASSES = 3       # kolikrát vyhladit elev (3×3 box) před derivacemi — tlumí mikro-texturu
                                 #   DMR, kterou Laplacián jinak zachytí jako falešné form lines všude
FORMLINE_MIN_LEN_MM = 3.0        # minimální délka form line na papíře [mm] (footprint ~30 m). ISOM
                                 #   minimum je 1,1 mm, ale volíme PŘÍSNĚJI (uživatel Sez. 29) — kratší
                                 #   úseky jsou „fousky" (vizuální šum), ne plnohodnotný terénní tvar
FORMLINE_DASH_PX = 2.0 * PX_PER_MM   # render dash (template 103: dash 2,0 mm); .omap nese pravý symbol
FORMLINE_BREAK_PX = 0.5 * PX_PER_MM  # render break: ZVĚTŠEN proti template (0,2 mm = 0,9 px = sub-px,
                                     #   v rastru neviditelný → form line splývá s 101). 0,5 mm je
                                     #   čitelně čárkované. .omap nese věrný symbol 103 (OOM renderuje
                                     #   0,2 mm autoritativně) — jako render-vs-omap u cest/železnice.
FORMLINE_CLASS = 1               # třída v mask_formlines.png (0 = pozadí, jediná třída)

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
#   --paths real           = reálné komunikace ze ZABAGED REST (real-půlka §4.9, Sez. 16),
#                            plná hierarchie 502-506 dle ZABAGED→ISOM (viz zabaged.map_path_to_isom).
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
# Šířky odvozené z ISOM rozměrů v template_classic.omap (papírové µm × PX_PER_MM ≈ 4,58):
# 503/504 = 525 µm ≈ 2,40 px, 505 = 375 µm ≈ 1,72 px, 506 = 270 µm ≈ 1,24 px (Sez. 18 verify).
# PIL bez antialiasingu → celočíselné šířky. (502 casing = PoC aproximace šířky silnice.)
PATH_STYLE = {
    ISOM_WIDE_ROAD:      ("casing", 3, None),         # černé okraje + hnědá výplň (ISOM 502: 300µm fill + 2×140µm border ≈ 580µm ≈ 3px)
    ISOM_ROAD:           ("solid", 2, None),          # 525 µm ≈ 2,4 px
    ISOM_VEHICLE_TRACK:  ("dashed", 2, (10.0, 4.0)),  # 525 µm ≈ 2,4 px; vozová: delší čárka
    ISOM_FOOTPATH:       ("dashed", 1, (7.0, 4.0)),   # 250 µm ≈ 1,15 px → 1 px (template-věrné; Sez. 23 oprava driftu „375µm/2px" ze Sez. 18)
    ISOM_SMALL_FOOTPATH: ("dashed", 1, (4.0, 4.0)),   # 270 µm ≈ 1,2 px → 1 px; kratší/jemnější čárka
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
# reálná půlka (ZABAGED Polohopis REST, Sez. 17, izomorfní s reálnými cestami): toky (linie)
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

# Budovy/stavby (Sez. 18, real-půlka, izomorfní s vodní PLOCHOU 301): ZABAGED
# Budova_..._plocha_ → ISOM 521 Building = plošný černý symbol (výplň + obrys). Jen reálná
# půlka (ZABAGED REST); bodová vrstva budov je v lesních výsecích prázdná → jen plochy.
# Mapování ZABAGED→ISOM viz zabaged.map_building_to_isom. Barva = černá (C_BLACK z palety).
ISOM_BUILDING = 521                # plošná budova → černá výplň + obrysová linie
BUILDING_NAME = {ISOM_BUILDING: "Building"}
# ISOM kód → třída v mask_buildings.png (0 = pozadí). Jediná třída (1).
BUILDING_CLASS = {ISOM_BUILDING: 1}

# El. vedení (Sez. 24, real-půlka, izomorfní s cestami): ZABAGED Elektrické_vedení → ISOM 510
# Power line. Render = tenká černá linie s krátkými kolmými příčkami („fousky") v intervalu —
# tak ji kreslí OB mapa (odlišení od cesty). Mapování viz zabaged.map_powerline_to_isom (vždy
# 510; NAPETI v datech prázdné → bez rozlišení 510/511). Pozor: 510, NE 516 (=Fence). Černá.
ISOM_POWERLINE = 510               # el. vedení → tenká linie + kolmé příčky
POWERLINE_NAME = {ISOM_POWERLINE: "Power line"}
# ISOM kód → třída v mask_powerlines.png (0 = pozadí). Jediná třída (1).
POWERLINE_CLASS = {ISOM_POWERLINE: 1}
# Render styl (mode, width [px], dash). mode "powerline" = plná linie + příčky (viz _draw_line_symbol).
POWERLINE_STYLE = {ISOM_POWERLINE: ("powerline", 1, None)}   # linie 0,15 mm ≈ 0,7 px → 1 px
# Příčky („zuby") symbolu 510 — na OB mapě odpovídají SLOUPŮM (běžci se jimi řídí, doménový
# fakt). Fáze 1: příčka na poloze reálného sloupu (ZABAGED Stožár_elektrického_vedení). Fáze 2
# (pseudorealistic): linie bez evidovaného sloupu dostane rovnoměrné příčky (dekorace, poloha
# vymyšlená). Rozměry z ISOM přes PX_PER_MM (papírové mm × ≈4,58).
POWERLINE_TICK_HALF_PX = round(0.5 * PX_PER_MM)      # ≈ 2 px (poloviční délka příčky, na každou stranu)
POWERLINE_TICK_SPACING_PX = round(2.5 * PX_PER_MM)   # ≈ 11 px (rovnoměrný interval, jen fáze 2)
POWERLINE_MAST_SNAP_PX = round(0.7 * PX_PER_MM)      # ≈ 3 px (práh „sloup leží na této linii")

# Železnice (Sez. 28, real-půlka, izomorfní s cestami/vedením): ZABAGED Železniční_trať →
# ISOM 509 Railway. POZOR: 509 je v template_classic.omap KOMBINOVANÝ symbol (type=16), NE
# prostá linie jako vedení 510 — skládá se z černých čárek (0,35 mm; dash 1,5 / break 1,0 mm)
# a bílého „pražcového" knockout podkladu (barva „White for railway"). Raster to zrcadlí
# (mode "railway"): bílý podklad → mezery mezi čárkami jsou BÍLÉ (odliší trať od pěšiny 505,
# jejíž mezery ukazují terén). Mapování viz zabaged.map_railway_to_isom (vždy 509). Černá/bílá z palety.
ISOM_RAILWAY = 509                 # železniční trať → černé čárky + bílý knockout
RAILWAY_NAME = {ISOM_RAILWAY: "Railway"}
# ISOM kód → třída v mask_railways.png (0 = pozadí). Jediná třída (1).
RAILWAY_CLASS = {ISOM_RAILWAY: 1}
# Render styl (mode, width [px], (dash, gap)). dash/gap z template (1,5 / 1,0 mm × PX_PER_MM
# ≈ 6,9 / 4,6 px); šířka 0,35 mm ≈ 1,6 → 2 px (silnější než pěšina → zřetelná trať).
RAILWAY_STYLE = {ISOM_RAILWAY: ("railway", 2, (6.9, 4.6))}

# Zpevněné plochy / kolejiště (Sez. 28, real-půlka, plošná — izomorfní s budovou 521 / vodní
# plochou 301): ZABAGED Kolejiště → ISOM 501 Paved area. 501 je v template KOMBINOVANÝ symbol
# (hnědá 50% výplň + obrysová linie). Raster: výplň = C_ROAD (zavedená hnědá zpevněného povrchu,
# DRY se silnicí 502 — paved i silnice jsou hnědé), obrys = C_BROWN (= template bounding line
# Brown 100%). Mapování viz zabaged.map_paved_to_isom (vždy 501). Volba 501 pro kolejiště =
# rozhodnutí uživatele (Sez. 28): nádraží se generalizuje na zpevněnou plochu, ne jednotlivé koleje.
ISOM_PAVED = 501                   # zpevněná plocha (kolejiště) → hnědá výplň + obrysová linie
PAVED_NAME = {ISOM_PAVED: "Paved area"}
# ISOM kód → třída v mask_paved.png (0 = pozadí). Jediná třída (1).
PAVED_CLASS = {ISOM_PAVED: 1}


# ---------- Skály a balvany (Sez. 30, real-půlka §8.5) ----------
# 3 ISOM symboly z 3 ZABAGED vrstev — KISS, vrstva = jeden symbol (jako budovy→521 / vedení→510):
#   204 Boulder           — bod (Osamělý_balvan)
#   207 Boulder cluster   — bod (Skupina_balvanů__bod_)
#   206 Gigantic boulder  — plocha (Skalní_útvary, plná černá plocha)
# Hybridní 202/206 podle plochy (zvažováno Sez. 30, Q2) ZAVRŽENO uživatelem v průběhu sezení:
# „rozhodování bez datového podkladu" — ZABAGED nemá atribut typu/výšky, práh by byl hádaný.
# Drift po stěně argumentů („proč jsou některé plné a jiné jen obrys?") → návrat ke KISS:
# Skalní_útvary jsou VŽDY 206 (plná plocha), nezávisle na velikosti.
# Smoothing polygonů (původní A2 záměr) také ZAVRŽEN: ZABAGED polygony jsou už dostatečně
# detailní (Shape_Length 680 m / Shape_Area 5289 m² = ~120 vrcholů). RAW je default.
ISOM_BOULDER = 204                 # 204 Boulder — bodový balvan, plný černý kruh
ISOM_GIGANTIC_BOULDER = 206        # 206 Gigantic boulder — skalní útvar v půdorysu, černá výplň
ISOM_BOULDER_CLUSTER = 207         # 207 Boulder cluster — bodová skupina balvanů, černý trojúhelník
ROCK_NAME = {ISOM_BOULDER: "Boulder", ISOM_GIGANTIC_BOULDER: "Gigantic boulder",
             ISOM_BOULDER_CLUSTER: "Boulder cluster"}
# ISOM kód → třída v mask_rocks.png (0 = pozadí). 3 třídy (jedna maska pro celou kategorii).
ROCK_CLASS = {ISOM_BOULDER: 1, ISOM_BOULDER_CLUSTER: 2, ISOM_GIGANTIC_BOULDER: 3}

# Render parametry (template_classic.omap autoritativní, rastr ladíme pro viditelnost — princip
# Sez. 28/29 „render px-tuned vs .omap věrný"). Vše v µm × PX_PER_MM/1000:
#   204 inner_radius=200 → 0,2 mm poloměr (= 0,4 mm průměr) → 0,917 px → 1 px viditelně mizí,
#                          ladíme na 2 px (= 0,44 mm), OOM stejně renderuje 0,4 mm věrně.
#   207 počet bodů 3 v template (-400 231; 400 231; 0 -462), base 0,8 mm, výška 0,693 mm →
#                          base 4 px, výška 3 px (vrchol DOLŮ, jako template orientace).
BOULDER_RADIUS_PX = max(2, round(0.4 * PX_PER_MM))           # 204 — kruh
BOULDER_CLUSTER_HALF_BASE_PX = max(2, round(0.4 * PX_PER_MM))  # 207 — polovina base trojúhelníku
BOULDER_CLUSTER_HEIGHT_PX = max(2, round(0.7 * PX_PER_MM))     # 207 — výška trojúhelníku (vrchol dolů)


# ---------- Mosty a lávky (Sez. 31, real-půlka §8.5) ----------
# 2 ISOM symboly z 3 ZABAGED vrstev — KISS (vrstva/kategorie → jeden symbol):
#   512   Bridge/tunnel  — linie + V-křídla na obou koncích (Most)
#   512.2 Footbridge     — kolmá čárka (Lávka linie + Lávka bod)
# Mapování viz zabaged.map_bridge_to_isom (→ 512) / map_footbridge_to_isom (→ 5122).
# 5122 = int alias ISOM kódu „512.2" (string s tečkou; omap_export ho mapuje na „512.2").
# Verify-against-source (template_classic.omap, Sez. 31):
#   512: line_symbol type=2, line_width=180 µm (0,18 mm), color=2 (černá);
#        start_symbol/end_symbol = úseček (-300,-436)→(0,0) a (0,0)→(300,-436), tj. šikmé V-křídlo
#        0,3 mm do strany × 0,44 mm zpět (úhel ~35° vůči ose).
#   512.2: point_symbol rotatable=true, kolmá čárka 0→±625 µm (= 1,25 mm celkem) × 0,25 mm tlusté.
ISOM_BRIDGE = 512                  # most pro vozidla/železnici → linie + V-křídla na koncích
ISOM_FOOTBRIDGE = 5122             # lávka pro pěší (= ISOM 512.2) → kolmá čárka, rotace k vodě
BRIDGE_NAME = {ISOM_BRIDGE: "Bridge", ISOM_FOOTBRIDGE: "Footbridge"}
# ISOM kód → třída v mask_bridges.png (multi-class: 1=most 512, 2=lávka 512.2). 0 = pozadí.
BRIDGE_CLASS = {ISOM_BRIDGE: 1, ISOM_FOOTBRIDGE: 2}

# Render parametry (template autoritativní, rastr px-tuned — princip render-px-tuned vs .omap věrný).
# Symbol 512 v OB konvenci (oprava Sez. 31 po Censure uživatele): **4 krátké rovnoběžné čárky
# vně osy cesty** (jedna na začátku NAD osou + jedna POD, jedna na konci NAD + jedna POD =
# „=  =" tvar na obou koncích). Žádná středová linie — cesta/železnice už je nakreslená pod
# symbolem. Template coords `-300 -436`: 300 µm podél tangenty (= délka rovnoběžné čárky),
# 436 µm kolmo k tangentě (= offset čárky od osy cesty). Tj. WING_LEN je „back" 300, WING_OFFSET
# je „out" 436 — vlastní symbol 512 je v paper-space na JEDNÉ straně osy a OOM render je
# implicitně mirroruje (= klasická OB bridge konvence: dvě rovnoběžné čárky vně osy).
BRIDGE_WING_LEN_PX = max(6, round(1.3 * PX_PER_MM))          # délka kolmé čárky (1,3 mm rastr-laděno; template 0,3 mm)
BRIDGE_WING_OFFSET_PX = max(3, round(0.6 * PX_PER_MM))       # offset čárky kolmo OD osy (0,6 mm rastr; template 0,44 mm)
BRIDGE_WIDTH_PX = 2                                          # tloušťka čárky (0,18 mm × PX_PER_MM ≈ 0,8 → 2 viditelně)
# POZN. (paměť `render-px-tuned-omap-authoritative`): konstanty zvětšené proti template kvůli
# čitelnosti v rastru (1,3 / 0,6 mm vs template 0,3 / 0,44 mm). OOM .omap nese věrný 512 symbol
# → renderuje autoritativně z template; rastr je feeder pro UC5 a potřebuje viditelné symboly.
# Lávka (512.2): 0,25 mm × 1,25 mm = ~1,15 × 5,7 px → ladíme na 2 × 6 px (viditelně).
FOOTBRIDGE_WIDTH_PX = max(2, round(0.25 * PX_PER_MM))        # tloušťka kolmé čárky (0,25 mm)
FOOTBRIDGE_HALF_LEN_PX = max(3, round(0.625 * PX_PER_MM))    # poloviční délka kolmé čárky (template 625 µm)


# ---------- Reálný terén (§8.5, Option 2): výchozí souřadnice dlaždice ----------
# Soví vrch (Lužické hory, povodí Svitávky) — vlastní terénně mapovaná oblast uživatele
# (proto výchozí lokalita; zná tu ground-truth). Členitý terén vhodný pro OB.
DEF_LAT, DEF_LON = 50.8214458, 14.6712747

# ---------- Vývojářské test lokality (CLI --location, per-lokalita rozměr) ----------
# Jeden zdroj pravdy souřadnic A rozměrů (DRY) — dřív ad-hoc v hlavě/diáři, společný
# rozměr 6×4 km (Sez. 25). Sez. 31 rozšířeno na (label, lat, lon, w_km, h_km) — různé
# formáty výseku (landscape/portrait/strip/square) testují korektní dotahování/ořezávání
# podkladů (DMR, ZABAGED, ortofoto) i v ne-1.5:1 poměrech. Existující 4 zůstávají
# landscape 6×4 km (kanonické výstupy stable). Sprint/ISSprOM = budoucí úkol (IDEAS).
DEV_LOCATIONS: dict[str, tuple[str, float, float, float, float]] = {
    "SV": ("Sovi vrch",   DEF_LAT,    DEF_LON,    6.0, 4.0),  # Lužické hory (default, terénně mapováno) — landscape
    "NL": ("Nova louka",  50.8140386, 15.1579069, 6.0, 4.0),  # Jizerské hory — landscape
    "LS": ("Lidove sady", 50.7773244, 15.0811114, 6.0, 4.0),  # Liberec městsko-lesní pod Ještědem — landscape
    "HS": ("Hruba Skala", 50.5481000, 15.1761500, 5.0, 5.0),  # Hruboskalsko (midpoint Kacanovy↔Doubravice) — SQUARE (Sez. 31)
    "NV": ("Novina",      50.7598686, 14.9601922, 3.0, 5.0),  # Lužické hory, kamenné železniční viadukty — PORTRAIT (Sez. 31)
}


# ---------- Souřadnicové přepočty (DRY: jeden zdroj pro grid↔px↔S-JTSK) ----------
# Tři vrstvy souřadnic: MŘÍŽKA (gx∈0..GW-1, gy∈0..GH-1, sever = gy 0), PIXEL plátna
# a S-JTSK metry (reálná data). Přepočty se dřív opakovaly v každé render funkci
# (proc/real cesty, voda, budovy, body, vrstevnice) → vytaženo sem (Sez. 19, DRY).
def _grid_to_px(gx: float, gy: float) -> tuple[float, float]:
    """Souřadnice mřížky → pixel plátna (lineárně, bez Y-flipu: gy 0 = sever = y 0)."""
    return (gx / (GW - 1) * W, gy / (GH - 1) * H)


def _sjtsk_to_grid(x: float, y: float, bbox: tuple) -> tuple[float, float]:
    """S-JTSK metry → souřadnice mřížky (inverze georef vektoru). Y-flip: sever = ymax = gy 0.

    `bbox` = (xmin, ymin, xmax, ymax). Sdílí reálné cesty/voda/budovy (Sez. 16-18) — výsek
    je tentýž jako u DMR vrstevnic (sdílený build_bbox), takže vše sedne na terén bezešvě.
    """
    xmin, ymin, xmax, ymax = bbox
    return ((x - xmin) / (xmax - xmin) * (GW - 1), (ymax - y) / (ymax - ymin) * (GH - 1))

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
        # epsilon v podmínce: poslední sub-ulp zbytek segmentu neřeš (jinak hrozí zacyklení)
        while d < seg - 1e-9:
            phase = pos % pattern
            in_dash = phase < dash
            # zbývající délka aktuální fáze (čárky nebo mezery)
            remain = (dash - phase) if in_dash else (pattern - phase)
            step = min(remain, seg - d)
            # float drift u NECELOČÍSELNÝCH dash/gap (např. železnice 6,9/4,6 px): fáze uvízne
            # těsně pod hranicí čárka↔mezera → remain≈0 → step≈0 → smyčka „creepuje" donekonečna.
            # Přesné dash/gap (pěšina 7,0/4,0) to netrefí. Nudge přes hranici udrží postup (Sez. 28).
            if step < 1e-9:
                pos += 1e-9          # posuň fázi přes hranici → příště se vyhodnotí druhá fáze
                continue
            if in_dash:
                t0, t1 = d / seg, (d + step) / seg
                ax, ay = x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0
                bx, by = x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1
                draw.line([ax, ay, bx, by], fill=color, width=width)
                mdraw.line([ax, ay, bx, by], fill=cls, width=width)
            d += step
            pos += step


def _draw_tick_at(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                  cx: float, cy: float, ux: float, uy: float, color: tuple, cls: int,
                  width: int, half_len: float) -> None:
    """Jedna krátká kolmá příčka v bodě (cx,cy), kolmá na směr (ux,uy) — jeden „zub"
    symbolu el. vedení (na poloze sloupu, fáze 1; nebo rovnoměrná dekorace, fáze 2)."""
    nx, ny = -uy, ux                                # kolmice (rotace směru o 90°)
    seg = [cx + nx * half_len, cy + ny * half_len, cx - nx * half_len, cy - ny * half_len]
    draw.line(seg, fill=color, width=width)
    mdraw.line(seg, fill=cls, width=width)


def _draw_perp_ticks(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                     pts: list[tuple[float, float]], color: tuple, cls: int,
                     width: int, spacing: float, half_len: float) -> None:
    """Rovnoměrné kolmé příčky podél linie (pseudorealistická dekorace, fáze 2 — vedení
    bez evidovaných sloupů). Jdeme po délce oblouku (jako _draw_dashed); v každém násobku
    `spacing` nakreslíme příčku kolmou na lokální směr. `pos` = ujetá vzdálenost,
    `next_tick` = pozice příští příčky (první až po `spacing`, ne na začátku linie)."""
    if len(pts) < 2:
        return
    pos = 0.0
    next_tick = spacing
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg == 0.0:
            continue
        ux, uy = (x1 - x0) / seg, (y1 - y0) / seg   # jednotkový směr segmentu
        while next_tick <= pos + seg:               # všechny příčky padnoucí do segmentu
            t = next_tick - pos                     # vzdálenost od začátku segmentu
            _draw_tick_at(draw, mdraw, x0 + ux * t, y0 + uy * t, ux, uy,
                          color, cls, width, half_len)
            next_tick += spacing
        pos += seg


def _nearest_seg(px: float, py: float,
                 lines_px: list[list[tuple[float, float]]]) -> tuple[float, float, float]:
    """(ux, uy, dist): jednotkový směr nejbližšího segmentu k bodu (px,py) napříč `lines_px`
    a vzdálenost k němu. Slouží k orientaci příčky na sloupu (fáze 1) a k přiřazení
    sloup↔linie (sloup leží na vedení → dist ≈ 0). Projekce bodu na úsečku: parametr `t`
    omezený na [0,1] dá nejbližší bod segmentu."""
    best_d2 = float("inf")
    best_dir = (1.0, 0.0)
    for line in lines_px:
        for (x0, y0), (x1, y1) in zip(line, line[1:]):
            dx, dy = x1 - x0, y1 - y0
            seg2 = dx * dx + dy * dy
            if seg2 == 0.0:
                continue
            t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / seg2))
            cx, cy = x0 + t * dx, y0 + t * dy
            d2 = (px - cx) ** 2 + (py - cy) ** 2
            if d2 < best_d2:
                best_d2 = d2
                L = math.hypot(dx, dy)
                best_dir = (dx / L, dy / L)
    return best_dir[0], best_dir[1], math.sqrt(best_d2)


def _draw_line_symbol(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                      curve_px: list[tuple[float, float]], color: tuple,
                      mode: str, width: int, dash: tuple | None, cls: int) -> None:
    """Generický liniový symbol na mapu (`draw`) + třída do GT masky (`mdraw`).

    Jediná kreslicí logika pro VŠECHNY liniové symboly (izomorfismus / DRY): cesty
    (černá, PATH_STYLE), vodní toky (modrá, WATER_LINE_STYLE) i el. vedení (černá,
    POWERLINE_STYLE) přes ni jdou stejně, liší se jen `color`/`mode`/`dash`. `solid` =
    plná, `dashed` = čárkovaná (dle dash/gap), `casing` = černé okraje + tenčí HNĚDÁ výplň
    (jen silnice 502 — ISOM Wide road, template color 11/14), `powerline` = plná tenká linie
    + kolmé příčky (ISOM 510). Maska dostává `cls`.
    """
    if len(curve_px) < 2:
        return
    if mode == "solid":
        draw.line(curve_px, fill=color, width=width)
        mdraw.line(curve_px, fill=cls, width=width)
    elif mode == "dashed":
        d, g = dash
        _draw_dashed(draw, mdraw, curve_px, color, cls, dash=d, gap=g, width=width)
    elif mode == "powerline":  # ISOM 510: holá tenká linie (příčky kreslí _generate_real_powerlines
        draw.line(curve_px, fill=color, width=width)   # ze sloupů/fáze 2 — ne z definice symbolu)
        mdraw.line(curve_px, fill=cls, width=width)
    elif mode == "railway":  # ISOM 509 (kombinovaný symbol): bílý knockout podklad + černé čárky
        # maska = celá osa trati jako JEDNA třída (čárky jsou vizuální detail, ne třídy)
        mdraw.line(curve_px, fill=cls, width=width)
        # bílý podklad („White for railway", knockout) → mezery mezi čárkami jsou BÍLÉ, ne
        # průhledné (odliší trať od pěšiny 505, jejíž mezery ukazují terén pod sebou)
        draw.line(curve_px, fill=C_WHITE, width=width)
        # černé čárky navrch (dash/break z template: 1,5 / 1,0 mm). _draw_dashed přepíše masku
        # na čárkách stejnou třídou (cls) — neškodné, maska už je solid z řádku výš.
        d, g = dash
        _draw_dashed(draw, mdraw, curve_px, color, cls, dash=d, gap=g, width=width)
    else:  # casing: silná černá, přes ni tenčí HNĚDÁ → hnědý pás s černými okraji (ISOM 502)
        draw.line(curve_px, fill=color, width=width)
        draw.line(curve_px, fill=C_ROAD, width=max(1, width - 2))
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


def _draw_powerline(draw: ImageDraw.ImageDraw, eldraw: ImageDraw.ImageDraw,
                    curve_px: list[tuple[float, float]], code: int) -> None:
    """El. vedení (černá, ISOM 510) dle POWERLINE_STYLE — wrapper nad _draw_line_symbol
    (izomorfní s _draw_path / _draw_water_line)."""
    mode, width, dash = POWERLINE_STYLE[code]
    _draw_line_symbol(draw, eldraw, curve_px, C_BLACK, mode, width, dash, POWERLINE_CLASS[code])


def _draw_railway(draw: ImageDraw.ImageDraw, rdraw: ImageDraw.ImageDraw,
                  curve_px: list[tuple[float, float]], code: int) -> None:
    """Železniční trať (černé čárky + bílý knockout, ISOM 509) dle RAILWAY_STYLE — wrapper
    nad _draw_line_symbol (izomorfní s _draw_path / _draw_powerline)."""
    mode, width, dash = RAILWAY_STYLE[code]
    _draw_line_symbol(draw, rdraw, curve_px, C_BLACK, mode, width, dash, RAILWAY_CLASS[code])


def _draw_bridge(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                 curve_px: list[tuple[float, float]]) -> None:
    """Most/tunel (ISOM 512): 4 krátké KOLMÉ čárky vně osy cesty (Sez. 31 oprava 2x).

    OB konvence (verify s uživatelem Sez. 31): most vyznačený DVĚMA páry krátkých čárek
    KOLMÝCH k ose cesty, zrcadlově nad i pod osou. ASCII:

        |  |              ← horní pár (nad osou: na začátku + na konci mostu)
        |  |
    ====|==|====           cesta
        |  |
        |  |              ← dolní pár (pod osou, zrcadlově)

    Žádná středová linie — cesta/železnice je již nakreslená pod symbolem. Stejný symbol
    pro most i tunel (template description: „Bridges and tunnels are represented using the
    same basic symbols"). První interpretace Sez. 31 (V-křídla na osu) byla špatná: template
    start/end_symbol je JEDNA POLOVINA symetrického páru a OOM ho zrcadlí kolem osy linie.

    Template coords `-300 -436` v paper-space: 300 µm „back" podél tangenty (kde leží
    bod čárky), 436 µm kolmo (offset od osy). Pro render kolmé čárky: 300 µm = offset
    od osy zakončení čárky vzdálenější od cesty, 436 µm = offset bližšího konce.
    Render: kolmá čárka od bodu (off od osy) k bodu (off+seg od osy)."""
    if len(curve_px) < 2:
        return
    width = BRIDGE_WIDTH_PX
    cls = BRIDGE_CLASS[ISOM_BRIDGE]
    seg = BRIDGE_WING_LEN_PX            # délka kolmé čárky (~0,3 mm)
    off = BRIDGE_WING_OFFSET_PX         # offset čárky od osy cesty (~0,44 mm = "vně cesty")
    # Pro každý konec mostu (start + end) nakresli 2 KOLMÉ čárky (nad+pod osou).
    for end_idx, prev_idx in ((0, 1), (-1, -2)):
        ex, ey = curve_px[end_idx]
        px2, py2 = curve_px[prev_idx]
        # tangenta podél osy mostu (směr není důležitý — kolmé čárky jsou stejné z obou stran)
        tdx, tdy = px2 - ex, py2 - ey
        tlen = math.hypot(tdx, tdy) or 1.0
        # normála (kolmá k tangentě) — jednotková
        nx_perp, ny_perp = -tdy / tlen, tdx / tlen
        # Kolmé čárky: od bodu (off od osy) k bodu (off+seg od osy), na obou stranách cesty
        for side in (+1, -1):
            base_x = ex + side * off * nx_perp              # bližší konec čárky (off od osy)
            base_y = ey + side * off * ny_perp
            tip_x = ex + side * (off + seg) * nx_perp       # vzdálenější konec (off+seg)
            tip_y = ey + side * (off + seg) * ny_perp
            draw.line([(base_x, base_y), (tip_x, tip_y)], fill=C_BLACK, width=width)
            mdraw.line([(base_x, base_y), (tip_x, tip_y)], fill=cls, width=width)


def _draw_footbridge_point(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                           cx: float, cy: float, rot_rad: float) -> None:
    """Bodová lávka (ISOM 512.2): kolmá čárka v poloze (cx, cy) rotovaná o rot_rad rad.

    Template_classic.omap (Sez. 31): point_symbol rotatable=true, polyline (0,-625) →
    (0,625) µm = vertikální čárka 1,25 mm tlustá 0,25 mm. Čárka se kreslí podél osy
    lávky (= kolmo k vodě pod ní). `rot_rad` = úhel orientace osy lávky vůči +x rastru;
    typicky se nastavuje kolmo k nejbližšímu vodnímu toku (řešeno volajícím — paralela
    řopíků orientovaných k hranici)."""
    half = FOOTBRIDGE_HALF_LEN_PX
    cos_r = math.cos(rot_rad)
    sin_r = math.sin(rot_rad)
    p1 = (cx - half * cos_r, cy - half * sin_r)
    p2 = (cx + half * cos_r, cy + half * sin_r)
    cls = BRIDGE_CLASS[ISOM_FOOTBRIDGE]
    draw.line([p1, p2], fill=C_BLACK, width=FOOTBRIDGE_WIDTH_PX)
    mdraw.line([p1, p2], fill=cls, width=FOOTBRIDGE_WIDTH_PX)


def _draw_area_symbol(draw: ImageDraw.ImageDraw, adraw: ImageDraw.ImageDraw,
                      ring_px: list[tuple[float, float]],
                      fill: tuple, outline: tuple, mask_class: int) -> None:
    """Plošný ISOM symbol: barevná výplň + obrysová linie na mapu + třída do GT masky.

    Sjednocuje plochy stejně, jako _draw_line_symbol sjednotil linie (Sez. 17): vodní
    plocha (modrá) i budova (černá) jsou týž tvar lišící se jen barvou. PIL polygon
    vyplní uzavřený prstenec, `outline` dá obrys (břeh/zeď). Maska dostane PLNOU výplň
    třídou (plošná GT, ne jen obrys)."""
    if len(ring_px) < 3:
        return
    draw.polygon(ring_px, fill=fill, outline=outline)
    adraw.polygon(ring_px, fill=mask_class)


def _draw_water_area(draw: ImageDraw.ImageDraw, wdraw: ImageDraw.ImageDraw,
                     ring_px: list[tuple[float, float]], code: int) -> None:
    """Vodní plocha (ISOM 301): modrá výplň + černý břeh — wrapper nad _draw_area_symbol."""
    _draw_area_symbol(draw, wdraw, ring_px, C_BLUE, C_BLACK, WATER_CLASS[code])


def _draw_building_area(draw: ImageDraw.ImageDraw, bdraw: ImageDraw.ImageDraw,
                        ring_px: list[tuple[float, float]], code: int) -> None:
    """Budova (ISOM 521): plná černá výplň + černý obrys — wrapper nad _draw_area_symbol."""
    _draw_area_symbol(draw, bdraw, ring_px, C_BLACK, C_BLACK, BUILDING_CLASS[code])


def _draw_paved_area(draw: ImageDraw.ImageDraw, adraw: ImageDraw.ImageDraw,
                     ring_px: list[tuple[float, float]], code: int) -> None:
    """Zpevněná plocha / kolejiště (ISOM 501): hnědá výplň + hnědý obrys — wrapper nad
    _draw_area_symbol (izomorfní s _draw_building_area / _draw_water_area)."""
    _draw_area_symbol(draw, adraw, ring_px, C_ROAD, C_BROWN, PAVED_CLASS[code])


def _draw_boulder(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                  cx: float, cy: float) -> None:
    """Bodový balvan (ISOM 204): plný černý kruh + GT maska (třída ROCK_CLASS[204]).

    Template_classic.omap: inner_radius="200" (= 0,2 mm poloměr, 0,4 mm průměr). Rastr
    ladíme na BOULDER_RADIUS_PX (≈ 2 px, viditelné) — .omap nese věrný 0,4 mm symbol,
    OOM ho vykreslí autoritativně (princip render-px-tuned vs .omap věrný, Sez. 28/29)."""
    r = BOULDER_RADIUS_PX
    bbox = (cx - r, cy - r, cx + r, cy + r)
    draw.ellipse(bbox, fill=C_BLACK)
    mdraw.ellipse(bbox, fill=ROCK_CLASS[ISOM_BOULDER])


def _draw_boulder_cluster(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                          cx: float, cy: float) -> None:
    """Bodová skupina balvanů (ISOM 207): plný černý trojúhelník vrcholem dolů + GT maska.

    Template_classic.omap: 3 body (-400 231; 400 231; 0 -462) — base 0,8 mm, výška 0,693 mm,
    orientace „sever" (= dva vrcholy nahoře, jeden DOLŮ). V mapovém paper-space (y up) je
    -462 dolů od středu; na rastru (y down) tedy +462 → vrchol směřuje DOLŮ v paper sense,
    ale na rastru je TROJÚHELNÍK S VRCHOLEM NAHORU. Ne, vlastně paper-space y-up → vrchol
    dolů = -y; po překlopení do rastru (y down) je vrchol nahoru. Držíme TEMPLATE orientaci:
    base nahoře (paper +y) → na rastru DOLE; vrchol dole (paper -y) → na rastru NAHOŘE."""
    hb = BOULDER_CLUSTER_HALF_BASE_PX            # polovina base
    h = BOULDER_CLUSTER_HEIGHT_PX                # výška (vrchol → base)
    # paper-space (template): (-400, +231), (+400, +231), (0, -462). Rastr y-flip → y se mění
    # znaménkem. Base = řádek y = +231 paper = -231 rastr → NAHOŘE v paper. Pro KISS rovnoramenný:
    # vrchol NAHOŘE (cx, cy - 2h/3), base DOLE [cx-hb, cy+h/3; cx+hb, cy+h/3] — třetina nahoru,
    # dvě třetiny dolů ≈ těžiště ve středu (cx, cy). Template má 231:462 = 1:2 (centrální moment).
    apex = (cx, cy - 2 * h / 3)
    base_l = (cx - hb, cy + h / 3)
    base_r = (cx + hb, cy + h / 3)
    pts = [apex, base_l, base_r]
    draw.polygon(pts, fill=C_BLACK)
    mdraw.polygon(pts, fill=ROCK_CLASS[ISOM_BOULDER_CLUSTER])


def _draw_gigantic_boulder(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                           ring_px: list[tuple[float, float]]) -> None:
    """Masivní skalní formace (ISOM 206 Gigantic boulder): plná černá plocha + GT maska.

    Template_classic.omap (id 35): `area_symbol inner_color="2" min_area="0" patterns="0"`
    = jen plná černá výplň (žádný pattern, žádný obrys jiné barvy). Mirror _draw_building_area,
    jen třída masky jiná (ROCK_CLASS[206])."""
    _draw_area_symbol(draw, mdraw, ring_px, C_BLACK, C_BLACK, ROCK_CLASS[ISOM_GIGANTIC_BOULDER])


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
    names = {ISOM_CONTOUR: "Contour", ISOM_INDEX_CONTOUR: "Index contour",
             ISOM_FORMLINE: "Form line"}
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


def _box_smooth(a: np.ndarray) -> np.ndarray:
    """3×3 box průměr — potlačí šum DMR PŘED derivacemi (druhá derivace = Laplacián šum
    zesiluje). Okraje replikací (`np.pad mode="edge"`). Devět posunutých výseků
    vypadlého paddingu sečteme a vydělíme 9 (klasický box filtr bez scipy)."""
    p = np.pad(a, 1, mode="edge")
    return (p[:-2, :-2] + p[:-2, 1:-1] + p[:-2, 2:]
            + p[1:-1, :-2] + p[1:-1, 1:-1] + p[1:-1, 2:]
            + p[2:, :-2] + p[2:, 1:-1] + p[2:, 2:]) / 9.0


def _formline_mask(elev: np.ndarray, cell_w_m: float, cell_h_m: float) -> np.ndarray:
    """Bool maska mřížky (GH, GW): kde má smysl kreslit pomocnou vrstevnici (ISOM 103).

    Dvě podmínky současně (viz konstanty FORMLINE_*):
      (1) mírný svah    — sklon < CONTOUR_STEP / FORMLINE_SPACING_LIMIT_M (rozestup > limit),
      (2) zakřivený terén — |Laplacián výšky| > FORMLINE_CURV_MIN (ne rovnoměrný svah).
    `np.gradient(z, dy, dx)` vrací první derivace ve FYZIKÁLNÍCH jednotkách (m/m), když mu
    předáme rozteč buňky [m] pro každou osu. Druhá aplikace na složky → druhé derivace
    (Laplacián = ∂²z/∂x² + ∂²z/∂y², jednotka 1/m). Vyhlazení _box_smooth tlumí šum.
    """
    sm = elev
    for _ in range(FORMLINE_SMOOTH_PASSES):        # opakované vyhlazení ≈ širší jádro (KISS bez scipy)
        sm = _box_smooth(sm)
    gy, gx = np.gradient(sm, cell_h_m, cell_w_m)   # ∂z/∂y (osa 0 = řádky), ∂z/∂x (osa 1 = sloupce)
    slope = np.hypot(gx, gy)
    slope_limit = CONTOUR_STEP / FORMLINE_SPACING_LIMIT_M
    gyy = np.gradient(gy, cell_h_m, axis=0)
    gxx = np.gradient(gx, cell_w_m, axis=1)
    curv = np.abs(gxx + gyy)                        # |Laplacián| [1/m]
    return (slope < slope_limit) & (curv > FORMLINE_CURV_MIN)


def _clip_line_to_mask(line: np.ndarray, mask: np.ndarray) -> list[list[tuple[float, float]]]:
    """Rozdělí polylinii (souřadnice mřížky) na úseky ležící v True oblasti `mask`.

    Form line se kreslí jen v plochém/zakřiveném terénu (maska), ne po celé délce poloviční
    izolinie. Sampluje masku v nejbližší buňce každého bodu; souvislé True body = jeden úsek
    (≥2 body). Tím vznikne „část pomocné vrstevnice" jen tam, kde je opodstatněná (uživatel)."""
    h, w = mask.shape
    segs: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    for gx, gy in line:
        ix = int(np.clip(round(float(gx)), 0, w - 1))
        iy = int(np.clip(round(float(gy)), 0, h - 1))
        if mask[iy, ix]:
            cur.append((float(gx), float(gy)))
        elif len(cur) >= 2:
            segs.append(cur)
            cur = []
        else:
            cur = []
    if len(cur) >= 2:
        segs.append(cur)
    return segs


def _polyline_len_px(pts: list[tuple[float, float]]) -> float:
    """Délka oblouku polyčáry v pixelech (součet délek úseček)."""
    return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
               for i in range(len(pts) - 1))


def _draw_point_symbol(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                       ps: dict) -> None:
    """Nakreslí jeden bodový symbol extrému na mapu (`draw`) i do GT masky (`mdraw`).

    Maska dostává místo barvy ID třídy (SYM_CLASS) — z mask_symbols.png je tak rovnou
    multi-class segmentační GT. Mřížka → pixely stejným přepočtem jako vrstevnice.
    """
    px, py = _grid_to_px(ps["gx"], ps["gy"])
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
                water_mode: str, paved_mode: str, buildings_mode: str, powerlines_mode: str,
                railways_mode: str, rocks_mode: str, bridges_mode: str,
                pseudorealistic: bool, lat: float, lon: float,
                elev: np.ndarray, crs_epsg: int | None,
                n_contours: int, n_formlines: int, n_paths: int, paths_info: list[dict],
                point_symbols: list[dict], water_info: list[dict], paved_info: list[dict],
                building_info: list[dict], powerlines_info: list[dict],
                railways_info: list[dict], rocks_info: list[dict],
                bridges_info: list[dict], omap_info: dict,
                layer_errors: dict[str, str] | None = None) -> dict:
    """Sestaví obsah meta.json: parametry, původ terénu, legendu GT tříd, info o exportech.

    Vyčleněno ze synthesize_pseudorealistic_map() (SLAP, Sez. 15, tehdy generate()):
    orchestrace kreslení vrstev a deklarativní sestavení metadat jsou dvě úrovně abstrakce.
    Vysoký počet parametrů je daň za to, že meta agreguje výstupy všech vrstev.
    """
    # cesty: legendu symbolů/tříd stavíme dynamicky ze SKUTEČNĚ použitých ISOM kódů
    # (proc dělá 503/505; real 502-506 dle ZABAGED→ISOM) — jeden zdroj pravdy PATH_NAME/PATH_CLASS.
    used_path_codes = sorted({p["symbol"] for p in paths_info})
    used_water_codes = sorted({w["symbol"] for w in water_info})
    used_building_codes = sorted({b["symbol"] for b in building_info})
    used_powerline_codes = sorted({p["symbol"] for p in powerlines_info})
    used_railway_codes = sorted({r["symbol"] for r in railways_info})
    used_paved_codes = sorted({p["symbol"] for p in paved_info})
    used_rock_codes = sorted({r["symbol"] for r in rocks_info})
    used_bridge_codes = sorted({b["symbol"] for b in bridges_info})
    return {
        "seed": seed,
        # pseudorealistic = fáze 2 (dekorace symbolů nad rámec tvrdých dat) zapnuta; False =
        # jen projekce reálných dat (onlyreal). Zatím působí na vedení (příčky), Sez. 24.
        "params": {"rug": rug, "det": det, "pseudorealistic": pseudorealistic},
        # původ výškopisu — pro reprodukovatelnost a atribuci (real = ČÚZK DMR 5G)
        "terrain": ({"source": "noise"} if terrain != "real" else {
            "source": "cuzk_dmr5g", "lat": lat, "lon": lon,
            "elev_min_m": round(float(elev.min()), 2),
            "elev_max_m": round(float(elev.max()), 2),
            "licence": "CC BY 4.0 (ČÚZK)",
        }),
        "grid": [GW, GH],
        "canvas": [W, H],
        "scale": f"1:{MAP_SCALE}",
        "contour_step_m": CONTOUR_STEP,
        "contour_index_m": CONTOUR_INDEX,
        # vektorový export vrstevnic (§9): formát, CRS, počet linií, ISOM symboly
        "contours_vector": {
            "file": "contours.geojson",
            "crs": ("EPSG:5514" if crs_epsg else "local_m"),
            "n_lines": n_contours,   # vč. pomocných vrstevnic 103 (jsou ve stejném souboru)
            "symbols": {"101": "Contour", "102": "Index contour", "103": "Form line"},
        },
        # pomocné vrstevnice (form lines, ISOM 103): počet, GT maska, heuristika fáze 1 z DMR
        # (rozestup vrstevnic > limit AND zakřivený terén). Jen reálný terén (Sez. 29).
        "formlines": {
            "count": n_formlines,
            "mask": "mask_formlines.png",
            "source": ("cuzk_dmr5g" if terrain == "real" else "none"),
            "spacing_limit_m": FORMLINE_SPACING_LIMIT_M,
            "curv_min_per_m": FORMLINE_CURV_MIN,
        },
        # cesty (§4.9): počet, GT maska, zdroj, ISOM symboly + třídy masky (dynamicky)
        "paths": {
            "count": n_paths,
            "mask": "mask_paths.png",
            # proc = Dijkstra least-cost (§9, cena ~ sklon); real = reálné komunikace ZABAGED REST
            "source": ("cuzk_zabaged" if paths_mode == "real" else "procedural_dijkstra"),
            "symbols": {str(c): PATH_NAME[c] for c in used_path_codes},
            "classes": {"0": "pozadí",
                        **{str(PATH_CLASS[c]): f"{c} {PATH_NAME[c]}" for c in used_path_codes}},
            "items": paths_info,
            # reálné cesty = ČÚZK open data → atribuce povinná (CC BY 4.0)
            **({"licence": "CC BY 4.0 (ČÚZK ZABAGED)"} if paths_mode == "real" else {}),
        },
        # voda (hydrografie): toky + plochy ze ZABAGED REST (real-půlka, Sez. 17). Sekce
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
        # zpevněné plochy / kolejiště (real-půlka, Sez. 28): plochy ze ZABAGED REST → ISOM 501.
        # Sekce jen když paved_mode != off; symboly/třídy dynamicky ze SKUTEČNĚ použitých kódů.
        **({"paved": {
            "count": len(paved_info),
            "mask": "mask_paved.png",
            "source": "cuzk_zabaged",
            "symbols": {str(c): PAVED_NAME[c] for c in used_paved_codes},
            "classes": {"0": "pozadí",
                        **{str(PAVED_CLASS[c]): f"{c} {PAVED_NAME[c]}" for c in used_paved_codes}},
            "items": paved_info,
            "licence": "CC BY 4.0 (ČÚZK ZABAGED)",
        }} if paved_mode == "real" else {}),
        # budovy/stavby (real-půlka, Sez. 18): plochy ze ZABAGED REST → ISOM 521. Sekce
        # jen když buildings_mode != off; symboly/třídy dynamicky ze SKUTEČNĚ použitých kódů.
        **({"buildings": {
            "count": len(building_info),
            "mask": "mask_buildings.png",
            "source": "cuzk_zabaged",
            "symbols": {str(c): BUILDING_NAME[c] for c in used_building_codes},
            "classes": {"0": "pozadí",
                        **{str(BUILDING_CLASS[c]): f"{c} {BUILDING_NAME[c]}" for c in used_building_codes}},
            "items": building_info,
            "licence": "CC BY 4.0 (ČÚZK ZABAGED)",
        }} if buildings_mode == "real" else {}),
        # el. vedení (real-půlka, Sez. 24): linie ze ZABAGED REST → ISOM 510. Sekce jen když
        # powerlines_mode != off; symboly/třídy dynamicky ze SKUTEČNĚ použitých kódů.
        **({"powerlines": {
            "count": len(powerlines_info),
            "mask": "mask_powerlines.png",
            "source": "cuzk_zabaged",
            "symbols": {str(c): POWERLINE_NAME[c] for c in used_powerline_codes},
            "classes": {"0": "pozadí",
                        **{str(POWERLINE_CLASS[c]): f"{c} {POWERLINE_NAME[c]}" for c in used_powerline_codes}},
            "items": powerlines_info,
            "licence": "CC BY 4.0 (ČÚZK ZABAGED)",
        }} if powerlines_mode == "real" else {}),
        # železnice (real-půlka, Sez. 28): tratě ze ZABAGED REST → ISOM 509. Sekce jen když
        # railways_mode != off; symboly/třídy dynamicky ze SKUTEČNĚ použitých kódů.
        **({"railways": {
            "count": len(railways_info),
            "mask": "mask_railways.png",
            "source": "cuzk_zabaged",
            "symbols": {str(c): RAILWAY_NAME[c] for c in used_railway_codes},
            "classes": {"0": "pozadí",
                        **{str(RAILWAY_CLASS[c]): f"{c} {RAILWAY_NAME[c]}" for c in used_railway_codes}},
            "items": railways_info,
            "licence": "CC BY 4.0 (ČÚZK ZABAGED)",
        }} if railways_mode == "real" else {}),
        # skály/balvany (real-půlka, Sez. 30): 3 ISOM symboly ze 3 ZABAGED vrstev. KISS,
        # vrstva → jeden symbol (jako budovy → 521). Sekce jen když rocks_mode != off;
        # symboly/třídy dynamicky ze SKUTEČNĚ použitých kódů.
        **({"rocks": {
            "count": len(rocks_info),
            "mask": "mask_rocks.png",
            "source": "cuzk_zabaged",
            "symbols": {str(c): ROCK_NAME[c] for c in used_rock_codes},
            "classes": {"0": "pozadí",
                        **{str(ROCK_CLASS[c]): f"{c} {ROCK_NAME[c]}" for c in used_rock_codes}},
            "items": rocks_info,
            "licence": "CC BY 4.0 (ČÚZK ZABAGED)",
        }} if rocks_mode == "real" else {}),
        # mosty/lávky (real-půlka, Sez. 31): Most→512 + Lávka linie+bod→512.2. KISS, kategorie
        # → jeden symbol (jako budovy→521). Sekce jen když bridges_mode != off; symboly/třídy
        # dynamicky ze SKUTEČNĚ použitých kódů. Pozor: 5122 v `symbols` exportu znamená „512.2".
        **({"bridges": {
            "count": len(bridges_info),
            "mask": "mask_bridges.png",
            "source": "cuzk_zabaged",
            "symbols": {("512.2" if c == ISOM_FOOTBRIDGE else str(c)): BRIDGE_NAME[c]
                        for c in used_bridge_codes},
            "classes": {"0": "pozadí",
                        **{str(BRIDGE_CLASS[c]):
                            f"{'512.2' if c == ISOM_FOOTBRIDGE else c} {BRIDGE_NAME[c]}"
                            for c in used_bridge_codes}},
            "items": bridges_info,
            "licence": "CC BY 4.0 (ČÚZK ZABAGED)",
        }} if bridges_mode == "real" else {}),
        # bodové symboly lokálních extrémů (§4.10) z malých uzavřených vrstevnic —
        # detekční anotace (COCO/YOLO styl): symbol, název, pozice (mřížka i pixely).
        # GT maska = mask_symbols.png (třídy viz symbol_classes).
        "point_symbols": [
            {"symbol": ps["symbol"], "symbol_name": SYM_NAME[ps["symbol"]],
             "grid": [round(ps["gx"], 2), round(ps["gy"], 2)],
             "px": [round(c, 1) for c in _grid_to_px(ps["gx"], ps["gy"])]}
            for ps in point_symbols
        ],
        "symbol_classes": {"0": "pozadí", "1": "109 Small knoll",
                           "2": "110 Small elongated knoll", "3": "111 Small depression"},
        # .omap export (§9): vrstevnice + cesty + body, template-based (vlastní čistý ISOM template)
        "omap": omap_info,
        # reálné vrstvy vynechané kvůli selhání REST/sítě (jen tolerant režim, jinak prázdné/chybí)
        **({"layer_errors": layer_errors} if layer_errors else {}),
    }


# =====================================================================
#  Cesty (§4.9): procedurální (Dijkstra) | reálné (ZABAGED REST)
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
        curve_px = [_grid_to_px(gx, gy) for gx, gy in curve_grid]
        code = ISOM_ROAD if k == 0 else ISOM_FOOTPATH    # hlavní plná / vedlejší čárkovaná
        _draw_path(draw, pdraw, curve_px, code)
        path_features.append((curve_grid, code))
        paths_info.append({"symbol": code, "symbol_name": PATH_NAME[code],
                           "orientation": "H" if horizontal else "V"})
    return path_features, paths_info


def _generate_real_paths(draw: ImageDraw.ImageDraw, pdraw: ImageDraw.ImageDraw,
                         lat: float, lon: float, geo_bbox: tuple) -> tuple[list, list]:
    """Reálné cesty (real-půlka §4.9): komunikace ze ZABAGED REST pro tentýž výsek.

    Stáhne komunikace (zabaged.fetch_paths), mapuje na ISOM (zabaged.map_path_to_isom),
    transformuje S-JTSK → grid (inverze _write_contours_geojson: Y-flip, sever = ymax =
    gy 0) → px a kreslí dle ISOM stylu. Reálné linie jsou už hladké (vektor z reality) →
    žádný splajn. Výsek je TENTÝŽ jako u DMR vrstevnic (sdílený build_bbox) → cesty sednou
    na terén. Vrací (path_features grid, paths_info).
    """
    from zabaged import fetch_paths, map_path_to_isom
    feats = fetch_paths(lat, lon, GW, GH, TILE_M)
    paths_info: list[dict] = []
    path_features: list[tuple] = []
    for f in feats:
        code = map_path_to_isom(f["layer"], f["props"])
        for line in f["lines"]:
            curve_grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            curve_px = [_grid_to_px(gx, gy) for gx, gy in curve_grid]
            if len(curve_px) < 2:
                continue
            _draw_path(draw, pdraw, curve_px, code)
            path_features.append((curve_grid, code))
            paths_info.append({"symbol": code, "symbol_name": PATH_NAME[code],
                               "layer": f["layer"]})
    return path_features, paths_info


def _generate_real_water(draw: ImageDraw.ImageDraw, wdraw: ImageDraw.ImageDraw,
                         lat: float, lon: float, geo_bbox: tuple) -> tuple[list, list, list]:
    """Reálná voda (real-půlka hydrografie, Sez. 17): toky + plochy ze ZABAGED REST.

    Mirror _generate_real_paths: stáhne vodu (zabaged.fetch_water), mapuje na ISOM
    (map_water_to_isom; None = podzemní tok → přeskočit), transformuje S-JTSK → grid
    (Y-flip, sever = ymax) → px a kreslí (toky linie 304/305/306, plochy polygon 301).
    Tentýž výsek jako DMR/cesty (sdílený build_bbox) → voda sedne na terén. Reálné linie
    jsou hladké (vektor z reality) → žádný splajn. Vrací (line_features, area_features,
    water_info) v souřadnicích MŘÍŽKY (zdroj pro vektor/OMAP).
    """
    from zabaged import fetch_water, map_water_to_isom
    line_feats, area_feats = fetch_water(lat, lon, GW, GH, TILE_M)
    line_features: list[tuple] = []
    area_features: list[tuple] = []
    water_info: list[dict] = []
    for f in line_feats:
        code = map_water_to_isom(f["layer"], f["props"])
        if code is None:                       # podzemní tok → nekreslit
            continue
        for line in f["lines"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            px = [_grid_to_px(gx, gy) for gx, gy in grid]
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
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in ring]
            px = [_grid_to_px(gx, gy) for gx, gy in grid]
            if len(px) < 3:
                continue
            _draw_water_area(draw, wdraw, px, code)
            area_features.append((grid, code))
            water_info.append({"symbol": code, "symbol_name": WATER_NAME[code], "kind": "area",
                               "layer": f["layer"]})
    return line_features, area_features, water_info


def _generate_real_buildings(draw: ImageDraw.ImageDraw, bdraw: ImageDraw.ImageDraw,
                             lat: float, lon: float, geo_bbox: tuple) -> tuple[list, list]:
    """Reálné budovy (real-půlka, Sez. 18; RAW od Sez. 27): plochy ze ZABAGED → ISOM 521.

    Kreslí se PŘESNĚ jako vodní plocha (_generate_real_water): SYROVÝ ZABAGED půdorys
    (S-JTSK → grid → px → polygon), BEZ generalizace i displacementu. Rozhodnutí uživatele
    Sez. 27 („kresli budovy jako vodu"): kartografická generalizace (DP/orthogonalizace/min-size)
    i displacement ničily/posouvaly skutečný tvar a polohu (verify: budova 1028994 = 15 vrcholů
    → 5 zkomolených). Voda je věrná právě proto, že je RAW — budovy teď stejně. Vrací
    (area_features [(grid, code)], building_info) v souřadnicích MŘÍŽKY (zdroj pro .omap)."""
    from zabaged import fetch_buildings, map_building_to_isom
    feats = fetch_buildings(lat, lon, GW, GH, TILE_M)
    area_features: list[tuple] = []
    building_info: list[dict] = []
    for f in feats:
        code = map_building_to_isom(f["layer"], f["props"])
        if code is None:
            continue
        for ring in f["rings"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in ring]
            px = [_grid_to_px(gx, gy) for gx, gy in grid]
            if len(px) < 3:
                continue
            _draw_building_area(draw, bdraw, px, code)
            area_features.append((grid, code))
            building_info.append({"symbol": code, "symbol_name": BUILDING_NAME[code],
                                  "kind": "area", "layer": f["layer"]})
    return area_features, building_info


def _generate_real_powerlines(draw: ImageDraw.ImageDraw, eldraw: ImageDraw.ImageDraw,
                              lat: float, lon: float, geo_bbox: tuple,
                              pseudorealistic: bool) -> tuple[list, list]:
    """Reálné el. vedení (real-půlka, Sez. 24): Elektrické_vedení ze ZABAGED REST → ISOM 510.

    Dvě fáze (projekce vs pseudorealistická dekorace, viz GLOSSARY):
      Fáze 1 (vždy): holá tenká linie + kolmé příčky na poloze REÁLNÝCH sloupů
        (Stožár_elektrického_vedení) — příčky odpovídají sloupům (běžci se jimi řídí).
      Fáze 2 (pseudorealistic=True): linie BEZ jediného evidovaného sloupu poblíž dostane
        rovnoměrné příčky (dekorace „vypadá jako vedení"; poloha vymyšlená). Linie se sloupy
        zůstanou poctivě jen se sloupovými příčkami.

    Mirror _generate_real_paths (S-JTSK → grid → px, sdílený výsek). Vrací (powerline_features
    grid, powerlines_info). Příčky se NEukládají do features (vektor/OMAP nese jen osu vedení).
    """
    from zabaged import fetch_powerlines, fetch_powerline_masts, map_powerline_to_isom
    feats = fetch_powerlines(lat, lon, GW, GH, TILE_M)
    masts_px = [_grid_to_px(*_sjtsk_to_grid(x, y, geo_bbox))
                for x, y in fetch_powerline_masts(lat, lon, GW, GH, TILE_M)]
    code = ISOM_POWERLINE
    color, cls, width = C_BLACK, POWERLINE_CLASS[code], POWERLINE_STYLE[code][1]
    powerlines_info: list[dict] = []
    powerline_features: list[tuple] = []
    lines_px: list[list[tuple[float, float]]] = []
    # 1) holé linie vedení (osa) + záznam do features
    for f in feats:
        c = map_powerline_to_isom(f["layer"], f["props"])
        for line in f["lines"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            px = [_grid_to_px(gx, gy) for gx, gy in grid]
            if len(px) < 2:
                continue
            _draw_powerline(draw, eldraw, px, c)
            powerline_features.append((grid, c))
            powerlines_info.append({"symbol": c, "symbol_name": POWERLINE_NAME[c],
                                    "layer": f["layer"]})
            lines_px.append(px)
    # 2) fáze 1: příčka na každém reálném sloupu (orientace dle nejbližšího segmentu vedení)
    for mx, my in masts_px:
        ux, uy, _ = _nearest_seg(mx, my, lines_px)
        _draw_tick_at(draw, eldraw, mx, my, ux, uy, color, cls, width, POWERLINE_TICK_HALF_PX)
    # 3) fáze 2 (pseudorealistic): linie bez sloupu poblíž → rovnoměrné příčky (dekorace)
    if pseudorealistic:
        for px in lines_px:
            has_mast = any(_nearest_seg(mx, my, [px])[2] <= POWERLINE_MAST_SNAP_PX
                           for mx, my in masts_px)
            if not has_mast:
                _draw_perp_ticks(draw, eldraw, px, color, cls, width,
                                 POWERLINE_TICK_SPACING_PX, POWERLINE_TICK_HALF_PX)
    return powerline_features, powerlines_info


def _generate_real_railways(draw: ImageDraw.ImageDraw, rdraw: ImageDraw.ImageDraw,
                            lat: float, lon: float, geo_bbox: tuple) -> tuple[list, list]:
    """Reálné železniční tratě (real-půlka, Sez. 28): Železniční_trať ze ZABAGED REST → ISOM 509.

    Čistá projekce tvrdých dat (fáze 1) — žádná pseudorealistická dekorace (na rozdíl od vedení
    nemá co domýšlet). Mirror _generate_real_powerlines bez sloupů/příček (S-JTSK → grid → px,
    sdílený výsek). Vrací (railway_features grid, railways_info)."""
    from zabaged import fetch_railways, map_railway_to_isom
    feats = fetch_railways(lat, lon, GW, GH, TILE_M)
    railways_info: list[dict] = []
    railway_features: list[tuple] = []
    for f in feats:
        c = map_railway_to_isom(f["layer"], f["props"])
        for line in f["lines"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            px = [_grid_to_px(gx, gy) for gx, gy in grid]
            if len(px) < 2:
                continue
            _draw_railway(draw, rdraw, px, c)
            railway_features.append((grid, c))
            railways_info.append({"symbol": c, "symbol_name": RAILWAY_NAME[c],
                                  "layer": f["layer"]})
    return railway_features, railways_info


def _generate_real_paved(draw: ImageDraw.ImageDraw, adraw: ImageDraw.ImageDraw,
                         lat: float, lon: float, geo_bbox: tuple) -> tuple[list, list]:
    """Reálné zpevněné plochy / kolejiště (real-půlka, Sez. 28): plochy ze ZABAGED → ISOM 501.

    Mirror _generate_real_buildings (RAW S-JTSK → grid → px → polygon, bez generalizace).
    Kolejiště = nádražní kolejová plocha (jednotlivé koleje data nemodelují jako linie). Vrací
    (area_features [(grid, code)], paved_info) v souřadnicích MŘÍŽKY (zdroj pro .omap)."""
    from zabaged import fetch_paved_areas, map_paved_to_isom
    feats = fetch_paved_areas(lat, lon, GW, GH, TILE_M)
    area_features: list[tuple] = []
    paved_info: list[dict] = []
    for f in feats:
        code = map_paved_to_isom(f["layer"], f["props"])
        for ring in f["rings"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in ring]
            px = [_grid_to_px(gx, gy) for gx, gy in grid]
            if len(px) < 3:
                continue
            _draw_paved_area(draw, adraw, px, code)
            area_features.append((grid, code))
            paved_info.append({"symbol": code, "symbol_name": PAVED_NAME[code],
                               "kind": "area", "layer": f["layer"]})
    return area_features, paved_info


def _generate_real_rocks(draw: ImageDraw.ImageDraw, rdraw: ImageDraw.ImageDraw,
                         lat: float, lon: float,
                         geo_bbox: tuple) -> tuple[list, list, list]:
    """Reálné skály a balvany (real-půlka, Sez. 30): MVP rozsah 204/207/206 ze ZABAGED.

    Tři vrstvy ZABAGED → tři ISOM symboly (KISS, vrstva → jeden symbol jako budovy→521):
      Osamělý_balvan__skála__skalní_suk  → 204 Boulder            (bod, plný černý kruh)
      Skupina_balvanů__bod_              → 207 Boulder cluster    (bod, plný černý trojúhelník)
      Skalní_útvary                      → 206 Gigantic boulder   (plná černá plocha)

    Smoothing polygonů (původní A2) i hybridní 202/206 podle plochy (zvažováno Q2) ZAVRŽENO
    uživatelem v průběhu sezení: ZABAGED polygony jsou už dost detailní (~120 vrcholů na 32×32 m
    polygon → plynulý obrys), a hybridní rozhodování nemělo datový podklad (vrstva nese jen
    `jmeno`, žádný typ/výška). Drift po stěně argumentů → KISS jedno mapování per vrstva.

    Vrací (rock_point_features [(gx, gy, code)], rock_area_features [(grid_ring, code)], rocks_info).
    Body a plochy oddělené (paralela s vodou: line_features / area_features) — .omap export
    je řeší různými objekty (point_object vs area)."""
    from zabaged import (fetch_boulders, fetch_boulder_clusters, fetch_rock_areas,
                         map_boulder_to_isom, map_boulder_cluster_to_isom, map_rock_area_to_isom)

    rock_point_features: list[tuple] = []      # (gx, gy, code) — body 204/207
    rock_area_features: list[tuple] = []       # (grid_ring, code) — plochy 206
    rocks_info: list[dict] = []

    # 1) Osamělé balvany → 204. Bod ZABAGED v S-JTSK → grid → px → kruh.
    for x, y in fetch_boulders(lat, lon, GW, GH, TILE_M):
        code = map_boulder_to_isom("Osamělý_balvan__skála__skalní_suk", {})
        gx, gy = _sjtsk_to_grid(x, y, geo_bbox)
        px, py = _grid_to_px(gx, gy)
        _draw_boulder(draw, rdraw, px, py)
        rock_point_features.append((gx, gy, code))
        rocks_info.append({"symbol": code, "symbol_name": ROCK_NAME[code], "kind": "point",
                           "layer": "Osamělý_balvan__skála__skalní_suk"})

    # 2) Skupiny balvanů (bod) → 207 Boulder cluster
    for x, y in fetch_boulder_clusters(lat, lon, GW, GH, TILE_M):
        code = map_boulder_cluster_to_isom("Skupina_balvanů__bod_", {})
        gx, gy = _sjtsk_to_grid(x, y, geo_bbox)
        px, py = _grid_to_px(gx, gy)
        _draw_boulder_cluster(draw, rdraw, px, py)
        rock_point_features.append((gx, gy, code))
        rocks_info.append({"symbol": code, "symbol_name": ROCK_NAME[code], "kind": "point",
                           "layer": "Skupina_balvanů__bod_"})

    # 3) Skalní útvary (polygon) → 206 Gigantic boulder (vždy, plná plocha)
    for f in fetch_rock_areas(lat, lon, GW, GH, TILE_M):
        code = map_rock_area_to_isom(f["layer"], f["props"])
        for ring in f["rings"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in ring]
            px = [_grid_to_px(gx, gy) for gx, gy in grid]
            if len(px) < 3:
                continue
            _draw_gigantic_boulder(draw, rdraw, px)
            rock_area_features.append((grid, code))
            rocks_info.append({"symbol": code, "symbol_name": ROCK_NAME[code], "kind": "area",
                               "layer": f["layer"]})

    return rock_point_features, rock_area_features, rocks_info


def _nearest_segment_tangent(bx: float, by: float,
                             lines_px: list[list[tuple[float, float]]]
                             ) -> tuple[float, float] | None:
    """Pro bod (bx, by) najde nejbližší segment v `lines_px` a vrátí jeho tangentu jednotkovou.

    Vrací None, když `lines_px` prázdné. Použito pro orientaci lávky kolmo k nejbližšímu
    vodnímu toku (Sez. 31; paralela `_ropik_outward` PCA, ale jednodušší — lávka má jen
    jeden tok pod sebou, ne lokální klastr). Segment = sousední dvojice bodů polyline."""
    best_d2 = float("inf")
    best_dir: tuple[float, float] | None = None
    for line in lines_px:
        for i in range(1, len(line)):
            x1, y1 = line[i - 1]
            x2, y2 = line[i]
            dx, dy = x2 - x1, y2 - y1
            seg_len2 = dx * dx + dy * dy
            if seg_len2 < 1e-9:
                continue
            # projekce bodu (bx,by) na segment: t∈[0,1] → kolmá vzdálenost
            t = max(0.0, min(1.0, ((bx - x1) * dx + (by - y1) * dy) / seg_len2))
            cx, cy = x1 + t * dx, y1 + t * dy
            d2 = (bx - cx) ** 2 + (by - cy) ** 2
            if d2 < best_d2:
                best_d2 = d2
                seg_len = math.sqrt(seg_len2)
                best_dir = (dx / seg_len, dy / seg_len)
    return best_dir


def _generate_real_bridges(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                           lat: float, lon: float, geo_bbox: tuple,
                           water_lines_px: list[list[tuple[float, float]]]
                           ) -> tuple[list, list, list]:
    """Reálné mosty a lávky (real-půlka, Sez. 31): Most→512 + Lávka→512.2 ze ZABAGED REST.

    Most = LineString (most přes vodu/komunikaci) → linie + V-křídla. Lávka má 2 ZABAGED
    vrstvy (linie + bod); render obou → 512.2 (kolmá čárka). Bodová lávka nemá orientaci
    v atributech → otáčí se kolmo k nejbližšímu vodnímu toku (`water_lines_px` jsou px
    polylinie z `_generate_real_water` — bez nich fallback rot=0 = horizontální čárka).
    Liniová lávka renderuje 512.2 čárku UPROSTŘED linie kolmo na osu lávky (lávka VEDE
    PŘES vodu — středová poloha = nad osou toku).

    Vrací (bridge_features [(grid, ISOM_BRIDGE)], footbridge_features [(gx, gy, ISOM_FOOTBRIDGE)],
    bridges_info). Most je liniový → grid polyline; lávka = body → (gx, gy)."""
    from zabaged import (fetch_bridges, fetch_footbridges,
                         map_bridge_to_isom, map_footbridge_to_isom)

    bridge_features: list[tuple] = []           # (grid_polyline, 512) pro .omap
    footbridge_features: list[tuple] = []       # (gx, gy, 5122) pro .omap (point objekty)
    bridges_info: list[dict] = []

    # 1) Mosty (Most, linie) → 512. RAW kreslení polyline + V-křídla na koncích.
    for f in fetch_bridges(lat, lon, GW, GH, TILE_M):
        code = map_bridge_to_isom(f["layer"], f["props"])
        for line in f["lines"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            px = [_grid_to_px(gx, gy) for gx, gy in grid]
            if len(px) < 2:
                continue
            _draw_bridge(draw, mdraw, px)
            bridge_features.append((grid, code))
            bridges_info.append({"symbol": code, "symbol_name": BRIDGE_NAME[code],
                                 "kind": "line", "layer": f["layer"],
                                 "jmeno": f["props"].get("jmeno")})

    # 2) Lávky → 512.2. Linie + bod (Sez. 31 probe Novina: 0 + 1 = 1 prvek).
    line_feats, points = fetch_footbridges(lat, lon, GW, GH, TILE_M)
    code_fb = map_footbridge_to_isom("Lávka (bod)", {})  # 5122

    # 2a) Lávky linie: kolmá čárka uprostřed osy lávky (kolmo na osu lávky =
    # rovnoběžně s tangentou v polovině) → osa čárky vznikne rotací podle tangenty.
    for f in line_feats:
        for line in f["lines"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            px = [_grid_to_px(gx, gy) for gx, gy in grid]
            if len(px) < 2:
                continue
            # střed linie = polovina celkové délky
            mid_i = len(px) // 2
            cx, cy = px[mid_i]
            # tangenta v poloviční pozici (= směr lávky); čárka 512.2 je rovnoběžná s lávkou
            prev_i = max(0, mid_i - 1)
            next_i = min(len(px) - 1, mid_i + 1)
            dx = px[next_i][0] - px[prev_i][0]
            dy = px[next_i][1] - px[prev_i][1]
            rot = math.atan2(dy, dx)
            _draw_footbridge_point(draw, mdraw, cx, cy, rot)
            gx_mid, gy_mid = grid[mid_i]
            footbridge_features.append((gx_mid, gy_mid, code_fb, rot))
            bridges_info.append({"symbol": code_fb, "symbol_name": BRIDGE_NAME[code_fb],
                                 "kind": "line", "layer": f["layer"],
                                 "jmeno": f["props"].get("jmeno")})

    # 2b) Lávky body: orientace kolmo k nejbližšímu vodnímu toku (tangenta vody → osa
    # lávky kolmá → rot = tangenta_vody + 90°). Bez vody fallback rot=0.
    for x, y in points:
        gx, gy = _sjtsk_to_grid(x, y, geo_bbox)
        px_b, py_b = _grid_to_px(gx, gy)
        tg = _nearest_segment_tangent(px_b, py_b, water_lines_px)
        if tg is None:
            rot = 0.0    # fallback: horizontální čárka (žádná voda ve výseku)
        else:
            # lávka KOLMO k vodě → osa lávky je normála toku, čárka 512.2 je rovnoběžná
            # s lávkou (template orientace), tj. rot = úhel normály = atan2(-tx, ty).
            tx, ty = tg
            rot = math.atan2(-tx, ty)
        _draw_footbridge_point(draw, mdraw, px_b, py_b, rot)
        footbridge_features.append((gx, gy, code_fb, rot))
        bridges_info.append({"symbol": code_fb, "symbol_name": BRIDGE_NAME[code_fb],
                             "kind": "point", "layer": "Lávka (bod)"})

    return bridge_features, footbridge_features, bridges_info


# =====================================================================
#  Řopíky / lehké opevnění LO37 — fáze 1 (projekce reálných dat), asset placement (Sez. 27)
# =====================================================================
# Řopík NENÍ prostý ISOM symbol, ale ASSET (budova 521 + vrstevnice náspu 101) — dvojici
# kreslí uživatel v OOM (asset pattern, Sez. 26). Generátor ho stáhne (ZABAGED Bunkr LO37),
# natočí (normála na lokální linii řopíků, „čelní zasypaný násep" = asset-sever VEN k nejbližší
# státní hranici — univerzální ČR) a vloží na každou reálnou polohu. Projekce, ne dekorace.
ROPIK_ASSET_PATH = Path(__file__).resolve().parent.parent.parent / "asset" / "ropik_10000.omap"
ROPIK_PCA_K = 6        # počet nejbližších řopíků pro odhad směru lokální linie (PCA)
_ROPIK_GEOM_CACHE: tuple | None = None   # (building_ring_um, contour_lines_um) — načteno jednou


def _load_ropik_asset() -> tuple[list, list]:
    """Načte geometrii řopík assetu (ropik_10000.omap): 1 budova 521 + vrstevnice 101.

    Vrací (building_ring, contour_lines) v PAPER µm relativně k počátku assetu (0,0 = poloha
    bunkru); asset-sever = −y (jak uživatel kreslí „sever nahoru"). Bere JEN mapové objekty
    z bloku <objects> (NE grafiku symbolů v <symbols> — to byl dřívější parsovací omyl).
    OOM coord flagy (1 = bezier řídicí, 18 = close) ignorujeme → polylinie/polygon. Cachuje."""
    global _ROPIK_GEOM_CACHE
    if _ROPIK_GEOM_CACHE is not None:
        return _ROPIK_GEOM_CACHE
    import re
    xml = ROPIK_ASSET_PATH.read_text(encoding="utf-8")
    syms = {m.group(1): m.group(2)
            for m in re.finditer(r'<symbol\b[^>]*\bid="(\d+)"[^>]*\bcode="([^"]+)"', xml)}
    mo = re.search(r'<objects count="\d+">(.*?)</objects>', xml, re.S)   # jen mapové objekty
    if mo is None:
        raise ValueError(f"Řopík asset {ROPIK_ASSET_PATH.name} nemá blok <objects>")
    building: list = []
    contours: list = []
    for o in re.finditer(r'<object\b[^>]*\bsymbol="(\d+)"[^>]*>.*?<coords count="\d+">(.*?)</coords>',
                         mo.group(1), re.S):
        code = syms.get(o.group(1))
        pts = [(float(p[0]), float(p[1]))                       # x y [flag] → flag ignorujeme
               for tok in o.group(2).strip().rstrip(";").split(";")
               if len(p := tok.split()) >= 2]
        if code == "521":
            building = pts
        elif code == "101":
            contours.append(pts)
    if not building:
        raise ValueError(f"Řopík asset {ROPIK_ASSET_PATH.name} postrádá budovu 521")
    _ROPIK_GEOM_CACHE = (building, contours)
    return _ROPIK_GEOM_CACHE


def _ropik_outward(bx: float, by: float, pts_arr: np.ndarray,
                   border_px: list[list[tuple[float, float]]]) -> tuple[float, float]:
    """Jednotkový směr „ven" pro řopík v px (bx,by): normála na lokální linii řopíků (PCA
    K nejbližších) otočená k nejbližší STÁTNÍ hranici. Bez hranice ve výseku → jen normála
    (strana nejednoznačná, ale konzistentní podél linie). px frame: x vpravo, y dolů, sever nahoře."""
    d2 = (pts_arr[:, 0] - bx) ** 2 + (pts_arr[:, 1] - by) ** 2
    nb = pts_arr[np.argsort(d2)[:ROPIK_PCA_K]]
    if len(nb) >= 2:
        # PCA: hlavní vlastní vektor kovariance = směr linie řopíků
        cov = np.cov((nb - nb.mean(axis=0)).T)
        w, v = np.linalg.eigh(cov)
        d = v[:, int(np.argmax(w))]
    else:
        d = np.array([1.0, 0.0])
    nx, ny = -float(d[1]), float(d[0])                  # normála na linii
    norm = math.hypot(nx, ny) or 1.0
    nx, ny = nx / norm, ny / norm
    if border_px:                                       # otoč normálu k nejbližšímu bodu hranice
        best, bestd = None, float("inf")
        for line in border_px:
            for px, py in line:
                dd = (px - bx) ** 2 + (py - by) ** 2
                if dd < bestd:
                    bestd, best = dd, (px, py)
        if best is not None and nx * (best[0] - bx) + ny * (best[1] - by) < 0:
            nx, ny = -nx, -ny
    return nx, ny


def _generate_real_ropiky(draw: ImageDraw.ImageDraw, bdraw: ImageDraw.ImageDraw,
                          cdraw: ImageDraw.ImageDraw, lat: float, lon: float,
                          geo_bbox: tuple) -> tuple[list, list]:
    """Řopíky (LO37) jako asset (fáze 1, real, Sez. 27): bod ZABAGED Bunkr → asset natočený
    normálou linie řopíků, „čelní násep" (asset-sever) VEN k nejbližší státní hranici.

    Kreslí budovu (černá 521) na rgb (`draw`) + masku budov (`bdraw`) a vrstevnici náspu
    (hnědá 101) na rgb + masku vrstevnic (`cdraw`). Vrací (ropik_features [(grid_geom, code)],
    ropik_info) pro .omap (řopík vrstevnice NEjde do contours.geojson — není to DMR izolinie)."""
    from zabaged import fetch_bunkers, fetch_state_border
    pts_sjtsk = fetch_bunkers(lat, lon, GW, GH, TILE_M)
    if not pts_sjtsk:                                   # jinde než u hranic 0 řopíků
        return [], []
    bunkers_px = [_grid_to_px(*_sjtsk_to_grid(x, y, geo_bbox)) for x, y in pts_sjtsk]
    border_px = [[_grid_to_px(*_sjtsk_to_grid(x, y, geo_bbox)) for x, y in line]
                 for line in fetch_state_border(lat, lon, GW, GH, TILE_M)]
    building_um, contours_um = _load_ropik_asset()
    K = PX_PER_MM / 1000.0          # asset µm → px (asset i mapa jsou 1:MAP_SCALE → bez měřítka)
    pts_arr = np.array(bunkers_px)
    ropik_features: list = []
    ropik_info: list = []

    def _to_grid(pts_px):           # px → grid (inverze _grid_to_px) pro .omap export
        return [(x / W * (GW - 1), y / H * (GH - 1)) for x, y in pts_px]

    for bx, by in bunkers_px:
        ux, uy = _ropik_outward(bx, by, pts_arr, border_px)
        # rotace: asset-sever (0,−1) → směr „ven" (ux,uy). Odvozeno z R(a)·(0,−1)=(sa,−ca):
        a = math.atan2(ux, -uy)
        ca, sa = math.cos(a), math.sin(a)

        def place(pts_um):          # asset µm (rel. počátku) → px (rotace + posun na bunkr)
            out = []
            for mx, my in pts_um:
                px_, py_ = mx * K, my * K
                out.append((bx + px_ * ca - py_ * sa, by + px_ * sa + py_ * ca))
            return out

        bring = place(building_um)
        _draw_building_area(draw, bdraw, bring, ISOM_BUILDING)      # černá 521 + maska budov
        ropik_features.append((_to_grid(bring), 521))
        for cline_um in contours_um:
            cline = place(cline_um)
            if len(cline) >= 2:
                draw.line(cline, fill=C_BROWN, width=1)            # hnědý násep
                cdraw.line(cline, fill=255, width=1)               # do masky vrstevnic
                ropik_features.append((_to_grid(cline), 101))
        ropik_info.append({"symbol": 521, "kind": "ropik"})
    return ropik_features, ropik_info


# =====================================================================
#  Hlavní generování
# =====================================================================
def _try_layer(label: str, fn, default, tolerant: bool, errors: dict[str, str]):
    """Zavolá kreslení reálné vrstvy `fn`; v tolerantním režimu pohltí selhání REST/sítě.

    `tolerant=False` (default, single-mapa CLI) = výjimka propadne ven: kdo žádá
    `--water real`, má vědět, že ZABAGED spadl. `tolerant=True` (dávkový batch přes
    mnoho lokalit) = vrstvu vynech, zaloguj varování, zapiš důvod do `errors` a vrať
    `default` (prázdné struktury) → mapa se vyrobí z toho, co je. Pozor: prázdná data
    (0 features v bboxu, jako pramen 312 ve Sově vrchu) výjimku NEvyhodí — `fn` vrátí
    prázdné seznamy normálně; sem se dostane jen reálné selhání dotazu (HTTP/síť/parse).
    """
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 — záměrně široké: izolace jedné vrstvy v dávce
        if not tolerant:
            raise
        errors[label] = str(e)
        _log.warning("vrstva '%s' vynechána (ZABAGED/síť selhala): %s", label, e)
        return default


def synthesize_pseudorealistic_map(
        lat: float, lon: float, w_km: float, h_km: float,
        only_real: bool = False, out_dir: str = "output",
        *,                                    # vše dál keyword-only — z popředí API zmizí
        seed: int = 1, rug: float = 0.5, det: float = 0.5,
        terrain: str = "real", paths: str = "real", water: str = "real",
        paved: str = "real", buildings: str = "real", powerlines: str = "real",
        railways: str = "real", ropiky: str = "real", rocks: str = "real",
        bridges: str = "real",
        tolerant: bool = False, ortho: bool = True, ortho_mpp: float = 0.5) -> Path:
    """Syntetizuje pseudorealistickou mapu lokality (lat, lon) o rozměru w_km×h_km.

    Reframe Sez. 23 (IDEAS „synthesize_pseudorealistic_map"): real-větev je *prediktor
    mapy* — skládá dva zdroje (DMR výškopis + ZABAGED vektor) do mapy konkrétního místa.
    Vrací cestu k výstupní složce (`out_dir`). Dvě oddělitelné fáze (Sez. 24, GLOSSARY):
    fáze 1 = projekce tvrdých dat (vždy), fáze 2 = pseudorealistická dekorace symbolů,
    co v datech nejsou (řízena `only_real`; viz níže).

    `w_km`×`h_km` [km] určují velikost výseku — funkce z nich na začátku odvodí rozměrové
    globály (`_apply_extent`: grid GW×GH, plátno W×H, svět v metrech) při konstantním
    rozlišení (PX_PER_MM), takže mm-odvozené prahy (budovy, displacement) platí vždy.

    `only_real=True` (CLI `--only-real`) vypne fázi 2 (pseudorealistickou dekoraci nad
    rámec tvrdých dat — dnes příčky vedení mimo evidované sloupy); default `False` = fáze
    2 zapnuta. Uvnitř se převede na `pseudorealistic` (doménový pojem, GLOSSARY).

    Keyword-only ocas (`seed`/`rug`/`det`/`terrain`/`paths`/…) drží i původní procedurální
    (noise) větev a per-vrstva volbu — default `terrain="real"` (prediktor), `terrain="noise"`
    = fraktální šum (Option 1, §8.5). U reálného terénu se `rug` na výškopis neuplatní.

    `paths="real"` (default) = reálné komunikace ze ZABAGED REST (real-půlka §4.9);
    `paths="proc"` = procedurální Dijkstra cesty (§9). `real` VYŽADUJE `terrain="real"`
    — reálné cesty mají S-JTSK souřadnice a párují se přes sdílený výsek; noise výsek
    je v lokálních metrech bez georef → spárovat nelze.

    `buildings="real"` = reálné budovy/stavby ze ZABAGED REST (real-půlka, ISOM 521);
    také VYŽADUJE `terrain="real"` (stejný georef důvod jako cesty/voda).

    `tolerant=True` (dávkový režim batch.py přes mnoho lokalit) = selhání REST/sítě u jedné
    reálné vrstvy ji vynechá místo pádu celé mapy; vynechané vrstvy se zapíšou do
    `meta.json` (`layer_errors`). Default `False` = single-mapa CLI selže hlučně.

    Rastrový z-order (pořadí kreslení do PNG): vrstevnice (§4.5) → bodové symboly extrémů
    (§4.10) → zpevněné plochy (501) → voda → cesty (§4.9) → el. vedení (510) → železnice (509) → budovy (521 navrch). Je to VĚDOMÁ generátorová volba pro
    čitelný feeder (hnědý terén vespod, černé komunikace/stavby dominují navrchu) — NE kopie
    OOM color draw orderu. Ten je jiná rovina: priorita BAREV (Sez. 18; černá 521 je tam
    naopak POD hnědou vrstevnicí), patří do OOM Colors okna = uživatelova doména, ne rastr.
    `rug` řídí členitost terénu (jen noise), `det` počet proc cest.

    Malé uzavřené vrstevnice (lokální extrémy) se generalizují na bodové symboly
    (§4.10): kopeček 109/110, prohlubeň 111 — místo prstence se kreslí značka a GT
    se zapíše do `mask_symbols.png` + seznam `point_symbols` v meta.json.

    Vedle rastru (rgb.png + GT masky) zapisuje `contours.geojson` — vrstevnice jako
    vektorové linie s ISOM symbolem (101/102), georeferencované v S-JTSK pro real
    terén (§9). To je „skutečný vektor", ne pixely: contourpy dává polylinie přímo.
    """
    # Velikost výseku → rozměrové globály (grid/plátno/svět) PŘED jakýmkoli generováním.
    # Dřív to dělal main() zvenčí; teď w_km/h_km jsou parametry → odpovědnost patří sem.
    _apply_extent(w_km, h_km)
    # only_real (veřejné API/CLI) → pseudorealistic (interní doménový pojem, fáze 2 dekorace).
    # Převod na hranici drží zbytek kódu (i _generate_real_powerlines/_build_meta) beze změny.
    pseudorealistic = not only_real
    if paths == "real" and terrain != "real":
        raise ValueError("--paths real vyžaduje --terrain real (reálné cesty potřebují "
                         "S-JTSK georef výseku; noise terén je v lokálních metrech).")
    if water == "real" and terrain != "real":
        raise ValueError("--water real vyžaduje --terrain real (reálná voda potřebuje "
                         "S-JTSK georef výseku; noise terén je v lokálních metrech).")
    if buildings == "real" and terrain != "real":
        raise ValueError("--buildings real vyžaduje --terrain real (reálné budovy potřebují "
                         "S-JTSK georef výseku; noise terén je v lokálních metrech).")
    if powerlines == "real" and terrain != "real":
        raise ValueError("--powerlines real vyžaduje --terrain real (reálné el. vedení potřebuje "
                         "S-JTSK georef výseku; noise terén je v lokálních metrech).")
    if railways == "real" and terrain != "real":
        raise ValueError("--railways real vyžaduje --terrain real (reálná železnice potřebuje "
                         "S-JTSK georef výseku; noise terén je v lokálních metrech).")
    if paved == "real" and terrain != "real":
        raise ValueError("--paved real vyžaduje --terrain real (reálná zpevněná plocha potřebuje "
                         "S-JTSK georef výseku; noise terén je v lokálních metrech).")
    if ropiky == "real" and terrain != "real":
        raise ValueError("--ropiky real vyžaduje --terrain real (řopíky ze ZABAGED potřebují "
                         "S-JTSK georef výseku; noise terén je v lokálních metrech).")
    if rocks == "real" and terrain != "real":
        raise ValueError("--rocks real vyžaduje --terrain real (reálné skály/balvany potřebují "
                         "S-JTSK georef výseku; noise terén je v lokálních metrech).")
    if bridges == "real" and terrain != "real":
        raise ValueError("--bridges real vyžaduje --terrain real (reálné mosty/lávky potřebují "
                         "S-JTSK georef výseku; noise terén je v lokálních metrech).")
    # Požadavek je jen DETERMINISMUS (stejný seed + parametry → stejná mapa), proto
    # stačí korektní numpy generátor (PCG64); bitová shoda s JS referencí netřeba.
    rng = np.random.default_rng(seed)
    _log.info("synthesize %.5f, %.5f · %g×%g km → grid %d×%d, plátno %d×%d px, 1:%d",
              lat, lon, w_km, h_km, GW, GH, W, H, MAP_SCALE)

    # --- výškopis: reálný (DMR 5G) nebo syntetický šum ---
    if terrain == "real":
        # Lazy import: pyproj je závislost jen pro Option 2; Option 1 zůstává offline.
        from dmr import fetch_elevation_grid, build_bbox
        elev = fetch_elevation_grid(lat, lon, GW, GH, tile_m=TILE_M)  # reálné metry (GH, GW), sever nahoře
        # georef pro vektorový export: skutečný S-JTSK bbox výseku (stejný TILE_M jako fetch)
        geo_bbox = build_bbox(lat, lon, GW, GH, TILE_M)
        crs_epsg: int | None = 5514                              # S-JTSK / Křovák
        _log.info("terén: ČÚZK DMR 5G (%.0f–%.0f m n. m.)", float(elev.min()), float(elev.max()))
    else:
        hbase = fractal(rng, 1.6 + rug * 2.6, 3 + round(rug * 2))  # výškopis (členitost = rug)
        vrange = 25 + rug * 90                                    # převýšení: víc členitosti → víc vrstevnic
        elev = BASE_ELEV + hbase * vrange                         # nadmořská výška [m]
        # georef šumu: skutečné umístění neznáme → lokální metry od (0,0), stejná
        # geometrie výseku jako real (TILE_M × poměr GW/GH). crs=None.
        geo_bbox = (0.0, 0.0, WORLD_W_M, TILE_M)
        crs_epsg = None
        _log.info("terén: fraktální šum (rug=%.2f)", rug)

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
            pts = [_grid_to_px(float(x), float(y)) for x, y in line]
            if len(pts) >= 2:
                draw.line(pts, fill=C_BROWN, width=width)
                cdraw.line(pts, fill=255, width=width)
                contour_features.append((line, symbol))   # grid souřadnice → georef ve vektor exportu
    _log.info("  vrstevnice: %d · body extrémů: %d", len(contour_features), len(point_symbols))

    # --- pomocné vrstevnice (form lines, ISOM 103): jen reálný terén (Sez. 29) ---
    # Čárkovaná vrstevnice na POLOVIČNÍ ekvidistanci (level + 2,5 m). Heuristika fáze 1 z DMR:
    # kreslíme jen úseky v masce `_formline_mask` (mírný svah AND zakřivený terén) — tím se vyhneme
    # ISOM zákazu "intermediate contours" (rovnoběžka na rovnoměrném svahu). Jen `terrain=="real"`:
    # noise terén je umělý perlin (form line tam nemá doménový smysl) a drží proc baseline.
    formline_features: list[tuple] = []
    fmask_img = Image.new("L", (W, H), 0)           # GT maska form lines (§8.1, jediná třída)
    fdraw = ImageDraw.Draw(fmask_img)
    if terrain == "real":
        fmask = _formline_mask(elev, cell_w_m, cell_h_m)
        half = CONTOUR_STEP / 2.0                   # poloviční ekvidistance [m]
        min_len_px = FORMLINE_MIN_LEN_MM * PX_PER_MM
        # poloviční hladina mezi každou dvojicí sousedních vrstevnic = právě JEDNA form line
        # (level+2,5 m) → ISOM pravidlo „jen jedna mezi vrstevnicemi" splněno automaticky
        for level in range(lo, hi + 1, CONTOUR_STEP):
            for line in cont.lines(level + half):
                for seg in _clip_line_to_mask(line, fmask):
                    pts = [_grid_to_px(x, y) for x, y in seg]
                    if _polyline_len_px(pts) < min_len_px:   # ISOM minimální délka (1,1 mm)
                        continue
                    _draw_dashed(draw, fdraw, pts, C_BROWN, FORMLINE_CLASS,
                                 dash=FORMLINE_DASH_PX, gap=FORMLINE_BREAK_PX, width=1)
                    formline_features.append((np.asarray(seg, dtype=float), ISOM_FORMLINE))
        _log.info("  pomocné vrstevnice (103): %d", len(formline_features))

    # --- bodové symboly lokálních extrémů (§4.10): hnědé kopečky/prohlubně ---
    # Rastr z-order: hned po vrstevnicích = POD vodou/cestami/budovami (hnědý terénní detail,
    # černé komunikace ho přirozeně překryjí — tak ho vidí oko na reálné mapě). Sez. 18:
    # opraveno (dřív chybně navrchu → hnědé body přes hlavní cesty).
    sym_mask_img = Image.new("L", (W, H), 0)        # GT maska bodových symbolů (§8.1)
    sdraw = ImageDraw.Draw(sym_mask_img)
    for ps in point_symbols:
        _draw_point_symbol(draw, sdraw, ps)

    # selhání reálných vrstev (jen tolerant režim): {vrstva: důvod} → meta.json. Prázdné = vše OK.
    layer_errors: dict[str, str] = {}

    # --- zpevněné plochy / kolejiště (ISOM 501): reálné ze ZABAGED REST (real-půlka, Sez. 28) ---
    # Rastr z-order: brzy (po terénu/bodech, PŘED vodou/cestami) — hnědá plocha je podklad, na
    # němž leží koleje (509), cesty i budovy. V lesních výsecích bez nádraží = 0 prvků. Jen --paved real.
    paved_area_features: list[tuple] = []
    paved_info: list[dict] = []
    paved_mask_img: Image.Image | None = None
    if paved == "real":
        paved_mask_img = Image.new("L", (W, H), 0)       # GT maska zpevněných ploch (§8.1)
        adraw = ImageDraw.Draw(paved_mask_img)
        paved_area_features, paved_info = _try_layer(
            "paved", lambda: _generate_real_paved(draw, adraw, lat, lon, geo_bbox),
            ([], []), tolerant, layer_errors)
        _log.info("  zpevněné plochy: %d", len(paved_info))

    # --- voda (hydrografie): reálná ze ZABAGED REST (real-půlka, Sez. 17) ---
    # Rastr z-order: PO vrstevnicích/bodech, PŘED cestami — modré toky/plochy leží na hnědém
    # terénu, černé cesty/budovy je překryjí nahoře (čitelnost feederu). Jen --water real.
    water_line_features: list[tuple] = []
    water_area_features: list[tuple] = []
    water_info: list[dict] = []
    water_mask_img: Image.Image | None = None
    if water == "real":
        water_mask_img = Image.new("L", (W, H), 0)      # GT maska vody (§8.1), multi-class
        wdraw = ImageDraw.Draw(water_mask_img)
        water_line_features, water_area_features, water_info = _try_layer(
            "water", lambda: _generate_real_water(draw, wdraw, lat, lon, geo_bbox),
            ([], [], []), tolerant, layer_errors)
        _log.info("  voda: %d (toky+plochy)", len(water_info))

    # --- cesty (§4.9): procedurální (Dijkstra least-cost) nebo reálné (ZABAGED REST) ---
    # Rastr z-order: PO vodě, PŘED budovami. Obě větve sdílí render (_draw_path) i GT masku
    # — liší se jen zdrojem geometrie (proc/real).
    path_mask_img = Image.new("L", (W, H), 0)       # GT maska cest (§8.1), multi-class
    pdraw = ImageDraw.Draw(path_mask_img)
    if paths == "real":
        path_features, paths_info = _try_layer(
            "paths", lambda: _generate_real_paths(draw, pdraw, lat, lon, geo_bbox),
            ([], []), tolerant, layer_errors)
    else:
        # proc cesty (Dijkstra) jsou offline → žádné REST selhání, tolerance se netýká
        path_features, paths_info = _generate_proc_paths(rng, elev, draw, pdraw,
                                                         cell_w_m, cell_h_m, det)
    n_paths = len(paths_info)
    _log.info("  cesty: %d (%s)", n_paths, paths)

    # --- el. vedení (ISOM 510): reálné ze ZABAGED REST (real-půlka, Sez. 24) ---
    # Rastr z-order: PO cestách, PŘED budovami — tenká černá linie s příčkami nad terénem,
    # izomorfní s komunikacemi. NENÍ kotva displacementu (vedení vede NAD budovami, odsazení
    # by lhalo o poloze) → pevná síť zůstává cesty+voda. Jen --powerlines real.
    powerline_features: list[tuple] = []
    powerlines_info: list[dict] = []
    powerline_mask_img: Image.Image | None = None
    if powerlines == "real":
        powerline_mask_img = Image.new("L", (W, H), 0)   # GT maska el. vedení (§8.1)
        eldraw = ImageDraw.Draw(powerline_mask_img)
        powerline_features, powerlines_info = _try_layer(
            "powerlines",
            lambda: _generate_real_powerlines(draw, eldraw, lat, lon, geo_bbox, pseudorealistic),
            ([], []), tolerant, layer_errors)
        _log.info("  el. vedení: %d", len(powerlines_info))

    # --- železnice (ISOM 509): reálná ze ZABAGED REST (real-půlka, Sez. 28) ---
    # Rastr z-order: PO vedení, PŘED budovami — černá trať (čárky + bílý knockout) nad terénem,
    # izomorfní s komunikacemi. V lesních výsecích bez trati = 0 prvků (žádný šum). Jen --railways real.
    railway_features: list[tuple] = []
    railways_info: list[dict] = []
    railway_mask_img: Image.Image | None = None
    if railways == "real":
        railway_mask_img = Image.new("L", (W, H), 0)     # GT maska železnic (§8.1)
        rdraw = ImageDraw.Draw(railway_mask_img)
        railway_features, railways_info = _try_layer(
            "railways",
            lambda: _generate_real_railways(draw, rdraw, lat, lon, geo_bbox),
            ([], []), tolerant, layer_errors)
        _log.info("  železnice: %d", len(railways_info))

    # --- budovy/stavby (§4.x): reálné ze ZABAGED REST (real-půlka, Sez. 18) ---
    # Rastr z-order: ÚPLNĚ NAVRCH — černá plocha budovy překryje vše pod sebou (vizuálně
    # dominantní blok). Pozor: v OOM color orderu je to naopak (521 priorita 8, pod cestami
    # i vrstevnicí) — rastr feederu a OOM separace jsou dvě roviny (Sez. 18). Jen --buildings real.
    building_area_features: list[tuple] = []
    building_info: list[dict] = []
    building_mask_img: Image.Image | None = None
    if buildings == "real":
        building_mask_img = Image.new("L", (W, H), 0)   # GT maska budov (§8.1)
        bdraw = ImageDraw.Draw(building_mask_img)
        # RAW kresba jako vodní plocha (Sez. 27): syrový ZABAGED půdorys, bez generalizace
        # i displacementu (ty ničily tvar/polohu — voda je věrná, protože je RAW).
        building_area_features, building_info = _try_layer(
            "buildings", lambda: _generate_real_buildings(draw, bdraw, lat, lon, geo_bbox),
            ([], []), tolerant, layer_errors)
        _log.info("  budovy: %d (RAW půdorys)", len(building_info))

    # --- řopíky / lehké opevnění LO37 (postprodukce, fáze 1 real, Sez. 27) ---
    # Asset (budova 521 + vrstevnice náspu 101) natočený normálou linie řopíků + „čelní násep"
    # VEN k nejbližší státní hranici. Kreslí se PO budovách (navrch); NEjde přes displacement
    # (pevný asset). Budova → maska budov (vytvoř, je-li --buildings off), násep → maska vrstevnic
    # (cdraw). Features pro .omap (řopík násep NEjde do contours.geojson). Jen --ropiky real.
    ropik_features: list[tuple] = []
    ropik_info: list[dict] = []
    if ropiky == "real":
        if building_mask_img is None:           # řopíky potřebují masku budov i bez --buildings real
            building_mask_img = Image.new("L", (W, H), 0)
            bdraw = ImageDraw.Draw(building_mask_img)
        ropik_features, ropik_info = _try_layer(
            "ropiky",
            lambda: _generate_real_ropiky(draw, bdraw, cdraw, lat, lon, geo_bbox),
            ([], []), tolerant, layer_errors)
        _log.info("  řopíky: %d", len(ropik_info))

    # --- skály / balvany (ISOM 204/207/202/206): reálné ze ZABAGED REST (real-půlka, Sez. 30) ---
    # Rastr z-order: ÚPLNĚ NAVRCH (po budovách+řopících) — replikuje OOM color order, kde
    # 202/204/206/207 mají vyšší prioritu (=draw nahoru) než 521 Building. Hruboskalsko: skály
    # vizuálně dominantní → musí být vidět. V plochém terénu (NL, SV) = 0 prvků (žádný šum).
    # Jen --rocks real. Hybridní 202 vs 206 řeší map_rock_area_to_isom podle plochy polygonu.
    rock_point_features: list[tuple] = []
    rock_area_features: list[tuple] = []
    rocks_info: list[dict] = []
    rock_mask_img: Image.Image | None = None
    if rocks == "real":
        rock_mask_img = Image.new("L", (W, H), 0)        # GT maska skal/balvanů (§8.1), multi-class
        rdraw_rocks = ImageDraw.Draw(rock_mask_img)
        rock_point_features, rock_area_features, rocks_info = _try_layer(
            "rocks",
            lambda: _generate_real_rocks(draw, rdraw_rocks, lat, lon, geo_bbox),
            ([], [], []), tolerant, layer_errors)
        # souhrn po symbolech (KISS: counter via dict — info je už klasifikované)
        by_code: dict[int, int] = {}
        for it in rocks_info:
            by_code[it["symbol"]] = by_code.get(it["symbol"], 0) + 1
        if by_code:
            parts = [f"{ROCK_NAME[c]}({c}):{n}" for c, n in sorted(by_code.items())]
            _log.info("  skály: %d (%s)", len(rocks_info), ", ".join(parts))
        else:
            _log.info("  skály: 0")

    # --- mosty + lávky (ISOM 512 / 512.2): reálné ze ZABAGED REST (real-půlka, Sez. 31) ---
    # Rastr z-order: ÚPLNĚ NAVRCH (po skály) — most kreslí přes komunikaci/vodu i přes
    # skály ve výseku (visuálně dominantní liniový prvek). Lávka je drobná. Bodová lávka
    # se orientuje kolmo k nejbližšímu vodnímu toku → potřebuje water_line_features v px
    # (převést z grid → px). Bez vody (--water off) → fallback rot=0 (horizontální čárka).
    # Jen --bridges real. V lesních výsecích bez mostů/lávek = 0 prvků (žádný šum).
    bridge_features: list[tuple] = []
    footbridge_features: list[tuple] = []
    bridges_info: list[dict] = []
    bridge_mask_img: Image.Image | None = None
    if bridges == "real":
        bridge_mask_img = Image.new("L", (W, H), 0)      # GT maska mostů/lávek (§8.1, multi-class)
        bdraw_bridges = ImageDraw.Draw(bridge_mask_img)
        # vodní toky v px pro orientaci lávky (převod grid → px)
        water_lines_px = [[_grid_to_px(gx, gy) for gx, gy in grid]
                          for grid, _ in water_line_features]
        bridge_features, footbridge_features, bridges_info = _try_layer(
            "bridges",
            lambda: _generate_real_bridges(draw, bdraw_bridges, lat, lon, geo_bbox, water_lines_px),
            ([], [], []), tolerant, layer_errors)
        # souhrn po symbolech (KISS, paralela skály)
        by_code = {}
        for it in bridges_info:
            by_code[it["symbol"]] = by_code.get(it["symbol"], 0) + 1
        if by_code:
            parts = [f"{BRIDGE_NAME[c]}({c}):{n}" for c, n in sorted(by_code.items())]
            _log.info("  mosty: %d (%s)", len(bridges_info), ", ".join(parts))
        else:
            _log.info("  mosty: 0")

    # --- zápis výstupů (§8.1): finální mapa + masky + meta ---
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    img.save(out / "rgb.png")
    # ortofoto podklad (verify proti realitě, Sez. 26): reálný letecký snímek TÉHOŽ výseku
    # (ČÚZK, sdílený build_bbox → pixel-zarovnané s rgb.png i s .omap objekty). Jen reálný
    # terén (potřebuje S-JTSK georef výseku); u noise se přeskočí. Rozlišení = plátno (W×H).
    # V .omap se připne jako podkladový template (paper-space, viz omap_export.write_omap).
    ortho_template = None       # předá se write_omap → připnutí ortofota jako podklad v .omap
    if ortho and terrain == "real":
        from ortofoto import fetch_ortofoto
        # rozlišení podkladu z požadovaného m/px (menší = ostřejší, ale větší soubor i RAM
        # v OOM). Konektor stáhne po dlaždicích, pokud rozměr přesáhne strop MapServeru (4096 px).
        o_w = round(WORLD_W_M / ortho_mpp)
        o_h = round(TILE_M / ortho_mpp)
        orto_arr = _try_layer("ortho",
                              lambda: fetch_ortofoto(lat, lon, GW, GH, TILE_M, o_w, o_h),
                              None, tolerant, layer_errors)
        if orto_arr is not None:
            Image.fromarray(orto_arr).save(out / "ortofoto.png")
            # podklad pod mapou s 50% průhledností; img_w/h = skutečné rozlišení fetche
            ortho_template = {"name": "ortofoto.png", "img_w": o_w, "img_h": o_h, "opacity": 0.5}
    cmask_img.save(out / "mask_contours.png")
    fmask_img.save(out / "mask_formlines.png")                              # pomocné vrstevnice 103 (GT)
    path_mask_img.save(out / "mask_paths.png")                              # cesty (GT, multi-class)
    sym_mask_img.save(out / "mask_symbols.png")                             # bodové symboly (GT, §8.1)
    if water_mask_img is not None:
        water_mask_img.save(out / "mask_water.png")                         # voda (GT, multi-class)
    if building_mask_img is not None:
        building_mask_img.save(out / "mask_buildings.png")                  # budovy (GT)
    if powerline_mask_img is not None:
        powerline_mask_img.save(out / "mask_powerlines.png")                # el. vedení (GT)
    if railway_mask_img is not None:
        railway_mask_img.save(out / "mask_railways.png")                    # železnice (GT)
    if paved_mask_img is not None:
        paved_mask_img.save(out / "mask_paved.png")                         # zpevněné plochy (GT)
    if rock_mask_img is not None:
        rock_mask_img.save(out / "mask_rocks.png")                          # skály/balvany (GT, multi-class)
    if bridge_mask_img is not None:
        bridge_mask_img.save(out / "mask_bridges.png")                      # mosty/lávky (GT, multi-class)
    # vektorový export vrstevnic (§9): ISOM 101/102 + pomocné 103, georef (real = S-JTSK).
    # Form line je taky vrstevnice (liniový objekt) → do téhož contours.geojson.
    n_contours = _write_contours_geojson(contour_features + formline_features, geo_bbox, crs_epsg,
                                         out / "contours.geojson")
    # .omap export (§9): vrstevnice + cesty + voda + body do uživatelova čistého ISOM 2017-2
    # template (template_classic.omap, Sez. 14). Vodní toky 304/305/306 = liniové objekty;
    # plochy → 301.1 (plošný symbol, jistě přiřaditelný objektu; kombinovaný 301 s břehem
    # je rozšíření). Vše type-1 objekt (OOM rozlišuje linie/plochu podle typu symbolu).
    water_omap_features = ([(g, c) for g, c in water_line_features]
                           + [(g, "301.1") for g, _ in water_area_features])
    # budovy = plošný symbol 521 (area, type-4 v template) → uzavřený prstenec, OOM vyplní
    building_omap_features = [(g, "521") for g, _ in building_area_features]
    # el. vedení = liniový symbol 510 (type-1 v template) → otevřený path
    powerline_omap_features = [(g, "510") for g, _ in powerline_features]
    # železnice = liniový symbol 509 (kombinovaný type-16 v template) → otevřený path; OOM
    # vykreslí kombinovaný symbol (čárky + bílý knockout) autoritativně z definice symbolu (Sez. 28)
    railway_omap_features = [(g, "509") for g, _ in railway_features]
    # zpevněné plochy → 501 (KOMBINOVANÝ symbol: hnědá výplň + OBRYSOVÁ LINIE). Bounding line je
    # významová — do kolejiště se nevstupuje (rozhodnutí uživatele Sez. 28), proto NE čistě plošný
    # 501.1 (bez obrysu, jako voda). Uzavřený prstenec s close flagem (viz AREA_CODES); OOM vyplní
    # area-část kombinovaného symbolu a nakreslí obrys (jako u vody 301 combined).
    paved_omap_features = [(g, "501") for g, _ in paved_area_features]
    # pomocné vrstevnice = liniový symbol 103 (čárkovaný, type-1 v template) → otevřený path;
    # OOM vykreslí čárkování autoritativně z definice symbolu (dash 2,0 / break 0,2 mm)
    formline_omap_features = [(g, "103") for g, _ in formline_features]
    # skály/balvany (Sez. 30): body 204/207 + plochy 202/206. Plochy 206 = area_object (jako 501/521),
    # 202 = line_object (uzavřená polylinie obrysu, jako 304/305). Body = point_object (jako 109/110/111).
    rock_point_omap_features = [(gx, gy, str(c)) for gx, gy, c in rock_point_features]
    rock_area_omap_features = [(g, str(c)) for g, c in rock_area_features]
    # mosty/lávky (Sez. 31): linie 512 = line_object (otevřený path, OOM renderuje V-křídla
    # autoritativně z line_symbol). Body 512.2 = point_object s rotací (OOM renderuje kolmou
    # čárku autoritativně z point_symbol; rotace = orientace lávky). 5122 → string „512.2".
    bridge_omap_features = [(g, "512") for g, _ in bridge_features]
    footbridge_omap_features = [(gx, gy, "512.2", rot) for gx, gy, _, rot in footbridge_features]
    from omap_export import write_omap
    omap_counts = write_omap(contour_features, path_features, point_symbols,
                             water_omap_features, building_omap_features,
                             powerline_omap_features,
                             GW, GH, WORLD_W_M, TILE_M, MAP_SCALE, out / "map.omap",
                             ortho_template=ortho_template, ropik_features=ropik_features,
                             railway_features=railway_omap_features,
                             paved_features=paved_omap_features,
                             formline_features=formline_omap_features,
                             rock_point_features=rock_point_omap_features,
                             rock_area_features=rock_area_omap_features,
                             bridge_features=bridge_omap_features,
                             footbridge_features=footbridge_omap_features)
    omap_info = {"file": "map.omap", **omap_counts}
    meta = _build_meta(seed, rug, det, terrain, paths, water, paved, buildings, powerlines, railways,
                       rocks, bridges,
                       pseudorealistic, lat, lon, elev,
                       crs_epsg, n_contours, len(formline_features), n_paths, paths_info, point_symbols, water_info,
                       paved_info, building_info, powerlines_info, railways_info, rocks_info, bridges_info,
                       omap_info, layer_errors)
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    # finální souhrn (SSoT = právě spočtené počty vrstev) — ta řádka, co inspirovala log (Sez. 27)
    _log.info("hotovo → %s · budovy %d · řopíky %d · voda %d · zpevněné %d · cesty %d · vrstevnice %d "
              "(pomocné %d) · vedení %d · železnice %d · skály %d · mosty %d · body %d · .omap objektů %d", out, len(building_info),
              len(ropik_info), len(water_info), len(paved_info), n_paths, len(contour_features),
              len(formline_features), len(powerlines_info), len(railways_info),
              len(rocks_info), len(bridges_info), len(point_symbols),
              omap_counts["objects"])
    return out


def main() -> None:
    # CLI zapne INFO log → uvidí se průběh + souhrn ze synthesize (formát = holá zpráva,
    # bez timestampů; warning vrstvy se pozná ze znění). batch.py basicConfig nevolá → tichý.
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description="Syntéza pseudorealistické mapy výseku OB terénu "
                                            "(default reálná data ČÚZK; --terrain noise = procedurální Option 1).")
    p.add_argument("--location", choices=list(DEV_LOCATIONS), default=None,
                   help="vývojářská test lokalita (přepíše --lat/--lon i --width/height-km, "
                        "rozměr per-lokalita): "
                        + ", ".join(f"{k}={v[0]} {v[3]:g}x{v[4]:g}km"
                                    for k, v in DEV_LOCATIONS.items()))
    p.add_argument("--seed", type=int, default=1, help="seed PRNG (determinismus)")
    p.add_argument("--rug", type=float, default=0.5, help="členitost terénu 0-1 (jen --terrain noise)")
    p.add_argument("--det", type=float, default=0.5, help="hustota detailů 0-1 (počet proc cest)")
    p.add_argument("--terrain", choices=["noise", "real"], default="real",
                   help="real = ČÚZK DMR 5G (default, §8.5), noise = fraktální šum (Option 1)")
    p.add_argument("--paths", choices=["proc", "real"], default="real",
                   help="real = ČÚZK ZABAGED REST (default), proc = procedurální Dijkstra "
                        "(real vyžaduje --terrain real)")
    p.add_argument("--water", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED REST toky+plochy (default), off = bez vody "
                        "(real vyžaduje --terrain real; proc hydro D8 = budoucí)")
    p.add_argument("--paved", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED REST Kolejiště → ISOM 501 zpevněná plocha (default), "
                        "off = bez zpevněných ploch (real vyžaduje --terrain real; v lese bez nádraží 0 prvků)")
    p.add_argument("--buildings", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED REST plochy → ISOM 521 (default), off = bez budov "
                        "(real vyžaduje --terrain real)")
    p.add_argument("--powerlines", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED REST linie → ISOM 510 (default), off = bez vedení "
                        "(real vyžaduje --terrain real)")
    p.add_argument("--railways", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED REST tratě → ISOM 509 (default), off = bez železnic "
                        "(real vyžaduje --terrain real; v lese bez trati 0 prvků)")
    p.add_argument("--ropiky", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED Bunkr LO37 → asset řopík (default), off = bez řopíků "
                        "(real vyžaduje --terrain real; jinde než u hranic 0 prvků)")
    p.add_argument("--rocks", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED Osamělý_balvan/Skupina_balvanů/Skalní_útvary "
                        "→ ISOM 204/207/202/206 (default), off = bez skal "
                        "(real vyžaduje --terrain real; v plochém terénu 0 prvků)")
    p.add_argument("--bridges", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED Most + Lávka → ISOM 512 / 512.2 (default), "
                        "off = bez mostů (real vyžaduje --terrain real; lávka se orientuje "
                        "kolmo k nejbližšímu vodnímu toku, --water real doporučeno)")
    p.add_argument("--only-real", action="store_true",
                   help="vypne pseudorealistickou fázi 2 (dekorace nad rámec tvrdých dat); "
                        "default = fáze 2 zapnuta. Zatím: příčky vedení mimo evidované sloupy")
    p.add_argument("--no-ortho", dest="ortho", action="store_false",
                   help="nestahovat ortofoto podklad (default = ČÚZK ortofoto výseku do ortofoto.png "
                        "+ připnutí do .omap; jen s --terrain real)")
    p.add_argument("--ortho-mpp", type=float, default=0.5,
                   help="rozlišení ortofoto podkladu [m/px] (default 0,5; menší = ostřejší, ale "
                        "větší soubor i RAM v OOM; konektor dlaždicuje nad 4096 px)")
    p.add_argument("--lat", type=float, default=DEF_LAT, help="zeměpisná šířka WGS84 (jen --terrain real)")
    p.add_argument("--lon", type=float, default=DEF_LON, help="zeměpisná délka WGS84 (jen --terrain real)")
    p.add_argument("--width-km", type=float, default=DEF_WIDTH_KM,
                   help=f"šířka výseku E-W [km] (default {DEF_WIDTH_KM} = baseline; --location má per-lokalita rozměr)")
    p.add_argument("--height-km", type=float, default=DEF_HEIGHT_KM,
                   help=f"výška výseku S-J [km] (default {DEF_HEIGHT_KM} = baseline; --location má per-lokalita rozměr)")
    p.add_argument("--out", default="output", help="výstupní složka")
    args = p.parse_args()
    # vývojářská lokalita (--location) přepíše souřadnice + výsek per-lokalita (Sez. 31:
    # různé formáty landscape/portrait pro test ořezů). Jinak ruční --lat/--lon/--width-km/
    # --height-km. _apply_extent volá až sama funkce.
    if args.location:
        _, lat, lon, w_km, h_km = DEV_LOCATIONS[args.location]
    else:
        lat, lon, w_km, h_km = args.lat, args.lon, args.width_km, args.height_km
    out = synthesize_pseudorealistic_map(
        lat, lon, w_km, h_km, only_real=args.only_real, out_dir=args.out,
        seed=args.seed, rug=args.rug, det=args.det, terrain=args.terrain,
        paths=args.paths, water=args.water, paved=args.paved, buildings=args.buildings,
        powerlines=args.powerlines, railways=args.railways, ropiky=args.ropiky,
        rocks=args.rocks, bridges=args.bridges,
        ortho=args.ortho, ortho_mpp=args.ortho_mpp)
    _log.info("výstup: %s", out.resolve())


if __name__ == "__main__":
    main()
