# DONE — AzimutLab

Dokončené úkoly (stručně co se udělalo). Aktuální/čekající: TODO.md.

## Sezení 42 (2026-05-29) — Olivová 520 z katastru (RÚIAN) + areály účelové zástavby + audit land-cover
- [x] **%THINK olivová 520 + probe RÚIAN** (verify-against-source, foundations před kódem). Nápad uživatele:
      olivovou (zákaz vstupu) volí mapař na soukromé pozemky u domů → vzít z katastru parcely se stavbou.
      Probe: **RÚIAN** běží na témže ČÚZK ArcGIS serveru, vrstva 5 `Parcela` má `druhpozemkukod` (codedValue
      doména ze serveru), `f=geojson` (izomorfní se ZABAGED), maxRec 1 000 000. **Pravidlo: druh ∈ {5 zahrada,
      13 zastavěná plocha a nádvoří} → 520**. Licence: veřejná open data zák. 111/2009 Sb. SV: 649+1212 parcel.
- [x] **Olivová 520 z RÚIAN** (nový konektor `ruian.py`, sourozenec). `fetch_private_land` (`where druhpozemkukod
      IN (5,13)`) + `map_private_land_to_isom`→520. Třetí zdroj do `_generate_real_surfaces` (z-order: olivová NAD
      žlutou → zahrada přemaže žlutý sad). 520 už plně zapojená (Sez. 41) → žádná změna draw/mask/omap/meta, jen víc
      prvků. `ISOM_CEMETERY`→`ISOM_OUT_OF_BOUNDS` (propsáno všude, 0 reziduí). Verify LS: centrum města souvisle
      olivové s žlutými parky (test uživatele „střed Liberce olivový s výjimkou parků" ✓).
- [x] **DRY refaktor — `arcgis.py`** (volba uživatele DRY > duplikace). Zobecněn `zabaged._fetch_layer` + geom
      parsery → sdílený `fetch_geojson_layer(server, layer_id, …)` + `geom_to_*` (cache-key zachován → cache se
      neinvalidovala). `zabaged.py` i `ruian.py` ho sdílí (precedent `dmr.build_bbox`). Behavior-preserving.
- [x] **Test LS → 4 nálezy opraveny + audit land-cover.** (1) **Jméno mapy** `map.omap`→`<lokalita>.omap`
      (`out.name`, orphany smazány). (2+3+4) Systematický audit **47 plošných ZABAGED vrstev** vs mapováno odhalil
      klíčovou mezeru **114 Areál účelové zástavby** (177 na LS) — řeší bílá hřiště/školy/kasárna (`typzast_k` 62
      typů): asfalt (408 autobus. nádraží/409 čerpačka) → **501**, vše ostatní → **520** olivová. Rozdělení 114 dle
      ISOM kódu mezi surfaces (520) a paved (501) kanál. Plus **105 kůlny/přístřešky → 521** (LS budovy 8273→9123).
      Audit: 151 GIA (overlay vlastnictví) + 4 (CHKO) = skip; vegetace 140/142/144 = vědomě bílá (gate); drobné
      mezery (115 ostatní plocha, zřícenina, zámek, tribuna…) → katalog/TODO.
- [x] **Verify** — `py_compile` celý balík OK; **proc baseline 65 drží**; refaktor behavior-preserving (SV 269 ploch);
      5 lokalit přegenerováno (pokryv SV 2140 / NL 174 / LS 20159 / HS 2268 / NV 603; LS areály 170 olivová + 7 asfalt,
      kůlny +850); STATISTICS regen; vizuál OK (SV zahrady u domů, LS centrum olivové). Korekce uživatele: ISOM barvy
      jsou normované (z palety), neladí se okem (paměť `isom-colors-from-palette-not-eye`).

## Sezení 41 (2026-05-29) — %AUDIT:CODE + plošný pokryv (surfaces): mapa dostala barvy
- [x] **%AUDIT:CODE** (LOC práh, 4981 ř. tracked). Kód zdravý, 0 kritických; dominanta = drift komentářů po
      refaktorech (paměť `slap-symbol-rewrite-comments`). Opraveno: **D1** crt název `ISOM2000-ISOM 2017-2.crt`
      (s mezerou) → bez mezery — **oprava Sez. 40 byla NEúplná** (mezera přežila v `generator.py:1019`, **template
      `<notes>`** propisované do každého `map.omap`, GLOSSARY, IDEAS); **D2** docstring `_draw_footbridge` 625/250→
      937/375 µm (zaostal za Sez. 35); **D3** „hybridní 202/206" reziduum v `zabaged.py` ×2 (zavrženo Sez. 30);
      **K1** stats „8 sekcí"→9; **K2** `_nearest_segment_tangent` → wrapper nad `_nearest_seg` (DRY, −18 ř.);
      **K3** GLOSSARY výčet os. A1 monolit nepovýšen (čitelný, „až bolí").
- [x] **Plošný pokryv `--surfaces real`** (Sez. 41, „konečně barvy"). %THINK → probe (verify-against-source):
      kompletní land-cover inventář ZABAGED + render struktura z template (plná výplň = tutovka, pattern = práce).
      **Volba uživatele „open land jako jedna žlutá":** louka/park/pole/sad (139/134/138/135) → ISOM **401** plná
      žlutá (`C_YELLOW` konečně ožila); hřbitov (116) → **520** olivová out-of-bounds (`C_OLIVE` nová, aproximace);
      parkoviště (123) → **501** přes `--paved` (DRY). ISOM-věrné pole 412 / sad 413 (pattern) = vědomá druhá vlna.
      Izomorfní s vodní plochou/budovou: `fetch_open_land`/`fetch_cemeteries`, `map_*_to_isom`, `_generate_real_surfaces`,
      `_draw_surface_area` (outline=None), multi-class `mask_surfaces.png` (1=open, 2=hřbitov), omap area 401/520,
      meta injekce (mimo `_build_meta` — A1, precedent Sez. 37/38). **Z-order ÚPLNĚ VESPOD** (podklad pod vrstevnicemi;
      les = bílá default = vegetace gate). `batch.py` surfaces="off" obě větve (lekce B1 Sez. 35).
- [x] **Verify** — `py_compile` OK; **proc baseline 65 drží** (regrese); 5 lokalit přegenerováno (pokryv SV 269 /
      NL 34 / LS 1105 / HS 365 / NV 103, sedí na probe); STATISTICS regen; vizuál OK (žlutá vespod, z-order sedí).
      **`compare_real_vs_gen` SV: otevřený prostor gen 0 % → 35.8 %** (real 34.7 %) — zaplnil recall mezeru Sez. 37;
      precision/recall ~55 % (projekce ≠ ruční generalizace kartografa). Zelená (hustník) zůstává 0 % = vegetace gate (UC5).

## Sezení 40 (2026-05-29) — Kapitalizace DEV_LOCATIONS + %THINK ISOM 2000↔2017-2 (verzní gap zavřen)
- [x] **Kapitalizace `DEV_LOCATIONS` sjednocena** (carry-over Sez. 39). Verify odhalil, že to nebyl plošný
      chaos, ale **jediný překlep**: `Soví Vrch` → `Soví vrch` (vrch = terénní útvar → druhé slovo malé dle
      českého pravopisu; ostatní — `Nová Louka`/`Lidové sady`/`Hrubá Skála` — jsou sídla/čtvrti/obce → správně).
      Opraveno ve 3 SSoT: `generator.py DEV_LOCATIONS`, `stats.py LOCATIONS`, `compare_real_vs_gen.py` (+ zrušen
      3řádkový komentář o nesouladu — nesoulad zmizel). `resources/` názvy ponechány (vnější daná jména).
      **Vedlejší užitek:** `maps/Soví vrch` == `resources/Soví vrch` → `compare` funguje bez kapitalizačního hacku.
- [x] **Verify** — `py_compile` 3 soubory OK; SV přegenerováno (počty sedí: budovy 1078 / řopíky 70 / průseky 46 /
      vrstevnice 462 / skály 253 / `.omap` 3502); složka na disku je `Soví vrch` (lowercase, NTFS case fix přes
      smazání staré `Soví Vrch/`); `compare` najde obě složky přirozeně; STATISTICS regen; render pixelově nezměněn.
- [x] **%THINK „vizuál vs čísla" ISOM 2000↔2017-2 → verzní domain gap ZAVŘEN** (uzavírá pravou otázku Sez. 38/39).
      Destilát: otázka se rozpadá na 2 osy dle cesty — **vektor** (symbol ID → číslo, crosswalk `.crt` řeší 1:1)
      vs **rastr** (pixely → vzhled, čísla irelevantní; = co čte UC5). Pro UC5 relevantní JEN vizuál. **Vizuální
      sonda** (jednorázový georef warp: reálná ISOM 2000 Soví vrch × náš 2017-2 render téže oblasti, grid-north,
      shodné měřítko, montáž vedle sebe) → **kartograf: „vše důležité v obou setech, snadno transformovatelné"**
      — verzní rozdíl vzhledu není podstatný (`101/102/103` = identické číslo = identická hnědá kostra). Dominantní
      rozdíl je **obsahový** (chybí vegetace žlutá/zelená = recall gap Sez. 37), NE verzní. **Rozhodnuto: zůstat
      2017-2 + deklarace verze (Sez. 38) + crosswalk pro vektor; NEgenerovat zvlášť 2000 variantu.** Propsáno do
      KB `isom-issprom.md` + IDEAS (→ DONE). Otevřený zůstává jen obsahový (vegetační) gap = UC5, jiná osa.
- [x] **Drobné docs opravy** — drift názvu crosswalku `ISOM2000-ISOM 2017-2.crt` (s mezerou) → `ISOM2000-ISOM2017-2.crt`
      (skutečný soubor bez mezery) v KB. **A1 monolit `generator.py`: DROP z „Příště"** (Stale check ≥5 sez) — vědomě
      odložený trigger „až bolí", zůstává TODO položkou, ne carry-over.

## Sezení 39 (2026-05-29) — Reorganizace kořene: sandbox → generator/ + maps/ + rename generate_map
- [x] **`sandbox/` zrušen → `generator/` (pilíř).** `git mv` 9 souborů `sandbox/generator-poc/` → `generator/`
      (historie zachována, status `R`/`RM`); `sandbox/README.md` smazán; fyzicky odstraněn zbytek (`.venv`/
      cache/výstupy = gitignored). Generátor (2600+ LOC / 24 vrstev) = dávno ne „PoC". Izomorfní s `connectors/`.
- [x] **Rename `synthesize_pseudorealistic_map()` → `generate_map()`** (reverz Sez. 23/25). Důvod původního
      přejmenování ověřen jako padlý (`stale-todo-verify-rationale`): jediný vstup pro OBĚ větve (real i noise
      přes `terrain=`) → „pseudorealistic" v názvu nepřesné; noise „na zánik" → kolize `generate`↔`procedural`
      teoretická. `out_dir` default `"output"`→`None` (→ `maps/output`). „Pseudorealistická" zůstává vlastností
      VÝSTUPU (GLOSSARY „Pseudorealistic map"), ne názvem funkce.
- [x] **Výstupy → `maps/<lokalita>/` kotvené v kořeni LAB** (přes `__file__`, ne cwd; default i pro noise).
      `_REPO_ROOT` jako SSoT umístění repa (DRY: connectors/asset/maps); `MAPS_DIR` v generator.py + batch.py +
      stats.py; cesty opraveny o úroveň výš (`parent.parent.parent`→`.parent.parent`, `parents[2]`→`[1]`).
      Izomorfní: `resources/` (reálné mapy dovnitř) ↔ `maps/` (generované ven).
- [x] **`.gitignore` zjednodušen** — ~18 ř. (per-lokalita výčet + `sandbox/**`) → jediné `maps/` + DRY cache
      (bez leading-slash matchuje `connectors/.X_cache`). **`.venv` do kořene LAB** (sdílený generator+connectors,
      Python 3.12; opraven rozpor README „venv v kořeni" vs realita).
- [x] **Docs propagace** — 14 živých `.md` (README ×6, architecture, CLAUDE, PROMPTS, connectors/README, 4× kb,
      TODO, RESEARCH, IDEAS, GLOSSARY) + sloučený `generator/README.md` (zrušen PoC framing). Diáře/DONE ponechány
      (historie). Rezidua jmen v komentářích/docstringu propsána (`slap-symbol-rewrite-comments`, grep = 0).
- [x] **Verify** — proc baseline **65 objektů drží** (souhrnný log); 6 modulů `py_compile` + batch import OK;
      5 lokalit přegenerováno do `maps/` (počty sedí na historii); STATISTICS.md regen z `maps/`; SV render
      pixelově nezměněn. **Nález:** kapitalizace `DEV_LOCATIONS` (Title-Case výstup vs lowercase `resources/`) —
      chybná „oprava" v compare vrácena (Censure, `verify-data-not-assume`); → TODO Příště konkrétně.

## Sezení 38 (2026-05-29) — %THINK ISOM 2000↔2017-2 → deklarace verze ve výstupu
- [x] **Deklarace ISOM verze v každém výstupu** (ochrana proti záměně 2000↔2017-2). `generator.py`:
      helper `_isom_meta()` (izomorfní s `_georef_meta`, injektován mimo `_build_meta` kvůli A1) →
      `meta["isom"] = {version:"2017-2", scale:10000, symbol_set}`. `template_classic.omap` `<notes>`:
      deklarace verze + **varování před číselným konfliktem** (521=Building ne High stone wall; Narrow
      ride 509→508; Railway 515→509) + odkaz na crosswalk `.crt` → **dědí se do každého `.omap`**.
- [x] **Template NEvyměněn za cizí soubor — verify dokázal, že nemá smysl.** Náš `template_classic.omap`
      je **100% geometricky identický s oficiálním OOM ISOM 2017-2 (1:10000) setem** (všechny `line_width`
      sedí; stažený 15000 set lišil ×1,5 = jen měřítko). Výměna by rozbila injekci objektů/ortofota
      (`<objects count="0">` cizí formát) + zmenšila symboly 1,5×. Lekce „měň jen s důkazem" (CLAUDE.md).
- [x] **Reference do KB** (CLAUDE.md: KB nese licenci): `docs/kb/ISOM2000-ISOM 2017-2.crt` (autoritativní
      crosswalk, GPL, OpenOrienteering/Kai Pastor) + `docs/kb/isom-2000-spec.pdf` (IOF, withdrawn; archiv
      ELTE). Crosswalk **nezávisle potvrdil** ruční crosswalk ze spec (3 jisté páry: Building 521↔526,
      Narrow ride 508↔509, Railway 509↔515).
- [x] **%THINK destilát + korekce Sez. 37.** Jediný tvrdý diskriminátor verze = `526` Building (v 2017-2
      neexistuje); `521`/`112`/`113` se recyklují s jiným významem → Sez. 37 marker byl kontaminovaný.
      Empirie použitých objektů: **4/6 reálných map v `resources/` = ISOM 2000.** Pravá otevřená osa
      (Sez. 39): liší se verze i VIZUÁLNĚ (render), nebo jen čísly (→ crosswalk stačí)?
- [x] **Verify:** proc baseline 65 drží (aditivní změna); `isom` blok 2017-2/10000 ve všech 5 lokalitách
      i v noise; 5 lokalit přegenerováno (počty drží: SV 46/NL 119/LS 20/HS 16/NV 44 průseků). Vizuál
      záměrně beze změny (deklarace textová).

## Sezení 37 (2026-05-29) — Georef výstupu (rgb.pgw + meta) + strojové porovnání s živou mapou
- [x] **Emit `rgb.pgw` + georef do `meta.json`** (enabler). `generator.py`: 3 helpery u `_write_contours_geojson`
      — `_world_file_coeffs` (pixel→S-JTSK = čistý scale+translate → rotační členy 0, +0,5 px na střed UL pixelu),
      `_write_world_file` (6 řádků, jen reálný terén), `_georef_meta` (real → S-JTSK bbox+pixel_size+world_file+
      `north:"grid"`+`grivation_deg:null`; noise → `local_m`). Georef injektován do volajícího, NE přes `_build_meta`
      (26 parametrů, A1 — nezhoršovat). Verify: `.pgw` ručně ověřen (C=xmin+½A, F=ymax+½E, B=D=0); proc 65 drží;
      všech 5 lokalit přegenerováno (mají `.pgw`).
- [x] **`compare_real_vs_gen.py`** (probe, strojové porovnání gen ↔ živá mapa, zatím Soví vrch). STAT 1 sémantický
      crosswalk + pokrytí, STAT 2 prostorová shoda po ISOM barvách (forward-map + tol). 2 bugy chyceny vlastním
      verify: int16 overflow v klasifikaci barev + ztráta tenkých linií nearest-vzorkováním → forward-mapování.
- [x] **Headline nález: ISOM 2000 (reálná SV) vs ISOM 2017-2 (gen)** — naivní kód-na-kód selhává (526=budova vs 521;
      508=nevýrazná pěšina vs náš průsek; 509=průsek vs naše železnice; 112/113/115 vs 109/110/111). 9/11 schopností
      gen má sémantický protějšek. Mezery: vegetace 262 obj / 70 ha (UC5), skály/srázy 142, ploty 31, bodové umělé 22.
- [x] **Verify-against-source: grivace** — world-file rotace reálných map = grivace, ověřeno proti `.omap` `grivation`
      na desetinu ° (SV 11,4 / Blatná 11,9 / Slovanka 3,75 = UTM u poledníku). **Závěr: co umíme z tvrdých dat,
      umisťujeme správně** (vrstevnice precision 84 % / recall 66 %; voda/černá placement 71-81 %) **a nevymýšlíme si.**
- [x] **Nález:** `GLOSSARY.md` existuje (root), Sez. 36 hlásilo chybu kvůli kontrole špatného path (`docs/`).

## Sezení 36 (2026-05-29) — Lesní průseky (ISOM 508 Narrow ride) ze ZABAGED
- [x] **Lesní průseky `--rides real` → ISOM 508 Narrow ride.** ZABAGED `Lesní průsek` (id 16, REST jméno
      s MEZEROU jako tramvaj/lávka), liniová, izomorfní s railways/powerlines. KISS vždy 508 (bez
      kategoriálního atributu — verify SV 46 prvků). Render černá čárkovaná dash 3,0/break 0,375 mm
      (dlouhé čárky, odliší od pěšiny 505). **Runnability pozadí NEKRESLENO** (vegetace = UC5 predikce
      ne data, ISOM „without background" varianta).
- [x] **Foundations před kódem** (verify-against-source): spec 508 z template id 115 + probe layer ID/atributy
      PŘED implementací (paměti `isom-spec-before-render`, `geometric-selfcheck-before-oom`) → 0 slepých iterací.
- [x] **Implementace** (mirror railways): `zabaged.fetch_forest_rides`/`map_ride_to_isom`, generator
      `_draw_ride`/`_generate_real_rides`/`--rides`/`mask_rides.png`/meta sekce, omap liniový kanál 508,
      stats 508, `batch.py` off obě větve (lekce B1 Sez. 35 — call-sites).
- [x] **Verify:** proc baseline 65 drží, průseky SV 46/NL 119/LS 20/HS 16/NV 44, vizuál čárkovaná 508 OK,
      všech 5 lokalit přegenerováno + STATISTICS.
- [x] **Propagace:** architecture UC2, spec §4.9i, katalog ◐→✓, oba sub-READMEs, hlavní README status
      (dorovnán k dnešku — chyběly i skály 30 + mosty 31-33). Nález: `GLOSSARY.md` v repu chybí (ač v checklistu).

## Sezení 35 (2026-05-28) — %AUDIT:CODE (LOC práh) + sjednocení rastru mostů/tunelů s .omap + fix batch noise
- [x] **%AUDIT:CODE** (LOC práh ≥500 překročen 3,5× = net +1756 LOC od Sez. 27). Přečteny sám
      generator/omap_export/stats/batch/palette + 3 konektory; kód zdravý, dominanta = drift komentářů.
- [x] **D1 — drift symbolu 202** (zavržená hybridní 202/206 logika popsaná jako aktivní na 5 místech
      `generator.py` vč. CLI helpu) smazán; `map_rock_area_to_isom` vrací vždy 206 (KISS).
- [x] **D2+K3 — rastr mostů/tunelů sjednocen s `.omap`.** Verify-against-source PŘED kódem (geometrie
      symbolu 512 z `template_classic.omap` id=125 + demo `Most.png`): `_draw_bridge` = 2 paralely
      (`_offset_polyline_px` ±0,75 mm) + nožičky `_draw_bridge_leg` (450 µm podél osy ven + 654 µm kolmo
      ven → `[ ]`); `_draw_tunnel` = portály `TUNNEL_PORTAL_HALF` 0,75 mm (přestal půjčovat `FOOTBRIDGE_*`).
      Konstanty na template: baseline 180→270 µm, lávka 625/250→937/375 µm. Smazán `_draw_bridge_brackets`
      + `BRIDGE_BRACKET_*` (Sez. 32 interpretace 60°, vyvrácená Most.omap demem).
- [x] **D3 — DRY:** 9× duplikovaný validační blok `real ⇒ terrain real` → smyčka (27→13 ř.).
- [x] **D4/D5 — zastaralé docstringy/komentáře:** `zabaged.py` modul (cesty→11 vrstev), `omap_export.py`
      výčet symbolů, z-order v `synthesize_pseudorealistic_map`, „Most vynechán" v `PATH_LAYERS`.
- [x] **K1/K2 — kosmetika:** zhuštěn chaotický komentář `_draw_boulder_cluster`; název 306 sjednocen
      na ISOM „Minor seasonal water channel" (`generator` + `stats`).
- [x] **B1 (kritické) — fix `batch.py --terrain noise` crash.** Noise i real větev nepředávaly
      `rocks=`/`bridges=` (default `real`) → noise padala na validaci, real je zbytečně stahovala.
      Doplněno `rocks="off", bridges="off"` do obou + komentář. Pre-existující (Sez. 30/32 nepropsáno).
- [x] **Verify:** syntax OK ×5, proc baseline 65 drží, most vizuálně OK (Novina výřez), všech 5 lokalit
      přegenerováno + STATISTICS (jen 306 název + časy, počty drží). A1 monolit (2623 ř.) = úvaha, neřešeno.

## Sezení 33 (2026-05-28) — Mosty/tunely DOKONČENY (OOM verify na NTBHEJ21) + out_dir do adresářů
- [x] **Nožičky 512 mostu — orientace ven** (Sez. 32 7. iter byla obráceně, neověřená). Diagnóza měřením
      `Most.omap` dema (ne hádáním): demo má levá strana osy reversed / pravá forward, kód zrcadlově →
      nožičky dovnitř. Symbol 125 v demu == template (identický). Fix: offset paralel na **pravou normálu**
      (záporný `BRIDGE_PARALLEL_OFFSET_UM`). Self-check relace == demo.
- [x] **Buffer crop pod mostem** (uživatel „cutnout linie 0,5 mm za závorkami"). Měření demu: cut endpointy
      perp ≈ 1250 µm = 0,75 (paralela) + 0,5. Nahradil křehkou crossing strategii (`>2 průsečíky → ignore`
      selhával na ZABAGED noise) **buffer pásem ±1,25 mm KOLMO od osy** + **úhlový filtr** (∥ osa < 25° =
      nesená trať nahoře → necropovat). Interpolovaný okraj (`_split_by_zones_interp`). Voda 130→145, cesty
      486→499 (dělení), železnice 5 (nesená ∥ ✓).
- [x] **Tunel = 512 otočené o 90°** (uživatel: tunel ≠ paralely; 512 zobrazují vjezdy). Oddělen emit:
      most = 2 paralely podél osy; **tunel = 2 krátké 512 KOLMÉ na obou koncích** (`_tunnel_portals`, 1,5 mm).
      Ortofoto verify: vjezdy na správných místech.
- [x] **Passage crop tunelu — fix 4 mm → 0,5 mm.** Dřív snap na nejbližší vrchol trati (řídké body).
      Fix: vjezdy se **projektují přesně na trať** (`_project_to_line`) + interp okraj. Self-check: konce
      železnice 499–500 µm od vjezdů.
- [x] **`--location` → výstup do složky lokality.** Názvy složek byly 2× (ASCII `DEV_LOCATIONS` / diakritika
      `stats.py`) → sjednoceno na diakritickou verzi (SSoT shoda obou). Orphany `output/` + `Hruboskalsko/` smazány.
- [x] **Úklid + DRY.** Smazány dead `_segment_intersection_pt`, `_crop_line_at_cutters`, `_apply_cut_zones`;
      vytaženy `_split_by_zones_interp`/`_emit_512_line`/`_point_on_line_px`/`_interp_grid_at`/`_project_to_line`.
      proc 65 drží; všech 5 lokalit přegenerováno do adresářů + STATISTICS 24/24.

## Sezení 31 (2026-05-28) — Mosty 512 + Lávky 512.2 + oprava tramvaje 509 + DEV_LOCATIONS refaktor
- [x] **Mosty `--bridges real`** (`Most` id=73 → ISOM 512, linie+V-křídla; render = středová linie 0,18 mm
      + 4 šikmá křídla na koncích symetricky ke 35° vůči ose, template autoritativní). Probe Novina
      ukázal `jmeno 2/4` = Novinský viadukt 199 m + Malý viadukt 143 m (oba kamenné železniční,
      `material_p='neznámý'` — ZABAGED nedělí kámen separátně, ISOM stejně nerozlišuje).
- [x] **Lávky `Lávka (linie)` (67) + `Lávka (bod)` (66) → ISOM 512.2 Footbridge** (bodový symbol s
      rotací kolmo k nejbližšímu vodnímu toku — paralela řopíku→hranici). Pro liniovou lávku se
      bere střed osy (MVP, drobnost TODO). V .omap rotation v radiánech (template signatura).
      **Nález:** Lávka má v REST jméno **s mezerou a závorkou** (`Lávka (linie)`), NE WFS escape
      `Lávka__linie_` jak v katalogu Sez. 23 — ČÚZK ZABAGED má 2 konvence názvů (verify `?f=json`
      před doplněním do `LAYER_IDS`).
- [x] **Tramvaj `Tramvajová dráha` (71) → 509** (oprava Sez. 28: vynechána „jako urbánní", chyběla
      točna Lidové sady). Probe LS: 25 LineString prvků, atributy chudé → KISS, vše → 509. Doplněno
      do `RAILWAY_LAYERS`. Lekce: „urbánní" není kritérium, když ISOM nerozlišuje (jeden symbol).
- [x] **Refaktor `DEV_LOCATIONS` na per-lokalita rozměr** (5-tuple: label, lat, lon, w_km, h_km):
      `DEV_W_KM`/`DEV_H_KM` zrušeno. Existující 4 lokality zůstávají landscape 6×4 km (kanonika
      stable). Přidáno **NV `Novina` 50.7598686, 14.9601922, 3×5 km PORTRAIT** (5. lokalita, kamenné
      železniční viadukty). HS `Hrubá Skála` změněna z landscape 6×4 na **SQUARE 5×5 km** centrovaný
      na **50.5481, 15.1762** = midpoint Kacanovy ↔ Doubravice (Doubravice = část obce Hrubá Skála,
      verify-against-source: Wikipedia uvádí 8 částí obce).
- [x] **Implementace**: `connectors/zabaged.py` (`fetch_bridges`/`fetch_footbridges` + `map_bridge_to_isom`/
      `map_footbridge_to_isom`); `generator.py` ISOM konstanty 512/5122 + `_draw_bridge` (V-křídla)/
      `_draw_footbridge_point` + `_nearest_segment_tangent` (helper rotace) + `_generate_real_bridges`
      + CLI `--bridges` + meta sekce `bridges` + `mask_bridges.png` 2-class; `omap_export.py` USED_CODES
      += 512/512.2, `ROTATABLE_CODES` += 512.2, `bridge_features`/`footbridge_features` parametry.
- [x] **Verify**: proc baseline **65 drží** přesně. NV (3×5 km portrait) **22 mostů** (Bridge:17,
      Footbridge:5, vč. Novinský + Malý viadukt). HS (5×5 km square) **639 skal** (459× plné 206!),
      13 mostů. LS (6×4 km) **40 železnic** (15 trat+vleček + 25 tramvaj nová), 76 mostů.
      Kanonika `Novina/`, `Hrubá Skála/` (square), `Lidové sady/` (tramvaj) regenerována v plné variantě.

## Sezení 30 (2026-05-28) — Skály/balvany (ISOM 204/207/206) ze ZABAGED
- [x] **Skály/balvany `--rocks real`** (real-půlka, 3 ZABAGED vrstvy → 3 ISOM symboly, KISS „vrstva =
      jeden symbol" jako budovy→521 / vedení→510). Verify-against-source `temp/probe_rocks.py` na Hrubé
      Skále PŘED kódem: `Osamělý_balvan__skála__skalní_suk` (bod, 6) → **204 Boulder**;
      `Skupina_balvanů__bod_` (bod, 168) → **207 Boulder cluster**; `Skalní_útvary` (plocha, 411) →
      **206 Gigantic boulder**. Žádná vrstva nenese typ/velikost/výšku (jen `jmeno`) → per-feature
      rozhodování by nemělo datový podklad.
- [x] **Hybridní 202/206 ZAVRŽEN + Chaikin smoothing ZAVRŽEN** (drift po stěně argumentů, 2 otočky
      uživatele): (1) `Shape_Area` ukázala ~120 vrcholů / 32×32 m → polygony „už pěkné" → Chaikin smazán
      (RAW jako voda/budovy); (2) práh 500 m² pro 202↔206 byl hádaný (žádný atribut ho neopodstatnil) →
      vše → 206 plná plocha. Smazány `_chaikin_smooth`, `ISOM_CLIFF_PASSABLE`, `_draw_cliff_line`,
      `_polygon_area_sjtsk`; 202 z `USED_CODES`. Potvrzení lekce „generalizuj jen s důkazem" (Sez. 27).
- [x] **Implementace**: `connectors/zabaged.py` (`LAYER_IDS` +10/12/130, `BOULDER_LAYERS`/
      `BOULDER_CLUSTER_LAYERS`/`ROCK_AREA_LAYERS`, `fetch_boulders`/`fetch_boulder_clusters`/
      `fetch_rock_areas`, `map_*_to_isom`→204/207/206); `generator.py` (ISOM 204/206/207, `_draw_boulder`
      kruh 0,4 mm / `_draw_boulder_cluster` trojúhelník 0,8×0,7 mm / `_draw_gigantic_boulder` wrapper
      `_draw_area_symbol`, `_generate_real_rocks`, `mask_rocks.png` 3-class, `--rocks {off,real}`, z-order
      úplně navrch); `omap_export.py` (`USED_CODES` +204/206/207, `AREA_CODES` +206, `rock_point_features`/
      `rock_area_features`).
- [x] **Verify (ve `.venv`):** Hrubá Skála 5,9×4 km **585 skal** (204:6 / 207:168 / 206:411, sedí na probe
      přesně; pískovcové věže dominují); NL 6×4 km **200 skal** (204:16 / 207:178 / 206:6). proc baseline
      nedotčen (rocks jen real). Branžový precedent: Karttapullautin (bod→204/205, plocha→206, plná výplň).
- [x] **Post-script (3 cleanup commity):** `HS` doplněn do `DEV_LOCATIONS` (`--location HS`); regen do
      CZ-named složek (`output_X/` špatná konvence, smazáno); **Censure! `--no-ortho`** smazal ortofoto
      podklady kanonik → regen v plné variantě. Pravidlo → paměť: **kanonické DEV_LOCATIONS = vždy plný
      režim, nikdy `--no-ortho`**.

## Sezení 29 (2026-05-28) — Pomocné vrstevnice (form lines, ISOM 103) z DMR
- [x] **ISOM 103 = Form line** (verify-against-source, ne hádání): uživatel zmínil „103", ověřeno v
      `template_classic.omap` — 103 = **Form line** (pomocná vrstevnice), NE slope line (ta je 101.1 / 103.1).
      Není to ZABAGED vrstva — **derivace z DMR výškopisu** (týž zdroj jako vrstevnice 101/102).
- [x] **Heuristika (návrh uživatele A1+A2):** form line jen kde **(1) mírný svah** (rozestup vrstevnic >
      `FORMLINE_SPACING_LIMIT_M`=40 m ⟺ sklon < `CONTOUR_STEP/limit`) **A (2) zakřivený terén**
      (`|Laplacián výšky| > FORMLINE_CURV_MIN`=0,004) — na rovnoměrném (lineárním) svahu Laplacián ≈ 0 →
      form line by jen kopírovala vrstevnici (ISOM zakazuje „intermediate contours"). `elev` 3× vyhlazen
      (3×3 box) před derivacemi — tlumí mikro-texturu DMR. Poloviční hladina (`level + 2,5 m`) ořezána na
      masku, filtr min. délky **3 mm** (přísněji než ISOM 1,1 mm — uživatel „bez fousků").
- [x] **Implementace** `generator.py` (`ISOM_FORMLINE`, `FORMLINE_*` konstanty, `_box_smooth`,
      `_formline_mask`, `_clip_line_to_mask`, `_polyline_len_px`, render blok jen `terrain=="real"`,
      `mask_formlines.png`, meta sekce `formlines`, log) + `omap_export.py` (103 v `USED_CODES`,
      `formline_features` param, emit jako 101/102, `n_formlines` v návratu) + `_write_contours_geojson`
      (103 do `names`). Render dashed hnědě, break zvětšen 0,2→0,5 mm (rastr; `.omap` symbol 103 věrný).
- [x] **Ladění prahů přes verify (`temp/probe_formline.py`), ne poslepu:** první prahy (curv 0,0015,
      1× smooth) daly **1466** úseků = plošný šum (mikro-textura DMR). Probe citlivosti (passes × curv ×
      spacing) + distribuce délek → `curv 0,004` + `min 3 mm` = **108** (hustší než mezikrok 70, fousky <3 mm
      pryč — obě uživatelova kritéria). Branžový precedent: Karttapullautin (poloviční hladiny + filtrace).
- [x] **Verify:** proc baseline **65 drží** (form line jen real terén → noise beze změny). NL 6×4 km:
      **108 form lines** vs 240 vrstevnic; vizuál (overlay) — form line jen v plochých zakřivených partiích,
      strmé svahy (husté vrstevnice) je nemají. Uživatel ověřil `map.omap` v OOM („super").
- [x] **SLAP docs:** GLOSSARY (Form line plná definice), spec §4.5 + §9 (form line blok, výčet `.omap`
      doplněn i o vedení/železnice/kolejiště — drift Sez. 24/28), README, TODO/DONE.

## Sezení 28 (2026-05-27) — Železnice 509 (+ vlečky) + kolejiště 501 + oprava float bugu v _draw_dashed
- [x] **Železnice → ISOM 509** (real-půlka, izomorfní s vedením 510). Verify-against-source PŘED kódem:
      vrstva je **`Železniční_trať` (id 75)**, ne „Železnice" (TODO se mýlilo); **509 = kombinovaný symbol**
      (čárky 0,35 mm + bílý „pražcový" knockout), ne prostá linie jako 510. `zabaged.fetch_railways` +
      `map_railway_to_isom`→509; `generator` mode `"railway"` (bílý podklad + černé čárky → mezery BÍLÉ,
      odliší od pěšiny 505), `_draw_railway`, `_generate_real_railways`, `--railways`, `mask_railways.png`;
      `omap_export` 509 v `USED_CODES` + `railway_features`; `batch` `railways="off"`. Export odkáže symbol 509.
- [x] **Vlečky → 509 (C)** — `Železniční_vlečka` (id 76) přidána do `RAILWAY_LAYERS` (map vrací 509 pro každou
      vrstvu). U libereckého nádraží 28 tratí (vs 6 jen `Železniční_trať`) = ten svazek kolejí.
- [x] **Kolejiště → ISOM 501 Paved area (B)** — nová **plošná** vrstva `--paved`. Verify u Liberec hl. n.:
      „10 kolejí" v datech NEJSOU linie, ale **jedna plocha `Kolejiště` (id 122, ~19 ha)**. `zabaged.fetch_paved_areas`
      + `map_paved_to_isom`→501; `generator` `ISOM_PAVED`, `_draw_paved_area` (C_ROAD výplň + C_BROWN obrys),
      `_generate_real_paved`, `mask_paved.png`, meta, CLI, z-order brzy (podklad pod kolejemi); `omap_export`
      `paved_features`. **Symbol: kombinovaný 501 s OBRYSOVOU linií** (ne 501.1 bez obrysu) — uživatel „do kolejiště
      se nevstupuje" (bounding line významová); voda 301.1 byla zbytečně konzervativní.
- [x] **Oprava latentního float bugu v `_draw_dashed`** — railway render zamrzl; diagnostika (ne hádání):
      neceločíselné `dash=6,9 / gap=4,6 px` → na hranici čárka↔mezera `step`→~1e-15 → smyčka „creepuje"
      donekonečna (>100k iterací na 10,8 px segmentu). Pěšiny (přesné 7,0/4,0) to roky maskovaly. Fix: epsilon
      v podmínce (`d < seg-1e-9`) + nudge (`step<1e-9: pos+=1e-9; continue`). Hardening i 505/506/306.
- [x] **Crossability hranic → IDEAS/TODO** (princip uživatele): styl obrysu nese překonatelnost (301 uncrossable
      vs 304/305/306 crossable; kolejiště 501 obrys = zákaz vstupu). Náš generátor honoruje volbou ISOM kódu.
      Dluh: vodní plochy vždy 301, toky vždy crossable (široká nepřekonatelná řeka by byla špatně) → TODO.
- [x] **Verify:** proc baseline **65 drží**; nádraží 28 železnic + 2 kolejiště (`.omap` 28× sym 120 + 2× sym 105);
      LS 6×4 přegenerováno **15 železnic + 1 kolejiště** + 8273 budov (`.omap` 13121 obj, 15× 509 + 1× 501).

## Sezení 27 (2026-05-27) — %AUDIT:CODE + budovy RAW (pravoúhlost zavržena) + koupaliště + řopíky + logging
- [x] **%AUDIT:CODE** (D1-D5+K1-K4, kritické 0): WFS→REST terminologický drift (~25 míst, vč. CLI help);
      `batch.py` `ortho=False`; asset `řopík_10000.*`→`ropik_10000.*` (ASCII); smazán `__future__` import;
      `map_to_isom`→`map_path_to_isom`; z-order/scale/shebang/„WFS"→„REST" kosmetika. Baseline 65 drží.
- [x] **Pravoúhlost budov → ZAVRŽENA → budovy RAW.** Implementováno (dominantní osa + tolerantní snap ±15° +
      slučování hran + rekonstrukce rohů; verify LS 96,4 % hran near-orto, 214 výjimek). ALE generalizace komolila
      tvar (budova 1028994: 15→5 vrcholů) → uživatel „kresli budovy jako vodu". **Smazáno ~430 LOC**: L1 generalizace
      (DP/min-size Sez. 18 + orthogonalizace) + L2 displacement (Sez. 21-22) + `diagnose_displacement.py`. Nový
      `_generate_real_buildings` = raw jako `_generate_real_water`. **Ponaučení → CLAUDE.md: generalizuj jen s důkazem.**
- [x] **Koupaliště (#1)** — `Pozemní_nádrž` (id 107, `podtypob_k='BA'` bazén) → ISOM 301. Lesní koupaliště LS
      (~1934 m²) chybělo, protože je nádrž, ne `Vodní_plocha`. Přidáno do `WATER_AREA_LAYERS` + `map_water_to_isom`.
- [x] **Řopíky (#2) — generátorová integrace.** `zabaged.fetch_bunkers` (Bunkr LO37) + `fetch_state_border`
      (`vyzn_zsh_k='1'` = státní hranice, ověřeno). Asset loader (jen mapové objekty z `<objects>` — oprava parsovacího
      bugu). Orientace = PCA-normála linie řopíků, „ven" k nejbližší státní hranici (univerzální ČR, ruší `OUTWARD=sever`).
      `--ropiky off|real`, postprod fáze v `synthesize_pseudorealistic_map`. SV 70 řopíků (70/70 na sever k hranici).
- [x] **Logging** v `synthesize_pseudorealistic_map` — `logging` (ne print), INFO průběh po vrstvách + finální souhrn;
      CLI zapíná (`main`→`basicConfig`), `batch.py` tichý. `_try_layer` stderr→`_log.warning`. Nápad uživatele.
- [x] Přegenerováno SV (1078 budov+70 řopíků) / NL (124) / LS (8273) — vše RAW, `layer_errors=None`.

## Sezení 26 (2026-05-27) — Ortofoto podklad + WFS→REST (města kompletní) + asset pattern + reálné řopíky
- [x] **Ortofoto podklad (3a, verify proti realitě)** — `connectors/ortofoto.py` (ČÚZK ORTOFOTO MapServer
      `arcgis1`, S-JTSK 5514, CC BY 4.0, sdílený `build_bbox`, **dlaždicování** nad strop 4096 px). Generátor
      `--ortho`/`--ortho-mpp` (default 0,5 m/px) → `ortofoto.png`; `omap_export` připne podkladový `<template>`
      do `map.omap` (paper-space, x=y=0, scale=map-mm/px, opacity 0,5, pod mapou). Formát `<template>` ověřen
      proti reálnému OOM 0.9.6 výstupu. SV/NL/LS 0,5 m/px; SV verify uživatelem (sedí pixel-přesně i v rozích).
- [x] **WFS→REST fix** (řešení nálezu Sez. 25) — `zabaged._fetch_layer` z WFS GetFeature na ArcGIS REST
      `MapServer/<id>/query` + sériová paging smyčka (`resultOffset += 2000`). `LAYER_IDS` (typeName→numerické ID),
      `f=geojson` (parsery beze změny), oprava `typuskom_k` (REST malými, WFS velkými — chyceno verify PŘED kódem).
      **Města kompletní:** SV budovy 1000→**1078**, **LS 1000→8273** budov + 3951 cest. Verify `temp/probe_rest_paging.py` (overlap 0).
- [x] **Asset pattern** — dvojice `<jméno>.omap` (vizuální vzor kreslený v OOM) + `<jméno>.rules.xml` (pravidla).
      `asset/ropik_10000.omap` (budova 521 + vrstevnice 101) + `.rules.xml` (`rotation_rule`, `draw_order`, `source`).
- [x] **Reálné řopíky na SV** — ZABAGED `Bunkr` (id 37, `typbunkr_k='LO37'` = lehký objekt vz.37), 70 bodů.
      Orientace = NORMÁLA na lokální linii řopíků (PCA okolí; nápad uživatele). Post-proces vložil 70 do SV map.omap.
- [x] **Měřítko fix** — `omap_export` přepisuje georef template (15000) na `MAP_SCALE` (10000); nesoulad (side-finding) opraven.
- [x] **Displacement práh** `MAX_DISPLACE_BUILDINGS=2000` — budova↔budova O(n²) na LS (8273) neúnosné → nad práh skip
      (efekt 0,4 mm zanedbatelný). Odblokovalo LS (doběhla za minuty).
- [x] **%BEEP → Stop/Notification hook** (`settings.local.json`). **Censure! (AI)** vymyšlený fortifikační fakt v rules
      (opraveno: k nepříteli zasypáno, střílny do vnitrozemí); `OUTWARD=sever` zadrátováno → TODO univerzalita.

## Sezení 25 (2026-05-27) — Refaktor `synthesize_pseudorealistic_map` + dev lokality (SV/NL/LS 6×4) + WFS limit nález
- [x] **Přejmenování `generate()` → `synthesize_pseudorealistic_map(lat, lon, w_km, h_km, only_real=False, out_dir="output", *, …)`**
      (reframe Sez. 23). Hlavních 6 parametrů vepředu, noise (Option 1) větev + per-vrstva toggly zachovány jako
      **keyword-only ocas** (default `terrain="real"`). `lat/lon` WGS84 (ne `n/e`). `only_real` (sladěn s CLI `--only-real`)
      → interní `pseudorealistic = not only_real` jen na hranici (`_generate_real_powerlines`/`_build_meta` beze změny, DRY).
      `_apply_extent(w_km, h_km)` přesunut z `main()` dovnitř funkce (rozměr je teď parametr).
- [x] **Dev lokality `DEV_LOCATIONS` + CLI `--location` SV/NL/LS @ 6×4 km** (`DEV_W_KM/H_KM`): DRY zdroj souřadnic
      (dřív ad-hoc). `--location KÓD` přepíše lat/lon + nastaví výsek 6×4. CLI defaulty překlopeny na `real`.
- [x] **Lidové sady (LS) = classic ISOM** (oponentura sprintu): `template_sprint.omap` je ISSprOM, ale generátor stojí
      na ISOM → LS jako classic (natrénuje hustou zástavbu); **ISSprOM/sprint pipeline → IDEAS** (samostatné sezení).
- [x] **`batch.py` na nový název** (noise = DEF extent + proc/off → baseline drží; real beze změny chování). `diagnose_displacement.py`
      nedotčen (`generate()` nevolá).
- [x] **Verify** (`.venv`): proc baseline **65 drží** přesně; real 6×4 km (grid 696×464) SV 2689 / NL 1079 / LS 3701 obj,
      `layer_errors: None`, vizuály sedí na terén.
- [x] **Nález: ČÚZK ArcGIS WFS tvrdý strop 1000 obj/dotaz** (SV+LS přesně 1000 budov). Verify-against-source (`temp/wfs_probe.py`):
      `count` strop nezvedá, `startIndex` paging rozbitý (anomálie) → **NE malá změna**; robustní = spatial tiling nebo přechod
      na ArcGIS REST. **Odloženo** → TODO `[!]` (bije hlavně města = sprint doména). **Censure! (AI)** odhad „malá změna" vyvrácen verify.
- [x] **`%END` cleanup pravidlo → `docs/PROMPTS.md`:** maž jen scratch (`temp/`, `output_*/`); cache (`.dmr_cache`,
      `.zabaged_cache`) + `__pycache__` NECH (regenerovatelné, ale zrychlují).

## Sezení 24 (2026-05-27) — Katalog ZABAGED→ISOM (149 vrstev) + el. vedení (510) + dvě fáze (pseudorealistic)
- [x] **Katalog VŠECH 149 vrstev ZABAGED Polohopis → ISOM** (`docs/kb/zabaged-isom-catalog.md`, nový):
      verify-against-source GetCapabilities (149 typů) + DescribeFeatureType (geom: 57 bodů/45 linií/47 ploch)
      + ISOM kódy z `template_classic.omap`. U každé vrstvy ISOM symbol, nebo důvod nepoužití; 13 sekcí
      (komunikace/voda/terén/vegetace/stavby/…), akční seznam kandidátů. Odkaz z `data-sources.md`.
- [x] **Verify-against-source nálezy (oprava zděděných předpokladů):** (a) **el. vedení = ISOM 510, NE 516**
      (516 = Fence/plot) — táhlo se 4 dokumenty (TODO, Příště Sez. 23, data-sources, komentář zabaged.py);
      (b) **`Most` = linie, ne bod** (komentář zabaged.py tvrdil opak). Propsáno (516→510) napříč.
- [x] **El. vedení `--powerlines real`** (`zabaged.py` + `generator.py` + `omap_export.py`): `Elektrické_vedení`
      → ISOM 510 (tenká černá linie); `NAPETI` v datech prázdné → vše 510 (bez 511). Render `mode "powerline"`,
      GT `mask_powerlines.png`, `.omap` liniový objekt 510, z-order po cestách. Izomorfní s vodou/budovami napříč
      3 soubory. Verify: proc 65 drží, Soví vrch 253=246+7 vedení.
- [x] **Příčky vedení = SLOUPY (dvě fáze, koncepční reframe uživatele):** příčky ISOM 510 odpovídají sloupům
      (běžci se jimi řídí) → **fáze 1** kreslí příčku na poloze reálného sloupu (`Stožár_elektrického_vedení`,
      `fetch_powerline_masts`, `_nearest_seg`+`_draw_tick_at`), **fáze 2** (`pseudorealistic=True`, default)
      doplní rovnoměrné jen na liniích bez sloupu. **Censure! (AI):** původně jsem příčky vymyslel rovnoměrně.
- [x] **Parametr `pseudorealistic` (default True) + CLI `--only-real`** (`generate`, meta): fáze 1 = projekce
      tvrdých dat, fáze 2 = pseudorealistická dekorace (co v datech není). Zatím působí na vedení; `%THINK`
      potvrdil, že dosavadní vrstvy jsou čistá projekce (no-op), budoucí konzument = vegetace. Spec §0b.
- [x] **Úklid:** konvence dočasné výstupy → `temp/` (gitignored); generator-poc scratch smazán, kanonické
      `Soví vrch/` + `Nová louka/` (6×4 km, 1079 obj / 3 vedení). lasertool ponechán (budoucí vegetace).

## Sezení 23 (2026-05-26) — Parametrizace výseku + reframe `synthesize_pseudorealistic_map` + úplnější/věrnější cesty
- [x] **Parametrizace výseku** (`generator.py`): velikost z konstant → argumenty `--width-km`/`--height-km`
      (š×v; souřadnice `--lat/--lon`). Otočená závislost: `PX_PER_MM` + `M_PER_CELL` (rozlišení) = jedna pravda,
      `W/H/GW/GH/TILE_M/WORLD_W_M` odvozeny v `_apply_extent(w_km,h_km)`. Rozlišení drží konstantní → mm-prahy
      (`MIN_BUILDING_PX`, `DISPLACE_*`) platí pro libovolnou velikost. Default = baseline (zpětná kompat).
      `WORLD_W_M` sjednoceno na `TILE_M·GW/GH` (jako `build_bbox`) — georef-konzistence (verify-against-source úlovek).
      Testy: Soví vrch 3,3 km², Nová louka 7,25 km² portrait, refresh 5×4 km (20 km²). proc baseline **65 drží**.
- [x] **Reframe „prediktor mapy" + název API** (`%THINK`): real-větev = `synthesize_pseudorealistic_map(n,e,w_km,h_km)`
      — dvoufázový (projekce DMR+ZABAGED → AI predikce chybějících symbolů z podobných lokalit, UC5 blokováno
      korpusem+licencí). Název zvolen proti `GetPredictedMap`/`GenerateProceduralMap` (kolize „procedural" s feederem).
      Zatím vize (IDEAS) + první enabler (parametrizace); přejmenování `generate()` = samostatný příští refaktor.
- [x] **502 Wide road — hnědá výplň** (`generator.py`, `palette.py`): casing měl bílou výplň → na bílém podkladu
      neviditelný. Template `color 11` = „Upper brown 50%" → `C_ROAD` (232,167,116) + černé okraje, width 4→3 (580 µm).
- [x] **505 Footpath 2→1 px** (template 250 µm; opraven drift „375µm/2px" ze Sez. 18, verify-against-source).
- [x] **Chybějící vrstva `Silnice_neevidovaná` → 503** (`zabaged.py`): účelové/lesní asfaltky (vč. páteřní
      Bedřichov→Nová louka) byly mimo `PATH_LAYERS` → na mapě úplně chyběly. Přidána + mapování → 503 Road
      (zpevněná <5 m). Odhaleno řetězcem ověření z uživatelova GeoJSON (bbox→cache→WFS limit→GetCapabilities).
      Princip „všechna data z geoportálu" → paměť; příště el. vedení 516, Most.
- [x] **Censure! (AI) ×2 + verify-against-source:** (a) posun lokality Soví vrch přes metriku `elev_min` místo
      záměru (vrch vypadl z výseku — data ukázala NoData jen 0,21 km, posunul jsem 2,2); (b) „silnice jsou v datech"
      bez ověření fetch řetězce (chyběla celá vrstva). Lekce → paměti `verify-data-not-assume`, `geoportal-data-completeness`.

## Sezení 22 (2026-05-26) — Displacement L2 (implementace) + nález pravoúhlost budov
- [x] **Kartografická generalizace Úroveň 2 — displacement** (`generator.py`): odsazení budov od pevné
      sítě (cesty+toky=kotva) a od sebe na ISOM min. mezeru 0,4 mm (`DISPLACE_GAP_PX`≈1,83 px).
      `resolve_displacement` — greedy kolmé odsazení od nejbližší linie (mezera k OKRAJI, nese půl
      render-šířky `_line_half_width_px`), budova↔budova symetricky (každá půl), akumulovaný posun
      clampovaný na strop `MAX_DISPLACE_PX`≈3,67 px (0,8 mm). Budova = tuhé těleso → translace celého ringu.
- [x] **Inverze kontroly LOKÁLNÍ jen pro budovy** (nález proti odhadu Sez. 21 „největší skrytý náklad"):
      rastrový z-order kreslí budovy POSLEDNÍ → pevná síť (voda+cesty) hotová → žádný přepis `generate()`.
      Split `_generate_real_buildings` → `_collect_real_buildings` (fetch→map→L1, bez kresby) +
      `_resolve_and_draw_buildings` (displacement→kresba→grid pro OMAP). `_fixed_network_px` (cesty+toky
      → px linie + half_width). Tolerance WFS obaluje jen SBĚR; resolve+draw běží na sebraném.
- [x] **GT konzistence:** posun na px geometrii → render + `mask_buildings.png` + OMAP z téže geometrie
      (jako L1, px→grid inverze). Posunutá maska JE správná GT (UC5 čte mapu, ne realitu).
- [x] **Datová korekce zadání „1–2 iterace" → 8** (verify-against-source vyvrátil vlastní odhad):
      `diagnose_displacement.py` rozšířen o měření PŘED i PO displacementu (`_measure` ×2, import
      `resolve_displacement`). Při 2 iteracích budova↔budova **regreduje** (14→16 v Č. Švýcarsku — odsazení
      od cest tlačí budovy k sobě); plató od ~6 (bb zpět na baseline, dořešen slepený pár) → `DISPLACE_ITERATIONS=8`.
- [x] **Verify (čísly):** proc baseline seed 1 = **65 obj drží** (displacement se proc netýká,
      behavior-preserving). Real (Č. Švýcarsko, plná realita) = 99 budov / 57 cest / 16 vody / 55 vrstevnic,
      OMAP **232 obj**, běh 5,2 s. Kolize: budova↔síť 14→**1** (Č. ráj 2→**0**), budova↔budova neutrální
      (14→14) / +1 (6→7), dotyk/překryv 1→**0**. **Vizuál (před/po výřez): budovy odsazené kolmo od cest,
      pevná síť netknutá** — efekt decentní, kartograficky správně. Zbytkový trade-off (strop) přiznán.
- [x] **Censure! (AI — fokus bez vizuální návratnosti):** displacement je „neviditelná" generalizace
      (posun = minimum čitelnosti 0,4 mm) — měl jsem to říct při VOLBĚ fokusu (L2 = měřitelný, ne vizuální
      skok, na rozdíl od L1 tvaru). Lekce: u volby fokusu odhadnout i vizuální návratnost.
- [x] **Nález → příští fokus (uživatel): pravoúhlost budov** (L1 tvar) — lidská obydlí ≈ 99 % obdélníky,
      na mapě splňuje sotva polovina. Orthogonalizace footprintu, nezávislé na L2. → TODO `[!]`.

## Sezení 20 (2026-05-26) — batch.py → reálné vrstvy (P1) + zrušení dělení resources
- [x] **`batch.py` → plná realita** (P1 nález %AUDIT:CODE Sez. 19): reálná sada (`--terrain real`) teď
      kreslí reálné cesty/vodu/budovy ze ZABAGED (Sez. 16-18), ne jen terén + **procedurální** cesty.
      `--terrain real` automaticky zapne `paths/water/buildings=real` (KISS); `det` se u real přestal
      losovat (cesty jdou ze ZABAGED → variace = lokalita); manifest po `generate()` čte skutečné počty
      vrstev + chyby z `meta.json` (SSoT výsledku). Bohatší UC5 dataset z reálné geometrie více míst ČR.
- [x] **`generator.py` tolerantní reálné vrstvy** — `generate(..., tolerant=False)` + helper `_try_layer`:
      v dávkovém režimu selhání WFS/sítě jedné vrstvy ji vynechá (warning + `layer_errors` v `meta.json`)
      místo pádu celé mapy; prázdná data (0 features) výjimku nevyhodí (rozlišení „nic v datech" vs „WFS
      spadlo"). CLI single-mapy beze změny (default `False` = selže hlučně). Verify: proc baseline **65 obj
      drží** (zpětně kompat.), real n=2 (Č.Švýcarsko 57/16/99, Č.ráj 26/1/22), tolerance doložena monkeypatchem.
- [x] **`resources/ own vs club` ZRUŠENO (DROP)** — trénink UC5 = **syntetika** (reframe Sez. 4), reálné
      mapy = jen verify/reference/hold-out → licenční dělení vlastní/klubové **bezpředmětné** (zpochybnil
      uživatel: „model trénujeme na vygenerovaném datasetu"). Vrácena plochá struktura `resources/`.
      Smazán **duplikát** `resources/template_classic.omap` (bit-identický; kanonická tracked kopie zůstává
      v `sandbox/generator-poc/`, kde ji čte `omap_export.py` — `resources/` je gitignored). `data-sources.md`
      conceptual-integrity oprava (trénink = syntetika, reálné mapy = verify; dělení zrušeno).

## Sezení 18 (2026-05-26) — Reálné budovy (ZABAGED→521) + kartografická generalizace L1 + OOM draw order
- [x] **`connectors/zabaged.py` +budovy** (real-půlka, izomorfní s vodní plochou): `BUILDING_AREA_LAYERS`,
      `fetch_buildings` (mirror area-půlky `fetch_water`), `map_building_to_isom` (→ 521). Verify-against-source:
      diagnostika `Budova_..._plocha_` na Soví vrchu → **105 ploch**, bodová vrstva `_bod_` prázdná
      (netáhne se, jako pramen 312), `druhbud` budova/vodojem → obojí 521 (rozhodnutí uživatele-mapéra).
- [x] **`generator.py` `--buildings off|real`** (real⇒terrain real, validace). **DRY refaktor**
      `_draw_water_area` → generický `_draw_area_symbol` + wrappery (voda modrá / budova černá —
      jako `_draw_line_symbol` u linií, Sez. 17). `_generate_real_buildings`, `mask_buildings.png`,
      meta sekce „buildings". Z-order opraven dle ISOM draw orderu: vrstevnice → **body** → voda →
      cesty → budovy (body extrémů 109/110/111 byly chybně navrch, přesunuty pod cesty).
- [x] **Kartografická generalizace Úroveň 1** (na kartografický feedback uživatele). Verify-against-source
      z `template_classic.omap` (ISOM 521 popis: min. plocha 0,5×0,5 mm, mezera 0,4 mm, průchod 0,3 mm),
      `PX_PER_MM ≈ 4,58`: (a) **min. velikost budovy** `_enforce_min_size` (floor 0,5 mm); (b) **zjednodušení
      obrysu** Douglas-Peucker `_simplify_polyline` (tolerance 0,3 mm passage); (c) **tloušťka 505** 1→2 px
      (ISOM 375 µm). **Conceptual integrity:** generalizace v px → grid pro OMAP odvozen zpět (render i `.omap`
      sdílí geometrii). Displacement (Úroveň 2, kolize budov-cest) → odloženo do IDEAS + `%THINK`.
- [x] **`omap_export.py` area close-flag fix** — OOM vyplní plošný symbol jen u UZAVŘENÉHO path; flagless
      export se nevyplnil (uživatel „neviděl budovy ani vodní plochu"). Verify-against-source: OOM po otevření
      sám doplnil flag **18** (hole point 16 + close point 2). `area_object` ho generuje (301.1 + 521).
      `USED_CODES` +521, `build_features` parametr, návrat +`buildings`.
- [x] **OOM draw order objasněn (verify-against-source, ne hádání):** draw order = **priorita barev**
      (nižší = navrch; Purple overprint 0 = úplně navrch), NE pořadí symbolů/objektů ani rastrový z-order.
      Uživatel dodal IOF zdroj (kap. 7 Colour order) + čerstvý ISOM 2017-2 template (New Map). **Výměna
      template draw order nezměnila** — OOM ISOM 2017-2 sada má vrstevnice na Brown 100% (priorita 6),
      **budovu 521 na „Black below purple" (8) = pod vrstevnicí**, 502 na 11/14 (vespod). To je **záměr
      OOM** (budova pod tratěmi 7 → vedlejší efekt pod vrstevnicí 6), ne bug. **Závěr: color-table draw
      order = uživatelova OOM doména** (Colors okno), ne úkol generátoru; export referencuje symboly přes
      ISOM kód → funguje s jakýmkoli ISOM 2017-2 template.
- [x] **`template_classic.omap`** přepsán uživatelem na čerstvý ISOM 2017-2 (New Map → Save; 169 symbolů,
      35 barev). 301.1 je v sadě standardně. Export i generate ověřeny (proc 65 / real 246 drží).
- [x] **Censure! → paměť `isom-spec-before-render`:** ISOM spec (rozměry, generalizace, draw order
      z template) studovat PŘED renderem nové vrstvy, ne reaktivně po feedbacku.
- [x] **Verify (čísly):** proc baseline seed 1 = **65 obj** (behavior-preserving refaktory) · real
      (terrain+paths+water+buildings) = **246 obj** (60 vrstevnic + 58 cest + 16 vody + **105 budov** + 7 bodů).
      **Vizuál: budovy podél údolí Svitávky a cest, sedí na terén; obrysy po generalizaci čisté bloky.**

## Sezení 17 (2026-05-26) — %CALIBRATE úklid (1. svého druhu) + reálná voda ze ZABAGED WFS
- [x] **%CALIBRATE (1. meta-audit projektu)** + IDEAS/TODO pruning — oba prahy poprvé
      (grep diáře: nikdy neproběhly). Schváleno vše: **D1** projektový `settings.local.json`
      ~45→9 wildcardů (redundantní `git -C`, holé echo-stringy, jednorázové `Start-Process`);
      **D2** dvě `[x]` položky z TODO odmazány (už v DONE); **D3** `always-show-visual-output`
      povýšen do `CLAUDE.md` (tvrdé pravidlo); **D4** `MEMORY.md` index doplněn; **K1** TODO
      UC2 rámování přepsáno (2 konektory žijí); **K2** PROMPTS cadence pozn. opravena +
      ukotvena; **K3** globální `settings.local.json` `sed` one-offs smazány. Cadence reset Sez. 17.
- [x] **`connectors/zabaged.py` +voda** (real-půlka hydrografie): `fetch_water` (toky+plochy),
      `map_water_to_isom` (podzemní→None, občasný→306, pojmenovaný→304, bezejmenný→305,
      plocha→301), `_geom_to_polygons` (outer rings). Verify-against-source: GetCapabilities
      → `Vodní_tok`/`Vodní_plocha`/`Zdroj_podzemních_vod`; diagnostika atributů na Soví vrchu.
- [x] **Verify-against-source catch 312≠313:** uživatel řekl „313 pramen", template (ISOM
      2017-2 Rev 6) má **312 = Spring** (313 = Prominent water feature). Pramen nakonec
      **vynechán** — `Zdroj_podzemních_vod` 0 ve výřezu (nejbližší PS 1,9 km), nevymýšlet.
- [x] **`generator.py` `--water off|real`** (real⇒terrain real, validace). **DRY refaktor
      `_draw_line_symbol`** — jediná kreslicí logika pro cesty (černá) i vodu (modrá);
      `_draw_path`/`_draw_water_line` = tenké wrappery. `_draw_water_area` (polygon výplň+břeh),
      `_generate_real_water` (S-JTSK→grid Y-flip, mirror real-cest), `mask_water.png`, meta
      sekce „water" (dynamicky). Z-order: vrstevnice → voda → cesty → body. `C_BLUE` už v paletě.
- [x] **`omap_export.py`** `USED_CODES` +304/305/306/301.1, `write_omap` +`water_features`
      (vše type-1 objekt; plocha jako 301.1 — kombinovaný 301 je type 16, nepřiřaditelný).
- [x] **Output konsolidován** → jediný `Soví vrch/` (= uživatelova vlastní terénně mapovaná
      oblast; gitignored), scratch `output*` smazány. Opraven komentář lokality (Děčínsko →
      Soví vrch, Lužické hory). Paměť `user-field-mapper-sovi-vrch`.
- [x] **Verify (čísly):** proc baseline seed 1 = **65 objektů** (56+2+7) = baseline Sez. 14/15
      → `_draw_line_symbol` refaktor behavior-preserving. Real (terrain+paths+water): OMAP 141
      obj (60 vrstevnic + 58 cest + **16 vody** + 7 bodů). Voda = 14 toků + 2 plochy. **Vizuál:
      Svitávka v centrálním údolí, přítoky v bočních, 2 rybníky — vše sedne na terén; uživatel
      potvrdil „Voda super! Kudos!".**

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
