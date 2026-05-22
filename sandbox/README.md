# Sandbox

Izolované experimenty (UC1). Každý experiment ve **vlastní složce** s krátkým README
(co zkoumá, jak spustit, závěr). Sandbox je k zahazování — co dozraje, povýší
do produkčního kódu / KB / Pic2Omap; co ne, zůstane jako reference.

## Konvence
- `sandbox/<NN>-<krátký-název>/` — pořadové číslo + slug (např. `01-purple-segmentation`).
- Každá složka: `README.md` (cíl / běh / závěr), kód, případně malá data.
- Velká data ne do gitu (viz `.gitignore`) — odkaz na zdroj nebo `output/`.
- Závěr experimentu se promítne do diáře sezení a (pokud relevantní) do `docs/kb/`.

*(zatím prázdný — první experiment přijde s prvním enabler-střípkem)*
