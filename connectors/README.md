# connectors/ — konektory reálných geodat (UC2 enabler)

Stahovače reálných dat třetích stran do nástrojů LABu. **UC2 v DAGu** (`docs/architecture.md`):
enabler pod aplikacemi. Vytaženo ze sandboxu (Sez. 16), protože konektory nejsou specifické
pro generátor — ten je dnes jediný konzument, ale koncepčně jsou samostatný enabler (zrcadlí
UC2 v DAGu). Vedle `connectors/` dnes stojí `generator/` (povýšen ze sandboxu, Sez. 39).

| Modul | Zdroj | Co vrací | Protokol |
|-------|-------|----------|----------|
| `dmr.py` | ČÚZK DMR 5G | výškopis (float32 grid) | ArcGIS ImageServer `exportImage` |
| `zabaged.py` | ČÚZK ZABAGED Polohopis | komunikace + lesní průseky + voda + budovy + vedení/lanovka + železnice + kolejiště + skály + mosty/tunely + řopíky + plošný pokryv (open land/hřbitov/parkoviště) + areály účelové zástavby + zámek/hrad/zřícenina + bodové orient. prvky (kříž/mohyla/věž/strom) + liniové (sráz/zeď), Sez. 43 + **mokřady 308 + pramen 312 + jeskyně/šachta 203.2 + nádrž 311, Sez. 44** + **stromořadí → 406 lineární les, Sez. 45** + **komín → 524 + zábrana → 519 Crossing point na zdi 513, Sez. 52** + **lanovka/vlek → 510 (sloučeno s vedením), Sez. 55** + **kamenolom `Povrchová těžba, lom` → 520 olivová, Sez. 56** + **pole balvanů `Skupina_balvanů__linie_` → 208 Boulder field, Sez. 57**; kůlny/skleníky/přístřešky vyřazeny Sez. 173 (GeoJSON) | ArcGIS REST `MapServer/<id>/query` (přechod z WFS Sez. 26) |
| `ruian.py` | ČÚZK RÚIAN (katastr) | katastrální parcely podle druhu pozemku → privátní pozemky (zahrada+zastavěná) → olivová 520 (GeoJSON) | ArcGIS REST `RUIAN/MapServer/5/query` (Sez. 42) |
| `ortofoto.py` | ČÚZK ORTOFOTO | letecký snímek výseku (podkladový template) | ArcGIS MapServer `export` (`arcgis1`) |
| `arcgis.py` | — (sdílený základ) | nízkoúrovňový ArcGIS REST transport: paging přes `exceededTransferLimit` + cache + GeoJSON parsery (DRY pro `zabaged`+`ruian`, Sez. 42/175) | — |
| `ssl_ctx.py` | certifi CA bundle | sdílený TLS kontext pro `urllib` konektory ČÚZK/Livelox; selže nahlas, když chybí `certifi` | — |
| `magnetic.py` | WMM (lokální) + pyproj | **grivace** (úhel grid S-JTSK → magnetický sever) pro bod+datum = deklinace (`pygeomag` WMM offline) + konvergence poledníků (`pyproj`); znaménko `decl−pyproj_conv` ověřeno proti skenům. Konzument: generator `--grivation-auto`. Sez. 112 | — (offline model, žádný REST/key; NOAA WMM API zavrženo = vyžaduje registraci+key) |
| `livelox.py` | **Livelox** (reálné OB mapy) | `download_map(classId)` → rastr `map.png` + georef `meta.json` (quad + **epsg z dat**: 5514/32633, WGS84 fallback typ B) + `blend.png` (warp přes ortofoto = georef důkaz). **Batch (Sez. 70):** `search_events`/`download_corpus` → korpus **268 map** (S.Čechy CZ + Žitavsko DE/SAXBO), 1 class/event, idempotent, backoff retry. **Páry (X,Y):** `build_georef_pair` (1 mapa → `ortho.png`+`gt_grid.png` zarovnané, GATE 1 Sez. 75), `build_pairs` (dávka, resumovatelná/tolerantní, QC offset; CLI `pairs` → 207 ČR map, Sez. 76). **UC5 korpus**, ne ČÚZK. Sez. 68/70/75/76 | `POST /Data/ClassInfo` → blob; `POST /Home/SearchEvents` (eventy) |
| `map_gt.py` | — (zpracování) | `segment_gt(map.png)` → runnability **GT** `gt_labels.png` (0 průchodný/1 ISOM 406/2 408/3 410/4 open/**255 ignore**) + `gt_vis.png`. Nearest-color na ISOM refs + majority filtr. **Olivová 520 → label 0** (Sez. 71, out-of-bounds ne runnability; 2 odstíny). **Fialový přetisk tratě → label 255 ignore** (Sez. 72, 2 purpurové odstíny z dat, maska dilatovaná po median; trénink přeskočí přes ignore_index; 31 % keep map ho nese). **Layout mimo mapu → 255 ignore** (Sez. 73 část B, `_detect_map_area`: barevný detektor — sytá ISOM paleta = mapa, černobílé bloky/papír = okraj → legenda/titulek/tiráž/logo/papír ignore; control-desc tabulka s barevnými symboly = known limitation). SLAP: stahování (`livelox`) ≠ segmentace. Sez. 68/71/72/73 | — |
| `curate.py` | — (zpracování) | `build_curation()` → manifest `_curation.json` (merge-aware): discipline {classic/sprint/mtbo/overview} + quality tagy → `keep`. Reader `load_curation`/`kept_dirs('classic')` = kontrakt UC5 loaderu. **268 → 216 keep classic** (Sez. 71). | — |
| `split.py` | — (zpracování) | **Geografický train/val/test split** (Sez. 76): ČR/DE filtr (`_cz_filter.json`, 216 keep → **207 ČR**, cizí = prázdné ČÚZK ortofoto) → clustery dle překryvu S-JTSK bboxů (union-find) → greedy 70/15/15 → `_split.json`. Bez leaku (celý cluster do 1 splitu). Reader `dirs_for('train')`/`split_of(cid)` = kontrakt loaderu. | ČÚZK ortofoto (filtr) |

**Sourozenci, ne kopie:** `dmr` = rastr/výškopis, `zabaged` = vektor topografie (ZABAGED), `ruian` = vektor
katastr (RÚIAN — druhý ČÚZK zdroj, Sez. 42), `ortofoto` = rastr/podklad. (Pozn.: `forest.py` = vektor věku
porostu AOPK „Les_Mapy" byl **archivován/smazán Sez. 102** — predikční vegetace jde ze separace reálné mapy
`generator/separate.py`, ne z proxy věku.) Sdílí `dmr.build_bbox` (tentýž S-JTSK
výsek → data z různých zdrojů sednou na sebe bez dalšího georef) i `arcgis.fetch_geojson_layer` (společný REST
transport pro `zabaged`+`ruian`). HTTPS konektory používají `ssl_ctx.ssl_context()` s `certifi` bundlem
(ČÚZK/Livelox TLS řetězec na Windows nesmí spadnout do tichého env workaroundu). Vše na `ags.cuzk.gov.cz`.
Mapování zdroj → ISOM (u `zabaged`/`ruian`) viz `data-sources.md`.

**Dvě větve:** ČÚZK/AOPK konektory (`dmr`…`ortofoto`) = **UC2** vstupní geodata pro generátor.
`livelox`+`map_gt`+`curate`+`split` = **UC5 korpus** reálných OB map + ground-truth běhatelnosti (supervised
trénink): stažení → GT segmentace → kurace → train/val/test split + páry (X,Y). Jiný zdroj i účel, žije
v `resources/livelox/`.

**Licence:** ČÚZK/AOPK open data **CC BY 4.0** (atribuce povinná — katalog + detail v
[`docs/kb/data-sources.md`](../docs/kb/data-sources.md)). **Livelox mapy NEJSOU open** — práva drží
kartograf/pořadatel/federace; korpus je privátní nekomerční experiment (TDM výjimka), legalizace (ČSOS)
až pokud model funguje. Proto `resources/livelox/` gitignored a nesdílí se.

**Stav (fáze B):** skripty na `sys.path`, ne instalovaný balík. Konzument
(`generator/generator.py`) si tuto složku přidá na `sys.path` (KISS). Produkční
balík/instalace přijde s monorepem (fáze A). Cache stažených dat (`.dmr_cache/`,
`.zabaged_cache/`, `.ruian_cache/`, `.ortofoto_cache/`) je gitignored — reálná ČÚZK data do gitu nepatří.
