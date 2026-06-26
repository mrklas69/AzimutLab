#!/usr/bin/env python3
"""Unit testy omap_export — obrázkové podklady (apply_image_template_layout).

Re-order + opacita podkladů jsou string-level operace nad `.omap` (OOM drží definice v <map> a view
ref odděleně); regrese v index-přemapování tiše rozhodí, který podklad je který. Pokrývá pořadí
(z-order), přemapování view indexů, přepis opacity dle jména, idempotenci a edge-cases.

Spouštět z kořene:  python tests/test_omap_export.py   (bez pytest závislosti, KISS)
"""
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "generator"))

from omap_export import apply_image_template_layout, image_template_names  # noqa: E402

LAYOUT = [("bg_dmr.png", 1.0), ("bg_ortho.png", 0.5), ("bg_scan.png", 0.25)]


def _tpl(name: str) -> str:
    """Minimální TemplateImage element (jen co apply_image_template_layout potřebuje: name + obal)."""
    return (f'<template type="TemplateImage" open="true" name="{name}" path="{name}" relpath="{name}">'
            f'<transformations adjustment_dirty="true" passpoints="0">'
            f'<transformation role="active" x="0" y="0" scale_x="1" scale_y="1" rotation="0"/>'
            f'</transformations></template>')


def _doc(defs: list[str], refs: list[tuple[int, float]]) -> str:
    """Sestaví minimální .omap: <map> def blok (s first_front_template) + <view> ref blok."""
    n = len(defs)
    def_xml = "".join(_tpl(name) for name in defs)
    ref_xml = "".join(f'<ref template="{i}" visible="true" opacity="{op:g}"/>' for i, op in refs)
    return (f'<map version="9">'
            f'<templates count="{n}" first_front_template="{n}">{def_xml}'
            f'<defaults use_meters_per_pixel="true" meters_per_pixel="0" dpi="0" scale="0"/></templates>'
            f'<view><map_view zoom="1"><map opacity="1" visible="true"/>'
            f'<templates count="{n}">{ref_xml}</templates></map_view></view></map>')


def _view_opacity_by_index(doc: str) -> dict[int, float]:
    return {int(i): float(op)
            for i, op in re.findall(r'<ref template="(\d+)"[^>]*opacity="([^"]+)"', doc)}


class TestApplyLayout(unittest.TestCase):
    def test_reorder_and_opacity(self):
        # gen pořadí [ortho, dmr, scan] s defaultními opacitami → cílový z-order [dmr, ortho, scan]
        doc = _doc(["bg_ortho.png", "bg_dmr.png", "bg_scan.png"],
                   [(0, 0.5), (1, 0.6), (2, 0.6)])
        out = apply_image_template_layout(doc, LAYOUT)
        # definice přeskládána do BG_LAYOUT pořadí
        self.assertEqual(image_template_names(out), ["bg_dmr.png", "bg_ortho.png", "bg_scan.png"])
        # view ref indexy přemapované + opacita přepsaná dle jména (index 0=dmr, 1=ortho, 2=scan)
        op = _view_opacity_by_index(out)
        self.assertEqual(op, {0: 1.0, 1: 0.5, 2: 0.25})

    def test_idempotent(self):
        doc = _doc(["bg_ortho.png", "bg_dmr.png", "bg_scan.png"], [(0, 0.5), (1, 0.6), (2, 0.6)])
        once = apply_image_template_layout(doc, LAYOUT)
        twice = apply_image_template_layout(once, LAYOUT)
        self.assertEqual(once, twice)

    def test_already_ordered_only_opacity(self):
        # pořadí už sedí (dmr, ortho, scan), jen opacita je „cizí" → re-order no-op, opacita se sjednotí
        doc = _doc(["bg_dmr.png", "bg_ortho.png", "bg_scan.png"], [(0, 0.6), (1, 0.6), (2, 0.6)])
        out = apply_image_template_layout(doc, LAYOUT)
        self.assertEqual(image_template_names(out), ["bg_dmr.png", "bg_ortho.png", "bg_scan.png"])
        self.assertEqual(_view_opacity_by_index(out), {0: 1.0, 1: 0.5, 2: 0.25})

    def test_unknown_template_kept_last(self):
        # podklad mimo BG_LAYOUT (např. bg_mobile) se nezahodí a jde za seřazené; jeho opacita zůstává
        doc = _doc(["bg_scan.png", "bg_mobile.png", "bg_dmr.png"],
                   [(0, 0.6), (1, 0.42), (2, 0.6)])
        out = apply_image_template_layout(doc, LAYOUT)
        self.assertEqual(image_template_names(out), ["bg_dmr.png", "bg_scan.png", "bg_mobile.png"])
        op = _view_opacity_by_index(out)
        self.assertEqual(op[0], 1.0)    # bg_dmr
        self.assertEqual(op[1], 0.25)   # bg_scan
        self.assertEqual(op[2], 0.42)   # bg_mobile si nechá svou opacitu (mimo layout)

    def test_no_templates_is_noop(self):
        doc = ('<map version="9"><templates count="0" first_front_template="0"></templates>'
               '<view><map_view><templates count="0"></templates></map_view></view></map>')
        self.assertEqual(apply_image_template_layout(doc, LAYOUT), doc)

    def test_preserves_template_geometry(self):
        # re-order přesouvá celé <template> bloky → path/relpath/scale konkrétního podkladu zůstávají
        doc = _doc(["bg_ortho.png", "bg_dmr.png"], [(0, 0.5), (1, 0.6)])
        out = apply_image_template_layout(doc, LAYOUT)
        # bg_dmr element je netknutý (jen přesunutý), pořád obsahuje svůj path
        self.assertIn('name="bg_dmr.png" path="bg_dmr.png" relpath="bg_dmr.png"', out)
        self.assertEqual(image_template_names(out), ["bg_dmr.png", "bg_ortho.png"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
