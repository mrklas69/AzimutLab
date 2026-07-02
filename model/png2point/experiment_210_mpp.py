"""
experiment_210_mpp.py — Sez. 179 experiment: je 210 Stony ground real-transfer kolaps (F1 0,00-0,25,
Sez. 121-162) rozlišovací strop, nebo trénovací bug?

Verify-against-source (template_classic.omap:219): 210.1 individual dot inner_radius=150 µm →
při měřítku 1:10000 = 3 m průměr na zemi → na CANONICAL_MPP=1,33 jen ~2,25 px (pod hranicí šumu
skenu). 204 Boulder (radius_mm=0.40, ~8 m/~6 px) transfer FUNGUJE (F1 0,76) → hypotéza: rozlišení,
ne training bug (5+ retrénů Sez. 121-162 ladilo hyperparametry, ne tohle).

Izolovaný jednotřídní experiment (NE změna sdíleného 10-třídního point_model): natrénuje SAMOSTATNÝ
Png2Point jen na 210 při 2× jemnějším MPP (0,665 m/px, dot 2,25px→~4,5px, srovnatelné s fungujícím
204 ~6px). Neriskuje regresi ostatních 9 tříd — samostatný checkpoint adresář
`resources/point_model_210mpp/`, kanonický `point_model/unet_best.pt` netknutý.

Mechanismus (verify-against-source, ne guess): inject.py čte TARGET_MPP/PX_PER_MM/POINT_CLASSES/
N_POINT jako module-level globals PŘI KAŽDÉM VOLÁNÍ (ne zamčené jako default parametry) →
monkey-patch PŘED prvním importem train.py/dataset.py v tomto procesu funguje, protože jejich
`from inject import N_POINT` čte už patchnutou hodnotu (první import v procesu = žádná stará
cache). `dataset.py`/`train.py` mají od Sez. 179 explicitní `target_mpp`/`tol_px` parametr
(mpp.resample_to_mpp default beze změny pro kanonickou cestu).

Použití:
    python model/png2point/experiment_210_mpp.py train [--epochs N] [--seed S]
    python model/png2point/experiment_210_mpp.py eval-real [--run-id ID] [Velbloud Blatná ...]
"""
import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
# POZOR (Sez. 179 postmortem): insert(0, …) obrací pořadí při opakovaném volání — poslední
# insert skončí PRVNÍ v sys.path. model/png2area má VLASTNÍ train.py (Png2Area) → kdyby byl
# před model/png2point, `import train` by tiše natáhl cizí modul se špatnou signaturou
# (TypeError na target_mpp/tol_px, ne ImportError — snadno přehlédnutelné). Proto png2area
# NENÍ v cestě vůbec (eval_real.py si ho při potřebě natáhne přes _import_path, ne plain import).
sys.path.insert(0, str(_REPO_ROOT / "connectors"))
sys.path.insert(0, str(_REPO_ROOT / "generator"))
sys.path.insert(0, str(_REPO_ROOT / "model"))
sys.path.insert(0, str(_REPO_ROOT / "model" / "png2point"))    # nejvyšší priorita (poslední insert)

CANONICAL_MPP = 1.33        # = mpp.CANONICAL_MPP (hardcoded tady, ať nemusíme importovat mpp před patchem)
EXPERIMENT_MPP = 0.665      # 2× jemnější — 210 dot 2,25px → ~4,5px (srovnatelné s fungujícím 204 ~6px)
SCALE = CANONICAL_MPP / EXPERIMENT_MPP        # = 2.0
TOL_PX_SCALED = 3 * SCALE                     # zachová reálnou toleranci (~4 m) při jiném rozlišení

_CKPT_DIR = _REPO_ROOT / "resources" / "point_model_210mpp"     # SAMOSTATNÝ adresář, nešahá na kanonický


def _patch_inject():
    """Patchne inject.py PŘED prvním importem train.py/dataset.py/eval_real.py v tomto procesu.

    Musí být volané jako úplně první krok — jinak by downstream moduly zachytily staré
    N_POINT=10/POINT_CLASSES(10 tříd) při svém `from inject import N_POINT` (kopie hodnoty
    při importu, ne live reference)."""
    import inject
    inject.TARGET_MPP = EXPERIMENT_MPP
    inject.PX_PER_MM = (inject.MAP_SCALE / 1000.0) / EXPERIMENT_MPP
    pc210 = next(pc for pc in inject.POINT_CLASSES if pc.code == "210")
    pc210.sigma_px *= SCALE      # zachová poměr sigma/rozestup teček (spacing taky škáluje s PX_PER_MM)
    inject.POINT_CLASSES = [pc210]
    inject.N_POINT = 1
    inject.CODE_TO_IDX = {"210": 0}
    print(f"[patch] inject: TARGET_MPP={inject.TARGET_MPP}  PX_PER_MM={inject.PX_PER_MM:.2f}  "
          f"210 r={pc210.radius_mm*inject.PX_PER_MM:.1f}px  sigma={pc210.sigma_px:.1f}  "
          f"N_POINT={inject.N_POINT}")
    return inject


def cmd_train(epochs: int, batch: int, lr: float, seed: int | None) -> None:
    _patch_inject()
    import train as train_mod          # první import v procesu → vidí patchnutý inject
    train_mod._CKPT_DIR = _CKPT_DIR    # samostatný run adresář (nešahá na kanonický point_model/)
    print(f"[experiment] target_mpp={EXPERIMENT_MPP}  tol_px={TOL_PX_SCALED}  ckpt_dir={_CKPT_DIR}")
    mf1 = train_mod.train(epochs=epochs, batch=batch, lr=lr, overfit=False, seed=seed,
                          target_mpp=EXPERIMENT_MPP, tol_px=TOL_PX_SCALED)
    print(f"\n[experiment] hotovo, test mF1={mf1}")


def cmd_eval_real(names: list[str], run_id: str | None) -> None:
    """Vyhodnotí natrénovaný experiment checkpoint na reálném skenu (izomorf eval_real.py, ale
    patchnuté inject + explicitní POINT_CKPT + TARGET_MPP/TOL_PX pro jemnější rozlišení)."""
    _patch_inject()
    if run_id:
        ckpt_path = _CKPT_DIR / "runs" / run_id / "best.pt"
    else:
        runs = sorted((_CKPT_DIR / "runs").glob("*/best.pt"), key=lambda p: p.stat().st_mtime)
        if not runs:
            sys.exit(f"žádný běh v {_CKPT_DIR / 'runs'} — spusť nejdřív `train`")
        ckpt_path = runs[-1]
    if not ckpt_path.exists():
        sys.exit(f"chybí checkpoint: {ckpt_path}")
    os.environ["POINT_CKPT"] = str(ckpt_path)
    import eval_real as er              # první import v procesu → vidí patchnutý inject
    er.TARGET_MPP = EXPERIMENT_MPP
    er.TOL_PX = TOL_PX_SCALED
    print(f"[eval_real experiment] ckpt={ckpt_path}  target_mpp={EXPERIMENT_MPP}  tol_px={TOL_PX_SCALED}")
    for nm in names:
        print("=" * 70)
        er.main(nm)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_train = sub.add_parser("train")
    ap_train.add_argument("--epochs", type=int, default=40)
    ap_train.add_argument("--batch", type=int, default=16)
    ap_train.add_argument("--lr", type=float, default=1e-4)
    ap_train.add_argument("--seed", type=int, default=None)

    ap_eval = sub.add_parser("eval-real")
    ap_eval.add_argument("names", nargs="*", default=["Velbloud", "Blatná", "Bedřichovka"])
    ap_eval.add_argument("--run-id", default=None)

    args = ap.parse_args()
    if args.cmd == "train":
        cmd_train(args.epochs, args.batch, args.lr, args.seed)
    else:
        cmd_eval_real(args.names, args.run_id)
