# Vytěžek z běhu ChatGPT 5.5 na ISOM-scan benchmarku (Sez. 144)

ChatGPT 5.5 za **41 minut v jediné odpovědi** rozpoznal 50 ISOM kódů ze skenu Branžeže a v našem
benchmarku porazil Claude Opus 4.8 (headline 0,50 vs 0,00; class_recall 0,875 vs 0,125). Uživatel:
*„předvedl, co neumíme po stovce sezení v generatoru(), dokonce co si slibuji od reconstructoru()."*
Tohle je vytěžek jeho **myšlenkového trace** (`Thinking.html`, 41 min, 208 vizuálních cropů, 92 fetchů
na O-Map Wiki) — nápady, ke kterým se vracíme v dalších sezeních.

> **Caveat (`external-ai-artifacts-verify-not-accept`):** ISOM fakta níže [I1–I7] jsou ChatGPT-sourced
> (O-Map Wiki). Než je zapečeme do spec/generátoru, **verify-against-source** proti IOF spec.

Tagy: [METHOD] postup · [GEN] generator() · [REC] reconstructor() · [BENCH] benchmark · [ISOM] doména · [TOOL] CV.

## TOP 5 k okamžitému zvážení
1. **[TOOL/REC] Black-excluding-brown maska** `(img.max(2)<130) & (img.max(2)-img.min(2)<18)` — „neutrálně
   tmavé" pixely: izoluje ČERNÉ symboly/cesty a vyloučí hnědé vrstevnice (velký channel spread). Triviální,
   přímo řeší náš boj o oddělení černé kresby od hnědé. Použít v reconstructoru i v měřicích skriptech.
2. **[GEN/TOOL] Exact-color histogram skenu** `Counter(map(tuple, arr.reshape(-1,3)))` → (a) **kalibrační
   cíl barev generátoru** (verify-against-source pro BARVU), (b) základ plošné separace. Naměřené reálné RGB:
   406 `(190,244,176)` · 408 `(126,235,100)` · 410/zelený X `(45,221,6)` · vrstevnice `(187,77,25)` ·
   403 `(255,223,163)` · 520 `(152,177,21)` · poledník `(0,212,212)` · 417 strom `(0,145,25)`.
3. **[REC] 16×16 shape-descriptor** — komponentu zmenší na 16×16, změří center (6:10)/corners/mid_edges/fill
   → rozliší **X** vs **ring** vs **plný kruh** bez šablony i ML. Mapuje přímo na png2point třídy 204/210/417/419
   = levný non-ML klasifikátor/ověřovač.
4. **[METHOD/ISOM] Render spec PDF + O-Map Wiki cross-ref na přesné tvary PŘED commitem** — disciplinované
   verify-against-source pro IDENTITU symbolu (dotahuje [[isom-spec-before-render]] z „přečíst" na „vizuálně zakotvit").
5. **[METHOD] Multi-resolution vizuální pipeline** — overlapping tiling (souřadnice v názvu souboru) → grid
   overlay s popisky → per-symbol NEAREST zoom 6–8× → candidate-overlay contact sheety. Reprodukovatelný
   postup, jak „vidět" hustou mapu (přesně to, co jsem dnes dělal ad-hoc).

## [TOOL] CV techniky (jádro úspěchu)
- **T1. Exact-color histogram → diskrétní ISOM paleta** (viz TOP 2). Digitální OB mapa = málo přesných barev.
- **T2. Black-vs-brown maska** (viz TOP 1) — nejcennější trik.
- **T3. Per-color distance masky + `cv2.connectedComponentsWithStats`** → filtr area/w/h/fill = univerzální
  detektor objektů per barevná třída (body i plochy).
- **T4. 16×16 shape-descriptor** (viz TOP 3).
- **T5. Kruhovitost + fill** `circ = 4πA/perim²` (+ aspect 0,55–1,8) → izolované plné kruhy = balvan 204 / strom 417.
- **T6. `colors_around`** — před zařazením bodu vypíše nejčastější barvy v okně 10–15 px → ověří třídu, chytí
  omyl (souřadnice na bílé).
- **T7. Candidate-overlay contact sheets** — magenta rámečky + indexy na sken + výřezy do mřížky = eye-in-the-loop.
- **T8. Tvar komponenty rozliší bod vs area-pattern** — tenké dlouhé (w≈2, h velké) = svislý vegetační raster 407/409, ne bod.

## [METHOD] Pracovní postup
- **M1. Render-first nad spec PDF** — stránky ISOM PDF → PNG (180 dpi), symboly vyříznul a zvětšil, místo čtení textu.
- **M2. Multi-resolution tiling** (viz TOP 5) — 4×5/4×4 překrývající cropy (30 px overlap) ×2 zoom.
- **M3. Konzervativní reporting** — jen vysoká jistota; u linií „četnost = vizuální odhad"; `confidence` per detekce.
- **M4. Output engineering** — finální JSON 1 řádek/detekci (`separators=(',',':')`) kvůli velikostnímu stropu.

## [ISOM] Doménové poznatky (⚠ verify proti IOF spec před adopcí)
- **I1.** Kódy bral z **O-Map Wiki**, ne ze starého 2000 PDF (úkol chtěl 2017-2) — 92 fetchů.
- **I2.** Dvojí číslování potvrzeno: OCAD 535 high tower / 536 small tower / 537 cairn / 538 fodder rack vs
  OOM 524–527; reportoval kanonické OOM (= naše [[isom-dual-numbering-oom-ocad]]).
- **I3.** Přesné tvary (self-corrected): 527 fodder = „Λ" na stopce; 525 small tower = obrácené T; 524 = hash/kříž;
  526 cairn = kroužek se středovým bodem.
- **I4.** „Definition must be given on the map": 115 Prominent landform, 419 Prominent vegetation feature.
- **I5.** Min-size: 405 forest 1×1 mm · 408 walk 0,7 mm · 206 průchod mezi pilíři > 0,15 mm.
- **I6.** Dvojice: 108 erosion gully vs 306 watercourse = délkou; 113 broken ground = méně zřetelné jámy; 203.2 = Dangerous pit (Rev 6, 1/2024).
- **I7.** Rozlišená taxonomie: vegetace 403/404/406/407/408/409/410; cesty 502–507; skály 201/202/206/208/210.

## [REC] Přímo pro reconstructor()
- **R1.** Pipeline T1–T5 = **deterministický non-ML reconstructor baseline** pro body i plochy na čistých
  renderech → (a) srovnávací baseline proti našim modelům, (b) auto-prelabeler/verifikátor GT, (c) classic-CV
  větev vedle Png2Point/Area.
- **R2.** Black-excluding-brown maska (T2) = čistá extrakce černých bodů a cest oddělená od vrstevnic.
- **R3.** Shape-descriptor (T4) → png2point třídy bez tréninku.
- **R4.** Pro REÁLNÉ skeny: nejdřív kvantizace na paletu (T1), pak masky = most „clean gen" → „real scan".

## [GEN] Pro věrnost generator()
- **G1.** Naměřená paleta skenu (T1) = **kalibrační cíl barev** — sladit emitované RGB s naměřenými.
- **G2.** Třídy, které kartograf kreslí a my (možná) ne: 407/409 svislý raster „good visibility", 403/404 rough
  open, 113 broken ground, 115 prominent landform, jemná hierarchie cest 504/507 → cíle pro KPI/pokrytí.

## [BENCH] Vylepšení benchmarku
- **B1.** Politika 601 Magnetic north line — ChatGPT ji počítal jako validní; my vyloučili. Rozhodnout explicitně.
- **B2.** **Třídy ekvivalence při skórování** — skály 201/202/206/208/210, pěšiny 505/506/507, rough open 403/404:
  GT je kolabuje, modely štěpí → jinak nefér penalizace (potvrzuje dnešní 505-vs-506 propad Opusu).
- **B3.** `confidence` per detekce → confidence-thresholded P/R křivky.
- **B4.** Normalizované souřadnice vedle px do schématu (přenositelnost přes rozlišení).
- **B5.** Liniové „počty" nespolehlivé (sám přiznává) → headline neopírat o raw line counts.
- **B6.** Definovat „dotýkající se balvan se počítá?" — jeho 204=8 vědomě vynechal balvany u skal (precision>recall).

## Sebekorekce (lekce izomorfní s našimi principy)
- Fodder rack nejdřív měl za budovu → ověřil spec → Λ/T. (Verify shape before commit.)
- Ring 417 vypadl z filtru (area 55 < cutoff 60) → rozšířil prahy. **Filtry tiše zahazují validní symboly**
  = naše [[no-silent-fallback]] / `verify-area-layer-full-render`.
- Souřadnice padla na bílou → „dělej to programově, ne od oka" = naše `verify-data-not-assume`.
