# DONE — AzimutLab

Dokončené úkoly (stručně co se udělalo). Aktuální/čekající: TODO.md.

## Sezení 12 (2026-05-25) — Recovery zastaralého klonu + fetch-check + vize dvoustupňové věrnosti
- [x] **Recovery:** lokální klon byl 20 commitů za origin (founding vs Sez. 11) — `%BEGIN`
      běžel na zastaralém stavu, UC2 odpracován redundantně. Záloha do branche
      `stale-hejna-2026-05-25` + `reset --hard origin/main`, gitignored smetí uklizeno.
- [x] **Fetch-check do `%BEGIN` (krok 0)** (`docs/PROMPTS.md`): `git fetch` + porovnat HEAD
      s `origin/main` před prací. Náprava příčiny omylu (clean ≠ up-to-date).
- [x] **Vize dvoustupňové věrnosti** (`IDEAS.md` + spec §8.4): stupeň 1 kartografická věrnost
      (fyzikální gate) → stupeň 2 věrnost skenu (augmentace). Bez A/B (kolize s Pic2Omap fází).
      Start = cesty Dijkstra (TODO `[!]`); hydro jádro D8 (toky/prameny/jezera-rybníky/bažiny) další.
- [x] **`resources/` = 6 reálných map** (gitignored): georef prozradil 2 OOM dema (vyřazena).
      Smíšený původ (vlastní vs klubové, „koupené" ≠ copyright) + role hold-out/reference v KB.

## Sezení 11 (2026-05-25) — Přestavba generátoru: řez na vrstevnice + cesty (§4.9)
- [x] **Cesty (§4.9)** (`generator.py`): Catmull-Rom splajn napříč mapou — `_catmull_rom`
      (uniform, krajní body zdvojené) + `_draw_dashed` (čárkování po délce oblouku). Waypointy
      okraj→okraj (H/V) + kolmý jitter, `n = 1+round(det*1.6)`. Hlavní plná černá (ISOM **503
      Road**, 2 px) / vedlejší čárkovaná (ISOM **505 Footpath**). Nová `mask_paths.png`
      (multi-class 1/2), nový param `--det`. Z-order: po vrstevnicích, před body. Splnil
      `[!]` dluh ze Sez. 10 (cesty odkládané od Sez. 6).
- [x] **Řez „znovu a lépe"** — zahozeny plošné vrstvy (vegetace §4.2, paseky §4.3, bažiny
      §4.4, balvany §4.11) + mrtvá pole (`slope/eb/gradient`, `_to_pixels`, `box_blur`,
      `_draw_dotted`) + masky `mask_veg/water/rock`. Důvod (A1): **vizuální věrnost** — vrstvy
      vypadaly uměle (bažina = pole „plusů") → kazily by domain gap feederu pro UC5. Zahodit
      špatně vypadající vrstvu > krmit model artefakty. Zůstaly vrstevnice + body 112/113/115
      + vektor/`.omap` (A2). Import palety zúžen na 3 barvy (bílá/hnědá/černá).
- [x] **`batch.py` srovnán** s novou signaturou `generate(seed, rug, det, …)` (pryč vd/wat/rock).
- [x] Verify (čísly, ne vírou): **real 60 vrstevnic + 7 bodů = bitově shodné s baseline Sez.
      8-10** (řez se vrstevnic/bodů nedotkl). Noise 56 vrstevnic + 2 cesty + 7 bodů. Staré masky
      pryč, `mask_paths` nenulová. Vizuál obou renderů čistý a „orienťácký". Cesty terén
      nerespektují (kříží kopce) — vědomá §4.9 vlastnost, §9 Dijkstra odložen.
- [x] **Volba A (procedurální cesty) potvrzena nad daty:** „převzít cesty ze ZM5" oponováno —
      ZM5 je zrušený rastr (1.7.2023 → ZTM5), vektor cest je v ZABAGED Polohopis (WFS, CC BY 4.0).
      Reálné cesty = UC2 konektor (data-driven), funguje jen pro real terén → odloženo do IDEAS.
      Procedurální §4.9 funguje noise i real. SLAP: spec §4/§4.9/§8.1, README ×2, GLOSSARY.

## Sezení 10 (2026-05-25) — Bodové symboly lokálních extrémů (§4.10)
- [x] **Generalizace malých izolinií → bodové symboly** (`generator.py`): uzavřená malá
      smyčka vrstevnice = lokální extrém → bodový symbol místo prstence (ISOM generalizace).
      Detekce dle TODO: uzavřenost + plocha shoelace pod prahem (`KNOLL_MAX_AREA_M2`=600 m²)
      + výška centroidu vs úroveň. Lok. max → **112 Small knoll** (hnědá tečka) / **113
      Elongated knoll** (poměr stran bbox > 2,5, hnědá elipsa); lok. min → **115 Small
      depression** (hnědý oblouk „⌣"). **116 Pit vědomě vynechán** — jiná feature class,
      z výškopisu neodlišitelný od 115 (oponováno TODO „všechny 4").
- [x] **`mask_symbols.png`** (multi-class GT) — konečně implementuje §8.1 (Sez. 9 D5 ji
      značila jako neimplementovanou). Třídy 1=112 / 2=113 / 3=115. + `point_symbols`
      v `meta.json` (detekční anotace COCO/YOLO styl: symbol, název, pozice mřížka i px).
- [x] Verify (čísly, ne vírou): zákon zachování `linie + symboly` drží na obou terénech
      (noise 63=56+7, real 67=60+7). **Real 67 = bitově shodné s baseline Sez. 8/9** —
      jen 7 linií se přesunulo na symboly. Maska: všech 7/7 symbolů má nenulovou třídu
      u středu; vizuál zvětšených výřezů potvrdil tvary 112/113/115 + spojitost okolních
      vrstevnic. 116/204 vynechány záměrně.

## Sezení 9 (2026-05-25) — %AUDIT:CODE + %AUDIT:DOCS (foundations úklid)
- [x] **%AUDIT:CODE** nad `sandbox/generator-poc/` (5 modulů, ~750 LOC; práh padl 8 sez/500 LOC).
      Hlavní závěr: mrtvého kódu skoro není (`%END` cleanup funguje). Opraveno: **R1** `C_WHITE`
      obcházen hardcoded `255` → zapojen z palety (DRY); **K1** `from __future__ import
      annotations` redundantní na Py 3.14 (PEP 649/749, ověřeno verzí) → smazán z 5 modulů;
      **K2** duplicita `TILE_M*(GW/GH)` → konstanta `WORLD_W_M`; **K3** jazyk v komentáři.
      **R2** (`C_PURPLE`/`Swatch.meaning`) vědomě ponecháno (izomorfní API palety).
- [x] **%AUDIT:DOCS** nad 19 `.md`. Opraveno D1-D7: **D1** `sandbox/README` „zatím prázdný"
      (5 sez. nepravda) → výčet experimentů + konvence `<NN>-` uvolněna; **D2** `architecture`
      rozpor „kód zatím žádný" vs „první reálný kód"; **D3** spec §4.5 tloušťky 0,7/1,3→1/3 px;
      **D4** `tools-models` stack +pyproj; **D5** spec §8.1 `mask_symbols` neimplementováno;
      **D7** `data-sources` URL `.cz`→`.gov.cz`.
- [x] **D6: založen `GLOSSARY.md`** (root) — doménový slovník (OB/ISOM, ČÚZK data, UC DAG,
      nástroje); propsán do README (layout + Docs). PROMPTS na něj odkazovaly, neexistoval.
- [x] Verify (ne odhad): noise + real (cache) běh OK, roh pixelu bílý, 8 barev = paleta,
      real 67 linií = bitově shodné s baseline Sez. 8 → úklid behavior-preserving.

## Sezení 8 (2026-05-25) — Vektorizace vrstevnic na ISOM + DRY paleta + ČSOS KB
- [x] **DRY: paleta → `palette.py`** (jediný zdroj pravdy): slovník `PALETTE` (slug→Swatch
      rgb+význam) + odvozené `C_*`. `generator.py` importuje (zahozeny lokální konstanty +
      inline `(0,0,0)`). Oponováno TODO „→ isom-issprom.md": runtime konzument je Python,
      parsovat MD je proti KISS → SSoT v kódu, docs (spec §5, KB) odkazují. Verify: noise
      render + batch import OK.
- [x] **Mapový portál ČSOS → KB** (`data-sources.md`): zdroj reálných OB map (cesta B,
      7000+ map, Mapová rada ČSOS + T-MAPY). **Gate ZAVŘENA dvojitě** (ověřeno ze stránky
      „O projektu"): copyright klubů + jen náhledy 96 dpi s vodoznakem, souhlas vydavatele
      nutný i pro výzkum. Verify-against-source dotáhl licenci z „nevím" na jednoznačné NE.
- [x] **Vektor vrstevnic → `contours.geojson`** (§9): polylinie z contourpy se symbolem
      **101 Contour / 102 Index contour**, georef **S-JTSK (EPSG:5514)** pro real (lokální
      metry noise). Žádná vektorizace rastru (AutoTrace) — z přesného zdroje. `dmr.build_bbox`
      zveřejněn. Verify: 67/68 linií, rozsah přesně 1465×1000 m.
- [x] **`.omap` export → `omap_export.py`** + `generator.py --omap-template`: template-based
      (nahradí `<objects>` ve funkčním ISOM `.omap`), Local CRS, paper-space transform
      (1 m→100 µm). Nesdílí kód s Pic2Omap `db2omap` (ten z rastru) — jen formát. **Verify
      uživatelem v OOM: vrstevnice sedí.** (OOM 0.9.6 jen `windows` platform → headless nejde.)
- [x] **lasertool / AutoTrace / multi-echo** do KB (`tools-models.md`, `data-sources.md`):
      lasertool = LIDAR point cloud→rastr (Karttapullautin rodina, naráží na vegetace gate);
      vektorizační nástroje pro UC4-III/UC3 (CoVe napřed); multi-echo LAS lze koupit (odloženo).

## Sezení 7 (2026-05-24) — Reálný batch dataset z lokalit ČR
- [x] **`batch.py --terrain noise|real`:** reálná větev vyrobí dataset map z různých míst ČR
      (`CZ_LOCATIONS` — 10 členitých OB oblastí). Hlavní variace = lokalita; losují se jen
      `vd/wat/rock` (`rug` u reálného terénu mrtvý). Manifest s lokalitou + souřadnicemi.
- [x] **Noise sada zachována bitově reprodukovatelná** (rozvětvení dle terénu — pořadí
      losování `master.random` se neposunulo). Variace `--rock` v noise větvi odložena (TODO).
- [x] **Montáž s popisky lokalit** (`build_montage(labels=...)`, bílý podklad + černý text);
      default `--out` → `output/dataset_<terrain>` (noise/real se nepřepíšou).
- [x] **Bug `dmr.py` (cache-before-validate):** cache zapisovala `raw` PŘED validací TIFF →
      degenerovaný soubor se uložil a každý další běh na něm spadl. Opraveno: `Image.open`
      předchází zápisu + srozumitelná `RuntimeError` (hint „mimo pokrytí / za hranicí").
- [x] **Krušné hory mimo hranici:** souřadnice 50.68,13.45 ležely na hřebeni = státní hranici,
      bbox 1466 m zasahoval za ni → ČÚZK vracel oříznutý 1364 B TIFF (ověřeno 3×, CL match).
      Posunuto na jižní svahy (50.50,13.40), převýšení 108 m. Odhaleno verify, ne tipem.
- [x] Verify (ne odhad): 10 map vygenerováno, montáž + manifest sedí, detail Moravského krasu
      (rock=0,975) ukazuje balvany ve strmu, reálné vrstevnice, bažinu v údolní nivě.

## Sezení 6 (2026-05-24) — Věrnost generátoru: balvany, obrys bažin, index contours
- [x] **Tečkovaný obrys bažin (§4.4):** `contourpy` na binární masce bažin (level 0,5),
      helper `_draw_dotted` (arc-length vzorkování teček). Obrys přesně kopíruje výplň,
      kreslen pod vrstevnicemi (z-order). Doplněn chybějící prvek spec §4.4.
- [x] **Vrstva balvanů (§4.11):** nový `--rock` parametr, `round(rock*120)` černých teček,
      přijetí `0.25 + slope*0.9` (slope-vážené = fyzikálně smysluplné), GT maska `mask_rock.png`.
- [x] **Index contours výraznější:** hlavní vrstevnice 2→3 px (baseline ukázal, že 2 px bez
      antialiasingu splývá; jasnější odlišení tříd pomáhá i UC5, v intencích spec §8.2).
- [x] Verify (ne odhad): noise render OK, `--terrain real` regrese OK (cache hit 0,31 s),
      všech 5 GT masek se zapisuje. Vizuálně ověřen obrys i slope-vážení balvanů.
- [x] `.gitignore`: vzor `output_*/` — obrana proti commitnutí pojmenovaných scratch renderů.

## Sezení 5 (2026-05-24) — Option 2: reálný ČÚZK DMR 5G terén
- [x] **Feasibility ověřena prakticky** (ne odhad): `pyproj` wheel na Py3.14 funguje;
      ČÚZK DMR 5G ArcGIS ImageServer (`/arcgis2/rest/services/dmr5g/ImageServer`,
      pixelType F32, S-JTSK) vrací float grid přes `exportImage`; Pillow čte float TIFF
      jako mode "F" → **žádný GDAL/rasterio nutný.**
- [x] **`dmr.py`** (nový): stažení DMR 5G dlaždice, WGS84→S-JTSK (pyproj), poměrový bbox
      (izotropní buňka), disk cache, sanity check výšek.
- [x] **`generator.py`**: `--terrain noise|real` + `--lat/--lon`, reálný `elev` v metrech
      → `hbase` normalizací, sjednocené hlavní vrstevnice (`level % 25`), atribuce v `meta.json`.
- [x] Ověřeno vizuálně: reálné vrstevnice (údolí/hřbety/sráz), zmenšený domain gap vs blob (§8.4).
      Regrese noise OK, cache hit 0,31 s, vegetace/bažiny správně syntetické (DMR ground-only).
- [x] SLAP propsání: spec §8.5, architecture, IDEAS, RESEARCH, data-sources (exportImage kanál),
      sandbox README (stack +pyproj, CC BY 4.0 atribuce), `.gitignore` (`.dmr_cache/`).

## Sezení 4 (2026-05-23) — Procedurální generátor OB map (MVP)
- [x] Resumé projektu (sjednocení obrazu) + debata o konektorech: tři datové cesty
      (A geodata / B korpusy / C syntetika), sim-to-real recept.
- [x] Spec generátoru zachycena do repa: `docs/kb/generator-procedural.md` (z Downloads).
- [x] **První reálný kód v repu:** `sandbox/generator-poc/generator.py` — vrstevnice
      (izolinie) + vegetace + bažiny + GT masky zdarma. Stack Python 3.14 + numpy +
      contourpy + Pillow (scikit-image vynechán, KISS + 3.14 wheels).
- [x] `batch.py` — mini dataset 16 map, reprodukovatelný z (seed0=1000, n=16), diverzita
      ověřena mozaikou.
- [x] Reframe (architecture/IDEAS): UC4-I syntetika z „úplný konec" → enabler-feeder pro UC5.

## Sezení 3 (2026-05-23) — Vegetace gate (ČÚZK plné mračno = NE)
- [x] Ověřeno: ČÚZK **neposkytuje** plné klasifikované multi-echo mračno jako open data.
      Nový hustý DMP OK je z **obrazové korelace** (fotogrammetrie, jen povrch, žádné echoes),
      surové LLS mračno není open. → „Vegetace gate" zavřena, náhrada jen CHM+NIR proxy.
      Ověřeno proti primárnímu zdroji (technická zpráva DMP OK, 1/2026).
- [x] KB konsolidace (SLAP): `data-sources.md` (DMP OK, oprava DMR 5G, „Vegetace gate"),
      `RESEARCH.md` (otázka uzavřena), `TODO.md` (`[!]` hotovo).

## Sezení 2 (2026-05-23) — UC2 průzkum ČÚZK + LIDAR research
- [x] UC2 průzkum ČÚZK geoportálu: přístup (WMS/WMTS/WFS/WCS/ATOM) + **licence = CC BY 4.0**
      (gate otevřena → na ČÚZK datech lze stavět UC4-II/III s atribucí).
- [x] DMR 5G (LIDAR výškopis): dostupnost 100 % ČR, formát LAZ, licence CC BY 4.0.
- [x] Naplněn `docs/kb/data-sources.md` — ČÚZK katalog + oprava terminologie ZTMP → ZABAGED/ZTM.
- [x] Doplněn `RESEARCH.md` — metoda LIDAR → orienteering mapa (Karttapullautin); nález
      „DMR 5G ground-only ≠ vegetace, třeba plné mračno bodů".

## Sezení 1 (2026-05-22) — Founding
- [x] Seznámení s Pic2Omap (architektura, workflow, dokumentační kultura).
- [x] %THINK nad 5 UC → zjištěno, že tvoří DAG (enablery pod aplikacemi), ne seznam.
- [x] Rozhodnutí: vztah k Pic2Omap = deštník→monorepo (B→A); MVP = UC1; jméno = AzimutLab.
- [x] Založena kostra repo: README, CLAUDE.md overlay, docs/PROMPTS.md,
      docs/architecture.md (kanonický DAG), IDEAS, RESEARCH, docs/kb/ (3 soubory),
      sandbox/, TODO/DONE/DIARY, .gitignore, git init (branch main).
