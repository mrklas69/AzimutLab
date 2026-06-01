# AzimutLab

A lab for cartography & orienteering map intelligence — tools, experiments, and a
knowledgebase. **Not one application: a set of them**, sharing a common understanding
of what an orienteering map *is*.

**Status: phase B (umbrella). First real code (since session 4): a procedural synthetic-map
generator in `generator/` (promoted from `sandbox/generator-poc/` in session 39) — feeds UC5
training with free ground-truth. Being rebuilt
"better, layer by layer" (session 11): currently contours + terrain-aware paths (§9, Dijkstra
least-cost — traverse slopes, don't climb) + knoll/depression point symbols (ISOM 2017-2 codes
109/110/111); vegetation/marsh/boulders were dropped (looked artificial → would hurt the feeder's
domain gap). Draws real terrain from ČÚZK DMR 5G (`--terrain real`) and — since session 16 — real paths from
ČÚZK ZABAGED Polohopis (ArcGIS REST since session 26; `--paths real`, ISOM 502-506), — since session 17 — real
water from the same `zabaged.py` connector (`--water real`, watercourses ISOM 304/305/306 + water bodies 301,
incl. swimming pools from `Pozemní_nádrž` since session 27), and — since session 18 — real buildings
(`--buildings real`, ISOM 521), drawn as **RAW footprints exactly like water** (session 27 dropped the earlier
level-1 generalization + level-2 displacement — they distorted the true shape; faithful raw data serves the feeder
better — *generalize only with evidence*), and — since session 24 — real power lines & cableways/ski-lifts
(`--powerlines real`, ISOM 510 "Power line, cableway or skilift", cross-ticks on real pylons; cableways
merged session 55), real pillboxes (`--ropiky real`, Czechoslovak
fortification `Bunkr` LO37 as an asset, oriented toward the nearest state border, since session 27), and
— since session 28 — real railways (`--railways real`, `Železniční_trať`+`_vlečka` → ISOM 509 combined
symbol) and railway yards (`--paved real`, `Kolejiště` → ISOM 501 paved area; the "ten parallel tracks"
at a station are one area in the data, not lines; since session 54 also `Ostatní plocha v sídlech` → **501.1
paved area without bounding line** — the administrative fill of built-up areas, drawn as a base layer beneath
everything, its hundreds of holes for buildings/greenery/roads cut out via the new **hole support** — see below),
and — since session 29 — auxiliary contours
(form lines, ISOM 103) derived from the DMR where terrain is gently sloped yet curved (drawn sparingly,
not as intermediate contours, per the ISOM rule); — since session 30 — real rocks/boulders
(`--rocks real`, ISOM 204/207/206, plus 208 boulder field since session 57 — line of boulders
buffered into a strip filled with random triangles); — sessions 31–33 — real bridges/tunnels/footbridges
(`--bridges real`, ISOM 512/512.2, raster unified with the `.omap` two-parallels layout in session 35);
and — session 36 — real forest rides (`--rides real`, `Lesní průsek` → ISOM 508 Narrow ride,
dashed line, no runnability background as vegetation is a UC5 prediction, not data); and — since session 41 —
real land cover (`--surfaces real`: open land meadow → ISOM 401 yellow; managed greenery (`Udržovaná zeleň`)
split by attribute `typ_pudy_k` since session 53 → park/ornamental garden → ISOM 402 Open land with scattered
trees (yellow + white dots), other managed greenery → ISOM 402.1 with scattered bushes (yellow + green dots);
arable field → ISOM 412 Cultivated land (yellow + black dot pattern, since session 47-48); orchards/gardens
(`Ovocný sad, zahrada`) → ISOM 520 olive out-of-bounds since session 49 (correcting the session-48 413 Orchard —
in the Czech landscape these are fenced gardens around houses/cottages, off-limits to runners, not runnable orchards);
ISOM 520 olive out-of-bounds = cemetery ∪ orchards/gardens ∪ private land ∪ utility-zoning compounds ∪ quarry (`Povrchová těžba, lom`, session 56 — fenced extraction site; a polygon, so 520 not the line-symbol 201 cliff); car parks/asphalt
→ 501 via `--paved`; drawn at the very bottom of the z-order, forest stays white = vegetation gate); and — since
session 42 — real **private land** as olive 520 from a second ČÚZK source, **RÚIAN cadastre** (`ruian.py`: parcels
of land-use type garden + built-up area → off-limits to runners), plus utility-zoning compounds (ZABAGED layer 114:
schools/sports grounds/barracks/industry → 520, asphalt transport areas → 501) and small structures (sheds → 521);
and — since session 43 (a **systematic catalogue audit** triggered by a missing chateau = youth hostel: the user's
recurring "it's missing / we don't map that" anti-pattern, fixed for good by data-driven counts of all 149 layers
across the 5 dev locations) — castles/chateaux → 521, **ruins** → 523 (Milštejn et al., dashed outline),
towers/water-towers/silos/… → 524, cairns/memorials → 526, crosses/wayside shrines → 530, prominent trees → 417
(`--landmarks`), and earth banks → 104, walls/ramparts → 513 (`--linefeatures`);
since session 44 (catalogue batch 4: water/wetland) marshes+peat bogs → 308 Marsh (`--marsh`, blue horizontal hatch),
springs → 312, cave/mineshaft entrances → 203.2, water tanks → 311 (`--landmarks`); since session 45 tree rows
(`Liniová vegetace`) → 406 Vegetation: slow running (`--treerows`, "linear forest": axis→buffer→strip; corrects the
earlier 416 = vegetation *boundary*, which was semantically wrong for a row of trees);
since session 52 factory chimneys → 524 (`--landmarks`) and barriers (`Zábrana`) → 519 Crossing point (`--barriers`,
only points lying on a 513 wall = actual gate through a fence; the wall is broken under the gate) — among the last simple
candidates, but the catalogue is **not** exhausted (session 55 re-probed: boulder field 208, underpass/ford 519, weir 528 still remain).
Since session 62 **forest age → green** (`--forest-age`, `forest.py`): AOPK stand polygons, attribute `BARVA` = ordinal age →
ISOM 406/408/410 (youngest→410 fight, …, old/non-forest→white). This is a **PROXY / prediction** (age ≠ true runnability —
the open-LiDAR vegetation gate is closed, session 59), marked `proxy:true`; the first prediction step toward UC5 vegetation.
`zabaged.py`, `ruian.py` and `forest.py` (siblings of `dmr.py`, sharing `arcgis.py` REST transport) are the real UC2 connectors. Exports contours (incl. form lines) + paths + rides + water + paved + buildings + powerlines + railways + rocks + bridges + surfaces + landmarks + linefeatures + marsh + treerows + forest age + barriers + points
to `.omap` (contours also to GeoJSON) — template-based on a
clean self-made ISOM 2017-2 template (session 14), inheriting faithful point geometry (110 ellipse,
111 arc) + the full symbol library. Since session 23 the map extent is parametric (`--width-km`/`--height-km`,
any location & aspect ratio; resolution held constant) and `zabaged.py` fetches the full relevant set of ZABAGED
layers, not a curated subset (e.g. `Silnice_neevidovaná` — unregistered/forest asphalt roads, previously missing;
**complete 149-layer ZABAGED→ISOM catalogue in `docs/kb/zabaged-isom-catalog.md`**, session 24) —
the real branch is conceptually a *map predictor* (`generate_map`): projection of available
geodata now, AI prediction of missing symbols from similar localities later (UC5). Session 24 also split the real
branch into two toggleable phases (`pseudorealistic`, default on; `--only-real` off): **phase 1 = projection** of
hard data, **phase 2 = pseudorealistic decoration** of symbols not in the data (today: even power-line ticks
where no pylon is recorded; future: vegetation). Session 25 realised the long-planned rename
`generate()` → `synthesize_pseudorealistic_map(lat, lon, w_km, h_km, only_real=False, out_dir, *, …)`
(renamed back to `generate_map` in session 39 — "generator" won out in conversation, and it is the
umbrella for future generators, not just this synthesis)
(the noise/Option-1 branch + per-layer toggles kept as a keyword-only tail) and added `--location`
dev shortcuts (`DEV_LOCATIONS`: Soví vrch / Nová louka / Lidové sady, all at 6×4 km; Lidové sady
rendered as classic ISOM — an ISSprOM/sprint pipeline is a separate future task). Verify-against-source
on 6×4 km extents exposed a hard ČÚZK ArcGIS WFS cap of 1000 objects/request — **fixed in session 26 by
switching `zabaged.py` from WFS to ArcGIS REST `MapServer/<id>/query`** with reliable `resultOffset` paging
(dense towns now complete: SV 1078, LS 8273 buildings). Session 27 added a `logging` progress/summary to
`generate_map` (CLI shows it; batch stays quiet). Session 54 added **hole support** across all area layers
(`geom_to_polygons` now returns GeoJSON inner rings; the raster cuts them out via even-odd scanline, the
`.omap` via hole-flags) — without it a large administrative polygon (501.1) would flood the extent. The same
session marked the project's first **large-area base fill beneath many other symbols** (501.1), which the
default ISOM Mapper palette couldn't handle: a custom colour "Dolní hnědá 50%" was added to
`template_classic.omap` at the very bottom of the colour-table priority so roads/paths stay on top (see
`docs/GLOSSARY.md` and the `omap-colortable-base-fill-priority` lesson).**

## What this is

AzimutLab is an umbrella project that grew out of [Pic2Omap](../Pic2Omap) (raster
orienteering map → vector `.omap`). Where Pic2Omap is one pipeline, AzimutLab is the
workbench around it: data connectors, models that "understand" maps, generators,
restoration — and the knowledgebase that ties them together.

It starts deliberately small (a knowledgebase + experiments) and is designed to **grow into
a monorepo** that eventually absorbs Pic2Omap as one app. Foundations before curtains.

## Use cases (the map)

The five use cases are **not a flat list — they form a dependency DAG.** Enablers
(data + model understanding) sit under the applications. Canonical detail and rationale:
[`docs/architecture.md`](docs/architecture.md).

```
META     UC1  Knowledgebase + Sandbox            ← where everything is recorded
          │
ENABLER  UC2  Data connectors    UC5  Models that "understand maps"
         (LIDAR/ortofoto/ČÚZK)        (palette separation, symbol classification)
          │                            │
APP      UC3  Restoration         UC4  Generators (I random / II inspired / III pic2omap)
         (de-purple, de-crease)
```

| UC | Name | Scope | Status |
|----|------|-------|--------|
| UC1 | Knowledgebase + Sandbox | Collect info, links, sources; isolated experiments; the DAG itself | ◐ founding (MVP) |
| UC2 | Data connectors | Survey + connect 3rd-party sources (LIDAR, ortofoto, QGIS, ČÚZK ZABAGED/RÚIAN/ZTM, geoportál) | ◐ connectors live (DMR 5G terrain, ZABAGED paths + water + buildings + power lines + land cover + point/line landmarks + marshes/springs/caves/tanks, RÚIAN cadastre parcels; full 149-layer catalogue data-driven audited, sessions 43–44) |
| UC5 | Map-understanding models | 100 % palette separation; point/line/area ISOM symbol classification | ☐ |
| UC3 | Restoration | Strip the purple race layer (controls, refreshments, OOB) + digital restore of worn printed maps | ☐ |
| UC4 | Generators | I: plausible-random · II: inspired (by image / coords) · III: **precise = Pic2Omap** (muddy scan → OCD/OMAP) | ◐ (I = PoC generator; III = Pic2Omap) |

UC4-III is the project's summit and currently lives in Pic2Omap. Full UC4-I
(plausible-random, not a random pile of ISOM symbols) is still the hardest goal — but as a
**synthetic-data generator with free ground-truth it became an enabler-feeder for UC5**
(session 4 reframe), no longer "the very end". Code: `generator/`.

## Relationship to Pic2Omap

**Decision (sezení 1): umbrella growing into monorepo (B→A).** AzimutLab is today a
meta-layer; Pic2Omap keeps running as its own repo. Once the UC5 core matures enough that
Pic2Omap actually consumes it, Pic2Omap is pulled in as `apps/pic2omap`. This keeps
Pic2Omap's 19 sessions of history and avoids building curtains before walls.

## Repository layout

```
CLAUDE.md              # thin project overlay (AI rules only — facts live here in README)
README.md              # this file — identity, DAG, status
docs/
  PROMPTS.md           # %BEGIN / %END macros
  architecture.md      # canonical DAG: layers, UC dependencies, Pic2Omap relationship
  diary/YYYY-MM-DD.md  # session log
  TODO.md / DONE.md    # work tracking
  DIARY.md             # session index
  IDEAS.md             # the 5 UC as a DAG, MVP cut, pending decisions
  RESEARCH.md          # survey of existing tools / methods
  GLOSSARY.md          # project terminology
  kb/                  # the knowledgebase (heart of UC1)
    data-sources.md    #   UC2 survey: ČÚZK / geoportál / ortofoto / LIDAR + licences
    isom-issprom.md    #   symbol semantics, spec links
    tools-models.md    #   CoVe, OCAD, Karttapullautin, U-Net, …
    generator-procedural.md   # UC4-I synthetic map generator spec (free-GT training data)
    zabaged-isom-catalog.md   # all 149 ZABAGED Polohopis layers → ISOM mapping or reason-not-used (session 24)
connectors/            # UC2 enabler: real-geodata connectors (pulled out of sandbox, session 16)
  dmr.py               #   ČÚZK DMR 5G elevation (ArcGIS ImageServer); --terrain real
  zabaged.py           #   ČÚZK ZABAGED Polohopis paths/forest rides/water/paved/buildings/power lines/railways/rocks/bridges/pillboxes/land cover/utility compounds/sheds/marshes/springs/caves/tanks/tree rows/chimneys/barriers (ArcGIS REST, GeoJSON); --paths/--rides/--water/--paved/--buildings/--powerlines/--railways/--rocks/--bridges/--ropiky/--surfaces/--landmarks/--linefeatures/--marsh/--treerows/--barriers real
  ruian.py             #   ČÚZK RÚIAN cadastre parcels by land-use → private land → olive 520 (session 42)
  forest.py            #   AOPK "Les_Mapy" stand polygons; BARVA = age → ISOM 406/408/410 green PROXY/prediction; --forest-age (session 62)
  arcgis.py            #   shared low-level ArcGIS REST transport (paging+cache+GeoJSON parsers; DRY for zabaged+ruian+forest, session 42/62)
generator/             # UC4-I/UC5 pillar: OB-map generator (promoted from sandbox/generator-poc, session 39)
  generator.py         #   generate_map(): contours + paths + water + buildings + rocks + bridges + … + masks
                       #     consumes connectors/ (real terrain, paths, water, …); adds them to sys.path
                       #   template_classic.omap: clean ISOM 2017-2 template for .omap export
asset/                 # shared map assets (řopík pillbox .omap)
resources/             # real OB maps — input/reference (gitignored, 3rd-party copyright)
maps/                  # generated maps — output, maps/<location>/ (gitignored, regenerable)
```

(All working documents — TODO/DONE/DIARY/IDEAS/RESEARCH/GLOSSARY — live under `docs/`
since session 47; only README.md and CLAUDE.md stay at the repo root.)

## Docs

Working documents are in Czech (per the global conventions):

- [docs/architecture.md](docs/architecture.md) — canonical UC DAG & layering
- [docs/GLOSSARY.md](docs/GLOSSARY.md) — project terminology
- [docs/IDEAS.md](docs/IDEAS.md) — design brainstorm
- [docs/RESEARCH.md](docs/RESEARCH.md) — survey of tools / methods / sources
- [docs/DIARY.md](docs/DIARY.md) — session log (detail in `docs/diary/`)
- [docs/TODO.md](docs/TODO.md) / [docs/DONE.md](docs/DONE.md) — work tracking

## License

Not yet decided.
