# STATISTICS — testovací mapy AzimutLab

Počty objektů per ISOM symbol napříč 5 DEV_LOCATIONS (`generator.py --location KÓD`).
Regeneruj skriptem `stats.py` po každém regen kanonika nebo po změně rendereru.

**Kanonické lokality** (různé formáty výseku pro test ořezu DMR/ZABAGED/ortofoto):

- **SV** — Soví vrch / Lužické hory  (`Soví vrch/`)
- **NL** — Nová Louka / Jizerské hory  (`Nová Louka/`)
- **LS** — Lidové sady / Liberec  (`Lidové sady/`)
- **HS** — Hruboskalsko / Český ráj  (`Hrubá Skála/`)
- **NV** — Novina / Lužické hory  (`Novina/`)

## Symboly × lokality

| Symbol | Název ISOM 2017-2 | SV | NL | LS | HS | NV |
|--------|-------------------|---:|---:|---:|---:|---:|
| **101** | Contour | 371 | 194 | 283 | 425 | 266 |
| **102** | Index contour | 91 | 46 | 88 | 99 | 61 |
| **103** | Form line | 228 | 108 | 250 | 246 | 55 |
| **109** | Small knoll | 49 | 18 | 74 | 232 | 11 |
| **110** | Small elongated knoll | 6 | 5 | 21 | 46 | 2 |
| **111** | Small depression | 21 | 39 | 106 | 158 | 10 |
| **204** | Boulder | 3109 | 2102 | 3419 | 5588 | 770 |
| **206** | Gigantic boulder | 58 | 3 | 77 | 753 | 27 |
| **207** | Boulder cluster | 146 | 178 | 132 | 171 | 9 |
| **208** | Boulder field | 7 | · | · | 3 | 4 |
| **210** | Stony ground | 6582 | 4590 | 7721 | 12258 | 1546 |
| **301** | Uncrossable body of water | 14 | 11 | 58 | 41 | 12 |
| **304** | Crossable watercourse | 70 | 90 | 124 | 28 | 43 |
| **305** | Small crossable watercourse | 107 | 119 | 148 | 90 | 88 |
| **306** | Minor seasonal water channel | 43 | 82 | 6 | 17 | 2 |
| **308** | Marsh | 3 | 2 | · | 7 | 7 |
| **310** | Indistinct marsh | 2 | 7 | · | 3 | 8 |
| **311** | Well, fountain or water tank | · | · | 6 | 2 | · |
| **312** | Spring | 10 | 6 | 16 | 23 | 10 |
| **203.2** | Cave or rocky pit | 5 | 1 | · | · | 3 |
| **401** | Open land | 79 | 21 | 161 | 138 | 39 |
| **402** | Open land with scattered trees | · | · | 13 | · | · |
| **402.1** | Open land with scattered bushes | 5 | 1 | 203 | 7 | 1 |
| **406** | Vegetation: slow running | 83 | 4 | 47 | 121 | 18 |
| **408** | Vegetation: walk | · | · | · | · | · |
| **410** | Vegetation: fight | · | · | · | · | · |
| **416** | Distinct vegetation boundary | · | · | · | · | · |
| **412** | Cultivated land | 16 | 7 | 21 | 57 | 11 |
| **520** | Area that shall not be entered | 354 | 30 | 1625 | 246 | 67 |
| **501** | Paved area | · | · | 8 | · | · |
| **501.1** | Paved area (no bounding line) | 5 | 2 | 60 | 9 | 3 |
| **502** | Wide road | 212 | 15 | 3192 | 170 | 29 |
| **503** | Road | 195 | 181 | 301 | 325 | 180 |
| **504** | Vehicle track | 466 | 98 | 231 | 393 | 253 |
| **505** | Footpath | · | 9 | 89 | 2 | 1 |
| **506** | Small footpath | 39 | 61 | 182 | 145 | 36 |
| **508** | Narrow ride | 46 | 119 | 20 | 16 | 44 |
| **509** | Railway | · | · | 40 | 3 | 5 |
| **510** | Power line, cableway or skilift | 32 | 5 | 20 | 41 | 10 |
| **521** | Building | 1171 | 133 | 9124 | 1449 | 331 |
| **523** | Ruin | 8 | · | 7 | 5 | · |
| **512** | Bridge/tunnel | 17 | 13 | 67 | 11 | 21 |
| **512.2** | Footbridge | 7 | 5 | 11 | 2 | 5 |
| **524** | High tower | 7 | 1 | 42 | 9 | 1 |
| **526** | Cairn | 4 | 13 | 21 | 9 | · |
| **530** | Prominent man-made feature | 33 | 8 | 53 | 50 | 5 |
| **417** | Prominent large tree | 38 | 1 | 12 | 9 | 1 |
| **104** | Earth bank | 71 | 35 | 393 | 377 | 105 |
| **107** | Erosion gully | · | · | · | · | · |
| **513** | Wall | 16 | 8 | 136 | 17 | 10 |
| **516** | Fence | · | · | · | · | · |
| **519** | Crossing point | · | · | 2 | · | · |
| **Σ** | Celkem objektů | 13826 | 8371 | 28610 | 23801 | 4110 |

Z 52 sledovaných ISOM symbolů reálně používáme **47** (zbytek = · znamená, že vrstva v dané lokalitě nemá žádný prvek; — znamená, že lokalita ještě nebyla regenerována). Legenda: · = 0 prvků, — = chybí výstup.

## Poslední aktualizace

- **SV** (`Soví vrch/`): 2026-06-10 13:45:15
- **NL** (`Nová Louka/`): 2026-06-10 13:45:33
- **LS** (`Lidové sady/`): 2026-06-10 13:47:13
- **HS** (`Hrubá Skála/`): 2026-06-10 13:47:36
- **NV** (`Novina/`): 2026-06-10 13:48:22

---
*Tabulka regenerována `stats.py` v 2026-06-10 13:48:23.*
