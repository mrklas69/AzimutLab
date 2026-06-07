# GLOSSARY — AzimutLab

Terminologie projektu. Krátké definice + odkaz na zdroj pravdy (detail nekopírujeme —
DRY). Pojmy se zavádějí, jak je projekt potkává; doplňuj v `%END`.

## Doména — orientační běh a mapy

- **OB** — orientační běh; sportovní disciplína navigace v terénu podle mapy.
- **Runnability** (průchodnost / běhatelnost) — jak rychle se daným terénem dá běžet (hustota podrostu/
  vegetace, podloží). ISOM ji kóduje barvou: bílá = volný les (plná rychlost), zelená 406/408/410 (slow/walk/
  fight, čím tmavší tím pomaleji), žlutá = otevřený terén. **NENÍ land-use** — polygon „les" neřekne, zda je
  běhatelný či hustník; to open geodata nemají ([[vegetace-gate]]). Cíl UC5: predikovat runnability z geo-
  podkladů, GT = co kartograf nakreslil na reálné mapě (viz **Ground-truth** níže, IDEAS „UC5 runnability korpus").
- **ISOM** (International Specification for Orienteering Maps) — norma pro klasické
  lesní OB mapy (**verze 2017-2, nejnovější — Rev 6 z 2024**, příští až ISOM2030). Symboly,
  barvy, priority. Cílová sémantika projektu. Detail: `docs/kb/isom-issprom.md`. Pozor: Rev 6
  **přečíslovalo bodové symboly** (109/110/111 vs staré 2017 112/113/115 — Sez. 13). **Pozor 2: reálné
  české OB mapy (vč. Soví vrch v `resources/`) bývají v ISOM 2000 číslování** — kolize významů kódů s 2017-2
  (526=budova vs 521=High stone wall, 508 Less distinct path↔Narrow ride, 509 Narrow ride↔Railway; Sez. 37,
  [[domain-gap]]). Čísla se **recyklují** → **jediný tvrdý marker verze = `526` Building** (v 2017-2 neexistuje;
  empirie Sez. 38: 4/6 map v `resources/` = ISOM 2000). Crosswalk hotový: [[crosswalk]]. Generátor deklaruje
  verzi v `meta["isom"]` + `.omap` `<notes>` (ochrana proti záměně, Sez. 38).
- **ISSprOM** — sesterská norma pro sprintové / městské mapy (2019-2). Stejný kód ≠
  stejný symbol napříč ISOM/ISSprOM (např. budovy black vs gray).
- **Vrstevnice** (contour) — izolinie výškového pole, spojnice bodů stejné nadmořské
  výšky. ISOM symbol **101**. Z principu se nekříží a nekončí ve vzduchu.
- **Index contour** (zvýrazněná / hlavní vrstevnice) — každá pátá vrstevnice, silnější
  čára pro snazší čtení. ISOM symbol **102**. V generátoru každých 25 m.
- **Form line** (pomocná / doplňková vrstevnice) — čárkovaná vrstevnice na **poloviční ekvidistanci**
  (2,5 m) tam, kde běžné vrstevnice nezachytí tvar. ISOM **103** (template: dash 2,0 / break 0,2 mm, hnědá).
  ISOM ji povoluje **střídmě** a ZAKAZUJE jako „intermediate contour" (plošné zahuštění). Generátor
  `--terrain real` (Sez. 29): heuristika z DMR — kreslí jen kde **(1) mírný svah** (rozestup vrstevnic >
  `FORMLINE_SPACING_LIMIT_M`) **A (2) zakřivený terén** (`|Laplacián výšky| > FORMLINE_CURV_MIN`); rovnoměrný
  (lineární) svah → form line by jen kopírovala vrstevnici = vynechána. Min. délka 3 mm (přísněji než ISOM
  1,1 mm — bez „fousků"). Render break zvětšen 0,2→0,5 mm (rastr; `.omap` nese věrný symbol 103). GT maska
  `mask_formlines.png`, vektor v `contours.geojson`. Branžový precedent: [[karttapullautin]] (poloviční hladiny
  + filtr). Jen real terén (z DMR, ne ZABAGED vrstva); noise beze změny (proc baseline drží).
- **Ekvidistance** — svislý rozestup vrstevnic (v projektu 5 m).
- **Kopeček** (knoll) — malá vyvýšenina; je-li menší než zobrazitelná vrstevnicí, kreslí
  se bodovým symbolem. ISOM **109** (Small knoll, kulatý) / **110** (Small elongated knoll,
  protáhlý). Generátor je odvozuje z malých uzavřených vrstevnic (lokální max, Sez. 10).
  (Kódy dle ISOM 2017-2 Rev 6 — staré 2017 mělo 112/113, viz pozn. u ISOM.)
- **Prohlubeň** (depression) — malá terénní sníženina. ISOM **111** (Small depression,
  hnědý oblouk „⌣"; staré 2017 = 115). Generátor z malých uzavřených vrstevnic (lokální
  min). **112 Pit** (jiná feature class — umělá/erozní díra) generátor nedělá (neodvoditelný
  z výškopisu).
- **Kartografická generalizace** — zjednodušení reality pro čitelnost mapy. V generátoru zbyla jen
  (1) malý kopeček/prohlubeň → bodová značka místo prstence (§4.10). **Generalizace BUDOV byla zavržena
  (Sez. 27):** min. velikost (`_enforce_min_size`), Douglas-Peucker obrys, orthogonalizace/pravoúhlost
  (Sez. 27) i displacement (L2, Sez. 22) komolily skutečný tvar/polohu → smazáno, budovy kresleny **RAW
  jako voda**. Zásada: **generalizuj jen s důkazem, raw je default** (CLAUDE.md). [[budova-stavba]]
- **Draw order / priorita barev** — pořadí vykreslování vrstev v OOM. Určuje ho **pořadí (priorita)
  BAREV** v mapě (nižší priorita = navrch; Purple overprint = 0 = úplně navrch), NE pořadí symbolů
  ani objektů. Závazně definované IOF (*Printing and Colour Definitions*, kap. 7); krycí klony
  (*White over green*, *Black below brown*…) jsou jeho součást. `.omap` export generátoru zdědí
  draw order z template → color-table je doména editace v OOM, ne generátoru (Sez. 18). Pozn.:
  OOM ISOM 2017-2 sada má budovu 521 na prioritě 8 (pod vrstevnicí 6 — záměr: budova pod tratěmi).
- **Cesta / pěšina** — liniová komunikace. ISOM škála dle zřetelnosti/sjízdnosti:
  **502 Wide road** (silnice — hnědý pás s černými okraji, render `casing` s `C_ROAD` výplní; pozor:
  502 a 503 jsou v ISOM templatu STEJNĚ tlusté, liší se plná/čárkovaná) · **503 Road** (zpevněná,
  plná černá 2 px) · **504 Vehicle track** (vozová, nezpevněná, čárkovaná 2 px) · **505 Footpath**
  (pěšina, čárkovaná **1 px** — template 250 µm, Sez. 23) · **506 Small footpath** (malá/neudržovaná).
  Generátor má dvě větve (`--paths`): **proc** = procedurální Dijkstra least-cost (§9), hlavní 503 /
  vedlejší 505; **real** = reálné komunikace ze ZABAGED (Sez. 16; ArcGIS REST od Sez. 26), plná hierarchie 502-506 dle
  povrchu/udržovanosti. Vrstvy: `Silnice__dálnice`/`Ulice`→502, **`Silnice_neevidovaná`** (účelové/lesní
  asfaltky, Sez. 23)→503, `Cesta` zpevněná→503 / nezpevněná→504, `Pěšina`→505/506.
- **Vodní tok / vodní plocha** (hydrografie) — voda na OB mapě, modrá. Toky ISOM **304**
  Crossable watercourse (hlavní, pojmenovaný) / **305** Small crossable watercourse (přítok) /
  **306** Minor/seasonal water channel (občasný, čárkovaný); plochy **301** Uncrossable body
  of water (výplň + břehová linie). **312 Spring** (pramen — pozor, ne 313 = Prominent water
  feature). Generátor `--water real` (Sez. 17): reálná půlka ze ZABAGED `Vodní_tok`/`Vodní_plocha`
  + `Pozemní_nádrž` (umělé nádrže vč. **koupališť/bazénů** `podtypob_k='BA'` → 301, Sez. 27 — Lesní
  koupaliště LS chybělo, je nádrž ne `Vodní_plocha`); podzemní toky (`typtoku_k=004`) se nekreslí.
- **Mokřad / jeskyně / pramen / nádrž** (dávka 4, Sez. 44) — **308 Marsh** (crossable bažina/močál +
  rašeliniště, modrá vodorovná šrafa; `--marsh`), **312 Spring** (pramen, modré „U" ústím nahoru),
  **203.2 Cave or rocky pit** (vstup do jeskyně/šachty, černá „Λ" stříška hrotem nahoru = „with a distinct
  entrance"; **203.1** je naopak **V** hrotem dolů = „without entrance"), **311 Well/fountain/water tank**
  (nadzemní nádrž, modrý čtverec z centroidu). Pramen/jeskyně/nádrž jdou přes `--landmarks` (bodové).
  **Konvence OOM symbolů: osa +y = DOLŮ** (rastr neflipuje); špatný předpoklad zrcadlil cave/spring (audit Sez. 44).
- **Stromořadí / lineární les** (Sez. 45) — řada stromů podél cesty/meze (alej). ZABAGED `Liniová vegetace` (id 15).
  Generátor `--treerows real` → **406 Vegetation: slow running** (světle zelený pás). ISOM kreslí stromořadí buď
  řadou bodů 417/418 (nutné polohy kmenů) nebo plošně tenkým nepravidelným pásem („lineární les") — volíme **plošně**,
  protože data nesou jen osu: osa → buffer (šířka 0,7 mm) → pás, min. plocha 1,0 mm² (ISOM minimum dimensions).
  **NE 416 Distinct vegetation boundary** — to je HRANICE mezi porosty (kraj lesa / předěl uvnitř lesa), ne řada stromů
  (oprava sémantiky Sez. 45, verify spec). První zelená vegetační plocha generátoru; [[vegetace-gate]] neporušuje
  (tvrdý objekt z dat, ne hádaná hustota — izomorf s 308 Marsh).
- **Pole balvanů — Boulder field** (Sez. 57) — plocha pokrytá tolika rozházenými kameny, že nejdou značit
  jednotlivě. ISOM **208 Boulder field** = náhodně rozmístěné a otočené plné trojúhelníky (area pattern, density
  0,8-1/mm²). ZABAGED `Skupina_balvanů__linie_` (id 13) vede pole jako LINII (osu) → generátor ji buffruje na
  úzký pás 1,5 mm (TÝŽ mechanismus jako stromořadí výše: osa→pás) a vyplní 208. `.omap` je `area_symbol` 208
  (OOM vyplní trojúhelníky věrně z definice), rastr = px-tuned aproximace. ISOM „generally will not impact
  runnability" → tvrdý kamenný objekt, [[vegetace-gate]] neporušuje (jako skály 204/206/207). Doplňuje `--rocks`.
- **Skalní plochy 206 z DMR — rock-relief** (Sez. 63) — ISOM **206 Impassable cliff** plochy odvozené z DMR
  sklonu (práh 46° + scipy morfologie scelí stěny do bloku → contourpy vektorizace na polygony), modul
  `generator/rock_relief.py`. **NAHRADILO** ZABAGED `Skalní_útvary` jako zdroj 206 (generalizovaný blob → věrný
  reliéf z výškopisu); bodové skály 204/207 a pole 208 zůstaly ze ZABAGED. Národní pokrytí (i kde forest-age díry
  má). +dep `scipy` (`requirements.txt`). Hi-res fetch capnut `MAX_AREA_PX` (ImageServer 500 nad ~7 Mpx, Sez. 65).
- **Prostup / branka — Crossing point** (Sez. 52) — místo, kudy se PROJDE přes plot/zeď (branka, schůdky). ISOM
  **519 Crossing point** = dvě rovnoběžné čárky („brána"), bodový rotatable symbol. Generátor `--barriers real`:
  ZABAGED `Zábrana` (id 54, „Závora, brána") → 519, ale **jen bod ležící na nosné zdi 513 (≤ 5 m)** — 519 je
  průchod plotem, NE závora na cestě (ta se v OB nemapuje, běžec ji obejde). Závory na cestách se zahodí (verify
  Sez. 52: jen 2/66 na LS na zdi). Orientace symbolu = tangenta zdi; **nepřekonatelná zeď 513 se pod brankou
  PŘERUŠÍ** (ISOM „line broken at the crossing point"). Jediná orientovaná bodová vrstva vedle řopíků/lávek.
- **Komín — High tower** (Sez. 52) — `Tovární komín` (id 31) → **524 High tower** (jako věž/silo, `--landmarks`);
  vysoká štíhlá stavba = orientační bod. Atribut `vyska_obj` (výška) nevyužit (524 nemá výškové varianty → KISS).
- **Budova / stavba** — umělý objekt na OB mapě. ISOM **521 Building** (plošný černý symbol,
  výplň + obrys). Generátor `--buildings real` (Sez. 18): reálná půlka ze ZABAGED
  `Budova_jednotlivá_nebo_blok_budov__plocha_` (mapování `map_building_to_isom` → 521; vodojem
  taky 521). Render izomorfní s vodní plochou 301 (`_draw_area_symbol`), jen černá místo modré.
  **RAW půdorys (Sez. 27):** kresleno přesně jako voda (syrový ZABAGED ring), BEZ generalizace či
  displacementu — ty komolily tvar/polohu (viz [[kartografická-generalizace]]).
- **El. vedení + lanovka/vlek** — el. vedení i lanovka/lyžařský vlek na OB mapě. ISOM **510 Power line,
  cableway or skilift** = JEDEN symbol pro všechny tři (tenká černá linie s kolmými příčkami na SLOUPECH
  — běžci se jimi řídí). Generátor `--powerlines real` (Sez. 24 + 55): reálná půlka ze ZABAGED
  `Elektrické_vedení` + `Lanová dráha, lyžařský vlek` (linie → osa) + `Stožár_elektrického_vedení` /
  `Stožár lanové dráhy` (body → příčky). Lanovka sloučena do `--powerlines` (Sez. 55, ISOM 510 nerozlišuje
  zdroj). Mapování `map_powerline_to_isom` → vždy 510 (`NAPETI`/`typ_ldv_k` nerozlišují →
  bez rozlišení 511 Major power line). **Pozor: 510, NE 516** (516 = Fence/plot — oprava zděděného
  předpokladu, verify proti template, Sez. 24). Příčky = dvě fáze (viz [[pseudorealistic]]).
- **Železnice** — železniční trať na OB mapě. ISOM **509 Railway** — v `template_classic.omap` **kombinovaný
  symbol** (type 16): černé čárky (0,35 mm; dash 1,5 / break 1,0 mm) + bílý „pražcový" knockout (`White for
  railway`), NE prostá linie jako vedení 510. Generátor `--railways real` (Sez. 28): reálná půlka ze ZABAGED
  `Železniční_trať` (id 75) + `Železniční_vlečka` (76, nádražní/průmyslové vlečky — u nádraží svazek kolejí);
  obě → 509 (`map_railway_to_isom`, KISS). Render mode `"railway"` = bílý knockout podklad + černé čárky navrch
  → mezery jsou BÍLÉ (odliší od pěšiny 505, jejíž mezery ukazují terén). Pozor: vrstva je `Železniční_trať`,
  ne „Železnice" (oprava TODO, Sez. 28).
- **Kolejiště / zpevněná plocha** — nádražní kolejová plocha (a obecně zpevněné plochy). ISOM **501 Paved
  area** — kombinovaný symbol (hnědá výplň + **obrysová linie**). Generátor `--paved real` (Sez. 28): reálná
  plošná půlka ze ZABAGED `Kolejiště` (id 122; `map_paved_to_isom` → 501), render `_draw_paved_area`
  (`C_ROAD` výplň + `C_BROWN` obrys, izomorfní s vodní plochou/budovou). **„10 kolejí" u nádraží v datech
  NEJSOU linie — ZABAGED je generalizuje do jedné plochy `Kolejiště`** (Liberec hl. n. ~19 ha). V `.omap`
  jako **kombinovaný 501 (s obrysem)**, ne 501.1 bez obrysu — **do kolejiště se nevstupuje**, bounding line
  je významová (rozhodnutí uživatele, Sez. 28; viz [[crossability]]). Sym id 105 (501.1 = id 106, čistá plocha).
- **501.1 Paved area (bez obrysu) / „ostatní plocha v sídlech"** — ZABAGED `Ostatní plocha v sídlech` (id 115)
  → **501.1** (`--paved`, Sez. 54): administrativní výplň zastavěného území (náměstí/dvory/parkoviště mezi
  budovami), **bez obrysu** (defaultně přístupná, na rozdíl od 501 kolejiště). Obří děravé polygony — díry
  (budovy/zeleň/cesty) vykrojí **[[podpora děr (holes)]]**; kreslí se VESPOD (z-order base, pod 520). Barva
  **„Dolní hnědá 50%"** (rastr `C_PAVED` světlejší než silnice; omap color priority 35 dole — viz [[Horní vs
  Dolní hnědá 50%]]). První velkoplošná base výplň pod mnoha symboly → default ISOM paleta Mapperu nestačila.
- **Podpora děr (holes)** — plošné symboly (501.1, voda, budovy, pokryv…) nesou z GeoJSON vnitřní prsteny
  (výřezy). `geom_to_polygons` vrací `[vnější, díra1, …]`; rastr je vyřízne even-odd scanline, `.omap`
  hole-flagem (Sez. 54). Bez nich velký polygon zalije výsek (501.1 by zalilo 41 % sídla).
- **Horní vs Dolní hnědá 50%** — ISOM má dva color sloty stejného odstínu (Upper/Lower brown 50%, identické
  CMYK), lišící se **color-table prioritou** v OOM: Upper (silnice 502) NAD Lower (paved 501/501.1). Sez. 54:
  do `template_classic.omap` přidána vlastní „Dolní hnědá 50%" na prioritu úplně dole, aby velkoplošná 501.1
  base nepřekrývala silniční okraje (paměť `omap-colortable-base-fill-priority`).
- **Plošný pokryv / land-cover** — plošné využití území na OB mapě. Generátor `--surfaces real` (Sez. 41-53):
  reálná plošná půlka ze ZABAGED + RÚIAN → ISOM symboly. **Open land → 401** (plná ŽLUTÁ, bez obrysu): louka
  (`Trvalý travní porost`) — není kultura, bez patternu. **Udržovaná zeleň → 402 / 402.1** (Sez. 53): štěpení podle
  `typ_pudy_k` — park/okrasná zahrada (`PO`) → **402 …scattered trees** (žlutá + BÍLÉ tečky), ostatní udržovaná
  zeleň (`UZ`) → **402.1 …scattered bushes** (žlutá + ZELENÉ tečky C_GREEN2); min. 9 mm² → 401; 402.1 = první
  „scattered bushes" zeleň z dat, [[vegetace-gate]] neporušuje (tvrdý objekt, mirror 406). **Pole → 412
  Cultivated land** (Sez. 47-48): `Orná půda…` → žlutá + **černý tečkový pattern** (template 412.1; min. 9 mm² → 401).
  **Olivová → 520 Area which shall not be entered** (plná OLIVOVÁ, zákaz vstupu — „zelená" v hantýrce orienťáků),
  **pět zdrojů (Sez. 42 + 49 + 56):** hřbitov (`Hřbitov` ZABAGED, ISOM nemá vlastní) ∪ **sad/zahrada** (`Ovocný sad,
  zahrada` ZABAGED — zahrady u domů/chalup, oplocené; Sez. 49 oprava chybného 413 Orchard) ∪ **privátní pozemek
  u domu** (RÚIAN parcely druhu zahrada+zastavěná, viz [[druh-pozemku]]) ∪ **oplocené areály účelové zástavby**
  (ZABAGED `Areál účelové zástavby` 114 mimo asfaltové typy — škola/hřiště/sport/stadión/kasárna/průmysl…) ∪
  **kamenolom** (ZABAGED `Povrchová těžba, lom` 118, Sez. 56 — oplocený těžební areál; NE 201 Impassable cliff,
  protože 201 je linie a lom je plocha → plocha→plocha, kamenné útvary zůstávají v z-orderu nad olivovou).
  **Asfaltové dopravní areály** (autobusové nádraží/čerpací stanice, `typzast_k` 408/409) + parkoviště + kolejiště
  → **501** přes `--paved` (rozdělení 114 podle ISOM kódu: 520→surfaces, 501→paved). Kůlny/přístřešky (`Kůlna…`
  105) → 521 přes budovy. Render `_draw_surface_area`/`_draw_dotted_surface_area` (`outline=None`), barvy
  `C_YELLOW`/`C_OLIVE`, maska `mask_surfaces.png` (multi-class 1=open/2=olivová/3=pole/4=402 park/5=402.1 zeleň). **Z-order: ÚPLNĚ VESPOD**
  (olivová NAD žlutou/polem — privátní zahrada RÚIAN přemaže pokryv pod ní), les = bílá default = [[vegetace-gate]] (UC5).
  **Olivová 520 = DISSOLVE do bloků (Sez. 98):** RÚIAN katastr fragmentuje zástavbu na tisíce drobných parcel
  (LS 52 % výseku, 91–96 % objektů 520) → kartograf kreslí jeden souvislý blok. Všechny zdroje 520 → sběrná maska →
  `contourpy` vektorizace (`_dissolve_mask_to_polys`, reuse `rock_relief`, bez `shapely`) → souvislé bloky. Kompas přestřel 9×→1,3×.
- **Plot 516 Fence** (Sez. 98) — liniový symbol oplocení. ZABAGED plot nevede (Sez. 57) → kreslen jako
  **pseudorealistická dekorace (fáze 2, vypne `--only-real`)** po obvodu RÚIAN-privát bloků (zástavba, kde je
  oplocení věrohodné). Práh `FENCE_MIN_AREA_M2` 0,5 ha (kalibr. proti reálným mapám gen≈orig); obvod narovnán `_rdp`
  (přímé spojnice vrcholů); ticky DOVNITŘ pozemku (`_draw_fence_line` per-tick `_point_in_ring`, ISOM spec „tags inside").
  Jen `.omap` + rgb (vlastní GT maska zatím ne — linie mimo plošné Png2Area Y, Png2Line neexistuje).
- **Crossability (překonatelnost hranic)** — ISOM kóduje **stylem obrysu/linie, zda lze hranici překonat**:
  301 Uncrossable body of water (plný břeh = NEpřekonat, obíhat) vs 304/305/306 crossable watercourse
  (přebrodit/překročit); plný obrys nepřekonatelné plochy (301, kolejiště 501) = bariéra. Generátor to honoruje
  **volbou ISOM symbolu** (a tím i v GT masce přes třídu). Dluh (Sez. 28): všechny vodní plochy → 301, všechny
  toky → crossable → široká nepřekonatelná řeka by byla špatně (TODO). „Brodnost" jako terénní znalost =
  část [[projekce-vs-predikce|predikce]] (UC5), ne vždy atribut v datech.
- **noise-půlka / real-půlka** — dvě paralelní datové osy generátoru: *syntetická* (fraktální
  šum / procedurální cesty) vs *reálná* (ČÚZK DMR 5G výškopis / ZABAGED komunikace + voda + budovy
  + vedení + železnice + kolejiště + lesní průseky + skály + mosty/tunely/lávky + řopíky). Izomorfní:
  `--terrain noise|real` ↔ `--paths proc|real` ↔ `--water off|real` ↔ `--paved off|real` ↔
  `--buildings off|real` ↔ `--powerlines off|real` ↔ `--railways off|real` ↔ `--rides off|real` ↔
  `--rocks off|real` ↔ `--bridges off|real` ↔ `--ropiky off|real` ↔ `--surfaces off|real`. Nemíchat
  zdroje napříč osou. (Reálná půlka od Sez. 42 čerpá i z **RÚIAN** katastru, ne jen ZABAGED — viz [[RÚIAN]].)
- **Ground-truth (GT)** — referenční „pravdivá" anotace pro trénink/validaci modelu.
  Klíčová výhoda generátoru: každá vrstva je zároveň segmentační maska → GT zdarma.
  U reálné mapy (`map_gt.py`) labely 0–4 (průchodný/406/408/410/open), navíc **label 255 = ignore**
  (trénink přeskočí přes `ignore_index`). Ignore nese: (1) **fialový přetisk tratě** (kroužky kontrol,
  spojnice, čísla — ne ISOM runnability barva; Sez. 72); (2) **layout mimo mapové území** (legenda,
  control-description tabulka, titulek, tiráž, logo, papírový okraj — `_detect_map_area`, Sez. 73 část B):
  detekce z barevnosti, ne geometrie — mapa má sytou ISOM paletu, mimo-mapové bloky jsou černobílé/papír.
  Obojí izomorf k olivové 520 → label 0 (out-of-bounds = ne běhatelnost).

- **Řopík** (lehké opevnění, ŘOP vz.37) — betonový pohraniční bunkr (čs. opevnění 30. let). V ZABAGED
  bodová vrstva `Bunkr` (`typbunkr_k='LO37'`). Na OB mapě = bodový orientační prvek (NE budova 521):
  asset `ropik_10000.omap` (bunkr na náspu). Generátor `--ropiky real` (integrace Sez. 27): `fetch_bunkers`
  + asset placement; orientace = normála na lokální linii řopíků, „čelní zasypaný násep" VEN k nejbližší
  **státní hranici** (`Hranice správní jednotky` `vyzn_zsh_k='1'`, univerzální ČR — sever u SV, JV u Šumavy).
  Fáze 1 (projekce, real data), NE pseudorealistická dekorace. Sez. 26-27.

## Data a geoinformatika

- **ČÚZK** — Český úřad zeměměřický a katastrální. Od 1. 7. 2023 poskytuje hlavní sady
  jako open data **CC BY 4.0**. Detail + katalog: `docs/kb/data-sources.md`.
- **ZABAGED®** — Základní báze geografických dat; vektorová topografická *databáze*
  (polohopis + výškopis). Zdroj pravdy, ze kterého se renderují mapy.
- **RÚIAN** — Registr územní identifikace, adres a nemovitostí (ČÚZK). **Druhý ČÚZK datový zdroj
  generátoru** (Sez. 42, modul `connectors/ruian.py`; týž ArcGIS REST server jako ZABAGED, jiný
  MapServer). Veřejná otevřená data dle zák. 111/2009 Sb., bezúplatně. Konzumujeme vrstvu `Parcela`
  (katastrální parcely) kvůli [[druh-pozemku]] → olivová 520. Transport sdílí s `zabaged.py` přes
  `arcgis.py`.
- **Druh pozemku** <a name="druh-pozemku"></a> — katastrální klasifikace parcely v RÚIAN
  (pole `druhpozemkukod`, codedValue doména ověřená ze serveru, Sez. 42): 2 orná · 3 chmelnice ·
  4 vinice · **5 zahrada** · 6 ovocný sad · 7,8 trvalý travní porost · 10 lesní pozemek · 11 vodní
  plocha · **13 zastavěná plocha a nádvoří** · 14 ostatní plocha. **Pravidlo olivové 520:** druh
  ∈ {5, 13} = privátní pozemek u domu, kam běžci nesmí (řeší ~80 % případů jako živý mapař; proximita
  k zástavbě nesena implicitně druhem — pole/louka daleko od domů mají jiný druh). Limit: oplocené
  louky/pole u domů (druh 2/7) zůstanou žluté (TODO „oplocené volné terény").
- **Areál účelové zástavby** — ZABAGED plošná vrstva (id 114) oplocených areálů v sídlech; atribut
  `typzast_k` rozlišuje 62 typů (škola/hřiště/sport/stadión/kasárna/průmysl/garáže/autobusové nádraží…).
  Generátor (Sez. 42): asfaltové dopravní plochy (408 autobusové nádraží, 409 čerpací stanice) → 501,
  vše ostatní → 520 olivová (oplocený = zákaz vstupu). Řeší „bílá hřiště/kasárna" (test LS Sez. 42).
- **ZTM** — Základní topografická mapa (ZTM5–ZTM250); hotové kartografické *dílo* (rastr).
- **DMR 5G** — Digitální model reliéfu 5. generace; LiDAR výškopis terénu (ground-only),
  přesnost ~0,18 m. Zdroj reálného terénu pro `--terrain real` (modul `dmr.py`).
- **DMP OK** — Digitální model povrchu z obrazové korelace (fotogrammetrie, **ne LiDAR**)
  → jen viditelný povrch, žádné penetrující odrazy.
- **CHM** (Canopy Height Model) — model výšky vegetace = DMP − DMR. Slabý proxy pro hustotu
  porostu (zelenou), ne plnohodnotná náhrada multi-echo LiDARu.
- **Multi-echo / LLS mračno** — klasifikované LiDAR mračno bodů se všemi odrazy (terén +
  vegetační echa). Potřebné pro vegetaci à la Karttapullautin; ČÚZK ho jako open data nemá
  (viz „Vegetace gate" v `data-sources.md`).
- **S-JTSK** (EPSG:5514) — Systém jednotné trigonometrické sítě katastrální; národní
  souřadný systém ČR (Křovák). ČÚZK data jsou v něm.
- **WGS84** (EPSG:4326) — globální zeměpisné souřadnice (lat/lon). Vstup `--lat/--lon`,
  přepočet na S-JTSK přes `pyproj`.
- **WMS / WMTS / WFS / WCS / ATOM** — OGC přístupové protokoly ČÚZK (prohlížecí rastr /
  dlaždice / vektor / rastr-výškopis / předpřipravené open-data jednotky). Pro generátor
  je klíčový **WFS** (vektor) — WMS vrací jen obrázek (z něj by se data musela segmentovat).
- **INSPIRE** — směrnice EU pro harmonizovaná geodata; ČÚZK publikuje témata jako služby.
  Relevantní: **TN** (Transport Networks — dopravní sítě) pro reálné cesty, **HY**
  (Hydrography — vodstvo) pro reálnou vodu. Data-driven zdroj pro UC4-II (viz IDEAS).
- **georef** (georeferencování) — přiřazení world souřadnic geometrii. U `--terrain real`:
  `contours.geojson` v S-JTSK, **`rgb.pgw`** ([[world-file]]) k rastru `rgb.png` + blok `georef`
  v `meta.json` (S-JTSK bbox, `pixel_size_m`, `north`, `grivation_deg`). Sez. 37.
- **World file** (`.pgw`/`.jgw`/…) — ESRI textová georeference rastru: 6 řádků afinní transformace
  pixel→world (A, D, B, E, C, F; C/F = střed levého horního pixelu). Rotační členy (D, B) ≠ 0 = rastr
  pootočený vůči osám CRS. Generátorový `rgb.pgw` je **grid-north-up → rotace 0**; reálné OB mapy mají
  v `.pgw` rotaci o [[grivace|grivaci]] (magnetic-north-up). Sez. 37.
- **Grivace** (grid-magnetic angle, angl. *grivation*) — úhel mezi **severem mapové sítě** (grid north)
  a **magnetickým severem** = konvergence poledníků + magnetická deklinace. OB mapy se kreslí magnetic-
  north-up → jejich georef do S-JTSK (Křovák) nese rotaci = grivaci (Soví vrch −11,4°; UTM u středového
  poledníku ~ jen deklinace, Slovanka −3,8°). Reálný `.omap` ji nese atributy `declination`/`grivation`,
  rastr `.pgw` jako rotaci — ověřeno shodné na desetinu ° (Sez. 37). Generátor grivaci zatím NEaplikuje
  (grid-north-up) → feature `--grivation` v IDEAS.

- **Ortofoto podklad** — letecký snímek výseku (ČÚZK ORTOFOTO MapServer `arcgis1`, CC BY 4.0,
  `connectors/ortofoto.py`, dlaždicování nad 4096 px) připnutý do `.omap` jako podkladový template
  (paper-space) pro vizuální verify generátoru proti realitě. CLI `--ortho`/`--ortho-mpp`. Sez. 26.

- **Pár (X,Y)** — tréninková dvojice UC5: **X = ortofoto** (vstup, RGB), **Y = `gt_grid.png`** (cíl,
  runnability labely). Oba warpnuté do TÉHOŽ S-JTSK gridu → **pixel-na-pixel zarovnané** (`build_georef_pair`,
  GATE 1 Sez. 75). Hromadná výroba `build_pairs` (livelox.py, resumovatelná/tolerantní) — 207 ČR map, Sez. 76.

- **ČR/DE filtr** — vyřazení map mimo pokrytí ČÚZK ortofota (X by bylo prázdné). Kritérium = podíl
  „prázdné bílé" v malém ortofoto náhledu (ČÚZK mimo ČR vrací jednolitou 253); práh 0,5. Korpus 216 keep
  classic → **207 ČR / 9 cizí** (DE Žitavsko + PL). Durable `resources/livelox/_cz_filter.json`. Sez. 76.

- **Geografický split** — rozdělení korpusu na **train/val/test** (70/15/15) tak, aby se překrývající mapy
  (sdílí stejný les) nedostaly do různých kupek = prevence **data leakage** (jinak val falešně optimistická,
  „student dostal u zkoušky příklady z domácího cvičení"). Implementace: souvislé komponenty grafu překryvu
  S-JTSK bboxů = clustery; celý cluster do jednoho splitu. `connectors/split.py` → `_split.json`. Sez. 76.

- **Dlaždice / tiling** — páry (X,Y) jsou různě velké (~800-4000 px), ale U-Net jede na **fixní vstup
  512×512** → sliding window 512 px, **stride 256 (50% překryv)**, poslední dlaždice zarovnaná k okraji.
  **Pre-tiling na disk** (ne random-crop za běhu): deterministické + vizuálně kontrolovatelné + rychlé IO;
  augmentace (flip/rot) až v loaderu. Dlaždice mapy jdou CELÉ do jejího [[split]]u (žádný leak). **Dva
  konzumenti (Sez. 88):** (a) archiv `model/runnability/tile.py` (Sez. 77, ortofoto→runnability) — Y=runnability,
  dlaždice s **<30 % validních (≠IGNORE) px se zahodí** (rohy quadu/layout) → `resources/tiles/`; (b) Png2Area
  `model/png2area/tile.py` (Sez. 88) — Y=`area_labels.png` 16 area kódů + pozadí, **BEZ rejection** (scan.png je plný render,
  pozadí 0 = legitimní třída, ne IGNORE) → `resources/area_tiles/`. Oba gitignored + `_tiles.json` (počty/class%/váhy).
  ~8 125 dlaždic (train 5 777 / val 1 224 / test 1 124).

- **IoU / mIoU** — *Intersection over Union*, metrika segmentace: pro třídu c je IoU = TP / (TP+FP+FN)
  (překryv predikce s GT / jejich sjednocení). **Per-class IoU** ukáže každou třídu zvlášť, **mIoU** je
  jejich průměr. UC5 měří per-class (průměr by maskoval, že vzácná 410 fight je ignorována). Počítá se
  z confusion matice, [[IGNORE]] (255) px se vynechá. `model/{runnability,png2area}/train.py`. Archiv runnability
  baseline val mIoU ~0,25 (Sez. 78); **Png2Area reconstructor test mIoU 0,621 ≈ val 0,629** (Sez. 90, první funkční
  model — val≈test = bez leaku; budovy 521 zachráněny vahami 0,00→0,68 proti overfitu) → **stabilizace Sez. 91 test
  0,640 / val 0,654** (cap vah @10 + cosine LR).

- **Generalizační strop** — když při tréninku **train loss klesá, ale validační metrika se nehýbe**
  (UC5 Sez. 78: val mIoU plochá ~0,25 od 1. epochy). Signál, že limit není v délce tréninku/hyperparametrech,
  ale ve vstupu nebo datech. UC5 závěr: runnability (hustota podrostu) je z RGB ortofota shora omezeně
  poznatelná → další krok = bohatší vstup (ablace), ne ladění modelu (princip „generalizuj s důkazem").

- **Class imbalance** — nerovnoměrné zastoupení tříd v GT (UC5: 410 fight jen 1,35 % labeled vs průchodný
  69 %). Bez korekce model degeneruje na „vždy hádej většinovou třídu". Řeší **váhy v loss** (median-frequency
  balancing: w = medián(frekvencí) / frekvence třídy → vzácná 410 dostává w≈8,4). Měřeno Sez. 76; spočteno
  z train dlaždic (po rejection) Sez. 77 → `class_weights_list` `[0,16, 1,0, 1,65, 8,27, 0,89]` v `_tiles.json`.

## Projekt — struktura a principy

- **UC** (use case) — jeden z pěti záměrů projektu (UC1-UC5). Tvoří **DAG**, ne seznam.
  Kanonický popis: `docs/architecture.md`.
- **DAG** (directed acyclic graph) — orientovaný acyklický graf závislostí. Zde: enablery
  (UC2 data, UC5 modely) leží pod aplikacemi (UC3 restaurace, UC4 generátory).
- **Enabler / aplikace** — enabler je předpoklad (data, model), aplikace je koncový produkt.
  Pravidlo: enabler před aplikací („foundations before curtains").
- **Feeder / enabler-feeder** — generátor (UC4-I) coby zdroj trénovacích dat pro UC5;
  „krmí" model. Reframe Sez. 4: ne konečný produkt, ale enabler.
- **Prediktor mapy / `generate_map`** — reframe real-větve generátoru (Sez. 23):
  pro konkrétní lokalitu (souřadnice + rozměry) vyrobit mapu. API:
  `generate_map(lat, lon, w_km, h_km, only_real=False, out_dir=None, *, …)`
  — `lat/lon` WGS84, `only_real` vypíná fázi 2; noise/toggly zachovány jako keyword-only ocas.
  Opačná tvář k noise-feederu. **Historie názvu:** `generate()` → `synthesize_pseudorealistic_map`
  (Sez. 25) → zpět `generate_map` (Sez. 39: v komunikaci převládl „generátor"; deštník i pro
  budoucí generátory, ne jen tuto syntézu). „Pseudorealistická" zůstává vlastností *výstupu*
  (viz níže), ne názvem funkce. Detail: IDEAS.
- **`generator()`** — pojem-agent **obalující funkci [[prediktor-mapy|`generate_map()`]]** (generativní
  větev). Generuje `.omap` (a jeho render) **z parametrů lokality**: pozice (lat/lon), rozměry výseku a —
  kvůli měnící se [[grivace|grivaci]] (magnetická deklinace v čase driftuje) — **datum/čas**. Skládá se ze
  dvou částí: **real** = [[projekce-vs-predikce|projekce]] tvrdých geodat (ČÚZK DMR / ZABAGED / RÚIAN → ISOM,
  *máme*) + **predict** = [[projekce-vs-predikce|predikce]] symbolů, které v datech nejsou (vegetace /
  paseky / hustníky), tak aby mapa vypadala co nejreálněji. Účel = [[feeder|enabler-feeder]]: libovolné
  množství párů [render, `.omap`] s [[ground-truth-gt|GT]] zdarma pro trénink [[reconstructor]]u (obchází
  [[sparse-gt-past|sparse-GT past]]). Pozn.: datum/čas dnes ještě není parametr → viz [[grivace]] feature.
- **`reconstructor()`** — pojem-agent **obalující funkci `reconstruct_map()`** (dříve navrženo `mapper()`).
  Ze **skenu existující** OB mapy (i opotřebené / pomačkané) vyrobí `.omap`. Pro **stejnou lokalitu a čas**
  znovu opatří **real část** přes [[generator]] (tvrdé vrstvy přesně z mapových služeb) a zkombinuje ji
  s **reverse-engineeringem skenu** (PNG→`.omap`) pro to, co v datech NENÍ — vegetace, kartografovy úpravy,
  fialový přetisk. Trénuje se na párech z [[generator]]u ([[domain-gap|sken-augmentovaný]] render ↔ `.omap`
  GT). **Plní hlavní aplikační cíl** (UC4-III). **[[pic2omap]] sem bude absorbován** (fáze B→A, načasování
  TBD), ne duplikován. Pozor: model „rozumí mapám" = `reconstructor`, NE archivovaný `ORTO→4 barvy` (ten
  „rozuměl ortofotu", Sez. 78 strop). Jméno `reconstruct_map()` voleno přes `regenerate_map()` — „regenerate"
  koliduje s programátorským „re-run téže generace", kdežto reconstructor rastr→vektor rekonstruuje (Sez. 79).
- **Fáze I / II / III** (Sez. 80) — pracovní rozklad cesty k [[reconstructor]]u: **I. [[generator]]()** vyrobí
  pseudorealistic `.omap` (real část ČÚZK + **prediktivní plochy ze separace barev z HD Livelox PNG** — bez
  degradace, separace chce kvalitu); **II. dataset** = export PNG z `.omap` + **degradace** (overprint /
  odřeniny / bláto = [[domain-gap]] Stupeň 2) → páry [`.omap`, sken-PNG]; **III. [[reconstructor]]()** = trénink
  modelu na párech z II. Degradér patří do II, ne do I. Pravé veřejné `.omap`/`.ocd` vektory neexistují
  (průzkum Sez. 80) → `.omap` tvoří generátor. Provenience **real/predict** flag v `.omap` říká, co model bere
  z dat vs ze skenu. Detail: IDEAS „Tři fáze I/II/III".
- **degradér / `degrade()`** (Sez. 86, `generator/degrade.py`) — fáze II krok, který z čistého renderu
  (`rgb.png`) vyrobí realistický „sken" (`scan.png` = **X** v páru). **Čistě fotometrický** (CMYK misregistrace,
  blur, papír+zažloutnutí, senzorový šum, JPEG) → **Y (`.omap`) se nemění**, pár zůstává konzistentní. Geometrii
  (rotace/warp) NEdělá — ta patří na úroveň páru (transformuje X i Y zároveň, loader D4 Sez. 78), ne sem (DRY/SLAP).
  Deterministický přes `seed` (= cid v `pairs`) → z jednoho renderu libovolně variant = augmentace. Zužuje
  [[domain-gap]] render→sken (reconstructor trénovaný na hladkém rastru by na reálné mapě selhal). **omap2png** =
  „render `.omap` → PNG"; náš rastr to dělá zdarma (`generate_map` produkuje `rgb.png`, Sez. 82 volba C), C++
  headless OOM až s důkazem gapu.
- **`omap_raster` / `area_labels.png`** (Sez. 87, `generator/omap_raster.py`) — Y-pipeline páru: rasterizace
  plošných (Area) ISOM symbolů z `.omap` → **label rastr** (`area_labels.png` = **Y** pro [[reconstructor|`Png2Area`]]).
  **Y odvozeno z `.omap`, NE z render masek `mask_*.png`** — reconstructor se učí na páru [scan, `.omap`], Y z téže
  `.omap` → pár **self-konzistentní** (nezávisí na render artefaktech). **Per-ISOM-kód** (volba Sez. 87): `CODE_TO_LABEL`
  16 area kódů → label 0..16 (0=pozadí; +403 Sez. 92); **statický** (konzistence napříč korpusem), seskupení tříd = modelové
  rozhodnutí NAD rasterizací (DRY, izomorf s [[degradér|`tile.py`]] labely). **Z-order statický ISOM** zdola nahoru
  (501.1/520 base … 521 budovy), **díry per-objekt** (vyříznuté jen v rámci objektu → odhalí nižší vrstvu).
  Transformace paper µm→px triviální z `meta.json`: `px=(paper/pw+0.5)·W`, `pw=world_m·1e6/scale` (měřeno Sez. 87,
  nezávislá na gridu). `object symbol="N"` = N-tý symbol v `<symbols>` (pořadový index; id==index ověřeno). Integrováno
  do [[pairs|`build_pair`]] (`labels=True` → `area_labels.png`). Vztah k `omap_export.AREA_CODES`: tam = „co se zapíše
  jako uzavřený path"; tady = „label schéma Png2Area" (jiná doména → vlastní seznam; DRY-extrakce až 3. konzument).
- **`Png2Area` / `Png2Point` / `Png2Line`** (Sez. 80; přejmenováno Sez. 82 z `Png2Polygon`/`Png2Linie` na
  terminologii OOM — symboly jsou v `.omap` typu **Point/Line/Area**, doloženo z `template_classic.omap`:
  `type=1` Point / `type=2` Line / `type=4` Area) — tři pomocné modely [[reconstructor]]u, dekompozice
  podle typu geometrie ISOM (area / point / line = tři různé CV úlohy: segmentace / detekce bodů / extrakce
  linií). GT zdarma z `.omap` (typ symbolu). Pořadí: **Area** první (reuse U-Net Sez. 78, vstup mapa ne
  ortofoto → vysoký strop), **Point** druhý (generátor má přesné polohy bodů → GT + libovolně instancí; „bodová
  větev" posed/pramen/vývrat), **Line** poslední (nejtěžší — vektorizace linií, segmentace+skeletonizace).
  **`Png2Area` model HOTOVO Sez. 88** (`model/png2area/{tile,dataset,train}.py`, izomorf s archivem
  `model/runnability/`): dlaždice [scan.png, area_labels.png] → `AreaTileDataset` (D4+ImageNet) → U-Net/ResNet34
  **16 ISOM area kódů + pozadí** (label 0..16 ze [[omap_raster]], bez ignore_index — Y je celé validní). **Plný trénink
  Sez. 90-91:** test mIoU 0,621→**0,640** (val 0,654, cap vah @10 + cosine LR); budovy 521 zachráněny 0,00→0,68; vzácné
  208/501/301.1 = datový strop → class-balanced expansion. Trénink = mrkla.
- **`separate_areas` / algoritmická separace** (Sez. 82, zobecněno Sez. 83, `generator/separate.py`) — GT-feeder
  pro [[reconstructor|`Png2Area`]]: z reálné Livelox mapy separuje plošné predikční ISOM symboly (zelená
  406/408/410 + **403 Rough open** ze Sez. 92 přes registr `AREA_CLASSES`) a vektorizuje (contourpy, reuse
  `rock_relief`) → predikční plochy do
  `.omap`. **403 (Sez. 92):** rozštěp žluté UVNITŘ open (gt label 4) přes `_is_pale_yellow` — bledá (403,
  predikt) vs sytá (401, real, neseparuje se) vs cesta vs bílá-záchyt; vlastní SCAN reference (ne render
  palette), staví na očištěném map_gt. Pattern třídy (404/407/409) separace NEumí (per-pixel slepá, Sez. 90).
  **Scope (Sez. 83):** jen co generátor neumí z tvrdých dat (vegetace, do budoucna paseky/podrost) —
  voda/skály/budovy zůstávají „real" (separace navíc = dvojí zdroj + konflikt + DRY). **Záměrně NE věrná na 100 %**
  (PoC ~90 %): kvalitu dotáhne MODEL trénovaný na množství párů, ne leštění prahu. Nahrazuje archivovaný
  [[forest-age-proxy]] jako zdroj predikční vegetace (univerzální + mapař = ground truth + konzistentní pár).
  `_fill_ignore` (Sez. 83): před vektorizací nahradí IGNORE pixely (fialový přetisk tratě 704/705 → 255 z [[runnability]]
  GT) nejbližším labelem — jinak kroužky/spojnice kontrol vykousnou díry do zelených ploch.
  **`TARGET_MPP` = 1,33 + `separate_areas(src_mpp)` downscale (Sez. 85):** je-li vstupní gt jemnější než
  `TARGET_MPP`, downscaluje se NEAREST (ne bilineár — smíšené mezitřídní px) PŘED vektorizací; polygony se ×f
  vynásobí ZPĚT na původní grid (výstup v image-px vstupu → volající se nemění). Dva důvody: **výkon** (separace
  je O(n² prstenců) — měřeno 0,56→1,33 mpp = **31,6× zrychlení**, věrnost ploch zachována, žrout #1 ze Sez. 84) +
  **konzistence** (`MIN_AREA_PX` laděné na 1,33 platí stejně napříč korpusem). Bez `src_mpp` = no-op (PoC).
- **`pairs.py` / `build_pair(cid)`** (Sez. 83, `generator/pairs.py`) — per-classId **továrna párů** [render, `.omap`]
  pro [[reconstructor]] (izomorf reframe „generator = továrna párů"; neplést s archivovaným `livelox.build_pairs` =
  ortofoto X,Y). Spojí REAL část (ČÚZK vrstvy z [[generator|`generate_map`]]) + PREDICT část (separace vegetace,
  `separate_areas`) do JEDNÉ georeferencované `.omap` (provenance real/predict). Společný grid = Livelox
  `_georef_grid` (centroid→lat/lon, obal→w_km/h_km); zarovnání přes jeden S-JTSK (`.omap` vektorový → pixel-grid
  netřeba; Gate A Sez. 83: shoda obalu medián ~1 px). Předáno přes `generate_map(predict_areas_sjtsk=…)`.
- **`omap2png` (rozhodnutí Sez. 82)** — rendrování `.omap` → PNG pro fázi II (export páru). OOM **nemá CLI/headless**
  export (jen GUI; ověřeno) → buď náš rastr (`generate_map` už `rgb.png` produkuje, aproximace), nebo C++ headless
  z OOM zdroje (`RenderConfig`+`MapRenderables::draw`+Qt offscreen, věrné). **Volba: náš rastr teď, C++ až měřený
  doménový gap dokáže, že je potřeba** („generalizuj s důkazem"). Detail: IDEAS „omap2png".
- **Projekce vs predikce** — dvě fáze prediktoru mapy. *Projekce* = deterministický převod dostupných
  geodat na ISOM (DMR→vrstevnice, ZABAGED→cesty/voda/budovy; *máme*). *Predikce* = odhad symbolů, které
  v datech NEJSOU (vegetace/průchodnost) z naučeného prioru podobných lokalit (UC5, blokováno korpusem +
  licencí). Nezaměňovat: dnešní `--terrain real` je **projekce**, ne predikce.
  Sez. 62: **`--forest-age` = první realizovaný predikční střípek** — zeleň 406/408/410 odvozená z VĚKU
  porostu (AOPK porostní skupiny, [[forest-age-proxy]]). Data tvrdá, ale věk→běhatelnost je proxy → značeno
  `proxy:true`. Není to plná UC5 predikce (žádný naučený prior), ale stojí už za hranicí projekce.
  **Sez. 82: jako zdroj predikční vegetace NAHRAZEN separací barev z mapy** (`generator/separate.py`; forest-age
  proxy mělo zeleň jen na 33 % korpusu, IoU 0,12, přestřel 3,3× → archivováno). `--forest-age` flag v kódu zůstal.
- **Pseudorealistic map** — výstup prediktoru: mapa, která *vypadá* realisticky, ale není skutečné
  terénní mapování (syntéza projekce + AI predikce). Pojmenování poctivě přiznává umělost (Sez. 23).
- **pseudorealistic (parametr) / fáze 1-2** — přepínač real-větve generátoru (Sez. 24, default
  `True`; CLI `--only-real` = `False`). **Fáze 1 = projekce** (deterministický převod tvrdých dat,
  100% věrnost). **Fáze 2 = pseudorealistická dekorace** (doplní symboly, co v datech nejsou, ale
  dělají mapu „orienťácky vypadající"; poloha vymyšlená → musí jít vypnout). Dnes jediný konzument
  fáze 2 = rovnoměrné příčky [[el-vedení]] mimo evidované sloupy + od Sez. 62 zeleň z věku porostu
  ([[forest-age-proxy]], první predikční krok k vegetaci). Generalizace L1/L2 budov NENÍ fáze 2 (věrná
  kartografie, kterou ISOM předepisuje). Spec §0b.
  Vztah k [[projekce-vs-predikce]]: fáze 2 sahá od dekorace (příčky) po predikci (vegetace, UC5).
- **forest-age-proxy** — ⟲ **ARCHIVOVÁNO Sez. 82** (A1 measure-first: pokrytí 33 % korpusu, IoU 0,12 s kresbou,
  přestřel zelené 3,3× → nevhodný zdroj predikční vegetace; nahrazeno [[separate_areas|separací z mapy]]; kód
  funkční, doložená cesta jako [[uc5-rgb-baseline-ceiling|Orto2Colors]]). — vrstva `--forest-age` (Sez. 62, `connectors/forest.py`): zeleň ISOM 406/408/410
  odvozená z VĚKU porostu (AOPK „Les_Mapy" porostní skupiny, atribut `BARVA` = ordinální věk doložený
  standardem KSLH). Mladý porost = nejhustší → 410 fight; tyčkovina → 408 walk; mladší kmenovina → 406 slow;
  starý les + bezlesí (`BARVA 15`) → bílá. **PROXY, ne věrná runnability**: věk je hrubý prediktor hustoty
  (mladý=hustý drží těsně, starší nejisté) — vědomě přijato (vegetace gate [[vegetace-gate]] zavřená pro
  open-LiDAR). Absolutní řezy `BARVA`→ISOM (stejné pro všechny mapy → konzistence pro UC5 feeder, ne
  per-mapová normalizace — ta by fabrikovala rozsah). Pokrytí 3/5 DEV (SV/HS bez AOPK dat). Charakter =
  [[projekce-vs-predikce|predikce]] (značeno `proxy:true` v meta).
- **Deštník / fáze B→A** — AzimutLab je teď meta-vrstva (fáze B, deštník) nad sourozeneckým
  Pic2Omap; cíl je monorepo (fáze A), které Pic2Omap absorbuje, až vznikne sdílené jádro.
- **Pic2Omap** — sourozenecký projekt (raster OB mapa → vektor `.omap`); UC4-III. Žije ve
  vlastním repu, neduplikovat sem (CLAUDE.md).
- **Gate** — licenční/datová brána: bez vyjasněné licence (nebo dostupnosti dat) se nad
  zdrojem nestaví. „Vegetace gate" = zavřená cesta k vegetaci z ČÚZK open dat.
- **Domain gap** — rozdíl mezi syntetikou a realitou (syntetika je hladší). Řeší se
  sim-to-real receptem.
- **Sim-to-real** — předtrénink na syntetice (cesta C) + fine-tuning/validace na reálných
  mapách (cesta B); reálný terén (A) dosazený do generátoru.
- **Cesty A / B / C** — datové zdroje pro UC5: (A) geodata ČÚZK, (B) reálné korpusy map,
  (C) syntetická generace. Detail: `RESEARCH.md`.
- **Sparse-GT past** — málo ground-truth anotací (z Pic2Omap pilotu); generátor ji obchází
  (GT zdarma).
- **SLAP** (Single Level of Abstraction Principle) — při změně konceptu aktualizovat všechny
  vrstvy najednou (model / kód / docs / data). Viz CLAUDE.md.

- **Asset** — znovupoužitelný vzor objektu pro generátor (zatím řopík). **Asset pattern** (Sez. 26):
  dvojice `<jméno>.omap` (vizuální geometrie kreslená v Mapperu — přesné body + ISOM symboly) +
  `<jméno>.rules.xml` (pravidla, co `.omap` nepojme: `rotation_rule`, `draw_order`, `source`). Žije v `asset/`.

## Nástroje a knihovny

- **OOM** (OpenOrienteering Mapper) — open-source editor OB map; cílový formát `.omap`.
  Symbol set je **vyměnitelný `.omap` soubor** („Nahrát symboly ze souboru"), ne závislost na verzi SW.
- **Crosswalk (`.crt`)** — cross-reference table mapující symboly mezi sadami (ISOM verze, ISSprOM, OSM).
  Klíčový: `docs/kb/ISOM2000-ISOM2017-2.crt` (OpenOrienteering, GPL) mapuje `<kód 2017-2>  <kód 2000>`.
  Mapuje přes **sémantiku** (význam), ne kód-na-kód — čísla se mezi verzemi recyklují (viz [[ISOM]]).
  Sez. 38.
- **OCAD** — komerční SW pro tvorbu map; formát `.ocd`.
- **Livelox** — platforma pro sdílení tras závodů s mapou na pozadí (livelox.com). **Cesta-B zdroj reálných
  OB map** pro UC5 runnability korpus (deep research Sez. 67): stažitelný přes interní endpoint `/Data/ClassInfo`
  → Azure blob (2 open-source nástroje), ale **jen RASTR** (PNG, ne vektor) + georef = quad
  (`projectedBoundingQuadrilateral` v CRS mapy + WGS84). Licenční gate (obchází podmínky; práva kartograf/pořadatel).
  **Konektor hotov Sez. 68** (`connectors/livelox.py`): gate 1 rozlišení = strop **1,33 m/px** (nativní 0,75
  server-side nedostupné; stačí na plošnou GT), gate 2 quad sedne na ortofoto **bez fitu** (oris/fitter overkill),
  **epsg ČÍST Z DAT** (5514 i 32633, nezávisí na poloze). GT segmentace `map_gt.py`. Detail: `data-sources.md`,
  IDEAS „UC5 runnability korpus".
- **Kurace korpusu** — výběr vhodných map z Livelox korpusu pro trénink (GT je strop supervised modelu →
  nekvalitní/jiný typ mapy kazí). `connectors/curate.py` (merge-aware) → manifest `resources/livelox/_curation.json`.
  Každá mapa: **discipline** (1 hodnota: `classic` = foot-O les ISOM = tréninkové jádro / `sprint` ISSprOM / `mtbo`
  cyklo / `overview` >=20000) + **quality tagy** (auto z jména/GT/epsg: `variant_contour`/`variant_black`/`base_layer`/
  `basemap` ne-OB OSM podklad/`training`/`foreign_crs`; vizuál ruční: `legend`/`logo`/`damage` foto vytištěné mapy/
  `composite` layout list s víc mapami různého měřítka na jednom obrázku → georef nesmyslný, Sez. 71 Drábovna+Jeskyňky).
  **keep** = `keep_override` JINAK (classic AND bez disqualify tagu). Sez. 71: **268 → 216 keep classic**. Reader
  `kept_dirs('classic')` = kontrakt UC5 loaderu. Merge zachová ruční tagy přes re-run (idempotent).
- **Karttapullautin** — generátor OB podkladů z klasifikovaného LiDAR mračna (vrstevnice +
  vegetace). Stojí za projekty MapAnt. Survey: `RESEARCH.md`.
- **CoVe** — color line vectorization pro orienťácké čáry (v OOM).
- **AutoTrace** — bitmap → vektor (raster tracing). Pro reálné skeny (UC4-III/UC3), **ne**
  pro náš generátor (ten má vektor z contourpy přímo).
- **lasertool** — lokální binárka: LiDAR point cloud → rastr (rodina Karttapullautin).
- **contourpy** — Python knihovna marching squares; generátor z ní bere vrstevnice jako
  polylinie.
- **marching squares** — algoritmus pro izolinie skalárního pole na mřížce.
- **Catmull-Rom splajn** — interpolační křivka procházející všemi kontrolními body
  (hladká; tečna v bodě ~ směr sousedů). Generátor jím kreslí cesty (§4.9); krajní
  body zdvojuje (clamp), aby prošel i konci. Helper `_catmull_rom`.
- **pyproj** — transformace souřadnic (WGS84 ↔ S-JTSK); závislost jen pro `--terrain real`.
- **`.omap` / `.ocd`** — XML/binární formáty OB map (OOM / OCAD). Generátor umí `.omap`
  export (template-based, `omap_export.py`).
- **GeoJSON** — textový vektorový formát; `contours.geojson` = vrstevnice jako LineString
  s ISOM symbolem.
