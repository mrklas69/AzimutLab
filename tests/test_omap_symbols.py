import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "generator"))

from omap_symbols import parse_symbol_ids  # noqa: E402


class OmapSymbolsTest(unittest.TestCase):
    def test_symbol_id_parser_ignores_attribute_order(self) -> None:
        doc = (
            '<symbols>'
            '<symbol code="301" name="Water" id="9"/>'
            '<symbol id="10" type="4" code="301.1"/>'
            '</symbols>'
        )
        self.assertEqual(parse_symbol_ids(doc, {"301", "301.1"}), {"301": 9, "301.1": 10})

    def test_required_symbols_fail_loudly(self) -> None:
        with self.assertRaisesRegex(ValueError, "chybí symboly"):
            parse_symbol_ids('<symbol id="1" code="301"/>', {"301", "301.4"}, source="mini.omap")

    def test_non_numeric_id_fails_loudly(self) -> None:
        with self.assertRaisesRegex(ValueError, "nečíselné id"):
            parse_symbol_ids('<symbol id="abc" code="301"/>', source="mini.omap")


if __name__ == "__main__":
    unittest.main()
