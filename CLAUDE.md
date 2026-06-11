# CLAUDE.md — AzimutLab (projektový overlay)

Rozšiřuje globální `~/.claude/CLAUDE.md`, nepřevažuje. Makra %BEGIN/%END:
viz `docs/PROMPTS.md`. Stav/architektura/UC DAG: README.md + `docs/architecture.md`
(ne sem).

## Doménové pracovní zásady
- **Foundations before curtains — tvrdě.** Projekt je deštník nad 5 UC (DAG, ne
  seznam). Enablery (UC2 data / UC5 modely) jdou před aplikacemi (UC3/UC4).
  Než sáhneš na aplikaci, ověř, že enabler pod ní stojí. Scope creep je
  primární riziko — vždy se ptej „je tohle MVP, nebo záclona?".
- **Verify-against-source.** Zděděno z Pic2Omap: `.omap`/`.ocd` XML a spec
  (ISOM/ISSprOM) jsou pravda; než uvěříš agregátu, koukni do geometrie/dat.
- **KB je živá, ne archiv.** Každý zdroj dat (UC2) nese v `docs/kb/` i licenci.
  Stavět UC4-II/III na datech bez vyjasněné licence = chyba.
- **Pic2Omap je sourozenec, ne kopie.** Dokud jsme deštník (fáze B), Pic2Omap
  žije ve vlastním repu — neduplikuj jeho kód sem; odkazuj. Absorpce (fáze A)
  je vědomý budoucí krok, ne tichý drift.
- **Vizuál ukazuj proaktivně.** Po každém renderu / změně vzhledu sám ukaž výstup
  (`rgb.png` přes Read), neptej se „chceš vidět?". Uživatel je rozhodující článek
  vizuálního verify (oko = source, doplněk verify-against-source). Proč/detail:
  paměť `always-show-visual-output`.
- **Generalizuj jen v odůvodněných případech — raw je default.** Reálná geodata (ZABAGED)
  jsou už věrný zdroj; nepřidávej generalizační vrstvu, dokud konkrétní vada nedokáže, že je
  potřeba. Generalizace půdorysu budov (Sez. 18 DP/min-size → Sez. 27 orthogonalizace +
  displacement) způsobila víc problémů než užitku (komolení tvaru, lichoběžníky, špatná
  orientace malých, neškálovatelný O(n²)) → **zavrženo, návrat k raw kresbě jako voda** (voda
  byla od začátku dokonalá právě proto, že raw). Lekce: „nejdřív raw, generalizuj až s důkazem".
- **No silent fallback.** Když chybí vstup/data/závislost nebo selže předpoklad, **selži nahlas
  nebo zarytě varuj** — nikdy tiše nespadni do náhradní cesty. Tichý fallback maskuje bugy a tváří
  se jako úspěch. Lekce: cache skip-existing dělal kompas slepým ke změnám generátoru (Sez. 99);
  `gitignored` korpus → ověř dostupnost, nepředpokládej (paměť `gitignored-availability-verify-not-assume`).
  Dobrý vzor: `measure_dod._missing_pgw` chybějící `.pgw` hlásí a vynechané mapy vypíše, nemlčí.

## %THINK — doménové rozšíření
U map/CV/generování zvaž: ISOM↔ISSprOM spec rozdíly, paper-space vs world georef,
limity color separation (RGB-identické páry), sparse-GT past. U generátorů (UC4):
realistické ≠ náhodný soubor symbolů — vrstevnice/terén musí dávat fyzický smysl.

## Klíčové soubory (orientace; plný rozpis README „Repository layout")
- `docs/architecture.md` — kanonický UC DAG, vrstvení, vztah k Pic2Omap (SSoT modelu).
- `docs/kb/` — knowledgebase (data-sources / isom-issprom / tools-models).
- `connectors/` — UC2 konektory reálných geodat: `dmr.py` (výškopis), `zabaged.py` (cesty/voda/budovy/…),
  `ruian.py` (katastr, Sez. 42), `ortofoto.py` (podklad); REST sourozenci sdílí `arcgis.py` transport
  (Sez. 42). (Predikční zeleň jde ze separace, ne z dat — `forest.py` proxy archiv Sez. 102.)
  UC5 korpus: `livelox.py` (stahování reálných OB map
  + páry X,Y `build_pairs`) + `map_gt.py` (runnability GT segmentace) + `curate.py` (kurace korpusu →
  `_curation.json`, 216 keep classic, Sez. 71) + `split.py` (ČR/DE filtr 207 ČR + geografický train/val/test
  split → `_split.json`, Sez. 76), Sez. 68. Sys.path skripty, ne balík (pozn.: `rock_relief.py`
  žije v `generator/`, ne zde).
- `generator/` — UC4-I/UC5 generátor OB map (pilíř Laboratoře; povýšen ze `sandbox/generator-poc/`
  v Sez. 39 — `sandbox/` zrušen, byl jediný obyvatel). Konzumuje `connectors/`. `generate_map()` =
  hlavní vstup. Výstupy → `maps/<lokalita>/` (gitignored, kotveno v kořeni přes `MAPS_DIR`).
  Fáze I `generator()`: `separate.py` (separace barev mapy → plochy, `separate_areas` + `TARGET_MPP`
  downscale, Sez. 82-85) + `pairs.py` (orchestrátor `build_pair`/`build_pairs` per-classId párů X,Y
  z Livelox korpusu, Sez. 83-85). `rock_relief.py` (skály 206 z DMR sklonu, Sez. 63). Post-process (string,
  ne ET): `cut.py` (geometrický ořez `.omap`, Sez. 114 — primitiva `cut_point`/`cut_line`/`cut_area`
  Sutherland-Hodgman → orchestrátor `clip_omap` přepíše `<coords>` se zachováním flagů, scoped na `<objects>`
  → wrappery `cut_box` papír [CLI `--location`, real terrain] / `clip_omap_to_quad` Livelox quad; odstraní přesah
  bboxu = okolní sídla „Nisa do Vesce", Sez. 109/113/114) + `gen_backgrounds.py` (OOM bg podklady do gen.omap: `add_backgrounds` Livelox
  pár / `add_resources_scan_background` resources měřicí mapa, Sez. 104/109).
- `model/` — UC5 model kód (3. top-level adresář, sourozenec `connectors/`/`generator/`, Sez. 77). **Tři
  podadresáře** (každý vlastní `{…,dataset,train}.py`, izomorfní): `runnability/` = **archiv** `ORTO→runnability`
  baseline (slepá ulička Sez. 79, `git mv` sem Sez. 88) · `png2area/` = **živý** reconstructor `Png2Area` (mapový
  sken → area label rastr, 18 tříd ze `omap_raster`; pár [scan.png, area_labels.png] z `pairs.py`; `tile.py`
  BEZ rejection — pozadí je legitimní třída; test mIoU 0,568 Sez. 103) · `png2point/` = **živý** reconstructor
  `Png2Point` (sken → bodové symboly, `inject.py` injekce ikonek + heatmap CenterNet, scope 204/210; test mF1
  0,897 Sez. 106). Trénink jen `mrkla` (RTX 5070, torch+CUDA); ntbhej = tile smoke `build_tiles_dev`
  (maps/, bez korpusu).
- `connectors/` + `generator/` + `model/` = sdílené kódové složky mimo (zrušený) sandbox, krok k fázi A —
  pořád ale **ne produkční balík** (ten přijde s přechodem na monorepo, fáze A). Sys.path skripty.
