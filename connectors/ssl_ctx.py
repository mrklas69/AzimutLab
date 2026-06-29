"""
ssl_ctx.py — sdílený TLS kontext z certifi pro HTTPS konektory (UC2, ČÚZK + Livelox).

Proč existuje: ČÚZK přešel (2026-06) na nový Let's Encrypt řetěz, který default trust
store uv-cpythonu na Windows neuznává → `urllib.request.urlopen` padá na
„certificate has expired", ač je server cert platný. Dočasně se to řešilo env
workaroundem `SSL_CERT_FILE=<certifi bundle>`, který ale musel každý běh nastavit ručně
(Sez. 173). Trvalý fix: konektory ověřují řetěz proti `certifi` CA bundle PŘÍMO přes
sdílený kontext — nezávisle na prostředí.

DRY: jeden kontext pro VŠECHNY síťové konektory (arcgis/dmr/ortofoto/livelox), aby se
`certifi.where()` neřešilo per-modul ani per-request. Předává se do
`urllib.request.urlopen(req, context=ssl_context())`.

No-silent-fallback: chybí-li certifi, selži NAHLAS (ImportError s vysvětlením). Tiché
spadnutí zpět na systémový trust store je přesně ten bug, který tenhle modul řeší.
"""

import ssl

# Singleton — certifi bundle se načítá jednou, ne per-request.
_CTX: ssl.SSLContext | None = None


def ssl_context() -> ssl.SSLContext:
    """Vrátí sdílený TLS kontext ověřující serverový řetěz proti certifi CA bundle.

    Cachovaný singleton; předá se jako `context=` do `urllib.request.urlopen`.
    """
    global _CTX
    if _CTX is None:
        try:
            import certifi
        except ImportError as e:  # no-silent-fallback: bez certifi konektory ČÚZK nefungují
            raise ImportError(
                "certifi není nainstalováno — síťové konektory ČÚZK/Livelox potřebují jeho "
                "CA bundle (ČÚZK Let's Encrypt řetěz neuznávaný systémovým trust store). "
                "Doinstaluj: pip install certifi (je v requirements.txt)."
            ) from e
        _CTX = ssl.create_default_context(cafile=certifi.where())
    return _CTX
