"""
curate.py — kurace Livelox korpusu pro UC5 trénink (taxonomie + manifest, Sez. 71).

GT je strop supervised modelu → korpus 268 reálných map má SMÍŠENOU vhodnost pro lesní
runnability. Tenhle modul každou mapu OTAGUJE (disciplína + kvalitní vlajky) a spočítá
`keep` flag; trénink pak konzumuje jen vhodné mapy. Nedestruktivní — nic nemaže, jen
zapíše manifest `resources/livelox/_curation.json`.

Taxonomie:
  discipline (1 hodnota): classic (foot-O les ISOM, jádro tréninku) / sprint (ISSprOM městské,
    jiná sémantika label 0) / mtbo (cyklo ISMTBOM, jiná symbolika) / overview (>=20000, hrubé).
  quality tagy (víc):
    AUTO (z jména/GT/epsg): variant_contour (vrstevnicovka), variant_black (black-only),
      base_layer (odstrojený podklad), basemap (ne-OB OSM/topo podklad), training (trénink/kontroly),
      foreign_crs (epsg mimo region).
    VIZUÁL (2. průchod, ruční): legend (legenda/popisky/control-description v ploše), logo (sponzor),
      damage (foto vytištěné mapy / sken / poškození → špinavé GT). damage je disqualifying.

keep = (keep_override když je) JINAK (discipline == classic AND žádný disqualify tag).
  disqualify = {variant_contour, variant_black, base_layer} — degenerovaná runnability GT.
  sprint/mtbo/overview NEjsou disqualify TAG, ale ne-classic disciplína → keep=false (oddělené,
  ne smazané — sprint/mtbo korpus zůstává pro případný budoucí model).

Merge (re-run): auto pole se PŘEPÍŠOU z aktuálních dat/pravidel; ruční (vizuál tagy + keep_override
  + reviewed) se ZACHOVAJÍ. Tím re-run po rozšíření korpusu / změně pravidel nezahodí ruční práci.

Spouštět z kořene repa (sys.path skript, fáze B — ne balík).
"""
import json
import os
import re
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
_REPO_ROOT = Path(__file__).resolve().parents[1]
_CORPUS_DIR = _REPO_ROOT / "resources" / "livelox"
_MANIFEST = _CORPUS_DIR / "_curation.json"

# --- jmenné klíče pro auto-disciplínu a auto-tagy (re.I; ascii i diakritika) ---
_RE_MTBO = re.compile(r"mtbo|cyklo|\bbike\b|\bmtb\b", re.I)
_RE_SPRINT = re.compile(r"sprint|issprom", re.I)
_RE_CONTOUR = re.compile(r"vrstevnic", re.I)            # vrstevnicovka / vrstevnice_mapa
_RE_BLACK = re.compile(r"black|_bw\b|\bbw\b|[čc]ern", re.I)
_RE_BASE = re.compile(r"podklad", re.I)                 # podklad / podkladovka
_RE_TRAIN = re.compile(r"tr[eé]nink|training|kontrol|control|cejch|cvi[čc]n", re.I)
# ne-OB podkladová mapa (OSM/Google/satelit/topo) — vizuál Sez. 71 chytil „OSM Bright" v keep.
# NENÍ to OB mapa → runnability GT z ní je nesmysl. Name-detectable (jméno nese zdroj podkladu).
_RE_BASEMAP = re.compile(r"\bosm\b|google|satelit|basemap|mapy\.cz|\bwms\b", re.I)

# CZ/region platné CRS: 5514/5513 S-JTSK, 32633 UTM33, 3045 ETRS89-UTM33, 4326 = náš WGS84 fallback.
VALID_EPSG = {5514, 5513, 32633, 3045, 4326}

# tagy, které VYŘAZUJÍ z tréninku (degenerovaná/nepoužitelná runnability GT)
DISQUALIFY_TAGS = {"variant_contour", "variant_black", "base_layer", "basemap", "damage"}
# Disqualify tag = jméno-hint (vrstevnicovka/black/podklad) AND ~bez vegetace. Sám název nestačí:
# „podkladovka" může být PLNÁ mapa (podklad pro stavbu tratí, 33 % zeleně — false-drop 1177415,
# Sez. 71 vizuál). Skutečný důkaz degenerace = nízká zeleň; práh empirický (varianty 0–5 %, plné >10 %).
VARIANT_GREEN_MAX = 8.0
# tagy přidávané jen VIZUÁLNÍM průchodem (ruční) — merge je zachovává přes re-run auto-tagů
VISUAL_TAGS = {"legend", "logo", "damage"}


def _green_pct(map_dir: Path) -> float:
    """Podíl zelených pixelů (label 1-3 = 406/408/410) v GT [%]. Indikátor lesní vegetace."""
    lab = np.asarray(Image.open(map_dir / "gt_labels.png"))
    return round(100 * float(((lab >= 1) & (lab <= 3)).sum()) / lab.size, 1)


def _auto_classify(name: str, scale, epsg, green: float) -> tuple[str, list[str]]:
    """Vrátí (discipline, auto_tags) z metadat + GT. Jen AUTO pole (vizuál tagy sem nepatří)."""
    # disciplína (1 hodnota; pořadí = priorita: mtbo > sprint > overview > classic)
    if _RE_MTBO.search(name):
        disc = "mtbo"
    elif _RE_SPRINT.search(name) or (scale and scale <= 5000):
        disc = "sprint"
    elif scale and scale >= 20000:
        disc = "overview"
    else:
        disc = "classic"

    tags: list[str] = []
    if _RE_BASEMAP.search(name):                    # ne-OB podklad (OSM/…) — bez green gate (může být zelený)
        tags.append("basemap")
    if green < VARIANT_GREEN_MAX:                   # degenerace = ~bez vegetace; jméno = jen hint
        if _RE_CONTOUR.search(name):
            tags.append("variant_contour")
        if _RE_BLACK.search(name):                  # „černá" jen když i skoro bez barev (ne course-name)
            tags.append("variant_black")
        if _RE_BASE.search(name):                   # „podklad" jen odstrojený (plná podkladovka = keep)
            tags.append("base_layer")
    if _RE_TRAIN.search(name):
        tags.append("training")
    if epsg not in VALID_EPSG:
        tags.append("foreign_crs")
    return disc, tags


def _compute_keep(discipline: str, tags: list[str], existing: dict) -> bool:
    """keep = keep_override (ruční) JINAK classic AND bez disqualify tagu."""
    if "keep_override" in existing:
        return bool(existing["keep_override"])
    return discipline == "classic" and not (set(tags) & DISQUALIFY_TAGS)


def build_curation(merge: bool = True) -> dict:
    """Projde korpus, auto-otaguje, (merge) zachová ruční pole → zapíše _curation.json. Vrací manifest.

    merge=True (default): načte existující manifest, AUTO pole přepíše z aktuálních dat/pravidel,
    ruční (vizuál tagy z VISUAL_TAGS + keep_override + reviewed) zachová. merge=False = od nuly.
    Mapy, které už v korpusu nejsou, z manifestu vypadnou (korpus = zdroj pravdy).
    """
    old = {}
    if merge and _MANIFEST.exists():
        old = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        old.pop("_meta", None)

    manifest: dict[str, dict] = {}
    for d in sorted(_CORPUS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        cid = d.name
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            green = _green_pct(d)
        except Exception:
            continue
        name = meta.get("name") or ""
        scale = meta.get("mapScale")
        epsg = meta.get("epsg")
        disc, auto_tags = _auto_classify(name, scale, epsg, green)

        prev = old.get(cid, {})
        # zachovej ruční vizuál tagy z předchozího manifestu (merge)
        visual = [t for t in prev.get("tags", []) if t in VISUAL_TAGS]
        tags = auto_tags + visual
        entry = {
            "name": name, "scale": scale, "epsg": epsg, "green_pct": green,
            "discipline": disc, "tags": tags,
            "reviewed": bool(prev.get("reviewed", False)),
        }
        if "keep_override" in prev:                 # ruční override disciplíny/tagů
            entry["keep_override"] = prev["keep_override"]
        entry["keep"] = _compute_keep(disc, tags, prev)
        manifest[cid] = entry

    kept = sum(1 for m in manifest.values() if m["keep"])
    out = {"_meta": {
        "generated": "connectors/curate.py (auto-tag + merge, Sez. 71)",
        "total": len(manifest), "kept": kept, "dropped": len(manifest) - kept,
        "taxonomy": {
            "discipline": ["classic", "sprint", "mtbo", "overview"],
            "auto_tags": ["variant_contour", "variant_black", "base_layer", "basemap",
                          "training", "foreign_crs"],
            "visual_tags": sorted(VISUAL_TAGS),
            "disqualify_tags": sorted(DISQUALIFY_TAGS),
            "keep": "keep_override JINAK (classic AND bez disqualify tagu)",
        },
    }}
    out.update(manifest)
    _MANIFEST.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_curation() -> dict:
    """Načte manifest (bez _meta). {} když neexistuje (kontrakt pro UC5 loader)."""
    if not _MANIFEST.exists():
        return {}
    data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    data.pop("_meta", None)
    return data


def kept_dirs(discipline: str = "classic") -> list[Path]:
    """Cesty k adresářům map s keep=true a danou disciplínou (default classic = tréninkové jádro).

    Kontrakt pro UC5 trénink: iteruj jen vhodné mapy. discipline=None = všechny keep bez ohledu
    na disciplínu (keep je u ne-classic stejně false, ale ponechán pro symetrii / budoucí override).
    """
    cur = load_curation()
    out = []
    for cid, m in cur.items():
        if not m.get("keep"):
            continue
        if discipline and m.get("discipline") != discipline:
            continue
        out.append(_CORPUS_DIR / cid)
    return out


if __name__ == "__main__":
    import sys
    from collections import Counter
    arg = sys.argv[1] if len(sys.argv) > 1 else "build"
    if arg == "build":
        m = build_curation(merge=True)
        kept = sum(1 for v in m.values() if v["keep"])
        print(f"manifest: {len(m)} map -> kept {kept} / dropped {len(m) - kept}")
        print("discipline:", dict(Counter(v["discipline"] for v in m.values())))
        print("tagy:", dict(Counter(t for v in m.values() for t in v["tags"])))
    elif arg == "list":
        # vypíše keep classic = tréninkové jádro (počet); bezpečně bez názvů (konzole cp1250)
        print(f"keep classic (tréninkové jádro): {len(kept_dirs('classic'))} map")
