"""SOLUTION - Read a ZAP-style JSON report and re-check each instance against the local portal."""

from __future__ import annotations

import urllib.parse

import requests
from zap_fixture import CONFIDENCES, RISKS, Finding

REPRODUCED = "reproduced"
NOT_REPRODUCED = "not-reproduced"
NOT_REPLAYABLE = "not-replayable"
LOOPBACK = ("127.0.0.1", "localhost", "::1")


def flatten(report: dict) -> list[Finding]:
    findings: list[Finding] = []
    for site in report.get("site", []):
        for alert in site.get("alerts", []):
            rule_id = alert.get("alertRef") or alert["pluginid"]
            risk = RISKS[int(alert["riskcode"])]
            confidence = CONFIDENCES[int(alert["confidence"])]
            for inst in alert.get("instances", []):
                findings.append(
                    Finding(
                        rule_id, alert["name"], risk, inst["uri"], inst.get("method", "GET"),
                        inst.get("param", ""), inst.get("attack", ""), inst.get("evidence", ""), confidence,
                    )
                )
    return findings


def replay(finding: Finding, timeout: float = 5) -> str:
    if urllib.parse.urlsplit(finding.uri).hostname not in LOOPBACK:
        raise ValueError(f"refusing to replay against {finding.uri}: loopback only")
    if not finding.attack or not finding.evidence or finding.method != "GET":
        return NOT_REPLAYABLE
    resp = requests.get(finding.uri, timeout=timeout, allow_redirects=False)
    if resp.status_code == 200 and finding.evidence in resp.text:
        return REPRODUCED
    return NOT_REPRODUCED


def replay_report(report: dict, timeout: float = 5) -> list[tuple[Finding, str]]:
    return [(f, replay(f, timeout)) for f in flatten(report)]


def summarise(results: list[tuple[Finding, str]]) -> dict[str, int]:
    counts = {REPRODUCED: 0, NOT_REPRODUCED: 0, NOT_REPLAYABLE: 0}
    for _, outcome in results:
        counts[outcome] += 1
    return counts
