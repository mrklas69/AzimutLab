# generator

Generátor výseku mapy pro orientační běh — **pilíř Laboratoře** (UC4-I/UC5
enabler-feeder), ne sandbox experiment (povýšen ze `sandbox/generator-poc/`
v Sez. 39 — 2600+ LOC / 24 vrstev už dávno není „PoC"). Konzumuje konektory
reálných dat z `connectors/` (UC2). Realizuje **MVP řez** specifikace
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
  **312** (ze `Zdroj_podzemních_vod`, v demo výřezu žádný). Procedurální voda (hydro jádro D8) zatím ne,
- **budovy** — `--buildings real` (real-půlka, Sez. 18; týž `zabaged.py`): `Budova_..._plocha_` →
  ISOM **521 Building** (plošný černý symbol). Vyžaduje `--terrain real`. **Kreslené RAW jako voda**
  (Sez. 27 — generalizace L1 i displacement L2 zavrženy, komolily tvar/polohu; *generalizuj jen s důkazem*),
- **pomocné vrstevnice** — form lines ISOM **103** (Sez. 29; derivace z DMR, ne ZABAGED — jen `--terrain real`),
  kde mírný svah AND zakřivený terén; min. délka 3 mm,
- **el. vedení** — `--powerlines real` (Sez. 24): `Elektrické_vedení` → ISOM **510** (příčky na reálných
  sloupech `Stožár_elektrického_vedení`),
- **železnice** — `--railways real` (Sez. 28+31): `Železniční_trať`+`_vlečka`+`Tramvajová dráha` → ISOM
  **509** (kombinovaný symbol, bílý knockout),
- **kolejiště / zpevněné plochy** — `--paved real` (Sez. 28): `Kolejiště` → ISOM **501 Paved area** (plocha
  s obrysem; „10 kolejí" je v datech jedna plocha, ne linie),
- **skály/balvany** — `--rocks real` (Sez. 30): `Osamělý_balvan…`→**204**, `Skupina_balvanů__bod_`→**207**,
  `Skalní_útvary` (plocha)→**206** (KISS vrstva = jeden symbol),
- **mosty/tunely/lávky** — `--bridges real` (Sez. 31–33): `Most`→**512** (2 paralely + buffer crop),
  `Tunel`→**512** otočené 90° na vjezdech, `Lávka`→**512.2**,
- **řopíky** — `--ropiky real` (Sez. 26–27): `Bunkr` LO37 jako asset, orientovaný k nejbližší státní hranici,
- **plošný pokryv** — `--surfaces real` (Sez. 41-42): open land (louka/park/pole/sad) → ISOM **401** (plná žlutá,
  KISS „open land jako jedna žlutá"; pole 412 / sad 413 s patternem = druhá vlna) + **olivová 520 Area which shall
  not be entered** ze tří zdrojů (Sez. 42): hřbitov + **RÚIAN privátní pozemky** (zahrada+zastavěná, `ruian.py`) +
  **areály účelové zástavby** (ZABAGED 114: škola/hřiště/sport/kasárna… → 520, asfalt 408/409 → 501). Kůlny (105)
  → 521. Parkoviště + asfalt → 501 přes `--paved`. **Z-order vespod** (podklad pod
  vrstevnicemi; olivová nad žlutou; les = bílá default = vegetace gate). Vyžaduje `--terrain real`,
- **budovové stavby** — `--buildings real` (Sez. 43 rozšíření): + `Zámek`/`Hrad` → **521**, `Rozvalina, zřícenina`
  → **523 Ruin** (čárkovaný obrys bez výplně). ČÚZK je vede zvlášť, ne v `Budova_99` (domov mládeže = bývalý zámek),
- **bodové orient. prvky** — `--landmarks real` (Sez. 43, audit katalogu): kříž→**530**, mohyla→**526**,
  věž/vodojem/silo/těžní/mlýn/motor/věžovitá stavba→**524**, významný strom→**417** (zelený kroužek),
- **liniové orient. prvky** — `--linefeatures real` (Sez. 43): sráz→**104 Earth bank** (plná + jednostranné ticky),
  zeď/hradba→**513 Wall**, liniová vegetace→**416** (zelená čárkovaná),
- **ground-truth masky** — každá vrstva i jako segmentační maska (§8.1),
- **reálný terén** — `--terrain real` dosadí ČÚZK DMR 5G místo šumu (§8.5, Option 2;
  výškopis z `dmr.py`).
- **vektor** — `contours.geojson` (ISOM **101/102** linie, georef S-JTSK pro real terén) a
  `<lokalita>.omap` (vždy; §9; `omap_export.py`; název = výstupní složka, Sez. 42). OMAP je **template-based** nad vlastním čistým ISOM
  2017-2 template `template_classic.omap` → věrná geometrie bodů (110 elipsa, 111 oblouk) + plná
  symbolová knihovna. Vrstevnice jsou přímo polylinie z contourpy — ne vektorizace pixelů.

**Přestavba (Sezení 11):** generátor stavíme „znovu a lépe", vrstvu po vrstvě, s
důrazem na vizuální věrnost. **Procedurální (noise-půlka)** plošné vrstvy (vegetace, paseky, bažiny,
balvany) byly vědomě **zahozeny** (vypadaly uměle → kazily by domain gap feederu); historie v gitu.
Skály/balvany se od Sez. 30 kreslí **reálně** ze ZABAGED (204/207/206), tedy jen v real-půlce.
Záměrně zatím NEobsahuje: **procedurální** vegetaci/bažiny/rýhy, **procedurální** vodu (reálná ze
ZABAGED je, Sez. 17), purpurovou závodní trať (§4.13), severník. (Pramen 312 je v konektoru, v demo výřezu chybí.)

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
| `mask_rides.png` / `mask_powerlines.png` / `mask_railways.png` / `mask_paved.png` / `mask_rocks.png` / `mask_bridges.png` / `mask_surfaces.png` | masky reálných vrstev 508 / 510 / 509 / 501 / 204·206·207 / 512·512.2 / 401·520 (každá jen při své `--…real`; surfaces multi-class 1=open land, 2=olivová zákaz vstupu) |
| `contours.geojson` | **vektor** vrstevnic + form lines (LineString + ISOM symbol 101/102/103; CRS S-JTSK pro real) |
| `<lokalita>.omap` | OpenOrienteering Mapper mapa (vždy; název = výstupní složka, Sez. 42; template-based: vrstevnice 101/102 + form lines 103 + cesty 502-506 + lesní průseky 508 + voda 301/304-306 + budovy 521 + vedení 510 + železnice 509 + kolejiště 501 + skály 204/206/207 + mosty/tunely 512 + lávky 512.2 + plošný pokryv 401/520 (olivová: hřbitov + RÚIAN privátní + areály 114) + řopíky + body 109/110/111, plná ISOM knihovna) |
| `meta.json` | seed, parametry, legenda tříd, info o vektor/omap exportu + blok `georef` (S-JTSK bbox, pixel_size_m, world_file, north, grivation_deg) |

Verify nástroj: **`compare_real_vs_gen.py`** — strojové porovnání generátoru se živě mapovanou OB mapou
z `resources/` (zatím Soví vrch). STAT 1 = symbolový crosswalk + pokrytí (pozor: reálné mapy bývají ISOM 2000,
gen 2017-2 → porovnání přes sémantiku, ne kód); STAT 2 = prostorová shoda po ISOM barvách (georef přes `.pgw`). Sez. 37.

## Stack

Python 3.12+ · numpy · contourpy (marching squares) · Pillow · pyproj (jen real režimy, WGS→S-JTSK).
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
