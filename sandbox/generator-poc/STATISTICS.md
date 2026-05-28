# STATISTICS — testovací mapy AzimutLab

Počty objektů per ISOM symbol napříč 5 DEV_LOCATIONS (`generator.py --location KÓD`).
Regeneruj skriptem `stats.py` po každém regen kanonika nebo po změně rendereru.

**Kanonické lokality** (různé formáty výseku pro test ořezu DMR/ZABAGED/ortofoto):

- **SV** — Soví vrch / Lužické hory  (`Soví Vrch/`)
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
| **204** | Boulder | 28 | 16 | 10 | 9 | 9 |
| **206** | Gigantic boulder | 79 | 6 | 20 | 459 | 13 |
| **207** | Boulder cluster | 146 | 178 | 132 | 171 | 9 |
| **301** | Uncrossable body of water | 14 | 11 | 58 | 41 | 12 |
| **304** | Crossable watercourse | 52 | 76 | 80 | 25 | 32 |
| **305** | Small crossable watercourse | 107 | 118 | 146 | 90 | 84 |
| **306** | Seasonal watercourse | 43 | 82 | 6 | 16 | 2 |
| **501** | Paved area | · | · | 1 | · | · |
| **502** | Wide road | 207 | 15 | 3154 | 169 | 24 |
| **503** | Road | 194 | 181 | 300 | 321 | 174 |
| **504** | Vehicle track | 464 | 98 | 230 | 392 | 251 |
| **505** | Footpath | · | 9 | 85 | 2 | 1 |
| **506** | Small footpath | 39 | 61 | 182 | 145 | 36 |
| **509** | Railway | · | · | 40 | 3 | 1 |
| **510** | Power line | 32 | 3 | 19 | 41 | 10 |
| **521** | Building | 1078 | 124 | 8273 | 1265 | 299 |
| **512** | Bridge/tunnel | 17 | 13 | 67 | 11 | 21 |
| **512.2** | Footbridge | 7 | 5 | 11 | 2 | 5 |
| **Σ** | Celkem objektů | 3273 | 1406 | 13636 | 4368 | 1388 |

Z 24 sledovaných ISOM symbolů reálně používáme **24** (zbytek = · znamená, že vrstva v dané lokalitě nemá žádný prvek; — znamená, že lokalita ještě nebyla regenerována). Legenda: · = 0 prvků, — = chybí výstup.

## Poslední aktualizace

- **SV** (`Soví Vrch/`): 2026-05-28 15:05:22
- **NL** (`Nová Louka/`): 2026-05-28 15:05:32
- **LS** (`Lidové sady/`): 2026-05-28 15:05:42
- **HS** (`Hrubá Skála/`): 2026-05-28 15:05:53
- **NV** (`Novina/`): 2026-05-28 15:03:46

---
*Tabulka regenerována `stats.py` v 2026-05-28 15:06:02.*
