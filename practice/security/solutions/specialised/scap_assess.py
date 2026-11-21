"""SOLUTION - run the probes through the guarded HTTP wrapper, then turn what was found into scored findings.

``run_assessment`` gives every probe one of five verdicts, and the difference between them is the point of the
exercise. A probe that returns evidence is ``found``; one that returns ``None`` is ``not-found`` - but ONLY a probe
whose positive control worked can say that. If anything else happened the answer is not "not vulnerable":

- ``ControlFailed``         -> ``inconclusive`` (the control did not work, so the probe proved nothing);
- ``requests`` exception    -> ``inconclusive`` (transport error); any other exception -> ``inconclusive`` too,
                               "probe crashed" (a crashed probe must never count as a pass);
- ``OutOfScope``            -> ``blocked`` (the probe tried something the rules refuse; the run continues);
- ``BudgetExhausted``       -> ``not-run`` for this probe AND every probe after it; the run stops.
"""

from __future__ import annotations

import requests
from scap_fixture import (
    Assessment,
    BudgetExhausted,
    Context,
    ControlFailed,
    OutOfScope,
    Result,
    rating,
)
from wstg_fixture import FLAW_MAP


def run_assessment(http, probes: dict) -> Assessment:
    """Run ``probes`` (flaw id -> probe) in order, sharing one ``Context(http)``; return an ``Assessment``.

    ``Result.requests`` is how many requests the probe sent (``http.used`` before and after).
    """
    ctx = Context(http)
    results: list[Result] = []
    names = list(probes)
    for index, flaw in enumerate(names):
        before = http.used
        try:
            evidence = probes[flaw](ctx)
            status, text = ("found", evidence) if evidence else ("not-found", "the probe's control worked and the flaw was not seen")
        except ControlFailed as exc:
            status, text = "inconclusive", str(exc)
        except BudgetExhausted:
            for left in names[index:]:
                results.append(Result(left, "not-run", "request budget exhausted before this probe ran", 0))
            return Assessment(tuple(results))
        except OutOfScope as exc:
            status, text = "blocked", f"refused by the rules of engagement: {exc}"
        except requests.RequestException as exc:
            status, text = "inconclusive", f"transport error: {type(exc).__name__}"
        except Exception as exc:  # noqa: BLE001 - a crashed probe proved nothing
            status, text = "inconclusive", f"probe crashed: {type(exc).__name__}: {exc}"
        results.append(Result(flaw, status, text, http.used - before))
    return Assessment(tuple(results))


def to_findings(assessment: Assessment, catalogue: dict, score_of) -> list[dict]:
    """One finding per ``found`` result, worst first.

    Each finding is a dict with: ``id`` (``SP-CAP-01``, numbered after sorting), ``flaw``, ``title`` and ``cwe`` from
    ``catalogue[flaw]``, ``vector`` and ``score`` (``score_of(vector)``), ``rating`` (``scap_fixture.rating``),
    ``evidence`` (the result's text), and ``refs`` - ``{"wstg": [...], "asvs": [...]}`` copied from
    ``wstg_fixture.FLAW_MAP[flaw]`` (empty lists when the flaw has no entry).
    Sort by score descending, then flaw id. Raise ``KeyError`` for a found flaw with no catalogue entry: an
    unreportable finding must be loud, not dropped.
    """
    rows = []
    for r in assessment.results:
        if r.status != "found":
            continue
        entry = catalogue[r.flaw]
        score = score_of(entry["vector"])
        refs = FLAW_MAP.get(r.flaw, {})
        rows.append({
            "flaw": r.flaw, "title": entry["title"], "cwe": entry["cwe"], "vector": entry["vector"],
            "score": score, "rating": rating(score), "evidence": r.evidence,
            "refs": {"wstg": list(refs.get("wstg", [])), "asvs": list(refs.get("asvs", []))},
        })
    rows.sort(key=lambda f: (-f["score"], f["flaw"]))
    for number, row in enumerate(rows, start=1):
        row["id"] = f"SP-CAP-{number:02d}"
    return rows
