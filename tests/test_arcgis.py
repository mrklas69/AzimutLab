import json
import pathlib
import sys
import tempfile
import unittest
import urllib.parse
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "connectors"))

import arcgis  # noqa: E402


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload
        self.headers = {"Content-Type": "application/json; charset=utf-8"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class ArcgisPagingTest(unittest.TestCase):
    def test_short_batch_with_exceeded_transfer_limit_continues(self) -> None:
        responses = [
            {"type": "FeatureCollection", "features": [{"id": 1}], "exceededTransferLimit": True},
            {"type": "FeatureCollection", "features": [{"id": 2}], "exceededTransferLimit": False},
        ]
        offsets: list[int] = []

        def fake_urlopen(req, **kwargs):
            parsed = urllib.parse.urlparse(req.full_url)
            params = urllib.parse.parse_qs(parsed.query)
            offsets.append(int(params["resultOffset"][0]))
            return _Response(responses.pop(0))

        with tempfile.TemporaryDirectory() as tmp:
            with patch("arcgis.ssl_context", return_value=None), patch("arcgis.urllib.request.urlopen", fake_urlopen):
                result = arcgis.fetch_geojson_layer(
                    "https://example.test/arcgis/rest/services/x/MapServer",
                    1,
                    (0, 0, 10, 10),
                    pathlib.Path(tmp),
                    page_size=2,
                )

        self.assertEqual([feature["id"] for feature in result["features"]], [1, 2])
        self.assertEqual(offsets, [0, 1])

    def test_exceeded_without_features_fails_loudly(self) -> None:
        def fake_urlopen(req, **kwargs):
            return _Response({"type": "FeatureCollection", "features": [], "exceededTransferLimit": True})

        with tempfile.TemporaryDirectory() as tmp:
            with patch("arcgis.ssl_context", return_value=None), patch("arcgis.urllib.request.urlopen", fake_urlopen):
                with self.assertRaisesRegex(RuntimeError, "bez features"):
                    arcgis.fetch_geojson_layer(
                        "https://example.test/arcgis/rest/services/x/MapServer",
                        1,
                        (0, 0, 10, 10),
                        pathlib.Path(tmp),
                    )


if __name__ == "__main__":
    unittest.main()
