"""Peak detekce pro heatmapové reconstructory (CenterNet konvence) — SSoT (audit D4, Sez. 158).

Dřív duplikováno: `png2point/train.py` (definice) + `png2point/eval_real.py` (doslovná kopie). Důvod kopie
byl obejít import `train.py` (táhne matplotlib/dataset) jen kvůli třem čistým funkcím — řeší se malým
modulem bez těžkých závislostí (jen torch/numpy). Teď jeden zdroj → detekční logika (NMS / práh / greedy
match) se nemůže mezi tréninkem a `eval_real` rozejít (train/serve konzistence na vrcholové metrice).
"""
import numpy as np
import torch
import torch.nn.functional as F


def nms(heat: torch.Tensor, kernel: int = 3) -> torch.Tensor:
    """Peak NMS přes max-pool: ponech jen px, které jsou lokální maximum. heat (B,C,H,W)."""
    pad = (kernel - 1) // 2
    hmax = F.max_pool2d(heat, kernel, stride=1, padding=pad)
    return heat * (hmax == heat).float()


def peaks_xy(heat2d: np.ndarray, thr: float) -> np.ndarray:
    """Souřadnice peaků (po NMS) nad prahem v jedné heatmapě → (K,2) array [x,y]."""
    ys, xs = np.where(heat2d > thr)
    return np.stack([xs, ys], axis=1).astype(np.float32) if len(xs) else np.zeros((0, 2), np.float32)


def match_counts(pred_xy: np.ndarray, gt_xy: np.ndarray, tol: float) -> tuple[int, int, int]:
    """Greedy match predikovaných peaků na GT v toleranci tol (px). Vrací (TP, FP, FN).

    Pro každý GT bod vezmi nejbližší dosud nespárovaný pred v tol → TP. Zbylé pred = FP, zbylé GT = FN."""
    if len(gt_xy) == 0:
        return 0, len(pred_xy), 0
    if len(pred_xy) == 0:
        return 0, 0, len(gt_xy)
    used = np.zeros(len(pred_xy), dtype=bool)
    tp = 0
    for g in gt_xy:
        d = np.hypot(pred_xy[:, 0] - g[0], pred_xy[:, 1] - g[1])
        d[used] = np.inf
        j = int(np.argmin(d))
        if d[j] <= tol:
            used[j] = True
            tp += 1
    fn = len(gt_xy) - tp
    fp = len(pred_xy) - used.sum()
    return tp, int(fp), int(fn)
