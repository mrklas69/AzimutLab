# ROADMAP — AzimutLab

> **Účel souboru.** Projekt je náročný, má mnoho sezení. Občas se stane, že se LLM (nebo
> i člověk) ztratí a začne pracovat na úkolech, které sice do projektu patří, ale mají
> **úplně jiné načasování**. Tenhle soubor je průvodce etapami — drží **tah na branku**.
>
> **Čte se na začátku každého sezení** (`%BEGIN`, krok 0.5 — viz `docs/PROMPTS.md`).

---

## Cíl projektu

**Reálný sken mapy → vektorové podklady mapového editoru OMAP/OCAD** (ISOM bodové, liniové
a plošné symboly).

Vstupní sken je „v divočině": nekvalitní fotka mobilem, **použitá** mapa (deformovaná,
znečištěná), navíc s **fialovým přetiskem** trasy závodu, ražení, občerstvovaček.
Výstup je čistá vektorová `.omap`/`.ocd` mapa.

## Resources (a proč je jich málo)

- **~6 OMAP** — na začátku máme jen ~3 kvalitní vektorové mapy (OCAD), navíc jen ze **dvou
  lokalit**. To je strašně málo.
- **Stovky PNG** — skeny reálných map jdou získat z internetu (Livelox).

Pro trénink kvalitních modelů je třeba **neomezené množství dlaždicových párů 512×512
`[PNG, OMAP]`**. Jak takový tréninkový set získat? → dvě etapy.

---

## Dvě etapy (a tvrdá fázová závora mezi nimi)

### Etapa 1 — `Generator()`
Generuje **pseudoorientační mapy** (orienťácké), které vypadají jako produkty skutečných
mapařů, a slouží k získání tréninkového setu.

Vstupní podklady jsou pestré — od **reálných a spolehlivých** (ZABAGED, DMR 5G) až po
**zcela fiktivní**, náhodně rozmístěné na obvyklých krajinných místech podle statistické
četnosti. **Nejužitečnější zdroj ISOM symbolů = vytěžování skenů map skutečných mapařů
z Liveloxu** — chce se naučit rozpoznat co nejvíc ISOM symbolů, ať si je nemusíme vymýšlet.

**Scan mining patří do této etapy.** Pokud práce ze skenu získává lokální paletu, separované
barevné vrstvy, black-vs-brown masky, kandidáty symbolů, měřicí GT nebo kalibrační signály pro
KOMPAS, je to přímé vytěžení pro `Generator()`. Zakázaná je až práce, která ladí cílový produkt
`sken → .omap` bez vazby na pokrytí/KOMPAS.

- **(g1) V této etapě nemá smysl podklady (skeny PNG) nijak degradovat — usilujeme o MAX
  VYTĚŽENÍ.** *(Opakovaná chyba LLM — viz „Antidrift" níže.)*
- **(g2) Měření etapy: KPI + KOMPAS.**
  - **KPI** = kolik ISOM symbolů z celkového setu umíme v generátoru věrohodně generovat.
  - **KOMPAS** = tabulka ISOM symbolů členěná: `point/line/area · isom_code · zdroj ·
    věrohodnost · provedení`.

### Etapa 2 — `Rekonstruktor()`
**Cílový produkt projektu**: ze skenu PNG získáváme `.omap`. (Tady patří degradace skenu
jako tréninková augmentace, dewarping, de-purple, čtení deformovaných map.)

### ⛔ Fázová závora
**Exit-kritérium (operacionalizováno Sez. 182 = rozhodnutí uživatele po auditu 260702-A1; nahrazuje
dřívější číselný práh „KPI ≥ 85 %"):** do Etapy 2 se smí, až má **každá díra KOMPASu verdikt** —
buď stav `ok`, nebo **doložený data-gate strop** (`DATA_GATE_CEILING` v `measure_dod.py`; zápis
vyžaduje ověřenou příčinu, ne dojem — disciplína „108" ze Sez. 178). Práh 85 % byl stanoven před
poznáním data-gate stropu a sankcionovanými prostředky je nedosažitelný: ČÚZK páka vyčerpaná
(potvrzeno 4×), zbývající symbolová hmota existuje jen v mapařských skenech (doklad Sez. 177 +
audit 260702). KPI zůstává jediným headline číslem — kompas děr, ne cílová funkce.

**Scan-mining (ruční GT uživatele) je paralelní trať, ne zátka závory** — krmí pokrytí teď i GT
potřeby Etapy 2, ale její tempo fázi neblokuje (Sez. 182).

Jsme v **Etapě 1 (`Generator()`)**. Proto:

> **`Rekonstruktor()` a „degradace" jsou ZATÍM ZAKÁZANÁ SLOVA.**
> *(Rozhodnutí uživatele, 2026-06-17.)*

Veškerá energie jde do **vytěžení** (rozšiřování pokrytí ISOM symbolů) a do **KOMPASu**,
ne do ladění modelů ani do degradace/augmentace podkladů.

---

## Antidrift — jak udržet „tah na branku"

Mechanismy proti opakovanému sklouznutí k práci se špatným načasováním:

1. **`%BEGIN` čte tento soubor** (krok 0.5, hned po git sync) — etapa a zákazy jsou
   v hlavě od první minuty sezení.
2. **Self-check před každým návrhem fokusu** — polož otázku:
   > „Je tohle **max vytěžení / plnění KOMPASu**, nebo **degradace / leštění modelu /
   > rekonstruktor**?"
   Pokud druhé → **STOP**, je to špatná etapa (viz fázová závora). Pozor na falešně
   pozitivní stopku: `scan mining` je v pořádku, když výstup krmí `Generator()`/KOMPAS.
3. **„Tah na branku" = rozšiřovat POKRYTÍ** (nové TYPY ISOM symbolů v generátoru), ne
   doladit už pokrytý symbol o procenta. Co generátor nenakreslí, rekonstruktor se nikdy
   nenaučí — pokrytí je strop (viz paměť `generator-coverage-is-the-ceiling`).
4. **KOMPAS je živá tabulka, ne archiv.** Slouží jako SSoT „co už umíme / co zbývá
   vytěžit". Bez ní energie uteče k leštění. Měří `generator/measure_dod.py --table`.

### Historie sklouznutí (ať se vidí, že to je vzorec)
Návrhy degradace/augmentace/rekonstruktor práce ve špatné fázi se opakovaly ~6×. Poslední:
Sez. 136 — sezení začalo návrhem geometrické augmentace (warp) + „degrade-lite" experimentu,
než ho uživatel otočil na vytěžení (pseudo body 417/419). Tento soubor vznikl jako pojistka.
