"""
train.py — trénink reconstructor modelu Png2Point (Sez. 105).

Druhý ze tří CV úloh dekompozice OOM podle geometrie (Sez. 80): Png2Area (plochy, hotovo) → **Png2Point
(body)** → Png2Line (linie). Úloha: mapový sken RGB → lokalizace + klasifikace bodových ISOM symbolů.
GT = injekce (inject.py): na čistý gen render se vkreslí kanonický symbol na náhodné místo → heatmapa peaků
zdarma (proč injekce místo gen bodů: kompas Sez. 96, gen body ≈ 4 % reality). Loader = dataset.py.

Architektura = HEATMAP REGRESE (CenterNet, Zhou 2019), ne segmentace ani bbox detektor:
- U-Net (ResNet34 ImageNet encoder, smp) → N_POINT kanálů logitů → sigmoid = heatmapa „tady je střed".
- Detekce = peak (3×3 max-pool NMS + práh). Husté symboly (210 stony pole) heatmapa zvládá líp než bbox.

Loss = penalty-reduced focal loss (CornerNet/CenterNet) — řeší extrémní nevyváženost peak-vs-pozadí
(drtivá většina px = 0): pozitiva váží (1-p)², negativa kolem peaku tlumí (1-gt)⁴ → soused peaku netrestá
jako čisté pozadí. Analog median-freq vah z Png2Area, ale standard pro heatmapy.

Metrika = peak F1 per třída (ne IoU): NMS peaky predikce ↔ GT centra, greedy match v toleranci TOL_PX →
precision/recall/F1. accuracy/IoU by u bodů neměřily lokalizaci.

Trénink jen na `mrkla`/HAL3000 (RTX 5070, BF16 autocast). Dva režimy:
  python model/png2point/train.py --overfit   # sanity gate: 1-2 mapy, fixní injekce, F1→~1
  python model/png2point/train.py             # plný trénink na train splitu, eval val + test
Každý běh zapisuje do resources/point_model/runs/<run_id>/; unet_best.pt mění
jen explicitní --promote.
"""
import argparse
import csv
import math
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np   # noqa: E402
import torch   # noqa: E402
import torch.nn.functional as F   # noqa: E402
from torch.utils.data import DataLoader   # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "model" / "png2point"))
sys.path.insert(0, str(_REPO_ROOT / "model"))

import segmentation_models_pytorch as smp   # noqa: E402
from dataset import PointTileDataset, _pointbase_paths   # noqa: E402
from inject import N_POINT, POINT_CLASSES   # noqa: E402
from checkpoints import (   # noqa: E402
    finish_diagnostic_run,
    finish_run,
    fingerprint_inputs,
    promote_run,
    save_best,
    start_run,
)

_CKPT_DIR = _REPO_ROOT / "resources" / "point_model"
ENCODER = "resnet34"
TOL_PX = 3           # tolerance matchingu peak↔GT (px) — 204 r≈3, stony rozestup ≈9 → 3 nehrne sousedy
# Práh detekce peaku je PER TŘÍDA v registru (POINT_CLASSES[c].peak_thr, Sez. 129); --peak-thr = globální override.
_CODES = [pc.code for pc in POINT_CLASSES]


# ----------------------------------------------------------------------------- model
def build_model() -> torch.nn.Module:
    """U-Net + ResNet34 (ImageNet pretrained), 3 vstupní kanály → N_POINT heatmap kanálů (logity).

    Focal prior bias init (RetinaNet/CenterNet, Sez. 125): bias výstupní vrstvy se nastaví tak, aby
    počáteční p(peak) ≈ π = 0,01 (ne 0,5 všude). Bez něj startují logity vysoké → model prvních ~15 epoch
    jen 'stlačuje' plochou heatmapu dolů (mrtvá fáze) a teprve pak skokem naskočí → kdy/jestli skok nastane
    závisí na seedu = hlavní zdroj rozptylu mF1 0,15–0,90. Prior bias mrtvou fázi odstraní."""
    model = smp.Unet(encoder_name=ENCODER, encoder_weights="imagenet",
                     in_channels=3, classes=N_POINT)
    prior = 0.01
    bias_val = -math.log((1.0 - prior) / prior)        # ≈ -4,595 → sigmoid(bias) ≈ 0,01
    head = model.segmentation_head[0]                   # poslední Conv2d (produkuje logity)
    torch.nn.init.constant_(head.bias, bias_val)
    return model


# ------------------------------------------------------------------------- focal loss
def focal_loss(logits: torch.Tensor, gt: torch.Tensor) -> torch.Tensor:
    """Penalty-reduced focal loss (CenterNet). logits/gt = (B,N_POINT,H,W); gt ∈ [0,1] heatmapa.

    pos (gt==1): -(1-p)² log p  → tlačí peak nahoru.
    neg (gt<1):  -(1-gt)⁴ p² log(1-p) → tlumí trest blízko peaku (gt→1 ⇒ váha→0), plný trest daleko.
    Normalizace počtem pozitiv (N peaků). Bez pozitiv (prázdná dlaždice) = jen neg člen."""
    p = torch.sigmoid(logits).clamp(1e-6, 1 - 1e-6)   # do (0,1) kvůli log
    pos = gt.eq(1.0).float()
    neg = 1.0 - pos
    neg_w = torch.pow(1.0 - gt, 4)                     # beta=4 — tlumení kolem peaku

    pos_loss = torch.log(p) * torch.pow(1 - p, 2) * pos          # alpha=2
    neg_loss = torch.log(1 - p) * torch.pow(p, 2) * neg_w * neg
    n_pos = pos.sum()
    pos_sum, neg_sum = pos_loss.sum(), neg_loss.sum()
    if n_pos == 0:
        return -neg_sum
    return -(pos_sum + neg_sum) / n_pos                # CenterNet: pos i neg normalizováno týmž n_pos
    # POZN. (Sez. 106): per-kanál normalizace ZKOUŠENA a ZHORŠILA (dělení neg členu malým n_pos řídké
    # třídy ho explodovalo → oba kanály na 0). 204 mrtvý NENÍ čistě imbalance — viz diagnostika níže.


# --------------------------------------------------------------------- peak detekce
def _nms(heat: torch.Tensor, kernel: int = 3) -> torch.Tensor:
    """Peak NMS přes 3×3 max-pool: ponech jen px, které jsou lokální maximum. heat (B,C,H,W)."""
    pad = (kernel - 1) // 2
    hmax = F.max_pool2d(heat, kernel, stride=1, padding=pad)
    return heat * (hmax == heat).float()


def _peaks_xy(heat2d: np.ndarray, thr: float) -> np.ndarray:
    """Souřadnice peaků (po NMS) nad prahem v jedné heatmapě → (K,2) array [x,y]."""
    ys, xs = np.where(heat2d > thr)
    return np.stack([xs, ys], axis=1).astype(np.float32) if len(xs) else np.zeros((0, 2), np.float32)


def _match_counts(pred_xy: np.ndarray, gt_xy: np.ndarray, tol: float) -> tuple[int, int, int]:
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


# ------------------------------------------------------------------------- metriky
@torch.no_grad()
def evaluate(model, loader, device, thr: float | None = None) -> tuple[list[dict], float]:
    """Projde loader, vrátí (per-class {tp,fp,fn,precision,recall,f1}, mean F1). BF16 autocast.

    GT centra = NMS peaky GT heatmapy (gt==1). Pred peaky = NMS sigmoid(logits) > práh.
    thr=None → PER-TŘÍDA práh z registru (POINT_CLASSES[c].peak_thr, Sez. 129); float → globální
    override pro všechny třídy (sweep / experiment přes --peak-thr)."""
    model.eval()
    thrs = [pc.peak_thr for pc in POINT_CLASSES] if thr is None else [thr] * N_POINT
    tp = np.zeros(N_POINT, np.int64)
    fp = np.zeros(N_POINT, np.int64)
    fn = np.zeros(N_POINT, np.int64)
    for x, gt in loader:
        x = x.to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits = model(x)
        pred = _nms(torch.sigmoid(logits.float())).cpu().numpy()       # (B,C,H,W)
        gt_nms = _nms(gt).numpy()                                       # GT centra (gt==1 → 1)
        B = pred.shape[0]
        for b in range(B):
            for c in range(N_POINT):
                p_xy = _peaks_xy(pred[b, c], thrs[c])
                g_xy = _peaks_xy(gt_nms[b, c], 0.99)
                t, f, n = _match_counts(p_xy, g_xy, TOL_PX)
                tp[c] += t; fp[c] += f; fn[c] += n

    per = []
    f1s = []
    for c in range(N_POINT):
        prec = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) else 0.0
        rec = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per.append({"code": _CODES[c], "tp": int(tp[c]), "fp": int(fp[c]), "fn": int(fn[c]),
                    "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)})
        f1s.append(f1)
    return per, float(np.mean(f1s)) if f1s else 0.0


def _fmt(per: list[dict]) -> str:
    return "  ".join(f"{d['code']} F1={d['f1']:.2f}(P{d['precision']:.2f}/R{d['recall']:.2f})"
                     for d in per)


# ---------------------------------------------------------------- průběžná statistika
def _save_history(history: list[dict], output_dir: Path) -> None:
    """Zapíše historii pouze do adresáře konkrétního běhu."""
    path = output_dir / "history.csv"
    cols = ["epoch", "loss", "mf1"] + [f"f1_{c}" for c in _CODES]
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(cols)
        for h in history:
            wr.writerow([h["epoch"], f"{h['loss']:.4f}", f"{h['mf1']:.4f}"]
                        + [f"{d['f1']:.4f}" for d in h["per"]])


def _plot_curve(history: list[dict], output_dir: Path, f1_label: str) -> None:
    eps = [h["epoch"] for h in history]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    ax1.plot(eps, [h["loss"] for h in history], "r-o", ms=3, label="train loss")
    ax1.set_xlabel("epocha"); ax1.set_ylabel("train loss", color="r")
    ax1.tick_params(axis="y", labelcolor="r"); ax1.grid(alpha=0.3)
    axb = ax1.twinx()
    axb.plot(eps, [h["mf1"] for h in history], "b-s", ms=3, label=f"{f1_label} mF1")
    axb.set_ylabel(f"{f1_label} mean F1", color="b"); axb.set_ylim(0, 1)
    axb.tick_params(axis="y", labelcolor="b")
    ax1.set_title(f"loss + F1 (poslední: {history[-1]['mf1']:.3f})")
    for c in range(N_POINT):
        ax2.plot(eps, [h["per"][c]["f1"] for h in history], "-o", ms=2, label=_CODES[c])
    ax2.set_xlabel("epocha"); ax2.set_ylabel("F1"); ax2.set_ylim(0, 1)
    ax2.grid(alpha=0.3); ax2.legend(fontsize=8, loc="lower right")
    ax2.set_title(f"per-class F1 ({f1_label})")
    fig.tight_layout()
    fig.savefig(output_dir / "curve.png", dpi=90)
    plt.close(fig)


# ------------------------------------------------------------------------------ EMA
class _EMA:
    """Exponenciální klouzavý průměr vah (Páka 1 stabilizace, Sez. 125).

    Drží 'shadow' kopii všech tensorů state_dict. Po každém kroku optimalizátoru se
    float tensory přiblíží aktuálním vahám faktorem (1-decay); ne-float buffery
    (např. BN `num_batches_tracked`) se kopírují přímo. Vyhlazené váhy konvergují
    klidněji než poslední iterace → menší run-to-run rozptyl (Png2Point mF1 0,15–0,90)."""

    def __init__(self, model: torch.nn.Module, decay: float):
        self.decay = decay
        # detach().clone() = nezávislá kopie mimo autograd graf
        self.shadow = {k: v.detach().clone() for k, v in model.state_dict().items()}

    @torch.no_grad()
    def update(self, model: torch.nn.Module) -> None:
        for k, v in model.state_dict().items():
            s = self.shadow[k]
            if v.dtype.is_floating_point:
                s.mul_(self.decay).add_(v.detach(), alpha=1.0 - self.decay)   # in-place EMA
            else:
                s.copy_(v)                                                    # buffery jen kopíruj

    def copy_to(self, model: torch.nn.Module) -> None:
        model.load_state_dict(self.shadow)


# -------------------------------------------------------------------------- trénink
def train(*, epochs: int, batch: int, lr: float, overfit: bool, thr: float | None = None,
          seed: int | None = None, ema: bool = False, ema_decay: float = 0.998,
          run_id: str | None = None) -> float | None:
    assert torch.cuda.is_available(), "trénink jen na CUDA GPU (mrkla/HAL3000, RTX 5070)"
    device = "cuda"
    if seed is not None:
        # Reprodukovatelný běh (Sez. 125): augmentace (crop/D4/injekce/degrade/purpura) jede přes
        # globální torch RNG → manual_seed zdeterminuje celý stream. cudnn deterministicky (mírně
        # pomalejší, ale run-to-run stabilní). Bez --seed zůstává staré nedeterministické chování.
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        np.random.seed(seed)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        print(f"[seed] reprodukovatelný běh, seed={seed} (cudnn deterministic)")
    else:
        torch.backends.cudnn.benchmark = True

    if overfit:
        # 1-2 point_base mapy z train splitu (gate = memorizace na čistém podkladu, Sez. 105/106)
        pb = _pointbase_paths("train")
        cids = [p.parent.parent.name for p in pb[:2]]
        print(f"[overfit] mapy: {cids}")
        train_ds = PointTileDataset("train", augment=False, limit_cids=cids)
        val_ds = train_ds
    else:
        train_ds = PointTileDataset("train", augment=True)
        val_ds = PointTileDataset("val", augment=False)

    train_dl = DataLoader(train_ds, batch_size=batch, shuffle=True, num_workers=0,
                          drop_last=not overfit)
    val_dl = DataLoader(val_ds, batch_size=batch, shuffle=False, num_workers=0)

    model = build_model().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = (None if overfit
                 else torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs))

    # EMA (Páka 1): druhý model jako eval cíl naplněný vyhlazenými vahami; None = vypnuto
    ema_obj = _EMA(model, ema_decay) if ema else None
    ema_model = build_model().to(device) if ema else None
    if ema:
        print(f"[ema] zapnuto, decay={ema_decay} (eval + best z vyhlazených vah)")

    pointbase_paths = (
        _pointbase_paths("train") + _pointbase_paths("val") + _pointbase_paths("test")
    )
    # Hashujeme split a malé generátorové manifesty všech použitých podkladů.
    # Samotné PNG by při každém startu zbytečně četly gigabajty; meta.json nese
    # parametry a provenance, které určují reprodukovatelnost point_base renderu.
    pointbase_manifests = [path.with_name("meta.json") for path in pointbase_paths]
    config = {
        "epochs": epochs,
        "batch": batch,
        "lr": lr,
        "overfit": overfit,
        "peak_thr": thr if thr is not None else [pc.peak_thr for pc in POINT_CLASSES],
        "seed": seed,
        "ema": ema,
        "ema_decay": ema_decay if ema else None,
        "encoder": ENCODER,
        "n_point": N_POINT,
        "codes": _CODES,
        "train_samples": len(train_ds),
        "val_samples": len(val_ds),
    }
    data_fingerprint = fingerprint_inputs(
        [_REPO_ROOT / "resources" / "livelox" / "_split.json", *pointbase_manifests],
        [f"pointbase_count={len(pointbase_paths)}"],
    )
    run = start_run(_CKPT_DIR, "png2point", config, data_fingerprint, run_id)
    print(f"[run] {run.run_id} → {run.run_dir}")

    print(f"train {len(train_ds)} dlaždic | val {len(val_ds)} | batch {batch} | lr {lr} | "
          f"epoch {epochs} | BF16 | {ENCODER} U-Net | {N_POINT} bod. tříd {_CODES}"
          + ("" if overfit else " | cosine LR"))

    best_f1 = -1.0
    history: list[dict] = []
    f1_label = "train" if overfit else "val"
    for ep in range(1, epochs + 1):
        model.train()
        t0 = time.time()
        running = 0.0
        for x, gt in train_dl:
            x, gt = x.to(device), gt.to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                logits = model(x)
            loss = focal_loss(logits.float(), gt)      # loss ve fp32 (log stabilita)
            loss.backward()
            optimizer.step()
            if ema_obj is not None:
                ema_obj.update(model)
            running += loss.item()
        avg = running / len(train_dl)
        if scheduler is not None:
            scheduler.step()

        # eval (a níže i best ckpt) z EMA vah, pokud zapnuto; jinak z živého modelu
        if ema_obj is not None:
            ema_obj.copy_to(ema_model)
        eval_target = ema_model if ema_obj is not None else model
        per, mf1 = evaluate(eval_target, val_dl, device, thr)
        dt = time.time() - t0
        lr_now = optimizer.param_groups[0]["lr"]
        print(f"ep {ep:>3}/{epochs}  loss {avg:.4f}  {f1_label} mF1 {mf1:.3f}  "
              f"lr {lr_now:.2e}  [{_fmt(per)}]  {dt:.0f}s")

        history.append({"epoch": ep, "loss": avg, "mf1": mf1, "per": per})
        _save_history(history, run.run_dir)
        _plot_curve(history, run.run_dir, f1_label)

        if not overfit and mf1 > best_f1:
            best_f1 = mf1
            save_best(
                run,
                eval_target.state_dict(),
                epoch=ep,
                metric_name="mf1",
                metric_value=mf1,
                model_metadata={"encoder": ENCODER, "n_point": N_POINT, "codes": _CODES},
            )

    if not overfit:
        ckpt = torch.load(run.best_path, weights_only=False)
        model.load_state_dict(ckpt["model"])
        test_dl = DataLoader(PointTileDataset("test", augment=False),
                             batch_size=batch, shuffle=False, num_workers=0)
        per, mf1 = evaluate(model, test_dl, device, thr)
        print(f"\n=== TEST (best ep {ckpt['epoch']}, val mF1 {ckpt['mf1']:.3f}) ===")
        print(f"test mF1 {mf1:.3f}  [{_fmt(per)}]")
        finish_run(run, "test_mf1", mf1)
        print(f"[run] dokončen; kanonický model beze změny. Promote: "
              f"python model/png2point/train.py --promote {run.run_id}")
        return mf1
    finish_diagnostic_run(run, "train_mf1", history[-1]["mf1"])
    print(f"[run] diagnostika dokončena bez promotovatelného checkpointu: {run.run_dir}")
    return None


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Png2Point reconstructor U-Net trénink (Sez. 105)")
    ap.add_argument("--overfit", action="store_true",
                    help="sanity gate: 1-2 mapy, fixní injekce, sleduj train F1→~1")
    ap.add_argument("--epochs", type=int, default=None, help="počet epoch (default 40 / overfit 60)")
    ap.add_argument("--batch", type=int, default=16, help="batch size (mrkla RTX 5070 baseline 16)")
    ap.add_argument("--lr", type=float, default=1e-4,
                    help="learning rate (AdamW, cosine decay). Nález Sez. 105: heatmapa konverguje "
                         "až s ~1e-3 (gate spouštěj --lr 1e-3); 1e-4 default pro klidnější plný trénink")
    ap.add_argument("--peak-thr", type=float, default=None,
                    help="globální override prahu detekce peaku pro VŠECHNY třídy (sweep/experiment). "
                         "Bez něj per-třída práh z registru POINT_CLASSES[c].peak_thr (Sez. 129).")
    ap.add_argument("--seed", type=int, default=None,
                    help="fixní seed → reprodukovatelný běh (Sez. 125). Bez něj nedeterministický jako dřív.")
    ap.add_argument("--ema", action="store_true",
                    help="EMA vah (Páka 1 stabilizace, Sez. 125) — eval i best z vyhlazených vah")
    ap.add_argument("--ema-decay", type=float, default=0.998, help="EMA decay (default 0.998)")
    ap.add_argument("--run-id", default=None,
                    help="vlastní ID běhu; default je UTC čas + náhodný suffix")
    ap.add_argument("--promote", metavar="RUN_ID",
                    help="atomicky povýší dokončený běh na unet_best.pt a skončí")
    args = ap.parse_args()
    if args.promote:
        if args.overfit or args.epochs is not None or args.run_id is not None:
            ap.error("--promote nelze kombinovat s parametry tréninku")
        target = promote_run(_CKPT_DIR, args.promote, "png2point")
        print(f"[promote] {args.promote} → {target}")
        raise SystemExit(0)

    n_ep = args.epochs if args.epochs is not None else (60 if args.overfit else 40)
    train(epochs=n_ep, batch=args.batch, lr=args.lr, overfit=args.overfit, thr=args.peak_thr,
          seed=args.seed, ema=args.ema, ema_decay=args.ema_decay, run_id=args.run_id)
