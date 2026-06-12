# KB — ISOM colour order (z-order / printing order)

Pořadí barev (= z-order při renderu) pro ISOM mapy. Rozhoduje, co překryje co, když se
dva symboly geometricky kříží. Cílová sémantika generátoru je **ISOM 2017-2**
([[isom-issprom]]); reálné vzorové mapy jsou většinou **ISOM 2000** (jiné pořadí — viz Q4).

**Zdroj:** IOF *Map Specifications — Printing and Colour Definitions* (únor 2022, dříve „ISOM
2017 Appendix 1"), kap. 7 „Colour order", tabulka str. 6. ISOM 2017-2 §2.7 barvy na tento
dokument deleguje. Lokální kopie: `iof-printing-colour-2022.pdf` (oficiální orienteering.sport
vrací 403 → lokální mirror z orienteering.sk). Cross-check proti plné tabulce IOF MC v issue
`OpenOrienteering/mapper#1966` (verze 2021, v relevantních řádcích shodná). Ověřeno Sez. 118.

## Oficiální ISOM 2017-2 colour order (navrch → vespod)

Řádky se ✓ ve sloupci ISOM 2017-2 (číslování naše; plná tabulka má i ISSprOM/ISSkiOM/ISMTBOM):

| # | Colour name | CMYK | pozn. |
|---|-------------|------|-------|
| 1 | Upper purple for course overprint | 35/85/0/0 | |
| 2 | White for course overprint | 0/0/0/0 | |
| 3 | White for railroad | 0/0/0/0 | |
| 4 | **Black 100%** | 0/0/0/100 | skály, kameny, ploty, **břehová linie 301** |
| 5 | Blue 100% point symbols | 100/0/0/0 | |
| 6 | Brown 100% point symbols | 0/56/100/18 | |
| 7 | Green 100% point symbols | 76/0/91/0 | |
| 8 | **Blue 100% line symbols** | 100/0/0/0 | **toky 304/305** |
| 9 | Dark green line symbols | 100/0/80/30 | |
| 10 | **Brown 100% line symbols** | 0/56/100/18 | **vrstevnice 101/102/103, sráz 104** |
| 11 | Lower purple for course overprint | 35/85/0/0 | |
| 12 | Brown 50% for road infill | 0/28/50/9 | |
| 13 | Black 100% for road outline | 0/0/0/100 | |
| 14 | Black 50% for large buildings and tramway | 0/0/0/50 | |
| 15 | Black 20% for canopy | 0/0/0/20 | |
| 16 | **Blue 100% area symbols** | 100/0/0/0 | **vodní plocha 301** |
| 17 | Blue 70% area symbols | 70/0/0/0 | |
| 18 | Blue 50% area symbols | 50/0/0/0 | |
| 19 | White over green and brown | 0/0/0/0 | |
| 20 | Brown 50% for paved area | 0/28/50/9 | |
| 21 | Yellow 100% + Green 50% | 38/27/100/0 | |
| 22 | Green 100% area symbols | 76/0/91/0 | |
| 23 | Green 60% area symbols | 46/0/55/0 | |
| 24 | Green 30% area symbols | 24/0/27/0 | |
| 25 | Black 30% area symbols | 0/0/0/30 | |
| 26 | White over Yellow | 0/0/0/0 | |
| 27 | Black for cultivated land and sandy ground | 0/0/0/100 | |
| 28 | Yellow 100% area symbols | 0/27/79/0 | |
| 29 | Yellow 75% area symbols | 0/20/59/0 | |
| 30 | Yellow 50% area symbols | 0/14/40/0 | |

## Klíčové relace (pro generátor)

- **Modrá vodní plocha (#16) je POD hnědou vrstevnicí (#10).** Vrstevnice kreslená přes vodní
  plochu by se VYTISKLA NAVRCH. Že reálné mapy nemají vrstevnice v jezerech je proto **geometrie**
  (kartograf je tam nekreslí), **NE color order** → z-order to nikdy nevyřeší, řešení je **clip**.
- **Černá 100% (#4) je NAD modrou plochou** → břehová linie 301 (černá) se kreslí přes vodní výplň
  (správně). I nižší černá „road outline" (#13) je nad modrou plochou.
- **Modré linie (toky, #8) jsou NAD hnědými vrstevnicemi (#10) i nad modrou plochou (#16)** → potok
  se kreslí přes vrstevnice i přes hladinu (správně, neclipovat).

## ISOM 2000 se LIŠÍ

ISOM 2000 (`isom-2000-spec.pdf`, §3.5.1 str. 5): spot tisk, JEDNA modrá deska pro vše; pořadí tisku
**yellow → green → grey → brown → blue → black → purple** (pozdější = navrch) → modrá (vč. ploch)
tiskne NAD hnědou. ALE spot inkousty se overprintují (§ Overprinting, str. 7: doporučen pro 100 %
Violet/Black/Brown/Blue/Green) → hnědá vrstevnice pod modrou plochou **prosvítá jako smíšená barva**,
není vykousnutá. ISOM 2017-2 v CMYK (neprůhledné vrstvy) tutéž čitelnost simuluje **rozdělením modré**:
linie nad hnědou (#8), plochy pod hnědou (#16).

## OOM template vs IOF (issue #1966)

V jádru (modrá plocha pod hnědou) se náš `generator/template_classic.omap` s IOF **shoduje**
(`Blue 100% for area features` priority 15 pod `Brown 100%` priority 6 = IOF-věrné). Známá odchylka
OOM od IOF je jen v HORNÍ části tabulky (OOM: Black > Green 100% > White railway > Blue 100% > Brown
100%; IOF: White railroad > Black > Blue pt > Brown pt > Green pt > Blue line > Brown line). Pro náš
problém vrstevnice-vs-voda je template správný — vada je geometrická, ne v paletě.

## Důsledky pro generátor (Sez. 118)

Tahle reference vyvrátila původní návrh „vrstevnice přes vodu schovat z-orderem (modrá nad hnědou)"
— IOF má pořadí opačné. Důsledky propsané do kódu/TODO:

1. **`CLAUDE.md` princip „Voda = no-draw zóna"** — vrstevnice (i terénní/vegetační/pseudo prvky) se
   přes vodu vyříznou GEOMETRICKY (clip), ne paletou. Výjimka jen prvky legitimně nad vodou z tvrdých
   dat: **břehová linie 301, toky 304/305, most/lávka 512, hráz**.
2. **TODO (Sez. 118)** — související úkoly: „vrstevnice přes vodu = CLIP", „416 přes vodu", „DRY
   konsolidace off-water filtr" (vrstevnice = 4. konzument). Viz `docs/TODO.md` blok UC4-I/UC5.

## Citace

- IOF *Map Specifications — Printing and Colour Definitions*, Feb 2022, kap. 7 (str. 6 tabulka),
  kap. 5 (purple pod black/brown/blue 100%). Lokálně `iof-printing-colour-2022.pdf`.
- ISOM 2017-2 §2.7 (deleguje barvy na výše uvedený Appendix).
- ISOM 2000, §3.5.1 / §3.5.2 + Overprinting (`isom-2000-spec.pdf`, str. 5 + 7).
- `OpenOrienteering/mapper#1966` — colour order odchylky OOM vs IOF.
