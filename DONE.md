# DONE — AzimutLab

Dokončené úkoly (stručně co se udělalo). Aktuální/čekající: TODO.md.

## Sezení 16 (2026-05-26) — Reálné cesty ze ZABAGED WFS (první UC2 konektor)
- [x] **`zabaged.py`** (nový, první reálný UC2 konektor) — reálné komunikace z ČÚZK ZABAGED
      Polohopis WFS 2.0.0 (`ags.cuzk.gov.cz`, **tatáž doména jako DMR**). Sourozenec `dmr.py`
      (NE kopie: dmr=rastr/výškopis, zabaged=vektor/cesty), sdílí `build_bbox` → bezešvost na terén.
      **GeoJSON output přímo** (obava IDEAS z GML parsingu padla), cache `.zabaged_cache/`.
- [x] **Verify-against-source před mapováním** (`_diagnostics`): axis order [x,y]=[easting,northing]
      ověřen na reálných souřadnicích; reálné hodnoty atributů (Cesta `povrch_k` Z/T/None,
      `typcesty_k`; Pěšina `TYPUSKOM_K`; Silnice `typsil_k`) → mapování psáno na datech, ne hádané.
- [x] **Mapování ZABAGED → ISOM** (`map_to_isom`, fyzický stav = ISOM logika): Silnice/Ulice →
      502 Wide road; Cesta zpevněná → 503 Road, nezpevněná → 504 Vehicle track; Pěšina udržovaná →
      505 Footpath, neudržovaná → 506 Small footpath. Turistická_trasa vynechána (duplikace sítě).
- [x] **`generator.py` `--paths proc|real`** (real ⇒ terrain real, validace ValueError). Render
      sjednocen `_draw_path` + `PATH_STYLE`/`PATH_CLASS` (DRY, izomorfismus proc↔real; casing pro
      502, dashed dle stylu). Proc/real cesty vyčleněny do `_generate_proc_paths`/`_generate_real_paths`
      (SLAP). Inverze S-JTSK→grid (Y-flip, sdílí georef vrstevnic). `_build_meta` +`paths_mode`
      (symbols/classes/licence dynamicky dle použitých kódů).
- [x] **`omap_export.py`** `USED_CODES` +502/504/506 (v template existují: id 108/111/113).
- [x] **Rozhodnutí: ZABAGED nativní, ne INSPIRE TN** — bohatší kategorizace komunikací pro les,
      tatáž ags doména, GeoJSON. INSPIRE TN = zbytečná harmonizovaná abstrakce téhož.
- [x] **Verify (čísly):** proc baseline seed 1 = 65 objektů (56+2+7) = baseline Sez. 14/15 →
      proc nezměněna. Validace flagu selhala správně. Real = 58 cest (502/503/504/506), OMAP 125
      obj. **Vizuál: cesty sedí na terén** (silnice v údolích, pěšiny traverzují svahy, Y-flip OK).
- [x] **KB/spec/README SLAP:** `data-sources.md` sekce „ZABAGED komunikace — WFS konektor"
      (endpoint, mapování, licence CC BY 4.0), spec §4.9/§9 (real-půlka), sandbox README,
      `.gitignore` +`.zabaged_cache/`.

## Sezení 15 (2026-05-25) — %AUDIT:CODE generator-poc + přemapování cesty 507→505
- [x] **%AUDIT:CODE** (1072 LOC, 5 modulů + spec + GLOSSARY + sandbox README) — LOC práh
      (≥500) padl podruhé po dvou přestavbách. Kód zdravý (DRY paleta, čistý dead-file stav);
      hlavní nález = reziduum SLAP dluhu Sez. 13/14 (drift ISOM kódů přežil v komentářích).
- [x] **D4(a) přemapování vedlejší cesty 507→505 Footpath** — verify-against-source proti
      `template_classic.omap`: ISOM 505 Footpath JE čárkovaná → pravidelná čárka generátoru jí
      odpovídá (Sez. 13 ji mylně zamítla „505 je plná"). Propsáno do 6 souborů: generator.py,
      omap_export.py, sandbox README, GLOSSARY, spec (§4.9/§8/§9, 5 míst), TODO. Konstanta
      `ISOM_FOOTPATH=505` teď sémanticky sedí (zrušilo K1 u kořene).
- [x] **D1/D2/K2 rezidua driftu** — docstring `generate()` 112/113/115→109/110/111; komentář
      „od nuly"→template-based; komentář z-orderu „505" po přemapování konzistentní.
- [x] **K4 SLAP** — meta dict (45 řádků) vyčleněn z `generate()` do `_build_meta()`.
- [x] **K3** — nepoužitý `template_sprint.omap` odstraněn (`git rm`; bez konzumenta v kódu).
- [x] **Verify (čísly):** noise seed 1 = 65 objektů (baseline Sez. 14, jen 507→505), real seed 1
      = 60 vrstevnic + 7 bodů (baseline Sez. 8–14). OMAP well-formed, vedlejší cesta id 112 (=505
      v template, dřív id 114=507). **Vizuál v OOM potvrzen uživatelem (Test OK, 505 a 507).**

## Sezení 14 (2026-05-25) — OMAP věrné body (template-based) + SLAP úklid ISOM driftu
- [x] **Uzavřena nezacommitovaná Sez. 13** — celá odpracovaná (kód+docs), ale nikdy
      necommitnutá (chybělo `%END`); dva commity (feat + docs) + push, procesní dluh splacen.
- [x] **OMAP export přepnut na template-based** (`omap_export.py`): z od-nuly (Sez. 13) zpět na
      template-based, ale nad VLASTNÍM čistým template `sandbox/generator-poc/template_classic.omap`
      (ISOM 2017-2, 169 symbolů / 35 barev, prázdné objekty). Skládáme jen `<objects>`; symbol id
      parsujeme z template podle ISOM kódu (id nejsou pořadová: 503→110, 507→114). `rotation=0` u 110.
- [x] **Věrná geometrie bodů** — 109 kruh / 110 elipsa (`area_symbol`) / 111 oblouk „⌣"
      (`line_symbol`) zděděné z template místo dřívějšího jednotného kruhu.
- [x] **Templaty přesunuty** `template_classic.omap` + `template_sprint.omap` do `sandbox/generator-poc/`
      (verzované, sebeobsažné; originály v gitignored `resources/` ponechány — uživatelova data).
- [x] **Refresh `output/map.omap`** — 169 symbolů (plná ISOM) + 65 objektů; **vizuál v OOM potvrzen uživatelem (Test OK)** — 110 elipsa / 111 oblouk sedí.
- [x] **SLAP úklid ISOM driftu** (dluh Sez. 13): GLOSSARY (kopeček 112/113→109/110, prohlubeň
      115→111, 116→112 Pit, cesta 505→507), spec §4.9/§8.1 (cesty 505→507), sandbox README
      (kódy + zrušený `--omap-template` + Dijkstra), README status box.
- [x] **INSPIRE TN/HY větev → IDEAS** (UC2→UC4-II): reálné cesty + voda jako vektor, oponováno
      WMS→WFS, real-only, dedikované příští sezení. + GLOSSARY termín INSPIRE.

## Sezení 13 (2026-05-25) — Terénní cesty (Dijkstra) + OMAP přestavba + oprava zastaralých ISOM kódů
- [x] **Terénně vázané cesty (§9, Dijkstra least-cost)** (`generator.py`): `_dijkstra_path`
      (8-soused, `heapq`, bez scipy) nahradil přímý splajn — cesty traverzují svah, nešplhají
      přes vrcholy. Cena = vzdálenost × (1 + LIN·sklon + SQ·sklon²) + **tvrdý strop 50 %**
      (hrana strmější zakázána, fallback). Cesty drženy v souř. mřížky (zdroj pro render i export).
- [x] **Odpuzování cest (#2)** — `_add_repulsion` zvyšuje cenu kolem nakreslené cesty → další
      cesta nesplyne (least-cost mezi blízkými konci by jinak dal jednu trasu).
- [x] **Oprava cesty přes sráz (#3)** — diagnostika `_diag_paths.py` ukázala max sklon 0.85
      (lineární penalty + repulsion). Kvadrát + strop → max sklon cest ≤ 0.49, průměr 3–6 %.
- [x] **Zastaralé ISOM kódy bodů opraveny (#1 nález):** 112/113/115 → **109/110/111**
      (Small knoll / Small elongated knoll / Small depression) dle ISOM 2017-2 Rev 6 (2024).
      Ověřeno proti oficiálnímu OOM `ISOM 2017-2_10000.omap`. Promítnuto: kód, meta, spec §4.10.
- [x] **OMAP export přepsán od nuly** (`omap_export.py`): z template-based (cizí `.omap`) na
      vlastní čistou ISOM sadu — `<colors>` (Brown/Black) + `<symbols>` (7) + objekty
      vrstevnice (101/102) + cesty (503/507) + body (109/110/111). Odstranilo dědění bordelu
      (101.1 LIDAR, 503 Minor road, cizí podklady). `--omap-template` zrušen (OMAP vždy).
- [x] **ISOM verze ověřena** (IOF): 2017-2 je nejnovější (Rev 6 2024, příští až ISOM2030).
- [x] **template_classic/sprint** — uživatel vyrobil v OOM vlastní čisté ISOM/ISSprOM templaty,
      vybrán/přejmenován `template_classic.omap` (1:10000) + `template_sprint.omap` (1:4000).

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
