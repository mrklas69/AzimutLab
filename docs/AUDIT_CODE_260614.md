# %AUDIT:CODE — AzimutLab — 2026-06-14

> **⚠ ARCHIV (Sez. 139).** Nálezy vypořádány v Sez. 125-127 (vč. MPP C1 → kanonické měřítko
> 1,33 Sez. 126). Řádkové reference do `docs/IDEAS.md` apod. míří do prořezaných docs (Sez. 127)
> → mohou neplatit. Historický artefakt; nejnovější audit kódu = `%AUDIT:CODE` commit `a1cc450` (Sez. 135).

Audit byl proveden pouze čtením a ověřovacími příkazy; produkční kód ani řídicí
dokumentace nebyly měněny. Rozsah: `connectors/`, `generator/`, `model/`,
aktuální řídicí dokumenty a lokálně dostupné artefakty v `resources/`.

## Souhrn

| Závažnost | Počet |
|---|---:|
| Kritické | 2 |
| Doporučené | 3 |
| Kosmetické | 2 |

Největší problém není architektonická velikost `generator.py`, ale porušená
jednotka fyzického rozlišení v celé tréninkové/evaluační trase reconstructorů.
Druhý kritický problém je destruktivní správa checkpointů při právě zaváděném
multi-seed měření.

## Kritické

### C1 — Tréninkové rastry mají 2,18 m/px, ale modelová pipeline je považuje za 1,33 m/px

**Stav:** potvrzeno kódem i reálnými artefakty.

Generátor odvozuje rastr z `MAP_SCALE = 10000` a `PX_PER_MM = 4.5855`
(`generator/generator.py:70-71,102-104`). Výsledné rozlišení je:

```text
10000 / (1000 × 4,5855) = 2,1808 m/px
```

Tuto hodnotu potvrzují `meta.json` v korpusu: kontrolovaných 20 párů má
`georef.pixel_size_m` přibližně 2,180–2,182. Například
`resources/livelox/1005002/gen/meta.json` uvádí `2.1805`.

Png2Area ale rastr pouze rozkrájí bez převzorkování
(`model/png2area/tile.py:103-122`) a metadata dlaždic fyzické rozlišení vůbec
nenesou (`model/png2area/tile.py:148-158`). Png2Point stejně načte
`gen_pointbase/rgb.png` a udělá přímý 512px crop
(`model/png2point/dataset.py:96-115`).

Následující vrstvy přitom tvrdí, že vstup má 1,33 m/px:

- `model/png2point/inject.py:37-42` z 1,33 m/px počítá velikost bodových symbolů;
- `model/purple.py:25-30` z 1,33 m/px počítá velikost fialového přetisku;
- `model/png2area/eval_real.py:37,217-224` převzorkuje reálný sken na 1,33 m/px;
- `model/png2point/eval_real.py:53,205-211` dělá totéž pro bodový model.

**Dopad:**

- reálný benchmark neběží ve fyzickém měřítku, na kterém byl model trénován;
- bodové symboly a fialový přetisk jsou na syntetickém podkladu přibližně
  `2,1808 / 1,33 = 1,64×` větší, než odpovídá kresbě podkladu;
- deklarované sim-to-real metriky směšují doménový rozdíl s rozdílem měřítka;
- `SIZE_JITTER = 20–25 %` nemůže systematickou chybu 64 % pokrýt;
- oba živé reconstructory sdílejí tutéž vadnou premisu.

**Návrh opravy:**

1. Zvolit jednu kanonickou hodnotu MPP jako SSoT.
2. Pokud zůstane cílem 1,33 m/px, převzorkovat celý pár X+Y před tilingem:
   RGB bilineárně, label rastr nearest-neighbor. Totéž provést pro
   `point_base` před cropem/injekcí.
3. Zapsat `source_mpp` a `target_mpp` do `_tiles.json` i checkpointu a při
   načtení vynutit guard proti mismatchi.
4. Rebuildnout datasety a oba živé modely přetrénovat; dosavadní syntetické i
   reálné metriky po opravě nejsou přímo srovnatelné.

### C2 — Každý experiment přepisuje kanonický checkpoint a může znehodnotit benchmark

**Stav:** potvrzeno kódem; lokální artefakty dokládají, že k tomu právě dochází.

Každý plný běh Png2Point zapisuje:

- průběh vždy do `history_full.csv` a `curve_full.png`
  (`model/png2point/train.py:280-315`);
- nejlepší průběžné váhy vždy přímo do `unet_best.pt`
  (`model/png2point/train.py:317-321`);
- po běhu znovu načte tentýž globální soubor
  (`model/png2point/train.py:323-330`).

Nové parametry `--seed` a `--ema` jsou určeny právě pro paralelní/sériové
experimenty (`model/png2point/train.py:350-357`), ale název výstupu seed, EMA,
decay ani čas běhu nerozlišuje. Checkpoint navíc tato metadata neukládá
(`model/png2point/train.py:319-320`).

V auditním snapshotu měl `resources/point_model/unet_best.pt` čas poslední změny
2026-06-14 14:23:02 a `history_full.csv` obsahoval jen tři epochy. Žádný Python
tréninkový proces neběžel. Ruční zálohy `unet_best_seed*.pt` existují, ale kód
jejich vznik ani návrat ke kanonickému modelu neřídí.

`model/png2point/eval_real.py:151-159` vždy bez volby načte právě
`resources/point_model/unet_best.pt`. Přerušený nebo slabý experiment tedy
okamžitě a tiše změní „produkční“ reálný benchmark.

**Dopad:**

- ztráta dříve nejlepšího modelu bez explicitního rozhodnutí;
- multi-seed výsledky nejsou reprodukovatelně přiřaditelné k vahám;
- reálný benchmark může měřit jiný checkpoint než syntetická metrika;
- stav souborů závisí na pořadí a případném přerušení experimentů.

**Návrh opravy:**

1. Každý běh ukládat do vlastního adresáře nebo pod `run_id`, například
   `seed-2_ema-0.998_20260614T1420/`.
2. Do checkpointu uložit seed, EMA/decay, threshold, test metriku, epochu a
   fingerprint dat/splitu.
3. Kanonický `unet_best.pt` měnit jen explicitním krokem `promote`, až po
   výběru schváleného běhu.
4. Zápis checkpointu provádět přes dočasný soubor a atomický rename.

Stejný globální vzor používají i `model/png2area/train.py:243-252` a archivní
`model/runnability/train.py:233-242`; akutní je nyní Png2Point kvůli aktivnímu
multi-seed/EMA měření.

## Doporučené

### D1 — Reálný Png2Point benchmark tiskne nesouvisející hardcoded syntetické skóre

`model/png2point/eval_real.py:255` vždy vypíše:

```text
vs syntetická 0,897
```

Současně načítá libovolný aktuální `unet_best.pt` (`:151-159`). Hodnota 0,897
patří historickému nedeterministickému běhu; aktuální diagnostika v
`docs/IDEAS.md:528-545` ji označuje za outlier a uvádí baseline seedů
0,151/0,247/0,318. Výstup benchmarku proto prezentuje jako dvojici dvě metriky
z různých modelů.

**Návrh opravy:** odstranit hardcoded číslo. Syntetickou test metriku načíst z
metadata stejného checkpointu, případně ji před reálným benchmarkem znovu
spočítat. Výstup musí uvést identitu checkpointu, seed, EMA a epochu.

### D2 — Oba reálné eval skripty selžou na čistém checkoutu bez `temp/`

`temp/` je gitignored a není verzované. Skripty nastaví `_OUT = repo/temp`
(`model/png2area/eval_real.py:38`, `model/png2point/eval_real.py:54`), ale před
ukládáním výstupů adresář nevytvoří
(`model/png2area/eval_real.py:220-234`,
`model/png2point/eval_real.py:258`).

**Dopad:** fresh clone nebo ruční úklid `temp/` skončí `FileNotFoundError` až po
drahé inferenci.

**Návrh opravy:** na začátku `main()` volat
`_OUT.mkdir(parents=True, exist_ok=True)`; ideálně sdílet malý helper obou
izomorfních benchmarků.

### D3 — `.omap` clipper interpretuje chybu formátu jako úspěšný no-op

`generator/cut.py` používá úzký regex vyžadující přesný tvar
`<objects count="N">` (`:220`). Když blok nenajde, `clip_omap()` tiše vrátí
`(0, 0)` (`:273-277`) a soubor ponechá neoříznutý. Při nečíselném coord tokenu
parser token pouze zahodí (`:231-237`); objekt bez úspěšně načtených souřadnic
se považuje za korektně ponechaný (`:282-285`).

To odporuje projektovému pravidlu „no silent fallback“ a
verify-against-source: změna XML serializace nebo poškozený objekt se může
tvářit jako úspěšný ořez.

**Návrh opravy:** chybějící `<objects>`, neplatný coord token a mapový objekt bez
validních coords mají vyhodit výjimku s cestou a identifikací objektu. Pokud
existuje legitimní bezsouřadnicový typ, povolit jej explicitním allowlistem.

## Kosmetické

### K1 — `purple.py` generuje o jednu kontrolu méně, než deklaruje

`n_ctrl` je komentován jako 5–12 kontrol (`model/purple.py:110`), ale vytvoří se
jen `n_ctrl + 1` bodů (`:116-118`) a kontroly jsou `pts[1:-1]` (`:129-131`).
První bod je start a poslední cíl, takže skutečný počet kontrol je 4–11.

**Návrh opravy:** pro 5–12 kontrol vytvořit `n_ctrl + 2` bodů, nebo proměnnou a
komentář přejmenovat podle skutečné sémantiky.

### K2 — Úvodní dokumentace `cut.py` popisuje již odstraněnou centroidovou implementaci

Docstring stále říká, že se objekty ořezávají centroidem a geometrický ořez je
„zatím NEimplementován“ (`generator/cut.py:7-16`). Ve stejném souboru je přitom
hotový geometrický orchestrátor `clip_omap()` (`:263-327`) a wrapper jej používá
(`:354-364`).

**Návrh opravy:** přepsat úvod podle současného geometrického řešení a odstranit
historický plán. Historie už patří do `DONE.md`/diary, ne do aktivního
docstringu.

## Ověření auditu

- `python -m compileall connectors generator model` prošel bez chyby.
- Ruff ani jiné lint/test nástroje nejsou v prostředí nainstalované.
- Nebyly nalezeny nové tracked záložní/prázdné Python soubory; archivní
  `model/runnability/` je označen záměrně.
- Existující známé položky z Fable5 auditu (zejména chybějící automatické testy
  a stringová editace `.omap`) nejsou znovu vydávány za nové nálezy; D3 je
  konkrétní nově potvrzené selhání v této implementaci.
