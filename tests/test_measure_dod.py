"""Testy KOMPAS data-gate stropu v `_provedeni` (Sez. 178, navazuje na nález Sez. 177)."""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "generator"))

from measure_dod import DATA_GATE_CEILING, _provedeni  # noqa: E402


class DataGateCeilingTest(unittest.TestCase):
    # `code` chodí z `run_table`/`run_kpi` jako `int` (crosswalk cíl, viz `_kompas_source(code: int)`),
    # NE jako str — testy proto volají `_provedeni` s int kódy, ať skutečně cvičí stejnou cestu jako
    # živý běh. (Sez. 178 postmortem: prvni verze testu volala str kody a nechytila by, ze DATA_GATE_CEILING
    # porovnavalo str klic proti int kodu — proslo, i kdyz zivy `--table` porad hlasil "chybí".)
    def test_ceiling_code_reports_strop_not_missing(self) -> None:
        self.assertIn("107", DATA_GATE_CEILING)
        self.assertEqual(_provedeni(107, 25, 0, 1000, 1000), "strop")

    def test_uncalibrated_gap_still_reports_missing(self) -> None:
        # 108 zůstává ZÁMĚRNĚ mimo registr — Sez. 177 zaznamenal jen počet (155/0), ne ověřenou
        # příčinu; dokud to nikdo neverifikuje, zůstává to akční "chybí", ne tichý "strop".
        self.assertNotIn("108", DATA_GATE_CEILING)
        self.assertEqual(_provedeni(108, 155, 0, 1000, 1000), "chybí")

    def test_ceiling_only_applies_when_orig_has_objects(self) -> None:
        self.assertEqual(_provedeni(107, 0, 0, 1000, 1000), "–")

    def test_existing_share_based_branches_unaffected(self) -> None:
        # regresní pojistka: původní větve `_provedeni` (mimo strop) zůstávají nedotčené.
        self.assertEqual(_provedeni(999, 10, 30, 100, 100), "přestřel")
        self.assertEqual(_provedeni(999, 30, 10, 100, 100), "podstřel")
        self.assertEqual(_provedeni(999, 20, 20, 100, 100), "ok")
        self.assertEqual(_provedeni(999, 0, 5, 100, 100), "jen gen")

    def test_ceiling_entries_have_nonempty_reason(self) -> None:
        expected_codes = {"107", "201", "202", "205", "208", "308"}
        self.assertEqual(set(DATA_GATE_CEILING), expected_codes)
        for code, reason in DATA_GATE_CEILING.items():
            self.assertTrue(reason.strip(), f"{code} nema zduvodneni")

    def test_all_ceiling_codes_survive_int_roundtrip(self) -> None:
        # Kazdy klic musi byt dohledatelny pres str(int(code)) — chyta pripadnou desetinnou
        # variantu (napr. budouci "204.5"), kde by `int()` zbytecne selhal/oriznul.
        for code in DATA_GATE_CEILING:
            self.assertEqual(str(int(code)), code, f"{code} neni cely int kod jako zbytek registru")


if __name__ == "__main__":
    unittest.main()
