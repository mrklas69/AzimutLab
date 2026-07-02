# CLAUDE.md — AzimutLab (projektový overlay)

Rozšiřuje globální `~/.claude/CLAUDE.md`, nepřevažuje. Kanonické globální
definice maker jsou v `~/.claude/PROMPTS.md`; projektový override `%BEGIN`/`%END`
je v `docs/PROMPTS.md`. Stav/architektura/UC DAG: README.md +
`docs/architecture.md` (ne sem).

## Doménové pracovní zásady
- **Foundations before curtains — tvrdě.** Projekt je deštník nad 5 UC (DAG, ne
  seznam). Enablery (UC2 data / UC5 modely) jdou před aplikacemi (UC3/UC4).
  Než sáhneš na aplikaci, ověř, že enabler pod ní stojí. Scope creep je
  primární riziko — vždy se ptej „je tohle MVP, nebo záclona?".
- **Verify-against-source.** Zděděno z Pic2Omap: `.omap`/`.ocd` XML a spec
  (ISOM/ISSprOM) jsou pravda; než uvěříš agregátu, koukni do geometrie/dat.
- **Výskyt/hustotu ISOM symbolu měř JEN přes `measure_dod`/`compare_isom` mašinérii, ne ad-hoc probe.**
  Dvojí číslování (OOM 524-531 vs OCAD 535-540) dělá naivní měření slepým — ad-hoc skript už 2× vyrobil
  falešné „0 → skip": Sez. 141 crosswalk-slepý `grep code="527"` (Bedřichovka kóduje 538), Sez. 144 probe
  porovnal int `516` se string setem `{"516"}`. `measure_dod._resolve_targets` crosswalk řeší správně —
  volej ho, nepiš vlastní. Než uvěříš „symbol nevede", verify přímým objekt-countem. Paměti
  [[isom-dual-numbering-oom-ocad]] + [[verify-data-not-assume]].
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
- **Voda = no-draw zóna.** Na vodní ploše (301) se geometricky NEKRESLÍ žádný terénní / vegetační / pseudo /
  predikční / separační prvek — vyříznout vodní maskou tak, aby geometricky nevznikl (**clip**, NE z-order).
  Týká se i **vrstevnic** (101/102/103/104, hnědá kresba z DMR): kartograf vrstevnici do vodní plochy nekreslí
  a color order ji NESkryje (IOF: modrá plocha je POD hnědou linií — ověřeno Sez. 118 proti IOF Printing &
  Colour Definitions kap. 7 + OpenOrienteering/mapper#1966; náš template to má IOF-věrně; plná reference
  `docs/kb/isom-colour-order.md`) → musí pryč geometricky, ne paletou. Opakovaný lapsus: balvany 204/210 + plot 516 na hladině (Sez. 113), hranice porostu
  416 přes vodu + vrstevnice přes vodu (Sez. 118). Výjimka jen prvky, které vodu **legitimně překlenují /
  ohraničují z tvrdých dat**: břehová linie 301 (černá, nad vodou), most/lávka 512/512.2, hráz, vtékající tok
  304/305. Každá NOVÁ vrstva musí rovnou počítat s vodní maskou (DRY: sdílený `off_water` filtr, ne per-vrstva
  záplata). Princip izomorfní s [[no-degradation-in-generator-phase]] — patří do výroby, ne dodatečně.

## %THINK — doménové rozšíření
U map/CV/generování zvaž: ISOM↔ISSprOM spec rozdíly, paper-space vs world georef,
limity color separation (RGB-identické páry), sparse-GT past. U generátorů (UC4):
realistické ≠ náhodný soubor symbolů — vrstevnice/terén musí dávat fyzický smysl.

## Klíčové soubory (orientace; plný rozpis README „Repository layout")
- `docs/architecture.md` — kanonický UC DAG, vrstvení, vztah k Pic2Omap (SSoT modelu).
- `docs/kb/` — knowledgebase (data-sources / isom-issprom / tools-models).
- `connectors/` — UC2 konektory reálných geodat: `dmr.py` (výškopis), `zabaged.py` (cesty/voda/budovy/…),
  `ruian.py` (katastr, Sez. 42), `ortofoto.py` (podklad); REST sourozenci sdílí `arcgis.py` transport
  (Sez. 42). (Predikční zeleň jde ze separace, ne z dat — `forest.py` proxy SMAZÁN Sez. 102, cesta zavržena.)
  UC5 korpus: `livelox.py` (stahování reálných OB map
  + páry X,Y `build_pairs`) + `map_gt.py` (runnability GT segmentace) + `curate.py` (kurace korpusu →
  `_curation.json`, 216 keep classic, Sez. 71) + `split.py` (ČR/DE filtr 207 ČR + geografický train/val/test
  split → `_split.json`, Sez. 76), Sez. 68. Sys.path skripty, ne balík (pozn.: `rock_relief.py`
  žije v `generator/`, ne zde).
- `isom/` — sdílené ISOM utility: SVG symbolový index + capability registr generátoru
  (`real`/`mixed`/`pseudo`/`mapper_scan`), test-vynucený invariant `CAPABILITIES == USED_CODES`.
- `isom_scan/` — scan-mining / GT-factory větev (19 souborů, Sez. 142+, ROADMAP-legální
  „Generator()/scan mining", audit 260619-A1): classic-CV kandidátní detektory bodů/ploch/linií
  ze skenů (`*_points_poc.py`), ruční GT (`mark_isoms.py`/`gt_ui.py`, ruční klikání = neopakovatelná
  práce uživatele), `calibration_manifest.json` (kalibrace/recall ledger, tracked), `review_ui.py`
  (kurace kandidátů → `.omap`). Krmí KOMPAS + generátorové pokrytí, NENÍ reconstructor.
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
- `model/` — UC5 model kód (3. top-level adresář, sourozenec `connectors/`/`generator/`, Sez. 77). **Čtyři
  podadresáře** (každý vlastní `{…,dataset,train}.py`, izomorfní): `runnability/` = **archiv** `ORTO→runnability`
  baseline (slepá ulička Sez. 79, `git mv` sem Sez. 88) · `png2area/` = **živý** reconstructor `Png2Area` (mapový
  sken → area label rastr, 20 ISOM kódů + pozadí = `N_AREA=21` po 404/407/409 Sez. 152; pár
  [`rgb.png`, `area_labels.png`] z `pairs.py`; degradace on-the-fly; `tile.py`
  BEZ rejection — pozadí je legitimní třída; test mIoU **0,577 Sez. 156** (21-class retrain; 0,683 Sez. 126 byl 5-class
  na kanonickém měřítku dlaždice 1,33 před scope expansion) · `png2point/` = **živý** reconstructor
  `Png2Point` (sken → bodové symboly, `inject.py` injekce ikonek + heatmap CenterNet, **10 tříd** 204/210/417/419/525/527/531/109/111/112
  od Sez. 162 — zelené/černé man-made + hnědé terénní body, kind `dot`/`arc`/`pit`/`tower`/`fodder`/`cross`/`tree`;
  112 je reconstructor-only, gen nekreslí, mimo `USED_CODES`); test mF1 **0,745** medián 3 seedů na kanonickém
  `model/mpp.CANONICAL_MPP`. **Reálný transfer:** silný na distinktivních tvarech (111/419/525/531/109 0,65–0,89),
  210 (drobné tečky) kolabuje. Plné per-třídní číslo/detail = SSoT `README.md`/`architecture.md`, NEduplikovat sem
  (kandidát 260702-%CALIBRATE, dřív rostl s každou expanzí scope). · `png2line/` = **živý** reconstructor `Png2Line` (sken → liniové symboly,
  segmentace+skeletonizace, vektorizace přes `model/vectorize.py`; kanonický 2-class watercourse 304/305,
  test mIoU 0,774 / reálný completeness 0,85–0,93; 5-class scope Sez. 152 retrénován+revertován Sez. 156 =
  watercourse regrese → watercourse-only; Sez. 130-134).
  Trénink `mrkla`/HAL3000 (RTX 5070, torch+CUDA); ntbhej = tile smoke `build_tiles_dev`
  (maps/, bez korpusu).
- `connectors/` + `generator/` + `model/` = sdílené kódové složky mimo (zrušený) sandbox, krok k fázi A —
  pořád ale **ne produkční balík** (ten přijde s přechodem na monorepo, fáze A). Sys.path skripty.
