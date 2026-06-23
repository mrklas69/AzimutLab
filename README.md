# AzimutLab

A lab for cartography & orienteering map intelligence — tools, experiments, and a
knowledgebase. **Not one application: a set of them**, sharing a common understanding
of what an orienteering map *is*.

**Status: phase B (umbrella).** Active foundations are UC2 connectors, the UC4-I
`generator()`, and **three live reconstructors**. Generator KPI is **65.8%** (`KPI_3MAP_CANONICAL`,
session 152).
`Png2Area` has test mIoU **0.577** (21-class, session 156 retrain on the expanded scope;
real eval_real Bedř soft mIoU 0.525 / pixel-acc 0.887), `Png2Point` a 3-seed median mF1 **0.811**
(5 classes 204/210/417/419/**531**; session 158 added 531 Prominent man-made X — real transfer
Velbloud F1 0.708 = on par with 419, distinctive black X transfers like the green one), and
`Png2Line` step 1 (watercourse) test mIoU **0.774**. The
session-152 line scope expansion (306 + 309 + 508*) was retrained and **measured in session 156:
watercourse regressed on real scans (0.409→~0.26 IoU, 309 collapsed) → reverted to the 2-class
watercourse-only checkpoint** (2nd confirmation of session 133; dashed 508 is a domain gap).
Real-domain transfer is the limiting metric: `Png2Line` reads real scans (completeness **0.85–0.93**,
no collapse), strict IoU **0.409** after a per-class confidence threshold. **Direction &
phase gate live in [ROADMAP.md](docs/ROADMAP.md)** (`Generator()` → `Rekonstruktor()`; we
are in the `Generator()` phase). **Scan mining** (palette/masks/symbol candidates from real scans)
is part of `Generator()` when it feeds KOMPAS/coverage, not a phase-gate violation. Current work is tracked in [TODO](docs/TODO.md); history is
in [DONE](docs/DONE.md) and [DIARY](docs/DIARY.md).

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
         (LIDAR/ortofoto/ČÚZK)        (reconstructors: Png2Area/Point/Line, scan→.omap)
          │                            │
APP      UC3  Restoration         UC4  Generators (I random / II inspired / III pic2omap)
         (de-purple, de-crease)
```

Direction & phase gate are the SSoT of [ROADMAP.md](docs/ROADMAP.md): one axis
`Generator()` → `Rekonstruktor()` (scan → vector `.omap`). The 5-UC DAG below is the static
structure; where they differ, ROADMAP wins.

| UC | Name | Scope | Status |
|----|------|-------|--------|
| UC1 | Knowledgebase + Sandbox | Collect info, links, sources; isolated experiments; the DAG itself | ◐ founding (MVP) |
| UC2 | Data connectors | Survey + connect 3rd-party sources (LIDAR, ortofoto, QGIS, ČÚZK ZABAGED/RÚIAN/ZTM, geoportál) | ◐ connectors live (DMR 5G terrain, ZABAGED paths + water + buildings + power lines + land cover + point/line landmarks + marshes/springs/caves/tanks, RÚIAN cadastre parcels; full 149-layer catalogue data-driven audited, sessions 43–44) |
| UC5 | Map-understanding models | `generator()` → reconstructors for Area/Point/Line ISOM geometry | ◐ **216 curated classic maps**, geographic split without leakage. `Png2Area`: 20 ISOM codes + background (`N_AREA=21`, incl. 404/407/409 scan-pattern classes), synthetic test mIoU **0.577** (21-class retrain, session 156) at canonical 1.33 m/px; real eval_real Bedř soft mIoU **0.525** / pixel-acc **0.887**, Blatná per-shade **0.232** / soft **0.363** (new 404/407/409 transfer weakly — rare in CZ maps, model hallucinates them). `Png2Point` (204/210/417/419 since Sez. 128): 3-seed synthetic median mF1 **0.827**; real mF1 **0.43-0.57** — **419 strong 0.67-0.76**, 417 moderate 0.48-0.57, 204 stable, 210 still collapses. `Png2Line`: session-152 scope (306/309/508*) retrained + measured session 156 → **watercourse regressed → reverted to 2-class watercourse-only** (test mIoU 0.774, real IoU 0.409; dashed 508 domain gap, 2nd confirmation of Sez. 133). Pseudo points 204/210 **and 417/418/419** (Sez. 136-137, boulder principle) drawn into the generator off water/rock/buildings/paths/paved/railway with ISOM spacing. Generator KPI **65.8%** (`KPI_3MAP_CANONICAL`, session 152). **Phase gate (ROADMAP.md): we are in the `Generator()` phase — `Rekonstruktor()` + "degradace" are frozen words until KOMPAS is full.** Details in architecture/TODO/DONE. |
| UC3 | Restoration | Strip the purple race layer (controls, refreshments, OOB) + digital restore of worn printed maps | ☐ |
| UC4 | Generators | I: plausible-random · II: inspired (by image / coords) · III: **precise = Pic2Omap** (muddy scan → OCD/OMAP) | ◐ (I = generator, Lab pillar — KPI 65.8 %; III = Pic2Omap) |

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
azimutlab.toml         # globální kartografická nastavení projektu (např. varianta 416/416.1)
CLAUDE.md              # thin project overlay (AI rules only — facts live here in README)
README.md              # this file — identity, DAG, status
docs/
  PROMPTS.md           # %BEGIN / %END macros
  ROADMAP.md           # SSoT of direction & phase gate: Generator() → Rekonstruktor() (session 136)
  AUDIT_SUPERVISOR_*.md    # meta-audit by the strongest model: _PROMPT = repeatable assignment, dated issues (session 117)
  architecture.md      # canonical DAG: layers, UC dependencies, Pic2Omap relationship
  diary/YYYY-MM-DD.md  # session log
  TODO.md / DONE.md    # work tracking
  DIARY.md             # session index (active window; older in DIARY-archive.md)
  DIARY-archive.md     # archived session index (sessions 1–122)
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
  ortofoto.py          #   ČÚZK ortophoto basemap under generated map (ČÚZK sibling of dmr/zabaged, session 42)
  magnetic.py          #   grivation (S-JTSK grid → magnetic-north angle) for point+date → magnetic meridians (session 132)
  livelox.py           #   UC5 corpus: real OB maps from Livelox → map.png + meta.json (georef, epsg from data) + blend.png (session 68)
  map_gt.py            #   UC5 corpus: runnability ground-truth (gt_labels/gt_vis) from real map via ISOM colour segmentation (session 68; olive 520 → label 0, session 71; purple course overprint → label 255 ignore, session 72; off-map layout — legend/table/title/paper — → label 255 ignore via colour detector, session 73 part B)
  curate.py            #   UC5 corpus: curation taxonomy + manifest (_curation.json) → keep set for training (session 71: 268 → 216 keep classic)
  split.py             #   UC5 corpus: geographic train/val/test split by bbox-overlap clusters (no leak) → _split.json; dirs_for() = loader contract (session 76)
isom/                  # Shared ISOM symbol utilities: SVG symbol index + generator capability registry (real/mixed/pseudo/mapper_scan)
generator/             # UC4-I/UC5 pillar: OB-map generator (promoted from sandbox/generator-poc, session 39)
  generator.py         #   generate_map(): contours + paths + water + buildings + rocks + bridges + … + masks
  rock_relief.py       #   ISOM 206 rock areas from DMR 5G slope (numpy+scipy+contourpy; --rocks real, session 63)
  separate.py          #   phase I: separate predictive areas (vegetation) from real Livelox map → polygons (sessions 82-85)
  pairs.py             #   phase I orchestrator: build_pair(cid) = real ČÚZK + separation → [rgb.png, .omap] pair
  degrade.py           #   phase II: degrade clean render → "scan" (CMYK misregistration/blur/paper/noise/JPEG; session 86)
  omap_raster.py       #   Y-pipeline: rasterize area ISOM symbols from .omap → label raster (Y for Png2Area; per-code, z-order, holes; session 87)
                       #     consumes connectors/ (real terrain, paths, water, …); adds them to sys.path
  omap_export.py       #   inserts generator output into user's clean ISOM 2017-2 template (USED_CODES set)
  cut.py               #   geometric clip of gen output (.omap + render) to real map field (rotated quad / axis box; Sutherland-Hodgman; sessions 109/114/142)
  gen_backgrounds.py   #   switchable OOM basemaps into corpus gen.omap (session 104)
  measure_dod.py       #   KPI/KOMPAS driver: histogram-intersection of ISOM distribution gen vs sample maps (--table/--dod; primary quantifier, session 100)
  compare_isom.py      #   ISOM symbol coverage: our gen .omap vs real OB map (crosswalk + detect_version; session 91)
  compare_real_vs_gen.py #  machine compare of generator vs hand-mapped OB map (verify-against-source; session 37, stale-drop 69)
  stats.py             #   aggregates meta.json of all DEV_LOCATIONS → STATISTICS.md table
  batch.py             #   batch generation of mini dataset + preview mosaic; noise vs real modes via --terrain
  palette.py           #   generator colour palette — SINGLE SOURCE OF TRUTH (DRY); ISOM 2017-2 screen approximation
  project_config.py    #   strictly-validated global config (azimutlab.toml loader, e.g. 416/416.1 variant)
                       #   template_classic.omap: clean ISOM 2017-2 template for .omap export
model/                 # UC5 model code (sibling of connectors/generator, sys.path scripts; session 77). Four subdirs, three live reconstructors:
  checkpoints.py       #   shared run_id checkpoints: atomic best.pt + manifest + explicit promote to canonical unet_best.pt
  mpp.py               #   canonical training-tile resolution (SSoT) + resample to it (session 126 MPP fix)
  purple.py            #   purple course-overprint augmentation (ISOM) for both reconstructors (supervisor audit A2a; session 123)
  vectorize.py         #   shared reconstructor postprocess: line mask → polyline (session 132)
  runnability/         #   ARCHIVED ortho→runnability model (dead-end session 79; git-moved here session 88)
    tile.py            #     pre-tiling (X,Y) pairs → 512×512 (stride 256, reject <30% valid px) → resources/tiles/ + median-freq weights
    dataset.py         #     PyTorch loader over tiles + augmentation (D4 + brightness/contrast); ImageNet norm (session 78)
    train.py           #     U-Net/ResNet34 (smp), BF16, per-class IoU → resources/model/ (session 78; baseline val mIoU 0.25 = RGB-only ceiling)
  png2area/            #   LIVE Png2Area reconstructor (session 88): map scan → area label raster, first of the 3 OOM-geometry CV tasks
    tile.py            #     resample + pre-tiling [rgb.png, area_labels.png] → 512×512; 20 ISOM codes + background (N_AREA=21)
    dataset.py         #     PyTorch loader (D4 + on-the-fly degrade augmentation + ImageNet norm, no IGNORE — Y is all-valid)
    train.py           #     U-Net/ResNet34, N_AREA labels, BF16; isolated runs/<run_id>/, explicit --promote; test mIoU 0.577 (21-class retrain, session 156)
  png2point/           #   LIVE Png2Point reconstructor (sessions 105–106): map scan → point symbols, second of the 3 CV tasks
    inject.py          #     inject ISOM icons onto clean point_base render → GT for free + Gaussian heatmap splat (scope 204 Boulder / 210 Stony / 417 large tree / 419 veg. feature / 531 man-made X; halo flag: green halo yes, black 531 no)
    dataset.py         #     PyTorch loader: reads point_base renders + random-crop 512, on-the-fly injection (infinite augmentation) + D4 + degrade
    train.py           #     U-Net + focal heatmaps + peak-NMS; isolated runs/<run_id>/, explicit --promote (canonical 1.33 m/px, 5 classes → median mF1 0.811; 531 real transfer Velbloud F1 0.708, peak_thr 0.60; real 210 F1 0.11–0.18)
  png2line/            #   LIVE Png2Line reconstructor (sessions 130–132; scope expanded 152, retrained+measured 156 → reverted to 2-class, see train.py): map scan → line segmentation, third of the 3 CV tasks
    tile.py            #     resample + pre-tiling [rgb.png, on-the-fly line Y from .omap] → 512×512; 304/305 + 306 + 309 + 508*, dilated GT
    dataset.py         #     PyTorch loader (D4 + degrade + purple augmentation; reuse png2area pattern)
    train.py           #     U-Net/ResNet34, N_LINE labels, BF16; isolated runs/<run_id>/, --promote; canonical = 2-class watercourse-only test mIoU 0.774 (5-class scope retrained Sez. 156 → watercourse regressed 0.409→0.26 real → reverted)
    eval_real.py       #     real-scan benchmark: strict IoU + relaxed completeness/correctness; per-class conf_thr (LineClass) → real IoU 0.409
asset/                 # shared map assets (řopík pillbox .omap)
resources/             # real OB maps + derived training tiles (tiles/) — input/reference (gitignored, 3rd-party copyright)
maps/                  # generated maps — output, maps/<location>/ (gitignored, regenerable)
```

(All working documents — TODO/DONE/DIARY/IDEAS/RESEARCH/GLOSSARY — live under `docs/`
since session 47; only README.md and CLAUDE.md stay at the repo root.)

## Docs

Working documents are in Czech (per the global conventions):

- [docs/ROADMAP.md](docs/ROADMAP.md) — direction & phase gate (read every `%BEGIN`)
- [docs/architecture.md](docs/architecture.md) — canonical UC DAG & layering
- [docs/GLOSSARY.md](docs/GLOSSARY.md) — project terminology
- [docs/IDEAS.md](docs/IDEAS.md) — design brainstorm
- [docs/RESEARCH.md](docs/RESEARCH.md) — survey of tools / methods / sources
- [docs/DIARY.md](docs/DIARY.md) — session log (detail in `docs/diary/`)
- [docs/TODO.md](docs/TODO.md) / [docs/DONE.md](docs/DONE.md) — work tracking

## License

Not yet decided.
