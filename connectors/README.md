# connectors/ — konektory reálných geodat (UC2 enabler)

Stahovače reálných dat třetích stran do nástrojů LABu. **UC2 v DAGu** (`docs/architecture.md`):
enabler pod aplikacemi. Vytaženo ze `sandbox/generator-poc/` (Sez. 16), protože konektory
nejsou specifické pro jeden experiment — generátor je dnes jediný konzument, ale koncepčně
jsou samostatný enabler (zrcadlí UC2 v DAGu).

| Modul | Zdroj | Co vrací | Protokol |
|-------|-------|----------|----------|
| `dmr.py` | ČÚZK DMR 5G | výškopis (float32 grid) | ArcGIS ImageServer `exportImage` |
| `zabaged.py` | ČÚZK ZABAGED Polohopis | komunikace + lesní průseky + voda + budovy + vedení + železnice + kolejiště + skály + mosty/tunely + řopíky (GeoJSON) | ArcGIS REST `MapServer/<id>/query` (přechod z WFS Sez. 26) |
| `ortofoto.py` | ČÚZK ORTOFOTO | letecký snímek výseku (podkladový template) | ArcGIS MapServer `export` (`arcgis1`) |

**Sourozenci, ne kopie:** `dmr` = rastr/výškopis, `zabaged` = vektor (komunikace + lesní průseky + voda +
budovy + vedení + železnice + kolejiště + skály + mosty/tunely + řopíky), `ortofoto` = rastr/podklad. Sdílí
`dmr.build_bbox` (tentýž S-JTSK výsek → data z různých zdrojů sednou na sebe bez dalšího
georef). Oba na `ags.cuzk.gov.cz`. Mapování zdroj → ISOM (u `zabaged`) viz `data-sources.md`.

**Licence:** ČÚZK open data **CC BY 4.0** (atribuce povinná — katalog + detail v
[`docs/kb/data-sources.md`](../docs/kb/data-sources.md)).

**Stav (fáze B):** skripty na `sys.path`, ne instalovaný balík. Konzument
(`sandbox/generator-poc/generator.py`) si tuto složku přidá na `sys.path` (KISS). Produkční
balík/instalace přijde s monorepem (fáze A). Cache stažených dat (`.dmr_cache/`,
`.zabaged_cache/`) je gitignored — reálná ČÚZK data do gitu nepatří.
