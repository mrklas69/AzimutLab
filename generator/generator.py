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
import random  # deterministické (seedované) rozmístění trojúhelníků 208 Boulder field (Sez. 57)
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import contourpy

# Kořen LAB — generator/ je jedna úroveň pod ním. Z _REPO_ROOT odvozujeme sdílené složky
# (connectors/ data, asset/ assety, maps/ výstupy) → jeden zdroj pravdy o umístění repa (DRY).
# (Sez. 39: generátor povýšen ze sandbox/generator-poc na pilíř generator/ → cesty o úroveň výš.)
_REPO_ROOT = Path(__file__).resolve().parent.parent

# Konektory reálných dat (UC2 enabler) žijí ve sdíleném `connectors/` v kořeni LAB
# (Sez. 16) — ne v generátoru, protože nejsou specifické pro něj (zrcadlí UC2 v DAGu).
# Generátor je zatím jediný konzument; jejich složku přidáme na sys.path (fáze B, KISS —
# produkční balík/instalace až s monorepem, fáze A). Lazy importy `dmr`/`zabaged` níže pak
# fungují, ať generator.py běží přímo, nebo ho importuje batch.py.
_CONNECTORS_DIR = _REPO_ROOT / "connectors"
if str(_CONNECTORS_DIR) not in sys.path:
    sys.path.insert(0, str(_CONNECTORS_DIR))

# Generované mapy → maps/<lokalita>/ v kořeni LAB (gitignored; izomorfní s resources/ =
# reálné mapy dovnitř ↔ maps/ generované ven). Kotveno k repu, ne k cwd → výstup nezávisí
# na tom, odkud generátor spustíš. (Sez. 39.)
MAPS_DIR = _REPO_ROOT / "maps"

# Barevná paleta (§5) — jediný zdroj pravdy je palette.py (DRY). Sousední modul:
# Python má složku spouštěného skriptu na sys.path, takže `palette` je viditelný,
# ať generator.py běží přímo, nebo ho importuje batch.py. Po řezu (Sez. 11) zbyly
# tři barvy: bílá (pozadí/les), hnědá (vrstevnice + body), černá (cesty).
from palette import C_WHITE, C_BROWN, C_BLACK, C_BLUE, C_ROAD, C_PAVED, C_YELLOW, C_YELLOW_PALE, C_OLIVE, C_GREEN1, C_GREEN2, C_GREEN3, C_BOUNDARY_GREEN
from project_config import CONFIG as AZIMUTLAB_CONFIG

# Logger generátoru — synthesize loguje průběh (INFO). Knihovna NEkonfiguruje root handler
# (žádný side-effect při importu): CLI (main) zapne basicConfig(INFO) → uvidí se; batch.py
# basicConfig nevolá → INFO se nezobrazí (tichý při dávce). Úroveň DEBUG = budoucí detail.
_log = logging.getLogger("generator")

# ---------- Rozměry výseku, mřížky a plátna, měřítko (§1) ----------
# Velikost výseku je PARAMETR (lokalita + rozměry → cíl generate_map);
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
              ISOM_SEASONAL_CHANNEL: "Minor seasonal water channel",
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
# Zřícenina (Sez. 43, audit katalogu, druhý ISOM kód téže „budovové" kategorie --buildings —
# mirror skály 204/206/207): ZABAGED Rozvalina,zřícenina → ISOM 523 Ruin. Render = čárkovaný
# černý OBRYS půdorysu BEZ výplně (template id=147 line_symbol dashed 0,75/0,375 mm) — ruina je
# neúplná stavba, odliší se tak od plné budovy 521. Klasický OB orientační bod (Milštejn na SV).
ISOM_RUIN = 523                    # zřícenina → čárkovaný černý obrys (bez výplně)
BUILDING_NAME = {ISOM_BUILDING: "Building", ISOM_RUIN: "Ruin"}
# ISOM kód → třída v mask_buildings.png (0 = pozadí). Multi-class: budova 1, zřícenina 2 (Sez. 43).
BUILDING_CLASS = {ISOM_BUILDING: 1, ISOM_RUIN: 2}

# El. vedení + lanovka/vlek (Sez. 24 + 55, real-půlka, izomorfní s cestami): ZABAGED
# Elektrické_vedení + Lanová dráha/lyžařský vlek → ISOM 510 „Power line, cableway or skilift".
# Render = tenká černá linie s krátkými kolmými příčkami („fousky") v intervalu — tak ji kreslí
# OB mapa (odlišení od cesty). Mapování viz zabaged.map_powerline_to_isom (vždy 510; NAPETI/typ
# v datech prázdné → bez rozlišení 510/511). Sloučeno do jedné vrstvy (ISOM 510 = jeden symbol
# pro vedení i lanovku, KISS). Pozor: 510, NE 516 (=Fence). Černá.
ISOM_POWERLINE = 510               # vedení/lanovka/vlek → tenká linie + kolmé příčky
POWERLINE_NAME = {ISOM_POWERLINE: "Power line, cableway or skilift"}
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

# Lesní průseky (Sez. 36, real-půlka, izomorfní s cestami/vedením): ZABAGED Lesní průsek → ISOM 508
# Narrow ride = průhled lesem BEZ zřetelné vyšlapané cesty (odlišení od 503-506). Render = černá
# čárkovaná linie; dash/break z template (id 115): 3,0 / 0,375 mm → dlouhé čárky s malými mezerami
# (≈ „skoro plná", odliší od pěšiny 505 7,0/4,0 i od 506 4,0/4,0). Šířka 0,21 mm ≈ 0,96 → 1 px.
# Runnability pozadí (žlutá/zelená dle prostupnosti) se NEKRESLÍ — vegetace = UC5 predikce (gate
# Sez. 3), ne data; ISOM varianta „without background". Mapování viz zabaged.map_ride_to_isom (vždy 508).
ISOM_NARROW_RIDE = 508             # lesní průsek → černá čárkovaná (bez runnability pozadí)
RIDE_NAME = {ISOM_NARROW_RIDE: "Narrow ride"}
# ISOM kód → třída v mask_rides.png (0 = pozadí). Jediná třída (1).
RIDE_CLASS = {ISOM_NARROW_RIDE: 1}
# Render styl (mode, width [px], (dash, gap)). dash/break z template 508 (3,0 / 0,375 mm × PX_PER_MM).
RIDE_STYLE = {ISOM_NARROW_RIDE: ("dashed", 1, (3.0 * PX_PER_MM, 0.375 * PX_PER_MM))}

# Zpevněné plochy / kolejiště (Sez. 28, real-půlka, plošná — izomorfní s budovou 521 / vodní
# plochou 301): ZABAGED Kolejiště → ISOM 501 Paved area. 501 je v template KOMBINOVANÝ symbol
# (hnědá 50% výplň + obrysová linie). Raster: výplň = C_PAVED (Lower brown 50%, ISOM color 13 — odlišná
# od silnice 502 = C_ROAD Upper brown 50%; v ISOM mají identické CMYK, rastr je odliší jasem, aby silnice
# na zpevněné ploše 501.1 vynikly — Sez. 54), obrys = C_BROWN (= template bounding line Brown 100%).
# Mapování viz zabaged.map_paved_to_isom (501 kolejiště / 501.1 parkoviště + ostatní plocha v sídlech).
ISOM_PAVED = 501                   # zpevněná plocha s obrysem (kolejiště = vymezený prostor) → hnědá výplň + obrysová linie
ISOM_PAVED_NB = 501.1              # zpevněná plocha BEZ obrysu (ostatní plocha v sídlech 115 Sez. 54; parkoviště Sez. 57 = průchozí)
PAVED_NAME = {ISOM_PAVED: "Paved area", ISOM_PAVED_NB: "Paved area (no bounding line)"}
# ISOM kód → třída v mask_paved.png (0 = pozadí). 501 = třída 1, 501.1 = třída 2 (rozliš pro UC5).
PAVED_CLASS = {ISOM_PAVED: 1, ISOM_PAVED_NB: 2}
# obrys per symbol: 501 má bounding line (černá), 501.1 je BEZ obrysu (administrativní výplň, Sez. 54).
PAVED_OUTLINE = {ISOM_PAVED: C_BLACK, ISOM_PAVED_NB: None}

# Plošný pokryv / land-cover (Sez. 41-42, real-půlka, plošná — izomorfní s vodní plochou 301 /
# budovou 521 / kolejiště 501). Dvě třídy v JEDNÉ vrstvě `--surfaces` (multi-class maska):
#   401 Open land  — louka/park → plná ŽLUTÁ výplň BEZ obrysu (template 401: inner_color
#                    Yellow 100%, patterns=0). KISS: víc ZABAGED vrstev → jeden symbol (volba uživatele
#                    Sez. 41 „open land jako jedna žlutá"); ISOM-věrné 412 pole = druhá vlna (Sez. 47).
#   520 Area which shall not be entered — plná OLIVOVÁ výplň BEZ obrysu (template 520: inner_color
#                    Yellow 100%/Green 50%, patterns=0). Tři zdroje: hřbitov (ZABAGED, ISOM nemá
#                    vlastní hřbitov) ∪ privátní pozemek u domu (RÚIAN: zahrada + zastavěná plocha
#                    a nádvoří, Sez. 42) ∪ sad/zahrada (ZABAGED `Ovocný sad, zahrada` — zahrady
#                    u domů/chalup, oplocené, Sez. 49). Vše = out-of-bounds, do téže třídy.
#   402 Open land with scattered trees / 402.1 …with scattered bushes — žlutá výplň + pravidelný
#                    pattern velkých teček (Sez. 53): park/okrasná zahrada → 402 (BÍLÉ tečky =
#                    rozptýlené stromy, template color 30 „White over yellow"); ostatní udržovaná
#                    zeleň → 402.1 (ZELENÉ tečky = rozptýlené keře, template color 27 „Green 60%“
#                    ≈ C_GREEN2). Štěpení nese atribut `typ_pudy_k` (viz map_open_land_to_isom).
#                    402.1 = první „scattered bushes" zeleň z dat, gate neporušuje (tvrdý objekt
#                    nesoucí kategorii, mirror stromořadí 406, Sez. 45).
# Z-order: ÚPLNĚ VESPOD (podklad pod vrstevnicemi) — viz generate_map. Les NENÍ open land (bílá =
# default pozadí, vegetace gate). Mapování viz zabaged.map_open_land_to_isom / map_cemetery_to_isom
# + ruian.map_private_land_to_isom.
ISOM_OPEN_LAND = 401               # otevřená plocha (louka) → plná žlutá (bez obrysu)
ISOM_OUT_OF_BOUNDS = 520           # zákaz vstupu (hřbitov + privátní pozemek + sad/zahrada) → plná olivová
ISOM_CULTIVATED = 412              # pole (orná půda) → žlutá výplň + ČERNÝ tečkový pattern (Sez. 47)
ISOM_SCATTERED_TREES = 402         # park/okrasná zahrada → žlutá + BÍLÉ tečky (scattered trees, Sez. 53)
ISOM_SCATTERED_BUSHES = 402.1      # ostatní udržovaná zeleň → žlutá + ZELENÉ tečky (scattered bushes, Sez. 53)
SURFACE_NAME = {ISOM_OPEN_LAND: "Open land", ISOM_OUT_OF_BOUNDS: "Area that shall not be entered",
                ISOM_CULTIVATED: "Cultivated land",
                ISOM_SCATTERED_TREES: "Open land with scattered trees",
                ISOM_SCATTERED_BUSHES: "Open land with scattered bushes (green dots)"}
# ISOM kód → třída v mask_surfaces.png (0 = pozadí). Multi-class: open land 1, olivová 2, pole 3,
# park 402 (scattered trees) 4, ostatní zeleň 402.1 (scattered bushes) 5.
SURFACE_CLASS = {ISOM_OPEN_LAND: 1, ISOM_OUT_OF_BOUNDS: 2, ISOM_CULTIVATED: 3,
                 ISOM_SCATTERED_TREES: 4, ISOM_SCATTERED_BUSHES: 5}
# ISOM kód → výplň plochy. 401 žlutá / 520 olivová (plné, bez obrysu); 412/402/402.1 mají žluté
# pozadí (jako 401) + navíc tečkový pattern (kreslí _draw_dotted_surface_area, ne plná výplň).
SURFACE_FILL = {ISOM_OPEN_LAND: C_YELLOW, ISOM_OUT_OF_BOUNDS: C_OLIVE,
                ISOM_CULTIVATED: C_YELLOW,
                ISOM_SCATTERED_TREES: C_YELLOW, ISOM_SCATTERED_BUSHES: C_YELLOW}
# ISOM kód → tečkový pattern: (barva tečky, poloměr px, rozestup px). Grid kotvený globálně (lícuje
# napříč plochami). Template: 412 černé tečky r 0,15 mm / grid 1,2 mm (color 31 „open land black");
# 402/402.1 velké tečky r 0,3 mm / grid 1,05 mm (větší a hustší než 412) — 402 bílé (color 30),
# 402.1 zelené (color 27 „Green 60%" ≈ C_GREEN2). Render = aproximace (malé px), .omap nese věrný symbol.
SURFACE_DOT = {
    ISOM_CULTIVATED:       (C_BLACK,  max(1, round(0.15 * PX_PER_MM)), 1.20 * PX_PER_MM),
    ISOM_SCATTERED_TREES:  (C_WHITE,  max(1, round(0.30 * PX_PER_MM)), 1.05 * PX_PER_MM),
    ISOM_SCATTERED_BUSHES: (C_GREEN2, max(1, round(0.30 * PX_PER_MM)), 1.05 * PX_PER_MM),
}
# ISOM min. mapovatelná plocha s patternem (template MINIMUM DIMENSIONS): 412 = 3×3 mm; 402/402.1
# = 2×2 mm s min_area 9 mm² (sjednoceno na 9 mm², izomorf s 412 — volba uživatele Sez. 47/53).
# Menší plocha → spadne na 401 (open land, izomorf se stromořadím Sez. 45). V px²: mm² × PX_PER_MM².
SURFACE_MIN_AREA_PX2 = {ISOM_CULTIVATED: round(9.0 * PX_PER_MM ** 2),
                        ISOM_SCATTERED_TREES: round(9.0 * PX_PER_MM ** 2),
                        ISOM_SCATTERED_BUSHES: round(9.0 * PX_PER_MM ** 2)}


# ---------- Mokřady (Sez. 44, katalog dávka 4, real-půlka, plošná) ----------
# `Bažina, močál` + `Rašeliniště (plocha)` → ISOM 308 Marsh (crossable). Template 308 = area_symbol
# s patternem: MODRÉ vodorovné čáry (color Blue 100%, line_spacing 0,45 mm, line_width 0,15 mm).
# Rastr to napodobí scanline šrafou (vodorovné modré čáry ořezané na polygon); .omap věrný ze symbolu.
# Projekce (ZABAGED→ISOM) = vždy 308 Marsh (NE 307 uncrossable — data nenesou překonatelnost; viz
# zabaged.map_marsh_to_isom). Z-order: nad plošným pokryvem (401/520), pod liniemi/body.
# PSEUDO FÁZE 2 (Sez. 99): ZABAGED nerozlišuje zřetelnou (308) vs nezřetelnou (310 Indistinct) bažinu —
# „indistinct" je kartografická interpretace okraje, ne katastrální fakt (measure-first: atribut
# rašeliniště/bažina geograficky binární, velikost nediskriminuje). Reálné mapy mají 308 i 310
# PROMÍCHANÉ v rámci mapy (medián ~59 % na 310) → ~MARSH_INDISTINCT_PCT % mokřadů reklasifikujeme na
# 310 deterministickou pseudonáhodou z polohy (jen pseudorealistic; --only-real = vše 308 = čistá projekce).
ISOM_MARSH = 308
ISOM_MARSH_INDISTINCT = 310                           # pseudo fáze 2: nezřetelná bažina (Sez. 99)
MARSH_NAME = {ISOM_MARSH: "Marsh", ISOM_MARSH_INDISTINCT: "Indistinct marsh"}
MARSH_CLASS = {ISOM_MARSH: 1, ISOM_MARSH_INDISTINCT: 2}   # mask_marsh.png (0 = pozadí, 1 = 308, 2 = 310)
MARSH_HATCH_SPACING_PX = max(2, round(0.45 * PX_PER_MM))  # 308: plné vodorovné čáry (template 0,45 mm)
# 310 Indistinct (template pattern type=2: line_spacing 0,90 mm = 2× řidší + tečkový point_distance
# 1,725 mm) → rastr napodobí 2× řidší PŘERUŠOVANOU šrafou (staggered ob řádek), vizuálně odliší od 308.
MARSH_INDISTINCT_SPACING_PX = max(3, round(0.90 * PX_PER_MM))   # rozestup řádků (template 0,90 mm)
MARSH_INDISTINCT_DASH_PX = max(2, round(0.60 * PX_PER_MM))      # délka dashe (~0,60 mm)
MARSH_INDISTINCT_GAP_PX = max(2, round(1.15 * PX_PER_MM))       # mezera mezi dashi (~point_distance)
MARSH_INDISTINCT_PCT = 55                             # pseudo: ~55 % mokřadů → 310 (medián reálných map ~59 %)


# ---------- Skály a balvany (Sez. 30 + 57, real-půlka §8.5) ----------
# 4 ISOM symboly ze 4 ZABAGED vrstev — KISS, vrstva = jeden symbol (jako budovy→521 / vedení→510):
#   204 Boulder           — bod (Osamělý_balvan)
#   207 Boulder cluster   — bod (Skupina_balvanů__bod_)
#   206 Gigantic boulder  — plocha (Skalní_útvary, plná černá plocha)
#   208 Boulder field     — linie → pás (Skupina_balvanů__linie_, náhodné trojúhelníky; Sez. 57)
# Hybridní 202/206 podle plochy (zvažováno Sez. 30, Q2) ZAVRŽENO uživatelem v průběhu sezení:
# „rozhodování bez datového podkladu" — ZABAGED nemá atribut typu/výšky, práh by byl hádaný.
# Drift po stěně argumentů („proč jsou některé plné a jiné jen obrys?") → návrat ke KISS:
# Skalní_útvary jsou VŽDY 206 (plná plocha), nezávisle na velikosti.
# Smoothing polygonů (původní A2 záměr) také ZAVRŽEN: ZABAGED polygony jsou už dostatečně
# detailní (Shape_Length 680 m / Shape_Area 5289 m² = ~120 vrcholů). RAW je default.
ISOM_BOULDER = 204                 # 204 Boulder — bodový balvan, plný černý kruh
ISOM_GIGANTIC_BOULDER = 206        # 206 Gigantic boulder — skalní útvar v půdorysu, černá výplň
ISOM_BOULDER_CLUSTER = 207         # 207 Boulder cluster — bodová skupina balvanů, černý trojúhelník
ISOM_BOULDER_FIELD = 208           # 208 Boulder field — plocha s náhodnými trojúhelníky (Sez. 57)
ISOM_STONY_GROUND = 210            # 210 Stony ground — pole jednotlivých teček (210.1, pseudo injekce Sez. 107)
ROCK_NAME = {ISOM_BOULDER: "Boulder", ISOM_GIGANTIC_BOULDER: "Gigantic boulder",
             ISOM_BOULDER_CLUSTER: "Boulder cluster", ISOM_BOULDER_FIELD: "Boulder field",
             ISOM_STONY_GROUND: "Stony ground"}
# ISOM kód → třída v mask_rocks.png (0 = pozadí). 5 tříd (jedna maska pro celou kategorii).
ROCK_CLASS = {ISOM_BOULDER: 1, ISOM_BOULDER_CLUSTER: 2, ISOM_GIGANTIC_BOULDER: 3,
              ISOM_BOULDER_FIELD: 4, ISOM_STONY_GROUND: 5}

# Render parametry (template_classic.omap autoritativní, rastr ladíme pro viditelnost — princip
# Sez. 28/29 „render px-tuned vs .omap věrný"). Vše v µm × PX_PER_MM/1000:
#   204 inner_radius=200 → 0,2 mm poloměr (= 0,4 mm průměr) → 0,917 px → 1 px viditelně mizí,
#                          ladíme na 2 px (= 0,44 mm), OOM stejně renderuje 0,4 mm věrně.
#   207 počet bodů 3 v template (-400 231; 400 231; 0 -462), base 0,8 mm, výška 0,693 mm →
#                          base 4 px, výška 3 px (vrchol DOLŮ, jako template orientace).
BOULDER_RADIUS_PX = max(2, round(0.4 * PX_PER_MM))           # 204 — kruh
BOULDER_CLUSTER_HALF_BASE_PX = max(2, round(0.4 * PX_PER_MM))  # 207 — polovina base trojúhelníku
BOULDER_CLUSTER_HEIGHT_PX = max(2, round(0.7 * PX_PER_MM))     # 207 — výška trojúhelníku (vrchol dolů)

# 208 Boulder field (Sez. 57): zdroj LINIE → buffer na úzký pás (½ šířky = 0,75 mm → pás 1,5 mm,
# volba uživatele) → vyplnit NÁHODNÝMI trojúhelníky. .omap je area_symbol 208 (OOM vyplní pattern
# autoritativně z definice id 38) → rastr jen px-tuned aproximace (princip render-px vs .omap, Sez. 28/29).
# ISOM 208: density 0,8-1 trojúhelník/mm² (→ rozestup ~1 mm), footprint trojúhelníku 12×6 m = 1,2×0,6 mm.
BOULDER_FIELD_HALF_WIDTH_PX = 0.75 * PX_PER_MM               # ½ šířky pásu (0,75 mm → pás 1,5 mm)
BOULDER_FIELD_MIN_AREA_PX2 = round(1.0 * PX_PER_MM ** 2)     # zahodit pásy pod ISOM min. plochou (1,0 mm²)
BOULDER_FIELD_TRI_SPACING_PX = 1.0 * PX_PER_MM               # rozestup trojúhelníků (~1/mm², ISOM 0,8-1)
BOULDER_FIELD_TRI_HALF_PX = max(2, round(0.3 * PX_PER_MM))   # polovina base trojúhelníku (~0,6 mm base)

# --- Pseudo injekce bodů 204/210 (Sez. 107, FÁZE 2 pseudorealistic) ---
# ZABAGED body 204/210 skoro nevede (kompas Sez. 96/107: 204 gen 3/orig 1064, 210 gen 0/orig 975) →
# bodové sub-KPI jen 18,4 %. Kartograf je v terénu kreslí HUSTĚ podle skalnatosti, geodata to neumí.
# Pseudo injekce je dosype ve statistické míře. NENÍ to projekce dat (poloha není pravdivá, reframe
# Sez. 79), ale uživatel zvolil VĚRNOU DISTRIBUCI (Sez. 107) → kontext = DOLOŽENÁ skalnatost:
#   maska = 206 skalní plochy (DMR sklon, rock_relief) + reálné ZABAGED 204/207 body, dilatováno o okolí.
# DŮVOD (nález Sez. 107): obecný sklon ≠ skalnatost — svažitá-ale-neskalnatá mapa (Bedřichovka, Jizerky)
# dostala 50 % hmoty v bodech (orig jen 3,8 %), masivní přestřel + ředění headline. Doložená skalnatost
# koreluje s reálnou hustotou bodů per mapa (Velbloud skalnatý → velká maska, Bedř ne → malá).
# Izomorf k pseudo vrstvám 310 marsh / 516 plot: gated `pseudorealistic`, BEZ vlastního flagu (visí na
# rocks="real" → point_base=off i only_real=off ji korektně vypnou).
PSEUDO_ROCK_DILATE_M = 150.0       # dilatace doložené skalnatosti o okolí [m] (suť/balvany kolem stěn;
                                   # 206/ZABAGED body jsou řídké → větší dilatace dá souvislý skalnatý region)
# Hustota na km² MASKY (KALIBRACE Sez. 107 na SHARE, ne absolutní Σ): gen celkově podstřeluje
# (Σgen ≈ ⅓ Σorig), takže „správný absolutní počet" bodů by dal nadměrný share → ředění. Cíl =
# gen_share(204+210) ≈ orig_share (~15 % průměr). Maska (doložená skalnatost) určuje KDE + hrubě korelaci,
# hustota globální. Věrná per-mapa distribuce z dat NEJDE (skalnatost není v geodatech, data-gate Sez. 107).
PSEUDO_BOULDER_PER_KM2 = 500.0     # hustota 204 boulderů na km² masky (KALIBRACE Sez. 107)
PSEUDO_STONY_FIELD_PER_KM2 = 12.0  # hustota 210 polí teček na km² masky (KALIBRACE)
PSEUDO_STONY_DOT_SPACING_PX = 1.2 * PX_PER_MM                 # rozestup teček 210 (spec point_distance 1200 µm)
PSEUDO_STONY_DOT_RADIUS_PX = max(1, round(0.15 * PX_PER_MM))  # 210.1 tečka (inner_radius 150 µm)


# ---------- Bodové orientační prvky (Sez. 43, real-půlka, audit katalogu) ----------
# 4 ISOM symboly z bodových ZABAGED vrstev — KISS vrstva → jeden symbol (jako skály). Mapování
# zabaged.map_landmark_to_isom. Geometrie z template_classic.omap (id 149/151/155/102):
#   524 High tower  — černý kříž „+" (2 čáry ±1,05 mm) + střední tečka (template inner 0,6 mm)
#   526 Cairn       — černý kroužek (r 0,36 mm, width 0,24 mm) + tečka uprostřed (trig point)
#   530 Prom. ring  — černý kroužek (r 0,36 mm, width 0,24 mm) BEZ tečky (man-made ring)
#   417 Large tree  — ZELENÝ kroužek (r 0,405 mm, width 0,27 mm) — bodový orient. prvek, mimo veg. gate
ISOM_HIGH_TOWER = 524
ISOM_CAIRN = 526
ISOM_PROM_RING = 530
ISOM_LARGE_TREE = 417
# 419 Prom. vegetation feature — ZELENÝ X (Sez. 136). NEMÁ ZABAGED zdroj (na rozdíl od 417 stromu) →
# jen pseudo injekce (_generate_pseudo_veg_points); sdílí render+.omap+meta cestu landmarků (proto zde).
ISOM_VEG_FEATURE = 419
# 418 Prom. bush or tree — ZELENÝ plný bod (Sez. 137). Stejně jako 419 NEMÁ ZABAGED zdroj (keře/buše
# se nemapují) → čistě pseudo injekce. Template id=103: inner_radius=75 µm (bílý střed, color 22) +
# outer_width=300 µm (zelený, color 3) → vizuálně plný zelený disk ⌀ ~0,375 mm; bílý střed (~0,56 px)
# v gen renderu vynechán (KISS, jako 419 nemá svatozář — kreslí ji až realita/degradér).
ISOM_PROM_BUSH = 418
# Sez. 44 (katalog dávka 4): pramen / nádrž / jeskyně. Geometrie z template (id 72/71/31):
#   312 Spring  — MODRÉ „U"/oblouk, ústí NAHORU (template: oblouk r≈0,54 mm, width 0,27 mm, color Blue)
#   311 Well    — MODRÝ čtverec (obrys, ½ strany 0,465 mm, width 0,27 mm) — well/fountain/water tank
#   203.2 Cave  — černá „Λ" (chevron / otočené V = stříška, hrot NAHORU) — NE plný trojúhelník!
#                 (oprava Sez. 44 dle uživatele; KONVENCE: omap +y = DOLŮ, ověřeno temp/sym_correct.png:
#                 203.1=V hrot dolů „without entrance", 203.2=Λ stříška hrot nahoru „with entrance").
#                 Geometrie template (id 31): hrot omap y=-735 → NAHOŘE, základna omap y=+465 → dole.
#                 Rastr = 2 chevron tahy (px-tuned); .omap = filled 203.2 (autoritativní, OOM věrná Λ).
# 203.2 je NECELÝ ISOM kód → klíč je string "203.2" (dict snese smíšené klíče; .omap přes str(code)).
ISOM_SPRING = 312
ISOM_WELL = 311
ISOM_CAVE = "203.2"
LANDMARK_NAME = {ISOM_HIGH_TOWER: "High tower", ISOM_CAIRN: "Cairn",
                 ISOM_PROM_RING: "Prominent man-made feature", ISOM_LARGE_TREE: "Prominent large tree",
                 ISOM_SPRING: "Spring", ISOM_WELL: "Well, fountain or water tank",
                 ISOM_CAVE: "Cave or rocky pit",
                 ISOM_VEG_FEATURE: "Prominent vegetation feature",
                 ISOM_PROM_BUSH: "Prominent bush or tree"}
# ISOM kód → třída v mask_landmarks.png (0 = pozadí). Multi-class (jedna maska pro kategorii).
LANDMARK_CLASS = {ISOM_HIGH_TOWER: 1, ISOM_CAIRN: 2, ISOM_PROM_RING: 3, ISOM_LARGE_TREE: 4,
                  ISOM_SPRING: 5, ISOM_WELL: 6, ISOM_CAVE: 7, ISOM_VEG_FEATURE: 8,
                  ISOM_PROM_BUSH: 9}
# Render parametry (px-tuned pro viditelnost; .omap věrný ze symbolu). µm × PX_PER_MM/1000:
LANDMARK_RING_R_PX = max(3, round(0.36 * PX_PER_MM))    # kroužek 530/526 (r ≈ 0,36 mm → ~2 px → min 3)
LANDMARK_TREE_R_PX = max(3, round(0.40 * PX_PER_MM))    # kroužek 417 (r ≈ 0,40 mm)
LANDMARK_DOT_R_PX = max(1, round(0.12 * PX_PER_MM))     # střední tečka 524/526 (~0,12 mm)
LANDMARK_TOWER_ARM_PX = max(4, round(1.05 * PX_PER_MM)) # rameno kříže 524 (±1,05 mm ≈ 4,8 px)
LANDMARK_SPRING_R_PX = max(3, round(0.54 * PX_PER_MM))  # oblouk pramene 312 (r ≈ 0,54 mm)
LANDMARK_WELL_HALF_PX = max(2, round(0.465 * PX_PER_MM))  # ½ strany čtverce 311 (0,465 mm)
LANDMARK_CAVE_APEX_PX = max(3, round(0.735 * PX_PER_MM))  # hrot „Λ" 203.2 NAD středem (0,735 mm)
LANDMARK_CAVE_TOP_PX = max(2, round(0.465 * PX_PER_MM))   # dolní konce „Λ" POD středem (0,465 mm)
LANDMARK_CAVE_HALF_PX = max(2, round(0.525 * PX_PER_MM))  # ½ rozevření „Λ" (0,525 mm)
LANDMARK_VEGFEAT_R_PX = max(3, round(0.60 * PX_PER_MM))   # polodélka ramene X 419 (≈0,60 mm, izomorf inject)
LANDMARK_BUSH_R_PX = max(2, round(0.375 * PX_PER_MM))    # vnější poloměr plného disku 418 (inner 75 + outer 300 µm)

# --- Pseudo injekce vegetačních bodů 417/419 (Sez. 136, FÁZE 2 pseudorealistic) ---
# Princip kamenů (Sez. 107): doložené ZABAGED stromy 417 jsou ŘÍDKÉ (~3 % reálné hustoty) → dosypeme
# je na reálnou hustotu; 419 nemá ZABAGED zdroj vůbec → čistě pseudo. Hustota MĚŘENA z kartografových
# .omap (eval_real GT/plocha, Sez. 136): medián 417 ~27/km², 419 ~18/km² (rozptyl 4–46 dle terénu).
# Umístění (volba uživatele): náhodně MIMO vodu + MIMO doloženou skalnatost (strom neroste v balvanitém
# poli; voda = no-draw zóna). Hustota LOSOVANÁ per mapa z rozsahu → rozmanitější tréninková sada.
PSEUDO_TREE_PER_KM2 = (15.0, 40.0)      # 417 Prominent large tree — cílová hustota (doplnit reálné ZABAGED na ni)
PSEUDO_VEGFEAT_PER_KM2 = (10.0, 28.0)   # 419 Prominent vegetation feature — čistě pseudo
# 418 Prominent bush or tree — čistě pseudo (Sez. 137). Hustota MĚŘENA z kartografových .omap stejně
# jako 417/419 (crosswalk-aware, eval_real GT/plocha): medián ~17,8/km², rozsah 6,6–25,3/km².
PSEUDO_BUSH_PER_KM2 = (8.0, 26.0)       # uniform průměr ~17 = reálný medián; rozsah pokrývá řídké i bohaté mapy
# ISOM: bodové symboly se NESMÍ překrývat (Sez. 136, nález uživatele {A} Nová Louka — dva symboly přes
# sebe). Minimální vzdálenost STŘEDŮ dvou pseudo veg bodů = součet jejich poloměrů + mezera (žádný dotyk).
PSEUDO_VEG_MIN_GAP_MM = 0.20            # mezera mezi okraji symbolů (rezerva nad „nedotýkat se")


# ---------- Crossing point (Sez. 52, real-půlka, bodová ORIENTOVANÁ vrstva) ----------
# ISOM 519 Crossing point = průchod plotem/zdí (branka, schůdky). ZABAGED `Zábrana` ležící na
# nosné zdi 513 → 519 (filtr + tangenta dělá zabaged.fetch_barriers; závory na cestách se zahodí).
# Symbol = 2 rovnoběžné čárky (template id 134: x=±450 µm, délka 1500 µm, width 270 µm) tvořící
# „bránu"; rotatable → osa symbolu = směr plotu (plot prochází mezerou mezi čárkami). KISS vrstva
# → jeden symbol, single-class maska. Orientace = jediná taková vedle řopíků/lávek (Sez. 52).
ISOM_CROSSING_POINT = 519
BARRIER_NAME = {ISOM_CROSSING_POINT: "Crossing point"}
BARRIER_CLASS = {ISOM_CROSSING_POINT: 1}                  # single-class maska (jen 519)
BARRIER_HALF_GAP_PX = max(2, round(0.45 * PX_PER_MM))    # ½ rozteče čárek PODÉL zdi (template x=±450 µm)
BARRIER_HALF_LEN_PX = max(3, round(0.75 * PX_PER_MM))    # ½ délky čárky KOLMO na zeď (template 1500/2 µm)
# Přerušení nosné zdi 513 pod brankou (ISOM 519: „line shall be broken at the crossing point" —
# nepřekonatelný plot se v průchodu přeruší, Sez. 52). Mezera = šířka symbolu „brány".
BARRIER_BREAK_HALF_MM = 0.6                              # ½ mezery v plotě pod brankou (mezera 1,2 mm)
BARRIER_BREAK_NEAR_M = 6.0                               # práh „brána leží na této zdi" (mírně > fetch 5 m)


# ---------- Liniové orientační prvky (Sez. 43, real-půlka, audit katalogu) ----------
# 3 ISOM symboly z liniových ZABAGED vrstev — KISS vrstva → jeden symbol (map_line_feature_to_isom):
#   104 Earth bank — terénní sráz: plná HNĚDÁ linie + krátké JEDNOSTRANNÉ kolmé čárky (ticks).
#       Orientace ticků (na nižší stranu svahu) by chtěla DMR sklon → zatím konzistentní pravá
#       normála (vizuálně = earth bank; přesná orientace = TODO, potřebuje výškopis).
#   513 Wall — zeď/hradba: plná černá linie (template id 128 line_width 240 µm).
#   107 Erosion gully — erozní rokle/výmol: plná HNĚDÁ linie (template width 375 µm, bez ticků;
#       `Rokle, výmol` id 94, Sez. 58). Bez atributu velikosti → KISS 107 (NE drobné 108). POZN.:
#       implementováno NASLEPO — 0 výskytů na 5 DEV lokalitách (erozní rýhy = měkké půdy, ne lesy
#       Liberecka); vizuál neověřen na reálném výseku, jen geometrie linie→linie + spec (volba uživatele).
# (Stromořadí už NENÍ zde — `Liniová vegetace` jde plošně jako 406 lineární les, viz TREE_ROW_* níže;
#  416 = hranice porostů bylo sémanticky špatně pro řadu stromů, Sez. 45.)
ISOM_EARTH_BANK = 104
ISOM_WALL = 513
ISOM_EROSION_GULLY = 107
LINEFEAT_NAME = {ISOM_EARTH_BANK: "Earth bank", ISOM_WALL: "Wall", ISOM_EROSION_GULLY: "Erosion gully"}
# ISOM kód → třída v mask_linefeatures.png (0 = pozadí). Multi-class (jedna maska pro kategorii).
LINEFEAT_CLASS = {ISOM_EARTH_BANK: 1, ISOM_WALL: 2, ISOM_EROSION_GULLY: 3}
LINEFEAT_COLOR = {ISOM_EARTH_BANK: C_BROWN, ISOM_WALL: C_BLACK, ISOM_EROSION_GULLY: C_BROWN}  # 104/107 sráz/rokle = HNĚDÁ (template color 6 Brown), NE černá (oprava audit Sez. 44)
# Render styl (mode, width px, dash). 513/104 obě plná (104 + ticks zvlášť); 107 plná hnědá tlustší.
LINEFEAT_STYLE = {
    ISOM_EARTH_BANK: ("solid", 1, None),
    ISOM_WALL: ("solid", 1, None),
    ISOM_EROSION_GULLY: ("solid", 2, None),   # 107 = plná hnědá ~2 px (template 375 µm), bez ticků
}
EARTHBANK_TICK_SPACING_PX = max(3, round(0.8 * PX_PER_MM))   # rozestup ticků sráz 104 (~0,8 mm)
EARTHBANK_TICK_LEN_PX = max(2, round(0.35 * PX_PER_MM))      # délka ticku (jednostranná, ~0,35 mm)

# ---------- Plot 516 Fence (Sez. 98, FÁZE 2 pseudorealistic) ----------
# OB kartograf kreslí oplocenou zástavbu jako jeden souvislý olivový blok 520 + plot po obvodu.
# ZABAGED plot NEVEDE (doloženo Sez. 57) → linii dokreslujeme VĚROHODNĚ kolem RÚIAN ZAHRAD (druh 5,
# Sez. 113: ne druh 13 zastavěná plocha; volba uživatele Sez. 98). Pseudo dekorace = fáze 2 (vypne ji --only-real), izomorf
# s příčkami vedení. Liniový symbol 516 Fence (template id 131, type 2). Render 1px černá jako 513
# (na rozlišení rastru je 1px minimum; .omap dostane věrný symbol 516 z definice). Vlastní GT maska
# zatím NE — linie nejsou v plošném Png2Area Y a Png2Line neexistuje (generalizuj jen s důkazem).
ISOM_FENCE = 516
FENCE_NAME = "Fence"
FENCE_WIDTH_PX = 1
# Plot jen kolem SOUVISLÉ zástavby ≥ 0,5 ha (measure-first Sez. 98): bez prahu plot přestřeloval
# 6,7× (kompas gen 160 / orig 24) — kreslil se kolem každého domku se zahradou (medián bloku ~190 m²).
# Práh 5000 m² → Bedřichovka 159→21 ≈ orig 24. Kartograf plotuje jen větší souvislé oplocené areály.
FENCE_MIN_AREA_M2 = 5000
# Obvod z contourpy masky je pixelově členitý → RDP narovná na přímé spojnice vrcholů (Sez. 98).
FENCE_SIMPLIFY_M = 5.0
# ISOM 516 „tags inside" (spec template): krátké ticky kolmo DOVNITŘ ohraničeného pozemku.
FENCE_TICK_SPACING_PX = max(4, round(3.0 * PX_PER_MM))   # rozestup ticků (~3 mm, ISOM 516 segment)
FENCE_TICK_LEN_PX = max(2, round(0.5 * PX_PER_MM))        # délka ticku dovnitř (~0,5 mm)


# ---------- Stromořadí jako „lineární les" (Sez. 45, real-půlka, liniová data → plošná reprezentace) ----------
# `Liniová vegetace` (id 15) = stromořadí. ISOM 416 (hranice porostů) je sémanticky špatně pro řadu
# stromů (verify spec Sez. 45) → kreslíme PLOŠNĚ: osa linie → buffer na úzký NEPRAVIDELNÝ pás
# („špageta") → 406 Vegetation: slow running (světlá zelená C_GREEN1, plná výplň bez obrysu, jako
# 401/520). První zelená vegetační plocha generátoru — legitimní (tvrdý objekt z dat, ne hádaná
# hustota → vegetace gate neporušuje; izomorf s 308 Marsh: KISS jedna úroveň, data hustotu nenesou).
# Šířka 0,7 mm ≈ 7 m (typická alej). Min. plocha 1,0 mm² (ISOM spec: nejmenší zelený dot-screen je
# 1,0 mm²) → menší úseky zahodit. Perturbace DETERMINISTICKÁ (sinus podél osy, ne random — real
# nelosuje, Sez. 20). Mapování viz zabaged.map_tree_row_to_isom.
ISOM_TREE_ROW = 406
TREEROW_NAME = {ISOM_TREE_ROW: "Vegetation: slow running"}
TREEROW_CLASS = {ISOM_TREE_ROW: 1}                       # mask_treerows.png (0 = pozadí, 1 = stromořadí)
TREEROW_HALF_WIDTH_PX = 0.35 * PX_PER_MM                 # ½ šířky pásu (0,7 mm → 0,35 mm na stranu)
TREEROW_MIN_AREA_PX2 = round(1.0 * PX_PER_MM ** 2)       # ISOM min. plocha zeleného screenu 1,0 mm²
TREEROW_WAVE_AMP = 0.35                                  # amplituda „špageta" perturbace (× half-width)
TREEROW_WAVE_LAMBDA_PX = 3.0 * PX_PER_MM                 # vlnová délka perturbace podél osy (~3 mm)


# ---------- Predikční vegetační/open kódy (ISOM 406/408/410 + 403) ----------
# Zeleň dle hustoty: 406 = C_GREEN1 (světlá, pomalý běh), 408 = C_GREEN2 (chůze), 410 = C_GREEN3
# (tmavá, fight). Plná výplň BEZ obrysu (vegetační plošný symbol, jako 406 stromořadí / 401 / 520).
ISOM_VEG_SLOW = 406                 # řidší porost → světle zelená
ISOM_VEG_WALK = 408                 # zapojený porost → středně zelená
ISOM_VEG_FIGHT = 410               # nejhustší → tmavě zelená


# ---------- Predikční plochy ze SEPARACE reálné mapy (Sez. 83/92) ----------
# Obecný registr plošných predikčních symbolů, které kreslí _draw_predict_areas (geometrie zvenčí,
# ze separace Livelox mapy přes pairs.py). Zeleň 406/408/410 + 403 Rough open (Sez. 92) = bledá žlutá
# (C_YELLOW_PALE), separovaná rozštěpem žluté uvnitř open (sytá 401 je real část, neseparuje se).
# Plošnou predikční zeleň nese neutrální `veg_area_*` proměnná / `mask_veg_area.png` /
# `real_sections["veg_area"]` (rename Sez. 93). Jediný zdroj predikční vegetace = SEPARACE.
# (Archiv Sez. 102: forest_age proxy AOPK věk→zeleň smazán jako doložená slepá ulička — 33 % pokrytí
#  korpusu, IoU 0,12, přestřel 3,3× /Sez. 82, 91/; pseudorealistic vegetace = budoucí směr, TODO.)
ISOM_ROUGH_OPEN = 403
PREDICT_AREA_FILL = {ISOM_VEG_SLOW: C_GREEN1, ISOM_VEG_WALK: C_GREEN2, ISOM_VEG_FIGHT: C_GREEN3,
                     ISOM_ROUGH_OPEN: C_YELLOW_PALE}
# ISOM kód → třída v mask_veg_area.png (0 = pozadí). Multi-class: fight 1 (nejhustší) → slow 3 → 403 4.
PREDICT_AREA_CLASS = {ISOM_VEG_FIGHT: 1, ISOM_VEG_WALK: 2, ISOM_VEG_SLOW: 3, ISOM_ROUGH_OPEN: 4}
PREDICT_AREA_NAME = {ISOM_VEG_SLOW: "Vegetation: slow running", ISOM_VEG_WALK: "Vegetation: walk",
                     ISOM_VEG_FIGHT: "Vegetation: fight", ISOM_ROUGH_OPEN: "Rough open land"}

# --- 416 Distinct vegetation boundary (Sez. 101): mezitřídní hranice predikčních veg ploch ---
# Měření Sez. 101: 416 = NEJVĚTŠÍ proporční díra KPI (orig 633 / gen 0). Reálné mapy kreslí ZŘETELNÉ
# hranice mezi oblastmi různé runnability (403↔406↔408↔410) tečkovanou linií. Data (separace) nemají
# info o „zřetelnosti" → bereme MEZITŘÍDNÍ hranice (kde se stýkají různé veg třídy) + DÉLKOVÝ práh
# (krátké šumové fragmenty separace odpadnou; reálné 416 medián 45-90 m). Měřením laděno na práh 50 m
# → KPI 46,1 → ~50 % (+3,8 pb; prototyp temp/proto_416). Stejný typ problému jako marsh 310 (data
# nediskriminují), ale heuristika MEZITŘÍDNÍ je doménově věrná (ISOM 416 = hranice různé runnability).
# Varianta symbolu je globální projektové nastavení v azimutlab.toml. OOM šablona nese obě
# definice; na jedné mapě se smí použít právě jedna. 416.1 nesmí ohraničovat 410 Fight.
ISOM_VEG_BOUNDARY = AZIMUTLAB_CONFIG.symbols.vegetation_boundary
BOUNDARY_NAME = {
    "416": "Distinct vegetation boundary, black dotted line",
    "416.1": "Distinct vegetation boundary, green dashed line",
}
BOUNDARY_CLASS = {"416": 1, "416.1": 1}     # mask_boundaries.png třída (jediná)
BOUNDARY_COLOR = {"416": C_BLACK, "416.1": C_BOUNDARY_GREEN}
BOUNDARY_STYLE = {
    "416": ("dashed", 1, (0.2 * PX_PER_MM, 0.45 * PX_PER_MM)),
    "416.1": ("dashed", max(1, round(0.14 * PX_PER_MM)),
              (0.30 * PX_PER_MM, 0.20 * PX_PER_MM)),
}
BOUNDARY_MIN_LEN_M = 50      # délkový práh úseku [m terénu] (měření Sez. 101: optimum KPI ~50 %)
BOUNDARY_SAMPLE_M = 3.0      # poloměr okolí pro detekci sousední veg třídy [m terénu]


# ---------- Mosty / tunely / lávky (ISOM 512 + 512.2, Sez. 32 spec-driven) ----------
# Verify Sez. 32: foto reálné OB mapy (uživatel) + ISOM 2017-2 PDF str. 32. Most a tunel
# sdílí ISOM 512 a MAJÍ SHODNÝ LAYOUT (závorky JEN na koncích linie), liší se viditelností
# trati mezi závorkami:
#   - Most  = osa PLNÁ (silnice/železnice nahoře viditelná po celé délce mostu) + závorky na koncích
#   - Tunel = osa VYNECHANÁ (trať pod zemí, mezi závorkami terén skrz) + závorky na koncích
# Závorka 512 = **2 šikmé čárky pod 60° vůči ose, symetricky NAD i POD osou** (= úplný pár,
# ne polovina jako v Sez. 31 template). Délka šikmé čárky 0,4 mm, vzdálenost paty od osy
# = 0,25 mm (= 0,5 mm rozestup spec / 2). Tloušťka čárky = 0,18 mm (= line_width 512 template).
# Lávka = single dash (template 512.2 id=127): kolmá čárka 1,25 mm × 0,25 mm, rotace k vodě.
ISOM_BRIDGE = 512                          # most (osa plná, závorky na koncích); tunel sdílí 512
                                           #   (osa vynechaná) — týž ISOM kód, viz map_tunnel_to_isom
ISOM_FOOTBRIDGE = 5122                     # lávka (= ISOM 512.2, single dash kolmo k vodě)
BRIDGE_NAME = {ISOM_BRIDGE: "Bridge", ISOM_FOOTBRIDGE: "Footbridge"}   # Tunnel = totéž jako Bridge
# Maska tříd v mask_bridges.png (multi-class): 1 = most, 2 = tunel, 3 = lávka. 0 = pozadí.
# Most a tunel mají STEJNÝ ISOM kód 512 ale ROZLIŠENÉ MASKOVÉ TŘÍDY → UC5 detektor je může
# rozlišit z kontextu (viditelná osa vs vynechaná osa).
BRIDGE_CLASS_BRIDGE = 1
BRIDGE_CLASS_TUNNEL = 2
BRIDGE_CLASS_FOOTBRIDGE = 3

# Geometrie symbolu 512 — verify-against-source template_classic.omap id=125 + Most.png demo
# (Sez. 33/35). Rastr (px-tuned) REPLIKUJE, co OOM vykreslí ze 2 objektů 512 v .omap
# (omap_export._bridge_parallels): most = 2 paralely lemující osu (±0,75 mm) + na koncích nožička
# 512. Nožička = template start/end_symbol „(-450,-654)→0,0" / „0,0→(450,-654)" µm: složka podél
# osy VEN (450 µm) + kolmá VEN od centerline (654 µm) → 4 nožičky tvoří [ ] kolem úseku křížení.
# Délky v paper µm; rastr = µm × PX_PER_MM/1000. (Dřív Sez. 32: šikmé čárky 60° z osy — kresba
# se rozcházela s .omap, sjednoceno Sez. 35.)
BRIDGE_LINE_WIDTH_UM = 270               # tloušťka baseline + nožiček (template 512 line_width=270, 0,27 mm)
BRIDGE_PARALLEL_OFFSET_UM = 750          # offset paralely od osy mostu (= omap_export.BRIDGE_PARALLEL_OFFSET_UM, ±0,75 mm)
BRIDGE_LEG_ALONG_UM = 450                # nožička: složka podél osy ven (template start/end_symbol)
BRIDGE_LEG_PERP_UM = 654                 # nožička: složka kolmo ven od osy (template 654 µm)
TUNNEL_PORTAL_HALF_UM = 750              # tunel: půl-délka kolmé závorky vjezdu (= omap_export.TUNNEL_PORTAL_HALF_UM, 1,5 mm)
BRIDGE_LINE_WIDTH_PX = max(2, round(BRIDGE_LINE_WIDTH_UM * PX_PER_MM / 1000))
BRIDGE_PARALLEL_OFFSET_PX = max(1, round(BRIDGE_PARALLEL_OFFSET_UM * PX_PER_MM / 1000))
BRIDGE_LEG_ALONG_PX = max(1, round(BRIDGE_LEG_ALONG_UM * PX_PER_MM / 1000))
BRIDGE_LEG_PERP_PX = max(2, round(BRIDGE_LEG_PERP_UM * PX_PER_MM / 1000))
TUNNEL_PORTAL_HALF_PX = max(2, round(TUNNEL_PORTAL_HALF_UM * PX_PER_MM / 1000))

# Lávka 512.2: kolmá čárka přes vodu/cestu (template id=127, coords 0,-937→0,938 = ±937 µm,
# line_width 375). Rastr na template-věrné hodnoty (Sez. 35; dřív 625/250 µm = drift od template).
FOOTBRIDGE_HALF_LEN_UM = 937             # polovina délky čárky (template ±937 µm)
FOOTBRIDGE_WIDTH_UM = 375                # tloušťka čárky (template 0,375 mm)
FOOTBRIDGE_HALF_LEN_PX = max(3, round(FOOTBRIDGE_HALF_LEN_UM * PX_PER_MM / 1000))
FOOTBRIDGE_WIDTH_PX = max(2, round(FOOTBRIDGE_WIDTH_UM * PX_PER_MM / 1000))


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
# Název (index 0) = zároveň název výstupní složky (`--location` ⇒ out_dir, viz main).
# Musí sedět s `stats.py` LOCATIONS (SSoT názvů složek pro STATISTICS.md).
DEV_LOCATIONS: dict[str, tuple[str, float, float, float, float]] = {
    "SV": ("Soví vrch",   DEF_LAT,    DEF_LON,    6.0, 4.0),  # Lužické hory (default, terénně mapováno) — landscape
    "NL": ("Nová Louka",  50.8140386, 15.1579069, 6.0, 4.0),  # Jizerské hory — landscape
    "LS": ("Lidové sady", 50.7773244, 15.0811114, 6.0, 4.0),  # Liberec městsko-lesní pod Ještědem — landscape
    "HS": ("Hrubá Skála", 50.5481000, 15.1761500, 5.0, 5.0),  # Hruboskalsko (midpoint Kacanovy↔Doubravice) — SQUARE (Sez. 31)
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


def _poly_to_grid_px(poly: list[list[tuple[float, float]]], geo_bbox: tuple) -> tuple[list, list]:
    """ZABAGED polygon [vnější, díra1, …] (S-JTSK) → (grid_rings, px_rings) (Sez. 54).

    Mirror starého per-ring transformu (S-JTSK → grid → px), jen přes VŠECHNY prsteny polygonu.
    `grid_rings` jdou do .omap (mřížkové souřadnice), `px_rings` do rastru. Sjednocuje 6 plošných
    call-sitů (voda/budovy/paved/surfaces/marsh/skály) — DRY."""
    grid_rings = [[_sjtsk_to_grid(x, y, geo_bbox) for x, y in ring] for ring in poly]
    px_rings = [[_grid_to_px(gx, gy) for gx, gy in g] for g in grid_rings]
    return grid_rings, px_rings


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


def _draw_ride(draw: ImageDraw.ImageDraw, ridraw: ImageDraw.ImageDraw,
               curve_px: list[tuple[float, float]], code: int) -> None:
    """Lesní průsek (černá čárkovaná, ISOM 508) dle RIDE_STYLE — wrapper nad _draw_line_symbol
    (izomorfní s _draw_path / _draw_railway). Bez runnability pozadí (vegetace = UC5)."""
    mode, width, dash = RIDE_STYLE[code]
    _draw_line_symbol(draw, ridraw, curve_px, C_BLACK, mode, width, dash, RIDE_CLASS[code])


def _draw_boundary(draw: ImageDraw.ImageDraw, bdraw: ImageDraw.ImageDraw,
                   curve_px: list[tuple[float, float]], code: str) -> None:
    """Hranice vegetace 416/416.1 dle globální konfigurace a BOUNDARY_STYLE.

    Wrapper nad _draw_line_symbol
    (izomorfní s _draw_ride). Mezitřídní hranice predikčních veg ploch (Sez. 101)."""
    mode, width, dash = BOUNDARY_STYLE[code]
    _draw_line_symbol(
        draw, bdraw, curve_px, BOUNDARY_COLOR[code], mode, width, dash, BOUNDARY_CLASS[code]
    )


def _offset_polyline_px(pts: list[tuple[float, float]], offset: float) -> list[tuple[float, float]]:
    """Posun polyline o `offset` px po LEVÉ normále lokální tangenty (per-bod); záporný offset =
    pravá normála. Rastrový protějšek omap_export._offset_polyline_left (tam µm) — jiná jednotka
    i modul, proto vlastní kopie (cross-module sdílení by znamenalo kruhový import generator↔omap)."""
    n = len(pts)
    if n < 2:
        return list(pts)
    out: list[tuple[float, float]] = []
    for i in range(n):
        cx, cy = pts[i]
        if i == 0:
            dx, dy = pts[1][0] - cx, pts[1][1] - cy
        elif i == n - 1:
            dx, dy = cx - pts[-2][0], cy - pts[-2][1]
        else:
            dx = (pts[i + 1][0] - pts[i - 1][0]) / 2.0
            dy = (pts[i + 1][1] - pts[i - 1][1]) / 2.0
        tlen = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / tlen, dx / tlen          # levá normála k lokální tangentě
        out.append((cx + offset * nx, cy + offset * ny))
    return out


def _draw_bridge_leg(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                     parallel: list[tuple[float, float]], at_start: bool, side: int) -> None:
    """Nožička 512 na jednom konci paralely (template start/end_symbol). Vede z koncového bodu
    podél osy VEN z mostu (BRIDGE_LEG_ALONG_PX) a kolmo VEN od centerline (BRIDGE_LEG_PERP_PX na
    stranu `side`). 4 nožičky obou paralel tvoří [ ] kolem úseku křížení (Most.png demo)."""
    if at_start:
        (ex, ey), (nx, ny) = parallel[0], parallel[1]
    else:
        (ex, ey), (nx, ny) = parallel[-1], parallel[-2]
    tdx, tdy = nx - ex, ny - ey                 # tangenta DOVNITŘ mostu (ke druhému bodu)
    tlen = math.hypot(tdx, tdy) or 1.0
    ux, uy = tdx / tlen, tdy / tlen
    lnx, lny = -uy, ux                          # levá normála tangenty dovnitř
    # tip: podél osy ven (= -tangenta dovnitř) + kolmo ven od osy (strana `side`)
    tip_x = ex - ux * BRIDGE_LEG_ALONG_PX + side * lnx * BRIDGE_LEG_PERP_PX
    tip_y = ey - uy * BRIDGE_LEG_ALONG_PX + side * lny * BRIDGE_LEG_PERP_PX
    draw.line([(ex, ey), (tip_x, tip_y)], fill=C_BLACK, width=BRIDGE_LINE_WIDTH_PX)
    mdraw.line([(ex, ey), (tip_x, tip_y)], fill=BRIDGE_CLASS_BRIDGE, width=BRIDGE_LINE_WIDTH_PX)


def _draw_bridge(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                 curve_px: list[tuple[float, float]]) -> None:
    """Most (ISOM 512): 2 paralely lemující osu (±0,75 mm) + nožičky 512 ven na koncích = [ ].

    Replikuje, co OOM vykreslí ze 2 objektů 512 v .omap (omap_export._bridge_parallels): baseline
    každé paralely + na obou koncích nožička podél osy ven a kolmo ven od centerline. Nesená trať
    (silnice/železnice) prochází středem viditelně; závorky vymezují úsek mostu. Verify Most.png
    demo (Sez. 33/35). Dřív (Sez. 32) rastr kreslil šikmé čárky 60° z osy → nesedělo s .omap."""
    if len(curve_px) < 2:
        return
    for side in (+1, -1):                       # paralela na každé straně osy mostu
        parallel = _offset_polyline_px(curve_px, side * BRIDGE_PARALLEL_OFFSET_PX)
        draw.line(parallel, fill=C_BLACK, width=BRIDGE_LINE_WIDTH_PX)
        mdraw.line(parallel, fill=BRIDGE_CLASS_BRIDGE, width=BRIDGE_LINE_WIDTH_PX)
        _draw_bridge_leg(draw, mdraw, parallel, at_start=True, side=side)
        _draw_bridge_leg(draw, mdraw, parallel, at_start=False, side=side)


def _draw_tunnel(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                 curve_px: list[tuple[float, float]]) -> None:
    """Tunel (ISOM 512): kolmé závorky na vjezdech (osa otočená 90°), trať mezi nimi přerušená.

    Replikuje omap_export._tunnel_portals: na obou koncích osy krátká KOLMÁ čára ±0,75 mm
    (= vjezd/výjezd tunelu), trať uvnitř je už ořezaná (_crop_line_at_passages). Verify Sez. 33
    (ortofoto). Sjednoceno s .omap konstantou TUNNEL_PORTAL_HALF (dřív si půjčoval FOOTBRIDGE_*)."""
    if len(curve_px) < 2:
        return
    for end_idx, neighbor_idx in ((0, 1), (-1, -2)):
        ex, ey = curve_px[end_idx]
        nx, ny = curve_px[neighbor_idx]
        tdx, tdy = nx - ex, ny - ey
        tlen = math.hypot(tdx, tdy) or 1.0
        nx_perp, ny_perp = -tdy / tlen, tdx / tlen      # kolmice k ose tunelu
        p1 = (ex - TUNNEL_PORTAL_HALF_PX * nx_perp, ey - TUNNEL_PORTAL_HALF_PX * ny_perp)
        p2 = (ex + TUNNEL_PORTAL_HALF_PX * nx_perp, ey + TUNNEL_PORTAL_HALF_PX * ny_perp)
        draw.line([p1, p2], fill=C_BLACK, width=BRIDGE_LINE_WIDTH_PX)
        mdraw.line([p1, p2], fill=BRIDGE_CLASS_TUNNEL, width=BRIDGE_LINE_WIDTH_PX)


def _draw_footbridge(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                     cx: float, cy: float, rot_rad: float) -> None:
    """Lávka bodová (ISOM 512.2): kolmá čárka v poloze (cx, cy), rotovaná o rot_rad.

    Template id=127: point_symbol rotatable=true, polyline (0,-937) → (0,938) µm =
    vertikální čárka 1,87 mm tlustá 0,375 mm (template-věrné hodnoty, Sez. 35; dřív 625/250
    µm = drift). `rot_rad` = úhel orientace osy lávky vůči
    +x rastru; nastavuje se kolmo k nejbližšímu vodnímu toku (řeší volající)."""
    cos_r = math.cos(rot_rad)
    sin_r = math.sin(rot_rad)
    p1 = (cx - FOOTBRIDGE_HALF_LEN_PX * cos_r, cy - FOOTBRIDGE_HALF_LEN_PX * sin_r)
    p2 = (cx + FOOTBRIDGE_HALF_LEN_PX * cos_r, cy + FOOTBRIDGE_HALF_LEN_PX * sin_r)
    draw.line([p1, p2], fill=C_BLACK, width=FOOTBRIDGE_WIDTH_PX)
    mdraw.line([p1, p2], fill=BRIDGE_CLASS_FOOTBRIDGE, width=FOOTBRIDGE_WIDTH_PX)


def _fill_rings_scanline(d: ImageDraw.ImageDraw,
                         rings_px: list[list[tuple[float, float]]], fill) -> None:
    """Vyplní víceprstencový polygon [vnější, díra1, …] na `d` přes even-odd scanline (Sez. 54).

    PIL `polygon` výřezy neumí. Hrany VŠECH prstenů (vnější + díry) se na každém řádku sčítají do
    jednoho seznamu průsečíků: mezi vnějškem a dírou lichý počet (kreslí se), uvnitř díry sudý
    (vynechá se) → díra zůstane prázdná. Hrany se počítají PER PRSTEN (uzavření `%n` v rámci
    prstenu, ne přes jeho hranici). Sdílí princip se scanline v _draw_marsh_area/_draw_dotted_."""
    ys = [p[1] for ring in rings_px for p in ring]
    y0, y1 = int(math.floor(min(ys))), int(math.ceil(max(ys)))
    for y in range(y0, y1 + 1):
        xs: list[float] = []
        for ring in rings_px:
            n = len(ring)
            for i in range(n):
                ax, ay = ring[i]
                bx, by = ring[(i + 1) % n]
                if (ay <= y < by) or (by <= y < ay):        # hrana kříží řádek (half-open)
                    t = (y - ay) / (by - ay)
                    xs.append(ax + t * (bx - ax))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):                  # vyplň mezi sudými páry (uvnitř, ne v díře)
            d.line([(xs[j], y), (xs[j + 1], y)], fill=fill, width=1)


def _draw_area_symbol(draw: ImageDraw.ImageDraw, adraw: ImageDraw.ImageDraw,
                      rings_px: list[list[tuple[float, float]]],
                      fill: tuple, outline: tuple, mask_class: int) -> None:
    """Plošný ISOM symbol: barevná výplň + obrysová linie na mapu + třída do GT masky.

    Sjednocuje plochy stejně, jako _draw_line_symbol sjednotil linie (Sez. 17): vodní
    plocha (modrá) i budova (černá) jsou týž tvar lišící se jen barvou. `rings_px` = prsteny
    [vnější, díra1, …] (Sez. 54). Bez děr (drtivá většina ploch) jde RYCHLÁ cesta: PIL C polygon
    (beze změny chování). S děrami (velké administrativní plochy) even-odd scanline vyřízne výřezy.
    Maska dostane PLNOU výplň třídou (plošná GT, ne jen obrys)."""
    outer = rings_px[0]
    if len(outer) < 3:
        return
    holes = [h for h in rings_px[1:] if len(h) >= 3]
    if not holes:                                       # rychlá cesta: žádné díry → PIL polygon (C)
        draw.polygon(outer, fill=fill, outline=outline)
        adraw.polygon(outer, fill=mask_class)
        return
    rings = [outer, *holes]
    if fill is not None:
        _fill_rings_scanline(draw, rings, fill)
    _fill_rings_scanline(adraw, rings, mask_class)
    if outline is not None:                             # obrys: každý prsten zvlášť (vnější i díry = hranice)
        for ring in rings:
            draw.line(list(ring) + [ring[0]], fill=outline)


def _draw_water_area(draw: ImageDraw.ImageDraw, wdraw: ImageDraw.ImageDraw,
                     rings_px: list[list[tuple[float, float]]], code: int) -> None:
    """Vodní plocha (ISOM 301): modrá výplň + černý břeh — wrapper nad _draw_area_symbol."""
    _draw_area_symbol(draw, wdraw, rings_px, C_BLUE, C_BLACK, WATER_CLASS[code])


def _draw_building_area(draw: ImageDraw.ImageDraw, bdraw: ImageDraw.ImageDraw,
                        rings_px: list[list[tuple[float, float]]], code: int) -> None:
    """Budovová stavba: 521 budova = plná černá výplň + obrys; 523 zřícenina = jen černý OBRYS
    bez výplně (ruina je neúplná stavba — odliší se od plné budovy; Sez. 43). Rastr kreslí plný
    obrys (zříceniny jsou malé, čárkování by zaniklo); .omap dostane věrný 523 dashed ze symbolu
    (princip „rastr px-tuned vs .omap věrný", Sez. 28/29). Wrapper nad _draw_area_symbol."""
    fill = C_BLACK if code == ISOM_BUILDING else None
    _draw_area_symbol(draw, bdraw, rings_px, fill, C_BLACK, BUILDING_CLASS[code])


def _draw_paved_area(draw: ImageDraw.ImageDraw, adraw: ImageDraw.ImageDraw,
                     rings_px: list[list[tuple[float, float]]], code: float) -> None:
    """Zpevněná plocha (ISOM 501 kolejiště / 501.1 parkoviště + ostatní plocha v sídlech): hnědá výplň +
    obrys dle symbolu — wrapper nad _draw_area_symbol (izomorfní s _draw_building_area / _draw_water_area).
    501 má ČERNÝ obrys (template „Paved area, with bounding line" = thin BLACK line; verify Sez. 50);
    501.1 je BEZ obrysu (PAVED_OUTLINE, Sez. 54/57 — průchozí/administrativní výplň, ne ohraničená plocha)."""
    _draw_area_symbol(draw, adraw, rings_px, C_PAVED, PAVED_OUTLINE[code], PAVED_CLASS[code])


def _draw_surface_area(draw: ImageDraw.ImageDraw, sdraw: ImageDraw.ImageDraw,
                       rings_px: list[list[tuple[float, float]]], code: int) -> None:
    """Plošný pokryv (ISOM 401 open land žlutá / 520 zákaz vstupu olivová): plná výplň BEZ obrysu
    — wrapper nad _draw_area_symbol (izomorfní s _draw_paved_area, jen outline=None: open land ani
    out-of-bounds nemají bounding line; barva dle SURFACE_FILL, třída dle SURFACE_CLASS)."""
    _draw_area_symbol(draw, sdraw, rings_px, SURFACE_FILL[code], None, SURFACE_CLASS[code])


def _draw_dotted_surface_area(draw: ImageDraw.ImageDraw, sdraw: ImageDraw.ImageDraw,
                              rings_px: list[list[tuple[float, float]]], code: int) -> None:
    """Plocha s tečkovým patternem (ISOM 412 pole / 402 park / 402.1 ostatní zeleň): ŽLUTÁ výplň +
    tečkový pattern ořezaný na polygon + plná třída do GT masky (Sez. 47/53). Barva/poloměr/rozestup
    teček řídí SURFACE_DOT[code]: 412 černé (r 0,15 mm, grid 1,2 mm); 402 bílé / 402.1 zelené (r 0,3 mm,
    grid 1,05 mm). .omap dostane věrný symbol (412 = 401 + 412.1 combined; 402/402.1 = samostatný
    combined area symbol z template).

    `rings_px` = [vnější, díra1, …] (Sez. 54). Tečky leží na PRAVIDELNÉ mřížce kotvené GLOBÁLNĚ
    (násobky rozestupu od počátku rastru) → pattern lícuje napříč sousedními plochami (ISOM „orientated
    to north"). Scanline (even-odd přes hrany VŠECH prstenů) teč jen uvnitř a vynechá díry."""
    outer = rings_px[0]
    if len(outer) < 3:
        return
    rings = [outer, *(h for h in rings_px[1:] if len(h) >= 3)]
    if len(rings) > 1:                                   # s děrami: pozadí/maska přes scanline (PIL výřezy neumí)
        _fill_rings_scanline(draw, rings, SURFACE_FILL[code])
        _fill_rings_scanline(sdraw, rings, SURFACE_CLASS[code])
    else:                                               # bez děr: rychlá PIL cesta (beze změny chování)
        draw.polygon(outer, fill=SURFACE_FILL[code])    # žluté pozadí (jako 401)
        sdraw.polygon(outer, fill=SURFACE_CLASS[code])  # GT maska: plná plocha
    dot_color, dot_r, sp = SURFACE_DOT[code]              # barva, poloměr, rozestup teček (per-symbol)
    ys = [p[1] for ring in rings for p in ring]
    y0, y1 = min(ys), max(ys)
    y = math.ceil(y0 / sp) * sp                          # první řádek mřížky uvnitř bboxu (globální kotva)
    while y <= y1:
        xs: list[float] = []
        for ring in rings:                              # průsečíky scanline s hranami (per prsten → díry vynechány)
            n = len(ring)
            for i in range(n):
                ax, ay = ring[i]
                bx, by = ring[(i + 1) % n]
                if (ay <= y < by) or (by <= y < ay):    # hrana kříží řádek (half-open interval)
                    t = (y - ay) / (by - ay)
                    xs.append(ax + t * (bx - ax))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):              # uvnitř polygonu = mezi sudými páry průsečíků
            x = math.ceil(xs[j] / sp) * sp              # první tečka mřížky v intervalu (globální kotva)
            while x <= xs[j + 1]:
                draw.ellipse([x - dot_r, y - dot_r, x + dot_r, y + dot_r], fill=dot_color)
                x += sp
        y += sp                                         # další řádek mřížky (Sez. 49 fix: chyběl → nekonečná smyčka)


def _draw_dashed_hline(draw: ImageDraw.ImageDraw, xa: float, xb: float, y: int, row: int) -> None:
    """Přerušovaná vodorovná modrá čára pro 310 Indistinct marsh (template tečkový pattern type=2).
    Dashe periody DASH+GAP, staggered o půl periody ob řádek (template offset_along_line)."""
    period = MARSH_INDISTINCT_DASH_PX + MARSH_INDISTINCT_GAP_PX
    x = xa + (period // 2 if row % 2 else 0)            # liché řádky posunuté → staggered tečky
    while x < xb:
        draw.line([(x, y), (min(x + MARSH_INDISTINCT_DASH_PX, xb), y)], fill=C_BLUE, width=1)
        x += period


def _draw_marsh_area(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                     rings_px: list[list[tuple[float, float]]], code: int) -> None:
    """Mokřad (308 Marsh / 310 Indistinct): MODRÁ vodorovná šrafa ořezaná na polygon + plná třída do masky.

    308 = plné čáry (rozestup MARSH_HATCH_SPACING_PX, template 0,45 mm); 310 = 2× řidší PŘERUŠOVANÁ
    šrafa (pseudo fáze 2, Sez. 99). .omap dostane věrný area symbol dle `code`. `rings_px` = [vnější,
    díra1, …] (Sez. 54). Scanline: pro každou vodorovnou linii najdi průsečíky s hranami VŠECH prstenů
    (even-odd), seřaď x a vyplň modře mezi sudými páry (díry vynechány). GT maska = PLNÁ výplň třídou."""
    outer = rings_px[0]
    if len(outer) < 3:
        return
    rings = [outer, *(h for h in rings_px[1:] if len(h) >= 3)]
    cls = MARSH_CLASS[code]
    if len(rings) > 1:                                  # s děrami: maska přes scanline (PIL výřezy neumí)
        _fill_rings_scanline(mdraw, rings, cls)
    else:
        mdraw.polygon(outer, fill=cls)                  # bez děr: rychlá PIL cesta (plná plocha)
    indistinct = (code == ISOM_MARSH_INDISTINCT)
    spacing = MARSH_INDISTINCT_SPACING_PX if indistinct else MARSH_HATCH_SPACING_PX
    ys = [p[1] for ring in rings for p in ring]
    y0, y1 = int(math.floor(min(ys))), int(math.ceil(max(ys)))
    for row, y in enumerate(range(y0, y1 + 1, spacing)):
        xs: list[float] = []
        for ring in rings:                              # průsečíky scanline s hranami (per prsten → díry vynechány)
            n = len(ring)
            for i in range(n):
                ax, ay = ring[i]
                bx, by = ring[(i + 1) % n]
                if (ay <= y < by) or (by <= y < ay):    # hrana kříží scanline (half-open interval)
                    t = (y - ay) / (by - ay)            # lineární interpolace x v průsečíku
                    xs.append(ax + t * (bx - ax))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):              # vyplň mezi sudými páry (uvnitř polygonu)
            if indistinct:
                _draw_dashed_hline(draw, xs[j], xs[j + 1], y, row)   # 310: přerušovaně, staggered
            else:
                draw.line([(xs[j], y), (xs[j + 1], y)], fill=C_BLUE, width=1)   # 308: plná čára


def _polygon_area_px(ring: list[tuple[float, float]]) -> float:
    """Plocha uzavřeného polygonu [px²] přes shoelace (Gaussův vzorec). Absolutní hodnota
    (nezávislá na orientaci vrcholů). Pro filtr min. mapovatelné plochy stromořadí (Sez. 45)."""
    n = len(ring)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        s += x0 * y1 - x1 * y0            # shoelace: Σ (x_i·y_{i+1} − x_{i+1}·y_i)
    return abs(s) / 2.0


def _point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    """Leží bod (x, y) uvnitř uzavřeného polygonu `ring`? Ray-casting (even-odd): od bodu
    vystřelíme polopřímku doprava a počítáme průsečíky s hranami — lichý počet = uvnitř.
    Pro rozmístění trojúhelníků 208 do buffrovaného pásu (Sez. 57)."""
    n = len(ring)
    inside = False
    j = n - 1                              # index předchozího vrcholu (hrana j→i)
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        # hrana protíná vodorovnou polopřímku v úrovni y, a průsečík je vpravo od x?
        if (yi > y) != (yj > y):
            x_cross = xj + (xi - xj) * (y - yj) / (yi - yj)
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _buffer_polyline_irregular(axis_px: list[tuple[float, float]],
                               half_w: float) -> list[tuple[float, float]]:
    """Osa (polyline) → uzavřený NEPRAVIDELNÝ pás („špageta", Sez. 45) jako prstenec px.

    Pro každý bod osy spočítáme kolmou normálu (z centrální tangenty) a odsadíme o half_w na
    obě strany → levý a pravý okraj pásu; prstenec = levý okraj tam + pravý okraj zpět. Šířka se
    DETERMINISTICKY vlní sinem podél délky osy (proč ne random: real nelosuje, Sez. 20) → okraj
    není strojově rovný buffer. Levá/pravá strana mají posunutou fázi (asymetrie = živější tvar)."""
    n = len(axis_px)
    if n < 2:
        return []
    left: list[tuple[float, float]] = []
    right: list[tuple[float, float]] = []
    s_acc = 0.0                           # kumulativní délka podél osy [px] (pro fázi vlny)
    for i in range(n):
        cx, cy = axis_px[i]
        # tangenta = centrální diference (kraje jednostranně) → směr osy v bodě i
        if i == 0:
            dx, dy = axis_px[1][0] - cx, axis_px[1][1] - cy
        elif i == n - 1:
            dx, dy = cx - axis_px[-2][0], cy - axis_px[-2][1]
            s_acc += math.hypot(cx - axis_px[i - 1][0], cy - axis_px[i - 1][1])
        else:
            dx = axis_px[i + 1][0] - axis_px[i - 1][0]
            dy = axis_px[i + 1][1] - axis_px[i - 1][1]
            s_acc += math.hypot(cx - axis_px[i - 1][0], cy - axis_px[i - 1][1])
        tlen = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / tlen, dx / tlen    # levá normála k tangentě
        phase = 2.0 * math.pi * s_acc / TREEROW_WAVE_LAMBDA_PX
        wl = half_w * (1.0 + TREEROW_WAVE_AMP * math.sin(phase))            # levá šířka
        wr = half_w * (1.0 + TREEROW_WAVE_AMP * math.sin(phase + 1.7))      # pravá (posun fáze)
        left.append((cx + nx * wl, cy + ny * wl))
        right.append((cx - nx * wr, cy - ny * wr))
    return left + right[::-1]             # prstenec: levý okraj tam, pravý zpět


def _draw_treerow_area(draw: ImageDraw.ImageDraw, tdraw: ImageDraw.ImageDraw,
                       ring_px: list[tuple[float, float]]) -> None:
    """Stromořadí / lineární les (ISOM 406): plná SVĚTLE ZELENÁ výplň BEZ obrysu + GT maska
    (izomorfní s _draw_surface_area; 406 je plošný vegetační symbol, hranici nemá). Buffrovaný
    pás je JEDEN prsten bez děr → předáno _draw_area_symbol jako [ring_px] (tvar list-ringů, Sez. 54)."""
    _draw_area_symbol(draw, tdraw, [ring_px], C_GREEN1, None, TREEROW_CLASS[ISOM_TREE_ROW])


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


def _draw_stony_dot(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                    cx: float, cy: float) -> None:
    """Jedna tečka pole 210 Stony ground (ISOM 210.1 individual dot): malý černý kruh + GT maska.

    Template id=43 (point, inner_radius=150 µm). Rastr clamp min 1 px ať tečka nezmizí; .omap nese
    věrný 0,15 mm symbol (OOM renderuje autoritativně, princip render-px vs .omap, Sez. 28/29)."""
    r = PSEUDO_STONY_DOT_RADIUS_PX
    bbox = (cx - r, cy - r, cx + r, cy + r)
    draw.ellipse(bbox, fill=C_BLACK)
    mdraw.ellipse(bbox, fill=ROCK_CLASS[ISOM_STONY_GROUND])


def _draw_boulder_cluster(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                          cx: float, cy: float) -> None:
    """Bodová skupina balvanů (ISOM 207): plný černý trojúhelník vrcholem nahoru + GT maska.

    Template_classic.omap id 36: 3 body (-400,231),(400,231),(0,-462) µm, base 0,8 mm, výška
    0,693 mm. V OOM paper-space (i v rastru) y roste DOLŮ → vrchol (y=-462) je NAHOŘE, base
    (y=+231) DOLE. Držíme tuto orientaci. Poměr výšky 231:462 = 1:2 → těžiště ≈ ve středu (cx,cy)."""
    hb = BOULDER_CLUSTER_HALF_BASE_PX            # polovina base
    h = BOULDER_CLUSTER_HEIGHT_PX                # výška (vrchol → base)
    # rovnoramenný trojúhelník: vrchol NAHOŘE (cy - 2h/3), base DOLE (cy + h/3) — třetina výšky
    # nad střed, dvě třetiny pod → těžiště ≈ střed (cx, cy). Sedí s template poměrem 231:462.
    apex = (cx, cy - 2 * h / 3)
    base_l = (cx - hb, cy + h / 3)
    base_r = (cx + hb, cy + h / 3)
    pts = [apex, base_l, base_r]
    draw.polygon(pts, fill=C_BLACK)
    mdraw.polygon(pts, fill=ROCK_CLASS[ISOM_BOULDER_CLUSTER])


def _draw_gigantic_boulder(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                           rings_px: list[list[tuple[float, float]]]) -> None:
    """Masivní skalní formace (ISOM 206 Gigantic boulder): plná černá plocha + GT maska.

    Template_classic.omap (id 35): `area_symbol inner_color="2" min_area="0" patterns="0"`
    = jen plná černá výplň (žádný pattern, žádný obrys jiné barvy). Mirror _draw_building_area,
    jen třída masky jiná (ROCK_CLASS[206])."""
    _draw_area_symbol(draw, mdraw, rings_px, C_BLACK, C_BLACK, ROCK_CLASS[ISOM_GIGANTIC_BOULDER])


def _draw_boulder_field_area(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                             ring_px: list[tuple[float, float]]) -> None:
    """Pole balvanů (ISOM 208 Boulder field): pás vyplněný NÁHODNÝMI plnými trojúhelníky + GT maska.

    GT maska = CELÝ pás (třída ROCK_CLASS[208]) — symbol je „kde leží pole 208", ne kde je každý
    trojúhelník. Rastr = px-tuned aproximace patternu (`.omap` nese area_symbol 208, OOM vyplní
    trojúhelníky věrně z definice id 38 — princip render-px vs .omap, Sez. 28/29).

    Rozmístění deterministické (regen → identický výstup): seed z rohu bbox pásu → `random.Random`.
    Pravidelná mřížka (rozestup ~1 mm = ISOM density 0,8-1/mm²) + jitter v buňce rozbije pravidelnost
    („randomly placed and orientated"); každý trojúhelník náhodně otočený. Jen body uvnitř pásu."""
    mdraw.polygon(ring_px, fill=ROCK_CLASS[ISOM_BOULDER_FIELD])     # maska = celý pás
    xs = [p[0] for p in ring_px]
    ys = [p[1] for p in ring_px]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sp = BOULDER_FIELD_TRI_SPACING_PX
    h = BOULDER_FIELD_TRI_HALF_PX
    # seed z rohu bbox (zaokrouhlený px) → různé pásy mají různý vzor, ale tentýž pás vždy stejný
    rng = random.Random((round(x0) * 73856093) ^ (round(y0) * 19349663))
    gx = x0
    while gx <= x1:
        gy = y0
        while gy <= y1:
            jx = gx + rng.uniform(-0.35, 0.35) * sp     # jitter → nepravidelnost
            jy = gy + rng.uniform(-0.35, 0.35) * sp
            if _point_in_ring(jx, jy, ring_px):
                ang = rng.uniform(0.0, 2.0 * math.pi)   # náhodná orientace trojúhelníku
                pts = [(jx + h * math.cos(ang + k * 2.0 * math.pi / 3),
                        jy + h * math.sin(ang + k * 2.0 * math.pi / 3)) for k in range(3)]
                draw.polygon(pts, fill=C_BLACK)
            gy += sp
        gx += sp


def _draw_landmark(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                   cx: float, cy: float, code: int | str) -> None:
    """Bodový orientační prvek (Sez. 43/44) na mapu (`draw`) + GT maska (`mdraw`, LANDMARK_CLASS).

    Render dle ISOM symbolu (px-tuned; .omap věrný ze symbolu):
      524 High tower → černý kříž „+" + střední tečka
      526 Cairn      → černý kroužek + tečka uprostřed
      530 ring       → černý kroužek (bez tečky)
      417 Large tree → ZELENÝ kroužek (C_GREEN3)
      418 Bush/tree  → ZELENÝ plný disk (C_GREEN3) — odlišný od 417 prstence i 419 X (Sez. 137)
      312 Spring     → MODRÝ oblouk „U", ústí NAHORU (Sez. 44)
      311 Well       → MODRÝ čtverec (obrys, Sez. 44)
      203.2 Cave     → černá „Λ" stříška (chevron, hrot NAHORU; NE plný trojúhelník — oprava Sez. 44)
    """
    cls = LANDMARK_CLASS[code]
    if code == ISOM_HIGH_TOWER:                         # kříž „+" + tečka
        a = LANDMARK_TOWER_ARM_PX
        draw.line([(cx - a, cy), (cx + a, cy)], fill=C_BLACK, width=1)
        draw.line([(cx, cy - a), (cx, cy + a)], fill=C_BLACK, width=1)
        mdraw.line([(cx - a, cy), (cx + a, cy)], fill=cls, width=1)
        mdraw.line([(cx, cy - a), (cx, cy + a)], fill=cls, width=1)
        d = LANDMARK_DOT_R_PX
        draw.ellipse([cx - d, cy - d, cx + d, cy + d], fill=C_BLACK)
        mdraw.ellipse([cx - d, cy - d, cx + d, cy + d], fill=cls)
    elif code in (ISOM_CAIRN, ISOM_PROM_RING):          # kroužek (+ tečka u cairn)
        r = LANDMARK_RING_R_PX
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=C_BLACK, width=1)
        mdraw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=cls, width=1)
        if code == ISOM_CAIRN:
            d = LANDMARK_DOT_R_PX
            draw.ellipse([cx - d, cy - d, cx + d, cy + d], fill=C_BLACK)
            mdraw.ellipse([cx - d, cy - d, cx + d, cy + d], fill=cls)
    elif code == ISOM_LARGE_TREE:                       # 417 Large tree — zelený kroužek
        r = LANDMARK_TREE_R_PX
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=C_GREEN3, width=1)
        mdraw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=cls, width=1)
    elif code == ISOM_PROM_BUSH:                        # 418 Prom. bush or tree — zelený PLNÝ disk
        # Template: plný zelený bod (outer color 3); odlišný od 417 (dutý prstenec) i 419 (X).
        r = LANDMARK_BUSH_R_PX
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C_GREEN3)
        mdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=cls)
    elif code == ISOM_VEG_FEATURE:                      # 419 Prom. vegetation feature — zelený X
        # Dvě zelené diagonály (mirror inject._stamp_cross; generátorový styl bez bílé svatozáře,
        # konzistentní s 417 kroužkem — svatozář kreslí až degradér/realita, ne čistý gen render).
        r = LANDMARK_VEGFEAT_R_PX
        draw.line([(cx - r, cy - r), (cx + r, cy + r)], fill=C_GREEN3, width=1)
        draw.line([(cx - r, cy + r), (cx + r, cy - r)], fill=C_GREEN3, width=1)
        mdraw.line([(cx - r, cy - r), (cx + r, cy + r)], fill=cls, width=1)
        mdraw.line([(cx - r, cy + r), (cx + r, cy - r)], fill=cls, width=1)
    elif code == ISOM_SPRING:                           # 312 Spring — modré „U", ústí NAHORU
        # Template (omap +y = DOLŮ): volné konce na omap y=-351 → NAHOŘE, oblouk dole → ústí
        # nahoru (∪). Stejný tvar jako 111 depression, jen modrá. PIL arc(0,180) = spodní půlkruh = ∪.
        r = LANDMARK_SPRING_R_PX
        bbox = [cx - r, cy - r, cx + r, cy + r]
        draw.arc(bbox, 0, 180, fill=C_BLUE, width=1)
        mdraw.arc(bbox, 0, 180, fill=cls, width=1)
    elif code == ISOM_WELL:                             # 311 Well/tank — modrý čtverec (obrys)
        s = LANDMARK_WELL_HALF_PX
        draw.rectangle([cx - s, cy - s, cx + s, cy + s], outline=C_BLUE, width=1)
        mdraw.rectangle([cx - s, cy - s, cx + s, cy + s], outline=cls, width=1)
    else:                                               # 203.2 Cave — černá „Λ" stříška (hrot NAHORU)
        # Template (omap +y = DOLŮ): hrot na omap y=-735 → NAHOŘE, základna dole → Λ (otočené V,
        # stříška). 203.2 = „with a distinct entrance" (vstup do jeskyně). 203.1 by byl V (hrot dolů).
        apex = (cx, cy - LANDMARK_CAVE_APEX_PX)          # hrot nahoře (Λ stříška)
        bl = (cx - LANDMARK_CAVE_HALF_PX, cy + LANDMARK_CAVE_TOP_PX)  # levý dolní konec
        br = (cx + LANDMARK_CAVE_HALF_PX, cy + LANDMARK_CAVE_TOP_PX)  # pravý dolní konec
        draw.line([bl, apex, br], fill=C_BLACK, width=1)  # 2 tahy = chevron „Λ"
        mdraw.line([bl, apex, br], fill=cls, width=1)


def _draw_crossing_point(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                         cx: float, cy: float, ux: float, uy: float) -> None:
    """ISOM 519 Crossing point: dvě čárky tvořící „bránu" v plotě (Sez. 52).

    (ux,uy) = jednotková tangenta nosné zdi v px. Čárky jsou KOLMÉ na zeď (směr normály),
    posunuté ±BARRIER_HALF_GAP_PX PODÉL zdi → plot prochází mezerou mezi nimi. px-tuned;
    .omap věrný ze symbolu (rotatable bodový objekt, rotace = úhel tangenty)."""
    nx, ny = -uy, ux                                  # normála na zeď = směr čárek
    g, h = BARRIER_HALF_GAP_PX, BARRIER_HALF_LEN_PX
    cls = BARRIER_CLASS[ISOM_CROSSING_POINT]
    for s in (1, -1):                                 # dvě čárky ±gap podél zdi
        mx, my = cx + s * g * ux, cy + s * g * uy     # střed čárky
        a = (mx - h * nx, my - h * ny)
        b = (mx + h * nx, my + h * ny)
        draw.line([a, b], fill=C_BLACK, width=1)
        mdraw.line([a, b], fill=cls, width=1)


def _generate_real_landmarks(draw: ImageDraw.ImageDraw, ldraw: ImageDraw.ImageDraw,
                             lat: float, lon: float, geo_bbox: tuple) -> tuple[list, list]:
    """Reálné bodové orientační prvky (real-půlka, Sez. 43): věž 524 / mohyla 526 / kříž 530 /
    strom 417 ze ZABAGED. Mirror _generate_real_rocks (body): vrstva → ISOM symbol přes
    map_landmark_to_isom. Vrací (landmark_features [(gx, gy, code)], landmarks_info)."""
    from zabaged import fetch_landmarks, map_landmark_to_isom
    landmark_features: list[tuple] = []
    landmarks_info: list[dict] = []
    for x, y, layer in fetch_landmarks(lat, lon, GW, GH, TILE_M):
        code = map_landmark_to_isom(layer)
        if code is None:
            continue
        gx, gy = _sjtsk_to_grid(x, y, geo_bbox)
        px, py = _grid_to_px(gx, gy)
        _draw_landmark(draw, ldraw, px, py, code)
        landmark_features.append((gx, gy, code))
        landmarks_info.append({"symbol": code, "symbol_name": LANDMARK_NAME[code],
                               "kind": "point", "layer": layer})
    return landmark_features, landmarks_info


def _generate_real_barriers(draw: ImageDraw.ImageDraw, bdraw: ImageDraw.ImageDraw,
                            geo_bbox: tuple, barrier_raw: list) -> tuple[list, list]:
    """Reálné zábrany na nosné zdi 513 → ISOM 519 Crossing point (real-půlka, Sez. 52).

    Mirror _generate_real_landmarks, ale ORIENTOVANÁ: tangenta nosné zdi (S-JTSK) se přepočte do
    px směru transformací dvou bodů (p a p+tangenta) — robustní vůči konvenci os (jako řopíky).
    `barrier_raw` = [(x, y, tdx, tdy)] ze zabaged.fetch_barriers (spočteno 1× v generate_map, sdíleno
    s přerušením zdi). Vrací (barrier_features [(gx, gy, rot_rad, code)], barriers_info); rot pro .omap
    (radiány, px konvence jako lávka 512.2)."""
    barrier_features: list[tuple] = []
    barriers_info: list[dict] = []
    code = ISOM_CROSSING_POINT
    for x, y, tdx, tdy in barrier_raw:
        gx, gy = _sjtsk_to_grid(x, y, geo_bbox)
        px, py = _grid_to_px(gx, gy)
        gx2, gy2 = _sjtsk_to_grid(x + tdx, y + tdy, geo_bbox)   # druhý bod podél tangenty
        px2, py2 = _grid_to_px(gx2, gy2)
        ux, uy = px2 - px, py2 - py
        norm = math.hypot(ux, uy) or 1.0
        ux, uy = ux / norm, uy / norm
        _draw_crossing_point(draw, bdraw, px, py, ux, uy)
        rot = math.atan2(uy, ux)                                # orientace symbolu (tangenta zdi)
        barrier_features.append((gx, gy, rot, code))
        barriers_info.append({"symbol": code, "symbol_name": BARRIER_NAME[code],
                              "kind": "point", "layer": "Zábrana"})
    return barrier_features, barriers_info


def _draw_earthbank_ticks(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                          pts: list[tuple[float, float]], cls: int) -> None:
    """Jednostranné kolmé čárky podél sráze (ISOM 104 Earth bank). Jako _draw_perp_ticks, ale
    tick jen na JEDNU stranu (pravá normála) — earth bank má ticky na nižší straně svahu.
    Orientace dle DMR sklonu = TODO (Sez. 43); zatím konzistentní pravá normála."""
    if len(pts) < 2:
        return
    pos = 0.0
    next_tick = EARTHBANK_TICK_SPACING_PX
    hl = EARTHBANK_TICK_LEN_PX
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg == 0.0:
            continue
        ux, uy = (x1 - x0) / seg, (y1 - y0) / seg
        nx, ny = -uy, ux                            # pravá normála (rotace směru o 90°)
        while next_tick <= pos + seg:
            t = next_tick - pos
            bx, by = x0 + ux * t, y0 + uy * t       # bod na linii
            draw.line([bx, by, bx + nx * hl, by + ny * hl], fill=C_BROWN, width=1)  # sráz = hnědá (jako linie 104)
            mdraw.line([bx, by, bx + nx * hl, by + ny * hl], fill=cls, width=1)
            next_tick += EARTHBANK_TICK_SPACING_PX
        pos += seg


def _draw_line_feature(draw: ImageDraw.ImageDraw, ldraw: ImageDraw.ImageDraw,
                       curve_px: list[tuple[float, float]], code: int) -> None:
    """Liniový orientační prvek (Sez. 43): 104 sráz (plná + ticky) / 513 zeď (plná). Wrapper nad
    _draw_line_symbol (DRY); 104 navíc jednostranné ticky. (Stromořadí 406 jde plošně, Sez. 45.)"""
    mode, width, dash = LINEFEAT_STYLE[code]
    color = LINEFEAT_COLOR[code]
    cls = LINEFEAT_CLASS[code]
    _draw_line_symbol(draw, ldraw, curve_px, color, mode, width, dash, cls)
    if code == ISOM_EARTH_BANK:
        _draw_earthbank_ticks(draw, ldraw, curve_px, cls)


def _generate_real_line_features(draw: ImageDraw.ImageDraw, ldraw: ImageDraw.ImageDraw,
                                 lat: float, lon: float, geo_bbox: tuple,
                                 barrier_break_px: list | None = None) -> tuple[list, list]:
    """Reálné liniové orientační prvky (real-půlka, Sez. 43): sráz 104 / zeď 513 ze ZABAGED.
    Mirror _generate_real_powerlines (linie). Vrací (linefeat_features [(grid, code)],
    linefeatures_info). (Stromořadí jde plošně jako 406, viz _generate_real_tree_rows, Sez. 45.)

    `barrier_break_px` = px body bran (Sez. 52): zeď 513 se v jejich místě PŘERUŠÍ (ISOM 519
    „line broken at the crossing point" — průchod plotem). Sráz 104 se neřeže. Přerušená zeď =
    víc grid kusů (omap i rastr mají mezeru), ale info zůstává 1× per zeď (count 513 nezkreslí
    mezeru jako nový prvek)."""
    from zabaged import fetch_line_features, map_line_feature_to_isom
    linefeat_features: list[tuple] = []
    linefeatures_info: list[dict] = []
    break_px = barrier_break_px or []
    half = BARRIER_BREAK_HALF_MM * PX_PER_MM
    near = BARRIER_BREAK_NEAR_M / (WORLD_W_M / W)           # práh „brána na této zdi" (m → plátno px)
    for f in fetch_line_features(lat, lon, GW, GH, TILE_M):
        code = map_line_feature_to_isom(f["layer"])
        if code is None:
            continue
        for line in f["lines"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            px = [_grid_to_px(gx, gy) for gx, gy in grid]
            if len(px) < 2:
                continue
            # zeď 513 přerušit pod brankami (519); sráz 104 nechat celý
            if code == ISOM_WALL and break_px:
                cum = _cum_distance_px(grid)
                zones = []
                for bpx, bpy in break_px:
                    pc, dist = _project_to_line(bpx, bpy, px, cum)
                    if dist <= near:
                        zones.append((pc - half, pc + half))
                pieces = _split_by_zones_interp(grid, cum, zones) if zones else [grid]
            else:
                pieces = [grid]
            linefeatures_info.append({"symbol": code, "symbol_name": LINEFEAT_NAME[code],
                                      "kind": "line", "layer": f["layer"]})  # 1× per zeď (i přerušenou)
            for piece in pieces:
                ppx = [_grid_to_px(gx, gy) for gx, gy in piece]
                if len(ppx) < 2:
                    continue
                _draw_line_feature(draw, ldraw, ppx, code)
                linefeat_features.append((piece, code))
    return linefeat_features, linefeatures_info


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


def _world_file_coeffs(bbox: tuple) -> tuple[float, float, float, float, float, float]:
    """Koeficienty ESRI world filu (.pgw) pro rgb.png: pixel → world (S-JTSK metry).

    Rastr je grid-north-up, osově zarovnaný se S-JTSK — mapování _grid_to_px ∘ _sjtsk_to_grid
    je čistý scale+translate BEZ rotace (`x = xmin + px·A`, `y = ymax + py·E`), takže rotační
    členy (B, D) jsou nulové. Reálné OB mapy mají v .pgw rotaci o grivaci (jsou magnetic-north-up);
    generátor ji nemá (Sez. 37). World file odkazuje STŘED levého horního pixelu → +0,5 px offset.
    Vrací (A, D, B, E, C, F) v pořadí řádků .pgw.
    """
    xmin, ymin, xmax, ymax = bbox
    a = (xmax - xmin) / W          # m/px, osa x (kladné)
    e = -(ymax - ymin) / H         # m/px, osa y (záporné: py roste dolů → y klesá; sever nahoře)
    c = xmin + 0.5 * a             # x středu levého horního pixelu
    f = ymax + 0.5 * e             # y středu levého horního pixelu
    return a, 0.0, 0.0, e, c, f


def _write_world_file(out_path: Path, bbox: tuple) -> None:
    """Zapíše world file (.pgw) k rgb.png — 6 řádků A,D,B,E,C,F (viz _world_file_coeffs).

    Jen reálný terén (S-JTSK georef); volá se po uložení rgb.png. Umožní georeferencovaný
    overlay generátoru proti reálné mapě v GIS (holistický verify-against-source, Sez. 37).
    """
    a, d, b, e, c, f = _world_file_coeffs(bbox)
    out_path.write_text(f"{a:.10f}\n{d:.10f}\n{b:.10f}\n{e:.10f}\n{c:.4f}\n{f:.4f}\n",
                        encoding="utf-8")


def _georef_meta(bbox: tuple, crs_epsg: int | None, grivation: float | None = None) -> dict:
    """Georef blok pro meta.json: CRS, bbox výseku, world file, orientace severu.

    Real (crs 5514) → S-JTSK bbox + .pgw odkaz + rozlišení; noise → lokální metry, bez world
    filu. `north` dokumentuje orientaci: bez grivace `"grid"` (rastr NENÍ rotován, default Sez. 37),
    s grivací `"magnetic"` — `.omap` georef nese grivaci jako metadata (OOM zobrazí natočené na
    magnetický sever), GEOMETRIE i rastr zůstávají v S-JTSK gridu (rotace jen v georef, izomorf
    s kartografem; Sez. 112). `grivation_deg` = úhel grid→magnetic [°] nebo None.
    """
    north = "magnetic" if grivation is not None else "grid"
    if crs_epsg is None:
        return {"crs": "local_m", "bbox": [round(v, 2) for v in bbox], "north": north,
                "grivation_deg": grivation}
    return {
        "crs": f"EPSG:{crs_epsg}",
        "bbox_sjtsk": [round(v, 3) for v in bbox],
        "pixel_size_m": round((bbox[2] - bbox[0]) / W, 4),
        "world_file": "rgb.pgw",
        "north": north,             # grid (grivace None, Sez. 37) / magnetic (grivace v .omap, Sez. 112)
        "grivation_deg": grivation,
    }


def _isom_meta() -> dict:
    """ISOM deklarace pro meta.json — ochrana proti záměně verze symbolů (Sez. 38).

    Číslování symbolů se mezi ISOM 2000 a 2017-2 RECYKLUJE s jiným významem: 521 = Building
    v 2017-2, ale High stone wall v 2000; Narrow ride 509→508; Railway 515→509. Bez explicitní
    verze konzument (UC5, člověk) hádá z čísel → konflikt (nález Sez. 37: reálné mapy v
    `resources/` jsou ISOM 2000, generátor 2017-2). Crosswalk: OOM `ISOM2000-ISOM2017-2.crt`.
    Měřítko 1:10000 — `template_classic.omap` je geometricky identický s oficiálním OOM
    1:10000 ISOM 2017-2 setem (line_width ověřeno Sez. 38), ne ruční odhad."""
    return {"version": "2017-2", "scale": MAP_SCALE, "symbol_set": "template_classic.omap"}


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


def _layer_meta_section(mask: str, info: list[dict], name_map: dict, class_map: dict) -> dict:
    """Jedna vrstvová sekce meta.json: count/mask/source/symbols/classes/items/licence.

    DRY + izomorfismus (A1, Sez. 50): tentýž ~10řádkový blok byl zkopírovaný 14× (část v
    `_build_meta`, část injektovaná zvlášť za ním → asymetrie). Helper je jediná pravda struktury
    sekce; `info` = seznam {"symbol": kód, …}, symboly/třídy se staví ze SKUTEČNĚ použitých kódů
    (jeden zdroj NAME/CLASS map). `key=str` u sortu: landmarks míchají int (524/312) i str ("203.2")."""
    used = sorted({it["symbol"] for it in info}, key=str)
    return {
        "count": len(info),
        "mask": mask,
        "source": "cuzk_zabaged",
        "symbols": {str(c): name_map[c] for c in used},
        "classes": {"0": "pozadí",
                    **{str(class_map[c]): f"{c} {name_map[c]}" for c in used}},
        "items": info,
        "licence": "CC BY 4.0 (ČÚZK ZABAGED)",
    }


def _build_meta(seed: int, rug: float, det: float, terrain: str, paths_mode: str,
                pseudorealistic: bool, lat: float, lon: float,
                elev: np.ndarray, crs_epsg: int | None,
                n_contours: int, n_formlines: int, n_paths: int, paths_info: list[dict],
                point_symbols: list[dict], omap_info: dict, real_sections: dict,
                layer_errors: dict[str, str] | None = None) -> dict:
    """Sestaví obsah meta.json: parametry, původ terénu, legendu GT tříd, info o exportech.

    Vyčleněno z generate_map() (SLAP, Sez. 15): orchestrace kreslení vrstev a deklarativní
    sestavení metadat jsou dvě úrovně abstrakce. Reálné vrstvy (rides/water/…/treerows) přicházejí
    jako hotový `real_sections` dict (sestavený v generate_map přes _layer_meta_section, A1 Sez. 50)
    → meta je jen rozbalí; tady zůstávají jen univerzální části (terén/grid/vrstevnice/cesty/body).
    """
    # cesty: legendu symbolů/tříd stavíme dynamicky ze SKUTEČNĚ použitých ISOM kódů
    # (proc dělá 503/505; real 502-506 dle ZABAGED→ISOM) — jeden zdroj pravdy PATH_NAME/PATH_CLASS.
    # (Cesty zůstávají vlastní, ne přes _layer_meta_section: source je proc|real a licence podmíněná.)
    used_path_codes = sorted({p["symbol"] for p in paths_info})
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
        # reálné ZABAGED/RÚIAN vrstvy (rides/water/paved/buildings/powerlines/railways/rocks/bridges/
        # surfaces/landmarks/linefeatures/marsh/treerows) — sestavené v generate_map přes
        # _layer_meta_section (A1 Sez. 50): jediná cesta i struktura sekce, žádná asymetrie
        # uvnitř/vně _build_meta. Sekce přítomna jen pro vrstvy s mode == real (jinak v dictu není).
        **real_sections,
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
                         lat: float, lon: float, geo_bbox: tuple,
                         bridge_cutters: list[list] | None = None,
                         tunnel_cutters: list[list] | None = None) -> tuple[list, list]:
    """Reálné cesty (real-půlka §4.9): komunikace ze ZABAGED REST pro tentýž výsek.

    `bridge_cutters` (volitelně, Sez. 32 E1) = mosty: použít CROSSING detection (most nad
    silnicí = 1-2 bod-průsečíky → cropuj; silnice na mostě = paralel souběh > 2 → ignore).
    `tunnel_cutters` (volitelně, Sez. 32 E4) = tunely: použít PASSAGE detection (silnice
    v silničním tunelu = passage zone mezi cutter endpoints → cropuj celý úsek).
    """
    from zabaged import fetch_paths, map_path_to_isom
    feats = fetch_paths(lat, lon, GW, GH, TILE_M)
    paths_info: list[dict] = []
    path_features: list[tuple] = []
    for f in feats:
        code = map_path_to_isom(f["layer"], f["props"])
        for line in f["lines"]:
            curve_grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            # Dvojí cropping: crossings (mosty) + passages (tunely), sekvenčně
            sub_curves = [curve_grid]
            if bridge_cutters:
                sub_curves = [s for c in sub_curves for s in _crop_line_under_bridge(c, bridge_cutters)]
            if tunnel_cutters:
                sub_curves = [s for c in sub_curves for s in _crop_line_at_passages(c, tunnel_cutters)]
            for sub in sub_curves:
                curve_px = [_grid_to_px(gx, gy) for gx, gy in sub]
                if len(curve_px) < 2:
                    continue
                _draw_path(draw, pdraw, curve_px, code)
                path_features.append((sub, code))
                paths_info.append({"symbol": code, "symbol_name": PATH_NAME[code],
                                   "layer": f["layer"]})
    return path_features, paths_info


def _generate_real_water(draw: ImageDraw.ImageDraw, wdraw: ImageDraw.ImageDraw,
                         lat: float, lon: float, geo_bbox: tuple,
                         bridge_cutters: list[list] | None = None) -> tuple[list, list, list]:
    """Reálná voda (real-půlka hydrografie, Sez. 17): toky + plochy ze ZABAGED REST.

    `bridge_cutters` (volitelně, Sez. 32 E1): seznam grid linií mostů. CROSSING detection
    cropuje vodní tok pod mostem (1-2 bod-průsečíky → cropuj; paralel souběh > 2 → ignore).
    Voda v tunelu je vzácná → tunely se nepoužívají jako cutter pro vodu.
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
            # Cropping mostů (buffer pás kolem osy, Sez. 33 verify Most.omap)
            sub_lines = (_crop_line_under_bridge(grid, bridge_cutters)
                         if bridge_cutters else [grid])
            for sub in sub_lines:
                px = [_grid_to_px(gx, gy) for gx, gy in sub]
                if len(px) < 2:
                    continue
                _draw_water_line(draw, wdraw, px, code)
                line_features.append((sub, code))
                water_info.append({"symbol": code, "symbol_name": WATER_NAME[code], "kind": "line",
                                   "layer": f["layer"], "name": f["props"].get("jmeno")})
    for f in area_feats:
        code = map_water_to_isom(f["layer"], f["props"])
        if code is None:
            continue
        for poly in f["rings"]:
            grid_rings, px_rings = _poly_to_grid_px(poly, geo_bbox)
            if len(px_rings[0]) < 3:
                continue
            _draw_water_area(draw, wdraw, px_rings, code)
            area_features.append((grid_rings, code))
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
        for poly in f["rings"]:
            grid_rings, px_rings = _poly_to_grid_px(poly, geo_bbox)
            if len(px_rings[0]) < 3:
                continue
            _draw_building_area(draw, bdraw, px_rings, code)
            area_features.append((grid_rings, code))
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
                            lat: float, lon: float, geo_bbox: tuple,
                            tunnel_cutters: list[list] | None = None) -> tuple[list, list]:
    """Reálné železniční tratě (real-půlka, Sez. 28): Železniční_trať ze ZABAGED REST → ISOM 509.

    `tunnel_cutters` (volitelně, Sez. 32 E4): seznam grid linií tunelů. PASSAGE detection
    cropuje železnici v úseku tunelu (= mezi nejbližšími body line k cutter start/end).
    Most NEcropuje železnici (železnice JE NA mostu = paralel souběh = bez crossing detection).
    """
    from zabaged import fetch_railways, map_railway_to_isom
    feats = fetch_railways(lat, lon, GW, GH, TILE_M)
    railways_info: list[dict] = []
    railway_features: list[tuple] = []
    for f in feats:
        c = map_railway_to_isom(f["layer"], f["props"])
        for line in f["lines"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            # Cropping tunelů (Sez. 32 E4, passage strategy)
            sub_lines = (_crop_line_at_passages(grid, tunnel_cutters)
                         if tunnel_cutters else [grid])
            for sub in sub_lines:
                px = [_grid_to_px(gx, gy) for gx, gy in sub]
                if len(px) < 2:
                    continue
                _draw_railway(draw, rdraw, px, c)
                railway_features.append((sub, c))
                railways_info.append({"symbol": c, "symbol_name": RAILWAY_NAME[c],
                                      "layer": f["layer"]})
    return railway_features, railways_info


def _generate_real_rides(draw: ImageDraw.ImageDraw, ridraw: ImageDraw.ImageDraw,
                         lat: float, lon: float, geo_bbox: tuple) -> tuple[list, list]:
    """Reálné lesní průseky (real-půlka, Sez. 36): Lesní průsek ze ZABAGED REST → ISOM 508.

    Mirror _generate_real_railways/_generate_real_paths (S-JTSK → grid → px → čárkovaná linie).
    KISS, vše → 508 (map_ride_to_isom). Vrací (ride_features [(grid, code)], rides_info) v
    souřadnicích MŘÍŽKY (zdroj pro .omap). V bezlesém výseku = 0 prvků."""
    from zabaged import fetch_forest_rides, map_ride_to_isom
    feats = fetch_forest_rides(lat, lon, GW, GH, TILE_M)
    rides_info: list[dict] = []
    ride_features: list[tuple] = []
    for f in feats:
        c = map_ride_to_isom(f["layer"], f["props"])
        for line in f["lines"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            px = [_grid_to_px(gx, gy) for gx, gy in grid]
            if len(px) < 2:
                continue
            _draw_ride(draw, ridraw, px, c)
            ride_features.append((grid, c))
            rides_info.append({"symbol": c, "symbol_name": RIDE_NAME[c], "layer": f["layer"]})
    return ride_features, rides_info


def _generate_real_paved(draw: ImageDraw.ImageDraw, adraw: ImageDraw.ImageDraw,
                         lat: float, lon: float, geo_bbox: tuple,
                         *, urban_base: bool = False) -> tuple[list, list]:
    """Reálné zpevněné plochy (real-půlka, Sez. 28+42+54+57): plochy ze ZABAGED → ISOM 501 / 501.1.

    Mirror _generate_real_buildings (RAW S-JTSK → grid → px → polygon, bez generalizace).
    Zdroj 501 (s obrysem): kolejiště (fetch_paved_areas, vymezený prostor) + asfaltové dopravní plochy
    z areálů účelové zástavby (114: autobusové nádraží / čerpací stanice — Sez. 42). Zdroj 501.1
    (BEZ obrysu): parkoviště (Sez. 57 — průchozí) + ostatní plocha v sídlech (115, Sez. 54 — díry
    vykrojí budovy/zeleň/cesty). Areály 114 mapují i na 520 (oplocené areály) → ty sem NEpatří
    (surfaces kanál), proto filtr `code in PAVED_CLASS` (vezme 501/501.1, přeskočí 520).

    **Dva z-order průchody (Sez. 54):** `urban_base=True` kreslí JEN 501.1 (base výplň sídla + parkoviště
    = ÚPLNĚ VESPOD, před surfaces → olivová 520 privátních parcel ji překryje, je věrnější);
    `urban_base=False` (default) kreslí JEN 501 (kolejiště NAD pokryvem, původní pozice).
    Sdílí jednu paved masku (volá se 2× s týmž adraw). Vrací (area_features [(grid_rings, code)],
    paved_info) v souřadnicích MŘÍŽKY (zdroj pro .omap)."""
    from zabaged import (fetch_paved_areas, map_paved_to_isom,
                         fetch_utility_areas, map_utility_area_to_isom)
    area_features: list[tuple] = []
    paved_info: list[dict] = []
    for feats, mapper in ((fetch_paved_areas(lat, lon, GW, GH, TILE_M), map_paved_to_isom),
                          (fetch_utility_areas(lat, lon, GW, GH, TILE_M), map_utility_area_to_isom)):
        for f in feats:
            code = mapper(f["layer"], f["props"])
            if code not in PAVED_CLASS:    # 520 (oplocené areály 114) patří do surfaces kanálu, ne sem
                continue
            if (code == ISOM_PAVED_NB) != urban_base:    # base průchod jen 501.1, top jen 501 (z-order Sez. 54)
                continue
            for poly in f["rings"]:
                grid_rings, px_rings = _poly_to_grid_px(poly, geo_bbox)
                if len(px_rings[0]) < 3:
                    continue
                _draw_paved_area(draw, adraw, px_rings, code)
                area_features.append((grid_rings, code))
                paved_info.append({"symbol": code, "symbol_name": PAVED_NAME[code],
                                   "kind": "area", "layer": f["layer"]})
    return area_features, paved_info


def _fill_mask_rings(mdraw: ImageDraw.ImageDraw, px_rings: list) -> None:
    """Vyplní polygon [outer, díra…] do sběrné L-masky (255) — even-odd přes díry (Sez. 98).

    Sběrná maska pro dissolve olivové 520: parcely, které se v katastru DOTÝKAJÍ, splynou v rastru
    do souvislého bloku; mezery (cesta/pole mezi shluky) zůstanou → oddělené bloky (záměr)."""
    rings = [px_rings[0], *(h for h in px_rings[1:] if len(h) >= 3)]
    if len(rings) > 1:
        _fill_rings_scanline(mdraw, rings, 255)
    else:
        mdraw.polygon(px_rings[0], fill=255)


def _dissolve_mask_to_polys(mask: np.ndarray) -> list:
    """Bool maska → list polygonů [outer, díra…] v px plátna (Sez. 98).

    Reuse `rock_relief` (contourpy marching squares + _group_holes na vnoření) — týž nástroj jako
    skály 206 a separace vegetace (izomorfismus maska→polygon, KISS, bez nové závislosti shapely).
    Souřadnice contourpy = (col, row) = (px x, px y)."""
    from rock_relief import _contour_rings, _group_holes
    out: list = []
    for poly in _group_holes(_contour_rings(mask)):
        out.append([[(float(x), float(y)) for x, y in ring] for ring in poly])
    return out


def _draw_fence_line(draw: ImageDraw.ImageDraw, ring_px) -> None:
    """Plot 516 po obvodu bloku zástavby: tenká černá linie + ticky DOVNITŘ pozemku (Sez. 98).

    ISOM 516 „tags inside" (spec template). Strana ticku se určuje per-tick testem `_point_in_ring`
    (robustní, nezávislé na orientaci ringu): z bodu na lince zkusíme krok podél normály — která
    strana padne dovnitř ringu, tam tick míří. Ring má být už narovnaný (RDP) a uzavřený."""
    from rock_relief import _point_in_ring
    pts = [(float(x), float(y)) for x, y in ring_px]
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    if len(pts) < 3:
        return
    draw.line(pts, fill=C_BLACK, width=FENCE_WIDTH_PX, joint="curve")
    ring = np.asarray(pts)
    acc = 0.0                                            # ujetá délka podél obvodu → rovnoměrné ticky
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        seg = math.hypot(bx - ax, by - ay)
        if seg == 0:
            continue
        ux, uy = (bx - ax) / seg, (by - ay) / seg       # jednotkový směr segmentu
        nx, ny = -uy, ux                                 # kolmice (jedna strana; druhá = záporná)
        d = FENCE_TICK_SPACING_PX - acc                 # vzdálenost k prvnímu ticku v tomto segmentu
        while d < seg:
            tx, ty = ax + ux * d, ay + uy * d            # bod ticku na lince
            sgn = 1.0 if _point_in_ring((tx + nx, ty + ny), ring) else -1.0   # která normála míří dovnitř
            draw.line([(tx, ty), (tx + sgn * nx * FENCE_TICK_LEN_PX,
                                  ty + sgn * ny * FENCE_TICK_LEN_PX)], fill=C_BLACK, width=1)
            d += FENCE_TICK_SPACING_PX
        acc = (acc + seg) % FENCE_TICK_SPACING_PX        # přenos zbytku délky do dalšího segmentu


def _generate_real_surfaces(draw: ImageDraw.ImageDraw, sdraw: ImageDraw.ImageDraw,
                            lat: float, lon: float, geo_bbox: tuple,
                            pseudorealistic: bool) -> tuple[list, list, list]:
    """Reálný plošný pokryv (real-půlka, Sez. 41-53): open land louka → 401 žlutá; park/okrasná zahrada
    → 402 (žlutá + bílé tečky scattered trees), ostatní udržovaná zeleň → 402.1 (žlutá + zelené tečky
    scattered bushes, Sez. 53); pole → 412 (žlutá + černý tečkový pattern); olivová 520 „zákaz vstupu"
    = hřbitov (ZABAGED) ∪ privátní pozemek u domu (RÚIAN: zahrada + zastavěná plocha, Sez. 42)
    ∪ sad/zahrada (ZABAGED, oplocené zahrady u domů/chalup, Sez. 49). Pět tříd v JEDNÉ multi-class
    masce (1=open land, 2=olivová, 3=pole, 4=park 402, 5=zeleň 402.1; štěpení nese `typ_pudy_k`).

    Mirror _generate_real_paved (RAW S-JTSK → grid → px → polygon, bez generalizace). Kultura 412
    pod ISOM min. plochou (SURFACE_MIN_AREA_PX2) → spadne na 401 (volba uživatele Sez. 47).

    OLIVOVÁ 520 = DISSOLVE DO BLOKŮ (Sez. 98, měření přestřelu + volba uživatele „zástavba = blok"):
    RÚIAN katastr fragmentuje zástavbu na tisíce drobných parcel (LS 18884 obj = 52 % výseku olivové,
    91-96 % z RÚIAN privát) → kartograf kreslí jeden souvislý olivový blok, ne mozaiku. Všechny zdroje
    520 → sběrná maska → contourpy dissolve (_dissolve_mask_to_polys) → souvislé bloky. RÚIAN ZAHRADA
    (druh 5) má vlastní pod-masku → její obvod = PLOT 516 (pseudo fáze 2, „kde má zástavba plot"; jen když
    `pseudorealistic`). NE druh 13 (zastavěná plocha = otisk budovy — plot by „uvěznil" panelák místo
    pozemku, Sez. 113). Ne-520 (401/412/402/402.1) jdou dál per-feature (beze změny).

    Z-ORDER (Sez. 42, téma 2): olivová se kreslí PO žluté/kultuře → privátní zahrada (RÚIAN 520)
    přemaže žluté/pole na témže místě. Vrací (area_features [(grid, code)], surfaces_info, fence_features
    [(grid_line, 516)]) v souřadnicích MŘÍŽKY (zdroj pro .omap). V bezlesém/lesním výseku = 0 prvků."""
    from zabaged import (fetch_open_land, fetch_cemeteries, fetch_utility_areas, fetch_quarries,
                         map_open_land_to_isom, map_cemetery_to_isom, map_utility_area_to_isom,
                         map_quarry_to_isom)
    from ruian import fetch_private_land, map_private_land_to_isom
    area_features: list[tuple] = []
    surfaces_info: list[dict] = []
    fence_features: list[tuple] = []
    olive_img = Image.new("L", (W, H), 0)            # celá olivová 520 (všechny zdroje) → dissolve bloky
    olive_ruian_img = Image.new("L", (W, H), 0)      # jen RÚIAN zahrada (druh 5) → obvod = plot 516 (Sez. 113: ne druh 13)
    odraw = ImageDraw.Draw(olive_img)
    ordraw = ImageDraw.Draw(olive_ruian_img)
    # Skupiny jdou stejnou plošnou cestou (RAW ring → výplň), liší se mapperem/barvou/patternem.
    # `is_ruian` = privátní katastr (zdroj plotu 516). Areály účelové zástavby (114) mapují i na 501
    # (asfaltové dopravní plochy) — ty sem NEpatří (paved kanál), proto filtr `code in SURFACE_FILL`.
    for feats, mapper, is_ruian in (
            (fetch_open_land(lat, lon, GW, GH, TILE_M), map_open_land_to_isom, False),
            (fetch_private_land(lat, lon, GW, GH, TILE_M), map_private_land_to_isom, True),
            (fetch_cemeteries(lat, lon, GW, GH, TILE_M), map_cemetery_to_isom, False),
            (fetch_utility_areas(lat, lon, GW, GH, TILE_M), map_utility_area_to_isom, False),
            (fetch_quarries(lat, lon, GW, GH, TILE_M), map_quarry_to_isom, False)):
        for f in feats:
            code = mapper(f["layer"], f["props"])
            if code not in SURFACE_FILL:    # 501 (asfaltové areály 114) patří do paved kanálu, ne sem
                continue
            for poly in f["rings"]:
                grid_rings, px_rings = _poly_to_grid_px(poly, geo_bbox)
                if len(px_rings[0]) < 3:
                    continue
                if code == ISOM_OUT_OF_BOUNDS:      # 520 → sběrná maska (dissolve níž), NE per-parcela
                    _fill_mask_rings(odraw, px_rings)
                    # plot 516 jen kolem ZAHRAD (druh 5), NE zastavěné plochy (druh 13 = otisk budovy → plot
                    # by „uvěznil" panelák místo pozemku, Sez. 113 Lidové sady). Druh 13 zůstává v 520 olivové.
                    if is_ruian and str(f["props"].get("druhpozemkukod")) == "5":
                        _fill_mask_rings(ordraw, px_rings)
                    continue
                # kultura pod ISOM min. plochou → degraduj na 401 open land (Sez. 47; filtr na vnějším prstenu)
                draw_code = code
                if code in SURFACE_MIN_AREA_PX2 and _polygon_area_px(px_rings[0]) < SURFACE_MIN_AREA_PX2[code]:
                    draw_code = ISOM_OPEN_LAND
                if draw_code in SURFACE_DOT:
                    _draw_dotted_surface_area(draw, sdraw, px_rings, draw_code)
                else:
                    _draw_surface_area(draw, sdraw, px_rings, draw_code)
                area_features.append((grid_rings, draw_code))
                surfaces_info.append({"symbol": draw_code, "symbol_name": SURFACE_NAME[draw_code],
                                      "kind": "area", "layer": f["layer"]})
    # --- olivová 520: dissolve sběrné masky → souvislé bloky (jeden blok = zástavba, Sez. 98) ---
    for poly_px in _dissolve_mask_to_polys(np.asarray(olive_img) > 0):
        if len(poly_px[0]) < 3:
            continue
        _draw_surface_area(draw, sdraw, poly_px, ISOM_OUT_OF_BOUNDS)
        grid_rings = [[(px / W * (GW - 1), py / H * (GH - 1)) for px, py in ring] for ring in poly_px]
        area_features.append((grid_rings, ISOM_OUT_OF_BOUNDS))
        surfaces_info.append({"symbol": ISOM_OUT_OF_BOUNDS, "symbol_name": SURFACE_NAME[ISOM_OUT_OF_BOUNDS],
                              "kind": "area", "layer": "olivová (dissolve)"})
    # --- plot 516 po obvodu RÚIAN ZAHRAD (druh 5; pseudo fáze 2: ZABAGED plot nevede, Sez. 57/98/113) ---
    # Jen kolem SOUVISLÉ zástavby ≥ FENCE_MIN_AREA_M2 (měření Sez. 98: bez prahu 6,7× přestřel).
    if pseudorealistic:
        from rock_relief import _rdp
        m_per_px2 = (WORLD_W_M / W) * (TILE_M / H)    # plocha 1 px [m²] (W px = WORLD_W_M, H px = TILE_M)
        eps_px = FENCE_SIMPLIFY_M / (WORLD_W_M / W)   # RDP tolerance: m terénu → px plátna
        for poly_px in _dissolve_mask_to_polys(np.asarray(olive_ruian_img) > 0):
            outer = poly_px[0]
            if len(outer) < 3:
                continue
            if _polygon_area_px(outer) * m_per_px2 < FENCE_MIN_AREA_M2:   # malý blok (domek+zahrada) → neplotovat
                continue
            simp = _rdp(np.asarray(outer, float), eps_px)    # pixelové schody → přímé spojnice vrcholů
            _draw_fence_line(draw, simp)
            grid = [(px / W * (GW - 1), py / H * (GH - 1)) for px, py in simp]
            fence_features.append((grid, ISOM_FENCE))
    return area_features, surfaces_info, fence_features


def _marsh_indistinct(cx: float, cy: float) -> bool:
    """Pseudo (fáze 2, Sez. 99): má mokřad s centroidem (cx, cy) v MŘÍŽCE být 310 Indistinct místo 308?

    Deterministická pseudonáhoda ~MARSH_INDISTINCT_PCT % z polohy — spatial hash (prvočísla),
    stabilní MEZI BĚHY (ne `hash()` s PYTHONHASHSEED) a nezávislá na pořadí. ZABAGED zřetelnost
    mokřadu nenese (measure-first Sez. 99: rašeliniště/bažina geograficky binární, velikost
    nediskriminuje) → náhoda do statistické míry reálných map (medián ~59 % na 310)."""
    h = (int(round(cx)) * 73856093) ^ (int(round(cy)) * 19349663)
    return (h % 100) < MARSH_INDISTINCT_PCT


def _generate_real_marsh(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                         lat: float, lon: float, geo_bbox: tuple,
                         pseudorealistic: bool) -> tuple[list, list]:
    """Reálné mokřady (real-půlka, Sez. 44): bažina/močál + rašeliniště → 308 Marsh / 310 Indistinct.

    Mirror _generate_real_surfaces (RAW S-JTSK → grid → px → šrafovaný polygon, bez generalizace).
    Projekce = vždy 308; pseudo fáze 2 (pseudorealistic) reklasifikuje ~55 % mokřadů na 310 Indistinct
    deterministickou pseudonáhodou z centroidu (data zřetelnost nenesou, Sez. 99). Vrací (area_features
    [(grid, code)], marsh_info) v souřadnicích MŘÍŽKY (zdroj pro .omap). V suchém výseku = 0 prvků."""
    from zabaged import fetch_marsh, map_marsh_to_isom
    area_features: list[tuple] = []
    marsh_info: list[dict] = []
    for f in fetch_marsh(lat, lon, GW, GH, TILE_M):
        base_code = map_marsh_to_isom(f["layer"], f["props"])   # projekce ZABAGED→ISOM = 308
        for poly in f["rings"]:
            grid_rings, px_rings = _poly_to_grid_px(poly, geo_bbox)
            if len(px_rings[0]) < 3:
                continue
            code = base_code
            if pseudorealistic and base_code == ISOM_MARSH:      # fáze 2: část → 310 Indistinct
                ring = grid_rings[0]
                cx = sum(p[0] for p in ring) / len(ring)
                cy = sum(p[1] for p in ring) / len(ring)
                if _marsh_indistinct(cx, cy):
                    code = ISOM_MARSH_INDISTINCT
            _draw_marsh_area(draw, mdraw, px_rings, code)
            area_features.append((grid_rings, code))
            marsh_info.append({"symbol": code, "symbol_name": MARSH_NAME[code],
                               "kind": "area", "layer": f["layer"]})
    return area_features, marsh_info


def _generate_real_tree_rows(draw: ImageDraw.ImageDraw, tdraw: ImageDraw.ImageDraw,
                             lat: float, lon: float, geo_bbox: tuple) -> tuple[list, list]:
    """Reálná stromořadí jako lineární les (real-půlka, Sez. 45): `Liniová vegetace` → ISOM 406.

    Liniová DATA (osa) → PLOŠNÁ reprezentace: osu převedu na px, buffruji na nepravidelný pás
    (_buffer_polyline_irregular), zahodím úseky pod ISOM min. plochou (TREEROW_MIN_AREA_PX2) a
    vyplním 406. Pro .omap vracím prstenec v souřadnicích MŘÍŽKY (inverze _grid_to_px nad px
    vrcholy — TÝŽ polygon jako rastr, konzistence rastr↔omap). Vrací (area_features [(grid, 406)],
    treerows_info). V bezstromořadovém výseku = 0 prvků."""
    from zabaged import fetch_tree_rows, map_tree_row_to_isom
    area_features: list[tuple] = []
    treerows_info: list[dict] = []
    for f in fetch_tree_rows(lat, lon, GW, GH, TILE_M):
        code = map_tree_row_to_isom(f["layer"])
        for line in f["lines"]:
            axis_px = [_grid_to_px(*_sjtsk_to_grid(x, y, geo_bbox)) for x, y in line]
            if len(axis_px) < 2:
                continue
            ring_px = _buffer_polyline_irregular(axis_px, TREEROW_HALF_WIDTH_PX)
            if _polygon_area_px(ring_px) < TREEROW_MIN_AREA_PX2:    # pod ISOM min. mapovatelnou plochou
                continue
            _draw_treerow_area(draw, tdraw, ring_px)
            # px prstenec → mřížka (inverze _grid_to_px: gx = px/W·(GW−1)) pro .omap (týž tvar)
            grid = [(px / W * (GW - 1), py / H * (GH - 1)) for px, py in ring_px]
            area_features.append(([grid], code))    # jeden prsten bez děr → tvar list-ringů (Sez. 54)
            treerows_info.append({"symbol": code, "symbol_name": TREEROW_NAME[code],
                                  "kind": "area", "layer": f["layer"]})
    return area_features, treerows_info


def _draw_predict_areas(draw: ImageDraw.ImageDraw, fdraw: ImageDraw.ImageDraw,
                        areas_sjtsk: list, geo_bbox: tuple) -> tuple[list, list]:
    """Predikční plochy ze SEPARACE reálné mapy (Sez. 83) → ISOM 406/408/410 + 403.

    Reframe (Sez. 79/82): JEDINÝ zdroj predikční vegetace = separace barev z Livelox mapy
    (mapař = GT). Geometrie přichází zvenčí v S-JTSK (orchestrátor `pairs.py` ji vyrobil ze
    separace přes Livelox quad) — žádný fetch. Predikční plochy: zeleň 406/408/410 + 403 Rough
    open (bledá žlutá, Sez. 92) — render/class/název z PREDICT_AREA_*. Provenance = predict
    (ne tvrdá ČÚZK projekce; meta `proxy: true`). `areas_sjtsk` = [(poly [vnější,díra…] v
    S-JTSK, code:int)]. Vrací (area_features [(grid, code)], info) v souřadnicích MŘÍŽKY (zdroj pro .omap)."""
    area_features: list[tuple] = []
    info: list[dict] = []
    for poly, code in areas_sjtsk:
        grid_rings, px_rings = _poly_to_grid_px(poly, geo_bbox)
        if len(px_rings[0]) < 3:
            continue
        # plná výplň bez obrysu (vegetační/open plošný symbol; barva+GT class dle kódu)
        _draw_area_symbol(draw, fdraw, px_rings, PREDICT_AREA_FILL[code], None, PREDICT_AREA_CLASS[code])
        area_features.append((grid_rings, code))
        info.append({"symbol": code, "symbol_name": PREDICT_AREA_NAME[code],
                     "kind": "area", "layer": "separace reálné mapy (predict)"})
    return area_features, info


def _predict_veg_boundaries(class_mask: Image.Image,
                            draw: ImageDraw.ImageDraw, bdraw: ImageDraw.ImageDraw) -> list:
    """Mezitřídní hranice predikčních veg ploch → zvolená varianta ISOM 416 (Sez. 101).

    416 = NEJVĚTŠÍ proporční díra KPI (orig 633 / gen 0). Reálné mapy kreslí ZŘETELNÉ hranice mezi
    oblastmi RŮZNÉ runnability (403↔406↔408↔410) tečkovanou linií. `class_mask` = PREDICT_AREA_CLASS
    rastr (1=410 fight … 4=403, 0=pozadí). Algoritmus (prototyp temp/proto_416, měřeno Sez. 101):
    contour každé třídy (rock_relief) → per-bod prstenu klasifikuj, je-li v okolí JINÁ veg vyšší
    třídy (dedup B>A, ať se hrana A↔B bere jen jednou) → souvislé mezitřídní úseky → DÉLKOVÝ práh
    BOUNDARY_MIN_LEN_M (krátké šumové fragmenty separace odpadnou) → RDP → polyline. Render tečkovaně
    do draw + bdraw maska; vrací [(grid, kód)] pro .omap. Při 416.1 vynechá hranice
    kolem 410 Fight, kde zelenou variantu norma zakazuje. Bez predikční zeleně = []."""
    from rock_relief import _contour_rings, _rdp
    L = np.asarray(class_mask)
    mpp = WORLD_W_M / W                                  # metry na px (render rozlišení)
    min_px = BOUNDARY_MIN_LEN_M / mpp
    rad = max(1, round(BOUNDARY_SAMPLE_M / mpp))
    features: list = []
    for A in sorted(int(v) for v in np.unique(L) if v):
        if ISOM_VEG_BOUNDARY == "416.1" and A == PREDICT_AREA_CLASS[ISOM_VEG_FIGHT]:
            continue
        for ring in _contour_rings(L == A):
            n = len(ring)
            if n < 4:
                continue
            # per-bod prstenu: má okolí JINOU veg vyšší třídy? (dedup B>A → hrana jen jednou)
            flag = np.zeros(n, bool)
            for i, (col, row) in enumerate(ring):
                c0, c1 = max(0, int(col) - rad), min(W, int(col) + rad + 1)
                r0, r1 = max(0, int(row) - rad), min(H, int(row) + rad + 1)
                nb = L[r0:r1, c0:c1]
                if ((nb > A) & (nb != 0)).any():
                    flag[i] = True
            if not flag.any():
                continue
            # souvislé úseky flag=True (cyklicky podél uzavřeného prstenu)
            idx = np.where(flag)[0]
            groups, cur = [], [idx[0]]
            for k in range(1, len(idx)):
                if idx[k] == idx[k - 1] + 1:
                    cur.append(idx[k])
                else:
                    groups.append(cur); cur = [idx[k]]
            groups.append(cur)
            if len(groups) > 1 and idx[0] == 0 and idx[-1] == n - 1:   # cyklický spoj konce a začátku
                groups[0] = groups.pop() + groups[0]
            for g in groups:
                if len(g) < 2:
                    continue
                pts = [ring[j] for j in g]
                ln = sum(((pts[k + 1][0] - pts[k][0]) ** 2 + (pts[k + 1][1] - pts[k][1]) ** 2) ** 0.5
                         for k in range(len(pts) - 1))
                if ln < min_px:                          # krátký šumový fragment → zahoď
                    continue
                simp = _rdp(np.asarray(pts, float), 1.5)
                if len(simp) < 2:
                    continue
                px = [(float(x), float(y)) for x, y in simp]
                _draw_boundary(draw, bdraw, px, ISOM_VEG_BOUNDARY)
                grid = [(x / W * (GW - 1), y / H * (GH - 1)) for x, y in simp]
                features.append((grid, ISOM_VEG_BOUNDARY))
    return features


def _generate_real_rocks(draw: ImageDraw.ImageDraw, rdraw: ImageDraw.ImageDraw,
                         lat: float, lon: float,
                         geo_bbox: tuple) -> tuple[list, list, list]:
    """Reálné skály a balvany (real-půlka, Sez. 30 + 57 + 63): 204/207/208 ze ZABAGED, 206 z DMR sklonu.

      Osamělý_balvan__skála__skalní_suk  → 204 Boulder            (bod ZABAGED, plný černý kruh)
      Skupina_balvanů__bod_              → 207 Boulder cluster    (bod ZABAGED, plný černý trojúhelník)
      **plocha 206 Gigantic boulder = DMR 5G SKLON** (Sez. 63, `rock_relief.detect_rock_areas`) —
        nahradilo generalizovaný ZABAGED `Skalní_útvary` (jeden blob → věrná členitost věží/průchodů)
      Skupina_balvanů__linie_            → 208 Boulder field      (linie ZABAGED → pás trojúhelníků, Sez. 57)

    Smoothing polygonů (původní A2) i hybridní 202/206 podle plochy (zvažováno Q2) ZAVRŽENO
    uživatelem v průběhu sezení: ZABAGED polygony jsou už dost detailní (~120 vrcholů na 32×32 m
    polygon → plynulý obrys), a hybridní rozhodování nemělo datový podklad (vrstva nese jen
    `jmeno`, žádný typ/výška). Drift po stěně argumentů → KISS jedno mapování per vrstva.

    Vrací (rock_point_features [(gx, gy, code)], rock_area_features [(grid_ring, code)], rocks_info).
    Body a plochy oddělené (paralela s vodou: line_features / area_features) — .omap export
    je řeší různými objekty (point_object vs area)."""
    from zabaged import (fetch_boulders, fetch_boulder_clusters,
                         fetch_boulder_field_lines, map_boulder_to_isom,
                         map_boulder_cluster_to_isom, map_boulder_field_to_isom)
    from rock_relief import detect_rock_areas    # 206 plocha z DMR sklonu (Sez. 63, nahradila ZABAGED Skalní_útvary)

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

    # 3) Skalní útvary (plocha) → 206 Gigantic boulder. ZDROJ = DMR 5G SKLON (Sez. 63), ne ZABAGED:
    #    ZABAGED `Skalní_útvary` je generalizovaný blok přes celý masiv; DMR sklon dá věrnou členitost
    #    (jednotlivé věže + otevřené průchody). Deterministická projekce z výškopisu (jako vrstevnice/
    #    form lines), NE proxy. Vrací polygony [outer, díra…] v S-JTSK → týž tok jako dřív (raw, díry).
    code = ISOM_GIGANTIC_BOULDER
    for poly in detect_rock_areas(lat, lon, geo_bbox, GW, GH, TILE_M):
        grid_rings, px_rings = _poly_to_grid_px(poly, geo_bbox)
        if len(px_rings[0]) < 3:
            continue
        _draw_gigantic_boulder(draw, rdraw, px_rings)
        rock_area_features.append((grid_rings, code))
        rocks_info.append({"symbol": code, "symbol_name": ROCK_NAME[code], "kind": "area",
                           "layer": "DMR rock relief (sklon)"})

    # 4) Pole balvanů (linie) → 208 Boulder field. Osa → buffer na úzký pás (mirror stromořadí 406,
    #    Sez. 45) → vyplnit náhodnými trojúhelníky. Velmi krátké pásy (pod ISOM min. plochou) zahodit.
    for f in fetch_boulder_field_lines(lat, lon, GW, GH, TILE_M):
        code = map_boulder_field_to_isom(f["layer"], f["props"])
        for line in f["lines"]:
            axis_px = [_grid_to_px(*_sjtsk_to_grid(x, y, geo_bbox)) for x, y in line]
            if len(axis_px) < 2:
                continue
            ring_px = _buffer_polyline_irregular(axis_px, BOULDER_FIELD_HALF_WIDTH_PX)
            if _polygon_area_px(ring_px) < BOULDER_FIELD_MIN_AREA_PX2:    # pod ISOM min. plochou
                continue
            _draw_boulder_field_area(draw, rdraw, ring_px)
            # px prstenec → mřížka (inverze _grid_to_px) pro .omap (týž tvar jako rastr; jako 406 Sez. 45)
            grid = [(px / W * (GW - 1), py / H * (GH - 1)) for px, py in ring_px]
            rock_area_features.append(([grid], code))
            rocks_info.append({"symbol": code, "symbol_name": ROCK_NAME[code], "kind": "area",
                               "layer": f["layer"]})

    return rock_point_features, rock_area_features, rocks_info


def _rasterize_water_grid(water_area_features: list | None) -> "np.ndarray | None":
    """Rasterizuj vodní plochy (301) na grid (GH,GW) → bool maska (True=voda); None když žádná voda.

    Outer ring = voda; holes (ostrovy v rybníce, prvky [1:]) = souš (vyrazí se zpět na False).
    Sdílí grid-rings formát s rock/water area features (Sez. 113)."""
    if not water_area_features:
        return None
    wseed = Image.new("L", (GW, GH), 0)
    wdraw = ImageDraw.Draw(wseed)
    for grid_rings, _code in water_area_features:
        if grid_rings and len(grid_rings[0]) >= 3:
            wdraw.polygon([(gx, gy) for gx, gy in grid_rings[0]], fill=1)    # outer = voda
        for hole in grid_rings[1:]:                                          # holes = ostrovy → souš
            if len(hole) >= 3:
                wdraw.polygon([(gx, gy) for gx, gy in hole], fill=0)
    arr = np.asarray(wseed, dtype=bool)
    return arr if arr.any() else None


def _build_forbid_px(forbid_imgs: list | None, dilate_px: int) -> "np.ndarray | None":
    """Sjednoť GT masky (budovy/cesty/zpevněné, px W×H „L") → jedna bool PX maska zakázaných míst,
    dilatovaná o poloměr symbolu (aby se ani OKRAJ bodu nedotkl prvku).

    PX rozlišení záměrně (NE grid jako voda/skály): cesty 502-506 a zpevněné 501 pásy jsou TENKÉ (pár px)
    → na hrubém gridu by zmizely a body by na ně padly částečně zakryté (Sez. 136 nález uživatele — kameny
    i 417/419 na 501 pásech podél cest). None = nic k vyloučení."""
    if not forbid_imgs:
        return None
    import scipy.ndimage as ndi
    acc = None
    for img in forbid_imgs:
        a = np.asarray(img) > 0                            # multi-class „L" maska: >0 = prvek
        acc = a if acc is None else (acc | a)
    if acc is None or not acc.any():
        return None
    if dilate_px > 0:
        acc = ndi.binary_dilation(acc, iterations=int(dilate_px))
    return acc


def _clip_fences_off_water(fence_features: list, water_area_features: list | None) -> list:
    """Vyřízni úseky plotu 516 nad vodní plochou (301) — plot na hladině = nesmysl (Sez. 113 Nová Louka).

    Surfaces (a tím fence) se generují PŘED vodou (z-order: pokryv vespod), takže vodní masku známe
    až teď. Rastr je OK (voda kreslí NAD plotem → překryje ho), filtrujeme jen .omap features:
    plot rozdělíme na souvislé úseky bodů MIMO vodu (úsek < 2 body zahodíme → plot u břehu prostě končí)."""
    water_cell = _rasterize_water_grid(water_area_features)
    if water_cell is None:
        return fence_features
    gh, gw = water_cell.shape                              # (GH, GW)

    def _wet(gx: float, gy: float) -> bool:
        c, r = int(round(gx)), int(round(gy))
        return bool(water_cell[r, c]) if (0 <= r < gh and 0 <= c < gw) else False

    out: list = []
    for grid, code in fence_features:
        run: list = []
        for gx, gy in grid:
            if _wet(gx, gy):
                if len(run) >= 2:
                    out.append((run, code))
                run = []
            else:
                run.append((gx, gy))
        if len(run) >= 2:
            out.append((run, code))
    return out


def _generate_pseudo_boulders(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                              rock_point_features: list, rock_area_features: list,
                              rng: np.random.Generator,
                              water_area_features: list | None = None,
                              forbid_imgs: list | None = None) -> list[tuple]:
    """Pseudo injekce bodů 204 Boulder + 210 Stony ground (FÁZE 2, Sez. 107).

    ZABAGED tyto body nevede v reálné hustotě (kompas: 204 gen 3/orig 1064, 210 gen 0/orig 975) →
    bodové sub-KPI zaostává. Dosypeme je na KONTEXTOVOU MASKU = DOLOŽENÁ SKALNATOST (volba uživatele
    „věrná distribuce" Sez. 107): 206 skalní plochy (z DMR sklonu, rock_area_features) + reálné ZABAGED
    204/207 body (rock_point_features), dilatováno o PSEUDO_ROCK_DILATE_M (suť/balvany vyzařují z stěn).
    Obecný sklon byl ZAVRŽEN (Sez. 107): svažitá-ale-neskalnatá mapa přestřelila body. NENÍ projekce
    dat (poloha v rámci masky náhodná, reframe Sez. 79), ale maska koreluje s reálnou skalnatostí mapy.

    rock_point_features — REÁLNÉ [(gx, gy, code)] (204/207) ze ZABAGED (před přidáním pseudo).
    rock_area_features  — [(grid_rings, code)] (206 plochy z DMR + 208 pole) — bereme jen 206 jako seed.
    water_area_features — [(grid_rings, code)] vodní plochy (301) — VYLOUČENY z masky i z 210 teček
                          (balvan na hladině = nesmysl, Sez. 113 Nová Louka). Outer = voda, holes (ostrovy) = souš.
    forbid_imgs         — GT masky budovy/cesty/zpevněné (px) → kámen NEumístit na 501 pás podél cesty
                          (Sez. 136 nález uživatele {A} Soví vrch: kameny pod cestou zakryté). PX rozlišení.
    Vrací pseudo point_features [(gx, gy, code)] (204 + 210.1); render + maska = side-effect.
    """
    import scipy.ndimage as ndi                          # dilatace masky (jako rock_relief)
    # --- maska doložené skalnatosti na grid úrovni (GH,GW) ---
    seed = Image.new("L", (GW, GH), 0)                    # 1 = skalnatý kontext
    sdraw = ImageDraw.Draw(seed)
    for grid_rings, code in rock_area_features:
        if int(float(code)) == ISOM_GIGANTIC_BOULDER:     # jen 206 (ne 208 pole — to je samo bodová textura)
            outer = grid_rings[0]
            if len(outer) >= 3:
                sdraw.polygon([(gx, gy) for gx, gy in outer], fill=1)
    for gx, gy, code in rock_point_features:              # reálné 204/207 = seedy
        sdraw.point((int(round(gx)), int(round(gy))), fill=1)
    mask = np.asarray(seed, dtype=bool)
    if not mask.any():
        return []                                         # žádná doložená skalnatost → žádné body (správně)
    # dilatace o okolí (skalnatost vyzařuje — suť pod stěnami, rozptýlené balvany)
    r_cells = max(1, round(PSEUDO_ROCK_DILATE_M / M_PER_CELL))
    mask = ndi.binary_dilation(mask, iterations=r_cells)
    # voda VEN z masky (balvan na hladině = nesmysl) — rasterizuj 301 plochy na grid, outer=voda, holes=souš
    water_cell = _rasterize_water_grid(water_area_features)
    if water_cell is not None:
        mask &= ~water_cell
        if not mask.any():
            return []                                     # celá skalnatost ležela na vodě
    cand = np.argwhere(mask)                              # [(řádek=gy, sloupec=gx)] kandidátní buňky

    area_km2 = len(cand) * (M_PER_CELL / 1000.0) ** 2     # plocha masky [km²]
    pts: list[tuple[float, float, str]] = []

    def _rand_cell_grid() -> tuple[float, float]:
        """Náhodná buňka z masky + jitter uvnitř buňky → (gx, gy) v grid souřadnicích."""
        gy_c, gx_c = cand[rng.integers(len(cand))]
        return gx_c + rng.uniform(-0.5, 0.5), gy_c + rng.uniform(-0.5, 0.5)

    # px maska budovy/cesty/zpevněné, dilatovaná o poloměr kamene → kámen ani okrajem na 501/cestu (Sez. 136)
    forbid_px = _build_forbid_px(forbid_imgs, dilate_px=BOULDER_RADIUS_PX + 1)
    fh, fw = (forbid_px.shape if forbid_px is not None else (0, 0))

    def _forbidden(px: float, py: float) -> bool:
        """True = px pozice leží na budově/cestě/zpevněné (kde se kámen zakryje)."""
        ix, iy = int(px), int(py)
        return forbid_px is not None and 0 <= iy < fh and 0 <= ix < fw and bool(forbid_px[iy, ix])

    # 204 Boulder — jednotlivé kruhy rozseté po masce
    n_boulder = round(area_km2 * PSEUDO_BOULDER_PER_KM2)
    for _ in range(n_boulder):
        gx, gy = _rand_cell_grid()
        px, py = _grid_to_px(gx, gy)
        if _forbidden(px, py):                          # kámen na budově/cestě/zpevněné → přeskoč (Sez. 136)
            continue
        _draw_boulder(draw, mdraw, px, py)
        pts.append((gx, gy, str(ISOM_BOULDER)))         # "204"

    # 210 Stony ground — POLE teček (každá tečka = samostatný bodový objekt 210.1, nález Sez. 96/106).
    # Elipsovitá oblast vyplněná tečkami na jittered gridu (rozestup spec 1,2 mm) — mirror inject._sample_field.
    # Pozn.: poloosy užší (3–8 teček) než inject trénink (3–12) ZÁMĚRNĚ — gen pole laděna na share/KPI (Sez. 107),
    # inject na Png2Point trénink; nejsou ve stejném páru, takže divergence je v pořádku (neslučovat naslepo, mění KPI).
    n_fields = round(area_km2 * PSEUDO_STONY_FIELD_PER_KM2)
    sp = PSEUDO_STONY_DOT_SPACING_PX
    for _ in range(n_fields):
        gx0, gy0 = _rand_cell_grid()
        ox, oy = _grid_to_px(gx0, gy0)                  # střed pole v px
        rx = rng.uniform(3, 8) * sp                     # poloosa pole (3–8 teček napříč)
        ry = rng.uniform(3, 8) * sp
        gy_px = oy - ry
        while gy_px <= oy + ry:
            gx_px = ox - rx
            while gx_px <= ox + rx:
                jx = gx_px + rng.uniform(-0.3, 0.3) * sp
                jy = gy_px + rng.uniform(-0.3, 0.3) * sp
                # tečku polož jen uvnitř elipsy a uvnitř plátna
                if ((jx - ox) / rx) ** 2 + ((jy - oy) / ry) ** 2 <= 1.0 and 0 <= jx < W and 0 <= jy < H:
                    # px → grid pro .omap (inverze _grid_to_px, jako 208/406 Sez. 45/57)
                    ggx, ggy = jx / W * (GW - 1), jy / H * (GH - 1)
                    # elipsa pole může přesáhnout přes břeh — vynech tečky na vodě (Sez. 113)
                    if water_cell is not None and water_cell[int(round(ggy)), int(round(ggx))]:
                        gx_px += sp
                        continue
                    if _forbidden(jx, jy):              # tečka na budově/cestě/zpevněné → přeskoč (Sez. 136)
                        gx_px += sp
                        continue
                    _draw_stony_dot(draw, mdraw, jx, jy)
                    pts.append((ggx, ggy, "210.1"))
                gx_px += sp
            gy_px += sp
    return pts


def _generate_pseudo_veg_points(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                                rock_area_features: list,
                                water_area_features: list | None, n_real_417: int,
                                rng: np.random.Generator,
                                forbid_imgs: list | None = None) -> list[tuple]:
    """Pseudo injekce bodů 417 Prominent large tree + 419 Prom. vegetation feature + 418 Prom. bush
    or tree (FÁZE 2, Sez. 136; 418 přidán Sez. 137).

    Princip kamenů (Sez. 107): 417 má jen ŘÍDKÝ doložený zdroj (ZABAGED Významný strom, ~3 % reálné
    hustoty), 418/419 žádný → dosypeme na reálnou MĚŘENOU hustotu (kartografovy .omap / eval_real GT:
    medián 417 ~27/km², 419 ~18/km², 418 ~18/km²; losováno per mapa pro rozmanitost). NENÍ projekce dat
    — poloha v rámci masky náhodná (reframe Sez. 79), maska jen vylučuje nemožná místa.

    Umístění (volba uživatele): MIMO vodu (no-draw zóna, CLAUDE.md) + MIMO hustou skalnatost (strom
    neroste v balvanitém poli) + MIMO budovy/cesty/zpevněné plochy (Sez. 136 nález — symbol pod liniovým/
    plošným prvkem se zakryje). Skalní maska = 206 plochy z DMR sklonu (rock_relief, Sez. 63), dilatované.
    Budovy/cesty/zpevněné se berou z hotových GT masek (forbid_imgs, px → grid).

    ISOM rozestup (Sez. 136, nález uživatele {A}): bodové symboly se NESMÍ překrývat → rejection sampling,
    nový bod zahozen, pokud je blíž než (r_a + r_b + mezera) ke kterémukoli už umístěnému.

    rock_area_features  — [(grid_rings, code)] (206 plochy + 208) — seed skalní masky (bere jen 206).
    water_area_features — vodní plochy 301 (vyloučeny z masky).
    n_real_417          — počet reálných ZABAGED 417 už nakreslených → odečte se od pseudo cíle (DOPLNĚNÍ
                          na hustotu, ne zdvojení). 419 reálné nemá → plná pseudo hustota.
    forbid_imgs         — list PIL „L" GT masek (budovy/cesty/zpevněné, px W×H; 0 = pozadí) → resamplují
                          se na grid a vyloučí (None/prázdné = nic navíc nevyloučit).
    mdraw = GT maska landmarků (LANDMARK_CLASS); render = side-effect do draw (rgb) + mdraw.
    Vrací pseudo point_features [(gx, gy, code)] (417 + 418 + 419).
    """
    import scipy.ndimage as ndi
    # --- skalní maska = 206 plochy (z DMR sklonu), dilatovaná o okolí (suť kolem stěn) ---
    rock = Image.new("L", (GW, GH), 0)
    rdraw = ImageDraw.Draw(rock)
    for grid_rings, code in rock_area_features:
        if int(float(code)) == ISOM_GIGANTIC_BOULDER and len(grid_rings[0]) >= 3:
            rdraw.polygon([(gx, gy) for gx, gy in grid_rings[0]], fill=1)
    rock_mask = np.asarray(rock, dtype=bool)
    if rock_mask.any():
        rock_mask = ndi.binary_dilation(rock_mask, iterations=max(1, round(PSEUDO_ROCK_DILATE_M / M_PER_CELL)))
    # --- kandidátní maska = CELÉ pole MINUS skály MINUS voda MINUS budovy/cesty/zpevněné ---
    mask = ~rock_mask                                     # bool (GH,GW), True = lze umístit
    water_cell = _rasterize_water_grid(water_area_features)
    if water_cell is not None:
        mask &= ~water_cell
    cand = np.argwhere(mask)                              # [(gy, gx)] kandidátní buňky (mimo vodu/skály)
    if not len(cand):
        return []                                         # celé pole zakázané (nemělo by nastat)
    area_km2 = len(cand) * (M_PER_CELL / 1000.0) ** 2

    def _rand_cell_grid() -> tuple[float, float]:
        """Náhodná buňka z masky + jitter uvnitř buňky → (gx, gy) v grid souřadnicích."""
        gy_c, gx_c = cand[rng.integers(len(cand))]
        return gx_c + rng.uniform(-0.5, 0.5), gy_c + rng.uniform(-0.5, 0.5)

    gap_px = PSEUDO_VEG_MIN_GAP_MM * PX_PER_MM
    r_of = {ISOM_LARGE_TREE: float(LANDMARK_TREE_R_PX), ISOM_VEG_FEATURE: float(LANDMARK_VEGFEAT_R_PX),
            ISOM_PROM_BUSH: float(LANDMARK_BUSH_R_PX)}
    # px maska budov/cest/zpevněných, dilatovaná o poloměr → ani OKRAJ symbolu se nedotkne tenkého pásu
    forbid_px = _build_forbid_px(forbid_imgs, dilate_px=round(max(r_of.values()) + gap_px))
    fh, fw = (forbid_px.shape if forbid_px is not None else (0, 0))
    # hustota losovaná per mapa z rozsahu; 417 = doplnit na cíl MÍNUS reálné ZABAGED (max 0 = už dost),
    # 418/419 = čistě pseudo (ZABAGED zdroj nemají) → plná losovaná hustota
    n_tree = max(0, round(area_km2 * rng.uniform(*PSEUDO_TREE_PER_KM2)) - n_real_417)
    n_veg = round(area_km2 * rng.uniform(*PSEUDO_VEGFEAT_PER_KM2))
    n_bush = round(area_km2 * rng.uniform(*PSEUDO_BUSH_PER_KM2))
    # rejection sampling: drž px pozice + poloměry umístěných (rostoucí numpy buffer)
    placed_xy: list[tuple[float, float]] = []
    placed_r: list[float] = []
    pts: list[tuple[float, float, str]] = []
    for code, n in ((ISOM_LARGE_TREE, n_tree), (ISOM_VEG_FEATURE, n_veg), (ISOM_PROM_BUSH, n_bush)):
        r_new = r_of[code]
        placed = attempts = 0
        budget = n * 25 + 50                             # strop pokusů (plná mapa → část se zahodí, OK)
        while placed < n and attempts < budget:
            attempts += 1
            gx, gy = _rand_cell_grid()
            px, py = _grid_to_px(gx, gy)
            ix, iy = int(px), int(py)
            # mimo budovy/cesty/zpevněné (px rozlišení — zachytí i tenké 501/cesty pásy, Sez. 136)
            if forbid_px is not None and 0 <= iy < fh and 0 <= ix < fw and forbid_px[iy, ix]:
                continue
            if placed_xy:                                 # min. vzdálenost středů ≥ r_a+r_b+mezera (žádný překryv)
                pxy = np.asarray(placed_xy)
                d2 = (pxy[:, 0] - px) ** 2 + (pxy[:, 1] - py) ** 2
                if (d2 < (np.asarray(placed_r) + r_new + gap_px) ** 2).any():
                    continue
            _draw_landmark(draw, mdraw, px, py, code)
            pts.append((gx, gy, str(code)))
            placed_xy.append((px, py))
            placed_r.append(r_new)
            placed += 1
    return pts


# =====================================================================
#  Mosty / tunely / lávky — fáze 1 (projekce reálných dat ZABAGED), Sez. 32 spec-driven
# =====================================================================
def _cum_distance_px(line_grid: list[tuple[float, float]]) -> list[float]:
    """Kumulativní vzdálenost bodů line_grid v paper-space (px). Pro mapování bod → d."""
    line_px = [_grid_to_px(gx, gy) for gx, gy in line_grid]
    cum = [0.0]
    for i in range(1, len(line_px)):
        cum.append(cum[-1] + math.hypot(line_px[i][0] - line_px[i - 1][0],
                                         line_px[i][1] - line_px[i - 1][1]))
    return cum


# Half-width pásu, v němž se křížící linie pod mostem přeruší (KOLMO od osy mostu):
# 0,75 mm (offset paralely 512, viz omap_export.BRIDGE_PARALLEL_OFFSET_UM) + 0,5 mm
# „za závorkami" (uživatel, verify Most.omap Sez. 33). Mimo tento pás linie pokračuje.
BRIDGE_CROP_HALFWIDTH_MM = 1.25
# Úsek křížící linie ~rovnoběžný s osou mostu (úhel < tohoto) = NESENÁ trať (jde PO mostě,
# nahoře, viditelná) → necropovat. Jen příčné úseky (pod mostem) se přeruší.
BRIDGE_CARRIED_PARALLEL_DEG = 25.0


def _point_on_line_px(line_px: list[tuple[float, float]], cum: list[float],
                      d: float) -> tuple[float, float, float, float]:
    """Bod (x,y) + jednotková tangenta (tx,ty) linie v kumulativní vzdálenosti d [px]."""
    for i in range(1, len(cum)):
        if d <= cum[i] or i == len(cum) - 1:
            seg = cum[i] - cum[i - 1]
            f = 0.0 if seg < 1e-9 else (d - cum[i - 1]) / seg
            x = line_px[i - 1][0] + f * (line_px[i][0] - line_px[i - 1][0])
            y = line_px[i - 1][1] + f * (line_px[i][1] - line_px[i - 1][1])
            tx, ty = line_px[i][0] - line_px[i - 1][0], line_px[i][1] - line_px[i - 1][1]
            tlen = math.hypot(tx, ty) or 1.0
            return x, y, tx / tlen, ty / tlen
    return line_px[-1][0], line_px[-1][1], 1.0, 0.0


def _interp_grid_at(line_grid: list[tuple[float, float]], cum: list[float],
                    d: float) -> tuple[float, float]:
    """Interpolovaný grid bod na kumulativní vzdálenosti d [px] (přesný okraj cutu)."""
    for i in range(1, len(cum)):
        if d <= cum[i] or i == len(cum) - 1:
            seg = cum[i] - cum[i - 1]
            f = 0.0 if seg < 1e-9 else (d - cum[i - 1]) / seg
            return (line_grid[i - 1][0] + f * (line_grid[i][0] - line_grid[i - 1][0]),
                    line_grid[i - 1][1] + f * (line_grid[i][1] - line_grid[i - 1][1]))
    return line_grid[-1]


def _crop_line_under_bridge(line_grid: list[tuple[float, float]],
                            cutter_lines_grid: list[list[tuple[float, float]]],
                            half_w_mm: float = BRIDGE_CROP_HALFWIDTH_MM,
                            parallel_deg: float = BRIDGE_CARRIED_PARALLEL_DEG
                            ) -> list[list[tuple[float, float]]]:
    """Most crop (verify Most.omap, Sez. 33): křížící linie pod mostem se PŘERUŠÍ v pásu
    ±half_w_mm KOLMO od osy mostu. Nahrazuje dřívější crossing strategii (bod-průsečíky,
    >2 → ignore), která selhávala na ZABAGED noise a cropovala jen ±0,5 mm kolem průsečíku
    (linie vykukovala zpod závorek 512 v 0,75 mm).

    Úhlový filtr: úsek ~rovnoběžný s osou mostu (úhel < parallel_deg) = NESENÁ trať (jde
    PO mostě, nahoře viditelná, jako oranžová silnice v Most.png) → NEcropovat. Jen příčné
    úseky (pod mostem = voda/jiná cesta/železnice) se přeruší. Robustní vůči počtu průsečíků.

    Použít pro: voda/cesty × mosty. (Tunely mají opačný filtr → `_crop_line_at_passages`.)"""
    if not cutter_lines_grid or len(line_grid) < 2:
        return [line_grid] if len(line_grid) >= 2 else []
    line_px = [_grid_to_px(gx, gy) for gx, gy in line_grid]
    cutters_px = [[_grid_to_px(gx, gy) for gx, gy in cl]
                  for cl in cutter_lines_grid if len(cl) >= 2]
    if not cutters_px:
        return [line_grid]
    cum = _cum_distance_px(line_grid)
    total = cum[-1]
    half_w_px = half_w_mm * PX_PER_MM
    cos_par = math.cos(math.radians(parallel_deg))
    step = 0.2 * PX_PER_MM                          # vzorkovací krok podél linie (~0,2 mm)
    # 1) vzorkuj podél linie → souvislé „inside" intervaly (perp < half_w AND příčný)
    zones: list[tuple[float, float]] = []
    in_zone, z_start, d = False, 0.0, 0.0
    while d <= total + 1e-9:
        x, y, tx, ty = _point_on_line_px(line_px, cum, min(d, total))
        ux, uy, dist = _nearest_seg(x, y, cutters_px)
        inside = dist < half_w_px and abs(tx * ux + ty * uy) <= cos_par
        if inside and not in_zone:
            in_zone, z_start = True, d
        elif not inside and in_zone:
            in_zone = False
            zones.append((z_start, d))
        d += step
    if in_zone:
        zones.append((z_start, total))
    return _split_by_zones_interp(line_grid, cum, zones)


def _split_by_zones_interp(line_grid: list[tuple[float, float]], cum: list[float],
                           zones: list[tuple[float, float]]
                           ) -> list[list[tuple[float, float]]]:
    """Rozdělí line_grid podle cut zón (cum px intervaly) s INTERPOLOVANÝMI hraničními body
    na okrajích zón (mezera nevykukuje ani nepřesahuje u řídkých linií). Sdílí most i tunel."""
    if not zones:
        return [line_grid] if len(line_grid) >= 2 else []
    zones = sorted(zones)
    merged = [zones[0]]
    for z in zones[1:]:
        if z[0] <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], z[1]))
        else:
            merged.append(z)
    pts = [(cum[k], line_grid[k]) for k in range(len(line_grid))]
    for a, b in merged:
        pts.append((a, _interp_grid_at(line_grid, cum, a)))
        pts.append((b, _interp_grid_at(line_grid, cum, b)))
    pts.sort(key=lambda p: p[0])
    EPS = 1e-6
    segments: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    for dd, gp in pts:
        if any(a + EPS < dd < b - EPS for a, b in merged):     # striktně vnitřní bod → vypustit
            if len(cur) >= 2:
                segments.append(cur)
            cur = []
        else:
            cur.append(gp)
    if len(cur) >= 2:
        segments.append(cur)
    return segments


def _project_to_line(tx: float, ty: float, line_px: list[tuple[float, float]],
                     cum: list[float]) -> tuple[float, float]:
    """Projekce bodu (tx,ty) na polyline → (kumulativní vzdálenost projekce [px], vzdálenost
    bodu od linie [px]). Přesný bod na úsečce (ne nejbližší vrchol)."""
    best_d2, best_cum = float("inf"), 0.0
    for i in range(1, len(line_px)):
        x0, y0 = line_px[i - 1]
        x1, y1 = line_px[i]
        dx, dy = x1 - x0, y1 - y0
        seg2 = dx * dx + dy * dy
        if seg2 == 0.0:
            continue
        t = max(0.0, min(1.0, ((tx - x0) * dx + (ty - y0) * dy) / seg2))
        cx, cy = x0 + t * dx, y0 + t * dy
        d2 = (tx - cx) ** 2 + (ty - cy) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_cum = cum[i - 1] + t * math.hypot(dx, dy)
    return best_cum, math.sqrt(best_d2)


def _crop_line_at_passages(line_grid: list[tuple[float, float]],
                           cutter_lines_grid: list[list[tuple[float, float]]],
                           near_mm: float = 2.0,
                           crop_mm: float = 0.5
                           ) -> list[list[tuple[float, float]]]:
    """Passage strategy (pro tunel cutter): trať PROCHÁZEJÍCÍ tunelem se přeruší. Vjezdy
    (konce tunel osy) se PROJEKTUJÍ přesně na trať (Sez. 33 fix: dřív snap na nejbližší
    vrchol ustřihával až ~4 mm před vjezd místo crop_mm). Cut zóna = mezi projekcemi vjezdů
    + crop_mm za každý vjezd (= trať viditelná až crop_mm před vstup, mezera celým tunelem).

    `near_mm` = max vzdálenost vjezdu od trati (zda trať tunelem prochází). Použít pro:
    železnice/silnice × tunely. Interpolovaný okraj (jako most) → přesná mezera."""
    if not cutter_lines_grid or len(line_grid) < 2:
        return [line_grid] if len(line_grid) >= 2 else []
    line_px = [_grid_to_px(gx, gy) for gx, gy in line_grid]
    cum = _cum_distance_px(line_grid)
    crop_px = crop_mm * PX_PER_MM
    near_px = near_mm * PX_PER_MM
    zones: list[tuple[float, float]] = []
    for cl in cutter_lines_grid:
        if len(cl) < 2:
            continue
        s_px = _grid_to_px(cl[0][0], cl[0][1])
        e_px = _grid_to_px(cl[-1][0], cl[-1][1])
        d_s, dist_s = _project_to_line(s_px[0], s_px[1], line_px, cum)
        d_e, dist_e = _project_to_line(e_px[0], e_px[1], line_px, cum)
        if dist_s > near_px or dist_e > near_px:
            continue                                # trať tunelem neprochází
        lo, hi = min(d_s, d_e), max(d_s, d_e)
        if hi - lo < 1e-6:
            continue
        zones.append((lo - crop_px, hi + crop_px))
    return _split_by_zones_interp(line_grid, cum, zones)


def _nearest_segment_tangent(bx: float, by: float,
                             lines_px: list[list[tuple[float, float]]]
                             ) -> tuple[float, float] | None:
    """Jednotková tangenta nejbližšího segmentu v `lines_px` k bodu (bx, by), nebo None.

    Tenký wrapper nad `_nearest_seg` (DRY — tatáž iterace segmentů + projekce na úsečku, Sez. 41):
    liší se jen okrajem — vrací None, když ve `lines_px` není ani jeden segment (≥2 body), aby
    volající (orientace bodové lávky kolmo k toku) poznal „žádný tok pod sebou" a sáhl po fallbacku
    rot=0; `_nearest_seg` by tam vrátil neutrální (1,0). Jinak deleguje."""
    if not any(len(line) >= 2 for line in lines_px):
        return None
    ux, uy, _ = _nearest_seg(bx, by, lines_px)
    return ux, uy


def _fetch_bridges_tunnels_geometries(lat: float, lon: float, geo_bbox: tuple
                                       ) -> tuple[list, list, list, list]:
    """Pre-fetch fáze (Sez. 32 E1+E4): stáhne mosty/tunely/lávky ze ZABAGEDu, vrátí JEN
    GEOMETRIE (žádné kreslení). Generator pak může z těchto grid linií udělat cutter pole
    pro `_generate_real_paths/_water/_railways`, které cropují průchozí vrstvy.

    Vrací 4-tici (volaný před vodou/cestami/železnicí):
      - bridge_grids: [grid_polyline] — všechny mosty
      - tunnel_grids: [grid_polyline] — všechny tunely
      - footbridge_lines_data: [(grid_polyline, layer, jmeno)] — pro pozdější render lávek
      - footbridge_points_data: [(x_sjtsk, y_sjtsk)] — surové body lávek (rotace zatím nevíme)
    """
    from zabaged import fetch_bridges, fetch_tunnels, fetch_footbridges
    bridge_grids: list = []
    tunnel_grids: list = []
    footbridge_lines_data: list = []
    for f in fetch_bridges(lat, lon, GW, GH, TILE_M):
        for line in f["lines"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            if len(grid) >= 2:
                bridge_grids.append(grid)
    for f in fetch_tunnels(lat, lon, GW, GH, TILE_M):
        for line in f["lines"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            if len(grid) >= 2:
                tunnel_grids.append(grid)
    line_feats, points = fetch_footbridges(lat, lon, GW, GH, TILE_M)
    for f in line_feats:
        for line in f["lines"]:
            grid = [_sjtsk_to_grid(x, y, geo_bbox) for x, y in line]
            if len(grid) >= 2:
                footbridge_lines_data.append((grid, f["layer"], f["props"].get("jmeno")))
    footbridge_points_data = list(points)
    return bridge_grids, tunnel_grids, footbridge_lines_data, footbridge_points_data


def _render_bridges_tunnels(draw: ImageDraw.ImageDraw, mdraw: ImageDraw.ImageDraw,
                             bridge_grids: list, tunnel_grids: list,
                             footbridge_lines_data: list, footbridge_points_data: list,
                             geo_bbox: tuple,
                             water_lines_px: list[list[tuple[float, float]]]
                             ) -> tuple[list, list, list, list]:
    """Render fáze (Sez. 32): kreslí závorky mostů + tunelů + lávky do rastru, vrátí
    features pro .omap export + info. Volá se PO všech ostatních vrstvách (z-order).

    Vrací (bridge_features, tunnel_features, footbridge_features, info):
      - bridge_features: [(grid, 512)] — mosty pro .omap (line objekt 512)
      - tunnel_features: [(grid, 512)] — tunely pro .omap (NEemit jako line, omap_export to
        zpracuje jako 2× point 512.2 na koncích — to dělá generate_map)
      - footbridge_features: [(gx, gy, 5122, rot)] — lávky bodové+liniové pro .omap
      - info: souhrn pro meta.json
    """
    from zabaged import map_bridge_to_isom, map_tunnel_to_isom, map_footbridge_to_isom

    bridge_features: list[tuple] = []
    tunnel_features: list[tuple] = []
    footbridge_features: list[tuple] = []
    info: list[dict] = []

    code_b = map_bridge_to_isom("Most", {})
    code_t = map_tunnel_to_isom("Tunel", {})
    code_fb = map_footbridge_to_isom("Lávka (bod)", {})

    for grid in bridge_grids:
        px = [_grid_to_px(gx, gy) for gx, gy in grid]
        _draw_bridge(draw, mdraw, px)
        bridge_features.append((grid, code_b))
        info.append({"symbol": code_b, "kind": "bridge", "layer": "Most"})

    for grid in tunnel_grids:
        px = [_grid_to_px(gx, gy) for gx, gy in grid]
        _draw_tunnel(draw, mdraw, px)
        tunnel_features.append((grid, code_t))
        info.append({"symbol": code_t, "kind": "tunnel", "layer": "Tunel"})

    # Lávky linie: čárka uprostřed osy, rovnoběžná s osou lávky
    for grid, layer, jmeno in footbridge_lines_data:
        px = [_grid_to_px(gx, gy) for gx, gy in grid]
        if len(px) < 2:
            continue
        mid_i = len(px) // 2
        cx, cy = px[mid_i]
        prev_i = max(0, mid_i - 1)
        next_i = min(len(px) - 1, mid_i + 1)
        dx = px[next_i][0] - px[prev_i][0]
        dy = px[next_i][1] - px[prev_i][1]
        rot = math.atan2(dy, dx)
        _draw_footbridge(draw, mdraw, cx, cy, rot)
        gx_mid, gy_mid = grid[mid_i]
        footbridge_features.append((gx_mid, gy_mid, code_fb, rot))
        info.append({"symbol": code_fb, "kind": "footbridge_line",
                     "layer": layer, "jmeno": jmeno})

    # Lávky body: rotace kolmá k nejbližšímu toku
    for x, y in footbridge_points_data:
        gx, gy = _sjtsk_to_grid(x, y, geo_bbox)
        px_b, py_b = _grid_to_px(gx, gy)
        tg = _nearest_segment_tangent(px_b, py_b, water_lines_px)
        if tg is None:
            rot = 0.0
        else:
            tx, ty = tg
            rot = math.atan2(-tx, ty)
        _draw_footbridge(draw, mdraw, px_b, py_b, rot)
        footbridge_features.append((gx, gy, code_fb, rot))
        info.append({"symbol": code_fb, "kind": "footbridge_point",
                     "layer": "Lávka (bod)"})

    return bridge_features, tunnel_features, footbridge_features, info


# =====================================================================
#  Řopíky / lehké opevnění LO37 — fáze 1 (projekce reálných dat), asset placement (Sez. 27)
# =====================================================================
# Řopík NENÍ prostý ISOM symbol, ale ASSET (budova 521 + vrstevnice náspu 101) — dvojici
# kreslí uživatel v OOM (asset pattern, Sez. 26). Generátor ho stáhne (ZABAGED Bunkr LO37),
# natočí (normála na lokální linii řopíků, „čelní zasypaný násep" = asset-sever VEN k nejbližší
# státní hranici — univerzální ČR) a vloží na každou reálnou polohu. Projekce, ne dekorace.
ROPIK_ASSET_PATH = _REPO_ROOT / "asset" / "ropik_10000.omap"
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
        _draw_building_area(draw, bdraw, [bring], ISOM_BUILDING)    # černá 521 + maska budov ([bring] = tvar list-ringů, Sez. 54)
        ropik_features.append(([_to_grid(bring)], 521))            # jeden prsten bez děr → list-ringů
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


def generate_map(
        lat: float, lon: float, w_km: float, h_km: float,
        only_real: bool = False, out_dir: str | None = None,
        *,                                    # vše dál keyword-only — z popředí API zmizí
        seed: int = 1, rug: float = 0.5, det: float = 0.5,
        terrain: str = "real", paths: str = "real", rides: str = "real", water: str = "real",
        paved: str = "real", buildings: str = "real", powerlines: str = "real",
        railways: str = "real", ropiky: str = "real", rocks: str = "real",
        bridges: str = "real", surfaces: str = "real", landmarks: str = "real",
        linefeatures: str = "real", marsh: str = "real", treerows: str = "real",
        barriers: str = "real",
        predict_areas_sjtsk: list | None = None,
        point_base: bool = False,
        tolerant: bool = False, ortho: bool = True, ortho_mpp: float = 0.5,
        grivation: float | None = None) -> Path:
    """Vygeneruje pseudorealistickou mapu lokality (lat, lon) o rozměru w_km×h_km.

    Reframe Sez. 23 (real-větev je *prediktor mapy*): skládá dva zdroje (DMR výškopis +
    ZABAGED vektor) do mapy konkrétního místa. „Pseudorealistická" = vypadá jako reálné
    mapování, ale je to projekce dat, ne skutečně zmapovaná mapa (GLOSSARY). Funkce dříve
    `synthesize_pseudorealistic_map` → přejmenována na `generate_map` (Sez. 39: v komunikaci
    převládl „generátor"; deštník i pro budoucí generátory, ne jen tuto syntézu).
    Vrací cestu k výstupní složce (`out_dir`; None → `maps/output`). Dvě oddělitelné fáze
    (Sez. 24, GLOSSARY):
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

    `point_base=True` (Sez. 106) = render podkladu pro Png2Point trénink: vynutí vypnutí VŠECH
    bodových symbolů (skály 204/207, landmarks, barriers, terénní extrémy 109/110/111), aby rgb.png
    neměl body bez GT (jinak nejednoznačná funkce, diagnostika Sez. 105). Plochy/linie/vegetace zůstávají.

    Rastrový z-order (pořadí kreslení do PNG): plošný pokryv (401 open land / 520 zákaz vstupu, ÚPLNĚ
    VESPOD = podklad) → predikční vegetace (406/408/410 zeleň + 403, ze separace) → stromořadí (406 lineární les) → mokřady (308) → vrstevnice (§4.5) → pomocné vrstevnice (103) →
    bodové symboly extrémů (§4.10) → zpevněné plochy (501) → voda → cesty (§4.9) → lesní průseky
    (508) → el. vedení (510) → železnice (509) → budovy (521) → řopíky → skály/balvany (204/207/206/208) →
    bodové orient. prvky (524/526/530/417/312/311/203.2) → liniové orient. prvky (104 sráz / 107 rokle / 513 zeď) →
    mosty/tunely/lávky (512/512.2 úplně navrch). Je to VĚDOMÁ generátorová volba pro
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
    # point_base (Sez. 106): podklad pro Png2Point trénink = render BEZ JEDINÉHO bodového symbolu.
    # Png2Point se učí detekovat INJEKTOVANÉ ikonky (inject.py) — kdyby měl podklad vlastní body bez
    # GT peaku (gen 204/207, landmarks, 109/110/111), funkce by byla nejednoznačná („tenhle kruh = 204,
    # tamten identický = nic") a model selže i na 1 dlaždici (diagnostika Sez. 105). Master flag vynutí
    # všechny bodové vrstvy off; terénní extrémy (vlastní flag nemají) se vynechají u kreslení níže.
    # Plochy/linie/vegetace zůstávají jako realistický kontext (206 skalní plocha padá s rocks=off —
    # drobná ztráta, akceptovaná pro MVP). Izomorf k „off", jen jedním záměrovým přepínačem.
    if point_base:
        rocks = landmarks = barriers = "off"
    # Všechny reálné vrstvy potřebují S-JTSK georef výseku (sdílený build_bbox) — noise terén je
    # v lokálních metrech bez georef, reálná data by se neměla na co napárovat. Jedna validace pro
    # všechny vrstvy (DRY): (CLI flag, zvolený mode, popis vrstvy do hlášky).
    for flag, mode, popis in (("--paths", paths, "reálné cesty"),
                              ("--rides", rides, "reálné lesní průseky"),
                              ("--water", water, "reálná voda"),
                              ("--buildings", buildings, "reálné budovy"),
                              ("--powerlines", powerlines, "reálné el. vedení"),
                              ("--railways", railways, "reálná železnice"),
                              ("--paved", paved, "reálná zpevněná plocha"),
                              ("--ropiky", ropiky, "řopíky ze ZABAGED"),
                              ("--rocks", rocks, "reálné skály/balvany"),
                              ("--bridges", bridges, "reálné mosty/tunely/lávky"),
                              ("--surfaces", surfaces, "reálný plošný pokryv"),
                              ("--landmarks", landmarks, "reálné bodové orient. prvky"),
                              ("--linefeatures", linefeatures, "reálné liniové orient. prvky"),
                              ("--marsh", marsh, "reálné mokřady"),
                              ("--treerows", treerows, "reálná stromořadí"),
                              ("--barriers", barriers, "reálné prostupy (zábrany na zdi)")):
        if mode == "real" and terrain != "real":
            raise ValueError(f"{flag} real vyžaduje --terrain real ({popis} potřebují S-JTSK "
                             "georef výseku; noise terén je v lokálních metrech).")
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

    # selhání reálných vrstev (jen tolerant režim): {vrstva: důvod} → meta.json. Definováno brzy,
    # protože plošný pokryv (z-order vespod, kreslí se hned) ho potřebuje už před vrstevnicemi.
    layer_errors: dict[str, str] = {}

    # --- zpevněná base (ISOM 501.1 „ostatní plocha v sídlech"): ÚPLNĚ VESPOD, pod pokryvem (Sez. 54) ---
    # 501.1 = administrativní výplň sídla (díry vykrojí budovy/zeleň/cesty). Kreslí se PŘED surfaces →
    # olivová 520 privátních parcel (RÚIAN, věrnější) ji NAHOŘE překryje (z-order: privátní/nepřístupné má
    # přednost před „zpevněná"). Sdílí paved masku s 501 kolejištěm (top fáze níž). Jen --paved real.
    paved_area_features: list[tuple] = []
    paved_info: list[dict] = []
    paved_mask_img: Image.Image | None = None
    adraw: ImageDraw.ImageDraw | None = None
    if paved == "real":
        paved_mask_img = Image.new("L", (W, H), 0)       # GT maska zpevněných ploch (§8.1), sdílená oběma fázemi
        adraw = ImageDraw.Draw(paved_mask_img)
        base_feats, base_info = _try_layer(
            "paved-base", lambda: _generate_real_paved(draw, adraw, lat, lon, geo_bbox, urban_base=True),
            ([], []), tolerant, layer_errors)
        paved_area_features += base_feats
        paved_info += base_info

    # --- plošný pokryv / land-cover (ISOM 401 open land + 520 zákaz vstupu): ÚPLNĚ VESPOD (Sez. 41-42) ---
    # Rastr z-order: PRVNÍ kresba na bílé plátno = podklad pod vrstevnicemi i vším ostatním. Žlutá
    # open land (louka/park) + pole 412 + olivová zákaz vstupu (hřbitov + privátní pozemek RÚIAN + sad/zahrada)
    # jsou plochy POD hnědou terénní kostrou (tak je vidí oko na reálné mapě). Les zůstává bílá (default
    # pozadí, nekreslí se — vegetace gate). Reálná půlka ze ZABAGED + RÚIAN REST, jedna multi-class maska.
    surface_area_features: list[tuple] = []
    surfaces_info: list[dict] = []
    fence_features: list[tuple] = []                      # plot 516 (obvod RÚIAN zahrad druh 5, Sez. 98/113)
    surface_mask_img: Image.Image | None = None
    if surfaces == "real":
        surface_mask_img = Image.new("L", (W, H), 0)     # GT maska pokryvu (§8.1), multi-class
        sfdraw = ImageDraw.Draw(surface_mask_img)
        surface_area_features, surfaces_info, fence_features = _try_layer(
            "surfaces", lambda: _generate_real_surfaces(draw, sfdraw, lat, lon, geo_bbox, pseudorealistic),
            ([], [], []), tolerant, layer_errors)
        _log.info("  plošný pokryv: %d (520 dissolve bloky + open land) + plot 516: %d",
                  len(surfaces_info), len(fence_features))

    # --- predikční vegetace → zeleň + 403 (ISOM 406/408/410/403): SEPARACE reálné mapy ---
    # Z-order: NAD plošným pokryvem (401/520 podklad), pod stromořadím/mokřady/vrstevnicemi/liniemi.
    # Zelená vegetace nad žlutou open land i nad bílým lesem; tenká stromořadí (alej) a hnědá kostra
    # zůstanou viditelné navrchu. JEDINÝ zdroj = `predict_areas_sjtsk` (Sez. 83, orchestrátor pairs.py
    # ze separace Livelox mapy); provenance = predict (viz meta). Bez něj (DEV `--location`, bez páru)
    # = bez zeleně (bílý les). Archiv Sez. 102: forest_age proxy AOPK smazán (slepá ulička, viz
    # PREDICT_AREA_* komentář); pseudorealistic vegetace = budoucí náhrada pro lokality bez skenu (TODO).
    veg_area_features: list[tuple] = []
    veg_area_info: list[dict] = []
    veg_area_mask_img: Image.Image | None = None
    boundary_features: list[tuple] = []           # 416/416.1 mezitřídní hranice (Sez. 101)
    boundary_mask_img: Image.Image | None = None
    predict_veg = predict_areas_sjtsk is not None
    if predict_veg:
        veg_area_mask_img = Image.new("L", (W, H), 0)  # GT maska zeleně (§8.1), multi-class
        fadraw = ImageDraw.Draw(veg_area_mask_img)
        veg_area_features, veg_area_info = _draw_predict_areas(
            draw, fadraw, predict_areas_sjtsk, geo_bbox)
        _log.info("  predikční vegetace (separace): %d (406/408/410 PREDICT)", len(veg_area_info))
        # 416/416.1 Distinct vegetation boundary: mezitřídní hranice predikčních veg ploch (Sez. 101,
        # největší KPI díra). Z-order: NAD plošnou zelení (kterou ohraničuje), pod liniemi/body.
        boundary_mask_img = Image.new("L", (W, H), 0)
        bdraw = ImageDraw.Draw(boundary_mask_img)
        boundary_features = _predict_veg_boundaries(veg_area_mask_img, draw, bdraw)
        _log.info("  hranice vegetace: %d (%s mezitřídní)", len(boundary_features),
                  ISOM_VEG_BOUNDARY)

    # --- stromořadí / lineární les (ISOM 406): `Liniová vegetace` → úzký zelený pás (Sez. 45) ---
    # Z-order: NAD plošným pokryvem (401/520 jsou podklad), pod vrstevnicemi/liniemi/body — světle
    # zelená vegetace nad žlutou open land, ale pod hnědou terénní kostrou. Jen --treerows real.
    # Liniová data (osa) → plošný buffer (KISS vždy 406; vegetace gate neporušuje — tvrdý objekt).
    treerow_area_features: list[tuple] = []
    treerows_info: list[dict] = []
    treerow_mask_img: Image.Image | None = None
    if treerows == "real":
        treerow_mask_img = Image.new("L", (W, H), 0)     # GT maska stromořadí (§8.1)
        trdraw = ImageDraw.Draw(treerow_mask_img)
        treerow_area_features, treerows_info = _try_layer(
            "treerows", lambda: _generate_real_tree_rows(draw, trdraw, lat, lon, geo_bbox),
            ([], []), tolerant, layer_errors)
        _log.info("  stromořadí: %d (406 lineární les)", len(treerows_info))

    # --- mokřady (ISOM 308 Marsh): bažina/močál + rašeliniště (Sez. 44, katalog dávka 4) ---
    # Z-order: NAD plošným pokryvem (401/520 jsou podklad), pod vrstevnicemi/liniemi/body. Modrá
    # vodorovná šrafa ořezaná na polygon. Jen --marsh real. KISS vrstva → vždy 308 (crossable).
    marsh_area_features: list[tuple] = []
    marsh_info: list[dict] = []
    marsh_mask_img: Image.Image | None = None
    if marsh == "real":
        marsh_mask_img = Image.new("L", (W, H), 0)       # GT maska mokřadů (§8.1)
        mhdraw = ImageDraw.Draw(marsh_mask_img)
        marsh_area_features, marsh_info = _try_layer(
            "marsh", lambda: _generate_real_marsh(draw, mhdraw, lat, lon, geo_bbox, pseudorealistic),
            ([], []), tolerant, layer_errors)
        n_ind = sum(1 for m in marsh_info if m["symbol"] == ISOM_MARSH_INDISTINCT)
        _log.info("  mokřady: %d (308 Marsh %d / 310 Indistinct %d)",
                  len(marsh_info), len(marsh_info) - n_ind, n_ind)

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
    # point_base (Sez. 106): vynech kreslení extrémů do rgb — podklad pro Png2Point nesmí mít žádné
    # body. (point_symbols zůstávají v .omap/meta/masce; pro point_base je nepoužíváme, jen rgb.png.)
    if not point_base:
        for ps in point_symbols:
            _draw_point_symbol(draw, sdraw, ps)

    # --- PRE-FETCH mostů/tunelů (Sez. 32 E1+E4): jen geometrie, žádné kreslení ---
    # Mosty/tunely se vykreslí navrch (= závorky lemují, kolmé čárky vstup/výstup) AŽ NA KONCI;
    # ale jejich grid linie potřebujeme TEĎ jako "cutter pole" pro voda/cesty/železnice, aby
    # se procházející linie přerušily v okolí mostu/tunelu (±0,5 mm). Sez. 31/32 = 4 iterace
    # bez ohledu na E1+E4; teď systematicky integrované do pipeline.
    bridge_grids: list = []
    tunnel_grids: list = []
    footbridge_lines_data: list = []
    footbridge_points_data: list = []
    if bridges == "real":
        bridge_grids, tunnel_grids, footbridge_lines_data, footbridge_points_data = _try_layer(
            "bridges_fetch",
            lambda: _fetch_bridges_tunnels_geometries(lat, lon, geo_bbox),
            ([], [], [], []), tolerant, layer_errors)
    # Cutter sady pro cropping (Sez. 32 6. iterace, dva typy strategií):
    # CROSSING strategy (bridge_cutters): 1-2 bod-průsečíky = crop; >2 = paralel souběh
    #   = ignore. Aplikuje se na voda/cesty/železnice křížené mostem POD ním.
    # PASSAGE strategy (tunnel_cutters): cropuje úsek line, kde line prochází mezi
    #   start a end tunelu (nezávisle na bod-průsečícich). Aplikuje se na železnice/cesty
    #   uvnitř tunelu.
    # Linie vedoucí PO MOSTĚ = paralel souběh = crossing > 2 → bez crop ✓ (uživatel E2).

    # --- zpevněné plochy / kolejiště (ISOM 501): reálné ze ZABAGED REST (real-půlka, Sez. 28) ---
    # Rastr z-order: brzy (po terénu/bodech, PŘED vodou/cestami) — hnědá plocha je podklad, na
    # němž leží koleje (509), cesty i budovy. NAD pokryvem (501.1 base + 401/520 už nakresleny výš).
    # Sdílí paved masku s 501.1 base fází. V lesních výsecích bez nádraží = 0 prvků. Jen --paved real.
    if paved == "real":
        top_feats, top_info = _try_layer(
            "paved", lambda: _generate_real_paved(draw, adraw, lat, lon, geo_bbox, urban_base=False),
            ([], []), tolerant, layer_errors)
        paved_area_features += top_feats
        paved_info += top_info
        _log.info("  zpevněné plochy: %d (501 kolejiště + 501.1 parkoviště/ostatní plocha v sídlech)", len(paved_info))

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
            "water",
            lambda: _generate_real_water(draw, wdraw, lat, lon, geo_bbox,
                                          bridge_cutters=bridge_grids),
            ([], [], []), tolerant, layer_errors)
        _log.info("  voda: %d (toky+plochy)", len(water_info))
        # plot 516 se generuje PŘED vodou (pokryv vespod) → vyřízni jeho úseky nad hladinou až teď (Sez. 113)
        if fence_features and water_area_features:
            n_before = len(fence_features)
            fence_features = _clip_fences_off_water(fence_features, water_area_features)
            if len(fence_features) != n_before:
                _log.info("  plot 516: ořez od vody %d → %d úseků", n_before, len(fence_features))

    # --- cesty (§4.9): procedurální (Dijkstra least-cost) nebo reálné (ZABAGED REST) ---
    # Rastr z-order: PO vodě, PŘED budovami. Obě větve sdílí render (_draw_path) i GT masku
    # — liší se jen zdrojem geometrie (proc/real).
    path_mask_img = Image.new("L", (W, H), 0)       # GT maska cest (§8.1), multi-class
    pdraw = ImageDraw.Draw(path_mask_img)
    if paths == "real":
        path_features, paths_info = _try_layer(
            "paths",
            lambda: _generate_real_paths(draw, pdraw, lat, lon, geo_bbox,
                                          bridge_cutters=bridge_grids,
                                          tunnel_cutters=tunnel_grids),
            ([], []), tolerant, layer_errors)
    else:
        # proc cesty (Dijkstra) jsou offline → žádné REST selhání, tolerance se netýká
        path_features, paths_info = _generate_proc_paths(rng, elev, draw, pdraw,
                                                         cell_w_m, cell_h_m, det)
    n_paths = len(paths_info)
    _log.info("  cesty: %d (%s)", n_paths, paths)

    # --- lesní průseky (ISOM 508): reálné ze ZABAGED REST (real-půlka, Sez. 36) ---
    # Rastr z-order: PO cestách, PŘED vedením — černá čárkovaná linie (průhled lesem bez cesty),
    # izomorfní s komunikacemi. V bezlesém výseku = 0 prvků (žádný šum). Jen --rides real.
    ride_features: list[tuple] = []
    rides_info: list[dict] = []
    ride_mask_img: Image.Image | None = None
    if rides == "real":
        ride_mask_img = Image.new("L", (W, H), 0)        # GT maska lesních průseků (§8.1)
        ridraw = ImageDraw.Draw(ride_mask_img)
        ride_features, rides_info = _try_layer(
            "rides", lambda: _generate_real_rides(draw, ridraw, lat, lon, geo_bbox),
            ([], []), tolerant, layer_errors)
        _log.info("  lesní průseky: %d", len(rides_info))

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
            lambda: _generate_real_railways(draw, rdraw, lat, lon, geo_bbox,
                                             tunnel_cutters=tunnel_grids),
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

    # --- skály / balvany (ISOM 204/207/206/208): reálné ze ZABAGED REST (real-půlka, Sez. 30 + 57) ---
    # Rastr z-order: ÚPLNĚ NAVRCH (po budovách+řopících) — replikuje OOM color order, kde
    # 204/206/207 mají vyšší prioritu (=draw nahoru) než 521 Building. Hruboskalsko: skály
    # vizuálně dominantní → musí být vidět. V plochém terénu (NL, SV) = 0 prvků (žádný šum).
    # Jen --rocks real. Body 204/207 + linie 208 ze ZABAGED (KISS vrstva → jeden symbol); plocha 206
    # z DMR sklonu (rock_relief, Sez. 63) — nahradila generalizovaný ZABAGED Skalní_útvary.
    # vyloučení pseudo bodů (kameny 204/210 I veg 417/419) z budov/cest/zpevněných (Sez. 136, nález
    # uživatele {A}): hotové GT masky (px). path vždy; building/paved mohou být None (vrstva off).
    # Sdíleno boulders i veg call (DRY). Tady je dostupné vše (budovy/cesty/zpevněné už proběhly).
    forbid_imgs = [m for m in (building_mask_img, path_mask_img, paved_mask_img) if m is not None]
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

        # PSEUDO injekce bodů 204/210 (FÁZE 2, Sez. 107) — dosype body, co ZABAGED nevede v reálné
        # hustotě (kompas: 204 gen 3/orig 1064, 210 gen 0/orig 975). Gated `pseudorealistic` (izomorf
        # 310/516); visí na rocks="real" → point_base i only_real ji korektně vypnou. Body nesou str
        # kódy ("204"/"210.1") — rock_point_omap_features dělá str(c) na všech, smíšení s int real kódy projde.
        if pseudorealistic:
            # maska z DOLOŽENÉ skalnatosti: reálné 204/207 body + 206 plochy (před přidáním pseudo)
            pseudo_pts = _try_layer(
                "pseudo_boulders",
                lambda: _generate_pseudo_boulders(draw, rdraw_rocks,
                                                  rock_point_features, rock_area_features, rng,
                                                  water_area_features, forbid_imgs),
                [], tolerant, layer_errors)
            rock_point_features = list(rock_point_features) + pseudo_pts
            n204 = sum(1 for *_, c in pseudo_pts if c == "204")
            n210 = sum(1 for *_, c in pseudo_pts if c == "210.1")
            # pseudo body i do rocks_info → meta.json je vidí (stats.py/STATISTICS, KPI je čte z .omap);
            # izomorf 310 marsh (pseudo sdílí sekci s reálnými skalami; Sez. 108 conceptual integrity).
            # 210.1 (render varianta) agregujeme na ISOM 210 Stony ground.
            for *_, c in pseudo_pts:
                code_i = 210 if c == "210.1" else int(c)
                rocks_info.append({"symbol": code_i, "symbol_name": ROCK_NAME[code_i],
                                   "kind": "point", "layer": "pseudo (Sez. 107)"})
            if pseudo_pts:
                _log.info("  pseudo body: 204:%d, 210.1(tečky):%d", n204, n210)

    # --- bodové orientační prvky (ISOM 524/526/530/417): reálné ze ZABAGED (Sez. 43, audit katalogu) ---
    # Rastr z-order: navrch (body, musí být vidět — jako skály). Jen --landmarks real. KISS vrstva →
    # jeden symbol (map_landmark_to_isom): věž 524 / mohyla 526 / kříž 530 / strom 417.
    landmark_features: list[tuple] = []
    landmarks_info: list[dict] = []
    landmark_mask_img: Image.Image | None = None
    if landmarks == "real":
        landmark_mask_img = Image.new("L", (W, H), 0)    # GT maska orient. prvků (§8.1), multi-class
        ldraw_lm = ImageDraw.Draw(landmark_mask_img)
        landmark_features, landmarks_info = _try_layer(
            "landmarks",
            lambda: _generate_real_landmarks(draw, ldraw_lm, lat, lon, geo_bbox),
            ([], []), tolerant, layer_errors)
        by_code_lm: dict[int | str, int] = {}
        for it in landmarks_info:
            by_code_lm[it["symbol"]] = by_code_lm.get(it["symbol"], 0) + 1
        if by_code_lm:
            # key=str: kódy míchají int (524/312/311) i str ("203.2") → sorted bez klíče padne (Sez. 44)
            parts = [f"{LANDMARK_NAME[c]}({c}):{n}" for c, n in sorted(by_code_lm.items(), key=lambda kv: str(kv[0]))]
            _log.info("  orient. prvky: %d (%s)", len(landmarks_info), ", ".join(parts))
        else:
            _log.info("  orient. prvky: 0")

        # PSEUDO injekce vegetačních bodů 417/418/419 (FÁZE 2, Sez. 136; 418 Sez. 137 — princip kamenů):
        # doložené stromy 417 jsou řídké (~3 % reálné hustoty), 418/419 ZABAGED zdroj nemají → dosypeme na
        # reálnou MĚŘENOU hustotu MIMO vodu + hustou skalnatost. Gated `pseudorealistic` (visí na landmarks="real", jako
        # pseudo boulders na rocks → point_base/only_real ji vypnou). Body → landmark_features (→ .omap
        # přes landmark_omap_features) + landmarks_info (→ meta.json, izomorf pseudo 204/210 do rocks_info).
        if pseudorealistic:
            n_real_417 = sum(1 for *_, c in landmark_features if int(float(c)) == ISOM_LARGE_TREE)
            # forbid_imgs (budovy/cesty/zpevněné) sdílené s pseudo boulders, definované u rocks bloku (Sez. 136)
            pseudo_veg = _try_layer(
                "pseudo_veg",
                lambda: _generate_pseudo_veg_points(draw, ldraw_lm, rock_area_features,
                                                    water_area_features, n_real_417, rng,
                                                    forbid_imgs),
                [], tolerant, layer_errors)
            landmark_features = list(landmark_features) + pseudo_veg
            for *_, c in pseudo_veg:                       # pseudo i do meta (stats/STATISTICS to čte)
                ci = int(c)
                landmarks_info.append({"symbol": ci, "symbol_name": LANDMARK_NAME[ci],
                                       "kind": "point", "layer": "pseudo (Sez. 136)"})
            if pseudo_veg:
                n417 = sum(1 for *_, c in pseudo_veg if c == "417")
                n418 = sum(1 for *_, c in pseudo_veg if c == "418")
                n419 = sum(1 for *_, c in pseudo_veg if c == "419")
                _log.info("  pseudo veg body: 417:%d, 418:%d, 419:%d", n417, n418, n419)

    # --- zábrany na zdi: PRE-FETCH (Sez. 52) ---
    # Spočítat brány JEDNOU, před linefeatures: (a) zeď 513 se pod nimi přeruší (break_px),
    # (b) symboly 519 se z týchž dat vykreslí níž. fetch_barriers stahuje i zdi 513 (sám) →
    # break je konzistentní se zdmi, které linefeatures kreslí. Tolerantní (síť) přes _try_layer.
    barrier_raw: list = []
    if barriers == "real":
        from zabaged import fetch_barriers
        barrier_raw = _try_layer("barriers", lambda: fetch_barriers(lat, lon, GW, GH, TILE_M),
                                 [], tolerant, layer_errors)
    barrier_break_px = [_grid_to_px(*_sjtsk_to_grid(x, y, geo_bbox)) for x, y, _, _ in barrier_raw]

    # --- liniové orientační prvky (ISOM 104/513): reálné ze ZABAGED (Sez. 43, audit katalogu) ---
    # Rastr z-order: po cestách/budovách, před body/skalami. Jen --linefeatures real. KISS vrstva →
    # jeden symbol: sráz 104 / zeď+hradba 513 (map_line_feature_to_isom). Stromořadí 406 plošně, Sez. 45.
    # Zeď 513 se přerušuje pod brankami 519 (barrier_break_px, ISOM „line broken at crossing point").
    linefeat_features: list[tuple] = []
    linefeatures_info: list[dict] = []
    linefeat_mask_img: Image.Image | None = None
    if linefeatures == "real":
        linefeat_mask_img = Image.new("L", (W, H), 0)    # GT maska liniových prvků (§8.1), multi-class
        ldraw_lf = ImageDraw.Draw(linefeat_mask_img)
        linefeat_features, linefeatures_info = _try_layer(
            "linefeatures",
            lambda: _generate_real_line_features(draw, ldraw_lf, lat, lon, geo_bbox, barrier_break_px),
            ([], []), tolerant, layer_errors)
        by_code_lf: dict[int, int] = {}
        for it in linefeatures_info:
            by_code_lf[it["symbol"]] = by_code_lf.get(it["symbol"], 0) + 1
        if by_code_lf:
            parts = [f"{LINEFEAT_NAME[c]}({c}):{n}" for c, n in sorted(by_code_lf.items())]
            _log.info("  liniové prvky: %d (%s)", len(linefeatures_info), ", ".join(parts))
        else:
            _log.info("  liniové prvky: 0")

    # --- zábrany na nosné zdi (ISOM 519 Crossing point): RENDER symbolů (Sez. 52) ---
    # Rastr z-order: navrch (bodový orient. symbol jako landmarks). Data z pre-fetch fáze výš
    # (barrier_raw); tady jen vykreslíme „branky" 519. Zeď pod nimi už je přerušená (linefeatures).
    barrier_features: list[tuple] = []
    barriers_info: list[dict] = []
    barrier_mask_img: Image.Image | None = None
    if barriers == "real":
        barrier_mask_img = Image.new("L", (W, H), 0)     # GT maska prostupů (§8.1), single-class (519)
        bdraw_b = ImageDraw.Draw(barrier_mask_img)
        barrier_features, barriers_info = _generate_real_barriers(draw, bdraw_b, geo_bbox, barrier_raw)
        _log.info("  prostupy (519 na zdi): %d", len(barriers_info))

    # --- mosty + tunely + lávky (ISOM 512 + 512.2): RENDER fáze (Sez. 32 spec-driven) ---
    # Data už máme z pre-fetch fáze. Tady jen vykreslíme závorky (rastr z-order: úplně navrch
    # — po skálách/budovách). Bodová lávka rotuje kolmo k nejbližšímu toku (potřebuje
    # water_lines_px z _generate_real_water; bez vody fallback rot=0).
    bridge_features: list[tuple] = []
    tunnel_features: list[tuple] = []
    footbridge_features: list[tuple] = []
    bridges_info: list[dict] = []
    bridge_mask_img: Image.Image | None = None
    if bridges == "real":
        bridge_mask_img = Image.new("L", (W, H), 0)
        bdraw_bridges = ImageDraw.Draw(bridge_mask_img)
        water_lines_px = [[_grid_to_px(gx, gy) for gx, gy in grid]
                          for grid, _ in water_line_features]
        bridge_features, tunnel_features, footbridge_features, bridges_info = _render_bridges_tunnels(
            draw, bdraw_bridges,
            bridge_grids, tunnel_grids, footbridge_lines_data, footbridge_points_data,
            geo_bbox, water_lines_px)
        # souhrn po typech (most / tunel / lávka)
        by_kind: dict[str, int] = {}
        for it in bridges_info:
            k = it["kind"]
            by_kind[k] = by_kind.get(k, 0) + 1
        if by_kind:
            parts = [f"{k}:{n}" for k, n in sorted(by_kind.items())]
            _log.info("  mosty/tunely/lávky: %d (%s)", len(bridges_info), ", ".join(parts))
        else:
            _log.info("  mosty/tunely/lávky: 0")

    # --- zápis výstupů (§8.1): finální mapa + masky + meta ---
    # out_dir None → kanonické maps/output v kořeni LAB (volající s --location předá maps/<lokalita>).
    out = Path(out_dir) if out_dir else MAPS_DIR / "output"
    out.mkdir(parents=True, exist_ok=True)
    img.save(out / "rgb.png")
    # world file (.pgw) pro rgb.png — georef rastru do S-JTSK (Sez. 37). Jen reálný terén
    # (crs_epsg != None); u noise je výsek lokální (žádné reálné umístění). Grid-north-up, bez
    # rotace o grivaci → overlay s reálnou (magnetic-north-up) mapou v GIS odhalí náklon i posun.
    if crs_epsg is not None:
        _write_world_file(out / "rgb.pgw", geo_bbox)
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
    if ride_mask_img is not None:
        ride_mask_img.save(out / "mask_rides.png")                          # lesní průseky 508 (GT)
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
    if landmark_mask_img is not None:
        landmark_mask_img.save(out / "mask_landmarks.png")                  # orient. prvky (GT, multi-class: 524/526/530/417)
    if linefeat_mask_img is not None:
        linefeat_mask_img.save(out / "mask_linefeatures.png")              # liniové prvky (GT, multi-class: 104/513)
    if barrier_mask_img is not None:
        barrier_mask_img.save(out / "mask_barriers.png")                    # prostupy 519 (GT, single-class)
    if bridge_mask_img is not None:
        bridge_mask_img.save(out / "mask_bridges.png")                      # mosty/tunely/lávky (GT, multi-class)
    if surface_mask_img is not None:
        surface_mask_img.save(out / "mask_surfaces.png")                    # plošný pokryv (GT, multi-class: 1=open land 401, 2=zákaz vstupu 520, 3=pole 412, 4=park 402, 5=zeleň 402.1 — Sez. 53)
    if marsh_mask_img is not None:
        marsh_mask_img.save(out / "mask_marsh.png")                         # mokřady (GT, 1=marsh 308)
    if treerow_mask_img is not None:
        treerow_mask_img.save(out / "mask_treerows.png")                    # stromořadí (GT, 1=lineární les 406)
    if veg_area_mask_img is not None:
        veg_area_mask_img.save(out / "mask_veg_area.png")              # predikční vegetace (GT, multi-class: 1=fight 410, 2=walk 408, 3=slow 406, 4=403 — ze separace)
    if boundary_mask_img is not None:
        boundary_mask_img.save(out / "mask_boundaries.png")           # 416 mezitřídní hranice veg ploch (Sez. 101)
    # vektorový export vrstevnic (§9): ISOM 101/102 + pomocné 103, georef (real = S-JTSK).
    # Form line je taky vrstevnice (liniový objekt) → do téhož contours.geojson.
    n_contours = _write_contours_geojson(contour_features + formline_features, geo_bbox, crs_epsg,
                                         out / "contours.geojson")
    # .omap export (§9): vrstevnice + cesty + voda + body do uživatelova čistého ISOM 2017-2
    # template (template_classic.omap, Sez. 14). Vodní toky 304/305/306 = liniové objekty;
    # plochy → 301 KOMBINOVANÝ (Blue 100% výplň + ČERNÁ břehová linie = neprůchodná hranice;
    # Sez. 58 oprava z 301.1 bez okraje — mapaři kreslí vodní plochu s okrajem, rastr ho má od
    # Sez. 18; combined area objekt funguje jako kolejiště 501 Sez. 28). NE 301.2 (= Blue 70% dominant).
    water_omap_features = ([(g, c) for g, c in water_line_features]
                           + [(g, "301") for g, _ in water_area_features])
    # budovy = plošný symbol 521 (area, type-4 v template) → uzavřený prstenec, OOM vyplní;
    # zříceniny 523 (Sez. 43) = týž area objekt, ale OOM nakreslí čárkovaný obrys (line symbol).
    # Code z featur (NE hardcode 521 — jinak by zřícenina vypadla jako budova).
    building_omap_features = [(g, str(c)) for g, c in building_area_features]
    # el. vedení = liniový symbol 510 (type-1 v template) → otevřený path
    powerline_omap_features = [(g, "510") for g, _ in powerline_features]
    # železnice = liniový symbol 509 (kombinovaný type-16 v template) → otevřený path; OOM
    # vykreslí kombinovaný symbol (čárky + bílý knockout) autoritativně z definice symbolu (Sez. 28)
    railway_omap_features = [(g, "509") for g, _ in railway_features]
    # lesní průseky = liniový symbol 508 (čárkovaný, type-1 v template) → otevřený path; OOM
    # vykreslí čárkování z definice symbolu (dash 3,0 / break 0,375 mm)
    ride_omap_features = [(g, "508") for g, _ in ride_features]
    # zpevněné plochy → 501 (KOMBINOVANÝ symbol: hnědá výplň + OBRYSOVÁ LINIE; kolejiště, do nějž se
    # nevstupuje — rozhodnutí uživatele Sez. 28) / 501.1 (plošný BEZ obrysu; ostatní plocha v sídlech
    # 115, Sez. 54). Uzavřený prstenec s close flagem (viz AREA_CODES); OOM vyplní area-část a u 501
    # nakreslí obrys. Code z featur (NE hardcode — jinak by 501.1 vypadlo jako 501).
    paved_omap_features = [(g, str(c)) for g, c in paved_area_features]
    # plošný pokryv → 401 (open land) / 520 (zákaz vstupu) = plošné symboly (area, uzavřený path
    # s close flagem; OOM vyplní plnou barvou). Sez. 41-42.
    surface_omap_features = [(g, str(c)) for g, c in surface_area_features]
    # mokřady → 308 Marsh = plošný symbol (area, type-4 s patternem v template; uzavřený path
    # s close flagem). OOM vykreslí modrý vodorovný pattern autoritativně z definice (Sez. 44).
    marsh_omap_features = [(g, str(c)) for g, c in marsh_area_features]
    # stromořadí → 406 Vegetation: slow running = plošný symbol (area, uzavřený path s close flagem;
    # OOM vyplní světle zelenou z definice). Prstenec už je buffrovaný pás (Sez. 45).
    treerow_omap_features = [(g, str(c)) for g, c in treerow_area_features]
    # predikční vegetace → 406/408/410 zeleň + 403 = plošný symbol (area, uzavřený path s close
    # flagem; OOM vyplní z definice). Ze separace reálné mapy (predict, Sez. 83). Code z featur.
    veg_area_omap_features = [(g, str(c)) for g, c in veg_area_features]
    # pomocné vrstevnice = liniový symbol 103 (čárkovaný, type-1 v template) → otevřený path;
    # OOM vykreslí čárkování autoritativně z definice symbolu (dash 2,0 / break 0,2 mm)
    formline_omap_features = [(g, "103") for g, _ in formline_features]
    # skály/balvany (Sez. 30): body 204/207 + plochy 206. Plocha 206 = area_object (jako 501/521),
    # body 204/207 = point_object (jako 109/110/111).
    rock_point_omap_features = [(gx, gy, str(c)) for gx, gy, c in rock_point_features]
    rock_area_omap_features = [(g, str(c)) for g, c in rock_area_features]
    # bodové orientační prvky (Sez. 43): 524/526/530/417 = point_object (jako 109/110/111, 204/207)
    landmark_omap_features = [(gx, gy, str(c)) for gx, gy, c in landmark_features]
    # liniové orientační prvky (Sez. 43): 104/513 = liniový objekt (otevřený path); OOM
    # vykreslí symbol z definice (104 ticky, 513 plná). Stromořadí 406 plošně (výš, Sez. 45).
    linefeat_omap_features = ([(g, str(c)) for g, c in linefeat_features]
                              + [(g, str(c)) for g, c in fence_features]   # plot 516 (pseudo, Sez. 98)
                              + [(g, str(c)) for g, c in boundary_features])   # 416 veg boundary (Sez. 101)
    # zábrany → 519 Crossing point = point_object s ROTACÍ (rotatable, jako lávka 512.2; Sez. 52).
    # rot v radiánech (px konvence) = orientace „brány" podél nosné zdi.
    barrier_omap_features = [(gx, gy, "519", rot) for gx, gy, rot, _ in barrier_features]
    # Mosty (Sez. 32 5. iterace dle Most.omap dema): 1 ZABAGED Most → emit 2 PARALELNÍ
    # line objekty 512 v omap_export (offset ±0,75 mm kolmo). Tunely → 1 line objekt 512
    # (uživatelův template kreslí jednu závorku na konci, vstup+výstup symetrické).
    # Lávka → 1 point objekt 512.2 s rotací (jako Sez. 32 dosud).
    bridge_omap_features = [(g, "512") for g, _ in bridge_features]
    tunnel_omap_features = [(g, "512") for g, _ in tunnel_features]
    footbridge_omap_features = [(gx, gy, "512.2", rot) for gx, gy, _, rot in footbridge_features]
    from omap_export import write_omap
    # název .omap = název výstupní složky (lokalita), ne generické „map.omap" (Sez. 42, bod 1
    # testu LS) — `maps/Lidové sady/Lidové sady.omap`. SSoT názvu = out.name (sdílené s rgb/meta).
    omap_name = f"{out.name}.omap"
    omap_counts = write_omap(contour_features, path_features, point_symbols,
                             water_omap_features, building_omap_features,
                             powerline_omap_features,
                             GW, GH, WORLD_W_M, TILE_M, MAP_SCALE, out / omap_name,
                             ortho_template=ortho_template, ropik_features=ropik_features,
                             railway_features=railway_omap_features,
                             ride_features=ride_omap_features,
                             paved_features=paved_omap_features,
                             formline_features=formline_omap_features,
                             rock_point_features=rock_point_omap_features,
                             rock_area_features=rock_area_omap_features,
                             bridge_features=bridge_omap_features,
                             tunnel_features=tunnel_omap_features,
                             footbridge_features=footbridge_omap_features,
                             surface_features=surface_omap_features,
                             landmark_features=landmark_omap_features,
                             linefeature_features=linefeat_omap_features,
                             marsh_features=marsh_omap_features,
                             treerow_features=treerow_omap_features,
                             veg_area_features=veg_area_omap_features,
                             barrier_features=barrier_omap_features,
                             grivation=grivation)
    omap_info = {"file": omap_name, **omap_counts}
    # reálné ZABAGED/RÚIAN vrstvy → meta sekce přes _layer_meta_section (A1 Sez. 50, DRY: jediná
    # struktura sekce + jediná cesta uvnitř i vně _build_meta, zrušena dřívější asymetrie). Tabulka
    # (mode, klíč, maska, info, NAME, CLASS) je jediný seznam vrstev — přidat další = jeden řádek.
    # Pořadí = z-order historie (paths zůstává vlastní v _build_meta: source proc|real, páteř).
    real_sections: dict = {}
    for mode, key, mask_name, info, name_map, class_map in (
            (rides, "rides", "mask_rides.png", rides_info, RIDE_NAME, RIDE_CLASS),
            (water, "water", "mask_water.png", water_info, WATER_NAME, WATER_CLASS),
            (paved, "paved", "mask_paved.png", paved_info, PAVED_NAME, PAVED_CLASS),
            (buildings, "buildings", "mask_buildings.png", building_info, BUILDING_NAME, BUILDING_CLASS),
            (powerlines, "powerlines", "mask_powerlines.png", powerlines_info, POWERLINE_NAME, POWERLINE_CLASS),
            (railways, "railways", "mask_railways.png", railways_info, RAILWAY_NAME, RAILWAY_CLASS),
            (rocks, "rocks", "mask_rocks.png", rocks_info, ROCK_NAME, ROCK_CLASS),
            (surfaces, "surfaces", "mask_surfaces.png", surfaces_info, SURFACE_NAME, SURFACE_CLASS),
            (landmarks, "landmarks", "mask_landmarks.png", landmarks_info, LANDMARK_NAME, LANDMARK_CLASS),
            (linefeatures, "linefeatures", "mask_linefeatures.png", linefeatures_info, LINEFEAT_NAME, LINEFEAT_CLASS),
            (marsh, "marsh", "mask_marsh.png", marsh_info, MARSH_NAME, MARSH_CLASS),
            (treerows, "treerows", "mask_treerows.png", treerows_info, TREEROW_NAME, TREEROW_CLASS),
            (barriers, "barriers", "mask_barriers.png", barriers_info, BARRIER_NAME, BARRIER_CLASS)):
        if mode == "real":
            real_sections[key] = _layer_meta_section(mask_name, info, name_map, class_map)
    # mosty/tunely/lávky: vlastní sekce (most+tunel sdílí ISOM 512, hardcoded symbols + maskové
    # třídy 1=most/2=tunel/3=lávka — _layer_meta_section to neumí, odvozuje symbols z 1 kódu→name).
    if bridges == "real":
        real_sections["bridges"] = {
            "count": len(bridges_info),
            "mask": "mask_bridges.png",
            "source": "cuzk_zabaged",
            "symbols": {"512": "Bridge/tunnel", "512.2": "Footbridge"},
            "classes": {"0": "pozadí",
                        str(BRIDGE_CLASS_BRIDGE): "512 Bridge",
                        str(BRIDGE_CLASS_TUNNEL): "512 Tunnel",
                        str(BRIDGE_CLASS_FOOTBRIDGE): "512.2 Footbridge"},
            "items": bridges_info,
            "licence": "CC BY 4.0 (ČÚZK ZABAGED)",
        }
    # predikční vegetace: VLASTNÍ sekce (ne _layer_meta_section) — FLAG `provenance: predict` +
    # `note` (zeleň ze separace, ne tvrdá projekce) — to helper neumí. Meta to musí přiznat, ať
    # konzument (UC5/compare/reconstructor) nevezme zeleň jako real. Symboly/třídy ze SKUTEČNĚ
    # použitých kódů (mirror _layer_meta_section). JEDINÝ zdroj = separace (forest_age proxy archiv Sez. 102).
    if predict_veg:
        used = sorted({it["symbol"] for it in veg_area_info}, key=str)
        real_sections["veg_area"] = {
            "count": len(veg_area_info),
            "mask": "mask_veg_area.png",
            "source": "separace_realne_mapy", "provenance": "predict", "proxy": True,
            "note": ("PREDICT: zeleň 406/408/410 + 403 SEPAROVANÁ z barev reálné OB mapy (mapař = GT, "
                     "Sez. 82/83), ne z tvrdých dat. GT-feeder pro Png2Area — věrnost ~90 %, dotáhne model."),
            "licence": "odvozeno z reálné OB mapy (kartograf/pořadatel; TDM režim)",
            "symbols": {str(c): PREDICT_AREA_NAME[c] for c in used},
            "classes": {"0": "pozadí",
                        **{str(PREDICT_AREA_CLASS[c]): f"{c} {PREDICT_AREA_NAME[c]}" for c in used}},
            "items": veg_area_info,
        }
        real_sections["veg_boundary"] = {
            "count": len(boundary_features),
            "mask": "mask_boundaries.png",
            "source": "separace_realne_mapy", "provenance": "predict", "proxy": True,
            "symbols": {ISOM_VEG_BOUNDARY: BOUNDARY_NAME[ISOM_VEG_BOUNDARY]},
            "classes": {"0": "pozadí", "1": f"{ISOM_VEG_BOUNDARY} "
                        f"{BOUNDARY_NAME[ISOM_VEG_BOUNDARY]}"},
            "items": [
                {"symbol": ISOM_VEG_BOUNDARY,
                 "symbol_name": BOUNDARY_NAME[ISOM_VEG_BOUNDARY],
                 "kind": "line", "layer": "separace reálné mapy (predict)"}
                for _ in boundary_features
            ],
        }
    meta = _build_meta(seed, rug, det, terrain, paths, pseudorealistic, lat, lon, elev,
                       crs_epsg, n_contours, len(formline_features), n_paths, paths_info,
                       point_symbols, omap_info, real_sections, layer_errors)
    # ISOM verze + georef výseku — injektováno zde (nejsou to vrstvy, precedent Sez. 37/38).
    # `isom` = deklarace verze (ochrana proti záměně 2000↔2017-2); `georef` = S-JTSK bbox + .pgw + sever.
    meta["isom"] = _isom_meta()
    meta["georef"] = _georef_meta(geo_bbox, crs_epsg, grivation)
    meta["azimutlab_config"] = {
        "file": "azimutlab.toml",
        "symbols": {"vegetation_boundary": ISOM_VEG_BOUNDARY},
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    # finální souhrn (SSoT = právě spočtené počty vrstev) — ta řádka, co inspirovala log (Sez. 27)
    _log.info("hotovo → %s · pokryv %d · budovy %d · řopíky %d · voda %d · zpevněné %d · cesty %d · průseky %d · "
              "vrstevnice %d (pomocné %d) · vedení %d · železnice %d · skály %d · mosty/tunely/lávky %d · "
              "body %d · .omap objektů %d", out, len(surfaces_info), len(building_info),
              len(ropik_info), len(water_info), len(paved_info), n_paths, len(rides_info),
              len(contour_features),
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
    p.add_argument("--rides", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED REST Lesní průsek → ISOM 508 Narrow ride (default), "
                        "off = bez průseků (real vyžaduje --terrain real; v bezlesém výseku 0 prvků)")
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
                        "→ ISOM 204/207/206 (default), off = bez skal "
                        "(real vyžaduje --terrain real; v plochém terénu 0 prvků)")
    p.add_argument("--bridges", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED Most/Tunel/Lávka → ISOM 512+512.2 (default), "
                        "off = bez mostů/tunelů/lávek (real vyžaduje --terrain real; bodová "
                        "lávka rotuje kolmo k vodě, --water real doporučeno)")
    p.add_argument("--surfaces", choices=["off", "real"], default="real",
                   help="real = ČÚZK plošný pokryv → ISOM 401 open land (louka/park, žlutá) + 412 pole "
                        "(žlutá + černý tečkový pattern) + 520 zákaz vstupu (olivová: hřbitov ZABAGED + "
                        "privátní pozemek RÚIAN + sad/zahrada ZABAGED) (default), off = bez pokryvu "
                        "(real vyžaduje --terrain real; les zůstává bílá = vegetace gate)")
    p.add_argument("--landmarks", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED bodové orient. prvky → ISOM 524 věž (věž/vodojem/silo/…) + "
                        "526 mohyla/pomník + 530 kříž/sloup + 417 významný strom + 312 pramen + "
                        "203.2 jeskyně/šachta + 311 nádrž (default), off = bez nich (real vyžaduje --terrain real)")
    p.add_argument("--linefeatures", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED liniové orient. prvky → ISOM 104 sráz + 513 zeď/hradba "
                        "(default), off = bez nich (real vyžaduje --terrain real)")
    p.add_argument("--marsh", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED mokřady (bažina/močál + rašeliniště) → ISOM 308 Marsh "
                        "(modrá vodorovná šrafa, default), off = bez nich (real vyžaduje --terrain real)")
    p.add_argument("--treerows", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED Liniová vegetace (stromořadí) → ISOM 406 lineární les "
                        "(světle zelený pás, default), off = bez nich (real vyžaduje --terrain real)")
    p.add_argument("--barriers", choices=["off", "real"], default="real",
                   help="real = ČÚZK ZABAGED Zábrana ležící na zdi 513 → ISOM 519 Crossing point "
                        "(průchod plotem; default), off = bez nich (real vyžaduje --terrain real; "
                        "závory na cestách se zahazují, vrstva je řídká)")
    p.add_argument("--only-real", action="store_true",
                   help="vypne pseudorealistickou fázi 2 (dekorace nad rámec tvrdých dat); "
                        "default = fáze 2 zapnuta. Zatím: příčky vedení mimo evidované sloupy")
    p.add_argument("--no-ortho", dest="ortho", action="store_false",
                   help="nestahovat ortofoto podklad (default = ČÚZK ortofoto výseku do ortofoto.png "
                        "+ připnutí do .omap; jen s --terrain real)")
    p.add_argument("--ortho-mpp", type=float, default=0.5,
                   help="rozlišení ortofoto podkladu [m/px] (default 0,5; menší = ostřejší, ale "
                        "větší soubor i RAM v OOM; konektor dlaždicuje nad 4096 px)")
    p.add_argument("--grivation", type=float, default=None,
                   help="grivace [°] = úhel grid(S-JTSK)→magnetický sever; zapíše se do .omap georef "
                        "(declination=grivation), OOM zobrazí mapu natočenou na magnetic-north (geometrie "
                        "i rastr zůstávají v gridu). Default None = grid-north (Sez. 37/112). Konvergence "
                        "S-JTSK v ČR ~7°, deklinace ~5° → grivace ~12° (sken Bedřichovka 10,88°)")
    p.add_argument("--grivation-auto", action="store_true",
                   help="spočítat grivaci z lokality (lat/lon) přes konektor magnetic.py "
                        "(WMM deklinace + S-JTSK konvergence) pro DNEŠNÍ datum; --grivation ji přebije")
    p.add_argument("--grivation-date", default=None, metavar="YYYY-MM-DD",
                   help="grivaci spočítat pro konkrétní datum (implies --grivation-auto; WMM platí 2024–2029)")
    p.add_argument("--lat", type=float, default=DEF_LAT, help="zeměpisná šířka WGS84 (jen --terrain real)")
    p.add_argument("--lon", type=float, default=DEF_LON, help="zeměpisná délka WGS84 (jen --terrain real)")
    p.add_argument("--width-km", type=float, default=DEF_WIDTH_KM,
                   help=f"šířka výseku E-W [km] (default {DEF_WIDTH_KM} = baseline; --location má per-lokalita rozměr)")
    p.add_argument("--height-km", type=float, default=DEF_HEIGHT_KM,
                   help=f"výška výseku S-J [km] (default {DEF_HEIGHT_KM} = baseline; --location má per-lokalita rozměr)")
    p.add_argument("--out", default=None,
                   help="výstupní složka (default: maps/<lokalita> u --location, jinak maps/output)")
    args = p.parse_args()
    # vývojářská lokalita (--location) přepíše souřadnice + výsek per-lokalita (Sez. 31:
    # různé formáty landscape/portrait pro test ořezů). Jinak ruční --lat/--lon/--width-km/
    # --height-km. _apply_extent volá až sama funkce.
    out_dir = args.out
    if args.location:
        name, lat, lon, w_km, h_km = DEV_LOCATIONS[args.location]
        # --location ⇒ výstup do maps/<lokalita> (název = SSoT pro STATISTICS.md),
        # ledaže uživatel dal explicitní --out. (Sez. 39: kotveno v kořeni LAB přes MAPS_DIR.)
        if out_dir is None:
            out_dir = str(MAPS_DIR / name)
    else:
        lat, lon, w_km, h_km = args.lat, args.lon, args.width_km, args.height_km
    # grivace: ruční --grivation má přednost; jinak auto z konektoru (--grivation-auto/-date)
    grivation = args.grivation
    if grivation is None and (args.grivation_auto or args.grivation_date):
        from datetime import date as _date
        from magnetic import grivation as _calc_grivation
        when = _date.fromisoformat(args.grivation_date) if args.grivation_date else None
        grivation = round(_calc_grivation(lat, lon, when), 2)
        _log.info("grivace (auto, %s) = %.2f°", args.grivation_date or "dnes", grivation)
    out = generate_map(
        lat, lon, w_km, h_km, only_real=args.only_real, out_dir=out_dir,
        seed=args.seed, rug=args.rug, det=args.det, terrain=args.terrain,
        paths=args.paths, rides=args.rides, water=args.water, paved=args.paved, buildings=args.buildings,
        powerlines=args.powerlines, railways=args.railways, ropiky=args.ropiky,
        rocks=args.rocks, bridges=args.bridges, surfaces=args.surfaces, landmarks=args.landmarks,
        linefeatures=args.linefeatures, marsh=args.marsh, treerows=args.treerows,
        barriers=args.barriers,
        ortho=args.ortho, ortho_mpp=args.ortho_mpp, grivation=grivation)
    _log.info("výstup: %s", out.resolve())
    # ořez přesahu na papír: real ČÚZK vrací CELÉ features protínající bbox → objekty sahají
    # mimo papír (okolní sídla, „Nisa do Vesce", Sez. 113/114). Vektorový .omap; rgb.png je už
    # ořezán canvasem. Jen real (noise je celý uvnitř → no-op zbytečný). No silent fallback: loguj.
    if args.terrain == "real":
        from cut import cut_box
        kept, removed = cut_box(out, out.name)
        _log.info("ořez na papír (cut_box): %d objektů po ořezu (%d celých mimo papír odstraněno; "
                  "linie/plochy přes hranu geometricky oříznuty)", kept, removed)


if __name__ == "__main__":
    main()
