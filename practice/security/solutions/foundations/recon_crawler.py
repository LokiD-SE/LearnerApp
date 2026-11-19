"""A scope-safe crawler for mapping the SandPay practice portal (WSTG-INFO-07, Map Execution Paths).

Reference solution. The crawler is read-only and stays in scope:

- it sends only GET requests - it records forms, it never submits them;
- it fetches only URLs on the scope origin (scheme, host and port of ``base_url``); anything else it meets
  (a link, a form action or a redirect ``Location``) is recorded in ``out_of_scope`` and never requested;
- it does not follow redirects automatically - it reads ``Location`` itself so it can check the scope first;
- it stops after ``max_pages`` fetches.

Run it only against the local practice portal (``support/sandpay_vuln.py``) or a system you have written
permission to test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests


@dataclass
class Form:
    page: str  # path of the page the form is on
    action: str  # path (in scope) or absolute URL the form submits to
    method: str  # "GET" or "POST", upper case
    fields: list[tuple[str, str, str]]  # (name, type, value) for every named <input>, hidden ones included


@dataclass
class SiteMap:
    pages: dict[str, int] = field(default_factory=dict)  # path?query -> status code
    content_types: dict[str, str] = field(default_factory=dict)  # path?query -> Content-Type
    forms: list[Form] = field(default_factory=list)
    redirects: dict[str, str] = field(default_factory=dict)  # path?query -> Location as sent
    out_of_scope: set[str] = field(default_factory=set)  # absolute URLs seen but never requested


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.forms: list[dict] = []
        self._form: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "form":
            self._form = {"action": a.get("action", ""), "method": (a.get("method") or "GET").upper(), "fields": []}
            self.forms.append(self._form)
        elif tag in ("input", "textarea", "select") and self._form is not None and a.get("name"):
            self._form["fields"].append((a["name"], a.get("type", "text") if tag == "input" else tag, a.get("value", "")))

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._form = None


def _origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme, parts.netloc


def path_of(url: str) -> str:
    """``http://127.0.0.1:8765/files?name=a`` -> ``/files?name=a`` (the key used in a SiteMap)."""
    parts = urlsplit(url)
    return urlunsplit(("", "", parts.path or "/", parts.query, ""))


def in_scope(url: str, base_url: str) -> bool:
    """True only for the same scheme, host and port as ``base_url``."""
    return _origin(url) == _origin(base_url)


def crawl(base_url: str, seeds: list[str], session: requests.Session | None = None, max_pages: int = 50) -> SiteMap:
    """Breadth-first GET crawl from ``seeds`` (paths), staying on ``base_url``'s origin."""
    http = session or requests.Session()
    site = SiteMap()
    queue = [urljoin(base_url, s) for s in seeds]
    seen: set[str] = set()
    while queue and len(site.pages) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        if not in_scope(url, base_url):
            site.out_of_scope.add(url)
            continue
        resp = http.get(url, allow_redirects=False, timeout=5)
        key = path_of(url)
        site.pages[key] = resp.status_code
        site.content_types[key] = resp.headers.get("Content-Type", "")
        if resp.is_redirect and "Location" in resp.headers:
            location = resp.headers["Location"]
            site.redirects[key] = location
            queue.append(urljoin(url, location))
            continue
        if "html" not in site.content_types[key]:
            continue
        parser = _PageParser()
        parser.feed(resp.text)
        for href in parser.links:
            queue.append(urljoin(url, href))
        for f in parser.forms:
            target = urljoin(url, f["action"] or url)
            action = path_of(target) if in_scope(target, base_url) else target
            if not in_scope(target, base_url):
                site.out_of_scope.add(target)
            site.forms.append(Form(key, action, f["method"], f["fields"]))
    return site
