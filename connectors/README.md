# connectors/ — konektory reálných geodat (UC2 enabler)

Stahovače reálných dat třetích stran do nástrojů LABu. **UC2 v DAGu** (`docs/architecture.md`):
enabler pod aplikacemi. Vytaženo ze sandboxu (Sez. 16), protože konektory nejsou specifické
pro generátor — ten je dnes jediný konzument, ale koncepčně jsou samostatný enabler (zrcadlí
UC2 v DAGu). Vedle `connectors/` dnes stojí `generator/` (povýšen ze sandboxu, Sez. 39).

| Modul | Zdroj | Co vrací | Protokol |
|-------|-------|----------|----------|
| `dmr.py` | ČÚZK DMR 5G | výškopis (float32 grid) | ArcGIS ImageServer `exportImage` |
| `zabaged.py` | ČÚZK ZABAGED Polohopis | komunikace + lesní průseky + voda + budovy + vedení/lanovka + železnice + kolejiště + skály + mosty/tunely + řopíky + plošný pokryv (open land/hřbitov/parkoviště) + areály účelové zástavby + kůlny + zámek/hrad/zřícenina + bodové orient. prvky (kříž/mohyla/věž/strom) + liniové (sráz/zeď), Sez. 43 + **mokřady 308 + pramen 312 + jeskyně/šachta 203.2 + nádrž 311, Sez. 44** + **stromořadí → 406 lineární les, Sez. 45** + **komín → 524 + zábrana → 519 Crossing point na zdi 513, Sez. 52** + **lanovka/vlek → 510 (sloučeno s vedením), Sez. 55** + **kamenolom `Povrchová těžba, lom` → 520 olivová, Sez. 56** + **pole balvanů `Skupina_balvanů__linie_` → 208 Boulder field, Sez. 57** (GeoJSON) | ArcGIS REST `MapServer/<id>/query` (přechod z WFS Sez. 26) |
| `ruian.py` | ČÚZK RÚIAN (katastr) | katastrální parcely podle druhu pozemku → privátní pozemky (zahrada+zastavěná) → olivová 520 (GeoJSON) | ArcGIS REST `RUIAN/MapServer/5/query` (Sez. 42) |
| `forest.py` | **AOPK** „Les_Mapy" (LHP/LHO Lesy ČR + ÚHÚL) | porostní skupiny (vrstva 19); atribut `BARVA` = ordinální věk → ISOM zeleň **406/408/410** (PROXY: věk≠runnability, predikce), Sez. 62 (GeoJSON) | ArcGIS REST `Les_Mapy_20nn/MapServer/19/query` na **`gis.nature.cz`** (ne ČÚZK; `maxRecordCount=1000`) |
| `ortofoto.py` | ČÚZK ORTOFOTO | letecký snímek výseku (podkladový template) | ArcGIS MapServer `export` (`arcgis1`) |
| `arcgis.py` | — (sdílený základ) | nízkoúrovňový ArcGIS REST transport: paging+cache+GeoJSON parsery (DRY pro `zabaged`+`ruian`+`forest`, Sez. 42/62) | — |
| `livelox.py` | **Livelox** (reálné OB mapy) | `download_map(classId)` → rastr `map.png` + georef `meta.json` (quad + **epsg z dat**: 5514/32633, WGS84 fallback typ B) + `blend.png` (warp přes ortofoto = georef důkaz). **Batch (Sez. 70):** `search_events`/`download_corpus` → korpus **268 map** (S.Čechy CZ + Žitavsko DE/SAXBO), 1 class/event, idempotent, backoff retry. **UC5 korpus**, ne ČÚZK. Sez. 68/70 | `POST /Data/ClassInfo` → blob; `POST /Home/SearchEvents` (eventy) |
| `map_gt.py` | — (zpracování) | `segment_gt(map.png)` → runnability **GT** `gt_labels.png` (0 průchodný/1 ISOM 406/2 408/3 410/4 open) + `gt_vis.png`. Nearest-color na ISOM refs + majority filtr. SLAP: stahování (`livelox`) ≠ segmentace. Sez. 68 | — |

**Sourozenci, ne kopie:** `dmr` = rastr/výškopis, `zabaged` = vektor topografie (ZABAGED), `ruian` = vektor
katastr (RÚIAN — druhý ČÚZK zdroj, Sez. 42), `forest` = vektor věku porostu (AOPK „Les_Mapy" — třetí zdroj,
JINÝ server `gis.nature.cz`; PROXY/predikce, Sez. 62), `ortofoto` = rastr/podklad. Sdílí `dmr.build_bbox` (tentýž S-JTSK
výsek → data z různých zdrojů sednou na sebe bez dalšího georef) i `arcgis.fetch_geojson_layer` (společný REST
transport pro `zabaged`+`ruian`). Vše na `ags.cuzk.gov.cz`. Mapování zdroj → ISOM (u `zabaged`/`ruian`) viz `data-sources.md`.

**Dvě větve:** ČÚZK/AOPK konektory (`dmr`…`ortofoto`) = **UC2** vstupní geodata pro generátor.
`livelox`+`map_gt` (Sez. 68) = **UC5 korpus** reálných OB map + ground-truth běhatelnosti (supervised
trénink) — jiný zdroj i účel, žije v `resources/livelox/`.

**Licence:** ČÚZK/AOPK open data **CC BY 4.0** (atribuce povinná — katalog + detail v
[`docs/kb/data-sources.md`](../docs/kb/data-sources.md)). **Livelox mapy NEJSOU open** — práva drží
kartograf/pořadatel/federace; korpus je privátní nekomerční experiment (TDM výjimka), legalizace (ČSOS)
až pokud model funguje. Proto `resources/livelox/` gitignored a nesdílí se.

**Stav (fáze B):** skripty na `sys.path`, ne instalovaný balík. Konzument
(`generator/generator.py`) si tuto složku přidá na `sys.path` (KISS). Produkční
balík/instalace přijde s monorepem (fáze A). Cache stažených dat (`.dmr_cache/`,
`.zabaged_cache/`, `.ruian_cache/`, `.ortofoto_cache/`) je gitignored — reálná ČÚZK data do gitu nepatří.
