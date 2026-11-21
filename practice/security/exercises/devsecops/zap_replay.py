"""Read a ZAP-style JSON report and re-check each instance against the local portal (DAST lesson).

Exercise - fill in the TODOs; ``tests/devsecops/test_zap_replay.py`` checks your work.

ZAP's "Traditional JSON Report" has ``site[].alerts[]``, and each alert has ``instances[]`` with ``uri``,
``method``, ``param``, ``attack`` and ``evidence``. The alert carries ``pluginid``, ``alertRef`` (the rule id,
optionally followed by a dash and the alert type), ``name``, ``riskcode`` and ``confidence``. A scanner's alert is a
CLAIM; ``replay`` checks one instance:

- ``flatten(report)``: one ``Finding`` per instance. ``rule_id`` is ``alertRef`` (fall back to ``pluginid``).
  ``risk`` is ``RISKS[int(riskcode)]`` and ``confidence`` is ``CONFIDENCES[int(confidence)]``: the documentation
  lists the risks Informational, Low, Medium, High and the confidences False Positive, Low, Medium, High,
  Confirmed in that order, and its sample report shows ``riskcode "3"`` as High and ``confidence "2"`` as Medium.
  ``method`` defaults to ``GET``; ``param``, ``attack`` and ``evidence`` to ``""``.
- ``replay(finding)``: ``"reproduced"`` / ``"not-reproduced"`` / ``"not-replayable"``. Refuse a URL whose host is
  not loopback with ``ValueError`` BEFORE anything else (scope). Passive alerts (no attack or no evidence) and
  non-GET instances (the JSON report does not hold a request body) are ``"not-replayable"``. Otherwise ``GET`` the
  instance's ``uri`` as recorded (no redirects): ``"reproduced"`` only when the status is 200 AND the evidence
  string is in the body; anything else is ``"not-reproduced"``.
- ``replay_report`` replays every finding of a report; ``summarise`` counts the three outcomes (all three keys
  always present).

A replay that reproduces is evidence the claim is true NOW, against THIS build. One that does not reproduce is not
proof of a false positive: say "not reproduced" and look at the instance before you close it.
"""

from __future__ import annotations

import urllib.parse

import requests
from zap_fixture import CONFIDENCES, RISKS, Finding

REPRODUCED = "reproduced"
NOT_REPRODUCED = "not-reproduced"
NOT_REPLAYABLE = "not-replayable"
LOOPBACK = ("127.0.0.1", "localhost", "::1")


def flatten(report: dict) -> list[Finding]:
    """One ``Finding`` per alert instance, in report order.

    TODO: loop ``report["site"]`` then ``["alerts"]`` then ``["instances"]`` (use ``.get(..., [])``) and build a
    ``Finding`` from the alert's and the instance's fields as the module docstring says.
    """
    raise NotImplementedError("flatten")


def replay(finding: Finding, timeout: float = 5) -> str:
    """Re-send one instance and report whether its evidence comes back.

    TODO: loopback check first (``ValueError``), then the not-replayable cases, then one ``requests.get``.
    """
    raise NotImplementedError("replay")


def replay_report(report: dict, timeout: float = 5) -> list[tuple[Finding, str]]:
    """``(finding, outcome)`` for every instance of the report.

    TODO: ``flatten`` then ``replay`` each one.
    """
    raise NotImplementedError("replay_report")


def summarise(results: list[tuple[Finding, str]]) -> dict[str, int]:
    """``{"reproduced": n, "not-reproduced": n, "not-replayable": n}`` for ``replay_report`` results.

    TODO: start from all three keys at 0 and count.
    """
    raise NotImplementedError("summarise")
