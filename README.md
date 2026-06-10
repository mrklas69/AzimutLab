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
buffered into a strip filled with random triangles; **since session 63 the 206 rock areas come from
DMR 5G slope** — `rock_relief.py` thresholds slope ≥46° and morphologically merges walls into blocks,
replacing the generalized ZABAGED rock blob with faithful tower/passage structure, verified against Mapy.com);
— sessions 31–33 — real bridges/tunnels/footbridges
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
(`--landmarks`), and earth banks → 104, walls/ramparts → 513, erosion gullies → 107 (`--linefeatures`, session 58; rare on the dev locations);
since session 44 (catalogue batch 4: water/wetland) marshes+peat bogs → 308 Marsh (`--marsh`, blue horizontal hatch;
since session 99 a pseudo phase-2 split reclassifies ~55 % to **310 Indistinct marsh** — dashed sparser hatch — as ČÚZK
carries no distinctness attribute, the same random-to-statistical-rate device as the 516 fence),
springs → 312, cave/mineshaft entrances → 203.2, water tanks → 311 (`--landmarks`); since session 45 tree rows
(`Liniová vegetace`) → 406 Vegetation: slow running (`--treerows`, "linear forest": axis→buffer→strip; corrects the
earlier 416 = vegetation *boundary*, which was semantically wrong for a row of trees);
since session 52 factory chimneys → 524 (`--landmarks`) and barriers (`Zábrana`) → 519 Crossing point (`--barriers`,
only points lying on a 513 wall = actual gate through a fence; the wall is broken under the gate) — among the last simple
candidates, but the catalogue is **not** exhausted (session 55 re-probed: boulder field 208, underpass/ford 519, weir 528 still remain).
Predictive vegetation (green 406/408/410 + 403 rough open) comes **only from colour separation of a real OB map**
(`predict_areas_sjtsk`, sessions 82/83) — the AOPK forest-age proxy (sessions 62–91) was **archived in session 102** as a
documented dead end (33 % corpus coverage, IoU 0.12, 3.3× over-prediction); pseudorealistic vegetation for scan-less
locations is a future direction. DEV `--location` maps therefore draw a white forest (no separation source).
`zabaged.py` and `ruian.py` (siblings of `dmr.py`, sharing `arcgis.py` REST transport) are the real UC2 connectors. Exports contours (incl. form lines) + paths + rides + water + paved + buildings + powerlines + railways + rocks + bridges + surfaces + landmarks + linefeatures + marsh + treerows + barriers + points
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
dev shortcuts (`DEV_LOCATIONS`: SV Soví vrch / NL Nová Louka / LS Lidové sady all at 6×4 km,
HS Hrubá Skála 5×5 km (square), NV Novina 3×5 km (portrait) — varied extents test non-1.5:1 clipping;
Lidové sady rendered as classic ISOM — an ISSprOM/sprint pipeline is a separate future task). Verify-against-source
on 6×4 km extents exposed a hard ČÚZK ArcGIS WFS cap of 1000 objects/request — **fixed in session 26 by
switching `zabaged.py` from WFS to ArcGIS REST `MapServer/<id>/query`** with reliable `resultOffset` paging
(dense towns now complete: SV 1078, LS 8273 buildings). Session 27 added a `logging` progress/summary to
`generate_map` (CLI shows it; batch stays quiet). Session 54 added **hole support** across all area layers
(`geom_to_polygons` now returns GeoJSON inner rings; the raster cuts them out via even-odd scanline, the
`.omap` via hole-flags) — without it a large administrative polygon (501.1) would flood the extent. The same
session marked the project's first **large-area base fill beneath many other symbols** (501.1), which the
default ISOM Mapper palette couldn't handle: a custom colour "Dolní hnědá 50%" was added to
`template_classic.omap` at the very bottom of the colour-table priority so roads/paths stay on top (see
`docs/GLOSSARY.md` and the `omap-colortable-base-fill-priority` lesson).** Session 98 fixed a measured
**olive 520 over-projection** (RÚIAN cadastre fragments built-up land into thousands of tiny parcels — compass
9× over-draw): the olive areas are now **dissolved into contiguous blocks** (contourpy on the raster mask, no
`shapely`; compass 9×→1.3×), and a **fence 516** is drawn pseudo-realistically (phase 2) around the built-up
blocks ≥ 0.5 ha — straightened (RDP) with tags inside the enclosure (ISOM spec), since ZABAGED carries no fence layer.

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
| UC5 | Map-understanding models | 100 % palette separation; point/line/area ISOM symbol classification; runnability prediction | ◐ corpus built & curated, baseline trained then reframed (session 68 connector + gates; session 70 scaled to **268 maps**; session 71 `map_gt` olive→out-of-bounds GT fix + `curate.py` taxonomy/manifest → **216 keep classic** foot-O training core; sessions 72–73 GT cleanup: purple course overprint + off-map layout → label 255 ignore; sessions 74–77 model pipeline: %THINK + step 0 smoke test (PyTorch cu128 on Blackwell RTX 5070) → aligned (X,Y) pairs + geographic split 145/31/31 + ~8 125 tiles; session 78 **baseline U-Net val mIoU 0.25 = RGB-only task ceiling**; **session 79 reframe**: the real goal "understand maps" = `reconstructor()` (map scan → `.omap`) fed by `generator()` (real + predict parts), and the ortho→runnability direction is **archived as a documented dead-end**, not the main line — see `docs/architecture.md`; session 88 builds the **first live reconstructor model `Png2Area`** (`model/png2area/`, U-Net 16 area codes + background, map scan → area label raster; archive moved to `model/runnability/`); **session 90 — first working Png2Area reconstructor**: main line unblocked (first session on corpus+CUDA machine); Branžež worst-case E2E `build_pair` 357 s (rotated quad aligned), overfit gate passed, nightly `build_pairs` + resume → **196/207 pairs** (95 %), `build_tiles` train 137/val 30/test 29 (geo-split, no leak), full training 40 ep → **test mIoU 0.621 ≈ val 0.629** (vs runnability baseline 0.25); buildings `521` rescued 0.00→0.68 by median-freq weights + data (Sez. 90 prediction confirmed); **session 91 stabilization** → **test mIoU 0.640 / val 0.654** (weight cap @10 + cosine LR, loss spikes gone; rare `208` data ceiling confirmed → class-balanced expansion); **session 92** — first vegetation area class above green: **403 Rough open** from colour separation; **DoD: `generator()` is done only at ≥ 90 % ISOM symbol coverage of the 5 sample maps** in `resources/` (`generator/measure_dod.py` driver, crosswalk-aware; **separation baseline 43 %**, sessions 94–95) — what the generator does not draw the reconstructor can never learn, so **extending coverage is a bigger lever than tuning the model**; **session 95 — ≥ 90 % is area-wise unreachable**: analytic cut (`compare_isom.symbol_geometry`) gives a **58 % area-only ceiling**, the rest are lines (18 types → Png2Line) and points (17 types → Png2Point), neither model exists yet → the path to 90 % runs through them, not through polishing areas; DoD baseline switched from the forest-age proxy to **colour separation** (the real pair-production path; the proxy 410 was fabrication — continuous 410 areas are not present in the maps); **session 100 — KPI redefined**: the binary DoD ≥ 90 % (unreachable 54 % ceiling, blind to incremental work — dissolve/marsh changes did not move it) is replaced as the primary `generator()` quantifier by the **proportional symbol-distribution similarity** (histogram intersection `Σ min(orig_share, gen_share)`, `measure_dod.py` default mode; DoD → `--dod` archive) — one number 0–100 %, robust to the bbox-envelope artefact; **baseline 46.1 %** (areas 60.9 / lines 47.7 / points 29.0 = Png2Point debt), target **55 % areas-only / ≥ 85 % with Png2Point+Png2Line** (61 % of symbol mass is lines+points); **session 101 — 416 Distinct vegetation boundary** drawn from inter-class boundaries of the predicted veg areas (length threshold 50 m) → **KPI 46.1 → 49.3 %** (lines sub 47.7 → 58.3); 403 measured and **rejected as a lever** (+0.1 pb — granularity gap: ČÚZK coarse multipolygons vs the cartographer's fine patches, KPI counts objects → the areas-only lever is now exhausted, confirmed 3× sessions 99–101); **session 106 — second live reconstructor `Png2Point` done** (`model/png2point/`, injected-symbol training + CenterNet heatmap, **test mF1 0.897**: 204 0.93 / 210 0.86); **session 107 — Png2Point points integrated into the generator**: pseudo-injection of 204 Boulder + 210 Stony ground into `gen.omap` on a **documented-rockiness mask** (206 DMR slope areas + real ZABAGED 204/207 boulders, dilated; slope alone ≠ rockiness → overshoot) calibrated on share → **KPI 50.3 → 59.1 % (+8.8 pb)**, points sub-KPI 18.4 → 54.3 %) |
| UC3 | Restoration | Strip the purple race layer (controls, refreshments, OOB) + digital restore of worn printed maps | ☐ |
| UC4 | Generators | I: plausible-random · II: inspired (by image / coords) · III: **precise = Pic2Omap** (muddy scan → OCD/OMAP) | ◐ (I = generator, Lab pillar — KPI 59.1 %; III = Pic2Omap) |

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
    hardware.md          #   machines (mrkla=RTX 5070 training rig, ntbhej=laptop); UC5 train/inference (session 74)
connectors/            # UC2 enabler: real-geodata connectors (pulled out of sandbox, session 16)
  dmr.py               #   ČÚZK DMR 5G elevation (ArcGIS ImageServer); --terrain real
  zabaged.py           #   ČÚZK ZABAGED Polohopis paths/forest rides/water/paved/buildings/power lines/railways/rocks/bridges/pillboxes/land cover/utility compounds/sheds/marshes/springs/caves/tanks/tree rows/chimneys/barriers (ArcGIS REST, GeoJSON); --paths/--rides/--water/--paved/--buildings/--powerlines/--railways/--rocks/--bridges/--ropiky/--surfaces/--landmarks/--linefeatures/--marsh/--treerows/--barriers real
  ruian.py             #   ČÚZK RÚIAN cadastre parcels by land-use → private land → olive 520 (session 42)
  arcgis.py            #   shared low-level ArcGIS REST transport (paging+cache+GeoJSON parsers; DRY for zabaged+ruian, session 42)
  livelox.py           #   UC5 corpus: real OB maps from Livelox → map.png + meta.json (georef, epsg from data) + blend.png (session 68)
  map_gt.py            #   UC5 corpus: runnability ground-truth (gt_labels/gt_vis) from real map via ISOM colour segmentation (session 68; olive 520 → label 0, session 71; purple course overprint → label 255 ignore, session 72; off-map layout — legend/table/title/paper — → label 255 ignore via colour detector, session 73 part B)
  curate.py            #   UC5 corpus: curation taxonomy + manifest (_curation.json) → keep set for training (session 71: 268 → 216 keep classic)
  split.py             #   UC5 corpus: geographic train/val/test split by bbox-overlap clusters (no leak) → _split.json; dirs_for() = loader contract (session 76)
generator/             # UC4-I/UC5 pillar: OB-map generator (promoted from sandbox/generator-poc, session 39)
  generator.py         #   generate_map(): contours + paths + water + buildings + rocks + bridges + … + masks
  rock_relief.py       #   ISOM 206 rock areas from DMR 5G slope (numpy+scipy+contourpy; --rocks real, session 63)
  separate.py          #   phase I: separate predictive areas (vegetation) from real Livelox map → polygons (sessions 82-85)
  pairs.py             #   phase I orchestrator: build_pair(cid) = real ČÚZK + separation → [scan.png, .omap] pair (sessions 83-86)
  degrade.py           #   phase II: degrade clean render → "scan" (CMYK misregistration/blur/paper/noise/JPEG; session 86)
  omap_raster.py       #   Y-pipeline: rasterize area ISOM symbols from .omap → label raster (Y for Png2Area; per-code, z-order, holes; session 87)
                       #     consumes connectors/ (real terrain, paths, water, …); adds them to sys.path
                       #   template_classic.omap: clean ISOM 2017-2 template for .omap export
model/                 # UC5 model code (sibling of connectors/generator, sys.path scripts; session 77). Three subdirs, two live reconstructors:
  runnability/         #   ARCHIVED ortho→runnability model (dead-end session 79; git-moved here session 88)
    tile.py            #     pre-tiling (X,Y) pairs → 512×512 (stride 256, reject <30% valid px) → resources/tiles/ + median-freq weights
    dataset.py         #     PyTorch loader over tiles + augmentation (D4 + brightness/contrast); ImageNet norm (session 78)
    train.py           #     U-Net/ResNet34 (smp), BF16, per-class IoU → resources/model/ (session 78; baseline val mIoU 0.25 = RGB-only ceiling)
  png2area/            #   LIVE Png2Area reconstructor (session 88): map scan → area label raster, first of the 3 OOM-geometry CV tasks
    tile.py            #     pre-tiling [scan.png, area_labels.png] pairs → 512×512 (no rejection — background is a class); 18 area codes + background from omap_raster; → resources/area_tiles/
    dataset.py         #     PyTorch loader (D4 + on-the-fly degrade augmentation + ImageNet norm, no IGNORE — Y is all-valid)
    train.py           #     U-Net/ResNet34, in→18 area codes + background, BF16, per-class IoU → resources/area_model/ (train on mrkla; session 103 test mIoU 0.568)
  png2point/           #   LIVE Png2Point reconstructor (sessions 105–106): map scan → point symbols, second of the 3 CV tasks
    inject.py          #     inject ISOM icons onto clean point_base render → GT for free + Gaussian heatmap splat (scope 204 Boulder / 210 Stony)
    dataset.py         #     PyTorch loader: reads point_base renders + random-crop 512, on-the-fly injection (infinite augmentation) + D4 + degrade
    train.py           #     U-Net (smp) + sigmoid heatmaps, focal loss, peak-NMS → F1 → resources/point_model/ (session 106 test mF1 0.897)
asset/                 # shared map assets (řopík pillbox .omap)
resources/             # real OB maps + derived training tiles (tiles/) — input/reference (gitignored, 3rd-party copyright)
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
