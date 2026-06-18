"""
train.py — trénink UC5 runnability modelu (Sez. 78, krok 4).

⟲ ARCHIVOVÁNO (Sez. 79) — směr `ortofoto → 4 runnability barvy` je DOLOŽENÁ slepá ulička
(val mIoU strop ~0,25, Sez. 78: podrost pod korunami z ortofota shora nevidět). Kód NEMAZÁN
(je to doložený nález „tudy ne"). Aktuální směr Laboratoře = `reconstructor()` (sken → `.omap`),
viz GLOSSARY `generator()`/`reconstructor()` + docs/TODO. U-Net/loss/IoU/křivka učení jsou ale
znovupoužitelné pro budoucí modely (Png2Area = mapa→plochy, reuse tohoto skeletu).

Segmentační síť ortofoto RGB → runnability (5 tříd ISOM): 0 průchodný, 1 = 406 slow,
2 = 408 walk, 3 = 410 fight, 4 = open. Label 255 (přetisk tratě + layout mimo mapu) je
IGNORE — loss i IoU ho přeskočí (ignore_index).

Architektura: U-Net s ResNet34 encoderem, ImageNet-pretrained (segmentation-models-pytorch).
Precedent z Pic2Omapu (U-Net resnet34 area segmentation, mIoU 0,666 — viz hardware.md).

Trénink jen na `mrkla` (RTX 5070, Blackwell sm_120). Mixed precision = BF16 autocast
(Tensor Cores; BF16 nepotřebuje GradScaler na rozdíl od FP16, má dost exponentu).

Dva režimy (CLI):
  python model/runnability/train.py --overfit   # sanity gate: 2 mapy, bez augmentace, train mIoU→~1
  python model/runnability/train.py             # plný trénink na train splitu, eval na val + test

Třída je nevyvážená (průchodný 69 % vs 410 fight 1,3 %) → CrossEntropyLoss s median-freq
váhami z tile.py (resources/tiles/_tiles.json). Metrika = per-class IoU + mIoU (accuracy by
schovala, že vzácné třídy model ignoruje).

Sys.path skript (fáze B). Checkpoint best (dle val mIoU) → resources/model/ (gitignored).
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")   # headless backend — kreslíme do PNG, žádné GUI okno (běží i na pozadí)
import matplotlib.pyplot as plt   # noqa: E402
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

_REPO_ROOT = Path(__file__).resolve().parents[2]   # model/runnability/ → o úroveň hloub (Sez. 88)
sys.path.insert(0, str(_REPO_ROOT / "model" / "runnability"))
sys.path.insert(0, str(_REPO_ROOT / "connectors"))

import segmentation_models_pytorch as smp   # noqa: E402

from dataset import TileDataset, class_weights   # noqa: E402
from map_gt import IGNORE, LABEL_NAME, N_CLASS   # noqa: E402  (N_CLASS = SSoT v map_gt, audit Sez. 81)

_CKPT_DIR = _REPO_ROOT / "resources" / "model"
ENCODER = "resnet34"


# ----------------------------------------------------------------------------- model
def build_model() -> nn.Module:
    """U-Net + ResNet34 encoder (ImageNet pretrained), 3 vstupní kanály → 5 tříd."""
    return smp.Unet(
        encoder_name=ENCODER,
        encoder_weights="imagenet",   # pretrained encoder → rychlejší konvergence
        in_channels=3,
        classes=N_CLASS,
    )


# ------------------------------------------------------------------------- metriky
def _confusion(pred: torch.Tensor, target: torch.Tensor, cm: torch.Tensor) -> None:
    """Akumuluje confusion matici (N_CLASS×N_CLASS) na GPU; IGNORE pixely vynechá.

    pred/target jsou (B,H,W) long. cm[t,p] += počet pixelů s GT t a predikcí p.
    Bincount nad zploštělým indexem t*N+p je rychlejší než smyčka přes třídy.
    """
    valid = target != IGNORE
    t = target[valid]
    p = pred[valid]
    idx = t * N_CLASS + p
    cm += torch.bincount(idx, minlength=N_CLASS * N_CLASS).reshape(N_CLASS, N_CLASS)


def _iou_from_cm(cm: torch.Tensor) -> tuple[list[float], float]:
    """Per-class IoU + mIoU z confusion matice.

    IoU_c = TP / (TP + FP + FN) = diag / (řádek + sloupec − diag). Třída bez pixelů (GT i pred)
    = NaN → vynecháme z mIoU (jinak by ji stáhla k nule). Vrací (per-class list, mIoU).
    """
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
    cm = torch.zeros(N_CLASS, N_CLASS, dtype=torch.long, device=device)
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits = model(x)
        pred = logits.argmax(1)
        _confusion(pred, y, cm)
    return _iou_from_cm(cm)


def _fmt_iou(per: list[float]) -> str:
    """Per-class IoU jako čitelný řádek 'název=0.42'."""
    return "  ".join(f"{LABEL_NAME[c].split()[0]}={per[c]:.3f}" for c in range(N_CLASS))


# ---------------------------------------------------------------- průběžná statistika
def _save_history(history: list[dict], tag: str) -> None:
    """Zapíše dosavadní historii epoch do CSV (resources/model/history_<tag>.csv).

    history = list dictů {epoch, loss, miou, iou0..iou4}. Přepisuje celý soubor po každé
    epoše (krátký, jednodušší než append) → uživatel může otevřít kdykoli za běhu.
    """
    path = _CKPT_DIR / f"history_{tag}.csv"
    cols = ["epoch", "loss", "miou"] + [f"iou_{LABEL_NAME[c].split()[0]}" for c in range(N_CLASS)]
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(cols)
        for h in history:
            wr.writerow([h["epoch"], f"{h['loss']:.4f}", f"{h['miou']:.4f}"]
                        + [f"{v:.4f}" for v in h["iou"]])


def _plot_curve(history: list[dict], tag: str, miou_label: str) -> None:
    """Překreslí křivku učení → resources/model/curve_<tag>.png (2 panely).

    Levý panel: train loss + mIoU (dvě osy y). Pravý panel: per-class IoU (5 čar).
    Volá se po každé epoše → uživatel sleduje učení live obnovováním obrázku.
    """
    eps = [h["epoch"] for h in history]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # --- levý: loss (vlevo) + mIoU (vpravo, twin osa) ---
    ax1.plot(eps, [h["loss"] for h in history], "r-o", ms=3, label="train loss")
    ax1.set_xlabel("epocha"); ax1.set_ylabel("train loss", color="r")
    ax1.tick_params(axis="y", labelcolor="r"); ax1.grid(alpha=0.3)
    axb = ax1.twinx()
    axb.plot(eps, [h["miou"] for h in history], "b-s", ms=3, label=f"{miou_label} mIoU")
    axb.set_ylabel(f"{miou_label} mIoU", color="b"); axb.set_ylim(0, 1)
    axb.tick_params(axis="y", labelcolor="b")
    ax1.set_title(f"loss + mIoU (poslední: {history[-1]['miou']:.3f})")

    # --- pravý: per-class IoU ---
    for c in range(N_CLASS):
        ax2.plot(eps, [h["iou"][c] for h in history], "-o", ms=3, label=LABEL_NAME[c])
    ax2.set_xlabel("epocha"); ax2.set_ylabel("IoU"); ax2.set_ylim(0, 1)
    ax2.grid(alpha=0.3); ax2.legend(fontsize=8, loc="upper left")
    ax2.set_title(f"per-class IoU ({miou_label})")

    fig.tight_layout()
    fig.savefig(_CKPT_DIR / f"curve_{tag}.png", dpi=90)
    plt.close(fig)


# -------------------------------------------------------------------------- trénink
def train(*, epochs: int, batch: int, lr: float, overfit: bool) -> None:
    """Hlavní tréninková smyčka. overfit=True → 2 mapy, bez augmentace (sanity gate)."""
    assert torch.cuda.is_available(), "trénink jen na CUDA GPU (mrkla, RTX 5070)"
    device = "cuda"
    torch.backends.cudnn.benchmark = True   # fixní rozměr dlaždice → cudnn si najde rychlé kernely

    # --- data ---
    if overfit:
        # vezmi 2 train mapy s nejvíc dlaždicemi (dost signálu, ať se má co naučit)
        from collections import Counter
        all_x = sorted((_REPO_ROOT / "resources" / "tiles" / "train").glob("*/*_x.png"))
        per_cid = Counter(p.parent.name for p in all_x)
        cids = [c for c, _ in per_cid.most_common(2)]
        print(f"[overfit] mapy: {cids}")
        train_ds = TileDataset("train", augment=False, limit_cids=cids)
        val_ds = train_ds                       # overfit: měř na týchž datech (chceme memorizaci)
    else:
        train_ds = TileDataset("train", augment=True)
        val_ds = TileDataset("val", augment=False)

    # num_workers=0: Windows + sys.path skript (spawn by reimportoval); IO je z SSD svižné.
    train_dl = DataLoader(train_ds, batch_size=batch, shuffle=True,
                          num_workers=0, drop_last=not overfit)
    val_dl = DataLoader(val_ds, batch_size=batch, shuffle=False, num_workers=0)

    # --- model + loss + optimizer ---
    model = build_model().to(device)
    w = torch.tensor(class_weights(), dtype=torch.float32, device=device)
    if overfit:
        w = None                                # overfit: bez vážení, ať vidíme čistou memorizaci
    criterion = nn.CrossEntropyLoss(weight=w, ignore_index=IGNORE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    print(f"train {len(train_ds)} dlaždic | val {len(val_ds)} | batch {batch} | "
          f"lr {lr} | epoch {epochs} | BF16 | {ENCODER} U-Net")

    best_miou = -1.0
    history: list[dict] = []                 # per-epoch metriky → CSV + křivka učení
    tag = "overfit" if overfit else "full"
    miou_label = "train" if overfit else "val"
    _CKPT_DIR.mkdir(parents=True, exist_ok=True)
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

        per, miou = evaluate(model, val_dl, device)
        dt = time.time() - t0
        print(f"ep {ep:>3}/{epochs}  loss {avg:.4f}  {miou_label} mIoU {miou:.3f}  "
              f"[{_fmt_iou(per)}]  {dt:.0f}s")

        # průběžná statistika: zapiš CSV + překresli křivku učení (uživatel sleduje live)
        history.append({"epoch": ep, "loss": avg, "miou": miou, "iou": per})
        _save_history(history, tag)
        _plot_curve(history, tag, miou_label)

        if not overfit and miou > best_miou:
            best_miou = miou
            torch.save({"model": model.state_dict(), "epoch": ep, "miou": miou,
                        "encoder": ENCODER, "n_class": N_CLASS},
                       _CKPT_DIR / "unet_best.pt")

    # --- finální eval na test (jen plný trénink, z nejlepšího checkpointu) ---
    if not overfit:
        ckpt = torch.load(_CKPT_DIR / "unet_best.pt", weights_only=False)
        model.load_state_dict(ckpt["model"])
        test_dl = DataLoader(TileDataset("test", augment=False),
                             batch_size=batch, shuffle=False, num_workers=0)
        per, miou = evaluate(model, test_dl, device)
        print(f"\n=== TEST (best ep {ckpt['epoch']}, val mIoU {ckpt['miou']:.3f}) ===")
        print(f"test mIoU {miou:.3f}  [{_fmt_iou(per)}]")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="UC5 runnability U-Net trénink")
    ap.add_argument("--overfit", action="store_true",
                    help="sanity gate: 2 mapy, bez augmentace, sleduj train mIoU→~1")
    ap.add_argument("--epochs", type=int, default=None, help="počet epoch (default 40 / overfit 80)")
    ap.add_argument("--batch", type=int, default=16,
                    help="batch size (mrkla RTX 5070 12 GB → 16 = zdokumentovaný baseline Sez. 78)")
    ap.add_argument("--lr", type=float, default=1e-4, help="learning rate (AdamW)")
    args = ap.parse_args()

    n_ep = args.epochs if args.epochs is not None else (80 if args.overfit else 40)
    train(epochs=n_ep, batch=args.batch, lr=args.lr, overfit=args.overfit)
