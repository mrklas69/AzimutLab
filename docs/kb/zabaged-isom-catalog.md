# KB — ZABAGED Polohopis → ISOM 2017-2 (katalog vrstev)

Kompletní katalog **všech 149 feature typů** ČÚZK ZABAGED® Polohopis a jejich
mapování na ISOM 2017-2. U každé vrstvy je buď cílový ISOM symbol, **nebo důvod, proč
ji nekreslíme**. Princip (Sez. 23, uživatel): *„stojíme o všechna data z geoportálu,
ne vybraná"* — proto je tu i to, co (zatím) nepoužíváme.

> **Verify-against-source (2026-05-27, Sez. 24):** vrstvy z `GetCapabilities`, geometrie
> z `DescribeFeatureType`, ISOM kódy z `generator/template_classic.omap`
> (plná knihovna). Žádný řádek není z paměti.
>
> Konektor: `connectors/zabaged.py` · souhrn zdroje + licence: `data-sources.md` ·
> ISOM sémantika: `isom-issprom.md`.

**Runtime endpoint (Sez. 26, přechod WFS→REST):** `https://ags.cuzk.gov.cz/arcgis/rest/services/ZABAGED_POLOHOPIS/MapServer/<id>/query`
(dotaz podle numerického ID vrstvy, `LAYER_IDS` v konektoru) · **Zdroj katalogu:** `GetCapabilities`
(WFS, výčet 149 typů) · **CRS:** EPSG:5514 (S-JTSK) · **Formát:** GeoJSON · **Licence:** CC BY 4.0 (atribuce)
**Celkem:** 149 feature typů — **57 bodů / 45 linií / 47 ploch**.

> Názvy ve sloupci „Vrstva" jsou doslovné **WFS `typeName`** z `GetCapabilities` (oddělovače =
> podtržítka, `__` = závorka/dvojité). **Pozor (Sez. 31):** REST `MapServer` u některých vrstev
> používá jiný display name (s mezerami/závorkami, např. `Lávka (linie)` ≠ WFS `Lávka__linie_`) —
> v konektoru se vrstvy adresují **numerickým ID** (`LAYER_IDS`), ne názvem; nový záznam ověř `?f=json`.

## Legenda stavu
- **✓ použito** — konektor táhne dnes (Sez. 16–33).
- **◐ kandidát** — relevantní pro OB les, k doplnění (prioritní seznam viz konec).
- **○ možné** — okrajově relevantní (vzácné ve výsecích / nízká priorita).
- **✗ mimo doménu** — administrativa / POI / urbánní / vegetace gate; nekreslíme (důvod v pozn.).

## Principy mapování
- **Fyzický stav, ne správní třída.** ISOM rozlišuje podle sjízdnosti/zřetelnosti, ne podle
  evidence. Klíč = atributy (`povrch_k`, `TYPUSKOM_K`, `typtoku_k`…), ne jen název vrstvy.
- **Vegetace gate (Sez. 3).** ISOM 400 (zelená/žlutá) kóduje **průchodnost porostu**, ne jeho
  druh. ZABAGED nese druh („les se stromy", „křoví"), ne vertikální strukturu → vegetační
  vrstvy nelze mapovat na 406–410. Max. rozlišení les/otevřeno (405/401), a i to generátor
  zatím zahodil (vypadalo uměle, Sez. 11). Detail: `data-sources.md` „Vegetace gate".
- **Odvozené nekreslit zvlášť.** Co vzniká z jiné vrstvy (břehová čára z vodní plochy), netáhneme
  podruhé.
- **Geometrie ze zdroje.** Mosty, lávky, zdi jsou v ZABAGEDu **linie**, ne body (ověřeno
  `DescribeFeatureType`) — pozor na zděděné předpoklady.

---

## 1. Komunikace — cesty, silnice, průseky (ISOM 50x)

| Vrstva (WFS typeName) | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Silnice__dálnice` | linie | 502 Wide road | ✓ | evidovaná silnice/dálnice (≥5 m, autodoprava) |
| `Ulice` | linie | 502 Wide road | ✓ | městská ulice (okraj obce ve výseku) |
| `Silnice_neevidovaná` | linie | 503 Road | ✓ | účelové/lesní asfaltky <5 m (Sez. 23 — páteřní Bedřichov→Nová louka) |
| `Cesta` | linie | 503 / 504 | ✓ | `povrch_k` Z/T → 503 Road; jinak → 504 Vehicle track |
| `Pěšina` | linie | 505 / 506 | ✓ | `TYPUSKOM_K` 026 → 505 Footpath; jinak → 506 Small footpath |
| `Silnice_ve_výstavbě` | linie | 503 Road | ◐ | rozestavěná; vzácná, na OB se hotově nezakresluje → spíš vynechat |
| `Lesní průsek` | linie | 508 Narrow ride | ✓ | **Sez. 36** (id 16, REST jméno s MEZEROU); KISS vždy 508; bez runnability pozadí (vegetace=UC5). SV 46 / NL 119 / LS 20 / HS 16 / NV 44 |
| `Turistická_trasa` | linie | — | ✗ | overlay značení vedené PO existující cestě → duplikace sítě (Sez. 16) |
| `Parkoviště__odpočívka` | plocha | 501 Paved area | ✓ | **Sez. 41** (`--paved`, id 123; DRY s kolejiště → 501) |
| `Křižovatka_úrovňová` | bod | — | ✗ | atributový bod silniční sítě, ne kreslený objekt |
| `Křižovatka_mimoúrovňová` | bod | — | ✗ | atributový bod silniční sítě |
| `Uzlový_bod_silniční_sítě__ostatní_` | bod | — | ✗ | topologický uzel sítě, ne objekt |

## 2. Mosty, přechody a prostupy (ISOM 512, 519)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Most` | linie | 512 Bridge/tunnel | ◐ | **linie, ne bod** (oprava zděděného předpokladu); Sez. 31 implementace rollbacknuta Sez. 32 (3 iterace bez spec-driven), znovu spec-driven |
| `Lávka (linie)` | linie | 512.2 Footbridge | ◐ | lávka pro pěší (REST jméno **s mezerou a závorkou**, ne podtržítka); spec-driven po Sez. 32 mostu |
| `Lávka (bod)` | bod | 512.2 Footbridge | ◐ | bodová varianta lávky (REST jméno s mezerou); single dash 1,25 mm × 0,25 mm template id=127 |
| `Tunel` | linie | 512 Bridge/tunnel | ◐ | žel./silniční tunel; ISOM 512 = stejný symbol pro most i tunel (spec str. 32: „Bridges and tunnels are represented using the same basic symbols") |
| `Brod` | linie | (519 Crossing point) | ○ | brod přes tok; ISOM nemá vlastní symbol, nejblíž žádný |
| `Propustek__linie_` | linie | — | ○ | propustek pod cestou; drobnost, většinou nekreslit |
| `Propustek__bod_` | bod | — | ○ | bodová varianta |
| `Podjezd (linie)` | linie | (519 Crossing point?) | ○ | tematická skupina s Most/Tunel; verify ISOM 519 spec před implementací |
| `Podjezd (bod)` | bod | (519 Crossing point?) | ○ | bodová varianta; viz výše |
| `Přívoz` | linie | — | ✗ | přes splavnou řeku, vzácné v OB |
| `Přístaviště` | bod | — | ✗ | voda, urbánní |
| `Hraniční_přechod__přeshraniční_propojení` | bod | — | ✗ | administrativní |

## 3. Železnice, dráhy a lanovky (ISOM 509, 510)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Železniční_trať` | linie | 509 Railway | ✓ | **POUŽITO Sez. 28** (`--railways`, id 75, kombinovaný symbol) |
| `Železniční_vlečka` | linie | 509 Railway | ✓ | **POUŽITO Sez. 28** (id 76; u nádraží svazek kolejí) |
| `Lanová_dráha__lyžařský_vlek` | linie | 510 Power line, cableway or skilift | ○ | hory / lyž. areály |
| `Stožár_lanové_dráhy` | bod | 510 (carrying mast) | ○ | stožár lanovky |
| `Tramvajová_dráha` | linie | (509 Railway) | ✗ | urbánní |
| `Metro` | linie | — | ✗ | podzemní / urbánní |
| `Kolejiště` | plocha | 501 Paved area | ✓ | **POUŽITO Sez. 28** (`--paved`, id 122; „10 kolejí" = plocha, ne linie; do kolejiště se nevstupuje → 501 s obrysem) |
| `Areál_železniční_stanice__zastávky` | plocha | — | ✗ | urbánní |
| `Železniční_stanice__zastávka` | bod | — | ✗ | POI |
| `Stanice_metra` | bod | — | ✗ | urbánní POI |
| `Železniční_přejezd__linie_` | linie | — | ✗ | drobnost |
| `Železniční_přejezd__bod_` | bod | — | ✗ | drobnost |
| `Železniční_točna__přesuvna` | plocha | — | ✗ | urbánní / technický |

## 4. Energetika a produktovody (ISOM 510, 511)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Elektrické_vedení` | linie | **510** Power line | ✓ | **použito (Sez. 24)**; 510 NE 516 (516 = Fence/plot); `NAPETI` prázdné → vše 510 |
| `Stožár_elektrického_vedení` | bod | 510 (příčka na sloupu) | ✓ | **použito (Sez. 24)** jako poloha příček vedení (fáze 1; běžci se sloupy řídí) |
| `Dálkový_produktovod__dálkové_potrubí` | linie | — | ✗ | většinou podzemní; ISOM nemá |
| `Dopravníkový_pás` | linie | — | ✗ | průmysl (lom/těžba) |
| `Rozvodna__transformovna` | plocha | — | ✗ | oplocený technický areál |
| `Přečerpávací_stanice_produktovodu` | plocha | — | ✗ | technický |
| `Elektrárna__plocha_` | plocha | — | ✗ | průmysl |
| `Elektrárna__bod_` | bod | — | ✗ | průmysl |
| `Dobíjecí_stanice` | bod | — | ✗ | POI |

## 5. Vodstvo (ISOM 30x)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Vodní_tok` | linie | 304 / 305 / 306 | ✓ | dle pojmenovanosti/stálosti; podzemní (`typtoku_k`=004) nekreslit |
| `Vodní_plocha` | plocha | 301 Uncrossable body of water | ✓ | výplň + břehová linie |
| `Zdroj_podzemních_vod` | bod | 312 Spring | ◐ | pramen; ve výsecích vzácný (Sez. 17), ale relevantní (`typzdroj_k` PS) |
| `Vodopád__linie_` | linie | 313 Prominent water feature | ○ | vodopád |
| `Vodopád__bod_` | bod | 313 Prominent water feature | ○ | bodová varianta |
| `Pozemní_nádrž` | plocha | 301 | ✓ | **použito Sez. 27** — koupaliště/bazény (`podtypob_k='BA'`) i ostatní → 301 (Lesní koupaliště LS) |
| `Nadzemní_zásobní_nádrž` | plocha | (311 Well/tank) | ○ | technická nádrž |
| `Břehová_čára` | linie | 301.4 bank line | ✗ | obrys vodní plochy — odvozeno z 301, netáhnout zvlášť |
| `Přehradní_hráz__jez` | linie | — | ○ | hráz/jez; ISOM 528 prom. line, většinou nekreslit přímo |
| `Plavební_komora` | linie | — | ✗ | splavná řeka |
| `Lodní_výtah__zdvihadlo` | linie | — | ✗ | splavná řeka |
| `Akvadukt__shybka` | linie | — | ✗ | technický vodní objekt |
| `Suchá_nádrž` | bod | — | ✗ | suchý poldr |
| `Chladící_věž` | plocha | (524 High tower) | ✗ | průmysl |

## 6. Mokřady a bažiny (ISOM 307–310)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Bažina__močál` | plocha | 308 Marsh / 307 Uncrossable marsh | ◐ | bažina; proc. generátor zahodil (Sez. 11), real-vrstva relevantní |
| `Rašeliniště__plocha_` | plocha | 308 Marsh | ○ | rašeliniště |
| `Rašeliniště__bod_` | bod | 308 Marsh | ○ | bodová varianta |

## 7. Terénní tvary, skály a balvany (ISOM 1xx, 2xx)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Osamělý_balvan__skála__skalní_suk` | bod | 204 Boulder | ✓ | Sez. 30 (`--rocks`); ZABAGED bez atributu typu/výšky → 205 odpadlo, KISS |
| `Skalní_útvary` | plocha | 206 Gigantic boulder | ✓ | Sez. 30 (`--rocks`, plná černá plocha); hybridní 202/206 podle plochy zavrženo „bez datového podkladu" |
| `Skupina_balvanů__bod_` | bod | 207 Boulder cluster | ✓ | Sez. 30 (`--rocks`) |
| `Skupina_balvanů__linie_` | linie | 208 Boulder field | ◐ | pole balvanů — odloženo (3 prvky na Hrubé Skále) |
| `Sesuv_půdy__suť` | plocha | 210 Stony ground | ◐ | suť — odloženo (0 prvků na Hrubé Skále, verify v Jeseníkách / Krkonoších) |
| `Vstup_do_jeskyně` | bod | 203.2 Cave | ○ | jeskyně = OB objekt |
| `Povrchová_těžba__lom` | plocha | 201 Impassable cliff | ○ | lom (skalní stěna) |
| `Ústí_šachty__štoly` | bod | (203.2 Cave) | ○ | důlní ústí (umělé) |
| `Stupeň__sráz` | linie | 104 Earth bank | ○ | terénní stupeň/sráz (zemní) |
| `Rokle__výmol` | linie | 107 Erosion gully / 108 | ○ | erozní rýha |
| `Kótovaný_bod` | bod | 603.0 Spot height | ○ | výšková kóta |
| `Pata_terénního_útvaru` | linie | — | ✗ | pomocná linie (pata svahu), ne ISOM symbol |

## 8. Vegetace a povrch (ISOM 4xx) — pozor vegetace gate

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Lesní_půda_se_stromy` | plocha | (405 Forest) | ✗ gate | jen „les", ne hustota → max maska les/otevřeno |
| `Lesní_půda_se_stromy_kategorizovaná__plocha_` | plocha | (405 Forest) | ✗ gate | dtto |
| `Lesní_půda_se_stromy_kategorizovaná__bod_` | bod | — | ✗ gate | dtto |
| `Lesní_půda_s_kosodřevinou` | plocha | (410 fight) | ✗ gate | druh ≠ průchodnost |
| `Lesní_půda_s_křovinatým_porostem` | plocha | (406–410) | ✗ gate | druh ≠ průchodnost |
| `Významný_nebo_osamělý_strom__lesík` | bod | 417 Prominent large tree | ◐ | osamělý strom = OB objekt |
| `Orná_půda_a_ostatní_dále_nespecifikované_plochy` | plocha | 401 Open land | ✓ | **Sez. 41** (`--surfaces`); MVP KISS → 401 žlutá; ISOM-věrné 412 Cultivated (pattern) = druhá vlna |
| `Trvalý_travní_porost` | plocha | 401 Open land | ✓ | **Sez. 41** (`--surfaces`, louka → žlutá); odstín 401 vs 403 = gate nuance, KISS 401 |
| `Udržovaná_zeleň` | plocha | 401 Open land | ✓ | **Sez. 41** (`--surfaces`, park → žlutá) |
| `Ovocný_sad__zahrada` | plocha | 401 Open land | ✓ | **Sez. 41** (`--surfaces`); MVP KISS → 401 žlutá; ISOM-věrné 413 Orchard (zelené tečky) = druhá vlna |
| `Liniová_vegetace` | linie | 416 Distinct vegetation boundary | ○ | mez / živý plot / řada stromů |
| `Vinice` | plocha | (414 Vineyard) | ✗ | vzácné v OB lese |
| `Chmelnice` | plocha | (414 obdoba) | ✗ | vzácné |
| `Hranice_užívání_půdy` | linie | (415 cultivation boundary) | ✗ | administrativní hranice využití |
| `Ostatní_plocha_v_sídlech` | plocha | — | ✗ | urbánní |
| `Hřbitov` | plocha | 520 Area that shall not be entered | ✓ | **Sez. 41** (`--surfaces`, olivová out-of-bounds); ISOM nemá vlastní hřbitov → 520 (verify template) |

## 9. Budovy a stavby plošné (ISOM 521–525)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Budova_jednotlivá_nebo_blok_budov__plocha_` | plocha | 521 Building | ✓ | plošná budova (vč. vodojemu zemního) |
| `Rozvalina__zřícenina` | plocha | 523 Ruin | ◐ | zřícenina = OB objekt |
| `Budova_jednotlivá_nebo_blok_budov__bod_` | bod | (521) | ✗ | v lesních výsecích prázdná (Sez. 18) |
| `Kůlna__skleník__fóliovník__přístřešek` | plocha | 521 Building / 522 Canopy | ○ | drobná stavba / přístřešek |
| `Hrad` | plocha | 521 Building | ○ | historická stavba |
| `Zámek` | plocha | 521 Building | ○ | historická stavba |
| `Věžovitá_stavba` | plocha | 524 High tower | ○ | věžovitá stavba (plošná) |
| `Tribuna` | plocha | — | ✗ | stadion, urbánní |
| `Stavební_objekt_GIA` | plocha | — | ✗ | technický |
| `Stavební_objekt_zakrytý` | plocha | — | ✗ | technický |
| `Skládka` | plocha | — | ✗ | skládka |
| `Úložné_místo` | plocha | — | ✗ | technický |
| `Areál_účelové_zástavby` | plocha | — | ✗ | urbánní areál |
| `Heliport` | plocha | — | ✗ | speciál |

## 10. Bodové umělé / orientační prvky (ISOM 52x–53x, 417)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Kříž__sloup_kulturního_významu` | bod | 530/531 Prominent man-made feature | ◐ | boží muka / kříž = klasický OB objekt |
| `Mohyla__pomník__náhrobek` | bod | 526 Cairn / 530 Prom. man-made | ◐ | mohyla / pomník = OB objekt |
| `Bunkr` | bod | asset (řopík) | ✓ | **použito Sez. 27** — LO37 → asset `ropik_10000.omap`, orientace k st. hranici (NE prostý 521) |
| `Věž__věžovitá_nástavba` | bod | 524 High tower | ◐ | rozhledna / věž = výrazný OB bod |
| `Vodojem_věžový` | bod | 524 High tower | ○ | vodárenská věž (zemní vodojem → 521, Sez. 18) |
| `Větrný_mlýn` | bod | 524 High tower / 526 | ○ | historický objekt |
| `Větrný_motor` | bod | 524 High tower | ○ | větrná elektrárna (velký orientační bod) |
| `Silo` | bod | 524 High tower / 526 | ○ | silo |
| `Těžní_věž` | bod | 524 High tower | ○ | důlní věž |
| `Tovární_komín` | bod | (524 / 526) | ✗ | průmysl |
| `Lyžařský_můstek` | linie | — | ✗ | speciál |

## 11. Bariéry a ohrazení (ISOM 105, 513–518)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Zeď` | linie | 513 Wall | ◐ | zeď = OB liniový objekt |
| `Hradba__val__bašta__opevnění` | linie | 105 Earth wall / 513 Wall | ○ | historické opevnění / val |
| `Zábrana` | bod | (519 Crossing point) | ○ | závora / zábrana |

## 12. Hranice, chráněná území a POI (administrativa — vše ✗)

| Vrstva | Geom | Stav | Proč ne |
|---|---|---|---|
| `Hranice_správní_jednotky_a_KÚ` | linie | ✗ | administrativní hranice |
| `Hranice_geomorfologické_jednotky` | linie | ✗ | administrativní / koncept |
| `Rozvodnice` | linie | ✗ | vodní rozvodí (koncept, ne objekt) |
| `Maloplošné_zvlástě_chráněné_území` | plocha | ✗ | administrativní (ochrana přírody) |
| `Velkoplošné_zvláště_chráněné_území` | plocha | ✗ | administrativní |
| `Ptačí_oblast` | plocha | ✗ | administrativní (Natura 2000) |
| `Evropsky_významná_lokalita` | plocha | ✗ | administrativní (Natura 2000) |
| `Definiční_bod_správního_celku` | bod | ✗ | administrativní bod |
| `Definiční_bod_části_obce` | bod | ✗ | administrativní bod |
| `Definiční_bod_náměstí` | bod | ✗ | administrativní bod |
| `Definiční_bod_adresního_místa` | bod | ✗ | administrativní bod |
| `Cizí_zastupitelský_úřad___definiční_bod` | bod | ✗ | POI |
| `Pošta_-_definiční_bod` | bod | ✗ | POI |
| `Škola_-_definiční_bod` | bod | ✗ | POI |
| `Školské_zařízení_-_definiční_bod` | bod | ✗ | POI |
| `Nemocnice_-_definiční_bod` | bod | ✗ | POI |
| `Zdravotnické_zařízení_-_definiční_bod` | bod | ✗ | POI |
| `Policejní_služebna_-_definiční_bod` | bod | ✗ | POI |
| `Hasičská_stanice__zbrojnice_-_definiční_bod` | bod | ✗ | POI |
| `Sociální_zařízení_-_definiční_bod` | bod | ✗ | POI |
| `Meteorologická_stanice_-_definiční_bod` | bod | ✗ | POI |
| `Úřad_veřejné_správy_-_definiční_bod` | bod | ✗ | POI |
| `Čerpací_stanice_pohonných_hmot_-_definiční_bod` | bod | ✗ | POI |

## 13. Geodetické body, letiště, pomocné (vše ✗)

| Vrstva | Geom | Stav | Proč ne |
|---|---|---|---|
| `Bod_polohového_bodového_pole` | bod | ✗ | geodetický bod (ne mapový obsah) |
| `Bod_základního_výškového_bodového_pole` | bod | ✗ | geodetický bod |
| `Bod_základního_tíhového_bodového_pole` | bod | ✗ | geodetický bod |
| `Letiště` | plocha | ✗ | speciál |
| `Obvod_letištní_dráhy` | plocha | ✗ | speciál |
| `Osa_letištní_dráhy` | linie | ✗ | speciál |
| `Doplňková_linie` | linie | ✗ | pomocná kreslicí linie ZABAGEDu |

---

## Shrnutí — co (zatím) kreslíme

| Stav | Počet | Které |
|---|---|---|
| ✓ použito | ~24 | cesty + voda + budovy + vedení + řopíky (Sez. 16–27) + železnice/kolejiště (28) + skály (30) + mosty/tunely/lávky (32–33) + lesní průseky (36) + **plošný pokryv: open land louka/park/pole/sad→401, hřbitov→520, parkoviště→501 (Sez. 41)** |
| ◐ kandidát | 11 | **viz akční seznam níže** |
| ○ možné | ~30 | okrajově relevantní (vzácné / nízká priorita) |
| ✗ mimo doménu | ~100 | administrativa, POI, urbánní, vegetace gate |

### Akční seznam kandidátů (◐) — priorita doplnění do konektoru

Seřazeno podle vizuální návratnosti pro OB lesní mapu (✓ `Elektrické_vedení` hotovo Sez. 24):

1. **`Most` → 512 Bridge/tunnel** — linie; spolu s `Lávka__linie_` → 512.2 Footbridge.
2. ~~`Osamělý_balvan…` → 204 + `Skupina_balvanů__bod_` → 207 + `Skalní_útvary` → 206~~ (HOTOVO Sez. 30, `--rocks`; KISS vrstva → jeden symbol).
3. ~~`Lesní průsek` → 508 Narrow ride~~ (HOTOVO Sez. 36, `--rides`; KISS vždy 508, bez runnability pozadí).
4. **`Kříž__sloup…` → 530/531** + **`Mohyla__pomník…` → 526/530** + ~~`Bunkr`~~ (HOTOVO Sez. 27 = asset řopík) + **`Věž…` → 524** — bodové orientační prvky.
5. **`Zeď` → 513 Wall** — liniový objekt.
6. **`Bažina__močál` → 308 Marsh** — pokud se vrátíme k mokřadům.
7. **`Zdroj_podzemních_vod` → 312 Spring** — pramen (ve výsecích vzácný).
8. ~~`Železniční_trať` → 509 Railway~~ (HOTOVO Sez. 28, `--railways`; `_vlečka` taky).

> Každý kandidát = nová vrstva v `PATH_LAYERS` / nová `*_LAYERS` + mapovací funkce + render
> styl + verify-against-source na reálném výseku (atributy → ISOM před renderem). Po ověření
> přesunout řádek na ✓ a doplnit do `data-sources.md`.
