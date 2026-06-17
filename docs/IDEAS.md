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

- **Png2Line — HOTOVÝ krok 1 + vektorizace (Sez. 130-132); detail v `architecture.md` UC5 + DONE.**
  Architektura A (model = jen segmentace, vektorizace = sdílený downstream krok) potvrzena funkční na
  watercourse 304/305 (test mIoU 0,774, reálný transfer completeness 0,85–0,93). **Otevřené větve** (v TODO):
  krok 2 dashed 508/516 JINÝM přístupem (přidání třídy zkoušeno a zavrženo Sez. 133 — doménový gap) + gap-bridging
  u junkcí + napojení poledníkového filtru do produkční cesty. Poledníkový detektor `north_grid.py` hotový +
  ověřen (Sez. 134, data-driven rozestup). *(Hotová implementace stažena z IDEAS Sez. 139 — žila tu jako changelog.)*
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
