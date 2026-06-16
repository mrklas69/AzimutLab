"""Sdílená správa checkpointů živých reconstructorů.

Každý trénink zapisuje do vlastního ``runs/<run_id>/``. Kanonický
``unet_best.pt`` se mění pouze explicitním promote krokem. Zápisy velkých
checkpointů i malých JSON manifestů probíhají přes dočasný soubor ve stejném
adresáři a atomický ``os.replace``.
"""
import hashlib
import json
import os
import re
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import torch

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
FORMAT_VERSION = 1


@dataclass(frozen=True)
class RunContext:
    """Cesty a neměnná metadata jednoho izolovaného tréninkového běhu."""

    model_dir: Path
    run_id: str
    model_kind: str
    run_dir: Path
    best_path: Path
    manifest_path: Path
    created_at: str
    config: dict[str, Any]
    data_fingerprint: str


def _utc_now() -> str:
    """Vrátí UTC čas v ISO 8601, vhodný do strojově čitelných metadat."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_run_id(model_kind: str) -> str:
    """Vytvoří čitelný a prakticky unikátní identifikátor běhu."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{model_kind}-{secrets.token_hex(3)}"


def validate_run_id(run_id: str) -> str:
    """Odmítne cesty a nejednoznačné názvy dřív, než se sáhne na filesystem."""
    if not _RUN_ID_RE.fullmatch(run_id):
        raise ValueError(
            "run_id musí začínat písmenem nebo číslicí a smí obsahovat jen "
            "A-Z, a-z, 0-9, tečku, podtržítko a pomlčku (max. 96 znaků)"
        )
    return run_id


def fingerprint_inputs(files: Iterable[Path], values: Iterable[str] = ()) -> str:
    """Spočítá SHA-256 nad důležitými manifesty a doplňkovými hodnotami.

    Chybějící soubor je chyba, ne tichý fallback. U velkých rastrů se do této
    funkce neposílají binární data, ale jejich kanonický split/tiles manifest.
    """
    digest = hashlib.sha256()
    for path in sorted((Path(p) for p in files), key=lambda p: str(p)):
        if not path.is_file():
            raise FileNotFoundError(f"chybí vstup pro fingerprint: {path}")
        # Absolutní cesta se mezi HAL3000/ntbhej liší; poslední tři části
        # zachovají např. classId/gen_pointbase/meta.json bez vazby na checkout.
        portable_name = "/".join(path.parts[-3:])
        digest.update(portable_name.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    for value in sorted(str(v) for v in values):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _temporary_path(target: Path) -> Path:
    """Vrátí unikátní dočasnou cestu ve stejném adresáři jako cíl."""
    return target.with_name(f".{target.name}.{secrets.token_hex(6)}.tmp")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    """Zapíše JSON atomicky, aby přerušený proces nenechal půl souboru."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_torch_save(payload: dict[str, Any], path: Path) -> None:
    """Uloží PyTorch checkpoint atomicky ve stejném adresáři."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        torch.save(payload, temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def start_run(
    model_dir: Path,
    model_kind: str,
    config: dict[str, Any],
    data_fingerprint: str,
    run_id: str | None = None,
) -> RunContext:
    """Založí nový izolovaný běh; existující run_id se nikdy nepřepíše."""
    chosen_id = validate_run_id(run_id or default_run_id(model_kind))
    run_dir = Path(model_dir) / "runs" / chosen_id
    run_dir.mkdir(parents=True, exist_ok=False)
    created_at = _utc_now()
    context = RunContext(
        model_dir=Path(model_dir),
        run_id=chosen_id,
        model_kind=model_kind,
        run_dir=run_dir,
        best_path=run_dir / "best.pt",
        manifest_path=run_dir / "manifest.json",
        created_at=created_at,
        config=dict(config),
        data_fingerprint=data_fingerprint,
    )
    _atomic_json(
        context.manifest_path,
        {
            "format_version": FORMAT_VERSION,
            "status": "running",
            "model_kind": model_kind,
            "run_id": chosen_id,
            "created_at": created_at,
            "config": context.config,
            "data_fingerprint": data_fingerprint,
        },
    )
    return context


def save_best(
    run: RunContext,
    model_state: dict[str, Any],
    epoch: int,
    metric_name: str,
    metric_value: float,
    model_metadata: dict[str, Any],
) -> None:
    """Atomicky nahradí nejlepší checkpoint pouze uvnitř daného běhu."""
    checkpoint = {
        "format_version": FORMAT_VERSION,
        "model": model_state,
        "epoch": epoch,
        metric_name: metric_value,
        # Zachování dosavadních top-level klíčů chrání případné externí čtečky.
        **model_metadata,
        "metadata": {
            "model_kind": run.model_kind,
            "run_id": run.run_id,
            "created_at": run.created_at,
            "config": run.config,
            "data_fingerprint": run.data_fingerprint,
            "selection_metric": {"name": metric_name, "value": metric_value},
            **model_metadata,
        },
    }
    atomic_torch_save(checkpoint, run.best_path)
    _atomic_json(
        run.manifest_path,
        {
            "format_version": FORMAT_VERSION,
            "status": "running",
            "model_kind": run.model_kind,
            "run_id": run.run_id,
            "created_at": run.created_at,
            "config": run.config,
            "data_fingerprint": run.data_fingerprint,
            "best": {
                "path": "best.pt",
                "epoch": epoch,
                "metric": {"name": metric_name, "value": metric_value},
            },
        },
    )


def finish_run(run: RunContext, test_metric_name: str, test_metric_value: float) -> None:
    """Doplní test metriku do checkpointu a uzavře manifest běhu."""
    if not run.best_path.is_file():
        raise FileNotFoundError(f"běh nemá nejlepší checkpoint: {run.best_path}")
    checkpoint = torch.load(run.best_path, weights_only=False, map_location="cpu")
    checkpoint["metadata"]["test_metric"] = {
        "name": test_metric_name,
        "value": test_metric_value,
    }
    checkpoint["metadata"]["finished_at"] = _utc_now()
    atomic_torch_save(checkpoint, run.best_path)

    manifest = json.loads(run.manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "completed"
    manifest["finished_at"] = checkpoint["metadata"]["finished_at"]
    manifest["test_metric"] = checkpoint["metadata"]["test_metric"]
    _atomic_json(run.manifest_path, manifest)


def finish_diagnostic_run(run: RunContext, metric_name: str, metric_value: float) -> None:
    """Uzavře overfit/smoke běh, který záměrně nevytváří promotovatelný checkpoint."""
    manifest = json.loads(run.manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "diagnostic_completed"
    manifest["finished_at"] = _utc_now()
    manifest["diagnostic_metric"] = {"name": metric_name, "value": metric_value}
    _atomic_json(run.manifest_path, manifest)


def promote_run(model_dir: Path, run_id: str, expected_model_kind: str) -> Path:
    """Atomicky povýší zvolený dokončený běh na kanonický ``unet_best.pt``."""
    chosen_id = validate_run_id(run_id)
    model_dir = Path(model_dir)
    source = model_dir / "runs" / chosen_id / "best.pt"
    manifest_path = source.with_name("manifest.json")
    if not source.is_file() or not manifest_path.is_file():
        raise FileNotFoundError(f"nenalezen dokončený běh {chosen_id}: {source.parent}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "completed":
        raise RuntimeError(f"běh {chosen_id} není dokončený (status={manifest.get('status')!r})")
    if manifest.get("model_kind") != expected_model_kind:
        raise RuntimeError(
            f"běh {chosen_id} patří modelu {manifest.get('model_kind')!r}, "
            f"očekáván {expected_model_kind!r}"
        )

    checkpoint = torch.load(source, weights_only=False, map_location="cpu")
    metadata = checkpoint.get("metadata", {})
    if metadata.get("run_id") != chosen_id or metadata.get("model_kind") != expected_model_kind:
        raise RuntimeError(f"checkpoint {source} neodpovídá svému manifestu")

    target = model_dir / "unet_best.pt"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(target)
    try:
        with source.open("rb") as source_handle, temporary.open("wb") as target_handle:
            shutil.copyfileobj(source_handle, target_handle, length=1024 * 1024)
            target_handle.flush()
            os.fsync(target_handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

    _atomic_json(
        model_dir / "promoted.json",
        {
            "format_version": FORMAT_VERSION,
            "model_kind": expected_model_kind,
            "run_id": chosen_id,
            "promoted_at": _utc_now(),
            "source": str(source.relative_to(model_dir)),
            "selection_metric": metadata.get("selection_metric"),
            "test_metric": metadata.get("test_metric"),
            "data_fingerprint": metadata.get("data_fingerprint"),
        },
    )
    return target
