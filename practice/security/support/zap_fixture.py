"""Shared types and hand-written ZAP-style data for the DAST lesson (``dast-with-owasp-zap``).

ZAP is NOT installed here and nothing in this project runs it. What this module holds:

- ``Finding``: one alert instance, the unit every exercise works with (the fields mirror ZAP's alert fields:
  rule, name, risk, confidence, URL, method, parameter, attack, evidence).
- ``RISKS`` / ``CONFIDENCES``: the orderings from ZAP's alert documentation.
- ``sample_report(base_url)``: a SYNTHETIC report written by hand in the shape of the sample in ZAP's
  "Traditional JSON Report" documentation (``site[].alerts[].instances[]``). It is not output of a ZAP run.
  The URLs point at the practice portal you pass in, so the replay exercise can check them.
- ``BASELINE_CONFIG``: a rule configuration file in the layout ZAP's baseline-scan documentation shows
  (``<rule id><TAB><WARN|IGNORE|FAIL>[<TAB><message>]``), with a comment line first.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass

RISKS = ("Informational", "Low", "Medium", "High")
CONFIDENCES = ("False Positive", "Low", "Medium", "High", "Confirmed")


@dataclass(frozen=True)
class Finding:
    rule_id: str
    name: str
    risk: str
    uri: str
    method: str = "GET"
    param: str = ""
    attack: str = ""
    evidence: str = ""
    confidence: str = "Medium"


XSS_ATTACK = "<script>alert(1)</script>"
TRAVERSAL_REAL = "../internal/settlement-keys.txt"
TRAVERSAL_STALE = "../../etc/passwd"


def _q(base: str, path: str, **params: str) -> str:
    return base + path + ("?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote) if params else "")


def sample_report(base_url: str) -> dict:
    """A synthetic ZAP-style traditional JSON report for the practice portal at ``base_url``.

    Four alerts: reflected XSS and path traversal (active, replayable GET instances), persistent XSS (a POST
    instance, which a replay cannot send because the JSON report holds no request body) and a missing CSP header
    (passive, no attack). The second path traversal instance is deliberately STALE: the portal does not serve
    ``/etc/passwd``, so a replay does not reproduce it.
    """
    return {
        "@version": "synthetic",
        "@generated": "Sat, 21 Nov 2026 10:00:00",
        "site": [
            {
                "@name": base_url,
                "@host": "127.0.0.1",
                "alerts": [
                    {
                        "pluginid": "40012",
                        "alertRef": "40012",
                        "name": "Cross Site Scripting (Reflected)",
                        "riskcode": "3",
                        "confidence": "2",
                        "riskdesc": "High (Medium)",
                        "instances": [
                            {
                                "uri": _q(base_url, "/search", q=XSS_ATTACK),
                                "method": "GET",
                                "param": "q",
                                "attack": XSS_ATTACK,
                                "evidence": XSS_ATTACK,
                            }
                        ],
                        "count": "1",
                        "cweid": "79",
                    },
                    {
                        "pluginid": "6",
                        "alertRef": "6-1",
                        "name": "Path Traversal",
                        "riskcode": "3",
                        "confidence": "2",
                        "riskdesc": "High (Medium)",
                        "instances": [
                            {
                                "uri": _q(base_url, "/files", name=TRAVERSAL_REAL),
                                "method": "GET",
                                "param": "name",
                                "attack": TRAVERSAL_REAL,
                                "evidence": "SETTLEMENT_SIGNING_KEY",
                            },
                            {
                                "uri": _q(base_url, "/files", name=TRAVERSAL_STALE),
                                "method": "GET",
                                "param": "name",
                                "attack": TRAVERSAL_STALE,
                                "evidence": "root:x:0:0",
                            },
                        ],
                        "count": "2",
                        "cweid": "22",
                    },
                    {
                        "pluginid": "40014",
                        "alertRef": "40014",
                        "name": "Cross Site Scripting (Persistent)",
                        "riskcode": "3",
                        "confidence": "2",
                        "riskdesc": "High (Medium)",
                        "instances": [
                            {
                                "uri": base_url + "/api/notes",
                                "method": "POST",
                                "param": "body",
                                "attack": XSS_ATTACK,
                                "evidence": XSS_ATTACK,
                            }
                        ],
                        "count": "1",
                        "cweid": "79",
                    },
                    {
                        "pluginid": "10038",
                        "alertRef": "10038-1",
                        "name": "Content Security Policy (CSP) Header Not Set",
                        "riskcode": "2",
                        "confidence": "3",
                        "riskdesc": "Medium (High)",
                        "instances": [
                            {"uri": base_url + "/login", "method": "GET", "param": "", "attack": "", "evidence": ""},
                            {"uri": base_url + "/search", "method": "GET", "param": "", "attack": "", "evidence": ""},
                        ],
                        "count": "2",
                        "cweid": "693",
                    },
                ],
            }
        ],
    }


# Layout from ZAP's baseline-scan documentation: "<id><TAB><ACTION>[<TAB><message>]"; lines starting with # are
# comments; only the rule id is used (the name in brackets is for people). The id is the rule's PLUGIN id: an
# alert reference such as 10038-1 is the rule id 10038 plus a dash and the alert type.
BASELINE_CONFIG = (
    "# zap-baseline rule configuration file\n"
    "# Change WARN to IGNORE to ignore rule or FAIL to fail if rule matches\n"
    "10010\tWARN\t(Cookie No HttpOnly Flag)\n"
    "10011\tFAIL\t(Cookie Without Secure Flag)\tsession cookies must be Secure\n"
    "10021\tIGNORE\t(X-Content-Type-Options Header Missing)\n"
    "10036\tINFO\t(HTTP Server Response Header)\n"
    "10038\tWARN\t(Content Security Policy (CSP) Header)\n"
)
