# generator

Generátor výseku mapy pro orientační běh — **pilíř Laboratoře**, `Generator()` etapa
ROADMAP (enabler-feeder párů `[render, .omap]`), ne sandbox experiment (povýšen ze
`sandbox/generator-poc/` v Sez. 39 — 4000+ LOC `generator.py` už dávno není „PoC"). Konzumuje konektory
reálných dat z `connectors/` (UC2). (Pozn.: UC5 **model** žije v samostatném `model/`,
sourozenec `generator/`/`connectors/` — ne uvnitř generátoru; viz README repa „Repository layout".)
**UC5 továrna párů (Sez. 82/83):** `separate.py` (`separate_areas`) separuje predikční plochy (vegetace
406/408/410 + **403 Rough open** ze Sez. 92 — rozštěp žluté uvnitř open: bledá=403 predikt / sytá=401 real,
přes `_is_pale_yellow`, vlastní scan reference) z reálné Livelox mapy; `pairs.py` (`build_pair(cid)`) je spojí s real ČÚZK vrstvami `generate_map`
do JEDNÉ georeferencované `.omap` per classId (provenance real/predict) — `[render, .omap]` pár pro `reconstructor()`.
Separace **downscaluje vstupní gt na `TARGET_MPP`=1,33 PŘED vektorizací** (Sez. 85, `separate_areas(src_mpp)` —
`pairs` předá `meta["effectiveMppX"]`): řeší výkon žroutu #1 (O(n² prstenců) — 31,6× zrychlení na jemném skenu,
věrnost zachována) + sjednotí měřítko separace napříč korpusem. Polygony se ×f vrací na původní grid (volající beze změny).
**Fáze II `degrade.py` (Sez. 86/103):** `degrade(rgb, seed)` degraduje čistý
`rgb.png` fotometrickými vadami (CMYK misregistrace / blur / papír+zažloutnutí /
šum+JPEG). Nezapisuje trvalý `scan.png`: volá se on-the-fly v modelovém loaderu
pouze nad X, zatímco Y se nemění. Geometrie (rotace/warp) sem nepatří —
transformuje X i Y na úrovni dlaždice. omap2png = náš rastr (`generate_map`
dělá `rgb.png`); C++ headless OOM až s důkazem doménového gapu.
**Y-pipeline `omap_raster.py` (Sez. 87):** `rasterize(omap, meta)` rasterizuje plošné (Area) ISOM symboly z `.omap`
→ **label rastr** (`area_labels.png` = **Y** páru, pro reconstructor `Png2Area`). Y z `.omap` (NE z render masek) →
pár self-konzistentní. Per-ISOM-kód (`CODE_TO_LABEL`: **20 ISOM kódů +
pozadí, `N_AREA=21`, labely 0–20**), statický z-order zdola nahoru a díry per
objekt. `pairs` volá s `labels=True`. Pár = **[`rgb.png` (X),
`area_labels.png` (Y)]**; degradace X probíhá až on-the-fly v loaderu.

**Post-process `.omap` (string/regex, NE ET — ten by rozbil inject regex i OOM):**
`cut.py` (Sez. 114) = geometrický ořez `.omap` (primitiva `cut_point`/`cut_line`/`cut_area`
Sutherland-Hodgman → orchestrátor `clip_omap` přepíše `<coords>` se zachováním flagů →
wrappery `cut_box` papír [CLI `--location`] / `clip_omap_to_quad` Livelox quad); odstraní
přesah bboxu = okolní sídla. **Neatline border (Sez. 138 E2):** `cut._emit_area` detekuje
řeznou hranu plochy s neproniknutelným obrysem (voda 301 / 520 / 521) a přerotuje ji na
uzavírací segment s flagem **16** → OOM nekreslí černý border podél umělé řezné hrany
(single-run; multi-run je doložený limit). `gen_backgrounds.py` (Sez. 104/109) = OOM bg
podklady do `gen.omap` (`add_backgrounds` Livelox pár / `add_resources_scan_background`
měřicí mapa). Podklady DMR hillshade + ortofoto + Livelox sken: `attach_dmr_hillshade` /
`attach_ortho` / `attach_livelox_scan` (Sez. 138/140, OOM *Templates* toggle; `_resolve_omap`
sdílí `gen.omap`/`<složka>.omap` resolution). **Orchestrátor `attach_verify_backgrounds(map_dir,
cid_dir=None)` (Sez. 140):** doplní k hotové `maps/` mapě DMR + (je-li `cid_dir`) Livelox sken;
ortofoto připíná `generate_map(ortho=True)` už při renderu. Volá se jen z **CLI cest** (lidská
verify mapa) — tréninkové páry v `resources/livelox/<cid>/gen/` podklady NEdostávají (model čte
rgb+labels). **`pairs.py map <classId> <název>`** (`make_map`, Sez. 140) = celý řetězec jedním
krokem (download → `segment_gt` → `build_pair` ortho=True → DMR+sken) → `maps/<název>` prohlížecí
mapa. `generator.py` CLI (DEV `--location`/ruční) dostane auto DMR po `cut_box` (`--no-backgrounds` vypne).

Realizuje **MVP řez** specifikace
[`docs/kb/generator-procedural.md`](../docs/kb/generator-procedural.md):

- **vrstevnice** — izolinie výškového pole (§4.5), hlavní zvýrazněné (3 px),
- **bodové symboly extrémů** — malé uzavřené vrstevnice → ISOM **109/110/111**
  (kopeček / protáhlý kopeček / prohlubeň; ISOM 2017-2 Rev 6, Sez. 13), generalizace (§4.10),
- **cesty** — dvě větve (`--paths`):
  - `proc` (default) — procedurální **Dijkstra least-cost** (§9, Sez. 13), hlavní plná (ISOM
    **503**) / vedlejší čárkovaná (ISOM **505**); cesty traverzují svah, nešplhají přes vrcholy,
  - `real` — **reálné komunikace z ČÚZK ZABAGED (ArcGIS REST)** (real-půlka §4.9, Sez. 16; `zabaged.py`),
    mapované na plnou ISOM hierarchii **502-506** (silnice/cesta zpevněná/vozová/pěšina) podle
    typu a povrchu; `Cesta typcesty_k=025` je z path kanálu vyjmuta jako 508 trace. Vyžaduje
    `--terrain real` (sdílí výsek s DMR → cesty sednou na terén),
- **lesní průseky / lineární stopy** — `--rides real` (Sez. 36+150; týž `zabaged.py`): `Lesní průsek`
  + neudržovaná `Cesta typcesty_k=025` → ISOM **508 Narrow ride** (průhled/linear trace terénem;
  černá čárkovaná 3,0/0,375 mm). **Pozor: ZABAGED je u průseků jen řídký fallback** (hlavní /
  dlouhodobě udržované linie), ne zdroj kompletnosti; kompletnější 508 má dodat scan/Png2Line.
  Runnability pozadí se nekreslí (vegetace = UC5). Vyžaduje `--terrain real`,
- **voda** — `--water real` (real-půlka, Sez. 17; týž `zabaged.py`): vodní toky ISOM **304/305/306**
  (pojmenovaný stálý / bezejmenný stálý / občasný; podzemní se nekreslí) + vodní plochy **301**
  (modrá výplň + břeh, vč. koupališť z `Pozemní_nádrž`, Sez. 27). Vyžaduje `--terrain real`. Pramen
  **312** (ze `Zdroj_podzemních_vod`) se kreslí přes `--landmarks` (bodový, Sez. 44 — modré „U" ústím
  nahoru). Procedurální voda (hydro jádro D8) zatím ne,
- **budovy** — `--buildings real` (real-půlka, Sez. 18; týž `zabaged.py`): `Budova_..._plocha_` →
  ISOM **521 Building** (plošný černý symbol). Vyžaduje `--terrain real`. **Kreslené RAW jako voda**
  (Sez. 27 — generalizace L1 i displacement L2 zavrženy, komolily tvar/polohu; *generalizuj jen s důkazem*),
- **pomocné vrstevnice** — form lines ISOM **103** (Sez. 29; derivace z DMR, ne ZABAGED — jen `--terrain real`),
  kde mírný svah AND zakřivený terén; min. délka 3 mm,
- **el. vedení + lanovka/vlek** — `--powerlines real` (Sez. 24 + 55): `Elektrické_vedení` +
  `Lanová dráha, lyžařský vlek` → ISOM **510** „Power line, cableway or skilift" (příčky na reálných
  sloupech `Stožár_elektrického_vedení` / `Stožár lanové dráhy`; ISOM 510 = týž symbol pro vedení i lanovku),
- **železnice** — `--railways real` (Sez. 28+31): `Železniční_trať`+`_vlečka`+`Tramvajová dráha` → ISOM
  **509** (kombinovaný symbol, bílý knockout),
- **kolejiště / zpevněné plochy** — `--paved real` (Sez. 28): `Kolejiště` → ISOM **501 Paved area** (plocha
  s obrysem; „10 kolejí" je v datech jedna plocha, ne linie); `Ostatní plocha v sídlech` → **501.1**
  Paved area bez obrysu (Sez. 54, base výplň zastavěného území vespod, odemčeno hole support),
- **skály/balvany** — `--rocks real` (Sez. 30 + 57 + 63): body `Osamělý_balvan…`→**204**, `Skupina_balvanů__bod_`→**207**
  + `Skupina_balvanů__linie_`→**208 Boulder field** (Sez. 57) ze ZABAGED; **plocha 206 Gigantic boulder = z DMR 5G
  SKLONU** (Sez. 63, `rock_relief.py`: práh sklonu 46° → morfologické scelení stěn do bloku → vektorizace) —
  nahradila generalizovaný ZABAGED `Skalní_útvary` (jeden blob → věrná členitost věží/průchodů, ověřeno proti Mapy.com).
  **Pseudo body 204/210 (Sez. 107, jen `pseudorealistic`):** `_generate_pseudo_boulders` injektuje 204 Boulder
  + 210.1 Stony ground (pole teček) na masku DOLOŽENÉ skalnatosti (206 plochy + reálné 204/207 body, dilatace),
  kalibrováno na share → KPI bodů 18,4 → 54,3 % (mirror inject geometrie Png2Point, ne model). **Sez. 138 E3:**
  rejection sampling balvanů (ISOM-korektní nepřekrývání; skupina → 207),
  **Pseudo body (Sez. 136-141, jen `pseudorealistic`):** `_generate_pseudo_points` (princip kamenů; do Sez. 140
  `_generate_pseudo_veg_points`, Sez. 141 zobecněno na veg + man-made). **Zelené veg (Sez. 136-137):** **417**
  Prominent large tree (zelený kroužek, doplní řídký ZABAGED `Významný_strom` na ~27/km²) / **418** Prominent bush
  (plný zelený disk, čistě pseudo ~18/km²) / **419** Prominent veg. feature (zelený X, čistě pseudo ~18/km²).
  **Černé man-made (Sez. 141, čistě pseudo, ZABAGED nevede):** **527** Fodder rack (krmelec, „Λ" stříška+noha,
  vzácný pseudo bod; Sez. 150 kalibrace dolů po KOMPAS přestřelu 103→3) / **525** Small tower
  (posed, „⊤", ~1,1/km²) / **531** Prom. man-made x (černý X, ~1,3/km²); hustota
  se měří crosswalk-aware (paměť `isom-dual-numbering-oom-ocad`). Umístění MIMO voda/206 skály/budovy/cesty/zpevněné/
  **železnice 509** (sdílený `_build_forbid_px`, px rozlišení; railway doplněna Sez. 138 E3) + ISOM rozestup
  (rejection sampling). 417/419 jsou ve scope Png2Point detekce, 418/527/525/531 ne (generátor kreslí pro budoucí trénink),
- **mosty/tunely/lávky** — `--bridges real` (Sez. 31–33): `Most`→**512** (2 paralely + buffer crop),
  `Tunel`→**512** otočené 90° na vjezdech, `Lávka`→**512.2**,
- **řopíky** — `--ropiky real` (Sez. 26–27): `Bunkr` LO37 jako asset, orientovaný k nejbližší státní hranici,
- **plošný pokryv** — `--surfaces real` (Sez. 41-53): open land louka → ISOM **401** (plná žlutá); **udržovaná
  zeleň → 402 / 402.1** (Sez. 53, štěpení `typ_pudy_k`: park/okrasná zahrada → 402 žlutá + bílé tečky, ostatní
  zeleň → 402.1 žlutá + zelené tečky); **pole → 412 Cultivated** (žlutá + černý tečkový pattern, Sez. 47-48) + **olivová
  520 Area which shall not be entered** z pěti zdrojů (Sez. 42 + 49 + 56): hřbitov + **sad/zahrada** (`Ovocný sad,
  zahrada` — zahrady u domů/chalup, oplocené; Sez. 49 oprava chybného 413 Orchard) + **RÚIAN privátní pozemky**
  (zahrada+zastavěná, `ruian.py`) + **areály účelové zástavby** (ZABAGED 114: škola/hřiště/sport/kasárna… → 520,
  asfalt 408/409 → 501) + **kamenolom** (ZABAGED `Povrchová těžba, lom` 118, Sez. 56: oplocený těžební areál → 520,
  ne 201 — plocha→plocha, kamenné útvary v z-orderu nad olivovou). Kůlny (105)
  → 521. Parkoviště → **501.1** (bez obrysu, průchozí; Sez. 57 oprava z 501), asfalt areálů → 501 přes `--paved`. **Z-order vespod** (podklad pod
  vrstevnicemi; olivová nad žlutou; les = bílá default = vegetace gate). Vyžaduje `--terrain real`,
- **olivová 520 dissolve + plot 516** — `--surfaces real` (Sez. 98): olivová 520 se sjednocuje do **souvislých bloků**
  (RÚIAN katastr fragmentuje zástavbu na tisíce parcel → kompas přestřel 9× → contourpy dissolve bez `shapely` → 1,3×).
  **Plot 516 Fence** (pseudo fáze 2, ZABAGED plot nevede) po obvodu RÚIAN-privát bloků ≥ 0,5 ha: RDP narovnání + ticky DOVNITŘ (ISOM „tags inside").
- **budovové stavby** — `--buildings real` (Sez. 43 rozšíření): + `Zámek`/`Hrad` → **521**, `Rozvalina, zřícenina`
  → **523 Ruin** (čárkovaný obrys bez výplně). ČÚZK je vede zvlášť, ne v `Budova_99` (domov mládeže = bývalý zámek),
- **bodové orient. prvky** — `--landmarks real` (Sez. 43, audit katalogu): kříž→**530**, mohyla→**526**,
  věž/vodojem/silo/těžní/mlýn/motor/věžovitá stavba/**tovární komín** (Sez. 52)→**524**, významný strom→**417** (zelený kroužek);
  **Sez. 44**: pramen→**312** (modré „U" ústím nahoru), jeskyně+šachta→**203.2 Cave** (černá „Λ" stříška hrotem
  nahoru), nádrž→**311** (modrý čtverec, z centroidu),
- **mokřady** — `--marsh real` (Sez. 44): bažina/močál + rašeliniště→**308 Marsh** (modrá vodorovná šrafa;
  projekce vždy crossable, NE 307) + **310 Indistinct** (pseudo fáze 2 Sez. 99: ~55 % náhodou, 2× řidší přerušovaná šrafa),
- **liniové orient. prvky** — `--linefeatures real` (Sez. 43): sráz→**104 Earth bank** (HNĚDÁ plná + jednostranné ticky),
  zeď/hradba→**513 Wall**, rokle/výmol→**107 Erosion gully** (Sez. 58; HNĚDÁ plná bez ticků, mirror 104; v ČR řídká, Σ0 na DEV),
- **stromořadí** — `--treerows real` (Sez. 45): `Liniová vegetace`→**406 Vegetation: slow running** („lineární les":
  osa→buffer→úzký světle zelený pás; oprava 416 = hranice porostů byla sémanticky špatně pro řadu stromů),
- **hranice porostu** — globální `azimutlab.toml` volí `symbols.vegetation_boundary = "416"` nebo
  `"416.1"` (výchozí). Volba platí pro RGB i `.omap`; zelená 416.1 se dle ISOM nekreslí kolem 410 Fight,
- **prostupy** — `--barriers real` (Sez. 52): `Zábrana` na nosné zdi 513→**519 Crossing point** („branka",
  orientace = tangenta zdi, zeď se pod brankou přeruší; jen bod na zdi = průchod plotem, závory na cestách zahozeny —
  2/66 na LS = řídké), **poslední kandidát ZABAGED katalogu**,
- **ground-truth masky** — každá vrstva i jako segmentační maska (§8.1),
- **reálný terén** — `--terrain real` dosadí ČÚZK DMR 5G místo šumu (§8.5, Option 2;
  výškopis z `dmr.py`).
- **vektor** — `contours.geojson` (ISOM **101/102** linie, georef S-JTSK pro real terén) a
  `<lokalita>.omap` (vždy; §9; `omap_export.py`; název = výstupní složka, Sez. 42). OMAP je **template-based** nad vlastním čistým ISOM
  2017-2 template `template_classic.omap` → věrná geometrie bodů (110 elipsa, 111 oblouk) + plná
  symbolová knihovna. Vrstevnice jsou přímo polylinie z contourpy — ne vektorizace pixelů.

> ⚠ **`template_classic.omap` je foundation artefakt, ne generovaný soubor.** Ručně ho vyrobil
> uživatel v OpenOrienteering Mapper (Sez. 14, přepsán Sez. 18) — drží symbol IDs, color-table
> (vč. rozlišení Upper/Lower brown 50% pro z-order priorit) a georef, z nichž `omap_export.py` čte.
> **K jeho výrobě/regeneraci NESTAČÍ uložit novou prázdnou mapu** (File → New, ISOM 2017-2) — nese
> specifické úpravy nad výchozí sadou (varianty symbolů 501.1/512.2, čistá `<objects>` bez cizího
> balastu). Přesný postup výroby drží uživatel; při potřebě změny template si vyžádej aktualizovanou
> verzi od něj, needituj naslepo.

**Přestavba (Sezení 11):** generátor stavíme „znovu a lépe", vrstvu po vrstvě, s
důrazem na vizuální věrnost. **Procedurální (noise-půlka)** plošné vrstvy (vegetace, paseky, bažiny,
balvany) byly vědomě **zahozeny** (vypadaly uměle → kazily by domain gap feederu); historie v gitu.
Skály/balvany se od Sez. 30 kreslí **reálně** ze ZABAGED (204/207/206, + 208 pole balvanů Sez. 57), tedy jen v real-půlce.
Záměrně zatím NEobsahuje: **procedurální** vegetaci/bažiny/rýhy, **procedurální** vodu (reálná ze
ZABAGED je, Sez. 17), purpurovou závodní trať (§4.13), severník. (Pramen 312 se kreslí přes `--landmarks`, Sez. 44.)

## Cíl

Doložit, že metoda „mapa = vrstvy ze skalárních polí" produkuje použitelná
trénovací data **s anotací zdarma** — keystone pro modelovou větev (UC5),
obchází sparse-GT past z Pic2Omap.

## Spuštění

```powershell
# z kořene repa, ve venv (default = reálná data ČÚZK → maps/output):
.venv\Scripts\python.exe generator\generator.py --terrain noise --paths proc
# noise (procedurální Option 1, baseline 65) → maps/output; parametry:
# --seed INT  --rug 0-1 (členitost terénu, jen noise)  --det 0-1 (počet proc cest)

# reálná data ČÚZK (DMR 5G terén + ZABAGED vrstvy; default souřadnice = Soví vrch, §8.5):
.venv\Scripts\python.exe generator\generator.py --terrain real
# jiná lokalita: --lat 50.82 --lon 14.67  (WGS84; dlaždice se cachuje do connectors/.dmr_cache/)

# vývojářské lokality (--location nastaví lat/lon/rozměr + zapne všechny reálné vrstvy):
.venv\Scripts\python.exe generator\generator.py --location SV
# výstup → maps/<lokalita>/ (kotveno v kořeni LAB); viz DEV_LOCATIONS: SV/NL/LS/HS/NV
# data pro výsek se cachují do connectors/.zabaged_cache/
```

Každý běh píše i `<lokalita>.omap` (název = výstupní složka, Sez. 42; template-based nad `template_classic.omap` — otevři v OOM).

Dávkový dataset (`batch.py`) — sada map + manifest + náhledová mozaika:

```powershell
# noise sada (16 map, reprodukovatelná z seed0+n) → maps/dataset_noise:
.venv\Scripts\python.exe generator\batch.py
# reálná sada z lokalit ČR (CZ_LOCATIONS — 10 členitých OB oblastí, DMR 5G terén) → maps/dataset_real:
.venv\Scripts\python.exe generator\batch.py --terrain real
```

## Výstup (`maps/<lokalita>/`, gitignored)

| Soubor | Obsah |
|--------|-------|
| `rgb.png` | čistý render = X páru; skenové vady se přidávají on-the-fly v modelovém loaderu |
| `area_labels.png` | label rastr plošných ISOM symbolů z `.omap` (Y páru pro `Png2Area`; `pairs` `labels=True`, Sez. 87) |
| `rgb.pgw` | world file — georef rastru do S-JTSK (jen `--terrain real`; grid-north-up, rotace 0 = bez grivace) |
| `mask_contours.png` | binární maska vrstevnic |
| `mask_paths.png` | multi-class maska cest (1=503 / 2=505 / 3=502 / 4=504 / 5=506; proc dělá 1+2, real 2-6 dle dat) |
| `mask_water.png` | multi-class maska vody (1=304 / 2=305 / 3=306 / 4=301; jen `--water real`) |
| `mask_buildings.png` | maska budov (1=521; jen `--buildings real`) |
| `mask_symbols.png` | multi-class maska bodových symbolů extrémů (1=109 / 2=110 / 3=111) |
| `mask_formlines.png` | maska pomocných vrstevnic (103; jen `--terrain real`) |
| `mask_rides.png` / `mask_powerlines.png` / `mask_railways.png` / `mask_paved.png` / `mask_rocks.png` / `mask_bridges.png` / `mask_surfaces.png` / `mask_landmarks.png` / `mask_linefeatures.png` / `mask_marsh.png` / `mask_treerows.png` | masky reálných vrstev 508 / 510 / 509 / 501·501.1 / 204·206·207 / 512·512.2 / 401·402·402.1·412·520 / bodové orient. (524·526·530·417·312·311·203.2) / liniové orient. (104·513) / 308·310 Marsh/Indistinct (class 1/2) / 406 stromořadí / `mask_veg_area.png` 406·408·410·403 plošná predikční zeleň/open (jen ze separace reálné mapy; forest-age proxy archiv Sez. 102) (každá jen při své `--…real`; multi-class kde víc tříd) |
| `contours.geojson` | **vektor** vrstevnic + form lines (LineString + ISOM symbol 101/102/103; CRS S-JTSK pro real) |
| `<lokalita>.omap` | OpenOrienteering Mapper mapa (vždy; název = výstupní složka, Sez. 42; template-based: vrstevnice 101/102 + form lines 103 + cesty 502-506 + lesní průseky 508 + voda 301/304-306 + budovy 521 + vedení 510 + železnice 509 + kolejiště 501 + ostatní plocha v sídlech 501.1 (base, s děrami, Sez. 54) + skály 204/206/207 + mosty/tunely 512 + lávky 512.2 + plošný pokryv 401/520 (olivová: hřbitov + RÚIAN privátní + areály 114) + stromořadí 406 lineární les + řopíky + body 109/110/111, plná ISOM knihovna) |
| `meta.json` | seed, parametry, legenda tříd, info o vektor/omap exportu + blok `georef` (S-JTSK bbox, pixel_size_m, world_file, north, grivation_deg) |

Verify nástroj: **`compare_real_vs_gen.py`** — strojové porovnání generátoru se živě mapovanou OB mapou
z `resources/` (zatím Soví vrch). STAT 1 = symbolový crosswalk + pokrytí (pozor: reálné mapy bývají ISOM 2000,
gen 2017-2 → porovnání přes sémantiku, ne kód); STAT 2 = prostorová shoda po ISOM barvách (georef přes `.pgw`). Sez. 37.

## Stack

Python 3.14 (testováno; PEP 649/749 bez `__future__`) · numpy · contourpy (marching squares) · Pillow · pyproj (jen real režimy, WGS→S-JTSK) ·
scipy (jen `--rocks real`: morfologie + connected-components pro rock-relief z DMR, Sez. 63). Viz `requirements.txt`.
Venv v kořeni LAB (`.venv`) — sdílený pro `generator/` i `connectors/`. Konektory reálných dat žijí
v **`connectors/`** v kořeni LAB (`dmr.py` výškopis, `zabaged.py` komunikace + voda + budovy + vedení +
železnice + kolejiště + skály + mosty/tunely + řopíky + plošný pokryv + areály 114/kůlny 105, `ruian.py` katastr
(privátní pozemky → olivová 520, Sez. 42), `ortofoto.py` podklad — sourozenci, sdílejí `dmr.build_bbox` i
`arcgis.py` REST transport); generátor si jejich složku přidá na `sys.path` (Sez. 16).

Reálná data = ČÚZK DMR 5G (výškopis) + ZABAGED Polohopis (vektorové vrstvy) + ORTOFOTO (podklad), vše
open data **CC BY 4.0** (atribuce povinná — uložena i v `meta.json`).

## Determinismus

Stejný `seed` + parametry → identická mapa. PRNG = numpy `default_rng` (PCG64);
spec doporučuje mulberry32, ale potřebujeme jen reprodukovatelnost, ne bitovou
shodu s JS referencí.
