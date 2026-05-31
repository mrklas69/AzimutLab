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
| `Most` | linie | 512 Bridge/tunnel | ✓ | **linie, ne bod** (oprava zděděného předpokladu); Sez. 31 implementace rollbacknuta Sez. 32 (3 iterace bez spec-driven), DOKONČENO Sez. 33 (2 paralely + nožičky 512, OOM verify) |
| `Lávka (linie)` | linie | 512.2 Footbridge | ✓ | lávka pro pěší (REST jméno **s mezerou a závorkou**, ne podtržítka); DOKONČENO Sez. 33 |
| `Lávka (bod)` | bod | 512.2 Footbridge | ✓ | bodová varianta lávky (REST jméno s mezerou); single dash 1,25 mm × 0,25 mm template id=127; DOKONČENO Sez. 33 |
| `Tunel` | linie | 512 Bridge/tunnel | ✓ | žel./silniční tunel; ISOM 512 = stejný symbol pro most i tunel (spec str. 32: „Bridges and tunnels are represented using the same basic symbols"); DOKONČENO Sez. 33 (portály 90° na vjezdech) |
| `Brod` | linie | (519 Crossing point) | ○ | brod přes tok; ISOM nemá vlastní symbol. **Změřeno Sez. 55:** SV 3 / NL 1 / LS 1 / HS 1 = Σ6 |
| `Propustek__linie_` | linie | — | ○ | propustek pod cestou; drobnost, většinou nekreslit |
| `Propustek__bod_` | bod | — | ○ | bodová varianta |
| `Podjezd (linie)` | linie | (519 Crossing point?) | ○ | tematická skupina s Most/Tunel; verify ISOM 519 spec před implementací. **Změřeno Sez. 55:** LS 11 / HS 1 = Σ12 |
| `Podjezd (bod)` | bod | (519 Crossing point?) | ○ | bodová varianta; viz výše. **Změřeno Sez. 55:** LS 1 = Σ1 |
| `Přívoz` | linie | — | ✗ | přes splavnou řeku, vzácné v OB |
| `Přístaviště` | bod | — | ✗ | voda, urbánní |
| `Hraniční_přechod__přeshraniční_propojení` | bod | — | ✗ | administrativní |

## 3. Železnice, dráhy a lanovky (ISOM 509, 510)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Železniční_trať` | linie | 509 Railway | ✓ | **POUŽITO Sez. 28** (`--railways`, id 75, kombinovaný symbol) |
| `Železniční_vlečka` | linie | 509 Railway | ✓ | **POUŽITO Sez. 28** (id 76; u nádraží svazek kolejí) |
| `Lanová dráha, lyžařský vlek` | linie | 510 Power line, cableway or skilift | ✓ | **Sez. 55** (`--powerlines`, id 72; REST jméno s mezerou/čárkou). ISOM 510 = „Power line, cableway *or skilift*" = TÝŽ symbol jako vedení → sloučeno do `--powerlines` (mirror vedení; KISS). `typ_ldv_k` (vlek/lanovka/kabinová) ISOM nerozlišuje → vždy 510. NL 2 / LS 1 (Ještěd) |
| `Stožár lanové dráhy` | bod | 510 (carrying mast) | ✓ | **Sez. 55** (`--powerlines`, id 61; přidáno do `POWERLINE_MAST_LAYERS` — příčky symbolu 510 na poloze sloupů, fáze 1, mirror `Stožár_elektrického_vedení`). NL 4 / LS 2 |
| `Tramvajová_dráha` | linie | 509 Railway | ✓ | **POUŽITO Sez. 31** (`--railways`, id 71; oprava Sez. 28 vynechání — tramvajová točna LS chyběla; 509 nerozlišuje tramvaj od železnice). LS 25 |
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
| `Zdroj podzemních vod` | bod | 312 Spring | ✓ | **Sez. 44** (`--landmarks`, modré „U" ústím nahoru ∪); pramen Σ65 napříč 5 lokalitami (REST jméno s mezerami) |
| `Vodopád__linie_` | linie | 313 Prominent water feature | ○ | vodopád. **Změřeno Sez. 55:** 0 ve všech 5 výsecích |
| `Vodopád__bod_` | bod | 313 Prominent water feature | ○ | bodová varianta. **Změřeno Sez. 55:** SV 1 / HS 1 = Σ2 |
| `Pozemní_nádrž` | plocha | 301 | ✓ | **použito Sez. 27** — koupaliště/bazény (`podtypob_k='BA'`) i ostatní → 301 (Lesní koupaliště LS) |
| `Nadzemní zásobní nádrž` | plocha | 311 Well/fountain/water tank | ✓ | **Sez. 44** (`--landmarks`, plocha → centroid → modrý čtverec); Σ8 (LS 6 / HS 2) |
| `Břehová_čára` | linie | 301.4 bank line | ✗ | obrys vodní plochy — odvozeno z 301, netáhnout zvlášť |
| `Přehradní_hráz__jez` | linie | (528 Prom. line) | ○ | hráz/jez — ODLOŽENO (Sez. 44): ISOM 528 vyžaduje definici v legendě mapy (ruční krok), mapování hráz↔528 sporné (jez = spíš přerušení toku 304). **Změřeno Sez. 55:** SV 3 / NL 3 / LS 7 = Σ13 |
| `Plavební_komora` | linie | — | ✗ | splavná řeka |
| `Lodní_výtah__zdvihadlo` | linie | — | ✗ | splavná řeka |
| `Akvadukt__shybka` | linie | — | ✗ | technický vodní objekt |
| `Suchá_nádrž` | bod | — | ✗ | suchý poldr |
| `Chladící_věž` | plocha | (524 High tower) | ✗ | průmysl |

## 6. Mokřady a bažiny (ISOM 307–310)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Bažina, močál` | plocha | 308 Marsh | ✓ | **Sez. 44** (`--marsh`, modrá vodorovná šrafa; KISS vždy crossable 308, NE 307 — data nenesou překonatelnost). NV 15 / HS 10 / NL 9 / SV 5 |
| `Rašeliniště (plocha)` | plocha | 308 Marsh | ✓ | **Sez. 44** (`--marsh`, spolu s bažinou — mokřad téhož symbolu) |
| `Rašeliniště__bod_` | bod | 308 Marsh | ○ | bodová varianta — odloženo (plošná pokrývá) |

## 7. Terénní tvary, skály a balvany (ISOM 1xx, 2xx)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Osamělý_balvan__skála__skalní_suk` | bod | 204 Boulder | ✓ | Sez. 30 (`--rocks`); ZABAGED bez atributu typu/výšky → 205 odpadlo, KISS |
| `Skalní_útvary` | plocha | 206 Gigantic boulder | ✓ | Sez. 30 (`--rocks`, plná černá plocha); hybridní 202/206 podle plochy zavrženo „bez datového podkladu" |
| `Skupina_balvanů__bod_` | bod | 207 Boulder cluster | ✓ | Sez. 30 (`--rocks`) |
| `Skupina_balvanů__linie_` | linie | 208 Boulder field | ◐ | pole balvanů — odloženo. **Změřeno Sez. 55** (`returnCountOnly` 5 lokalit): SV 7 / HS 3 / NV 4 = **Σ14** (ne „3 na HS"). Vyžaduje nový render (buffer linie → plocha s ISOM area pattern trojúhelníky) |
| `Sesuv_půdy__suť` | plocha | 210 Stony ground | ◐ | suť — odloženo. **Změřeno Sez. 55:** SV 1 = Σ1 (marginální; verify v Jeseníkách / Krkonoších) |
| `Vstup do jeskyně` | bod | 203.2 Cave | ✓ | **Sez. 44** (`--landmarks`, černá „Λ" stříška hrotem nahoru = „with a distinct entrance"; NE plný trojúhelník — oprava dle uživatele; 203.1 = V hrotem dolů „without entrance"). Σ s šachtou 9 |
| `Povrchová_těžba__lom` | plocha | 201 Impassable cliff | ○ | lom — ODLOŽENO (Sez. 44): plocha lomu ≠ hrana srázu (201 značí linii s ticky). **Změřeno Sez. 55:** LS 1 = Σ1 (kamenolom; marginální) |
| `Ústí šachty, štoly` | bod | 203.2 Cave | ✓ | **Sez. 44** (`--landmarks`, týž symbol jako jeskyně — spec „…or mineshafts…") |
| `Stupeň__sráz` | linie | 104 Earth bank | ✓ | **Sez. 43** (`--linefeatures`, id 95 → 104 plná linie + jednostranné ticky; zemní sráz, NE skalní 201). **Σ981 = nejčastější dosud netáhnutá**. SV 71 / LS 393 / HS 377 |
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
| `Významný_nebo_osamělý_strom__lesík` | bod | 417 Prominent large tree | ✓ | **Sez. 43** (`--landmarks`, `LANDMARK_POINT_LAYERS_417`; osamělý strom = OB objekt, zelený kroužek). Drift v katalogu (◐) opraven Sez. 55 — implementace existuje (`map_landmark_to_isom` → 417) |
| `Orná_půda_a_ostatní_dále_nespecifikované_plochy` | plocha | 412 Cultivated land | ✓ | **Sez. 41** (`--surfaces`, KISS → 401); **Sez. 47-48 druhá vlna → 412** (žlutá + černý tečkový pattern, template 412.1; min. 9 mm² → 401). SV 16 / NL 7 / LS 21 / HS 57 / NV 11 |
| `Trvalý_travní_porost` | plocha | 401 Open land | ✓ | **Sez. 41** (`--surfaces`, louka → žlutá); odstín 401 vs 403 = gate nuance, KISS 401 |
| `Udržovaná_zeleň` | plocha | 402 / 402.1 | ✓ | **Sez. 41** (`--surfaces`, → 401 žlutá); **Sez. 53** štěpení podle `typ_pudy_k`: `PO` park/okrasná zahrada → **402 Open land with scattered trees** (žlutá + bílé tečky), `UZ` ostatní udržovaná zeleň → **402.1 …with scattered bushes** (žlutá + zelené tečky). LS 3 PO / 14 UZ. 402.1 = první „scattered bushes" zeleň z dat, gate neporušuje (mirror 406) |
| `Ovocný_sad__zahrada` | plocha | 520 Area that shall not be entered | ✓ | **Sez. 41** (`--surfaces`, KISS → 401); **Sez. 48 → 413 Orchard, Sez. 49 oprava → 520 olivová**: v ČR krajině jde převážně o zahrady u rodinných domů/chalup — oplocené, nepřístupné → out-of-bounds, ne běhatelný sad (rozhodnutí uživatele). SV 167 / NL 4 / LS 700 / HS 158 / NV 52 přesunuto do 520 |
| `Liniová_vegetace` | linie → plocha | 406 Vegetation: slow running | ✓ | **Sez. 45** (`--treerows`, id 15 → stromořadí jako „lineární les": osa linie → buffer → úzký světle zelený pás, šířka 0,7 mm, min. plocha 1,0 mm²). **416 byla Sez. 43, oprava → 406 Sez. 45** (verify spec: 416 Distinct vegetation boundary = HRANICE porostů / kraj lesa, NE řada stromů; ISOM kreslí alej plošně nebo body 417/418, my plošně — data nesou jen osu). První zelená vegetační plocha, gate neporušuje (tvrdý objekt z dat). SV 83 / HS 121 (Σ273) |
| `Vinice` | plocha | (414 Vineyard) | ✗ | vzácné v OB lese |
| `Chmelnice` | plocha | (414 obdoba) | ✗ | vzácné |
| `Hranice_užívání_půdy` | linie | (415 cultivation boundary) | ✗ | administrativní hranice využití |
| `Ostatní_plocha_v_sídlech` | plocha | 501.1 | ✓ | **Sez. 54: HOTOVO → 501.1 Paved area bez obrysu.** Administrativní výplň zastavěného území: obří polygon (2371/1734/494 ha) se STOVKAMI DĚR (571/692/578…) pro budovy/zeleň/cesty. **Podpora děr (holes) dodělána Sez. 54** (parser `geom_to_polygons` vrací vnitřní prsteny, rastr even-odd scanline vyřízne výřezy, omap hole-flag) → 501.1 vyplní jen volné plochy mezi budovami (10 % výseku, ne 41 % záplava). Z-order vespod (pod 520 RÚIAN parcelami); barva „Dolní hnědá 50%" (rastr `C_PAVED`, omap color priority 35 dole, aby silnice vynikly) |
| `Hřbitov` | plocha | 520 Area that shall not be entered | ✓ | **Sez. 41** (`--surfaces`, olivová); ISOM nemá vlastní hřbitov → 520. **Olivová 520 má od Sez. 42 i RÚIAN privátní pozemky + areály 114** |
| `Areál_účelové_zástavby` | plocha | 520 / 501 | ✓ | **Sez. 42** (audit land-cover; `--surfaces`). `typzast_k` 62 typů: asfalt (408 autobus. nádraží/409 čerpačka) → 501, vše ostatní (škola/hřiště/sport/kasárna/průmysl…) → 520. Řeší „bílá hřiště/kasárna" (test LS) |

## 9. Budovy a stavby plošné (ISOM 521–525)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Budova_jednotlivá_nebo_blok_budov__plocha_` | plocha | 521 Building | ✓ | plošná budova (vč. vodojemu zemního) |
| `Rozvalina__zřícenina` | plocha | 523 Ruin | ✓ | **Sez. 43** (`--buildings`, id 103; čárkovaný obrys bez výplně; `podtypob`=rozvalina). Milštejn ad. SV 8 / LS 7 / HS 5 (Σ20) |
| `Budova_jednotlivá_nebo_blok_budov__bod_` | bod | (521) | ✗ | v lesních výsecích prázdná (Sez. 18; probe Sez. 43: 0 ve všech 5) |
| `Kůlna__skleník__fóliovník__přístřešek` | plocha | 521 Building | ✓ | **Sez. 42** (audit; přidáno do `BUILDING_AREA_LAYERS` → 521, drobné stavby; LS budovy 8273→9123) |
| `Hrad` | plocha | 521 Building | ✓ | **Sez. 43** (`--buildings`, id 101 → 521 jako budova; HS 3) |
| `Zámek` | plocha | 521 Building | ✓ | **Sez. 43** (`--buildings`, id 102 → 521; **domov mládeže Krompach na SV** = bývalý zámek, 1882 m²; Σ3) |
| `Věžovitá_stavba` | plocha | 524 High tower | ✓ | **Sez. 43** (`--landmarks`, id 100; footprint ~3 m² → centroid → 524 bod, ne 521; Σ9) |
| `Tribuna` | plocha | — | ✗ | stadion, urbánní (probe Sez. 43: LS 2, jinde 0) |
| `Stavební_objekt_GIA` | plocha | — | ✗ | technický overlay vlastnictví (IČO; Σ813 ale ne mapový obsah) |
| `Stavební_objekt_zakrytý` | plocha | — | ✗ | technický |
| `Skládka` | plocha | — | ✗ | skládka (probe Sez. 43: 0 ve všech 5) |
| `Úložné_místo` | plocha | — | ✗ | technický |
| `Areál_účelové_zástavby` | plocha | 520 / 501 | ✓ | **Sez. 42** — viz sekce 8 (id 114, `typzast_k`); duplikátní řádek (zde dříve mylně ✗ „urbánní") sjednocen Sez. 43 |
| `Heliport` | plocha | — | ✗ | speciál (probe Sez. 43: LS 1) |

## 10. Bodové umělé / orientační prvky (ISOM 52x–53x, 417)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Kříž__sloup_kulturního_významu` | bod | 530 Prominent man-made feature | ✓ | **Sez. 43** (`--landmarks`, id 24 → 530 ring; boží muka/kříž). SV 33 / LS 53 / HS 50 (Σ149) |
| `Mohyla__pomník__náhrobek` | bod | 526 Cairn | ✓ | **Sez. 43** (`--landmarks`, id 25 → 526; mohyla/pomník/náhrobek). Σ47 |
| `Bunkr` | bod | asset (řopík) | ✓ | **použito Sez. 27** — LO37 → asset `ropik_10000.omap`, orientace k st. hranici (NE prostý 521) |
| `Věž__věžovitá_nástavba` | bod | 524 High tower | ✓ | **Sez. 43** (`--landmarks`, id 26 → 524; `podtypob`=věž kostela/kaple). SV 5 / LS 23 (Σ37) |
| `Vodojem_věžový` | bod | 524 High tower | ✓ | **Sez. 43** (`--landmarks`, id 27 → 524; **0 v 5 výsecích**, mapováno pro úplnost) |
| `Větrný_mlýn` | bod | 524 High tower | ✓ | **Sez. 43** (`--landmarks`, id 32 → 524; **0 v 5 výsecích**, pro úplnost) |
| `Větrný_motor` | bod | 524 High tower | ✓ | **Sez. 43** (`--landmarks`, id 33 → 524; **0 v 5** kromě LS 1, pro úplnost) |
| `Silo` | bod | 524 High tower | ✓ | **Sez. 43** (`--landmarks`, id 28 → 524; **0 v 5 výsecích**, pro úplnost) |
| `Těžní_věž` | bod | 524 High tower | ✓ | **Sez. 43** (`--landmarks`, id 30 → 524; **0 v 5 výsecích**, pro úplnost) |
| `Tovární_komín` | bod | 524 High tower | ✓ | **Sez. 52** (`--landmarks`, id 31 → 524; vysoká štíhlá stavba jako věž/silo; atribut `vyska_obj` nevyužit — KISS). LS 12 / SV 1 |
| `Lyžařský_můstek` | linie | — | ✗ | speciál (probe Sez. 43: LS 1, jinde 0) |

## 11. Bariéry a ohrazení (ISOM 105, 513–518)

| Vrstva | Geom | ISOM | Stav | Pozn. / proč ne |
|---|---|---|---|---|
| `Zeď` | linie | 513 Wall | ✓ | **Sez. 43** (`--linefeatures`, id 39 → 513 plná linie; `typzed` null → KISS). SV 16 / LS 136 (Σ172) |
| `Hradba__val__bašta__opevnění` | linie | 513 Wall | ✓ | **Sez. 43** (`--linefeatures`, id 38 → 513; kamenné historické opevnění). HS 15 (zřícenina hradu) |
| `Zábrana` | bod | 519 Crossing point | ✓ | **Sez. 52** (`--barriers`, id 54 → 519; jediný typ `typ_k=Z` „Závora, brána"). Mapuje se JEN bod ležící na zdi 513 (≤ 5 m) = skutečný průchod plotem; závory na cestách se zahodí. Verify Sez. 52: 2/66 na LS (medián 183 m od zdi). Zeď 513 se pod brankou přeruší (ISOM „line broken at crossing point") |

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
| ✓ použito | ~46 | cesty + voda + budovy + vedení + řopíky (Sez. 16–27) + železnice/kolejiště/**tramvaj** (28/31) + skály (30) + mosty/tunely/lávky (32–33) + lesní průseky (36) + **plošný pokryv: open land→401, hřbitov→520, parkoviště→501 (Sez. 41)** + **areály 114→520/501, kůlny 105→521 (Sez. 42)** + **RÚIAN privátní pozemky→520 (Sez. 42, `ruian.py`)** + **Sez. 43 (systematický audit katalogu): zámek/hrad→521, zřícenina→523, věž/věžovitá stavba/vodojem/silo/těžní/mlýn/motor→524, mohyla→526, kříž→530, strom→417, sráz→104, zeď/hradba→513** + **Sez. 44 (dávka 4 vodní/mokřady): bažina+rašeliniště→308 (`--marsh`), pramen→312, jeskyně+šachta→203.2, nádrž→311 (`--landmarks`)** + **Sez. 45: stromořadí `Liniová vegetace`→406 lineární les (`--treerows`, oprava 416→406)** + **Sez. 52: komín→524, zábrana→519** + **Sez. 53-54: udržovaná zeleň→402/402.1, ostatní plocha v sídlech→501.1 (holes)** + **Sez. 55: lanovka/vlek+stožár→510 (`--powerlines`, mirror el. vedení)** |
| ◐/○ odloženo | ~10 | **se ZMĚŘENÝMI počty (Sez. 55, `temp/probe_remaining_layers.py`):** balvany-linie 208 (Σ14: SV 7/HS 3/NV 4), podjezd 519 (Σ12: LS 11), hráz 528 (Σ13: legenda mapy + sporné), brod 519 (Σ6), vodopád 313 (Σ2), lom 201 (Σ1: LS), suť 210 (Σ1) — viz akční seznam |
| ○ možné | ~10 | okrajově relevantní (lanovka přesunuta do ✓ Sez. 55; rokle 107 Σ0, silnice ve výstavbě Σ0, …) |
| ✗ mimo doménu | ~80 | administrativa, POI, geodetické body, urbánní, vegetace gate, pomocné kreslicí linie |

> **Verify-against-source data-driven (Sez. 43):** výskyt VŠECH 149 vrstev změřen napříč 5
> DEV_LOCATIONS (`returnCountOnly`, `temp/probe_all_layers.py`) → stav každého řádku se opírá
> o reálný počet, ne odhad od stolu. Censure! (potřetí) „chybí X → to nemapujeme": tabulka teď
> garantuje, že u KAŽDÉ vrstvy s ISOM ekvivalentem je buď implementace, NEBO tvrdý doložený důvod
> (vegetace gate / administrativa / 0 výskytů v 5 reprezentativních výsecích). Paměť `geoportal-data-completeness`.

### Akční seznam kandidátů — stav po Sez. 44 (dávka 4)

1. ~~`Bažina, močál` → 308 Marsh~~ **HOTOVO Sez. 44** (`--marsh`; id 131, NV 15 / HS 10 / NL 9 / SV 5).
2. ~~`Zdroj podzemních vod` → 312 Spring~~ **HOTOVO Sez. 44** (`--landmarks`; id 19, Σ65 sedí na probe).
3. ~~`Vstup do jeskyně`/`Ústí šachty, štoly` → 203.2 Cave~~ **HOTOVO Sez. 44** (`--landmarks`; id 11/34, Σ9).
4. **`Přehradní_hráz__jez` → 528** (id 22, Σ13) — **ODLOŽENO Sez. 44**: 528 vyžaduje definici v legendě mapy (ruční krok kartografa), mapování hráz↔528 sporné (jez = spíš přerušení toku). Vyžaduje rozhodnutí uživatele.
5. ~~`Nadzemní zásobní nádrž` → 311~~ **HOTOVO Sez. 44** (`--landmarks`; id 108, Σ8 = LS 6 + HS 2). **`Povrchová_těžba__lom` → 201** (id 118, Σ1) — **ODLOŽENO**: plocha lomu ≠ hrana srázu (201 = linie s ticky dolů), Σ1 marginální.
6. ~~`Rašeliniště (plocha)` → 308~~ **HOTOVO Sez. 44** (`--marsh`, spolu s bažinou).
7. ~~`Lanová dráha, lyžařský vlek` + `Stožár lanové dráhy` → 510~~ **HOTOVO Sez. 55** (`--powerlines`, id 72/61; NL 2 / LS 1 lanovka, mirror el. vedení).
8. *(○ druhá vlna, ZMĚŘENO Sez. 55)* brod 519 (Σ6) / podjezd 519 (Σ12, LS 11; verify spec) / vodopád 313 (Σ2) / balvany-linie 208 (Σ14; nový area pattern) / kótovaný bod (SKIP, viz níže).

> **Korekce Sez. 55 — „katalog vyčerpán" (Sez. 52) byl nepřesný.** Sez. 52 prohlásil katalog za
> vyčerpaný, ALE ○ kandidáti lanovka/lom/brod/podjezd/hráz NEBYLI změřeni jako Sez. 43 (jen odhad
> „hory / Σ1"). Probe Sez. 55 (`temp/probe_remaining_layers.py`, `returnCountOnly` 5 lokalit) ukázal
> nenulový výskyt: lanovka NL 2/LS 1 (→ HOTOVO), balvany-linie Σ14, podjezd Σ12, hráz Σ13, brod Σ6.
> Lekce: „vyčerpáno" tvrď až po měření, ne od oka (paměť `verify-data-not-assume`).

**Kótovaný bod (id 9, Σ353) — SKIP s odůvodněním (Sez. 43):** vrstva nese JEN atribut `vyska`
(nadm. výška), žádný typ ani fyzickou značku → je to **virtuální výškopisný bod**, ne fyzický objekt
v krajině (na rozdíl od šrafované nivelační značky). OB mapy výškové kóty zpravidla nekreslí (zahltily
by mapu čísly). ISOM 603 Spot height by byl technicky možný, ale obsahově nevhodný → vědomě nekreslíme.
(Geodetické body bodového pole 6/7/8 jsou naopak fyzické čepy, ale = geodetická infrastruktura, ✗.)

> Každý kandidát = nová vrstva v `*_LAYERS` + mapovací funkce + render styl + verify-against-source
> na reálném výseku (atributy → ISOM před renderem). Po ověření přesunout řádek na ✓ a doplnit do `data-sources.md`.
