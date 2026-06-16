"""
zabaged.py — reálné vektorové prvky z ČÚZK ZABAGED® Polohopis (ArcGIS REST; UC2 konektor, real-půlka).

Sourozenec dmr.py (NE kopie): dmr.py táhne reálný VÝŠKOPIS (DMR 5G, rastr/ImageServer),
zabaged.py táhne reálné POLOHOPISNÉ VEKTORY (ArcGIS REST query). Od cest (§4.9, Sez. 16) postupně
přibyly: voda (toky+plochy, 17), budovy (18), el. vedení + stožáry (24), železnice/tramvaj +
kolejiště (28+31), řopíky + státní hranice (27), skály/balvany (30), mosty/tunely/lávky (32-33),
lesní průseky (36), plošný pokryv / land-cover + areály účelové zástavby (41-42), bodové orient.
prvky (věž/kříž/strom/pramen/jeskyně/nádrž, 43-44), liniové orient. prvky (sráz/zeď, 43), mokřady
(44), stromořadí = lineární les (45), kultura pole + sad/zahrada (48-49), komín → 524 + zábrana →
519 na nosné zdi (52). Plný výčet = `*_LAYERS`
konstanty níže + `docs/kb/zabaged-isom-catalog.md`.
Vše bere tentýž výsek přes sdílený dmr.build_bbox() → reálné prvky padnou bezešvě na tentýž terén
jako vrstevnice z DMR. Mapování ZABAGED→ISOM dělají `map_*_to_isom` funkce (po verify atributů).

Zdroj: ČÚZK ZABAGED Polohopis, ArcGIS REST MapServer `/query` (open data, CC BY 4.0 —
atribuce povinná). `f=geojson` → GeoJSON přímo (žádný GML parsing, izomorfní s contours.geojson).

Klíčová zjištění (Sez. 16 = WFS, Sez. 26 = přechod na REST):
  - REST: .../arcgis/rest/services/ZABAGED_POLOHOPIS/MapServer/<layer_id>/query
  - PROČ REST místo WFS (Sez. 26): WFS GetFeature tvrdě uřezával na 1000 obj/dotaz a
    startIndex paging byl rozbitý → velká města přicházela o objekty. REST query má strop
    2000 + spolehlivý resultOffset paging (viz _fetch_layer + LAYER_IDS).
  - vrstvy se adresují numerickým layer ID (LAYER_IDS), ne typeName; in/outSR=EPSG:5514.
  - geometrie LineString/Polygon (i Multi-); atributy v REST jsou MALÝMI písmeny (pozor:
    WFS měl `TYPUSKOM_K` velkými, REST `typuskom_k` — viz map_path_to_isom).

Pozn. k souřadnicím: S-JTSK (EPSG:5514) má v ČR záporné x i y (x ≈ -700 tis = easting,
y ≈ -1000 tis = northing). Axis order REST odpovědi (in/outSR=5514) se ověřuje regresí
(vizuál sedí na terén) i diagnostikou (main).
"""

from pathlib import Path

# Sdílený výsek s výškopisem (izomorfismus, bezešvost) — build_bbox je public (Sez. 8).
from dmr import build_bbox
# Sdílený nízkoúrovňový ArcGIS REST transport (Sez. 42, DRY se sourozencem ruian.py): paging+
# cache+error smyčka + GeoJSON geom parsery. Parsery se importují pod původními `_geom_to_*`
# jmény → call-sites beze změny (behavior-preserving refaktor).
from arcgis import (fetch_geojson_layer,
                    geom_to_lines as _geom_to_lines,
                    geom_to_polygons as _geom_to_polygons,
                    geom_to_points as _geom_to_points)

# REST endpoint ZABAGED Polohopis MapServer (Sez. 26: přechod z WFS). WFS GetFeature tvrdě
# uřezával na 1000 obj/dotaz a startIndex paging byl rozbitý (Sez. 25); REST query má strop
# 2000 + SPOLEHLIVÝ resultOffset paging (ověřeno temp/probe_rest_paging.py: SV budovy 1078,
# dávky navazují, overlap 0) → města se stáhnou kompletní. Vrstvy se adresují numerickým
# layer ID (ne typeName).
_REST_SERVER = "https://ags.cuzk.gov.cz/arcgis/rest/services/ZABAGED_POLOHOPIS/MapServer"
_PAGE = 2000   # maxRecordCount REST query (ověřeno) — velikost dávky v paging smyčce

# WFS typeName → REST layer ID (ověřeno proti MapServer?f=json, Sez. 26; obnova: temp/probe_zabaged_rest.py).
LAYER_IDS = {
    "Cesta": 83, "Pěšina": 82, "Silnice__dálnice": 79,
    "Silnice_neevidovaná": 80, "Ulice": 84,
    "Lesní průsek": 16,                # (Sez. 36) REST jméno s MEZEROU (jako tramvaj/lávka), ne escape
    "Železniční_trať": 75, "Železniční_vlečka": 76, "Kolejiště": 122,
    "Tramvajová dráha": 71,            # (Sez. 31) jméno s MEZEROU, ne WFS escape s podtržítkem

    "Vodní_tok": 93, "Vodní_plocha": 132, "Pozemní_nádrž": 107,
    "Budova_jednotlivá_nebo_blok_budov__plocha_": 99,
    "Elektrické_vedení": 88, "Stožár_elektrického_vedení": 87,
    # Lanovka/vlek (Sez. 55) → 510 (mirror vedení; ISOM 510 = „Power line, cableway or skilift").
    # REST jména s MEZEROU/ČÁRKOU (jako tramvaj/lávka), ID z MapServer ?f=json (linie 72 / sloup 61).
    "Lanová dráha, lyžařský vlek": 72, "Stožár lanové dráhy": 61,
    "Bunkr": 37, "Hranice_správní_jednotky": 1,
    # Skály a balvany (Sez. 30, ID ověřená přes MapServer ?f=json + temp/probe_rocks.py).
    # Osamělý_balvan… 10 = bodové „turisticky významné" balvany (na Hruboskalsku 6 prvků).
    # Skupina_balvanů… 12 = bodová pole drobných kamenů (168 na Hrubé Skále). Skalní_útvary
    # 130 = polygony skal (411 na Hrubé Skále, medián 1132 m², max 30 444 m²).
    "Osamělý_balvan__skála__skalní_suk": 10,
    "Skupina_balvanů__bod_": 12,
    "Skupina_balvanů__linie_": 13,    # liniová pole balvanů (Sez. 57, → 208 Boulder field; Σ14 SV/HS/NV)
    "Skalní_útvary": 130,
    # Mosty / tunely / lávky (Sez. 32 znovu, spec-driven po rollbacku Sez. 31).
    # REST jména: Most + Tunel s podtržítky/bez (Most = jedno slovo, OK), Lávka má MEZERU
    # a závorky (`Lávka (linie)`/`Lávka (bod)`, NE WFS-styl `Lávka__linie_`).
    "Most": 73,
    "Tunel": 74,
    "Lávka (linie)": 67,
    "Lávka (bod)": 66,
    # Plošný pokryv / land-cover (Sez. 41, `--surfaces` + parkoviště do `--paved`). ID + REST
    # jména ověřena ?f=json + temp probe count (SV/LS/NL). POZOR: REST jména s MEZERAMI/ČÁRKAMI
    # a diakritikou (jako tramvaj/lávka), ne WFS escape. Vinice (136)/Chmelnice (137)/kosodřevina
    # (141) vynechány — 0 prvků ve všech DEV_LOCATIONS.
    "Ostatní plocha v sídlech": 115,    # → 501.1 (Sez. 54; administrativní výplň sídla s děrami)
    "Hřbitov": 116,
    "Parkoviště, odpočívka": 123,
    "Udržovaná zeleň": 134,
    "Ovocný sad, zahrada": 135,
    "Orná půda a ostatní dále nespecifikované plochy": 138,
    "Trvalý travní porost": 139,
    # Areál účelové zástavby (Sez. 42, audit land-cover): oplocené areály v sídlech (škola,
    # hřiště, sportovní areál, stadión, kasárna, průmysl, garáže, autobusové nádraží, …) — atribut
    # typzast_k rozliší typ (62 hodnot). Kůlna/přístřešek = drobné stavby → 521 (mirror budov).
    "Areál účelové zástavby": 114,
    "Kůlna, skleník, fóliovník, přístřešek": 105,
    # Povrchová těžba (Sez. 56): kamenolom = oplocený areál se zákazem vstupu → 520 olivová
    # (stěna lomu 201 je LINIE s ticky → plochu lomu na ni nedotahujeme; KISS plocha→plocha).
    # REST jméno s mezerou/čárkou (ověřeno ?f=json + probe id 118: LS Σ1, druhtez_p='kámen').
    "Povrchová těžba, lom": 118,
    # Budovové stavby — historické + zříceniny (Sez. 43, audit katalogu „nic užitečného nevypadne").
    # ČÚZK vede zámek/hrad/zříceninu v SAMOSTATNÝCH plošných vrstvách (NE v Budova_..._plocha_ 99) →
    # bez nich vypadly z mapy (verify Sez. 43: domov mládeže Krompach = `Zámek` 102; Milštejn = `Rozvalina`).
    "Zámek": 102,
    "Hrad": 101,
    "Rozvalina, zřícenina": 103,
    # Bodové orientační prvky (Sez. 43, audit katalogu — ISOM 52x-53x + 417). Klasické OB body,
    # dosud vypadávaly. REST jména s mezerami/čárkami (ověřeno ?f=json + probe atributů Sez. 43).
    "Kříž, sloup kulturního významu": 24,        # → 530 (ring)
    "Mohyla, pomník, náhrobek": 25,              # → 526 Cairn
    "Věž, věžovitá nástavba": 26,                # → 524 High tower (podtypob = věž kostela/kaple)
    "Věžovitá stavba": 100,                      # plocha (3 m² footprint) → centroid → 524
    "Významný nebo osamělý strom, lesík": 14,    # → 417 Prominent large tree (typveg = osamělý strom/lesík)
    "Vodojem věžový": 27,                        # → 524 (0 ve výsecích, pro úplnost)
    "Silo": 28,                                  # → 524 (0, pro úplnost)
    "Těžní věž": 30,                             # → 524 (0, pro úplnost)
    "Větrný mlýn": 32,                           # → 524 (0, pro úplnost)
    "Větrný motor": 33,                          # → 524 (0, pro úplnost)
    "Tovární komín": 31,                         # → 524 High tower (Sez. 52; LS 12/SV 1, atribut vyska_obj nevyužit — KISS)
    # Liniové orientační prvky (Sez. 43, audit katalogu): terénní sráz / zeď.
    "Stupeň, sráz": 95,                          # → 104 Earth bank (Σ981 = nejčastější netáhnutá!)
    "Rokle, výmol": 94,                          # → 107 Erosion gully (Sez. 58, Σ0 na DEV — naslepo)
    "Zábrana": 54,                               # → 519 Crossing point (Sez. 52; jen na nosné zdi 513, viz fetch_barriers)
    "Zeď": 39,                                   # → 513 Wall
    "Hradba, val, bašta, opevnění": 38,          # → 513 Wall (kamenné historické opevnění)
    "Liniová vegetace": 15,                      # → 406 lineární les (stromořadí; Sez. 45, NE 416 = hranice porostů)
    # Vodní / mokřady / terénní bodové prvky (Sez. 44, katalog dávka 4). REST jména ověřena
    # ?f=json (mezery/čárky/závorky, NE WFS podtržítka — paměť zabaged-rest-naming-conventions).
    # Bažina+rašeliniště = plochy → 308 (--marsh); pramen/jeskyně/šachta/nádrž = body → --landmarks.
    "Bažina, močál": 131,                        # plocha → 308 Marsh
    "Rašeliniště (plocha)": 18,                  # plocha → 308 Marsh (rašeliniště = mokřad téhož symbolu)
    "Zdroj podzemních vod": 19,                  # bod → 312 Spring (NE 313 = orientovaný prom. water feature)
    "Vstup do jeskyně": 11,                      # bod → 203.2 Cave or rocky pit
    "Ústí šachty, štoly": 34,                    # bod → 203.2 (důlní ústí; spec „…or mineshafts…")
    "Nadzemní zásobní nádrž": 108,               # plocha → centroid → 311 Well/fountain/water tank
}

# Feature typy komunikací relevantní pro OB (les). Turistická_trasa se vynechává — vede
# zpravidla PO existující cestě/pěšině → duplikovala by liniovou síť (rozhodnuto Sez. 16).
# (Silnice/Ulice jsou v lese vzácné, ale patří do sítě, kde výsek zasáhne okraj obce.)
# Silnice_neevidovaná = účelové/lesní asfaltky mimo silniční evidenci — v lese ČASTÉ a pro
# OB klíčové (Sez. 23: chyběla páteřní asfaltka Bedřichov→Nová louka). Most je samostatná
# liniová vrstva → ISOM 512 (BRIDGE_LAYERS, Sez. 32, NE bod jak dříve mylně uvedeno);
# Silnice_ve_výstavbě zatím vynechána (ve výsecích vzácná). Plný katalog 149 vrstev:
# docs/kb/zabaged-isom-catalog.md.
PATH_LAYERS = ("Cesta", "Pěšina", "Silnice__dálnice", "Silnice_neevidovaná", "Ulice")

# Lesní průseky (Sez. 36, real-půlka, liniová — izomorfní s cestami). ZABAGED `Lesní průsek`
# (id 16, REST jméno s MEZEROU jako tramvaj/lávka) → ISOM 508 Narrow ride = průhled lesem BEZ
# zřetelné vyšlapané cesty (odlišení od 503-506). KISS, vrstva → jeden symbol (vrstva nese jen
# nekategoriální atributy — verify SV: 46 prvků, žádný typ/šířka). Runnability pozadí (žlutá/zelená
# dle prostupnosti) se NEKRESLÍ: vegetace není v datech (gate Sez. 3), je to UC5 predikce ne projekce
# → ISOM varianta „without background". Mapování viz map_ride_to_isom.
RIDE_LAYERS = ("Lesní průsek",)

# Železnice + tramvaj (Sez. 28+31, real-půlka, liniová — izomorfní s cestami/vedením). ZABAGED:
# `Železniční_trať` (id 75) = osy hlavních tratí; `Železniční_vlečka` (76) = průmyslové/nádražní
# vlečky; **`Tramvajová dráha` (71) = městská tramvaj** (Sez. 31, oprava Sez. 28 vynechání:
# tramvajová točna LS chyběla, ISOM 509 nerozlišuje tramvaj od železnice — vše „Railway").
# Všechny tři → ISOM 509 (map_railway_to_isom, vždy 509, KISS jako budovy→521/vedení→510).
# Pozn.: jméno tramvajové vrstvy v REST je `Tramvajová dráha` s MEZEROU (ne WFS escape
# s podtržítky jako železnice — paralela Lávka Sez. 31; ČÚZK má historicky obě konvence).
# POZN.: „deset kolejí vedle sebe" u nádraží NEJSOU linie — ZABAGED je generalizuje do plochy
# `Kolejiště` (→ PAVED_AREA_LAYERS, 501). Katalog: docs/kb/zabaged-isom-catalog.md (sekce 3).
RAILWAY_LAYERS = ("Železniční_trať", "Železniční_vlečka", "Tramvajová dráha")

# Kolejiště / zpevněné plochy (Sez. 28, real-půlka, plošná — izomorfní s vodní plochou/budovou).
# ZABAGED `Kolejiště` (id 122, plocha) = nádražní kolejová plocha (Liberec hl. n. ~19 ha jako
# JEDEN polygon; jednotlivé koleje data nemodelují jako linie). → ISOM 501 Paved area (kombinovaný
# symbol: hnědá 50% výplň + obrysová linie). Mapování viz map_paved_to_isom. Vzor pro budoucí
# další zdroje 501 (parkoviště ap.). Jinde než u nádraží/zpevněných ploch = 0 prvků.
PAVED_AREA_LAYERS = ("Kolejiště", "Parkoviště, odpočívka")  # Sez. 41 (DRY); kolejiště → 501 s obrysem,
#                                                              parkoviště → 501.1 BEZ obrysu (Sez. 57, průchozí)
# `Ostatní plocha v sídlech` (id 115) → 501.1 Paved area BEZ obrysu (Sez. 54). Administrativní výplň
# zastavěného území: obří polygon se STOVKAMI DĚR (budovy/zeleň/cesty vykrojené ven) — díry teď parser
# nese (geom_to_polygons, Sez. 54), takže 501.1 vyplní jen volné plochy mezi nimi (náměstí/dvory/
# parkoviště), ne celé sídlo (Sez. 53 bez děr zalila 41 % výseku → odloženo na holes). Samostatná
# konstanta (jiný symbol i sémantika než kolejiště), ale táhne se týmž fetch_paved_areas (DRY).
OTHER_URBAN_AREA_LAYERS = ("Ostatní plocha v sídlech",)

# Plošný pokryv / land-cover (Sez. 41, real-půlka, plošná — izomorfní s vodní plochou/budovou).
# Dvě skupiny podle ISOM:
#  OPEN_LAND = otevřené plochy. Druh nese VRSTVA, u zeleně i ATRIBUT (Sez. 47/53): louka `Trvalý
#    travní porost` → 401 Open land (plná žlutá); `Udržovaná zeleň` se ŠTĚPÍ podle `typ_pudy_k` na park/
#    okrasnou zahradu → 402 (žlutá + bílé tečky) a ostatní zeleň → 402.1 (žlutá + zelené tečky); pole
#    `Orná půda…` → 412 Cultivated land (žlutá + černý tečkový pattern); sad/zahrada `Ovocný sad, zahrada`
#    → 520 olivová (Sez. 49: zahrady u domů/chalup, oplocené = out-of-bounds, ne běhatelný sad — oprava
#    Sez. 48 = 413 Orchard). Sez. 41 bylo KISS vše→401; Sez. 47/49/53 rozliší kulturu/zeleň (mapping nese
#    vrstva+atribut, viz map_open_land_to_isom). Les NENÍ open land — zůstává bílá (vegetace gate).
#  CEMETERY = hřbitov → 520 Area that shall not be entered (plná olivová, out-of-bounds). ISOM nemá
#    vlastní hřbitovní symbol → 520 (verify template Sez. 41). Umělá plocha, čistá projekce bez gate.
# Render: 401/520 plná výplň; 412 žlutá výplň + černý tečkový pattern (Sez. 47). Mapování viz map_*_to_isom.
OPEN_LAND_LAYERS = ("Trvalý travní porost", "Udržovaná zeleň",
                    "Orná půda a ostatní dále nespecifikované plochy", "Ovocný sad, zahrada")
CEMETERY_LAYERS = ("Hřbitov",)

# Kamenolom (Sez. 56, povrchová těžba). `Povrchová těžba, lom` → 520 Area that shall not be
# entered (olivová, out-of-bounds) — oplocený těžební areál se zákazem vstupu, izomorfní
# s hřbitovem (plocha → vždy 520). NEmapujeme na 201 Impassable cliff: 201 je LINIE (hrana
# stěny s ticky), ZABAGED dává PLOCHU → dotahování stěny z plochy = over-engineering pro Σ1
# (LS kamenolom). Kamenné/zemní útvary (201/206/104) zůstávají v z-orderu NAD olivovou.
QUARRY_LAYERS = ("Povrchová těžba, lom",)

# Mokřady (Sez. 44, katalog dávka 4, real-půlka, plošná — izomorfní s open land/hřbitovem).
# `Bažina, močál` + `Rašeliniště (plocha)` → ISOM 308 Marsh (crossable, modrý vodorovný pattern).
# KISS vrstva → jeden symbol: nemáme atribut překonatelnosti → vždy 308 (crossable), NE 307
# uncrossable (klasický OB předpoklad; nepřekonatelnost = terénní znalost, ne data — viz crossability
# TODO). Rašeliniště = mokřad téhož symbolu. Mapování viz map_marsh_to_isom.
MARSH_AREA_LAYERS = ("Bažina, močál", "Rašeliniště (plocha)")

# Vodní feature typy (Sez. 17, real-půlka hydrografie). ZABAGED Polohopis dělí vodu na
# linie (Vodní_tok) a plochy (Vodní_plocha) — izomorfní s cesty=linie. Pramen
# (Zdroj_podzemních_vod) se NEtáhne: ve výsecích OB map je vzácný (ověřeno — v demo
# výřezu 0, nejbližší PS 1,9 km) a 312 Spring je real-only bez náhrady (rozhodnuto Sez. 17).
# Plochy: kromě Vodní_plocha (přírodní — rybníky/jezera) i Pozemní_nádrž (umělé nádrže vč.
# KOUPALIŠŤ/bazénů, podtypob_k='BA') — taky 301. Verify Sez. 27: Lesní koupaliště v LS je
# Pozemní_nádrž ~1934 m², NE Vodní_plocha → bez ní na mapě chybělo.
WATER_LINE_LAYERS = ("Vodní_tok",)
WATER_AREA_LAYERS = ("Vodní_plocha", "Pozemní_nádrž")

# Budovy/stavby (Sez. 18, real-půlka). ZABAGED dělí budovy na bodovou a plošnou vrstvu;
# bodová (`_bod_`) je v lesních OB výsecích prázdná (ověřeno — 0 features na Sovím vrchu),
# proto se táhne jen plošná (izomorfní s Vodní_plocha). Pramen-like vynechání bodové
# vrstvy = „nevymýšlet, co v datech není" (jako Zdroj_podzemních_vod, Sez. 17).
# Sez. 42 (audit land-cover): přidána `Kůlna, skleník, fóliovník, přístřešek` (id 105) = drobné
# stavby (přístřešky, skleníky, kůlny — časté v zahrádkářských koloniích) → taky 521 (KISS, mirror
# budov; drobné, ale reálné). Obě vrstvy plošné, mapuje map_building_to_isom (DRY přes tuto konstantu).
# Sez. 43 (audit katalogu): + `Zámek`/`Hrad` (id 102/101) → 521 jako běžná budova (footprint do měřítka;
# zámek SV = domov mládeže Krompach, 1882 m²; hrad HS 87-145 m²). ČÚZK je vede zvlášť, ne v Budova_99.
BUILDING_AREA_LAYERS = ("Budova_jednotlivá_nebo_blok_budov__plocha_",
                        "Kůlna, skleník, fóliovník, přístřešek",
                        "Zámek", "Hrad")
# Zříceniny (Sez. 43, audit katalogu). ZABAGED `Rozvalina, zřícenina` (id 103, plocha, `podtypob`=
# rozvalina) → ISOM 523 Ruin = čárkovaný černý obrys půdorysu (NE plná výplň jako 521; ruina =
# neúplná stavba). Klasický OB orientační bod (Milštejn na SV ad.). Plošná vrstva → mapuje
# map_building_to_isom (DRY, druhý ISOM kód téže „budovové" kategorie --buildings, mirror skály 204/206/207).
RUIN_AREA_LAYERS = ("Rozvalina, zřícenina",)

# Bodové orientační prvky (Sez. 43, audit katalogu, real-půlka, bodové — izomorfní s body skal
# 204/207). ISOM kategorie 52x-53x + 417. KISS vrstva → jeden ISOM symbol (jako skály/budovy);
# rozliší map_landmark_to_isom. Skupiny dle cílového ISOM kódu:
#   524 High tower  — vysoká věž/stožár (věž kostela/kaple, vodojem věžový, silo, těžní věž, větrný
#                     mlýn/motor, tovární komín); + plošná `Věžovitá stavba` (footprint 3 m² → centroid,
#                     ne 521). Komín (Sez. 52) má atribut `vyska_obj`, ale 524 nemá výškové varianty → KISS.
#   526 Cairn       — mohyla/pomník/náhrobek (memorial stone / trig point).
#   530 Prom. ring  — kříž/sloup kulturního významu (boží muka — prominent man-made feature, ring).
#   417 Large tree  — významný/osamělý strom (ZELENÝ kroužek; bodový orientační prvek, ne plošná
#                     vegetace → mimo vegetace gate Sez. 3).
# Vodojem/silo/těžní/mlýn/motor mají 0 výskytů ve všech 5 DEV_LOCATIONS (probe Sez. 43), ale ISOM
# ekvivalent existuje → mapujeme i je (princip „nic užitečného nevypadne" — jinde se vyskytnou).
LANDMARK_POINT_LAYERS_524 = ("Věž, věžovitá nástavba", "Vodojem věžový", "Silo",
                             "Těžní věž", "Větrný mlýn", "Větrný motor", "Tovární komín")
LANDMARK_POINT_LAYERS_526 = ("Mohyla, pomník, náhrobek",)
LANDMARK_POINT_LAYERS_530 = ("Kříž, sloup kulturního významu",)
LANDMARK_POINT_LAYERS_417 = ("Významný nebo osamělý strom, lesík",)
LANDMARK_AREA_LAYERS_524 = ("Věžovitá stavba",)        # plocha → centroid → 524 (malý footprint)
# Vodní/terénní bodové prvky (Sez. 44, katalog dávka 4). Připojené do --landmarks (bodové,
# izomorfní s věží/mohylou). Pozn.: 203.2 je NECELÝ ISOM kód (string) — map_landmark_to_isom
# proto vrací int | str; render i .omap pracují přes str(code), takže míchání nevadí.
#   312 Spring  — pramen (modré „U", ústí nahoru).
#   203.2 Cave  — vstup do jeskyně + ústí šachty/štoly (černá „Λ" stříška, hrot nahoru — „with a distinct
#                 entrance"; 203.1 by byl V hrotem dolů „without entrance"; oprava Sez. 44).
#   311 Well    — nadzemní zásobní nádrž; plocha → centroid (jako Věžovitá stavba → 524).
LANDMARK_POINT_LAYERS_312 = ("Zdroj podzemních vod",)
LANDMARK_POINT_LAYERS_203_2 = ("Vstup do jeskyně", "Ústí šachty, štoly")
LANDMARK_AREA_LAYERS_311 = ("Nadzemní zásobní nádrž",)  # plocha → centroid → 311 (bodový symbol)

# Liniové orientační prvky (Sez. 43, audit katalogu, real-půlka, liniové — izomorfní s cestami/
# vedením). KISS vrstva → jeden ISOM symbol (map_line_feature_to_isom):
#   104 Earth bank — terénní stupeň/sráz (zemní, NE skalní 201; bez atributu výšky → KISS 104).
#                    Σ981 napříč 5 DEV_LOCATIONS = NEJČASTĚJŠÍ dosud netáhnutá vrstva (silný OB prvek).
#   513 Wall       — zeď + hradba/val/bašta/opevnění (kamenné; `typzed` null → KISS 513).
#   107 Erosion gully — `Rokle, výmol` (id 94, Sez. 58): erozní rýha, polyline, jen `fid_zbg` →
#                    KISS 107 (NE drobné 108). Σ0 na 5 DEV (erozní terény = měkké půdy, ne lesy
#                    Liberecka) → implementováno NASLEPO (linie→linie, spec ověřen; vizuál neověřen).
LINE_FEATURE_LAYERS_104 = ("Stupeň, sráz",)
LINE_FEATURE_LAYERS_513 = ("Zeď", "Hradba, val, bašta, opevnění")
LINE_FEATURE_LAYERS_107 = ("Rokle, výmol",)

# Zábrana → ISOM 519 Crossing point (Sez. 52, real-půlka, bodová ORIENTOVANÁ — vedle řopíků/lávek
# jediná taková). ZABAGED `Zábrana` (id 54) nese jediný typ (`typ_k=Z` = „Závora, brána"). ISOM 519
# = průchod PŘES plot/zeď (branka, schůdky), NE závora na cestě → mapujeme JEN zábrany ležící na
# nosné linii 513 (zeď/hradba); závory na cestách (v OB irelevantní — běžec je obejde) se zahodí.
# Verify-against-source Sez. 52: z 66 zábran na LS leží na 513 jen 2 (medián vzdálenosti od zdi
# 183 m) → vrstva je řídká, ale spravedlivě naplní skutečné průchody v plotě (volba uživatele
# „úplnost i za nízký výtěžek"). Orientace symbolu = tangenta nosné zdi (plot prochází mezi čárkami).
BARRIER_LAYERS = ("Zábrana",)
BARRIER_WALL_LAYERS = LINE_FEATURE_LAYERS_513      # nosné linie (DRY: tytéž zdi jako --linefeatures)
BARRIER_MAX_WALL_DIST_M = 5.0                       # bod ≤ 5 m od zdi = „na zdi" (měření Sez. 52: ≤1 m i ≤5 m = 2/66)

# Stromořadí jako „lineární les" (Sez. 45, real-půlka, liniová DATA → plošná REPREZENTACE).
# `Liniová vegetace` (id 15) je v datech výhradně stromořadí (`typveg_k=S`). ISOM 416 Distinct
# vegetation boundary = HRANICE mezi porosty (kraj lesa / předěl uvnitř lesa), NE řada stromů →
# 416 sémanticky špatně (verify-against-source spec, Sez. 45). ISOM kreslí stromořadí buď řadou
# bodů 417/418 (vyžaduje polohy kmenů — v datech nemáme, jen osu) nebo plošně jako úzký pás lesa
# → volíme PLOŠNĚ: osa → 406 Vegetation: slow running (světlá zelená). Buffer (= šířka pásu =
# kartografie) dělá generátor; konektor vrací jen osu (čistá data). KISS vrstva → vždy 406.
TREE_ROW_LAYERS = ("Liniová vegetace",)

# Areál účelové zástavby (Sez. 42, audit land-cover, real-půlka, plošná). ZABAGED `Areál účelové
# zástavby` (id 114) = oplocené areály v sídlech, atribut `typzast_k` rozlišuje 62 typů (1xx průmysl/
# zemědělství, 2xx kultura/školství, 3xx sport/rekreace, 4xx technické/dopravní). Mapování dle typu
# (map_utility_area_to_isom):
#   asfaltové dopravní plochy (autobusové nádraží 408, čerpací stanice 409) → 501 Paved area
#   VŠE ostatní (škola, hřiště, sport, stadión, kasárna, průmysl, garáže, nemocnice, zahrádk. osada…)
#     → 520 Area which shall not be entered (olivová — oplocený areál, kam běžci nesmí; volba Sez. 42)
# Řeší testovací nálezy LS Sez. 42 (bílá hřiště/školy/kasárna/autobusové nádraží). Render se podle
# ISOM kódu rozdělí mezi surfaces (520) a paved (501) kanál — viz generator._generate_real_*.
UTILITY_AREA_LAYERS = ("Areál účelové zástavby",)
# typzast_k asfaltových dopravních ploch → 501 (zbytek → 520). KISS množina: jen jednoznačně
# zpevněné dopravní areály (Sez. 42, volba uživatele „asfaltové → 501"); jemnější rozlišení = druhá vlna.
PAVED_AREAL_TYPZAST = {"408", "409"}   # 408 autobusové nádraží, 409 čerpací stanice pohonných hmot

# El. vedení + lanovka/vlek (Sez. 24 + 55, real-půlka). Liniové vrstvy (ověřeno: el. vedení
# MultiLineString; lanovka `esriGeometryPolyline`), izomorfní s komunikacemi. Stožáry
# (`Stožár_elektrického_vedení` / `Stožár lanové dráhy`) jsou bodové vrstvy — nesou polohu
# SLOUPŮ, na něž ISOM symbol 510 kreslí kolmé příčky (běžci se jimi řídí, doménový fakt
# uživatele) → reálná data pro příčky (fáze 1, ne vymyšlené). ISOM 510 = „Power line, cableway
# or skilift" = JEDEN symbol pro vedení i lanovku/vlek (verify template id=121, Sez. 55) → sloučeno
# do jedné vrstvy (KISS, jako --rocks/--landmarks slučují více zdrojů). Katalog: zabaged-isom-catalog.md.
POWERLINE_LAYERS = ("Elektrické_vedení", "Lanová dráha, lyžařský vlek")
POWERLINE_MAST_LAYERS = ("Stožár_elektrického_vedení", "Stožár lanové dráhy")

# Řopíky / lehké opevnění (Sez. 27, fáze 1 = projekce reálných dat, NE dekorace). ZABAGED
# `Bunkr`, filtr typbunkr_k='LO37' (lehký objekt vz.37 čs. pohraničního opevnění); bodová vrstva.
# Na OB mapě = asset (NE prostý ISOM 521 — řopík ≠ běžná stavba), orientace dle linie řopíků +
# „ven" k nejbližší státní hranici. Vyskytují se jen u hranic → jinde 0 prvků (žádný šum).
BUNKER_LAYERS = ("Bunkr",)
BUNKER_TYPE_LO37 = "LO37"          # typbunkr_k řopíku (ostatní typy bunkru zatím vynecháváme)
# Státní hranice pro orientaci řopíku „ven" (Sez. 27). `Hranice správní jednotky` nese VŠECHNY
# správní hranice (KÚ/obec/okres…); vyzn_zsh_k='1' = státní (ověřeno: vyzn_zsh_p „Stát, Oblast, Kraj…").
STATE_BORDER_LAYERS = ("Hranice_správní_jednotky",)
STATE_BORDER_CODE = "1"            # vyzn_zsh_k hodnota pro státní hranici

# Skály a balvany (Sez. 30, real-půlka, MVP rozsah). Verify-against-source (probe_rocks.py
# na Hrubé Skále): vrstvy mají JEN atribut `jmeno` (žádné rozlišení typ/velikost/výška) →
# KISS, vrstva → jeden ISOM symbol (jako budovy→521, vedení→510, železnice→509).
# ZABAGED táhne BODOVÉ 204/207 + LINIOVÉ 208; plochu 206 už NE — `Skalní_útvary` (generalizovaný
# blok přes masiv) nahradil DMR rock-reliéf (`generator/rock_relief.py`, Sez. 63: věrná členitost
# věží z výškopisu). Proto zde ROCK_AREA_LAYERS / fetch_rock_areas / map_rock_area_to_isom NEJSOU.
# Sesuv_půdy__suť (→ 210 Stony ground) zůstává odloženo (Σ1 v probe Sez. 55, marginální).
# Skupina_balvanů__linie_ (→ 208 Boulder field) realizováno Sez. 57 (změřeno Σ14, ne „3" jak
# tvrdil Sez. 30 odhad — probe Sez. 55: SV 7 / HS 3 / NV 4).
BOULDER_LAYERS = ("Osamělý_balvan__skála__skalní_suk",)            # bodové „turisticky významné"
BOULDER_CLUSTER_LAYERS = ("Skupina_balvanů__bod_",)                # bodová pole drobných kamenů (bod)
BOULDER_FIELD_LINE_LAYERS = ("Skupina_balvanů__linie_",)          # liniová pole balvanů → 208 (buffer pás)

# Mosty / tunely / lávky (Sez. 32 znovu, spec-driven po rollbacku Sez. 31).
# Verify-against-source: foto reálných OB map (uživatel) + ISOM 2017-2 PDF str. 32 + Q&A.
# Klíčové rozhodnutí Sez. 32: most a tunel sdílí ISOM 512 ALE mají SHODNÝ LAYOUT (závorky
# JEN na koncích linie), liší se jen viditelností trati mezi závorkami:
#   Most  = trať PLNÁ mezi závorkami (silnice/železnice viditelná, jen závorky vymezují vstup/výstup)
#   Tunel = trať VYNECHANÁ mezi závorkami (terén skrz, jako bys trať „smazal" v daném úseku)
# Lávka = single dash (template 512.2, kolmá čárka 1,25 mm × 0,25 mm) — pro krátké lávky bez cesty.
# `Most` (id 73, LineString) a `Tunel` (id 74, LineString) jsou samostatné ZABAGED vrstvy
# (NE ve stejném balíku — Sez. 31 fail). `Lávka (linie)` (67) + `Lávka (bod)` (66) = 2 vrstvy
# stejného typu lávky podle geometrické reprezentace.
BRIDGE_LAYERS = ("Most",)                                # most → 512 (osa plná, závorky na koncích)
TUNNEL_LAYERS = ("Tunel",)                               # tunel → 512 (osa vynechaná, závorky na koncích)
FOOTBRIDGE_LINE_LAYERS = ("Lávka (linie)",)              # lávka linie → 512.2 (single dash)
FOOTBRIDGE_POINT_LAYERS = ("Lávka (bod)",)               # lávka bod → 512.2 (single dash)


def _fetch_layer(layer: str, bbox: tuple[float, float, float, float],
                 cache_dir: Path) -> dict:
    """Stáhne jednu vrstvu jako GeoJSON FeatureCollection (REST query + paging, cache na disk).

    `bbox` = (xmin, ymin, xmax, ymax) v S-JTSK (z build_bbox). Mapuje ZABAGED vrstvu NAME→ID
    (LAYER_IDS) a deleguje na sdílený `arcgis.fetch_geojson_layer` (Sez. 42, DRY paging+cache
    se sourozencem ruian.py). REST `MapServer/<id>/query` s envelope filtrem vrátí prvky
    protínající výsek; `f=geojson` → tatáž struktura jako dřív WFS (parsery `_geom_to_*` beze
    změny). Server omezuje dávku na `_PAGE` (2000) → paging přes resultOffset (Sez. 26).

    Cache key má prefix `zbg_rest_<layer>` (odlišení od staré WFS cache i od RÚIAN cache);
    formát klíče zachován z dřívějška → existující cache se NEinvaliduje. Izomorfní s dmr cache.
    """
    lid = LAYER_IDS.get(layer)
    if lid is None:
        raise ValueError(f"Vrstva {layer!r} nemá REST layer ID (doplň do LAYER_IDS).")
    return fetch_geojson_layer(_REST_SERVER, lid, bbox, cache_dir,
                               page_size=_PAGE, cache_key=f"zbg_rest_{layer}")


# --- sdílené tělo prostých fetch_* funkcí (DRY, Sez. 50) -------------------------------
# 14 fetch_* funkcí mělo IDENTICKÉ tělo lišící se jen vrstvami, parserem geometrie a klíčem
# výstupu — izomorfismus dotažený do copy-paste (audit Sez. 50). Dva helpery to sjednocují:
# liniové/plošné features (`_collect_features`) a body (`_collect_points`). Speciální fetch
# (landmarks centroid, state_border filtr+coords) zůstávají vlastní.
def _collect_features(layers, lat: float, lon: float, gw: int, gh: int, tile_m: float,
                      cache_dir: str | Path | None, parser, key: str) -> list[dict]:
    """Stáhne `layers` → [{"layer", "props", key: geometrie}]. `parser` = `_geom_to_lines`
    (klíč "lines") nebo `_geom_to_polygons` (klíč "rings"); prázdná geometrie se přeskočí."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[dict] = []
    for layer in layers:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            geom = parser(feat.get("geometry") or {})
            if geom:
                out.append({"layer": layer, "props": feat.get("properties", {}), key: geom})
    return out


def _collect_points(layers, lat: float, lon: float, gw: int, gh: int, tile_m: float,
                    cache_dir: str | Path | None, predicate=None) -> list[tuple[float, float]]:
    """Stáhne bodové `layers` → [(x, y)] v S-JTSK. Volitelný `predicate(props)` filtr (řopíky
    typbunkr_k, …). Sdílené tělo fetch_powerline_masts/fetch_boulders/fetch_bunkers (Sez. 50)."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[tuple[float, float]] = []
    for layer in layers:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            if predicate is None or predicate(feat.get("properties", {})):
                out.extend(_geom_to_points(feat.get("geometry") or {}))
    return out


def fetch_paths(lat: float, lon: float, gw: int, gh: int,
                tile_m: float = 1000.0,
                cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné komunikace pro výsek (lat, lon) jako seznam liniových features.

    Každý prvek: {"layer": název vrstvy, "props": atributy ZABAGED, "lines": [[(x,y)..]]}
    — `lines` je seznam polylinií v S-JTSK metrech (MultiLineString rozbalen na části).
    Mapování na ISOM symbol se dělá výš (po verify atributů, Sez. 16).

    Výsek je TENTÝŽ jako u dmr.fetch_elevation_grid (sdílený build_bbox) → cesty sednou
    na terén bez dalšího georef počítání.
    """
    return _collect_features(PATH_LAYERS, lat, lon, gw, gh, tile_m, cache_dir, _geom_to_lines, "lines")


def fetch_forest_rides(lat: float, lon: float, gw: int, gh: int,
                       tile_m: float = 1000.0,
                       cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné lesní průseky pro výsek (lat, lon) jako seznam liniových features.

    Každý prvek: {"layer", "props", "lines": [[(x,y)..]]} — polylinie v S-JTSK metrech
    (MultiLineString rozbalen). Mapování na ISOM (map_ride_to_isom → 508) se dělá výš (Sez. 36).
    Izomorfní s fetch_paths/fetch_railways (linie). Tentýž výsek (sdílený build_bbox) → průsek
    sedne na terén i k cestám. V bezlesém výseku = 0 prvků (žádný šum)."""
    return _collect_features(RIDE_LAYERS, lat, lon, gw, gh, tile_m, cache_dir, _geom_to_lines, "lines")


def fetch_railways(lat: float, lon: float, gw: int, gh: int,
                   tile_m: float = 1000.0,
                   cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné železniční tratě pro výsek (lat, lon) jako seznam liniových features.

    Každý prvek: {"layer", "props": atributy ZABAGED, "lines": [[(x,y)..]]} — `lines` je
    seznam polylinií v S-JTSK metrech (MultiLineString rozbalen). Mapování na ISOM
    (map_railway_to_isom → 509) se dělá výš, po verify atributů (Sez. 28).

    Izomorfní s fetch_paths/fetch_powerlines (linie). Tentýž výsek (sdílený build_bbox) →
    trať sedne na terén i k cestám/vodě. V lesních výsecích bez trati = 0 prvků (žádný šum).
    """
    return _collect_features(RAILWAY_LAYERS, lat, lon, gw, gh, tile_m, cache_dir, _geom_to_lines, "lines")


def fetch_paved_areas(lat: float, lon: float, gw: int, gh: int,
                      tile_m: float = 1000.0,
                      cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné zpevněné plochy (kolejiště → 501; parkoviště + ostatní plocha v sídlech → 501.1)
    pro výsek (lat, lon) jako plošné features.

    Každý prvek: {"layer", "props", "rings": [[outer, díra…]..]} — polygony (s děrami, Sez. 54)
    v S-JTSK metrech. Mapování na ISOM (map_paved_to_isom → 501/501.1) se dělá výš (Sez. 28/54/57).
    Izomorfní s fetch_buildings/area-půlkou fetch_water. V lesních výsecích bez nádraží/sídla = 0
    prvků (žádný šum). Tentýž výsek (sdílený build_bbox)."""
    # 501.1 (ostatní plocha v sídlech + parkoviště) PRVNÍ → kreslí se VESPOD paved kanálu (base výplň
    # pod kolejištěm 501; z-order = pořadí features × urban_base průchod, Sez. 54/57).
    return _collect_features(OTHER_URBAN_AREA_LAYERS + PAVED_AREA_LAYERS,
                             lat, lon, gw, gh, tile_m, cache_dir, _geom_to_polygons, "rings")


def fetch_water(lat: float, lon: float, gw: int, gh: int,
                tile_m: float = 1000.0,
                cache_dir: str | Path | None = None) -> tuple[list[dict], list[dict]]:
    """Vrátí reálnou vodu pro výsek (lat, lon): (line_feats, area_feats).

    `line_feats` = vodní toky (Vodní_tok): [{"layer", "props", "lines": [[(x,y)..]]}]
    `area_feats` = vodní plochy (Vodní_plocha): [{"layer", "props", "rings": [[(x,y)..]]}]
    — `rings` jsou vnější obrysy ploch (díry ignorujeme; malé rybníky je nemají).
    Mapování na ISOM (map_water_to_isom) se dělá výš, po verify atributů (Sez. 17).

    Tentýž výsek jako dmr/cesty (sdílený build_bbox) → voda sedne na terén i k cestám.
    Izomorfní s fetch_paths; oddělené linie/plochy, protože render i ISOM symbol se liší.
    """
    line_feats = _collect_features(WATER_LINE_LAYERS, lat, lon, gw, gh, tile_m, cache_dir,
                                   _geom_to_lines, "lines")
    area_feats = _collect_features(WATER_AREA_LAYERS, lat, lon, gw, gh, tile_m, cache_dir,
                                   _geom_to_polygons, "rings")
    return line_feats, area_feats


def fetch_buildings(lat: float, lon: float, gw: int, gh: int,
                    tile_m: float = 1000.0,
                    cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné budovy pro výsek (lat, lon) jako seznam plošných features.

    Každý prvek: {"layer", "props": atributy ZABAGED, "rings": [[(x,y)..]]} — `rings`
    jsou vnější obrysy budov v S-JTSK metrech (MultiPolygon rozbalen). Bodová vrstva
    budov se netáhne (v lesních výsecích prázdná, viz BUILDING_AREA_LAYERS). Mapování
    na ISOM (map_building_to_isom) se dělá výš, po verify atributů (Sez. 18).

    Izomorfní s area-půlkou fetch_water (plochy mají rings, ne lines). Tentýž výsek
    (sdílený build_bbox) → budovy sednou na terén i k cestám/vodě.
    """
    # Budovová kategorie = běžné budovy/kůlny/zámek/hrad (→ 521) + zříceniny (→ 523, Sez. 43).
    # map_building_to_isom rozliší ISOM kód podle vrstvy (mirror skály: víc vrstev → víc kódů, 1 fetch).
    return _collect_features((*BUILDING_AREA_LAYERS, *RUIN_AREA_LAYERS),
                             lat, lon, gw, gh, tile_m, cache_dir, _geom_to_polygons, "rings")


def fetch_powerlines(lat: float, lon: float, gw: int, gh: int,
                     tile_m: float = 1000.0,
                     cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné el. vedení pro výsek (lat, lon) jako seznam liniových features.

    Každý prvek: {"layer", "props": atributy ZABAGED, "lines": [[(x,y)..]]} — `lines` je
    seznam polylinií v S-JTSK metrech (MultiLineString rozbalen). Mapování na ISOM
    (map_powerline_to_isom → 510) se dělá výš, po verify atributů (Sez. 24).

    Izomorfní s fetch_paths (linie). Tentýž výsek (sdílený build_bbox) → vedení sedne na
    terén i k cestám/vodě. Vzor pro budoucí doplňování dalších liniových vrstev z katalogu.
    """
    return _collect_features(POWERLINE_LAYERS, lat, lon, gw, gh, tile_m, cache_dir, _geom_to_lines, "lines")


def fetch_powerline_masts(lat: float, lon: float, gw: int, gh: int,
                          tile_m: float = 1000.0,
                          cache_dir: str | Path | None = None) -> list[tuple[float, float]]:
    """Vrátí polohy stožárů el. vedení pro výsek jako seznam bodů (x, y) v S-JTSK metrech.

    Stožáry (`Stožár_elektrického_vedení`, geom Point) nesou polohu SLOUPŮ → reálná data
    pro kolmé příčky symbolu ISOM 510 (fáze 1, Sez. 24; ověřeno: stožár leží na vrcholu
    linie vedení). Atributy (výška) jsou v datech prázdné → vracíme jen souřadnice.
    Tentýž výsek (sdílený build_bbox) jako linie vedení → příčky sednou na vedení."""
    return _collect_points(POWERLINE_MAST_LAYERS, lat, lon, gw, gh, tile_m, cache_dir)


def fetch_bunkers(lat: float, lon: float, gw: int, gh: int,
                  tile_m: float = 1000.0,
                  cache_dir: str | Path | None = None) -> list[tuple[float, float]]:
    """Vrátí polohy řopíků (lehkých opevnění LO37) pro výsek jako body (x, y) v S-JTSK metrech.

    ZABAGED `Bunkr` (bodová vrstva); filtr `typbunkr_k='LO37'` = lehký objekt vz.37 čs.
    pohraničního opevnění (= řopík). Ostatní typy bunkru (těžké, atypické) se zatím vynechávají.
    Na OB mapě se nekreslí jako prostý symbol, ale jako asset (řopík ≠ budova) — orientace
    + placement řeší generátor. Izomorfní s fetch_powerline_masts (body). Sez. 27."""
    return _collect_points(BUNKER_LAYERS, lat, lon, gw, gh, tile_m, cache_dir,
                           predicate=lambda p: p.get("typbunkr_k") == BUNKER_TYPE_LO37)


def fetch_state_border(lat: float, lon: float, gw: int, gh: int,
                       tile_m: float = 1000.0,
                       cache_dir: str | Path | None = None) -> list[list[tuple[float, float]]]:
    """Vrátí linie STÁTNÍ hranice protínající výsek jako polylinie (x, y) v S-JTSK metrech.

    ZABAGED `Hranice správní jednotky` nese všechny správní hranice; filtr `vyzn_zsh_k='1'`
    vybere státní (ostatní = obec/okres/KÚ, nezajímají). Slouží k orientaci řopíku „ven" =
    směr k nejbližší státní hranici (univerzální ČR — sever u SV, JV u Šumavy; Sez. 27).
    Prázdné, když výsek hranici neprotíná (vnitrozemí). Izomorfní s fetch_powerlines (linie)."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    out: list[list[tuple[float, float]]] = []
    for layer in STATE_BORDER_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            if str(feat.get("properties", {}).get("vyzn_zsh_k")) == STATE_BORDER_CODE:
                out.extend(_geom_to_lines(feat.get("geometry") or {}))
    return out


def fetch_boulders(lat: float, lon: float, gw: int, gh: int,
                   tile_m: float = 1000.0,
                   cache_dir: str | Path | None = None) -> list[tuple[float, float]]:
    """Vrátí polohy osamělých balvanů/skal/skalních suků pro výsek jako body (x, y) v S-JTSK.

    ZABAGED `Osamělý_balvan__skála__skalní_suk` (bodová vrstva, id 10). Ověřeno Sez. 30 na
    Hrubé Skále (6 prvků, jen `jmeno` jako atribut — žádný typ/velikost) → všechny mapujeme
    na 204 (KISS, jako řopíky/stožáry). Mapování na ISOM kód (map_boulder_to_isom → 204) se
    dělá výš. Izomorfní s fetch_powerline_masts/fetch_bunkers (body). Vzácné objekty
    (Hruboskalsko, klasická skalní oblast: 6/24 km² ≈ 0,25/km²) — atributy navíc nejsou."""
    return _collect_points(BOULDER_LAYERS, lat, lon, gw, gh, tile_m, cache_dir)


def fetch_boulder_clusters(lat: float, lon: float, gw: int, gh: int,
                           tile_m: float = 1000.0,
                           cache_dir: str | Path | None = None) -> list[tuple[float, float]]:
    """Vrátí polohy skupin balvanů (boulder clusters) pro výsek jako body (x, y) v S-JTSK.

    ZABAGED `Skupina_balvanů__bod_` (bodová vrstva, id 12). Bodová varianta — skupina je
    natolik těsná, že se nevykresluje per-balvan. Verify Sez. 30 (Hrubá Skála): 168 prvků
    (= 7/km², hojné), jen `jmeno` jako atribut → vše → 207 Boulder cluster (KISS). Liniová
    varianta `Skupina_balvanů__linie_` (id 13) jde zvlášť přes `fetch_boulder_field_lines`
    → ISOM 208 Boulder field (realizováno Sez. 57; změřeno Σ14, ne „3" z odhadu Sez. 30).
    Izomorfní s fetch_boulders."""
    return _collect_points(BOULDER_CLUSTER_LAYERS, lat, lon, gw, gh, tile_m, cache_dir)


def fetch_boulder_field_lines(lat: float, lon: float, gw: int, gh: int,
                              tile_m: float = 1000.0,
                              cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí osy liniových polí balvanů (`Skupina_balvanů__linie_`) pro výsek (Sez. 57).

    Každý prvek: {"layer", "props", "lines": [[(x,y)..]]} (S-JTSK; MultiLineString rozbalen) =
    ČISTÁ DATA (osa), bez bufferu — plošný pás (ISOM 208 Boulder field) staví generátor, stejně
    jako u stromořadí 406 (`fetch_tree_rows`). ZABAGED modeluje pole balvanů jako linii (osu),
    fyzicky je to protáhlá plocha → buffer na pás. Vrstva má jen `jmeno` → KISS vždy 208."""
    return _collect_features(BOULDER_FIELD_LINE_LAYERS, lat, lon, gw, gh, tile_m, cache_dir,
                             _geom_to_lines, "lines")


def fetch_bridges(lat: float, lon: float, gw: int, gh: int,
                  tile_m: float = 1000.0,
                  cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné mosty (ZABAGED `Most` linie) pro výsek jako seznam liniových features.

    Každý prvek: {"layer", "props", "lines": [[(x,y)..]]} — `lines` jsou polylinie v S-JTSK
    metrech (LineString → single-line list, MultiLineString rozbalen). Mapování na ISOM
    (`map_bridge_to_isom` → 512) řeší generator.py. Izomorfní s fetch_railways.
    Sez. 32: most a tunel jsou ODDĚLENÉ funkce (`fetch_bridges` vs `fetch_tunnels`), na
    rozdíl od Sez. 31 sloučení — render se liší (most = osa plná, tunel = osa vynechaná)."""
    return _collect_features(BRIDGE_LAYERS, lat, lon, gw, gh, tile_m, cache_dir, _geom_to_lines, "lines")


def fetch_tunnels(lat: float, lon: float, gw: int, gh: int,
                  tile_m: float = 1000.0,
                  cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné tunely (ZABAGED `Tunel` linie) pro výsek jako seznam liniových features.

    Izomorfní s fetch_bridges. Tunel a most sdílí ISOM 512, ale render se liší (most osa
    plná, tunel vynechaná) → konektor je dělí, aby generator.py znal který je který."""
    return _collect_features(TUNNEL_LAYERS, lat, lon, gw, gh, tile_m, cache_dir, _geom_to_lines, "lines")


def fetch_footbridges(lat: float, lon: float, gw: int, gh: int,
                      tile_m: float = 1000.0,
                      cache_dir: str | Path | None = None
                      ) -> tuple[list[dict], list[tuple[float, float]]]:
    """Vrátí reálné lávky (ZABAGED `Lávka (linie)` + `Lávka (bod)`) pro výsek.

    Vrací (line_feats, points):
      - line_feats = liniové lávky: [{"layer", "props", "lines": [[(x,y)..]]}]
      - points = bodové lávky: [(x, y), ...] v S-JTSK metrech
    Obě → ISOM 512.2 Footbridge (single dash, template id=127). Bodová lávka NEnese
    orientaci v atributech → render rotuje kolmo k nejbližšímu vodnímu toku."""
    line_feats = _collect_features(FOOTBRIDGE_LINE_LAYERS, lat, lon, gw, gh, tile_m, cache_dir,
                                   _geom_to_lines, "lines")
    points = _collect_points(FOOTBRIDGE_POINT_LAYERS, lat, lon, gw, gh, tile_m, cache_dir)
    return line_feats, points


def fetch_open_land(lat: float, lon: float, gw: int, gh: int,
                    tile_m: float = 1000.0,
                    cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné otevřené plochy (louka/park/pole + sad/zahrada) pro výsek jako plošné features.

    Každý prvek: {"layer", "props", "rings": [[(x,y)..]]} — vnější obrysy ploch v S-JTSK
    metrech (MultiPolygon rozbalen). Mapování na ISOM (map_open_land_to_isom) výš (Sez. 41/47/49).
    Izomorfní s fetch_paved_areas/fetch_buildings. Druh plochy nese VRSTVA + atribut (louka 139 → 401,
    udržovaná zeleň 134 → 402/402.1 dle typ_pudy_k, pole 138 → 412, sad/zahrada 135 → 520 olivová).
    Les NENÍ open land (vegetace gate)."""
    return _collect_features(OPEN_LAND_LAYERS, lat, lon, gw, gh, tile_m, cache_dir,
                             _geom_to_polygons, "rings")


def fetch_cemeteries(lat: float, lon: float, gw: int, gh: int,
                     tile_m: float = 1000.0,
                     cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné hřbitovy pro výsek jako plošné features.

    Každý prvek: {"layer", "props", "rings": [[(x,y)..]]} — vnější obrysy v S-JTSK metrech.
    Mapování na ISOM (map_cemetery_to_isom → 520 Area that shall not be entered) výš (Sez. 41).
    Izomorfní s fetch_paved_areas. Umělá plocha, čistá projekce (žádný vegetace gate)."""
    return _collect_features(CEMETERY_LAYERS, lat, lon, gw, gh, tile_m, cache_dir,
                             _geom_to_polygons, "rings")


def fetch_quarries(lat: float, lon: float, gw: int, gh: int,
                   tile_m: float = 1000.0,
                   cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné kamenolomy (povrchová těžba) pro výsek jako plošné features (Sez. 56).

    Každý prvek: {"layer", "props", "rings": [[(x,y)..]]} — vnější obrysy v S-JTSK metrech.
    Mapování na ISOM (map_quarry_to_isom → 520 Area that shall not be entered) výš. Izomorfní
    s fetch_cemeteries. Oplocený těžební areál = out-of-bounds, čistá projekce (žádný gate)."""
    return _collect_features(QUARRY_LAYERS, lat, lon, gw, gh, tile_m, cache_dir,
                             _geom_to_polygons, "rings")


def fetch_marsh(lat: float, lon: float, gw: int, gh: int,
                tile_m: float = 1000.0,
                cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné mokřady (bažina/močál + rašeliniště) pro výsek jako plošné features (Sez. 44).

    Každý prvek: {"layer", "props", "rings": [[(x,y)..]]} — vnější obrysy v S-JTSK metrech
    (MultiPolygon rozbalen). Mapování na ISOM (map_marsh_to_isom → 308 Marsh) výš. Izomorfní
    s fetch_open_land/fetch_cemeteries. Klasický OB prvek (crossable marsh), čistá projekce."""
    return _collect_features(MARSH_AREA_LAYERS, lat, lon, gw, gh, tile_m, cache_dir,
                             _geom_to_polygons, "rings")


def fetch_utility_areas(lat: float, lon: float, gw: int, gh: int,
                        tile_m: float = 1000.0,
                        cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí reálné areály účelové zástavby (114) pro výsek jako plošné features.

    Každý prvek: {"layer", "props", "rings": [[(x,y)..]]} — vnější obrysy v S-JTSK metrech.
    `props` nese `typzast_k`/`typzast_p` (typ areálu) → map_utility_area_to_isom rozliší 520
    (areály) vs 501 (asfaltové dopravní plochy). Izomorfní s fetch_cemeteries. Render rozdělí
    generator podle ISOM kódu mezi surfaces (520) a paved (501) kanál (Sez. 42)."""
    return _collect_features(UTILITY_AREA_LAYERS, lat, lon, gw, gh, tile_m, cache_dir,
                             _geom_to_polygons, "rings")


def map_path_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED komunikaci na ISOM 2017-2 liniový symbol (kód).

    Klíč = FYZICKÝ stav (sjízdnost / zřetelnost), ne správní třída — tak rozlišuje
    ISOM. Ověřeno proti reálným datům (verify-against-source, Sez. 16): `povrch_k`
    Z/T = zpevněná, None = nezpevněná; `typuskom_k` 026 = udržovaná pěšina, jinak
    neudržovaná (REST: atribut malými; WFS ho měl velkými — Sez. 26). Mapovací tabulka:
      Silnice/Ulice     → 502 Wide road     (evidovaná, ≥5 m, autodoprava)
      Silnice neevid.   → 503 Road          (účelová/lesní asfaltka, zpevněná <5 m)
      Cesta zpevněná    → 503 Road          (sjízdná autem)
      Cesta nezpevněná  → 504 Vehicle track (vozová, jen pomalu sjízdná)
      Pěšina udržovaná  → 505 Footpath
      Pěšina neudrž.    → 506 Small footpath

    Vrací holý ISOM kód (int) — konektor nezná render konstanty generátoru (žádný
    cyklický import; generator.py kód interpretuje přes PATH_STYLE). Mapování není
    1:1 (správní třída ZABAGED vs zřetelnost/sjízdnost ISOM) — vědomá aproximace.
    """
    if layer in ("Silnice__dálnice", "Ulice"):
        return 502
    if layer == "Silnice_neevidovaná":
        return 503   # neevidovaná účelová/lesní asfaltka (zpevněná, <5 m) → Road, ne 502
    if layer == "Cesta":
        return 503 if props.get("povrch_k") in ("Z", "T") else 504
    if layer == "Pěšina":
        # pozor: REST vrací atribut malými (`typuskom_k`); WFS ho měl velkými (Sez. 26)
        return 505 if props.get("typuskom_k") == "026" else 506
    # No silent fallback (Sez. 110, ChatGPT %AUDIT:CODE): dřív neznámá vrstva tiše spadla na 503
    # (viditelná plná cesta) → přejmenovaná/nová ZABAGED vrstva (stalo se WFS→REST Sez. 26) by se
    # tvářila jako správná data. Selži nahlas — volající fetchuje jen známé PATH vrstvy.
    raise ValueError(f"map_path_to_isom: neznámá ZABAGED komunikační vrstva {layer!r} "
                     f"(props klíče: {sorted(props)[:8]}) — přidej mapování nebo oprav fetch filtr")


def map_ride_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED lesní průsek na ISOM 2017-2 liniový symbol (kód).

    `Lesní průsek` → **508 Narrow ride** (vždy; KISS, jako vedení→510 / železnice→509). Verify
    Sez. 36 (Soví vrch): 46 prvků, vrstva bez kategoriálního atributu (typ/šířka) → jeden symbol.
    508 = průhled lesem bez vyšlapané cesty (ISOM odlišuje od 503-506). Runnability pozadí se
    nekreslí (vegetace = UC5 predikce, ne data). Konektor vrací holý ISOM kód (int)."""
    return 508


def map_railway_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED železniční trať / tramvaj na ISOM 2017-2 liniový symbol (kód).

    `Železniční_trať` / `Železniční_vlečka` / `Tramvajová dráha` → **509 Railway** (vždy; KISS,
    jako budovy→521 / vedení→510). ISOM nerozlišuje trať podle počtu kolejí / elektrizace /
    tramvaje vs vlaku → jeden symbol. Sez. 31: oprava Sez. 28, kde tramvaj byla vynechána jako
    „urbánní" — chybělo to na LS (točna Lidové sady).

    Pozor (verify-against-source, Sez. 28): symbol 509 je v template_classic.omap kombinovaný
    (type=16: černé čárky + bílý „pražcový" knockout), NE prostá linie jako vedení 510. Konektor
    vrací jen holý ISOM kód (int) — render/styl zná generator.py (žádný cyklický import)."""
    return 509


def map_paved_to_isom(layer: str, props: dict) -> float:
    """Mapuje ZABAGED zpevněnou plochu na ISOM 2017-2 plošný symbol (kód).

    `Kolejiště` → **501 Paved area** (S obrysem; KISS, jako budovy→521). 501 je v template_classic.omap
    kombinovaný symbol (hnědá 50% výplň + obrysová linie). Volba 501 = rozhodnutí uživatele (Sez. 28):
    kolejiště = vymezený prostor („do kolejiště se nevstupuje") → zřetelná hranice = obrys (ISOM 501
    „where they have a distinct boundary").

    `Parkoviště, odpočívka` → **501.1 Paved area BEZ obrysu** (Sez. 57, oprava z 501). Parkoviště je
    PRŮCHOZÍ zpevněná plocha splývající s okolím (na rozdíl od vymezeného kolejiště) → bez obrysu (volba
    uživatele, OB praxe). Důsledek: 501.1 jde do spodního z-order průchodu (base výplň, jako níže).

    `Ostatní plocha v sídlech` (115) → **501.1 Paved area BEZ obrysu** (Sez. 54). Administrativní výplň
    zastavěného území; díry (budovy/zeleň/cesty) parser nově nese (Sez. 54) → 501.1 vyplní jen volné
    plochy mezi nimi (náměstí/dvory/parkoviště), ne celé sídlo (kontrast Sez. 53 bez děr = 41 % zality).
    Necelý kód 501.1 → float (render přes str(code), precedent 402.1/412.1). Konektor vrací holý ISOM
    kód — render zná generator.py (žádný cyklický import)."""
    if layer in ("Ostatní plocha v sídlech", "Parkoviště, odpočívka"):
        return 501.1
    return 501


def map_open_land_to_isom(layer: str, props: dict) -> float:
    """Mapuje ZABAGED otevřenou plochu na ISOM 2017-2 plošný symbol (kód).

    Druh plochy nese VRSTVA, u udržované zeleně navíc ATRIBUT (Sez. 47/53, land-cover):
      - `Orná půda a ostatní dále nespecifikované plochy` (138) → **412 Cultivated land**
        (žlutá + černý tečkový pattern, orientace k severu);
      - `Ovocný sad, zahrada` (135) → **520 Area that shall not be entered** (olivová). V ČR krajině
        jde převážně o zahrady u rodinných domů a chalup — oplocené, nepřístupné běžci → out-of-bounds,
        ne běhatelný ovocný sad (rozhodnutí uživatele Sez. 49, oprava Sez. 48 = chybné 413 Orchard).
      - `Udržovaná zeleň` (134) se ŠTĚPÍ podle atributu `typ_pudy_k` (Sez. 53, verify-against-source
        probe): `PO` „park, okrasná zahrada" → **402 Open land with scattered trees** (žlutá + BÍLÉ
        tečky = rozptýlené stromy); `UZ` „ostatní udržovaná zeleň" → **402.1 Open land with scattered
        bushes** (žlutá + ZELENÉ tečky = rozptýlené keře/záhony). Dnes celá vrstva → 401 (Sez. 41);
        uživatel rozlišil park/zeleň přes atribut. 402.1 je první „scattered bushes" zeleň z dat —
        gate neporušuje (tvrdý ZABAGED objekt nesoucí kategorii, mirror stromořadí 406, Sez. 45).
      - `Trvalý travní porost` (louka, 139) → **401 Open land** (plná žlutá; louka není kultura
        ani park → bez patternu).
    Pod ISOM min. plochou (412: 3×3 mm; 402/402.1: 9 mm²) plocha spadne na 401 (řeší render, ne mapper).
    Konektor vrací holý ISOM kód (int|float; 402.1 je necelý kód → float, render přes str(code))."""
    if layer == "Orná půda a ostatní dále nespecifikované plochy":
        return 412
    if layer == "Ovocný sad, zahrada":
        return 520
    if layer == "Udržovaná zeleň":
        # park/okrasná zahrada (PO) → 402 (bílé tečky); ostatní udržovaná zeleň (UZ) → 402.1 (zelené tečky)
        return 402 if props.get("typ_pudy_k") == "PO" else 402.1
    return 401


def map_cemetery_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED hřbitov na ISOM 2017-2 plošný symbol (kód).

    `Hřbitov` → **520 Area that shall not be entered** (vždy; KISS). ISOM 2017-2 nemá vlastní
    hřbitovní symbol (verify template Sez. 41) → 520 = olivová out-of-bounds plocha, tak se hřbitov
    na OB mapě kreslí. Umělá plocha, čistá projekce bez gate. Konektor vrací holý ISOM kód (int)."""
    return 520


def map_quarry_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED kamenolom na ISOM 2017-2 plošný symbol (kód, Sez. 56).

    `Povrchová těžba, lom` → **520 Area that shall not be entered** (vždy; KISS). Oplocený
    těžební areál se zákazem vstupu = olivová out-of-bounds plocha (volba uživatele, izomorfní
    s hřbitovem). NE 201 Impassable cliff: 201 je LINIE (hrana stěny), ZABAGED dává PLOCHU →
    plocha→plocha je věrná projekce, stěnu z plochy nedotahujeme (Σ1 marginální). `druhtez_p`
    nese druh těžby (kámen/…), ISOM ho nerozlišuje. Konektor vrací holý ISOM kód (int)."""
    return 520


def map_marsh_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED mokřad na ISOM 2017-2 plošný symbol (kód, Sez. 44).

    `Bažina, močál` + `Rašeliniště (plocha)` → **308 Marsh** (vždy; KISS). Crossable marsh
    (modrý vodorovný pattern). NE 307 Uncrossable marsh — data nenesou atribut překonatelnosti,
    crossable je default OB předpoklad (nepřekonatelnost = terénní znalost, viz crossability TODO).
    Konektor vrací holý ISOM kód (int)."""
    return 308


def map_utility_area_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED areál účelové zástavby (114) na ISOM 2017-2 plošný symbol (kód, Sez. 42).

    Klíč = `typzast_k` (typ areálu, 62 hodnot). Asfaltové dopravní plochy (408 autobusové nádraží,
    409 čerpací stanice) → **501 Paved area** (zpevněná); VŠE ostatní (škola, hřiště, sport, stadión,
    kasárna, průmysl, garáže, nemocnice, zahrádkářská osada, …) → **520 Area which shall not be
    entered** (olivová — oplocený areál, kam běžci nesmí; volba uživatele Sez. 42). `typzast_k` je
    v datech int → porovnání přes str(). Render rozdělí generator podle kódu (520→surfaces, 501→paved).
    """
    if str(props.get("typzast_k")) in PAVED_AREAL_TYPZAST:
        return 501
    return 520


def map_water_to_isom(layer: str, props: dict) -> int | None:
    """Mapuje ZABAGED vodní prvek na ISOM 2017-2 kód (int), nebo None = nekreslit.

    Klíč = FYZICKÝ stav (zřetelnost/charakter), ne správní třída — ISOM logika. Ověřeno
    proti reálným datům (verify-against-source, Sez. 17) na výřezu Svitávky:
      Vodní_tok podzemní (typtoku_k=004)   → None  (není na povrchu vidět → nekreslit)
      Vodní_tok občasný (vydattok_p)        → 306 Minor/seasonal water channel (čárkovaný)
      Vodní_tok stálý, pojmenovaný (hlavní) → 304 Crossable watercourse (silnější linie)
      Vodní_tok stálý, bezejmenný (přítok)  → 305 Small crossable watercourse (tenčí linie)
      Vodní_plocha                           → 301 Uncrossable body of water (výplň + břeh)
      Pozemní_nádrž (umělá vč. koupališť)    → 301 (Sez. 27; bazén/nádrž = vodní plocha na mapě)

    Hierarchie 304/305 podle pojmenovanosti toku (generalizovatelné — pojmenovaný tok je
    v ZABAGED evidovaný/významnější; ne hardcode konkrétní řeky). Vrací holý ISOM kód
    (int) nebo None; render konstanty zná generator.py (žádný cyklický import).
    """
    if layer == "Vodní_tok":
        if props.get("typtoku_k") == "004":       # podzemní tok → na povrchu neviditelný
            return None
        if props.get("vydattok_p") == "občasný":  # občasný (vysychající) tok
            return 306
        if props.get("jmeno"):                    # pojmenovaný stálý tok = hlavní
            return 304
        return 305                                 # bezejmenný stálý přítok
    if layer in ("Vodní_plocha", "Pozemní_nádrž"):  # Pozemní_nádrž = umělé nádrže/koupaliště (Sez. 27)
        return 301
    return None


def map_building_to_isom(layer: str, props: dict) -> int | None:
    """Mapuje ZABAGED budovu na ISOM 2017-2 kód (int), nebo None = nekreslit.

    Ověřeno proti reálným datům (verify-against-source, Sez. 18) na výřezu Soví vrch:
    `druhbud` = „budova blíže neurčená" (104×) / „vodojem zemní" (1×); `jmeno` None.
    Vodojem zemní mapuje uživatel (terénní mapér Soví vrchu) také na 521 — v rastru se
    chová jako malá budova (rozhodnutí Sez. 18). Mapování:
      Budova_..._plocha_ (jakýkoli druhbud)  → 521 Building (plošný černý symbol)
      Kůlna, skleník, fóliovník, přístřešek  → 521 Building (Sez. 42, drobné stavby)
      Zámek / Hrad                           → 521 Building (Sez. 43, historická stavba = budova)
      Rozvalina, zřícenina                   → 523 Ruin   (Sez. 43, čárkovaný obrys, ne plná výplň)

    Bez rozlišení podle `druhbud` (KISS — jen jeden druh na výřezu navíc). Vrací holý
    ISOM kód (int) nebo None; render konstanty zná generator.py (žádný cyklický import).
    """
    if layer in RUIN_AREA_LAYERS:        # zřícenina (Sez. 43) → 523 Ruin (čárkovaný obrys)
        return 523
    if layer in BUILDING_AREA_LAYERS:    # budovy + kůlny + zámek/hrad (Sez. 42/43) → 521 (DRY s konstantou)
        return 521
    return None


def map_powerline_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED el. vedení i lanovku/vlek na ISOM 2017-2 liniový symbol (kód).

    Ověřeno proti reálným datům (verify-against-source, Sez. 24) na výřezech Soví vrch (7
    linií) a Český ráj (2): atribut `NAPETI` (napětí) i `NAZEV` jsou v datech **prázdné**
    (None) → podle napětí NELZE rozlišit VN/VVN, takže žádné dělení 510 vs 511 Major power
    line. Vše → **510 Power line, cableway or skilift** (KISS, jako budovy → vždy 521).

    Lanovka/vlek (`Lanová dráha, lyžařský vlek`, Sez. 55) → **týž 510**: ISOM 510 je jeden
    symbol „Power line, cableway *or skilift*" (template id=121). Atribut `typ_ldv_k`
    (vlek/lanovka/kabinová) ISOM nerozlišuje → vždy 510.

    Pozor (oprava zděděného předpokladu): el. vedení je ISOM **510**, NE 516 (516 = Fence/plot;
    verify proti template_classic.omap, Sez. 24). Vrací holý ISOM kód (int)."""
    return 510   # NAPETI/typ_ldv_k nerozlišují → vše 510; render konstanty zná generator.py


def map_boulder_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED osamělý balvan na ISOM 2017-2 bodový symbol (kód).

    `Osamělý_balvan__skála__skalní_suk` → **204 Boulder** (vždy; KISS, jako budovy→521).
    Verify Sez. 30 (Hrubá Skála): vrstva má JEN atribut `jmeno` (žádný typ/velikost/výška) →
    nelze rozlišit balvan (204) od velkého balvanu (205) ani od „skalního suku" (206 plocha).
    Bezpečnější KISS než hádat: jeden symbol = jedna vrstva. Vrací holý ISOM kód (int).
    Pokud by ZABAGED někdy doplnil atribut (např. výška), rozšířit zde."""
    return 204


def map_boulder_cluster_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED skupinu balvanů (bod) na ISOM 2017-2 symbol (kód).

    `Skupina_balvanů__bod_` → **207 Boulder cluster** (vždy; KISS). Vrstva má jen `jmeno`
    (Sez. 30). 207 = trojúhelník, plný černý, orientace na sever (ISOM template id 36)."""
    return 207


def map_boulder_field_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED liniové pole balvanů na ISOM 2017-2 symbol (kód).

    `Skupina_balvanů__linie_` → **208 Boulder field** (vždy; KISS, vrstva má jen `jmeno`).
    ISOM 208 = plocha s náhodně rozmístěnými plnými trojúhelníky (template area_symbol id 38).
    Zdroj je LINIE (osa) → generátor ji buffruje na úzký pás a vyplní 208 (mirror 406 stromořadí)."""
    return 208


def map_landmark_to_isom(layer: str) -> int | str | None:
    """Mapuje ZABAGED bodový orientační prvek na ISOM 2017-2 symbol (kód, Sez. 43/44).

    KISS vrstva → jeden symbol (jako skály 204/207, budovy 521). Skupiny:
      věž/stožár/vodojem/silo/těžní věž/větrný mlýn/motor/tovární komín + věžovitá stavba → 524 High tower
      mohyla/pomník/náhrobek                                                → 526 Cairn
      kříž/sloup kulturního významu                                        → 530 Prom. man-made (ring)
      významný/osamělý strom, lesík                                        → 417 Prominent large tree
      pramen (zdroj podzemních vod)                                        → 312 Spring (Sez. 44)
      vstup do jeskyně / ústí šachty, štoly                                → "203.2" Cave (Sez. 44)
      nadzemní zásobní nádrž (plocha → centroid)                           → 311 Well/tank (Sez. 44)
    Vrací ISOM kód (int, NEBO str "203.2" — necelý kód) nebo None; render konstanty zná
    generator.py (žádný cyklický import). Volající i .omap pracují přes str(code) → míchání nevadí."""
    if layer in LANDMARK_POINT_LAYERS_524 or layer in LANDMARK_AREA_LAYERS_524:
        return 524
    if layer in LANDMARK_POINT_LAYERS_526:
        return 526
    if layer in LANDMARK_POINT_LAYERS_530:
        return 530
    if layer in LANDMARK_POINT_LAYERS_417:
        return 417
    if layer in LANDMARK_POINT_LAYERS_312:
        return 312
    if layer in LANDMARK_POINT_LAYERS_203_2:
        return "203.2"
    if layer in LANDMARK_AREA_LAYERS_311:
        return 311
    return None


def fetch_landmarks(lat: float, lon: float, gw: int, gh: int,
                    tile_m: float = 1000.0,
                    cache_dir: str | Path | None = None) -> list[tuple[float, float, str]]:
    """Vrátí bodové orientační prvky pro výsek jako (x, y, layer) v S-JTSK (Sez. 43).

    Bodové vrstvy (kříž/mohyla/věž/strom/…) → poloha přes _geom_to_points. Plošná
    `Věžovitá stavba` (footprint ~3 m²) → CENTROID polygonu (průměr vrcholů; ISOM 524 je bodový
    symbol). `layer` se nese dál → map_landmark_to_isom rozliší ISOM kód (mirror skály: víc vrstev,
    jeden fetch). Izomorfní s fetch_boulders/fetch_boulder_clusters (body)."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    point_layers = (*LANDMARK_POINT_LAYERS_524, *LANDMARK_POINT_LAYERS_526,
                    *LANDMARK_POINT_LAYERS_530, *LANDMARK_POINT_LAYERS_417,
                    *LANDMARK_POINT_LAYERS_312, *LANDMARK_POINT_LAYERS_203_2)  # Sez. 44 pramen/jeskyně
    out: list[tuple[float, float, str]] = []
    for layer in point_layers:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            for x, y in _geom_to_points(feat.get("geometry") or {}):
                out.append((x, y, layer))
    # plošné věžovité stavby (524) + nádrže (311) → centroid (průměr vrcholů vnějšího ringu)
    for layer in (*LANDMARK_AREA_LAYERS_524, *LANDMARK_AREA_LAYERS_311):
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            for poly in _geom_to_polygons(feat.get("geometry") or {}):
                outer = poly[0] if poly else None       # poly = [vnější, díra…]; centroid z vnějšího (Sez. 54)
                if outer:
                    cx = sum(p[0] for p in outer) / len(outer)
                    cy = sum(p[1] for p in outer) / len(outer)
                    out.append((cx, cy, layer))
    return out


def map_line_feature_to_isom(layer: str) -> int | None:
    """Mapuje ZABAGED liniový orientační prvek na ISOM 2017-2 symbol (kód, Sez. 43).

    KISS vrstva → jeden symbol: Stupeň,sráz → 104 Earth bank; Zeď/Hradba → 513 Wall.
    Vrací holý ISOM kód (int) nebo None. (`Liniová vegetace` už NENÍ zde — stromořadí jde
    plošně jako 406 lineární les, viz fetch_tree_rows/map_tree_row_to_isom, Sez. 45.)"""
    if layer in LINE_FEATURE_LAYERS_104:
        return 104
    if layer in LINE_FEATURE_LAYERS_513:
        return 513
    if layer in LINE_FEATURE_LAYERS_107:
        return 107
    return None


def fetch_line_features(lat: float, lon: float, gw: int, gh: int,
                        tile_m: float = 1000.0,
                        cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí liniové orientační prvky pro výsek (Sez. 43): sráz 104 / zeď 513 / rokle 107 (Sez. 58).

    Každý prvek: {"layer", "props", "lines": [[(x,y)..]]} (S-JTSK; MultiLineString rozbalen).
    Mapování na ISOM (map_line_feature_to_isom) výš. Izomorfní s fetch_powerlines/fetch_railways."""
    return _collect_features((*LINE_FEATURE_LAYERS_104, *LINE_FEATURE_LAYERS_513, *LINE_FEATURE_LAYERS_107),
                             lat, lon, gw, gh, tile_m, cache_dir, _geom_to_lines, "lines")


def _nearest_wall_tangent(p: tuple[float, float],
                          walls: list[list[tuple[float, float]]]) -> tuple[float, tuple[float, float]]:
    """Nejbližší segment zdí 513 k bodu `p`: vrátí (vzdálenost [m], jednotková tangenta (tdx,tdy)).

    Bez segmentů → (inf, (1,0)). Tangenta = směr nejbližšího segmentu zdi (orientace „brány" 519)."""
    px, py = p
    best_d, best_t = float("inf"), (1.0, 0.0)
    for ln in walls:
        for i in range(len(ln) - 1):
            ax, ay = ln[i]
            bx, by = ln[i + 1]
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            if seg2 == 0.0:
                continue
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
            qx, qy = ax + t * dx, ay + t * dy
            d = ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5
            if d < best_d:
                seg = seg2 ** 0.5
                best_d, best_t = d, (dx / seg, dy / seg)
    return best_d, best_t


def fetch_barriers(lat: float, lon: float, gw: int, gh: int,
                   tile_m: float = 1000.0,
                   cache_dir: str | Path | None = None) -> list[tuple[float, float, float, float]]:
    """Vrátí zábrany ležící NA nosné zdi 513 jako (x, y, tdx, tdy) v S-JTSK (Sez. 52).

    ISOM 519 Crossing point = průchod plotem/zdí, ne závora na cestě → bod `Zábrana` se mapuje
    POUZE pokud leží ≤ BARRIER_MAX_WALL_DIST_M od linie 513 (zeď/hradba); ostatní (závory na
    lesních/účelových cestách, medián 183 m od zdi — verify Sez. 52) se zahodí. (tdx,tdy) =
    jednotková tangenta nosné zdi (orientace symbolu „brány"); generator ji přepočte do gridu.
    Izomorfní s řopíky (orientovaný bod vázaný na linii), jen orientace = tangenta (ne normála)."""
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / ".zabaged_cache"
    bbox = build_bbox(lat, lon, gw, gh, tile_m)
    walls: list[list[tuple[float, float]]] = []           # nosné zdi 513 (linie)
    for layer in BARRIER_WALL_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            walls.extend(_geom_to_lines(feat.get("geometry") or {}))
    out: list[tuple[float, float, float, float]] = []     # zábrany u zdi → bod + tangenta
    for layer in BARRIER_LAYERS:
        fc = _fetch_layer(layer, bbox, cache_dir)
        for feat in fc.get("features", []):
            for x, y in _geom_to_points(feat.get("geometry") or {}):
                dist, (tdx, tdy) = _nearest_wall_tangent((x, y), walls)
                if dist <= BARRIER_MAX_WALL_DIST_M:
                    out.append((x, y, tdx, tdy))
    return out


def map_tree_row_to_isom(layer: str) -> int:
    """Stromořadí (`Liniová vegetace`) → ISOM 406 Vegetation: slow running (Sez. 45).

    KISS vrstva → vždy 406. Reprezentace = úzký plošný pás („lineární les"); buffer osy na
    plochu dělá generátor (šířka pásu = kartografická volba, ne data)."""
    return 406


def fetch_tree_rows(lat: float, lon: float, gw: int, gh: int,
                    tile_m: float = 1000.0,
                    cache_dir: str | Path | None = None) -> list[dict]:
    """Vrátí osy stromořadí (`Liniová vegetace`) pro výsek (Sez. 45). Každý prvek:
    {"layer", "props", "lines": [[(x,y)..]]} (S-JTSK; MultiLineString rozbalen) = ČISTÁ DATA
    (osa), bez bufferu — plošný pás (406) staví generátor. Mirror fetch_line_features."""
    return _collect_features(TREE_ROW_LAYERS, lat, lon, gw, gh, tile_m, cache_dir, _geom_to_lines, "lines")


def map_bridge_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED most (linie) na ISOM 2017-2 symbol (kód).

    `Most` → **512 Bridge/tunnel** (vždy; KISS). Sez. 32 spec-driven: ISOM 2017-2 PDF
    str. 32 + foto reálné OB mapy ukazují most jako symbol 512 s **závorkami JEN na
    koncích linie** (= start_symbol + end_symbol v line_symbol), trať mezi nimi viditelná."""
    return 512


def map_tunnel_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED tunel (linie) na ISOM 2017-2 symbol (kód).

    `Tunel` → **512 Bridge/tunnel** (vždy; KISS, stejný symbol jako most). Sez. 32 spec-
    driven: ISOM 2017-2 PDF str. 32 doslovně *„Bridges and tunnels are represented using
    the same basic symbols."* Foto reálné OB mapy: závorky na koncích, trať mezi nimi
    VYNECHANÁ (= úplně mizí, terén viditelný skrz; ne dashed). Generator vykreslí oba módy
    odlišně (most = osa plná, tunel = osa vynechaná), ZABAGED→ISOM kódování je shodné."""
    return 512


def map_footbridge_to_isom(layer: str, props: dict) -> int:
    """Mapuje ZABAGED lávku (linie nebo bod) na ISOM 2017-2 symbol (kód).

    `Lávka (linie)` i `Lávka (bod)` → **512.2 Footbridge** (vždy; KISS). Template
    `template_classic.omap` id=127 = point_symbol rotatable, kolmá čárka 1,25 mm × 0,25 mm
    = spec-konformní single dash. Sez. 32: vrátí 5122 jako int alias (string „512.2" se
    sub-tečkou se převede v omap_export podle ROTATABLE_CODES)."""
    return 5122   # = ISOM kód 512.2 jako int (DRY s ostatními ints)


# Pozn.: geom parsery `_geom_to_lines/_geom_to_polygons/_geom_to_points` byly přesunuty do
# sdíleného `arcgis.py` (Sez. 42, DRY se sourozencem ruian.py) a importují se nahoře pod
# původními jmény (`geom_to_* as _geom_to_*`) — call-sites zůstaly beze změny.


def _diagnostics(lat: float, lon: float) -> None:
    """Verify-against-source: stáhne výsek a vypíše bbox, počty, vzorek souřadnic a
    unikátní hodnoty klíčových atributů (typ/povrch) — podklad pro mapování → ISOM."""
    from collections import Counter

    GW, GH, TILE_M = 170, 116, 1000.0
    bbox = build_bbox(lat, lon, GW, GH, TILE_M)
    print(f"Lokalita ({lat}, {lon})  bbox S-JTSK = {tuple(round(v, 1) for v in bbox)}")
    feats = fetch_paths(lat, lon, GW, GH, TILE_M)
    print(f"Celkem features: {len(feats)}\n")
    by_layer: Counter = Counter(f["layer"] for f in feats)
    for layer in PATH_LAYERS:
        layer_feats = [f for f in feats if f["layer"] == layer]
        print(f"=== {layer}: {by_layer[layer]} features ===")
        if not layer_feats:
            continue
        # vzorek souřadnic — ověří axis order (x ≈ -700k easting, y ≈ -1000k northing)
        sample = layer_feats[0]["lines"][0][0]
        print(f"  vzorek souřadnice prvního bodu: {sample}")
        # unikátní hodnoty každého atributu (krátké → kódové sloupce pro mapování)
        keys = layer_feats[0]["props"].keys()
        for k in keys:
            vals = Counter(str(f["props"].get(k)) for f in layer_feats)
            if len(vals) <= 12:   # jen kategoriální (kódy/typy), ne FID/délky
                print(f"  {k}: {dict(vals)}")
        print()


if __name__ == "__main__":
    import sys
    lat = float(sys.argv[1]) if len(sys.argv) > 1 else 50.8214458
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else 14.6712747
    _diagnostics(lat, lon)
