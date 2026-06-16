# IDEAS — AzimutLab

Nezralé směry a alternativy, které ještě nemají dost podkladů pro aktivní TODO.
Jakmile vznikne konkrétní další krok, přesune se do `TODO.md`; rozhodnutí a hotová
práce patří do `architecture.md`, `GLOSSARY.md` a `DONE.md`.

## Program a architektura

- **UC3 jako první aplikace před UC4-III.** De-purple + de-crease může přinést
  hmatatelný výsledek s menším enabler-minimem než úplný Pic2Omap. Rozhodnout až
  po revizi UC taxonomie z TODO A4.
- **Kvantifikovat spouštěč fáze B → A.** „Dozrálé UC5 jádro" musí znamenat
  konkrétní sdílený modul nebo druhého konzumenta, ne pocit z velikosti repa.
- **Kanonická mezivrstva napříč UC.** Převzít Pic2Omap `db.json`, nebo navrhnout
  vlastní formát až ve chvíli, kdy existují alespoň dva skuteční konzumenti.
- **Zobecnění mimo orientační mapy.** OSM/Google a jiné mapové domény odložit,
  dokud nestojí orienteering jádro; jinak by se rozpadla conceptual integrity.
- **ISSprOM / sprint pipeline.** Vyžaduje samostatný template, přemapování
  ZABAGED→ISSprOM a městské kalibrační mapy. Není to přepínač nad dnešním ISOM
  generátorem. Spouštěč: konkrétní sprintový konzument.

## Generátor

- **Noise větev později degradovat na test fixture.** Procedurální PoC už není
  hlavní produktová cesta, ale je levný offline deterministický regresní vstup.
  Mazat jej až po nahrazení stejně silným smoke testem.
- **Lepší polygonizace skal jen s doloženou vadou.** Raw geometrie je default.
  Generalizaci otevřít teprve nad konkrétním vizuálním nebo metrickým selháním.
- **Rotace rastru o grivaci.** `.omap` metadata jsou hotová; rotaci `rgb.png`
  řešit až pro konzumenta magnetic-north skenu. Patří do transformace páru nebo
  dlaždice, protože musí shodně transformovat X, Y i georef.
- **Pseudorealistická vegetace pro lokality bez skenu.** Dnešní predikční
  vegetace vzniká separací reálné mapy. Pro čisté DEV lokality chybí procedurální
  prior; případný model nebo generátor musí vytvářet věrohodnou strukturu, ne
  tvrdit, že odhaduje skutečnou průchodnost.

## Věrnost skenu

- **Geometrická augmentace po fotometrické.** Fialový přetisk a degradace jsou
  hotové, ale sklad, lokální warp a deformace papíru zůstávají. Transformace musí
  měnit X i Y současně; label rastr vždy nearest-neighbor.
- **Robustní multi-epoch ortofoto/CIR.** Jednoduchý NDVI ani dvouepochový rozdíl
  nerozlišil ISOM zeleň a trpěl radiometrickým driftem. Smysl může mít až
  relativní normalizace, více epoch a model pracující se strukturou v čase.
  Otevírat jen s lepším pokrytím a měřitelným přínosem proti dnešnímu feederu.

## Reconstructor

- **Png2Line — segmentace + odložená vektorizace (rozhodnuto Sez. 130, %THINK + rešerše).**
  Třetí reconstructor (sken → liniové ISOM symboly). Rešerše doložila čtyři branžové rodiny:
  segmentace+skeletonizace+vektorizace (dominantní pro vrstevnice/cesty z topo map), graph-based
  (RoadTracer/Sat2Graph — topologie nativně, ale těžké), line-segment transformer (LETR — laděný na
  ROVNÉ čáry, špatný fit na zakřivené OB linie), a **symbol-reconstruction synthetic data** (Chiang
  et al. 2022) — přímá validace našeho injekčního triku (imitation maps z rekonstrukce symbolů +
  mix s reálnými daty překoná real-only).
  - **Klíčové zjištění (probe injekčního triku):** trik se přenáší jen ČÁSTEČNĚ. Png2Line se rozpadá
    na dvě ORTOGONÁLNÍ podúlohy: **(A) per-class segmentace linií** (izomorfní s Png2Area, U-Net, GT
    zdarma z injekce + `.omap`) a **(B) maska → polyline vektorizace** (genuinně nová práce: skeletonizace,
    přemostění mezer u čárek, řešení křížení/junctions, RDP). Injekce řeší jen (A) — generování dat.
  - **Zvolená architektura (A): neuronový Png2Line = JEN segmentace** (jako Png2Area, který taky
    nevektorizuje — vrací area label rastr). Maska→polyline = **sdílený downstream „.omap assembly" krok**
    pro všechny tři modely (area→polygon, point→hotovo, line→polyline), ne součást modelu; zpočátku crude
    `skeletonize + RDP`, dashed/crossing jako MĚŘENÉ known limitations. KISS, reuse `tile.py`/`dataset.py`/
    `degrade`/`purple`/`eval_real`. Nový kód = jen line-aware GT + vektorizační postprocess.
  - **Izomorfismus s Png2Point (drží přístup KISS):** Png2Point predikuje 1px bod jako nafouklý Gaussian
    → peak NMS. Png2Line predikuje 1px linii jako **DILATOVANOU masku** (ať se tenká linie v U-Netu
    nerozpustí — lekce „tvar > velikost, budovy 521 0,00" z Png2Area) → skeletonizace zpět na 1px.
  - **Scope (vzor Png2Point start 204/210): souvislá distinktivní linie PRVNÍ** (505/506 cesta nebo
    304/305 tok) — de-risk celé pipeline bez dashed komplikace; PAK **508 narrow ride (dashed) + 516 fence**
    (doložený nejtěžší případ: „line-tracing nefunguje na dashed"). Dvě iterace, každá de-riskuje další.
  - **Doložená rizika:** dashed linie (508/516) tříští trasování → potřeba gap-bridging; text/anotace dělají
    díry (náš layout-bleed Sez. 118); tenké třídy se v U-Netu downsamplingem rozpustí (proto dilatovaná GT).
  - **KROK 1 HOTOVO (Sez. 130-131), architektura A potvrzena funkční:** watercourse 304/305 plný trénink
    (test mIoU 0,774 / IoU 0,55) → reálný transfer **completeness 0,85–0,93** (model trasuje reálné toky,
    žádný kolaps jako Png2Point 210; segmentace-only stačí), slabina precision přestřel na cesty → **conf_thr
    práh 0,95** (registr `LineClass`, izomorf `peak_thr`): IoU 0,409 / F1 0,773. Detail DONE/diář Sez. 131.
    ZBÝVÁ: (B) vektorizace maska→polyline (sdílený krok) + krok 2 dashed 508/516 (i strukturální cure precision).
  - **(B) vektorizace HOTOVO Sez. 132:** `model/vectorize.py` (skeletonize → graf kostry → trasování → vlastní
    RDP + `rasterize_polylines`), `scan_px_to_paper` inverze georef (SSoT vedle `paper_to_scan_px`),
    `model/png2line/vectorize_omap.py` (predikce → vektorizace → `.omap` klon georef + linie 304 + měření).
    **Ztráta vektorizace malá: ΔIoU −0,039 / ΔF1 −0,028** (3 mapy) → skeletonize+RDP drží strukturu. +scikit-image.
    Buschdörfl (NĚMECKÁ Livelox, 4. mapa): 98 % vektoru do 3 px od modrých pixelů skenu (nefíruje na cesty).
- **Poledníkový detektor — IMPLEMENTOVÁN + OVĚŘEN (Sez. 134).** `model/png2line/north_grid.py` (Codex `ac953ab`,
  dotažen Sez. 134): post-vectorization filtr, diskriminátor = členství v pravidelné soustavě. Buschdörfl: 5-liniový grid
  77,4° (pod grivací) / rozestup 30 mm → 27 poledníků odstraněno, vody zachovány. Gen render poledníky NEKRESLÍ (grivace
  jen georef metadata) = doménový gap. **Rozestup data-driven** (medián mezer + rel. tolerance, ne fixní 30±7 mm → funguje
  napříč měřítky). Follow-up: napojit do produkční cesty + 2. mapa (viz TODO). Původní záměr níže ↓.
- **Poledníkový detektor (nález uživatele Sez. 132) — svébytný modul, NE filtr na vodstvo.** Magnetické poledníky
  (modré rovné rovnoběžné čáry orientující mapu na sever) Png2Line bere jako watercourse 304/305 (modré + liniové).
  **Klíč (korekce uživatele): NELZE řešit geometrickým filtrem na watercourse výstupu** — rovný vodní KANÁL
  orientovaný na magnetický sever by se smazal. Diskriminátor poledníku = **členství v pravidelné rovnoběžné
  SOUSTAVĚ** (≥3 rovné čáry, konstantní kolmý rozestup, směr = grivace z georef), ne „rovná ∧ modrá ∧ ‖ sever".
  Osamělý kanál ‖ severu netvoří soustavu → detektor ho nechá být. **Metoda:** promítnout linie do směru kolmého
  na magnetický sever → poledníky = PERIODICKÉ peaky (rozestup ověřitelný autokorelací/FFT); kanál = ojedinělý peak.
  Grid je GLOBÁLNÍ vlastnost mapy → detektor běží nad celým skenem (ne per-pixel třída). Edge cases: grivace ≠ 0
  (poledníky pod úhlem — brát směr z georef, ne svislici); poledníky bývají i ČERNÉ (pak watercourse nebere).
  Otevřené k ověření: kreslí gen render poledníky do X párů? (pokud reálné Livelox je mají a trénink ne →
  doménový gap). Doložení nálezu Sez. 132: Buschdörfl ostrý peak 22 polyline na 90° (4× nad pozadím), vizuál.
- **Patternové area třídy.** Nearest-color rozliší odstín, ne mřížku, tečky,
  diagonály a směrové čárky. Každá nová jemná třída musí současně splnit:
  generátor ji umí vytvořit, render nese viditelný signál a
  `omap_raster.CODE_TO_LABEL` má samostatný label.
- **Class-balanced rozšíření korpusu.** Slabý model může fungovat jako filtr pro
  hard-example mining: vytipuje mapy se vzácnou třídou, člověk je potvrdí a teprve
  pak se přidají do geograficky čistého splitu. Použít jen pokud per-class
  diagnostika ukáže datový strop, ne jako automatický recept na horší metriku.
- **Multi-task encoder až po Png2Line.** Společný encoder a tři hlavy
  Area/Point/Line mohou odstranit duplicitu, ale teprve až všechny tři samostatné
  úlohy stojí a měření prokáže skutečně sdílené featury.
