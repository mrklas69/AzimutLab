"""
palette.py — barevná paleta generátoru OB map (JEDINÝ ZDROJ PRAVDY, DRY).

Aproximace ISOM 2017-2 pro obrazovku. Toto je jediné místo v celém projektu,
kde žijí konkrétní RGB hodnoty mapové palety:
  - generator.py importuje konstanty C_* odsud (nemá vlastní kopii),
  - dokumentace (spec `docs/kb/generator-procedural.md` §5 a KB
    `docs/kb/isom-issprom.md`) na tento soubor ODKAZUJE, nekopíruje hodnoty.

Díky tomu se palety na více místech nemůžou tiše rozejít (princip DRY /
jediný zdroj pravdy z CLAUDE.md). Změna odstínu = změna jen zde.
"""

from typing import NamedTuple

# Typový alias: RGB barva je trojice celých čísel 0-255 (red, green, blue).
# Alias dává jménu význam — `RGB` čtenáři řekne víc než holé `tuple[int, int, int]`.
RGB = tuple[int, int, int]


class Swatch(NamedTuple):
    """Jeden odstín palety: RGB hodnota + lidský význam (pro legendu/dokumentaci).

    NamedTuple = neměnná pojmenovaná n-tice. Chová se jako tuple (lze rozbalit,
    je hashable a lehká), ale k položkám se přistupuje jménem: `s.rgb`, `s.meaning`.
    Volíme ji místo dataclass, protože swatch je malá neměnná hodnota — přesně to,
    pro co je NamedTuple idiomatická.
    """
    rgb: RGB
    meaning: str


# ---------- Kanonická paleta ----------
# Klíč = slug (strojový identifikátor odstínu), hodnota = Swatch(rgb, význam).
# Pořadí drží spec §5 (bílá → žlutá → zeleně → hnědá → modrá → černá → purpur),
# ať je tabulka v dokumentu a tento dict izomorfní (snadné porovnání očima).
PALETTE: dict[str, Swatch] = {
    "white":  Swatch((255, 255, 255), "průběžný les / podklad"),
    "yellow": Swatch((254, 202, 23),  "otevřená plocha (paseka)"),
    "green1": Swatch((194, 232, 176), "světle zelená — pomalý běh"),
    "green2": Swatch((109, 199, 113), "středně zelená — chůze"),
    "green3": Swatch((45, 169, 79),   "tmavě zelená — těžko prostupné"),
    "brown":  Swatch((160, 95, 31),   "vrstevnice, rýhy"),
    "road":   Swatch((232, 167, 116), "silnice 502 — výplň (ISOM Upper brown 50%)"),
    "blue":   Swatch((46, 194, 248),  "voda, mokřad"),
    "black":  Swatch((0, 0, 0),       "skály, cesty, stavby"),
    "purple": Swatch((196, 0, 172),   "trať (purpurová) — §4.13, zatím neimplementováno"),
}

# ---------- Pohodlné pojmenované konstanty ----------
# Odvozené z PALETTE (žádná druhá kopie hodnot!) — umožní v generator.py psát
# `C_YELLOW` místo `PALETTE["yellow"].rgb`. Všech 10 pro izomorfismus: i barvy,
# které generátor zatím nekreslí (purpurová trať), tu jsou připravené.
C_WHITE  = PALETTE["white"].rgb
C_YELLOW = PALETTE["yellow"].rgb
C_GREEN1 = PALETTE["green1"].rgb
C_GREEN2 = PALETTE["green2"].rgb
C_GREEN3 = PALETTE["green3"].rgb
C_BROWN  = PALETTE["brown"].rgb
C_ROAD   = PALETTE["road"].rgb
C_BLUE   = PALETTE["blue"].rgb
C_BLACK  = PALETTE["black"].rgb
C_PURPLE = PALETTE["purple"].rgb
