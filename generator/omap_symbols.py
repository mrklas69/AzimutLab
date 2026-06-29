"""Sdílené parsování symbolů z `.omap` XML.

OOM ukládá atributy symbolů jako běžné XML atributy bez garantovaného pořadí.
Stringové editory `.omap` proto nesmí hledat jen variantu `id="..." code="..."`.
"""

import re

_SYMBOL_RE = re.compile(r"<symbol\b(?P<attrs>[^>]*)>")
_ATTR_RE = re.compile(r'([A-Za-z_][\w:.-]*)="([^"]*)"')


def parse_attrs(fragment: str) -> dict[str, str]:
    """Jednoduchý atributový parser pro OOM tag fragmenty."""
    return {m.group(1): m.group(2) for m in _ATTR_RE.finditer(fragment)}


def parse_symbol_ids(
    doc: str,
    required_codes: set[str] | frozenset[str] | None = None,
    *,
    source: str = ".omap",
) -> dict[str, int]:
    """Vrátí první symbol id pro ISOM kódy v dokumentu.

    `required_codes=None` znamená načíst všechny symboly s `code` a číselným `id`.
    Když je sada povinných kódů předaná, chybějící symboly jsou chyba, ne tichý
    fallback bez části kresby.
    """
    ids: dict[str, int] = {}
    for match in _SYMBOL_RE.finditer(doc):
        attrs = parse_attrs(match.group("attrs"))
        code = attrs.get("code")
        sym_id = attrs.get("id")
        if not code or sym_id is None:
            continue
        if required_codes is not None and code not in required_codes:
            continue
        try:
            ids.setdefault(code, int(sym_id))
        except ValueError as exc:
            raise ValueError(f"{source}: symbol code {code!r} má nečíselné id {sym_id!r}") from exc

    if required_codes is not None:
        missing = sorted(code for code in required_codes if code not in ids)
        if missing:
            raise ValueError(f"{source}: chybí symboly {missing}")
    return ids
