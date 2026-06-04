# generator

Generátor výseku mapy pro orientační běh — **pilíř Laboratoře** (UC4-I/UC5
enabler-feeder), ne sandbox experiment (povýšen ze `sandbox/generator-poc/`
v Sez. 39 — 2600+ LOC / 24 vrstev už dávno není „PoC"). Konzumuje konektory
reálných dat z `connectors/` (UC2). (Pozn.: UC5 **model** žije v samostatném `model/`,
sourozenec `generator/`/`connectors/` — ne uvnitř generátoru; viz README repa „Repository layout".)
**UC5 továrna párů (Sez. 82/83):** `separate.py` (`separate_areas`) separuje predikční plochy (vegetace
406/408/410) z reálné Livelox mapy; `pairs.py` (`build_pair(cid)`) je spojí s real ČÚZK vrstvami `generate_map`
do JEDNÉ georeferencované `.omap` per classId (provenance real/predict) — `[render, .omap]` pár pro `reconstructor()`.
Separace **downscaluje vstupní gt na `TARGET_MPP`=1,33 PŘED vektorizací** (Sez. 85, `separate_areas(src_mpp)` —
`pairs` předá `meta["effectiveMppX"]`): řeší výkon žroutu #1 (O(n² prstenců) — 31,6× zrychlení na jemném skenu,
věrnost zachována) + sjednotí měřítko separace napříč korpusem. Polygony se ×f vrací na původní grid (volající beze změny).
**Fáze II `degrade.py` (Sez. 86):** `degrade(rgb, seed)` degraduje čistý render → „sken" (`scan.png` = X páru) —
4 fotometrické vrstvy (CMYK misregistrace / blur / papír+zažloutnutí / šum+JPEG), Y (`.omap`) se nemění. `pairs`
volá s `degrade=True`. Geometrie (rotace/warp) NEní zde — patří na úroveň páru/dlaždice (loader D4, DRY). omap2png =
náš rastr (`generate_map` dělá `rgb.png`); C++ headless OOM až s důkazem doménového gapu (Sez. 82).

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
    typu a povrchu. Vyžaduje `--terrain real` (sdílí výsek s DMR → cesty sednou na terén),
- **lesní průseky** — `--rides real` (Sez. 36; týž `zabaged.py`): `Lesní průsek` → ISOM **508 Narrow ride**
  (průhled lesem bez vyšlapané cesty; černá čárkovaná 3,0/0,375 mm). KISS vždy 508; runnability pozadí se
  nekreslí (vegetace = UC5). Vyžaduje `--terrain real`,
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
  nahradila generalizovaný ZABAGED `Skalní_útvary` (jeden blob → věrná členitost věží/průchodů, ověřeno proti Mapy.com),
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
- **budovové stavby** — `--buildings real` (Sez. 43 rozšíření): + `Zámek`/`Hrad` → **521**, `Rozvalina, zřícenina`
  → **523 Ruin** (čárkovaný obrys bez výplně). ČÚZK je vede zvlášť, ne v `Budova_99` (domov mládeže = bývalý zámek),
- **bodové orient. prvky** — `--landmarks real` (Sez. 43, audit katalogu): kříž→**530**, mohyla→**526**,
  věž/vodojem/silo/těžní/mlýn/motor/věžovitá stavba/**tovární komín** (Sez. 52)→**524**, významný strom→**417** (zelený kroužek);
  **Sez. 44**: pramen→**312** (modré „U" ústím nahoru), jeskyně+šachta→**203.2 Cave** (černá „Λ" stříška hrotem
  nahoru), nádrž→**311** (modrý čtverec, z centroidu),
- **mokřady** — `--marsh real` (Sez. 44): bažina/močál + rašeliniště→**308 Marsh** (modrá vodorovná šrafa;
  KISS vždy crossable, NE 307),
- **liniové orient. prvky** — `--linefeatures real` (Sez. 43): sráz→**104 Earth bank** (HNĚDÁ plná + jednostranné ticky),
  zeď/hradba→**513 Wall**, rokle/výmol→**107 Erosion gully** (Sez. 58; HNĚDÁ plná bez ticků, mirror 104; v ČR řídká, Σ0 na DEV),
- **stromořadí** — `--treerows real` (Sez. 45): `Liniová vegetace`→**406 Vegetation: slow running** („lineární les":
  osa→buffer→úzký světle zelený pás; oprava 416 = hranice porostů byla sémanticky špatně pro řadu stromů),
- **věk porostu → zeleň** — `--forest-age real` (Sez. 62, `forest.py`): AOPK porostní skupiny (atribut `BARVA`=věk)
  → ISOM **406/408/410** (mlazina→410 fight tmavá / tyčkovina→408 walk / mladší→406 slow / staré+bezlesí→bílá).
  **PROXY/predikce** (věk≠runnability; 2. půlka generátoru, značeno `proxy:true`), absolutní řezy (ne per-mapové),
  pokrytí 3/5 DEV (SV/HS bez AOPK dat). **První predikční střípek k vegetaci** (gate pro open-LiDAR zavřená, Sez. 59),
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
| `rgb.png` | finální mapa (vstup modelu) |
| `rgb.pgw` | world file — georef rastru do S-JTSK (jen `--terrain real`; grid-north-up, rotace 0 = bez grivace) |
| `mask_contours.png` | binární maska vrstevnic |
| `mask_paths.png` | multi-class maska cest (1=503 / 2=505 / 3=502 / 4=504 / 5=506; proc dělá 1+2, real 2-6 dle dat) |
| `mask_water.png` | multi-class maska vody (1=304 / 2=305 / 3=306 / 4=301; jen `--water real`) |
| `mask_buildings.png` | maska budov (1=521; jen `--buildings real`) |
| `mask_symbols.png` | multi-class maska bodových symbolů extrémů (1=109 / 2=110 / 3=111) |
| `mask_formlines.png` | maska pomocných vrstevnic (103; jen `--terrain real`) |
| `mask_rides.png` / `mask_powerlines.png` / `mask_railways.png` / `mask_paved.png` / `mask_rocks.png` / `mask_bridges.png` / `mask_surfaces.png` / `mask_landmarks.png` / `mask_linefeatures.png` / `mask_marsh.png` / `mask_treerows.png` | masky reálných vrstev 508 / 510 / 509 / 501·501.1 / 204·206·207 / 512·512.2 / 401·402·402.1·412·520 / bodové orient. (524·526·530·417·312·311·203.2) / liniové orient. (104·513) / 308 Marsh / 406 stromořadí / `mask_forest_age.png` 406·408·410 věk porostu PROXY (každá jen při své `--…real`; multi-class kde víc tříd) |
| `contours.geojson` | **vektor** vrstevnic + form lines (LineString + ISOM symbol 101/102/103; CRS S-JTSK pro real) |
| `<lokalita>.omap` | OpenOrienteering Mapper mapa (vždy; název = výstupní složka, Sez. 42; template-based: vrstevnice 101/102 + form lines 103 + cesty 502-506 + lesní průseky 508 + voda 301/304-306 + budovy 521 + vedení 510 + železnice 509 + kolejiště 501 + ostatní plocha v sídlech 501.1 (base, s děrami, Sez. 54) + skály 204/206/207 + mosty/tunely 512 + lávky 512.2 + plošný pokryv 401/520 (olivová: hřbitov + RÚIAN privátní + areály 114) + stromořadí 406 lineární les + řopíky + body 109/110/111, plná ISOM knihovna) |
| `meta.json` | seed, parametry, legenda tříd, info o vektor/omap exportu + blok `georef` (S-JTSK bbox, pixel_size_m, world_file, north, grivation_deg) |

Verify nástroj: **`compare_real_vs_gen.py`** — strojové porovnání generátoru se živě mapovanou OB mapou
z `resources/` (zatím Soví vrch). STAT 1 = symbolový crosswalk + pokrytí (pozor: reálné mapy bývají ISOM 2000,
gen 2017-2 → porovnání přes sémantiku, ne kód); STAT 2 = prostorová shoda po ISOM barvách (georef přes `.pgw`). Sez. 37.

## Stack

Python 3.12+ · numpy · contourpy (marching squares) · Pillow · pyproj (jen real režimy, WGS→S-JTSK) ·
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
