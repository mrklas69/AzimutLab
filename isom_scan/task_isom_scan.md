# Test: rozpoznání ISOM symbolů ze skenu OB mapy

## Účel
Změřit, jak dobře dokáže (vision) model **ze skenu mapy orientačního běhu** rozpoznat,
klasifikovat a lokalizovat co nejvíce **ISOM symbolů** — bez doučení, jen ze spec a barevné
palety. Slouží jako baseline „co zvládne hotový model přímo na skenu".

## Vstup
- **`task_isom_scan.png`** — sken OB mapy, **1655 × 1868 px** (RGB).
  - Provenance: ořez mapového pole reálné mapy *Okruhy / Branžež* (Český ráj, 2.–4. 6. 2026),
    Livelox `classId 1127443`. Titulek, loga, QR a legenda odříznuty — zůstalo jen mapové pole.
  - Měřítko originálu **1 : 10 000**, ekvidistance **5 m**, autor SW **OCAD 2020** (→ ISOM **2017-2**).
  - Rozlišení skenu cca **0,89 mm/px** v terénu (zmenšeno oproti nativnímu).

## Reference (přiloženo)
- **`isom-2000-spec.pdf`** — definice a vzhled symbolů. ⚠ **Je to ISOM 2000**, mapa je
  **ISOM 2017-2**. Pro *vzhled* symbolů jsou obě verze prakticky shodné; liší se ale **číslování**
  (a OCAD navíc používá vlastní sadu kódů 535–540 pro umělé body tam, kde OOM dává 524–531).
  → **Reportuj v kanonických kódech ISOM 2017-2 a VŽDY uveď i anglický název symbolu** — název je
  jednoznačný napříč číslovacími sadami, kód sám ne.
- **`iof-printing-colour-2022.pdf`** — normovaná barevná paleta ISOM (CMYK/RGB) + pořadí tisku
  (color order). Barva je silný klasifikační klíč (hnědá = terén, modrá = voda, zelená = porost,
  černá = umělé/skály/cesty, žlutá = otevřená plocha, olivová = zákaz vstupu).

## Úkol
Najdi v `task_isom_scan.png` **všechny ISOM symboly, které dokážeš rozpoznat**, a vrať je v tabulce
níže. Cílem je maximální pokrytí *při zachování přesnosti* — viz pravidla.

## Souřadný systém
- Pixelové souřadnice nad `task_isom_scan.png`.
- **Origin = levý horní roh**, osa **+X vpravo**, osa **+Y dolů**, jednotka **px** (celé číslo).
- Rozsah: X ∈ ⟨0; 1655⟩, Y ∈ ⟨0; 1868⟩.
- Pro přenositelnost uváděj i **normalizované** souřadnice (xn = x/1655, yn = y/1868), zaokrouhleno
  na 3 desetinná místa.

## Výstupní formát

### A) Strojový výstup — JSON (POVINNÉ)
Vrať **jeden** blok ```` ```json ```` s tímto schématem. Toto je hodnocený výstup —
skóruje ho `score.py`, tak dodrž schéma přesně (nepřidávej komentáře dovnitř JSON):

```json
{
  "detections": [
    {
      "code": "204",
      "name": "Boulder",
      "geom": "point",
      "count": 12,
      "confidence": 0.9,
      "points": [{"x": 340, "y": 910}, {"x": 512, "y": 1203}],
      "note": ""
    }
  ]
}
```
- `code` — kanonický ISOM 2017-2 kód (string: `"204"`, `"301"`, `"527"`).
- `name` — oficiální EN název ze spec (`"Boulder"`, `"Marsh"`, …) — jednoznačný i napříč číslováním.
- `geom` — `"point"` | `"line"` | `"area"`.
- `count` — počet výskytů (objektů) daného symbolu.
- `confidence` — 0–1, tvoje jistota klasifikací (nejistý kód < 0,5, viz Pravidla).
- `points` — souřadnice dle pravidla granularity níže (px, origin levý-horní).
- `note` — volitelná poznámka (nejistota, záměna, …); prázdný string když nic.

### B) Lidská tabulka (volitelné, pro čtení)
Stejná data jako tabulka — jen pro člověka, nehodnotí se:

| ISOM kód | Název (EN) | Geom | Četnost | Výskyty |
|---|---|---|---|---|

## Pravidlo granularity (Výskyty)
- **Bodové symboly** (2xx balvany/skály, 4xx body zeleně, 5xx umělé body, …): vyjmenuj
  souřadnice **každého výskytu** jako `(x, y | xn, yn)`, oddělené `;`.
- **Plochy a linie** (vrstevnice, voda, zeleň, cesty, srázy, …): uveď **jen četnost** + **2–3
  reprezentativní body** (např. centroidy největších instancí) jako orientaci, ne úplný výčet.

## Pravidla
- **Klasifikuj podle vzhledu + barvy + spec, ne podle dohadu.** Když si symbolem nejsi jist, uveď
  nejbližší kód a **explicitně to označ** (`?` za kódem + krátká pozn.). **Nehádej tiše** —
  nejistota patří do výstupu, ne zametená pod koberec.
- **Nepřiřazuj kód, který v mapě nevidíš**, jen proto, že „v lese bývá".
- Pokud dvě verze číslování kolidují (524–531 vs 535–540), rozhoduje **anglický název** + vzhled.

## Skórování (vyhodnocení)
Vektorová ground-truth (zdrojový `.omap`) pro tento sken **neexistuje** — k dispozici je jen sken.
Vyhodnocení proto stojí na dvou pilířích:

1. **Expertní oko (primární).** Mapu posuzuje OB kartograf (autorita věrnosti). Per třída se hodnotí
   hrubě **precision / recall**: kolik z reportovaných výskytů je reálných (P) a kolik reálných
   výskytů model zachytil (R). Souhrn = pokrytí tříd × kvalita lokalizace.
2. **Hrubá automatická kotva (doplněk).** `resources/livelox/1127443/gt_labels.png` nese runnability
   segmentaci (les / otevřeno / voda — viz `connectors/map_gt.py`). Slouží jako sanity-check
   plošných tříd (zeleň 4xx, otevřeno 401/403, voda 301): hrubě sedí pokrytí ploch reportu
   s touto maskou? Není to per-symbol GT, jen mantinel pro velké plochy.

> Pozn.: kotva i sken pochází z `resources/livelox/1127443/` (gitignored korpus) — pro běh testu
> stačí `task_isom_scan.png` + obě PDF v této složce; kotva je jen pro vyhodnocovatele.

---
*Výstup vlož pod tuto čáru.*
