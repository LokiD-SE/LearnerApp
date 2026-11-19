"""Turn ASVS requirements and WSTG tests into a test plan for one target level (exercise).

Write every function that raises NotImplementedError; the docstrings say what each must do. Run the
tests with: .venv/bin/python -m pytest tests/foundations/test_wstg_plan.py

ASVS 5.0.0, "How to Reference ASVS Requirements": each requirement has an identifier
``<chapter>.<section>.<requirement>`` (for example ``1.2.5``), and because identifiers may change between
versions, "it is preferable for other documents, reports, or tools to use the following format:
``v<version>-<chapter>.<section>.<requirement>``" - for example ``v5.0.0-1.2.5``. "The ``v`` preceding the version
number in the format should always be lowercase." The release CSV writes ids with a capital V and no version
(``V1.2.5``), so a plan converts them.

Levels (ASVS 5.0.0, "Application Security Verification Levels"): an application that complies with L2 implements
"all of the L1 and L2 requirements"; the CSV's ``L`` column says the level at which a requirement starts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REQ_ID = re.compile(r"^V?(\d+)\.(\d+)\.(\d+)$")
REF = re.compile(r"^v(\d+\.\d+\.\d+)-(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class PlanItem:
    flaw: str
    wstg: tuple[str, ...]  # WSTG tests to run; empty = the guide has no test for it (a gap to cover yourself)
    asvs: tuple[str, ...]  # versioned refs (v5.0.0-8.2.2) of the requirements in scope at the target level
    deferred: tuple[str, ...]  # versioned refs of the requirements above the target level

    @property
    def wstg_gap(self) -> bool:
        return not self.wstg


def asvs_ref(req_id: str, version: str = "5.0.0") -> str:
    """``V8.2.2`` or ``8.2.2`` -> ``v5.0.0-8.2.2``. Raises ``ValueError`` for anything else."""
    raise NotImplementedError("TODO: write asvs_ref")


def parse_asvs_ref(ref: str) -> tuple[str, int, int, int]:
    """``v5.0.0-1.2.5`` -> ``("5.0.0", 1, 2, 5)``. A capital ``V`` or a missing version is an error."""
    raise NotImplementedError("TODO: write parse_asvs_ref")


def for_level(requirements: list[dict], level: int) -> list[dict]:
    """The requirements an application at ``level`` (1, 2 or 3) must meet: every row whose ``L`` is at most
    ``level``. Raises ``ValueError`` for another level."""
    raise NotImplementedError("TODO: write for_level")


def build_plan(flaws: list[str], mapping: dict[str, dict], requirements: list[dict], level: int,
               version: str = "5.0.0") -> list[PlanItem]:
    """One plan item per flaw, in the order given.

    ``mapping[flaw]`` is ``{"wstg": [...], "asvs": ["V8.2.2", ...]}``. Each ASVS id is looked up in
    ``requirements`` (rows with ``req_id`` and ``L``): those in scope at ``level`` go to ``asvs``, the rest to
    ``deferred``, both as versioned references in the mapping's order. A flaw missing from the mapping, or an
    ASVS id missing from ``requirements``, raises ``KeyError`` - a plan must not silently drop a risk.
    """
    raise NotImplementedError("TODO: write build_plan")
