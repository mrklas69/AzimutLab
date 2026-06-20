# model/ — UC5 model kód (reconstructor)

Třetí top-level složka kódu LABu, sourozenec `connectors/` a `generator/` (Sez. 77). Cíl
**`reconstructor()`** = sken OB mapy → `.omap` (reframe Sez. 79; feeder = `generator()` páry X,Y).
Dekompozice podle typu geometrie ISOM → tři CV úlohy, GT zdarma z `.omap`.

## Tři reconstructory + archiv (typicky `{tile,dataset,train,eval_real}.py`, izomorfní)

> Výjimky z čtveřice: `png2point/` nemá `tile.py` (injekce běží on-the-fly v `dataset.py`, ne pre-tiling);
> archiv `runnability/` nemá `eval_real.py` (vznikl až s živými reconstructory).

| Podadresář | Stav | Úloha |
|------------|------|-------|
| `runnability/` | **archiv** | `ORTO → runnability` baseline (slepá ulička Sez. 79, val mIoU strop ~0,25; `git mv` sem Sez. 88). Nemazáno — doložené „tudy ne". |
| `png2area/` | **živý** | `Png2Area`: sken → area label rastr (20 ISOM kódů + pozadí = `N_AREA=21`, po 404/407/409 v Sez. 152). Pár [`rgb.png`, `area_labels.png`] z `pairs.py`; degradace on-the-fly. Poslední plný test před scope expanzí mIoU **0,683** (Sez. 126). |
| `png2point/` | **živý** | `Png2Point`: sken → bodové symboly (`inject.py` injekce ikonek + CenterNet heatmap; scope 204/210/417/419 od Sez. 128). Test mF1 **0,827** (medián 3 seedů). |
| `png2line/` | **živý** | `Png2Line`: sken → liniové symboly (segmentace + skeletonizace, GT z `.omap`). Label scope je 304/305 + 306 + 309 + 508*; starý checkpoint/vectorizer zůstává watercourse-only do rebuild/retrain. Krok 1 watercourse měl test mIoU **0,774**; reálný transfer completeness 0,93. |

## Sdílené moduly (vedle podadresářů)

| Modul | Účel |
|-------|------|
| `mpp.py` | **SSoT kanonického měřítka dlaždice** `CANONICAL_MPP=1,33` m/px + `resample_to_mpp` (Sez. 126, audit C1/K1). Symboly i páry i `eval_real` lícují na tuto hodnotu. |
| `checkpoints.py` | Sdílená správa checkpointů: izolované `runs/<run_id>/` + atomický `--promote` na kanonický `unet_best.pt` (Sez. 127). |
| `purple.py` | Fialový přetisk tratě (ISOM 701-706) JEN do X = augmentace obou modelů (A2a, Sez. 123). Mimo `generator/` = hranice paralelního vlákna. |
| `vectorize.py` | Maska → polyline (skeletonize → graf → RDP), čistá geometrie bez torch; sdílený `.omap assembly` postprocess (Sez. 132). |
| `png2line/north_grid.py` | Poledníkový detektor (pravidelná rovnoběžná soustava → odfiltruj z watercourse výstupu, Sez. 134). |
| `png2line/vectorize_omap.py` | Predikce → vektorizace → `.omap` klon georef + měření ztráty (Sez. 132). |

## Stav (fáze B)

Skripty na `sys.path`, ne instalovaný balík (KISS; produkční balík přijde s monorepem, fáze A).
Sdílí `connectors/` i `generator/`. **Trénink jen `mrkla`/HAL3000** (RTX 5070, torch+CUDA + Livelox
korpus); ntbhej = jen tile smoke (`build_tiles_dev`, bez korpusu). Testy v kořenovém `tests/`.
