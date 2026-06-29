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
| `png2area/` | **živý** | `Png2Area`: sken → area label rastr (20 ISOM kódů + pozadí = `N_AREA=21`, po 404/407/409 v Sez. 152). Pár [`rgb.png`, `area_labels.png`] z `pairs.py`; degradace on-the-fly. **21-class test mIoU 0,577** (Sez. 156 retrain; eval_real Bedř soft 0,525 / acc 0,887; nové 404/407/409 slabý reálný transfer). |
| `png2point/` | **živý** | `Png2Point`: sken → bodové symboly (`inject.py` injekce ikonek + CenterNet heatmap; scope **204/210/417/419/531/525/527/109/111/112** od Sez. 162 — černé man-made ⊤/Λ/X, zelené veg, hnědé terénní disk/oblouk/▽). Test mF1 medián **0,745** (10 tříd, 3 seedy, stabilní 0,738–0,763); **reálný transfer**: 111 SILNÝ 0,71–0,89, 419/531/525 SILNÝ 0,67–0,77, 109 medián 0,65, 527/112 střední-dobrý, 210 kolabuje (drobné tečky). |
| `png2line/` | **živý** | `Png2Line`: sken → liniové symboly (segmentace + skeletonizace, GT z `.omap`). Sez. 156 retrénoval 5-class scope (306/309/508*) a ZMĚŘIL → **watercourse regrese (real IoU 0,409→0,26, 309 kolaps) → REVERT na 2-class watercourse-only** (test mIoU **0,774**, completeness 0,93; 2. potvrzení Sez. 133). |

## Sdílené moduly (vedle podadresářů)

| Modul | Účel |
|-------|------|
| `mpp.py` | **SSoT kanonického měřítka dlaždice** `CANONICAL_MPP=1,33` m/px + `resample_to_mpp` (Sez. 126, audit C1/K1). Symboly i páry i `eval_real` lícují na tuto hodnotu. |
| `norm.py` | **SSoT ImageNet normalizace** pro modelové loadery (mean/std; extrakce DRY dluhu z auditů). |
| `peaks.py` | Sdílené peak/NMS/matching utility pro heatmapové detektory a eval (sjednocuje train/eval peak logiku). |
| `checkpoints.py` | Sdílená správa checkpointů: izolované `runs/<run_id>/` + atomický `--promote` na kanonický `unet_best.pt` (Sez. 127). |
| `purple.py` | Fialový přetisk tratě (ISOM 701-706) JEN do X = augmentace obou modelů (A2a, Sez. 123). Mimo `generator/` = hranice paralelního vlákna. |
| `vectorize.py` | Maska → polyline (skeletonize → graf → RDP), čistá geometrie bez torch; sdílený `.omap assembly` postprocess (Sez. 132). |
| `png2line/north_grid.py` | Poledníkový detektor (pravidelná rovnoběžná soustava → odfiltruj z watercourse výstupu, Sez. 134). |
| `png2line/vectorize_omap.py` | Predikce → vektorizace → `.omap` klon georef + měření ztráty (Sez. 132). |

## Stav (fáze B)

Skripty na `sys.path`, ne instalovaný balík (KISS; produkční balík přijde s monorepem, fáze A).
Sdílí `connectors/` i `generator/`. **Trénink jen `mrkla`/HAL3000** (RTX 5070, torch+CUDA + Livelox
korpus); ntbhej = jen tile smoke (`build_tiles_dev`, bez korpusu). Testy v kořenovém `tests/`.
