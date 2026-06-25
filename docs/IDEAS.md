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

- **Png2Line — otevřené nezralé větve** (krok 1 watercourse 304/305 + vektorizace HOTOVO Sez. 130-132,
  detail `architecture.md` UC5 + DONE). Nezralé: **krok 2 dashed 508/516 JINÝM přístupem** — přidání třídy
  do multi-class je **2× doložený neúspěch** (Sez. 133 doménový gap completeness 0,14–0,22; Sez. 156 5-class
  scope retrénován → watercourse regrese 0,409→0,26 + 309 kolaps → revert na 2-class) → jiný přístup =
  morfologické přemostění přerušení / dashed-specifická augmentace, NE další třída. + gap-bridging u junkcí
  (tříštění toků na uzlech) + napojení poledníkového filtru (`north_grid.py`, hotový Sez. 134) do produkční inference.
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
- **Hotový pretrained model místo vlastního tréninku? (Etapa 2; Sez. 142.)** Plug-and-play model
  „sken → ISOM" prakticky NEEXISTUJE — problém není „umět detekovat vzory", ale „znát naši symbolovou
  sadu" (ISOM kódy = doménový slovník, který pretrained modely nemají) → ~5 %. Class-agnostic foundation
  (SAM/SAM2) dá masky bez sémantiky + je out-of-domain (fotky vs kartografie, drobné Point/Line nezvládá);
  open-vocab (GroundingDINO/CLIP) nefunguje na abstraktní značky. **Cokoli stáhneš = stejně doučit na párech
  (X, Y)** — což je přesně to, kvůli čemu existuje `generator()`. Stažený model proto nemění strategii, jen
  startovní bod tréninku. **Reálná páka = silnější pretrained BACKBONE** (dnes `encoder_weights="imagenet"`
  resnet34 ve všech třech `train.py` — transfer learning UŽ těžíme; změna `ENCODER` na resnet50/efficientnet
  /SAM-encoder-jako-feature-extractor = levný experiment, může zvednout mIoU bez nových dat). Až za fázovou
  závorou ROADMAP (Etapa 2 / model), ne teď. **Empirický test té ~5 % hypotézy = `isom_scan/` benchmark**
  (fixní prompt + JSON výstup, oddělený `score.py` proti GT, `results.csv` napříč cloud i lokálními modely;
  headline `point_F1`). Detaily/úkoly v TODO „ISOM-scan benchmark".
- **Vytěžek z běhu ChatGPT 5.5 (Sez. 146) — `docs/IDEAS_from_chatgpt55.md`.** ChatGPT 5.5 v benchmarku
  drtivě porazil Opus (class_recall 0,875 vs 0,125) classic-CV technikami „od ruky". **Nejcennější k převzetí:**
  (1) **black-excluding-brown maska** `(max<130)&(max−min<18)` = oddělení černé kresby od hnědých vrstevnic
  (REC + měřicí skripty); (2) **exact-color histogram skenu** = kalibrační cíl barev generátoru (GEN, verify
  pro BARVU) + základ separace; (3) **16×16 shape-descriptor** X/ring/kruh = non-ML klasifikátor png2point tříd;
  (4) **render-first spec + O-Map Wiki** na přesné tvary před commitem (dotahuje [[isom-spec-before-render]]).
  Plný seznam (TOP 5 + tagy METHOD/GEN/REC/BENCH/ISOM/TOOL) v doku. ISOM fakta tam jsou ChatGPT-sourced →
  verify proti IOF spec před adopcí ([[external-ai-artifacts-verify-not-accept]]).
- **Vytěžek z druhého běhu ChatGPT (Sez. 165, `isom_scan/chatgpt_40min_aktivita1.pdf`).** Pipeline ≈ naše
  scan-mining (color masky + `connectedComponents` + kontaktní listy + template — už máme v `separate.py`/
  `points_common`/`black_brown_poc`/`gt_ui`). **Nové k převzetí:** (1) **circularity `4πA/P²` + convex-hull
  solidity** = geometrický diskriminátor kruhových bodů od fragmentů linií/srázů → **přesunuto do TODO** (řeší
  doložený balvany-vs-sráz FP); (2) **HoughCircles** (`dp=1, minDist=10, param2=18, r 4-10px`) na kroužkové
  symboly (417/419/109/526) = levná classic-CV alternativa k CenterNet pro scan-mining kandidáty (marginální vůči
  Png2Point, ale cheap). **Klíčový postřeh:** benchmark sken `task_isom_scan.png` = NÁŠ gen render (čisté barvy)
  → exact-RGB masky ChatGPTu fungují jen tam; na reálném použitém skenu drží naše nearest-color. ISOM/CV fakta
  verify před adopcí ([[external-ai-artifacts-verify-not-accept]]).
