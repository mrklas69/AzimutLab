import pathlib
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "connectors"))

import ssl_ctx  # noqa: E402


class SslContextTest(unittest.TestCase):
    def tearDown(self) -> None:
        ssl_ctx._CTX = None

    def test_certifi_bundle_is_used_directly(self) -> None:
        sentinel = object()
        fake_certifi = types.SimpleNamespace(where=lambda: "bundle.pem")
        ssl_ctx._CTX = None
        with patch.dict(sys.modules, {"certifi": fake_certifi}):
            with patch("ssl_ctx.ssl.create_default_context", return_value=sentinel) as create:
                self.assertIs(ssl_ctx.ssl_context(), sentinel)
                self.assertIs(ssl_ctx.ssl_context(), sentinel)

        create.assert_called_once_with(cafile="bundle.pem")


if __name__ == "__main__":
    unittest.main()
