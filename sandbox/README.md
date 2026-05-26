# Sandbox

Izolované experimenty (UC1). Každý experiment ve **vlastní složce** s krátkým README
(co zkoumá, jak spustit, závěr). Sandbox je k zahazování — co dozraje, povýší
do produkčního kódu / KB / Pic2Omap; co ne, zůstane jako reference.

## Konvence
- `sandbox/<název>/` — každý experiment ve vlastní složce. Pořadový prefix `<NN>-`
  (např. `01-purple-segmentation`) je **doporučený, ne povinný** — zaběhlé popisné
  názvy (`generator-poc/`) jsou v pořádku, ať se nemusí přepisovat odkazy napříč repem.
- Každá složka: `README.md` (cíl / běh / závěr), kód, případně malá data.
- Velká data ne do gitu (viz `.gitignore`) — odkaz na zdroj nebo `output/`.
- Závěr experimentu se promítne do diáře sezení a (pokud relevantní) do `docs/kb/`.

## Experimenty
- **`generator-poc/`** (od Sez. 4, živé) — procedurální generátor výseku OB mapy: vrstevnice
  z výškového pole + bodové symboly extrémů (109/110/111) + cesty (proc Dijkstra / real ZABAGED)
  + reálná voda a budovy (ZABAGED) + kartografická generalizace, ground-truth masky zdarma.
  Reálný terén z ČÚZK DMR 5G (`--terrain real`), vektor vrstevnic (`contours.geojson` + `.omap`).
  Plošné vrstvy vegetace/bažiny/balvany byly vědomě zahozeny (Sez. 11 — vypadaly uměle).
  První reálný kód v repu (enabler-feeder pro UC5). Detail: `generator-poc/README.md`,
  metodika `docs/kb/generator-procedural.md`.
