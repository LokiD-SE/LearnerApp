"""Evidence you can hand over: recorded exchanges as an HTTP Archive (HAR) 1.2 log, with secrets redacted.

ZAP and Burp can both save traffic; HAR is the format browsers' developer tools also export, so a developer
can open your evidence in their own tools. Field rules follow the HAR 1.2 specification (Jan Odvarko,
softwareishard.com). The spec warns that a HAR "can contain privacy & security sensitive data", so evidence
leaves your machine only after ``redact``.

You write:

- ``to_har(exchanges, creator_name, creator_version)`` - the HAR log as a dict (``json.dumps`` it to save);
- ``redact(har, ...)`` - a copy with credentials and secrets masked.
"""

from __future__ import annotations

import copy  # noqa: F401 - you will need these
import json  # noqa: F401
import urllib.parse  # noqa: F401

from proxy_fixture import Exchange

SENSITIVE_HEADERS = ("authorization", "proxy-authorization", "cookie", "set-cookie")
SENSITIVE_FIELDS = ("password", "token", "api_secret", "csrf")
MASK = "[REDACTED]"


def _header_list(headers: list[tuple[str, str]]) -> list[dict]:
    return [{"name": n, "value": v} for n, v in headers]


def _get(headers: list[tuple[str, str]], name: str) -> str | None:
    return next((v for n, v in headers if n.lower() == name), None)


def to_har(exchanges: list[Exchange], creator_name: str = "sandpay-recorder", creator_version: str = "1.0") -> dict:
    """A HAR 1.2 document: ``{"log": {"version": "1.2", "creator": {...}, "entries": [...]}}``.

    Per entry (sorted by ``started``, oldest first - "the preferred way"):
    - ``startedDateTime``: ISO 8601 with milliseconds and ``Z`` for UTC, e.g. ``2026-11-19T09:15:02.481Z``;
    - ``timings``: ``send``, ``wait``, ``receive`` in ms (rounded to 3 decimals); ``time`` is their sum;
    - ``request``: ``method``, ``url`` (no fragment), ``httpVersion``, ``cookies`` (``name``/``value`` from the
      Cookie header), ``headers`` (``name``/``value`` list, in order), ``queryString`` (name/value pairs,
      blank values kept), ``headersSize`` -1 (not measured), ``bodySize``, and ``postData`` (``mimeType`` from
      Content-Type, ``text``) only when there is a body;
    - ``response``: ``status``, ``statusText``, ``httpVersion``, ``cookies`` (from each Set-Cookie:
      ``name``, ``value``, ``httpOnly`` and ``secure`` booleans, ``path``/``domain`` when present),
      ``headers``, ``content`` (``size``, ``mimeType``, ``text``), ``redirectURL`` (Location or ``""``),
      ``headersSize`` -1, ``bodySize``;
    - ``cache``: ``{}``; ``comment``: the exchange's notes joined with ``"; "``, only if there are notes.
    No pages are recorded, so ``pages`` is left out.
    """
    raise NotImplementedError("TODO: implement to_har - see the docstring")


def redact(har: dict, header_names: tuple[str, ...] = SENSITIVE_HEADERS,
           fields: tuple[str, ...] = SENSITIVE_FIELDS) -> dict:
    """A deep copy of ``har`` with secrets replaced by ``"[REDACTED]"``; the input is not changed.

    - header values whose name (case-insensitive) is in ``header_names``, in requests and responses;
    - every cookie ``value`` in requests and responses;
    - query-string values whose name is in ``fields``;
    - in ``postData.text`` and ``content.text`` that parse as JSON: the value of every key (at any depth,
      case-insensitive) in ``fields``, re-serialised with ``json.dumps``; form-encoded ``postData.text``
      (``application/x-www-form-urlencoded``) gets the same treatment for its parameters.
    Everything else - URLs, status codes, other headers, timings - is kept, because it is the evidence.
    """
    raise NotImplementedError("TODO: implement redact - see the docstring")

