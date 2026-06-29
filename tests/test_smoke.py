import os
import pathlib
import sys
import unittest

if os.environ.get("AZIMUT_RUN_SMOKE") != "1":
    raise unittest.SkipTest("Live generator smoke se spouští explicitně přes AZIMUT_RUN_SMOKE=1")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from smoke import GeneratorSmokeTest  # noqa: F401,E402
