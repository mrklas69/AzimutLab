"""
train.py — trénink reconstructor modelu Png2Line (Sez. 130).

TŘETÍ ze tří CV úloh dekompozice OOM podle geometrie (Sez. 80): Png2Area (plochy) | Png2Point (body) |
**Png2Line (linie)**. Mapový sken RGB → per-class segmentace liniových ISOM symbolů (krok 1: N_LINE=2,
pozadí + watercourse 304/305). Vektorizace maska→polyline je ODLOŽENÝ sdílený krok (IDEAS „Png2Line —
segmentace + odložená vektorizace"), NE součást modelu. Izomorfní s model/png2area/train.py (reuse
U-Net/loss/IoU/křivka/checkpoints) — liší se: N_LINE tříd, line_tiles/line_model adresáře.

Architektura: U-Net + ResNet34 encoder, ImageNet-pretrained (segmentation-models-pytorch) — TÝŽ jako
Png2Area (segmentace je vyřešené teritorium; přínos Png2Line = liniová GT + odložená vektorizace, ne nová síť).

Trénink jen na `mrkla`/HAL3000 (RTX 5070). Mixed precision = BF16 autocast.

Dva režimy (CLI):
  python model/png2line/train.py --overfit   # sanity gate: 2 mapy, bez augmentace, train mIoU→~1
  python model/png2line/train.py             # plný trénink na train splitu, eval na val + test

Třída je EXTRÉMNĚ nevyvážená (watercourse << 1 % px) → CrossEntropyLoss s median-freq váhami z tile.py.
Metrika = per-class IoU + mIoU (accuracy by schovala, že model predikuje samé pozadí).

Sys.path skript (fáze B). Každý běh → resources/line_model/runs/<run_id>/; unet_best.pt mění jen --promote.
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")   # headless backend — kreslíme do PNG, žádné GUI okno
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np   # noqa: E402
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

_REPO_ROOT = Path(__file__).resolve().parents[2]   # model/png2line/ → o dvě úrovně hloub
sys.path.insert(0, str(_REPO_ROOT / "model" / "png2line"))
sys.path.insert(0, str(_REPO_ROOT / "model"))
sys.path.insert(0, str(_REPO_ROOT / "generator"))

import segmentation_models_pytorch as smp   # noqa: E402

from dataset import LineTileDataset, class_weights   # noqa: E402
from omap_raster import N_LINE, LINE_LABEL_NAME   # noqa: E402  (SSoT line schématu, Sez. 130)
from checkpoints import (   # noqa: E402
    finish_diagnostic_run,
    finish_run,
    fingerprint_inputs,
    promote_run,
    save_best,
    start_run,
)

_CKPT_DIR = _REPO_ROOT / "resources" / "line_model"
ENCODER = "resnet34"

# Strop median-freq vah (stejný koncept jako Png2Area, Sez. 91): watercourse je tak vzácná, že syrová
# median-freq váha je obrovská → cap brání rozhoupání lossu. Laditelné --weight-cap bez re-tilingu.
WEIGHT_CAP = 10.0


# ----------------------------------------------------------------------------- model
def build_model() -> nn.Module:
    """U-Net + ResNet34 encoder (ImageNet pretrained), 3 vstupní kanály → N_LINE tříd."""
    return smp.Unet(
        encoder_name=ENCODER,
        encoder_weights="imagenet",
        in_channels=3,
        classes=N_LINE,
    )


# ------------------------------------------------------------------------- metriky
def _confusion(pred: torch.Tensor, target: torch.Tensor, cm: torch.Tensor) -> None:
    """Akumuluje confusion matici (N_LINE×N_LINE) na GPU. Bez IGNORE — všechny px validní."""
    t = target.reshape(-1)
    p = pred.reshape(-1)
    idx = t * N_LINE + p
    cm += torch.bincount(idx, minlength=N_LINE * N_LINE).reshape(N_LINE, N_LINE)


def _iou_from_cm(cm: torch.Tensor) -> tuple[list[float], float]:
    """Per-class IoU + mIoU z confusion matice. Třída bez px = NaN → vynecháme z mIoU."""
    cm = cm.double()
    tp = cm.diag()
    fp = cm.sum(0) - tp
    fn = cm.sum(1) - tp
    denom = tp + fp + fn
    iou = torch.where(denom > 0, tp / denom, torch.full_like(tp, float("nan")))
    per = iou.tolist()
    present = iou[~torch.isnan(iou)]
    miou = float(present.mean()) if len(present) else float("nan")
    return per, miou


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: str) -> tuple[list[float], float]:
    """Projde loader, vrátí (per-class IoU, mIoU). Bez gradientů, BF16 autocast."""
    model.eval()
    cm = torch.zeros(N_LINE, N_LINE, dtype=torch.long, device=device)
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits = model(x)
        pred = logits.argmax(1)
        _confusion(pred, y, cm)
    return _iou_from_cm(cm)


def _fmt_iou(per: list[float]) -> str:
    """Per-class IoU jako čitelný řádek 'třída=0.42' (jen třídy s číslem, NaN se vynechá)."""
    return "  ".join(f"{LINE_LABEL_NAME[c]}={per[c]:.2f}"
                     for c in range(N_LINE) if per[c] == per[c])   # x==x → ne-NaN


# ---------------------------------------------------------------- průběžná statistika
def _save_history(history: list[dict], output_dir: Path) -> None:
    """Zapíše dosavadní historii epoch do izolovaného adresáře běhu."""
    path = output_dir / "history.csv"
    cols = ["epoch", "loss", "miou"] + [f"iou_{LINE_LABEL_NAME[c]}" for c in range(N_LINE)]
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(cols)
        for h in history:
            wr.writerow([h["epoch"], f"{h['loss']:.4f}", f"{h['miou']:.4f}"]
                        + [f"{v:.4f}" for v in h["iou"]])


def _plot_curve(history: list[dict], output_dir: Path, miou_label: str) -> None:
    """Překreslí křivku učení do izolovaného adresáře běhu."""
    eps = [h["epoch"] for h in history]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    ax1.plot(eps, [h["loss"] for h in history], "r-o", ms=3, label="train loss")
    ax1.set_xlabel("epocha"); ax1.set_ylabel("train loss", color="r")
    ax1.tick_params(axis="y", labelcolor="r"); ax1.grid(alpha=0.3)
    axb = ax1.twinx()
    axb.plot(eps, [h["miou"] for h in history], "b-s", ms=3, label=f"{miou_label} mIoU")
    axb.set_ylabel(f"{miou_label} mIoU", color="b"); axb.set_ylim(0, 1)
    axb.tick_params(axis="y", labelcolor="b")
    ax1.set_title(f"loss + mIoU (poslední: {history[-1]['miou']:.3f})")

    for c in range(N_LINE):
        ax2.plot(eps, [h["iou"][c] for h in history], "-o", ms=2, label=LINE_LABEL_NAME[c])
    ax2.set_xlabel("epocha"); ax2.set_ylabel("IoU"); ax2.set_ylim(0, 1)
    ax2.grid(alpha=0.3); ax2.legend(fontsize=7, loc="upper left")
    ax2.set_title(f"per-class IoU ({miou_label})")

    fig.tight_layout()
    fig.savefig(output_dir / "curve.png", dpi=90)
    plt.close(fig)


# -------------------------------------------------------------------------- trénink
def train(*, epochs: int, batch: int, lr: float, overfit: bool,
          weight_cap: float = WEIGHT_CAP, seed: int | None = None,
          run_id: str | None = None) -> None:
    """Hlavní tréninková smyčka. overfit=True → 2 mapy, bez augmentace (sanity gate)."""
    assert torch.cuda.is_available(), "trénink jen na CUDA GPU (mrkla/HAL3000, RTX 5070)"
    device = "cuda"
    if seed is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        np.random.seed(seed)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        print(f"[seed] reprodukovatelný běh, seed={seed} (cudnn deterministic)")
    else:
        torch.backends.cudnn.benchmark = True

    # --- data ---
    if overfit:
        from collections import Counter
        all_x = sorted((_REPO_ROOT / "resources" / "line_tiles" / "train").glob("*/*_x.png"))
        per_cid = Counter(p.parent.name for p in all_x)
        cids = [c for c, _ in per_cid.most_common(2)]
        print(f"[overfit] mapy: {cids}")
        train_ds = LineTileDataset("train", augment=False, limit_cids=cids)
        val_ds = train_ds                       # overfit: měř na týchž datech (chceme memorizaci)
    else:
        train_ds = LineTileDataset("train", augment=True)
        val_ds = LineTileDataset("val", augment=False)

    # num_workers>0 (Sez. 126): on-the-fly degrade je drahý → paralelní loading, ať GPU nehladoví.
    NW = 4
    train_dl = DataLoader(train_ds, batch_size=batch, shuffle=True, num_workers=NW,
                          drop_last=not overfit, persistent_workers=True, pin_memory=True)
    val_dl = DataLoader(val_ds, batch_size=batch, shuffle=False, num_workers=NW,
                        persistent_workers=True, pin_memory=True)

    # --- model + loss + optimizer ---
    model = build_model().to(device)
    if overfit:
        w = None                                # overfit: bez vážení, ať vidíme čistou memorizaci
    else:
        raw = torch.tensor(class_weights(), dtype=torch.float32, device=device)
        w = raw.clamp(max=weight_cap)           # strop vah (Sez. 91)
        clipped = [(LINE_LABEL_NAME[c], float(raw[c]), float(w[c]))
                   for c in range(N_LINE) if raw[c] > weight_cap]
        if clipped:
            print("cap vah @ {:.0f}: ".format(weight_cap)
                  + "  ".join(f"{n} {r:.1f}->{cv:.0f}" for n, r, cv in clipped))
    criterion = nn.CrossEntropyLoss(weight=w)   # BEZ ignore_index — Y je celé validní (0..N_LINE-1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = (None if overfit
                 else torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs))

    config = {
        "epochs": epochs, "batch": batch, "lr": lr, "overfit": overfit,
        "weight_cap": weight_cap, "seed": seed, "encoder": ENCODER, "n_line": N_LINE,
        "train_samples": len(train_ds), "val_samples": len(val_ds),
    }
    data_fingerprint = fingerprint_inputs(
        [_REPO_ROOT / "resources" / "line_tiles" / "_tiles.json"],
        [f"train={len(train_ds)}", f"val={len(val_ds)}"],
    )
    run = start_run(_CKPT_DIR, "png2line", config, data_fingerprint, run_id)
    print(f"[run] {run.run_id} → {run.run_dir}")

    print(f"train {len(train_ds)} dlaždic | val {len(val_ds)} | batch {batch} | "
          f"lr {lr} | epoch {epochs} | BF16 | {ENCODER} U-Net | {N_LINE} tříd"
          + ("" if overfit else " | cosine LR"))

    best_miou = -1.0
    history: list[dict] = []
    miou_label = "train" if overfit else "val"
    for ep in range(1, epochs + 1):
        model.train()
        t0 = time.time()
        running = 0.0
        for x, y in train_dl:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                logits = model(x)
                loss = criterion(logits, y)
            loss.backward()
            optimizer.step()
            running += loss.item()
        avg = running / len(train_dl)

        if scheduler is not None:
            scheduler.step()

        per, miou = evaluate(model, val_dl, device)
        dt = time.time() - t0
        lr_now = optimizer.param_groups[0]["lr"]
        print(f"ep {ep:>3}/{epochs}  loss {avg:.4f}  {miou_label} mIoU {miou:.3f}  "
              f"lr {lr_now:.2e}  [{_fmt_iou(per)}]  {dt:.0f}s")

        history.append({"epoch": ep, "loss": avg, "miou": miou, "iou": per})
        _save_history(history, run.run_dir)
        _plot_curve(history, run.run_dir, miou_label)

        if not overfit and miou > best_miou:
            best_miou = miou
            save_best(
                run, model.state_dict(), epoch=ep,
                metric_name="miou", metric_value=miou,
                model_metadata={"encoder": ENCODER, "n_line": N_LINE},
            )

    # --- finální eval na test (jen plný trénink, z nejlepšího checkpointu) ---
    if not overfit:
        ckpt = torch.load(run.best_path, weights_only=False)
        model.load_state_dict(ckpt["model"])
        test_dl = DataLoader(LineTileDataset("test", augment=False),
                             batch_size=batch, shuffle=False, num_workers=0)
        per, miou = evaluate(model, test_dl, device)
        print(f"\n=== TEST (best ep {ckpt['epoch']}, val mIoU {ckpt['miou']:.3f}) ===")
        print(f"test mIoU {miou:.3f}  [{_fmt_iou(per)}]")
        finish_run(run, "test_miou", miou)
        print(f"[run] dokončen; kanonický model beze změny. Promote: "
              f"python model/png2line/train.py --promote {run.run_id}")
    else:
        finish_diagnostic_run(run, "train_miou", history[-1]["miou"])
        print(f"[run] diagnostika dokončena bez promotovatelného checkpointu: {run.run_dir}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Png2Line reconstructor U-Net trénink (Sez. 130)")
    ap.add_argument("--overfit", action="store_true",
                    help="sanity gate: 2 mapy, bez augmentace, sleduj train mIoU→~1")
    ap.add_argument("--epochs", type=int, default=None, help="počet epoch (default 40 / overfit 80)")
    ap.add_argument("--batch", type=int, default=16, help="batch size (mrkla RTX 5070 baseline)")
    ap.add_argument("--lr", type=float, default=1e-4, help="learning rate (AdamW, cosine decay)")
    ap.add_argument("--weight-cap", type=float, default=WEIGHT_CAP,
                    help=f"strop median-freq vah (default {WEIGHT_CAP:.0f}, Sez. 91)")
    ap.add_argument("--seed", type=int, default=None,
                    help="fixní seed → reprodukovatelný běh; uloží se do checkpointu")
    ap.add_argument("--run-id", default=None, help="vlastní ID běhu; default UTC čas + suffix")
    ap.add_argument("--promote", metavar="RUN_ID",
                    help="atomicky povýší dokončený běh na unet_best.pt a skončí")
    args = ap.parse_args()

    if args.promote:
        if args.overfit or args.epochs is not None or args.run_id is not None:
            ap.error("--promote nelze kombinovat s parametry tréninku")
        target = promote_run(_CKPT_DIR, args.promote, "png2line")
        print(f"[promote] {args.promote} → {target}")
        raise SystemExit(0)

    n_ep = args.epochs if args.epochs is not None else (80 if args.overfit else 40)
    train(epochs=n_ep, batch=args.batch, lr=args.lr, overfit=args.overfit,
          weight_cap=args.weight_cap, seed=args.seed, run_id=args.run_id)
