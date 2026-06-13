"""Striktně validovaná globální konfigurace AzimutLabu."""

from dataclasses import dataclass
from pathlib import Path
import tomllib


CONFIG_PATH = Path(__file__).resolve().parent.parent / "azimutlab.toml"
VEGETATION_BOUNDARY_CODES = frozenset({"416", "416.1"})


@dataclass(frozen=True)
class SymbolConfig:
    vegetation_boundary: str


@dataclass(frozen=True)
class AzimutLabConfig:
    symbols: SymbolConfig


def load_config(path: Path = CONFIG_PATH) -> AzimutLabConfig:
    """Načte projektové nastavení; chybějící či neplatná hodnota je chyba."""
    try:
        with path.open("rb") as stream:
            raw = tomllib.load(stream)
        code = raw["symbols"]["vegetation_boundary"]
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(f"Nelze načíst globální konfiguraci {path}: {exc}") from exc

    if not isinstance(code, str) or code not in VEGETATION_BOUNDARY_CODES:
        allowed = ", ".join(sorted(VEGETATION_BOUNDARY_CODES))
        raise ValueError(
            f"{path}: symbols.vegetation_boundary musí být jedna z hodnot: {allowed}"
        )
    return AzimutLabConfig(symbols=SymbolConfig(vegetation_boundary=code))


CONFIG = load_config()
