# AUDIT_SUPERVISOR — 2026-06-12 (1. vydání)

**Auditor:** Claude Fable 5 · **Rozsah:** celý projekt AzimutLab (docs + kód + proces,
Sez. 1–116) · **Metoda:** dle `docs/AUDIT_SUPERVISOR_PROMPT.md` — řídící docs přečteny celé,
stav kódu ověřen průzkumem zdrojů (rozsahy, testy, metriky, degradace, SSoT), nálezy
dokládány sezeními/soubory. **Publikum:** Opus 4.8, ChatGPT 5.5 a další modely pracující
na projektu; rozhodující článek = uživatel.

---

## TL;DR

Projekt má výjimečnou procesní disciplínu (measure-first, no silent fallback, diáře,
Censure) a poctivě archivované slepé uličky — to je nadprůměr a nesmí se rozbít.
Tři nejzávažnější námitky míří jinam: **(A1) doménový gap syntetika→reálný sken se
vůbec neměří** — oba „funkční" reconstructory (mIoU 0,568 / mF1 0,897) jsou změřeny
výhradně na vlastní syntetice, přitom vrcholová úloha žije celá v reálné doméně;
**(A2) fialový přetisk a geometrické poškození neexistují nikde v tréninkové cestě**,
ačkoli zadání vrcholu je „sken POUŽITÉ mapy"; **(A3) KPI je počty objektů, ne
kartografická věrnost, a generátor se na něj začal kalibrovat** — Goodhartovo riziko
je už doložené z diářů. K tomu architektonické docs ~37 sezení zaostávají za reálným
směrem (odklad A1-revize ze Sez. 79) — sám zadavatel tohoto auditu označil rekonstrukci
sken→vektor jako „UC3", zatímco docs ji vedou jako UC4-III. Nic z toho není fatální;
všechno je opravitelné levně, pokud se to udělá teď.

---

## A. Námitky

### A1 — Doménový gap se neměří; obě hlavní metriky jsou in-domain syntetika — KRITICKÁ

**Doklad:** `model/png2area/` trénuje i testuje na párech [gen render `rgb.png`,
`area_labels.png` z vlastní `.omap`] (pairs.py); `model/png2point/` měří F1 na
**injektovaných** ikonkách na `point_base` renderu (přiznáno v diáři Sez. 106: „F1 =
injekce na point_base, ne reálné skeny"). Průzkum kódu nenašel jediné vyhodnocení na
reálném skenu. TODO to vede jen jako vedlejší bod pro Png2Point („reálný transfer,
doménový gap"), pro Png2Area neexistuje vůbec.

**Dopad:** mIoU 0,568 a mF1 0,897 jsou horní odhady; o úloze, kvůli které projekt
existuje (čtení reálné mapy), zatím nevypovídají nic. Hrozí měsíce optimalizace
feederu (KPI, pokrytí), jejichž přínos pro reálnou doménu nikdo nezměřil — tj. přesně
ta past, kterou projekt už jednou zažil (ortofoto→runnability, strop odhalen až
tréninkem, Sez. 78–79).

**Doporučení:** Postavit **reálný benchmark hned**, levně: (a) 5 map v `resources/`
má sken + kartografovu `.omap` + crosswalk `.crt` → rasterizovat kartografovy plochy
přes `omap_raster` = reálné Y, sken = reálné X; (b) pustit `unet_best.pt` na 2–3
Livelox skeny a vizuálně + číselně srovnat se separační GT. Reportovat **dvojici
čísel (syntetika / realita)** při každém dalším tréninku — domain gap se stane druhým
KPI. Teprve gap rozhodne, kam investovat (degradace? pokrytí? architektura?).

### A2 — Fialový přetisk a geometrická degradace chybí v celé tréninkové cestě — VYSOKÁ

**Doklad:** `generator/degrade.py` = 5 čistě fotometrických vrstev (CMYK misregistrace
/ blur / papír / šum / JPEG). Fialová (704/705) existuje jen jako **ignore** v GT
(`map_gt.py`, label 255) — žádný kód ji nikde **nekreslí** do X. Geometrická půlka
augmentace (sklad/ohyb/warp) je otevřené TODO od Sez. 86. IDEAS ji zmiňují (ř. 339
„fialový overprint, odřeniny"), ale není to trackovaná položka s prioritou.

**Dopad:** Vrcholová úloha je definovaná jako sken **použité** mapy: fialový přetisk,
ohyby, špína. Model, který fialovou nikdy neviděl jako vstupní šum, na ní bude
halucinovat — a přitom UC3 (de-purple) je v IDEAS veden jako nejlevnější aplikace.
Augmentace přetiskem je triviální: nakreslit náhodnou trať (start trojúhelník, kolečka,
spojnice, čísla) ISOM purpurou do X on-the-fly v `dataset.py._augment`; Y se nemění.
Stejný vzor jako degrade — a injekční know-how (`inject.py`) už existuje.

**Doporučení:** Zapsat do TODO jako [!] hned po Png2Area re-tréninku (301-voda):
(1) purple-course augmentace do `_augment`; (2) geometrická augmentace (fold/warp)
na úrovni dlaždice (transformuje X i Y, vedle D4 — přesně jak TODO samo říká).
Pořadí ověřit proti A1: benchmark může ukázat, že fialová je menší problém než např.
ostrost — proto nejdřív měřit.

### A3 — KPI = histogram počtů objektů; Goodhart už začal — VYSOKÁ

**Doklad:** KPI (Sez. 100) = histogram intersection **podílů počtů objektů** per ISOM
kód. Diáře samy dokládají citlivost na hru s granularitou (508: rozsekání kusů =
+0,59 pb „gaming", Sez. 102; 416 zavedeno s délkovým prahem laděným na KPI, Sez. 101)
a pseudo vrstvy 204/210 se **kalibrují na share** přímo proti referenčním mapám
(Sez. 107). Reference = 5 map (na ntbhej jen 2) — výkyvy ±6,7 pb na jediný mechanismus
(Sez. 115–116) ukazují malé n. KPI nevidí polohu, tvar ani vzhled symbolu.

**Dopad:** Jakmile se generátor kalibruje na metriku, metrika přestává být nezávislým
měřítkem. KPI růst (43→59→55 %) je legitimní kompas děr v pokrytí, ale **není** důkaz,
že páry lépe trénují reconstructor — to může doložit jen A1 benchmark. Riziko: další
sezení budou honit pb místo věrnosti (přesně to, co uživatel u Sez. 100 chtěl zastavit —
„utápění v metodologii" — se může vrátit v nové podobě).

**Doporučení:** (1) KPI ponechat jako kompas, ale **úspěch fáze vázat na A1 benchmark**
(reconstructor na reálném skenu), ne na KPI samotné. (2) Rozšířit referenční sadu KPI — pozor,
KPI potřebuje **vektorovou** `.omap` (počty objektů); Livelox je raster-only a jako
reference sloužit nemůže (oprava prvotní formulace auditu). Rozšíření = získat další
kartografické `.omap` (sbírka `resources/`, kluby), i 3–5 map znatelně sníží rozptyl. (3) Po-symbolová prostorová metrika existuje
v zárodku (`compare_real_vs_gen.py`, STAT 1/2) a byla Sez. 69 odstavena jako stale —
zvážit oživení per-symbol rastr IoU na matched výseku jako druhý, negamovatelný pohled.

### A4 — Architektonické docs ~37 sezení za realitou (odklad A1-revize ze Sez. 79) — VYSOKÁ

**Doklad:** `docs/architecture.md` stále vede UC5 jako „palette separation, klasifikace
symbolů", UC3 jako nejlevnější aplikaci a reconstructor jen jako reframe-poznámku;
„Plná revize UC3 / UC4-III / fázový plán / Pic2Omap absorpce odložena (A1)" visí od
Sez. 79. Mezitím reconstructor() + generator() **jsou** hlavní osa projektu (2 funkční
modely, KPI fáze). Nejsilnější doklad driftu: **sám uživatel v zadání tohoto auditu
popsal rekonstrukci sken→vektor jako „UC3"**, zatímco docs ji vedou jako UC4-III /
Pic2Omap — taxonomie UC už neodpovídá mentálnímu modelu vlastníka projektu.

**Dopad:** Porušení vlastní zásady Conceptual Integrity + SLAP („žádná vrstva nesmí
zůstat na starší abstrakci"). Každý nový model/agent, který si přečte architecture.md,
dostane zkreslený obraz hlavního tahu — a %BEGIN ji čte každé sezení.

**Doporučení:** Jedno docs-only sezení na ntbhej (nepotřebuje CUDA ani korpus):
překreslit DAG kolem osy generator() → reconstructor (Png2Area/Point/Line) → aplikace
(de-purple, Pic2Omap), vyjasnit vztah UC3↔UC4-III↔reconstructor (sloučit, nebo
přečíslovat), propsat do README/GLOSSARY/IDEAS. Levné, dávno zralé.

### A5 — 13,5k LOC bez jediného automatizovaného testu — STŘEDNÍ (roste)

**Doklad:** Průzkum: žádné `tests/`, pytest ani assert-golden skripty. Verifikace
= ruční rituály opakované v sezeních (noise proc 65 byte-identický, golden Šulcák
48/2,56 ha, py_compile 7/7). Bug 301 vs 301.1 žil ~8 dní a dva plné tréninky, protože
žádný invariant nepropojil kódy generátoru s `omap_raster` (Sez. 110; dnes SSoT fix).

**Dopad:** Ruční golden checky fungují, ale platí se za ně při každém sezení znovu
a chrání jen to, na co si model vzpomene. Další 301-typ bugu je otázka času — kód
roste (~+700 LOC mezi audity kódu) a monolitové globály zvyšují vazby.

**Doporučení:** Ne plná test suite (over-engineering proti fázi B) — **5 invariantních
smoke testů** v jednom souboru: (1) noise-mode checksum (proc 65); (2) golden Šulcák
počty/ha; (3) `AREA_ZORDER` ⊆ symboly v template + shoda s kódy, které `omap_export`
zapisuje; (4) `build_pair` na mini fixture → Y obsahuje nenulové pixely pro každý kód
přítomný v `.omap`; (5) cut primitiva mini-verify (už existují ad-hoc, Sez. 114 —
jen je zachovat). Přesně ty kontroly, které se dnes dělají ručně — automatizace je
levnější než jediné jejich ruční opakování.

### A6 — Reprodukovatelnost vázaná na jeden stroj a gitignored artefakty — STŘEDNÍ

**Doklad:** `_curation.json` (ruční vizuální tagy Sez. 71!) a `_split.json` žijí jen
na HAL3000 (TODO Sez. 110-111: na ntbhej NEJSOU); `Velbloud.pgw` chybí na ntbhej →
KPI na skalnaté mapě neměřitelné (carry přes 3 sezení); korpus se na druhém stroji
stahoval znovu (57→264) a hrozí rozjetí kurace.

**Dopad:** Ztráta HAL3000 disku = ztráta ručních tagů (neopakovatelná lidská práce)
a tréninkového splitu → neporovnatelnost všech dosavadních mIoU. Bus factor 1 stroj.

**Doporučení:** Kurace/split/`.pgw` jsou malé textové soubory **bez copyright obsahu**
— commitnout je (případně do privátní větve), nebo aspoň pravidelná záloha mimo
HAL3000. Do `%END` přidat krok „měřicí artefakty zálohovány?".

### A7 — Png2Line: poslední a nejtěžší enabler nemá ani %THINK — STŘEDNÍ

**Doklad:** 61 % hmoty symbolů = linie+body (Sez. 100); body hotové, linie „neexistuje,
nejtěžší" (TODO, IDEAS ř. 392 — „vektorizace linií = otevřený problém"). Žádný průzkum
metod (skeletonizace vs detekce vs polygon-RNN vs segment-then-trace) zatím neproběhl.

**Dopad:** Cíl ≥ 85 % KPI bez Png2Line nelze splnit; je to kritická cesta. Riziko, že
se výzkumná nejistota odhalí pozdě (analogie: 204 root-cause stál 2 sezení; linie budou
těžší).

**Doporučení:** Zařadit %THINK + rešerši brzy (ntbhej-friendly, bez CUDA): jak dělá
rastr→vektor linií zbytek branže (cartographic line extraction, deep vectorization,
HRNet/segmentace+skeleton, Pic2Omap zkušenost). Ověřit, zda injekční trik (Sez. 105)
přenese — paměť `png2point-inject-clean-base` tvrdí, že ano; doložit probou dřív, než
se na tom postaví plán.

---

## B. Připomínky

**B1 — `generator.py` 4 340 ř., 6 globálů (GW/GH/W/H/TILE_M/WORLD_W_M), ~130 výskytů.**
Rozhodnutí „split až bolí / fáze A" (Sez. 50) respektuji — ale všimněte si, že nové
funkce už monolit obcházejí (`cut.py`, `gen_backgrounds.py` jako string post-procesy
nad `.omap`). To je správný vzor: **nové věci jako moduly, monolit nepřikrmovat.**
Post-process přes string-regex místo XML parseru je ale křehké — každý nový zápis
do `.omap` musí myslet na to, že ho cut/backgrounds nerozbijí (doloženo: clip nesmí
přes ET kvůli inject, Sez. 109). Aspoň: sdílený modul pro string-level `.omap` operace,
ať konvence žije jednou.

**B2 — `ISOM_REF` už není kopie, ale divergovaný dvojník** (map_gt nese olivovou +
purpury navíc). Pravidlo „extrakce až 3. konzument" je v pořádku, ale dvojník se stejným
jménem a jiným obsahem je past pro každého nového agenta — přejmenovat jeden z nich
(např. `GT_REF`), nebo do obou doplnit křížový komentář o divergenci.

**B3 — Licence korpusu: „legalizace až pokud model funguje" je vědomé riziko, ale
pozor na dvě věci:** (1) EU TDM výjimka (DSM čl. 4) připouští **opt-out** nositele
práv — nikdo zatím neověřil Livelox ToS z tohoto pohledu (deep research Sez. 67/110
řešil dostupnost, ne opt-out); (2) váhy modelu trénované na korpusu mohou být derivát —
do vyjasnění držet privátně i checkpointy a neukazovat výřezy map ve veřejných docs.
Pro kolegy: **nikdy nevkládat výřezy Livelox map do commitovaných souborů.**

**B4 — `requirements.txt` nedělený (trénink vs runtime).** Hranice „matplotlib =
trénink-only" je nepsaná a už jednou vystřelila (clip_quad×matplotlib rozbil produkční
běh na ntbhej, Sez. 112). Rozdělit na `requirements.txt` + `requirements-train.txt`,
nebo aspoň komentářové sekce + import-guard. Levné, zabrání recidivě.

**B5 — DIARY index znovu bobtná.** Pravidlo %END říká „1–2 věty hook", nález
%CALIBRATE Sez. 51/86 totéž — řádky Sez. 110–116 jsou znovu mnohařádkové odstavce
a index už dnes přesahuje 25k-token read-cap (vlastní důvod splitu archivu). Disciplínu
indexu vrátit: detail patří do diáře, index je rozcestník.

**B6 — Pseudo vrstvy potřebují jednotný registr.** 516 plot, 310 split ~55 %, pseudo
204/210 — každá vznikla jinak a lekce „pseudo musí do meta I .omap" (Sez. 108) se učila
za pochodu. Jeden seznam pseudo mechanismů (GLOSSARY tabulka: vrstva → mechanismus →
kde je v meta/stats/Y) zlevní každé další rozšíření a umožní benchmarku A1 pseudo
vrstvy poctivě vyřadit.

**B7 — Deep research za 103 agentů uťatý limitem (Sez. 110)** = nehospodárný tvar
průzkumu. Pro příště: fázovat (scout → cílený fan-out), průběžně sklízet do RESEARCH.md,
ať i uťatý běh zanechá plnou stopu.

---

## C. Doporučení pro kolegy (Opus 4.8, ChatGPT 5.5, …)

Destilát z diářů — vzory, které se opakovaně vyplatily, a chyby, které se opakovaně
trestaly. Držte je:

1. **Measure-first je zákon.** Diáře dokládají ≥6 vyvrácených „jasných" hypotéz
   (508 páka, 403 páka, 313 vodopád-mýtus, sklon=skalnatost, suppression 520, z-order
   520). Před každou „rychlou výhrou" simulujte dopad na KPI/datech; kód až po měření.
2. **Nález agenta ≠ fakt.** Sez. 93: 4 agentí falešné poplachy; Sez. 110: ChatGPT audit
   měl 1 kritický zásah + šum. Každý nález ověřit proti zdroji, než se zapíše/opraví.
3. **Žádný tichý fallback — včetně cache.** Skip-existing udělal kompas slepým
   (Sez. 99); každá cache musí mít invalidaci klíčovanou na verzi kódu (`_code_mtime`
   vzor). Chybějící vstup = hlasité selhání, ne náhradní cesta.
4. **Nesahat na loss/trénink před diagnózou.** Censure Sez. 106 (per-kanál focal
   zhoršila). Nejdřív root-cause na malém diagnostickém skriptu, pak změna.
5. **Konvence se ověřuje u uživatele, ne odhaduje.** Vizuální verify dělá uživatel
   (oko = source); orientace symbolů, kresba kartografa (520 budovy, Sez. 109) —
   ptát se PŘED kódem. Hierarchie: USER DEMO → FOTO → PDF spec → OOM → kód.
6. **Stroj × úloha.** Korpus + CUDA = HAL3000/mrkla; audity/docs/ČÚZK = kdekoli.
   Nenavrhovat fokus, který stroj neutáhne (%BEGIN bod 4) — a úklid prioritně na ntbhej.
7. **Nová vrstva = checklist propagace** (meta.json + `.omap` + stats + Y rastr +
   batch obě větve + docs vrstvy). Lekce 301/301.1 a pseudo-meta (Sez. 108/110): jedna
   zapomenutá vrstva = tichá díra na měsíce.
8. **Crosswalk vždy.** Reálné mapy jsou ISOM 2000, generátor 2017-2; integer-prefix
   srovnání bez `.crt` už jednou vyrobilo neplatný baseline (Sez. 94).
9. **Při optimalizaci KPI se vždy ptej: pomůže to reconstructoru na reálném skenu?**
   Pokud nevíš, je to kandidát na A1 benchmark, ne na další pb.

---

## D. Co funguje — nerozbíjet

- **Diářová kultura + Censure + Příště/carry** — auditovatelnost projektu je
  mimořádná; tento audit by bez ní nebyl možný.
- **Poctivé archivování slepých uliček** (ortofoto→runnability, forest_age proxy,
  Velbloud .pgw dead-end) — negativní výsledky se nemažou, dokládají se.
- **Golden vzorek (Šulcák) a byte-identické verify** — jen je zautomatizovat (A5).
- **SSoT opravy po nálezech** (AREA_CODES ← AREA_ZORDER) — správný reflex.
- **Doménové zásady v CLAUDE.md** (raw default, no silent fallback, foundations
  first) — reálně se vymáhají, ne jen deklarují.

---

---

## Stav řešení (aktualizováno Sezení 118, 2026-06-12 — Opus 4.8)

Reakce na audit. Akční položky převedeny do `docs/TODO.md` (sekce „Audit supervisor 2026-06-12 — námitky"),
tam je tracking. Stav nálezů ověřen proti zdroji:

| # | Námitka | Stav | Poznámka |
|---|---------|------|----------|
| A1 | doménový gap se neměří | **PŘIJATO → TODO [!]** | benchmark = next po voda-re-tréninku; přímo odpovídá na uživatelovo „má smysl dělat páry?" (Sez. 118 diskuse) |
| A2 | fialový přetisk + geom degradace | **PŘIJATO → TODO** | mění `dataset.py` → ne za běhu tréninku |
| A3 | KPI Goodhart | **ČÁSTEČNĚ ŘEŠENO** | Sez. 118 diskuse: uživatel zpochybnil KPI<0,95 jako gate; vázat úspěch na A1, ne KPI |
| A4 | architektura docs za realitou | **PŘIJATO → TODO** | docs-only sezení ntbhej (UC3↔UC4-III) |
| A5 | 0 automatizovaných testů | **PŘIJATO → TODO** | 5 smoke testů, nový soubor |
| A6 | reprodukovatelnost bus factor 1 | **PŘIJATO → TODO** | commit `_split`/`_curation`/`.pgw` |
| A7 | Png2Line bez %THINK | **PŘIJATO → TODO** | rešerše brzy, ntbhej |
| B2 | `ISOM_REF` divergovaný dvojník | **✅ VYŘEŠENO** | křížový komentář o divergenci doplněn do `compare_real_vs_gen.py` (map_gt měl, compare ne) |
| B4 | requirements nedělený | **ČÁSTEČNĚ** | komentářové sekce už existují (matplotlib trénink-only); zbývá fyzický split / import-guard |
| B1,B3,B5,B6,B7 | drobnosti | **PŘIJATO → TODO** | viz TODO blok |

**Verifikace auditu (zásada „nález ≠ fakt", audit bod C2):** všechny nálezy ověřeny proti zdroji — drží, žádný
falešný poplach. Korekce: B4 mířil na stav před vznikem komentářových sekcí (dnes částečně hotové); audit sám
opravil prvotní A3 formulaci (Livelox raster nemůže být KPI ref). Audit hodnocen jako solidní a vyvážený.

---

*Příští vydání auditu: porovnat stav námitek A1–A7 (VYŘEŠENO/TRVÁ/ZHORŠENO) dle
`AUDIT_SUPERVISOR_PROMPT.md` bodu 3.*
