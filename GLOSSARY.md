# GLOSSARY — AzimutLab

Terminologie projektu. Krátké definice + odkaz na zdroj pravdy (detail nekopírujeme —
DRY). Pojmy se zavádějí, jak je projekt potkává; doplňuj v `%END`.

## Doména — orientační běh a mapy

- **OB** — orientační běh; sportovní disciplína navigace v terénu podle mapy.
- **ISOM** (International Specification for Orienteering Maps) — norma pro klasické
  lesní OB mapy (verze 2017-2). Symboly, barvy, priority. Cílová sémantika projektu.
  Detail: `docs/kb/isom-issprom.md`.
- **ISSprOM** — sesterská norma pro sprintové / městské mapy (2019-2). Stejný kód ≠
  stejný symbol napříč ISOM/ISSprOM (např. budovy black vs gray).
- **Vrstevnice** (contour) — izolinie výškového pole, spojnice bodů stejné nadmořské
  výšky. ISOM symbol **101**. Z principu se nekříží a nekončí ve vzduchu.
- **Index contour** (zvýrazněná / hlavní vrstevnice) — každá pátá vrstevnice, silnější
  čára pro snazší čtení. ISOM symbol **102**. V generátoru každých 25 m.
- **Form line** — pomocná vrstevnice mezi základními. ISOM **103**. Generátor zatím nedělá.
- **Ekvidistance** — svislý rozestup vrstevnic (v projektu 5 m).
- **Kopeček** (knoll) — malá vyvýšenina; je-li menší než zobrazitelná vrstevnicí, kreslí
  se bodovým symbolem. ISOM **112** (Small knoll, kulatý) / **113** (Elongated knoll,
  protáhlý). Generátor je odvozuje z malých uzavřených vrstevnic (lokální max, Sez. 10).
- **Prohlubeň** (depression) — malá terénní sníženina. ISOM **115** (Small depression,
  hnědý oblouk „⌣"). Generátor z malých uzavřených vrstevnic (lokální min). 116 Pit
  (jiná feature class — umělá/erozní díra) generátor nedělá (neodvoditelný z výškopisu).
- **Kartografická generalizace** — zjednodušení reality pro čitelnost mapy. V generátoru:
  příliš malý kopeček/prohlubeň se nekreslí prstencem vrstevnice, ale bodovou značkou (§4.10).
- **Ground-truth (GT)** — referenční „pravdivá" anotace pro trénink/validaci modelu.
  Klíčová výhoda generátoru: každá vrstva je zároveň segmentační maska → GT zdarma.

## Data a geoinformatika

- **ČÚZK** — Český úřad zeměměřický a katastrální. Od 1. 7. 2023 poskytuje hlavní sady
  jako open data **CC BY 4.0**. Detail + katalog: `docs/kb/data-sources.md`.
- **ZABAGED®** — Základní báze geografických dat; vektorová topografická *databáze*
  (polohopis + výškopis). Zdroj pravdy, ze kterého se renderují mapy.
- **ZTM** — Základní topografická mapa (ZTM5–ZTM250); hotové kartografické *dílo* (rastr).
- **DMR 5G** — Digitální model reliéfu 5. generace; LiDAR výškopis terénu (ground-only),
  přesnost ~0,18 m. Zdroj reálného terénu pro `--terrain real` (modul `dmr.py`).
- **DMP OK** — Digitální model povrchu z obrazové korelace (fotogrammetrie, **ne LiDAR**)
  → jen viditelný povrch, žádné penetrující odrazy.
- **CHM** (Canopy Height Model) — model výšky vegetace = DMP − DMR. Slabý proxy pro hustotu
  porostu (zelenou), ne plnohodnotná náhrada multi-echo LiDARu.
- **Multi-echo / LLS mračno** — klasifikované LiDAR mračno bodů se všemi odrazy (terén +
  vegetační echa). Potřebné pro vegetaci à la Karttapullautin; ČÚZK ho jako open data nemá
  (viz „Vegetace gate" v `data-sources.md`).
- **S-JTSK** (EPSG:5514) — Systém jednotné trigonometrické sítě katastrální; národní
  souřadný systém ČR (Křovák). ČÚZK data jsou v něm.
- **WGS84** (EPSG:4326) — globální zeměpisné souřadnice (lat/lon). Vstup `--lat/--lon`,
  přepočet na S-JTSK přes `pyproj`.
- **WMS / WMTS / WFS / WCS / ATOM** — OGC přístupové protokoly ČÚZK (prohlížecí rastr /
  dlaždice / vektor / rastr-výškopis / předpřipravené open-data jednotky).
- **georef** (georeferencování) — přiřazení world souřadnic geometrii. `contours.geojson`
  je u `--terrain real` georeferencován v S-JTSK.

## Projekt — struktura a principy

- **UC** (use case) — jeden z pěti záměrů projektu (UC1-UC5). Tvoří **DAG**, ne seznam.
  Kanonický popis: `docs/architecture.md`.
- **DAG** (directed acyclic graph) — orientovaný acyklický graf závislostí. Zde: enablery
  (UC2 data, UC5 modely) leží pod aplikacemi (UC3 restaurace, UC4 generátory).
- **Enabler / aplikace** — enabler je předpoklad (data, model), aplikace je koncový produkt.
  Pravidlo: enabler před aplikací („foundations before curtains").
- **Feeder / enabler-feeder** — generátor (UC4-I) coby zdroj trénovacích dat pro UC5;
  „krmí" model. Reframe Sez. 4: ne konečný produkt, ale enabler.
- **Deštník / fáze B→A** — AzimutLab je teď meta-vrstva (fáze B, deštník) nad sourozeneckým
  Pic2Omap; cíl je monorepo (fáze A), které Pic2Omap absorbuje, až vznikne sdílené jádro.
- **Pic2Omap** — sourozenecký projekt (raster OB mapa → vektor `.omap`); UC4-III. Žije ve
  vlastním repu, neduplikovat sem (CLAUDE.md).
- **Gate** — licenční/datová brána: bez vyjasněné licence (nebo dostupnosti dat) se nad
  zdrojem nestaví. „Vegetace gate" = zavřená cesta k vegetaci z ČÚZK open dat.
- **Domain gap** — rozdíl mezi syntetikou a realitou (syntetika je hladší). Řeší se
  sim-to-real receptem.
- **Sim-to-real** — předtrénink na syntetice (cesta C) + fine-tuning/validace na reálných
  mapách (cesta B); reálný terén (A) dosazený do generátoru.
- **Cesty A / B / C** — datové zdroje pro UC5: (A) geodata ČÚZK, (B) reálné korpusy map,
  (C) syntetická generace. Detail: `RESEARCH.md`.
- **Sparse-GT past** — málo ground-truth anotací (z Pic2Omap pilotu); generátor ji obchází
  (GT zdarma).
- **SLAP** (Single Level of Abstraction Principle) — při změně konceptu aktualizovat všechny
  vrstvy najednou (model / kód / docs / data). Viz CLAUDE.md.

## Nástroje a knihovny

- **OOM** (OpenOrienteering Mapper) — open-source editor OB map; cílový formát `.omap`.
- **OCAD** — komerční SW pro tvorbu map; formát `.ocd`.
- **Karttapullautin** — generátor OB podkladů z klasifikovaného LiDAR mračna (vrstevnice +
  vegetace). Stojí za projekty MapAnt. Survey: `RESEARCH.md`.
- **CoVe** — color line vectorization pro orienťácké čáry (v OOM).
- **AutoTrace** — bitmap → vektor (raster tracing). Pro reálné skeny (UC4-III/UC3), **ne**
  pro náš generátor (ten má vektor z contourpy přímo).
- **lasertool** — lokální binárka: LiDAR point cloud → rastr (rodina Karttapullautin).
- **contourpy** — Python knihovna marching squares; generátor z ní bere vrstevnice jako
  polylinie.
- **marching squares** — algoritmus pro izolinie skalárního pole na mřížce.
- **pyproj** — transformace souřadnic (WGS84 ↔ S-JTSK); závislost jen pro `--terrain real`.
- **`.omap` / `.ocd`** — XML/binární formáty OB map (OOM / OCAD). Generátor umí `.omap`
  export (template-based, `omap_export.py`).
- **GeoJSON** — textový vektorový formát; `contours.geojson` = vrstevnice jako LineString
  s ISOM symbolem.
