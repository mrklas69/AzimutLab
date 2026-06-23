# AUDIT_CODE_260623

**Datum:** 2026-06-23 · **Auditor:** Claude Opus 4.8 (1M), 4 paralelní agenti + ruční verify proti zdroji ·
**Rozsah:** `generator/`, `model/`, `connectors/`, `isom/` + cross-cutting. **Vynecháno:** `isom_scan/` (5159 LOC,
živě mění paralelní vlákno „260621-Buschdörfl" → audit by zastaral). **Cadence:** %AUDIT:CODE od Sez. 143 (15 sez).

## TL;DR
Kód je nadprůměrně pečlivý — bohaté komentáře, vědomé DRY helpery, no-silent-fallback vesměs dodržen, SSoT registry
(`capabilities`/`USED_CODES`, `AREA_ZORDER`↔`omap_export`, `CANONICAL_MPP`). **Žádný bug-level kritický nález**
mimo jeden no-silent (split.py). Tři páky: **(1)** `split.py` tichý drop map z tréninkového poolu (no-silent),
**(2)** `capabilities` liniové kódy 306/309/508 tvrdí živý Png2Line signál, který Sez. 156 **revertoval** (registr
lže o scope — anti-Goodhart), **(3)** orientační docs (`AGENTS.md`/`CLAUDE.md`/README layout) zaostaly za kódem.
Většina DRY dluhu je vědomě komentovaná („extrahovat až 3. konzument"); tři z nich ten práh už překročily.

**Falešné poplachy zachycené verifikací:** `PX_PER_MM` je 2× ne 3× (zadání zastaralé); `ISOM_REF` má jen 2 konzumenty
(pod dokumentovaným prahem extrakce); 531 capability povýšení ověřeno jako konzistentní.

---

## OPRAVENO HNED (v tomto sezení)
Vlastní čerstvá práce + jednoznačné docs faktické chyby (nízké riziko, vysoká páka):
- **Vlastní 531 stale docstringy** (nedodělek dnešního commitu `91f4751`): `inject.py` modul docstring + `_heat_overlay`
  5. barva (531 oranžová, izomorf `eval_real._overlay`) + `eval_real.parse_carto_points` docstring (`CODE_TO_IDX … 531→4`).
- **`AGENTS.md` faktické chyby** (čte se každé sezení, aktivně zaváděl): `clip_quad.py`→`cut.py` (přejmenováno Sez. 114,
  soubor neexistoval), `forest.py` archiv→SMAZÁN (Sez. 102), doplněn `png2line/` (vynechán — „tři" → „čtyři podadresáře,
  tři živé reconstructory"), čísla 0,683→0,577 / 0,827→0,811, scope +531.
- **README „Repository layout" bodové faktické chyby (D10, jednoznačná část):** doplněn `png2{area,point}/eval_real.py`,
  `png2line/{north_grid,vectorize_omap}.py`, celý `tools/`; `png2line/tile.py` popis 5-class→2-class (revert Sez. 156);
  root-files věta + `AGENTS.md`. (Strukturální část D10 — layout JEN v per-dir READMEs + odkaz z root/CLAUDE/AGENTS — zůstává k odsouhlasení.)
- **[C1] `split.py` no-silent** (commit `ed5d7cb`): chybějící mapa v `_cz_filter.json` teď HLASITĚ varuje na stderr;
  **selekce ZACHOVÁNA** (chybějící = konzervativně vyřazena → mIoU split se nerozejde) — bezpečná půlka opravy. Re-build
  filtru po růstu korpusu zůstává manuální krok (lazy re-probe = samostatné rozhodnutí, ne uděláno).
- **[D1] `capabilities` 306/309/508 `SCAN_LIVE_LINE`→`SCAN_CANDIDATE`** (commit `ed5d7cb`): sladěno s Png2Line scope po
  revertu Sez. 156 (živý jen 304/305) — registr už nelže o scan signálu (anti-Goodhart). Test sladěn + 304 assertce.
  **Zbývá (k odsouhlasení):** 309 `generator_kind=mapper_scan` je aspirativní (generátor 309 z dat nekreslí, Png2Line neumí) — revize, zda 309 vůbec patří do registru / jaký zdroj.

## K ODSOUHLASENÍ (neopraveno — %AUDIT:CODE pravidlo / riziko / netriviální)

### Kritický
- **[C1] `connectors/split.py:42,74` — tichý drop mapy z tréninkového poolu.** `cz_dirs()` `nw.get(d.name, 1.0) < EMPTY`
  → mapa chybějící v `_cz_filter.json` dostane default 1.0 → tiše vyřazena jako „cizí"; `_near_white_map()` re-probuje JEN
  když chybí celý soubor → růst korpusu nikdy nespustí přepočet → nově kurátorované keep mapy tiše vypadnou z tréninku.
  Porušuje no-silent-fallback (sourozenec `curate.py:134` plní explicitním printem). **Známý dluh** (TODO „split.py:72
  tichý default"). **Riziko opravy:** změna chování splitu = neporovnatelné mIoU → opravit vědomě (log/raise chybějícího
  klíče, ne změna selekce). Páka roste, až poroste korpus.

### Doporučené
- **[D1] `isom/capabilities.py:149/159/166` — 306/309/508 `SCAN_LIVE_LINE` nadhodnocuje Png2Line scope.** Ověřeno proti
  SSoT `omap_raster.LINE_CLASSES` (N_LINE=2 = jen 304/305 po Sez. 156 revertu; 309 kolaps F1 0,000, 306/508 doménový gap).
  Registr tvrdí živý scan signál pro linie, co reconstructor neumí → `preferred_kind` 306/508 (GEN_REAL) překlápí na
  mapper_scan na neexistujícím signálu = anti-Goodhart (podkopává účel registru). **Nedokončený revert Sez. 156/157**
  (LINE_CLASSES kód revertován, capabilities + `test_symbol_capabilities.py:60-63` zapomenuty = SLAP). Fix: 306/508 →
  `SCAN_CANDIDATE`, 309 → rozhodnout (má i divný `generator_kind=mapper_scan` bez zdroje) + sladit test. **Netriviální
  → tvá volba** (souvisí s dnešní capability prací, ale dluh je z Sez. 156).
- **[D2] `connectors/arcgis.py:79` — paging končí dle délky dávky, ne `exceededTransferLimit`** → tichý ořez, když vrstva
  má `maxRecordCount` < 2000 (třída chyby WFS-1000 Sez. 25-26). Dnes neškodí (ZABAGED cap 2000). = TODO B4, trvá 3 audity.
- **[D3] `connectors/zabaged.py:826/855/899` — area-mappery tichý catch-all default** (`map_open_land`→401 / `map_paved`→501
  / `map_utility_area`→520) vs `map_path_to_isom:779` zahardenováno na raise (Sez. 110). Nová/přejmenovaná vrstva tiše
  dostane default kód. Fix: raise jako u path-mapperu (no-silent + conceptual integrity).
- **[D4] DRY balíček `model/` — práh 3+ konzumentů překročen** (= TODO D9, dozrálé): ImageNet MEAN/STD **6×** (`png2{area,
  point,line}/{dataset,eval_real}.py`), eval_real tiled-inference blok **3×** (area/point/line `predict_*`), `src_mpp`
  pgw lambda **4×**, `_map_area_mask` **2×** (point≡line eval_real), peak helpery `_nms`/`_peaks_xy`/`_match_counts`
  kopie train→point eval_real. Fix: `model/eval_common.py` (tiled inference + pgw→mpp) + `model/norm.py` (ImageNet SSoT)
  + `model/peaks.py`. **Riziko:** dotýká se živých reconstructorů → odsouhlasit dávku.
- **[D5] DRY `.pgw` parse 4×** (`cut.py:41`, `gen_backgrounds.py:53`, `measure_dod.py` 3× inline, `compare_real_vs_gen.py`)
  → sdílený `read_pgw()` (ideálně `connectors/` vedle geo-helperů).
- **[D6] Mrtvý kód `generator.py`:** `BRIDGE_NAME`/`ISOM_BRIDGE`/`ISOM_FOOTBRIDGE` (732-735, dict se nečte; meta mostů
  jména hardcoduje znovu) + `ROTATABLE_CODES` členy `512.2`/`519` (82, nikdy nevyhodnocené — jdou vlastními smyčkami).
- **[D7] Mrtvý EMA experiment `png2point/train.py:219-243`** (~25 ř. + CLI `--ema`) — paměť i `eval_real.py:268` říkají
  „EMA slepá ulička", ale docstring `_EMA` ji prezentuje pozitivně. Default off. Fix: odstranit nebo docstring srovnat.
- **[D8] Kolize jména `PX_PER_MM`** — `generator.py:76` = 4,5855 (rastr/papír) vs `model/{purple,png2point/inject}.py`
  ≈ 7,52 (px/mm dlaždice); `MAP_SCALE=10000` 3×. Footgun. Fix: přejmenovat (`PAPER_PX_PER_MM` vs `TILE_PX_PER_MM`) + SSoT do `mpp.py`.
- **[D9] `generator/degrade.py` umístěn špatně** — importuje ho jen `model/` (3× `dataset.py`, každý přidává generator/ na
  path), v `generator/` nikdo. Sourozenec `purple.py` (táž augmentace) žije v `model/`. Fix: přesun do `model/`.
- **[D10] README „Repository layout" drift** — chybí `tools/` (3 soubory), `model/png2{area,point}/eval_real.py`,
  `png2line/{north_grid,vectorize_omap}.py`. Per-dir READMEs jsou aktuální → root zaostal. (CLAUDE.md/AGENTS.md „Klíčové
  soubory" duplikují layout — root README:79 deklaruje „CLAUDE.md thin, facts in README", realita opačná. Strukturální:
  zvážit layout JEN v per-dir READMEs + odkaz.)
- **[D11] Png2Line checkpoint-výběr ≠ deployment** — `train.evaluate` měří mIoU holým argmax BEZ `LINE_CONF_THR`, ale
  `eval_real`/`vectorize_omap` práh aplikují → best checkpoint vybírán jiným pravidlem než nasazení. Dopad pravděpodobně
  malý (conf_thr ořezává FP). Png2Point past nemá (peak_thr stejné v train i eval).

### Kosmetické (stručně, file:line v agent logu)
K1 `compare_isom.detect_version:188` tichý default „2017-2" (warn) · K2 `_point_in_ring` 2 signatury (generator:1548 vs
rock_relief:126, lokální import stíní) · K3 scanline/shoelace duplicita 4× (propletené s pattern-kresbou) · K4
`LINE_LABEL_VIS` neodvozené z registru · K5 `__future__ import annotations` + bezdiakritické komentáře v `isom/`+`tools/`
(starší ostrov, proti paměti `python314-no-future-annotations`) · K6 `mpp.py:60` no-op ternary `arr if not label else arr`
· K7 521 Building jako jediný area kód bez `SCAN_AREA` (nekonzistence reportu) · K8 `CONFLICT_POLICY` termín
„external_geodata" ≠ `GEN_REAL` · K9 `split.py` sys.path 4× inline (helper existuje v livelox) · K10 `STATISTICS.md`
generovaný artefakt commitnutý · K11 `_layer_meta_section` source „cuzk_zabaged" i pro rocks (206 z DMR).

### Nejisté (nedoloženo)
- `livelox.py:165` `_resolve_georef` docstring↔kód rozpor u WGS84 fallbacku — nedoloženo, že tvar dat existuje; padlo by hlasitě.

---

## Pozitivní (nerozbíjet)
- `_try_layer` tolerant + `warning` + `layer_errors`; `measure_dod._missing_pgw`; `curate.py:134` explicitní vynechání;
  `map_path_to_isom` raise — vzorové no-silent. Georef `paper_to_scan_px` čistě DRY (1 def, ostatní importují).
  `USED_CODES = generator_codes()` jeden zdroj. Dead-file scan čistý (žádné .bak/.tmp/ne-ASCII/prázdné adresáře).
  531 capability + test konzistentní.

*Nálezy → úkoly: po odsouhlasení do TODO (až paralelní vlákno uvolní `docs/TODO.md`). C1/D1 mají nejvyšší páku.*
