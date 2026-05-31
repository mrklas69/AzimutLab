# connectors/ — konektory reálných geodat (UC2 enabler)

Stahovače reálných dat třetích stran do nástrojů LABu. **UC2 v DAGu** (`docs/architecture.md`):
enabler pod aplikacemi. Vytaženo ze sandboxu (Sez. 16), protože konektory nejsou specifické
pro generátor — ten je dnes jediný konzument, ale koncepčně jsou samostatný enabler (zrcadlí
UC2 v DAGu). Vedle `connectors/` dnes stojí `generator/` (povýšen ze sandboxu, Sez. 39).

| Modul | Zdroj | Co vrací | Protokol |
|-------|-------|----------|----------|
| `dmr.py` | ČÚZK DMR 5G | výškopis (float32 grid) | ArcGIS ImageServer `exportImage` |
| `zabaged.py` | ČÚZK ZABAGED Polohopis | komunikace + lesní průseky + voda + budovy + vedení/lanovka + železnice + kolejiště + skály + mosty/tunely + řopíky + plošný pokryv (open land/hřbitov/parkoviště) + areály účelové zástavby + kůlny + zámek/hrad/zřícenina + bodové orient. prvky (kříž/mohyla/věž/strom) + liniové (sráz/zeď), Sez. 43 + **mokřady 308 + pramen 312 + jeskyně/šachta 203.2 + nádrž 311, Sez. 44** + **stromořadí → 406 lineární les, Sez. 45** + **komín → 524 + zábrana → 519 Crossing point na zdi 513, Sez. 52** + **lanovka/vlek → 510 (sloučeno s vedením), Sez. 55** (GeoJSON) | ArcGIS REST `MapServer/<id>/query` (přechod z WFS Sez. 26) |
| `ruian.py` | ČÚZK RÚIAN (katastr) | katastrální parcely podle druhu pozemku → privátní pozemky (zahrada+zastavěná) → olivová 520 (GeoJSON) | ArcGIS REST `RUIAN/MapServer/5/query` (Sez. 42) |
| `ortofoto.py` | ČÚZK ORTOFOTO | letecký snímek výseku (podkladový template) | ArcGIS MapServer `export` (`arcgis1`) |
| `arcgis.py` | — (sdílený základ) | nízkoúrovňový ArcGIS REST transport: paging+cache+GeoJSON parsery (DRY pro `zabaged`+`ruian`, Sez. 42) | — |

**Sourozenci, ne kopie:** `dmr` = rastr/výškopis, `zabaged` = vektor topografie (ZABAGED), `ruian` = vektor
katastr (RÚIAN — druhý ČÚZK zdroj, Sez. 42), `ortofoto` = rastr/podklad. Sdílí `dmr.build_bbox` (tentýž S-JTSK
výsek → data z různých zdrojů sednou na sebe bez dalšího georef) i `arcgis.fetch_geojson_layer` (společný REST
transport pro `zabaged`+`ruian`). Vše na `ags.cuzk.gov.cz`. Mapování zdroj → ISOM (u `zabaged`/`ruian`) viz `data-sources.md`.

**Licence:** ČÚZK open data **CC BY 4.0** (atribuce povinná — katalog + detail v
[`docs/kb/data-sources.md`](../docs/kb/data-sources.md)).

**Stav (fáze B):** skripty na `sys.path`, ne instalovaný balík. Konzument
(`generator/generator.py`) si tuto složku přidá na `sys.path` (KISS). Produkční
balík/instalace přijde s monorepem (fáze A). Cache stažených dat (`.dmr_cache/`,
`.zabaged_cache/`, `.ruian_cache/`, `.ortofoto_cache/`) je gitignored — reálná ČÚZK data do gitu nepatří.
