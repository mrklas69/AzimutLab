"""
train.py — trénink reconstructor modelu Png2Area (Sez. 88).

První ze tří CV úloh dekompozice OOM podle geometrie (Sez. 80): Png2Area (plochy) → mapový sken RGB
predikuje area label rastr (16 tříd: 0 pozadí + 15 ISOM plošných kódů, schéma omap_raster Sez. 87).
Páry [scan.png, area_labels.png] vyrábí generator/pairs.py; tile.py je krájí, dataset.py je čte.
Izomorfní s archivovaným model/runnability/train.py (reuse U-Net/loss/IoU/křivka) — liší se: vstup je
mapa ne ortofoto, 16 area tříd ne 5 runnability, BEZ ignore_index (Y z naší .omap je celé validní).

Architektura: U-Net s ResNet34 encoderem, ImageNet-pretrained (segmentation-models-pytorch).
Precedent z Pic2Omapu (U-Net resnet34 area segmentation, mIoU 0,666 — viz hardware.md).

Trénink jen na `mrkla` (RTX 5070, Blackwell sm_120). Mixed precision = BF16 autocast
(Tensor Cores; BF16 nepotřebuje GradScaler na rozdíl od FP16, má dost exponentu).

Dva režimy (CLI):
  python model/png2area/train.py --overfit   # sanity gate: 2 mapy, bez augmentace, train mIoU→~1
  python model/png2area/train.py             # plný trénink na train splitu, eval na val + test

Třída je nevyvážená (pozadí 60–90 % vs vzácné plochy <1 %) → CrossEntropyLoss s median-freq váhami
z tile.py (resources/area_tiles/_tiles.json). Metrika = per-class IoU + mIoU (accuracy by schovala,
že vzácné třídy model ignoruje).

Sys.path skript (fáze B). Checkpoint best (dle val mIoU) → resources/area_model/ (gitignored).
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

_REPO_ROOT = Path(__file__).resolve().parents[2]   # model/png2area/ → o dvě úrovně hloub
sys.path.insert(0, str(_REPO_ROOT / "model" / "png2area"))
sys.path.insert(0, str(_REPO_ROOT / "generator"))

import segmentation_models_pytorch as smp   # noqa: E402

from dataset import AreaTileDataset, class_weights   # noqa: E402
from omap_raster import N_AREA, LABEL_NAME   # noqa: E402  (SSoT area schématu, Sez. 87)

_CKPT_DIR = _REPO_ROOT / "resources" / "area_model"
ENCODER = "resnet34"

# Strop median-freq vah (Sez. 91). Bez něj obří váhy (208=120 / 501=36 / 402=23) rozhoupávaly
# loss (spiky ep 30/36, Sez. 90) — jeden batch s několika px vzácné třídy vystřelí gradient.
# Cap je tréninkový HYPERPARAMETR (jak agresivně vážit), ne vlastnost dat → žije tady, ne v
# _tiles.json (ten drží surové median-freq váhy = SSoT). Tím zůstává raw váha dohledatelná
# a cap laditelný (--weight-cap) bez re-tilingu.
WEIGHT_CAP = 10.0


# ----------------------------------------------------------------------------- model
def build_model() -> nn.Module:
    """U-Net + ResNet34 encoder (ImageNet pretrained), 3 vstupní kanály → N_AREA tříd."""
    return smp.Unet(
        encoder_name=ENCODER,
        encoder_weights="imagenet",   # pretrained encoder → rychlejší konvergence
        in_channels=3,
        classes=N_AREA,
    )


# ------------------------------------------------------------------------- metriky
def _confusion(pred: torch.Tensor, target: torch.Tensor, cm: torch.Tensor) -> None:
    """Akumuluje confusion matici (N_AREA×N_AREA) na GPU. Bez IGNORE — všechny px validní.

    pred/target jsou (B,H,W) long. cm[t,p] += počet px s GT t a predikcí p. Bincount nad
    zploštělým indexem t*N+p je rychlejší než smyčka přes třídy."""
    t = target.reshape(-1)
    p = pred.reshape(-1)
    idx = t * N_AREA + p
    cm += torch.bincount(idx, minlength=N_AREA * N_AREA).reshape(N_AREA, N_AREA)


def _iou_from_cm(cm: torch.Tensor) -> tuple[list[float], float]:
    """Per-class IoU + mIoU z confusion matice.

    IoU_c = TP / (TP + FP + FN) = diag / (řádek + sloupec − diag). Třída bez px (GT i pred) = NaN
    → vynecháme z mIoU (jinak by ji stáhla k nule). Vrací (per-class list, mIoU)."""
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
    cm = torch.zeros(N_AREA, N_AREA, dtype=torch.long, device=device)
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits = model(x)
        pred = logits.argmax(1)
        _confusion(pred, y, cm)
    return _iou_from_cm(cm)


def _fmt_iou(per: list[float]) -> str:
    """Per-class IoU jako čitelný řádek 'kód=0.42' (jen třídy s číslem, NaN se vynechá)."""
    return "  ".join(f"{LABEL_NAME[c]}={per[c]:.2f}"
                     for c in range(N_AREA) if per[c] == per[c])   # x==x → ne-NaN


# ---------------------------------------------------------------- průběžná statistika
def _save_history(history: list[dict], tag: str) -> None:
    """Zapíše dosavadní historii epoch do CSV (resources/area_model/history_<tag>.csv)."""
    path = _CKPT_DIR / f"history_{tag}.csv"
    cols = ["epoch", "loss", "miou"] + [f"iou_{LABEL_NAME[c]}" for c in range(N_AREA)]
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(cols)
        for h in history:
            wr.writerow([h["epoch"], f"{h['loss']:.4f}", f"{h['miou']:.4f}"]
                        + [f"{v:.4f}" for v in h["iou"]])


def _plot_curve(history: list[dict], tag: str, miou_label: str) -> None:
    """Překreslí křivku učení → resources/area_model/curve_<tag>.png (2 panely)."""
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

    # --- pravý: per-class IoU (16 tříd → menší legenda) ---
    for c in range(N_AREA):
        ax2.plot(eps, [h["iou"][c] for h in history], "-o", ms=2, label=LABEL_NAME[c])
    ax2.set_xlabel("epocha"); ax2.set_ylabel("IoU"); ax2.set_ylim(0, 1)
    ax2.grid(alpha=0.3); ax2.legend(fontsize=6, loc="upper left", ncol=2)
    ax2.set_title(f"per-class IoU ({miou_label})")

    fig.tight_layout()
    fig.savefig(_CKPT_DIR / f"curve_{tag}.png", dpi=90)
    plt.close(fig)


# -------------------------------------------------------------------------- trénink
def train(*, epochs: int, batch: int, lr: float, overfit: bool,
          weight_cap: float = WEIGHT_CAP) -> None:
    """Hlavní tréninková smyčka. overfit=True → 2 mapy, bez augmentace (sanity gate)."""
    assert torch.cuda.is_available(), "trénink jen na CUDA GPU (mrkla, RTX 5070)"
    device = "cuda"
    torch.backends.cudnn.benchmark = True   # fixní rozměr dlaždice → cudnn si najde rychlé kernely

    # --- data ---
    if overfit:
        from collections import Counter
        all_x = sorted((_REPO_ROOT / "resources" / "area_tiles" / "train").glob("*/*_x.png"))
        per_cid = Counter(p.parent.name for p in all_x)
        cids = [c for c, _ in per_cid.most_common(2)]
        print(f"[overfit] mapy: {cids}")
        train_ds = AreaTileDataset("train", augment=False, limit_cids=cids)
        val_ds = train_ds                       # overfit: měř na týchž datech (chceme memorizaci)
    else:
        train_ds = AreaTileDataset("train", augment=True)
        val_ds = AreaTileDataset("val", augment=False)

    # num_workers=0: Windows + sys.path skript (spawn by reimportoval); IO je z SSD svižné.
    train_dl = DataLoader(train_ds, batch_size=batch, shuffle=True,
                          num_workers=0, drop_last=not overfit)
    val_dl = DataLoader(val_ds, batch_size=batch, shuffle=False, num_workers=0)

    # --- model + loss + optimizer ---
    model = build_model().to(device)
    if overfit:
        w = None                                # overfit: bez vážení, ať vidíme čistou memorizaci
    else:
        raw = torch.tensor(class_weights(), dtype=torch.float32, device=device)
        w = raw.clamp(max=weight_cap)           # strop vah (Sez. 91) — viz WEIGHT_CAP
        # vypiš, které třídy cap reálně ořízl (raw → capped), ať je zásah dohledatelný
        clipped = [(LABEL_NAME[c], float(raw[c]), float(w[c]))
                   for c in range(N_AREA) if raw[c] > weight_cap]
        if clipped:
            print("cap vah @ {:.0f}: ".format(weight_cap)
                  + "  ".join(f"{n} {r:.1f}->{cv:.0f}" for n, r, cv in clipped))
    criterion = nn.CrossEntropyLoss(weight=w)   # BEZ ignore_index — Y je celé validní (0..N_AREA-1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    # Cosine LR decay (Sez. 91): LR plynule k ~0 ke konci tréninku → uhladí finální oscilace
    # vah/loss. Jen plný trénink (overfit chce čistou memorizaci s fixním LR = baseline).
    scheduler = (None if overfit
                 else torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs))

    print(f"train {len(train_ds)} dlaždic | val {len(val_ds)} | batch {batch} | "
          f"lr {lr} | epoch {epochs} | BF16 | {ENCODER} U-Net | {N_AREA} tříd"
          + ("" if overfit else " | cosine LR"))

    best_miou = -1.0
    history: list[dict] = []
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

        if scheduler is not None:
            scheduler.step()                    # posun LR podle cosine rozvrhu (po epoše)

        per, miou = evaluate(model, val_dl, device)
        dt = time.time() - t0
        lr_now = optimizer.param_groups[0]["lr"]
        print(f"ep {ep:>3}/{epochs}  loss {avg:.4f}  {miou_label} mIoU {miou:.3f}  "
              f"lr {lr_now:.2e}  [{_fmt_iou(per)}]  {dt:.0f}s")

        history.append({"epoch": ep, "loss": avg, "miou": miou, "iou": per})
        _save_history(history, tag)
        _plot_curve(history, tag, miou_label)

        if not overfit and miou > best_miou:
            best_miou = miou
            torch.save({"model": model.state_dict(), "epoch": ep, "miou": miou,
                        "encoder": ENCODER, "n_area": N_AREA},
                       _CKPT_DIR / "unet_best.pt")

    # --- finální eval na test (jen plný trénink, z nejlepšího checkpointu) ---
    if not overfit:
        ckpt = torch.load(_CKPT_DIR / "unet_best.pt", weights_only=False)
        model.load_state_dict(ckpt["model"])
        test_dl = DataLoader(AreaTileDataset("test", augment=False),
                             batch_size=batch, shuffle=False, num_workers=0)
        per, miou = evaluate(model, test_dl, device)
        print(f"\n=== TEST (best ep {ckpt['epoch']}, val mIoU {ckpt['miou']:.3f}) ===")
        print(f"test mIoU {miou:.3f}  [{_fmt_iou(per)}]")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Png2Area reconstructor U-Net trénink (Sez. 88)")
    ap.add_argument("--overfit", action="store_true",
                    help="sanity gate: 2 mapy, bez augmentace, sleduj train mIoU→~1")
    ap.add_argument("--epochs", type=int, default=None, help="počet epoch (default 40 / overfit 80)")
    ap.add_argument("--batch", type=int, default=16,
                    help="batch size (mrkla RTX 5070 → 16 = zdokumentovaný baseline Sez. 78)")
    ap.add_argument("--lr", type=float, default=1e-4, help="learning rate (AdamW, cosine decay)")
    ap.add_argument("--weight-cap", type=float, default=WEIGHT_CAP,
                    help=f"strop median-freq vah (default {WEIGHT_CAP:.0f}, Sez. 91)")
    args = ap.parse_args()

    n_ep = args.epochs if args.epochs is not None else (80 if args.overfit else 40)
    train(epochs=n_ep, batch=args.batch, lr=args.lr, overfit=args.overfit,
          weight_cap=args.weight_cap)
