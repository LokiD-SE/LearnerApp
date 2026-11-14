"""Puts the code under test on the import path.

By default the tests import your work from ``exercises/``. With ``AI_TARGET=solutions`` they import the
reference solutions from ``solutions/`` instead (``python scripts/verify.py`` uses both). Both folders have
the same layout, so a test writes ``from ml_foundations.arrays import normalise`` and never names either.
``support/`` (the scripted fake LLM, toy embeddings) is on the path for both: ``from llm_fake import ScriptedLLM``.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
TARGET = os.environ.get("AI_TARGET", "exercises")
if TARGET not in ("exercises", "solutions"):
    raise SystemExit(f"AI_TARGET must be 'exercises' or 'solutions', not {TARGET!r}")
sys.path.insert(0, str(ROOT / TARGET))
sys.path.insert(1, str(ROOT / "support"))
