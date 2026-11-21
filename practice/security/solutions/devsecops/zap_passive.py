"""SOLUTION - A tiny passive scanner in the spirit of ZAP's passive rules.

Passive means it only READS responses it is given; it sends no attack. ``passive_alerts`` judges one recorded
response; ``passive_scan`` fetches the steps you list (ordinary requests, like a person using the site) and
judges every response. These are simplified versions of the rules ZAP documents, not ZAP's code.
"""

from __future__ import annotations

import re
import urllib.parse

import requests
from zap_fixture import RISKS, Finding

# rule id -> (name, risk), exactly as the ZAP alert documentation lists them (read 21 November 2026).
RULES = {
    "10038-1": ("Content Security Policy (CSP) Header Not Set", "Medium"),
    "10020-1": ("Missing Anti-clickjacking Header", "Medium"),
    "10021": ("X-Content-Type-Options Header Missing", "Low"),
    "10036-2": ('Server Leaks Version Information via "Server" HTTP Response Header Field', "Low"),
    "10035-4": ("Strict-Transport-Security Header on Plain HTTP Response", "Informational"),
    "10010": ("Cookie No HttpOnly Flag", "Low"),
    "10011": ("Cookie Without Secure Flag", "Low"),
    "10054-1": ("Cookie without SameSite Attribute", "Low"),
    "90022": ("Application Error Disclosure", "Medium"),
}
LOOPBACK = ("127.0.0.1", "localhost", "::1")
ERROR_TEXT = re.compile(r'Traceback \(most recent call last\)|^\s*File ".+", line \d+', re.MULTILINE)


def is_loopback(url: str) -> bool:
    return urllib.parse.urlsplit(url).hostname in LOOPBACK


def passive_alerts(url: str, status: int, headers: list[tuple[str, str]], body: str) -> list[Finding]:
    by_name: dict[str, list[str]] = {}
    for name, value in headers:
        by_name.setdefault(name.lower(), []).append(value)
    is_html = "text/html" in " ".join(by_name.get("content-type", [])).lower()
    csp = " ".join(by_name.get("content-security-policy", [])).lower()
    found: list[Finding] = []

    def add(rule_id: str, evidence: str = "") -> None:
        name, risk = RULES[rule_id]
        found.append(Finding(rule_id, name, risk, url, evidence=evidence))

    if is_html and not csp:
        add("10038-1")
    if is_html and not (by_name.get("x-frame-options") or "frame-ancestors" in csp):
        add("10020-1")
    if "nosniff" not in " ".join(by_name.get("x-content-type-options", [])).lower():
        add("10021")
    server = " ".join(by_name.get("server", []))
    if re.search(r"\d", server):
        add("10036-2", server)
    hsts = by_name.get("strict-transport-security")
    if hsts and url.startswith("http://"):
        add("10035-4", hsts[0])
    for cookie in by_name.get("set-cookie", []):
        cookie_name = cookie.split("=", 1)[0].strip()  # the NAME is evidence; the value is a session id
        attrs = [a.strip().lower() for a in cookie.split(";")[1:]]
        if "httponly" not in attrs:
            add("10010", cookie_name)
        if "secure" not in attrs:
            add("10011", cookie_name)
        if not any(a.startswith("samesite=") for a in attrs):
            add("10054-1", cookie_name)
    match = ERROR_TEXT.search(body)
    if match:
        add("90022", match.group(0).strip()[:80])
    return found


def passive_scan(base_url: str, steps: list[tuple[str, str, dict | None]], timeout: float = 5) -> list[Finding]:
    if not is_loopback(base_url):
        raise ValueError(f"refusing to scan {base_url}: the practice scanner only talks to loopback")
    seen: set[tuple[str, str, str]] = set()
    found: list[Finding] = []
    for method, path, payload in steps:
        resp = requests.request(method, base_url + path, json=payload, timeout=timeout, allow_redirects=False)
        headers = [(k, v) for k, v in resp.headers.items() if k.lower() != "set-cookie"]
        headers += [("Set-Cookie", c) for c in resp.raw.headers.getlist("Set-Cookie")]
        for alert in passive_alerts(base_url + path, resp.status_code, headers, resp.text):
            key = (alert.rule_id, alert.uri, alert.evidence)
            if key not in seen:
                seen.add(key)
                found.append(alert)
    return sorted(found, key=lambda a: (-RISKS.index(a.risk), a.rule_id, a.uri))
