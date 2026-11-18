"""Puts the code under test on the import path.

By default the tests import your work from ``exercises/``. With ``SEC_TARGET=solutions`` they import the
reference solutions from ``solutions/`` instead (``python scripts/verify.py`` uses both). Both folders have
the same layout, so a test writes ``from <topic>.<module> import ...`` and never names either.
``support/`` (shared practice targets) is on the path for both.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
TARGET = os.environ.get("SEC_TARGET", "exercises")
if TARGET not in ("exercises", "solutions"):
    raise SystemExit(f"SEC_TARGET must be 'exercises' or 'solutions', not {TARGET!r}")
sys.path.insert(0, str(ROOT / TARGET))
sys.path.insert(1, str(ROOT / "support"))
