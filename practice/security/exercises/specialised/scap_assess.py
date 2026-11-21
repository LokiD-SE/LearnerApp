"""EXERCISE - run the probes through the guarded HTTP wrapper, then turn what was found into scored findings.

``run_assessment`` gives every probe one of five verdicts. A probe that returns evidence (a non-empty string) is
``found``; one that returns ``None`` is ``not-found`` - but ONLY because its positive control worked. If anything
else happened the answer is NOT "not vulnerable":

- ``ControlFailed``        -> ``inconclusive`` (the control failed, so the probe proved nothing); evidence = the message;
- a ``requests`` exception -> ``inconclusive``, evidence ``"transport error: <ExceptionType>"``; any other exception
                              -> ``inconclusive``, evidence ``"probe crashed: <ExceptionType>: <message>"``;
- ``OutOfScope``           -> ``blocked`` (evidence starts ``"refused by the rules of engagement: "``); the run goes on;
- ``BudgetExhausted``      -> ``not-run`` for this probe AND every probe after it, 0 requests each; the run stops.

``Result.requests`` is how many requests the probe sent: ``http.used`` after minus before. Probes share ONE
``Context(http)`` so each user logs in once.

``to_findings`` turns the ``found`` results into the report's findings (see its docstring).
"""

from __future__ import annotations

import requests  # noqa: F401
from scap_fixture import (  # noqa: F401
    Assessment,
    BudgetExhausted,
    Context,
    ControlFailed,
    OutOfScope,
    Result,
    rating,
)
from wstg_fixture import FLAW_MAP  # noqa: F401


def run_assessment(http, probes: dict) -> Assessment:
    """Run ``probes`` (flaw id -> probe function taking a Context) in order; return an ``Assessment`` of one
    ``Result`` per probe, in the same order. TODO."""
    raise NotImplementedError("run_assessment")


def to_findings(assessment: Assessment, catalogue: dict, score_of) -> list[dict]:
    """One finding dict per ``found`` result, worst first. Keys: ``id`` (``SP-CAP-01`` ..., numbered AFTER sorting),
    ``flaw``, ``title``, ``cwe``, ``vector``, ``score`` (``score_of(vector)``), ``rating`` (``rating(score)``),
    ``evidence``, and ``refs`` = ``{"wstg": [...], "asvs": [...]}`` from ``FLAW_MAP[flaw]`` (empty lists when the flaw
    has no entry). Sort by score descending, then flaw id. A found flaw missing from ``catalogue`` raises
    ``KeyError`` - an unreportable finding must be loud, not dropped. TODO."""
    raise NotImplementedError("to_findings")
