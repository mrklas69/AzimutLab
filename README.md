# AzimutLab

A lab for cartography & orienteering map intelligence — tools, experiments, and a
knowledgebase. **Not one application: a set of them**, sharing a common understanding
of what an orienteering map *is*.

**Status: phase B (umbrella).** Active foundations are UC2 connectors, the UC4-I/UC5
`generator()`, and two live reconstructors. Generator KPI is **58.6%**. `Png2Area`
has test mIoU **0.683** and `Png2Point` a 3-seed median mF1 **0.874**; real-domain
transfer remains the limiting metric and `Png2Line` is not implemented. Current work
is tracked in [TODO](docs/TODO.md); history is in [DONE](docs/DONE.md) and
[DIARY](docs/DIARY.md).

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
| UC5 | Map-understanding models | `generator()` → reconstructors for Area/Point/Line ISOM geometry | ◐ **216 curated classic maps**, geographic split without leakage. `Png2Area`: 17 ISOM codes + background (`N_AREA=18`), synthetic test mIoU **0.683** at canonical 1.33 m/px; real per-shade mIoU **0.336/0.357**, soft pixel accuracy **0.89-0.91**. `Png2Point` (204/210/417/419 since Sez. 128): 3-seed synthetic median mF1 **0.827**; real mF1 **0.41-0.54** — **419 strong 0.67-0.76**, 417 moderate 0.40-0.49, 204 stable, 210 still collapses. `Png2Line` is the missing final reconstructor. Generator KPI **58.6%**; details in architecture/TODO/DONE. |
| UC3 | Restoration | Strip the purple race layer (controls, refreshments, OOB) + digital restore of worn printed maps | ☐ |
| UC4 | Generators | I: plausible-random · II: inspired (by image / coords) · III: **precise = Pic2Omap** (muddy scan → OCD/OMAP) | ◐ (I = generator, Lab pillar — KPI 58.6 %; III = Pic2Omap) |

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
  AUDIT_FABLE5_*.md    # meta-audit by the strongest model: _PROMPT = repeatable assignment, dated issues (session 117)
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
  pairs.py             #   phase I orchestrator: build_pair(cid) = real ČÚZK + separation → [rgb.png, .omap] pair
  degrade.py           #   phase II: degrade clean render → "scan" (CMYK misregistration/blur/paper/noise/JPEG; session 86)
  omap_raster.py       #   Y-pipeline: rasterize area ISOM symbols from .omap → label raster (Y for Png2Area; per-code, z-order, holes; session 87)
                       #     consumes connectors/ (real terrain, paths, water, …); adds them to sys.path
                       #   template_classic.omap: clean ISOM 2017-2 template for .omap export
model/                 # UC5 model code (sibling of connectors/generator, sys.path scripts; session 77). Three subdirs, two live reconstructors:
  checkpoints.py       #   shared run_id checkpoints: atomic best.pt + manifest + explicit promote to canonical unet_best.pt
  runnability/         #   ARCHIVED ortho→runnability model (dead-end session 79; git-moved here session 88)
    tile.py            #     pre-tiling (X,Y) pairs → 512×512 (stride 256, reject <30% valid px) → resources/tiles/ + median-freq weights
    dataset.py         #     PyTorch loader over tiles + augmentation (D4 + brightness/contrast); ImageNet norm (session 78)
    train.py           #     U-Net/ResNet34 (smp), BF16, per-class IoU → resources/model/ (session 78; baseline val mIoU 0.25 = RGB-only ceiling)
  png2area/            #   LIVE Png2Area reconstructor (session 88): map scan → area label raster, first of the 3 OOM-geometry CV tasks
    tile.py            #     resample + pre-tiling [rgb.png, area_labels.png] → 512×512; 17 ISOM codes + background
    dataset.py         #     PyTorch loader (D4 + on-the-fly degrade augmentation + ImageNet norm, no IGNORE — Y is all-valid)
    train.py           #     U-Net/ResNet34, 18 labels, BF16; isolated runs/<run_id>/, explicit --promote; test mIoU 0.683
  png2point/           #   LIVE Png2Point reconstructor (sessions 105–106): map scan → point symbols, second of the 3 CV tasks
    inject.py          #     inject ISOM icons onto clean point_base render → GT for free + Gaussian heatmap splat (scope 204 Boulder / 210 Stony / 417 large tree / 419 veg. feature)
    dataset.py         #     PyTorch loader: reads point_base renders + random-crop 512, on-the-fly injection (infinite augmentation) + D4 + degrade
    train.py           #     U-Net + focal heatmaps + peak-NMS; isolated runs/<run_id>/, explicit --promote (canonical 1.33 m/px → mF1 0.874; real 210 F1 0.11–0.18)
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
