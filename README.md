# AzimutLab

A lab for cartography & orienteering map intelligence — tools, experiments, and a
knowledgebase. **Not one application: a set of them**, sharing a common understanding
of what an orienteering map *is*.

**Status: phase B (umbrella). First real code (since session 4): a procedural synthetic-map
generator in `sandbox/generator-poc/` — feeds UC5 training with free ground-truth. Being rebuilt
"better, layer by layer" (session 11): currently contours + terrain-aware paths (§9, Dijkstra
least-cost — traverse slopes, don't climb) + knoll/depression point symbols (ISOM 2017-2 codes
109/110/111); vegetation/marsh/boulders were dropped (looked artificial → would hurt the feeder's
domain gap). Draws real terrain from ČÚZK DMR 5G (`--terrain real`) and — since session 16 — real paths from
ČÚZK ZABAGED Polohopis WFS (`--paths real`, ISOM 502-506), — since session 17 — real water from the same
`zabaged.py` connector (`--water real`, watercourses ISOM 304/305/306 + water bodies 301), and — since session 18 —
real buildings (`--buildings real`, ISOM 521) with level-1 cartographic generalization (min. size + Douglas-Peucker
outline) and — since session 22 — level-2 displacement (buildings nudged off the fixed road/water network to the
ISOM 0,4 mm minimum gap; `resolve_displacement`). `zabaged.py` (sibling of `dmr.py`) is the first real UC2 connector. Exports contours+paths+water+buildings+points
to `.omap` (contours also to GeoJSON) — template-based on a
clean self-made ISOM 2017-2 template (session 14), inheriting faithful point geometry (110 ellipse,
111 arc) + the full symbol library. Since session 23 the map extent is parametric (`--width-km`/`--height-km`,
any location & aspect ratio; resolution held constant) and `zabaged.py` fetches the full relevant set of ZABAGED
layers, not a curated subset (e.g. `Silnice_neevidovaná` — unregistered/forest asphalt roads, previously missing) —
the real branch is conceptually a *map predictor* (`synthesize_pseudorealistic_map`): projection of available
geodata now, AI prediction of missing symbols from similar localities later (UC5).**

## What this is

AzimutLab is an umbrella project that grew out of [Pic2Omap](../Pic2Omap) (raster
orienteering map → vector `.omap`). Where Pic2Omap is one pipeline, AzimutLab is the
workbench around it: data connectors, models that "understand" maps, generators,
restoration — and the knowledgebase that ties them together.

It starts deliberately small (a knowledgebase + sandbox) and is designed to **grow into
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
| UC2 | Data connectors | Survey + connect 3rd-party sources (LIDAR, ortofoto, QGIS, ČÚZK ZABAGED/ZTM, geoportál) | ◐ first connectors live (DMR 5G terrain, ZABAGED paths + water + buildings) |
| UC5 | Map-understanding models | 100 % palette separation; point/line/area ISOM symbol classification | ☐ |
| UC3 | Restoration | Strip the purple race layer (controls, refreshments, OOB) + digital restore of worn printed maps | ☐ |
| UC4 | Generators | I: plausible-random · II: inspired (by image / coords) · III: **precise = Pic2Omap** (muddy scan → OCD/OMAP) | ◐ (I = PoC generator; III = Pic2Omap) |

UC4-III is the project's summit and currently lives in Pic2Omap. Full UC4-I
(plausible-random, not a random pile of ISOM symbols) is still the hardest goal — but as a
**synthetic-data generator with free ground-truth it became an enabler-feeder for UC5**
(session 4 reframe), no longer "the very end". PoC: `sandbox/generator-poc/`.

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
  kb/                  # the knowledgebase (heart of UC1)
    data-sources.md    #   UC2 survey: ČÚZK / geoportál / ortofoto / LIDAR + licences
    isom-issprom.md    #   symbol semantics, spec links
    tools-models.md    #   CoVe, OCAD, Karttapullautin, U-Net, …
    generator-procedural.md  # UC4-I synthetic map generator spec (free-GT training data)
connectors/            # UC2 enabler: real-geodata connectors (pulled out of sandbox, session 16)
  dmr.py               #   ČÚZK DMR 5G elevation (ArcGIS ImageServer); --terrain real
  zabaged.py           #   ČÚZK ZABAGED Polohopis paths + water + buildings (WFS, GeoJSON); --paths/--water/--buildings real
sandbox/               # UC1: isolated experiments, one folder each
  generator-poc/       #   first code: procedural OB-map generator (contours + paths + water + buildings + extremum symbols + masks)
                       #     consumes connectors/ for real terrain, paths, water & buildings; adds them to sys.path
                       #     + template_classic.omap: clean ISOM 2017-2 template for .omap export
IDEAS.md               # the 5 UC as a DAG, MVP cut, pending decisions
RESEARCH.md            # survey of existing tools / methods
GLOSSARY.md            # project terminology
TODO.md / DONE.md      # work tracking
DIARY.md               # session index
```

## Docs

Working documents are in Czech (per the global conventions):

- [docs/architecture.md](docs/architecture.md) — canonical UC DAG & layering
- [GLOSSARY.md](GLOSSARY.md) — project terminology
- [IDEAS.md](IDEAS.md) — design brainstorm
- [RESEARCH.md](RESEARCH.md) — survey of tools / methods / sources
- [DIARY.md](DIARY.md) — session log (detail in `docs/diary/`)
- [TODO.md](TODO.md) / [DONE.md](DONE.md) — work tracking

## License

Not yet decided.
