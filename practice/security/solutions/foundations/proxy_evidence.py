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

import copy
import json
import urllib.parse

from proxy_fixture import Exchange

SENSITIVE_HEADERS = ("authorization", "proxy-authorization", "cookie", "set-cookie")
SENSITIVE_FIELDS = ("password", "token", "api_secret", "csrf")
MASK = "[REDACTED]"


def _header_list(headers: list[tuple[str, str]]) -> list[dict]:
    return [{"name": n, "value": v} for n, v in headers]


def _get(headers: list[tuple[str, str]], name: str) -> str | None:
    return next((v for n, v in headers if n.lower() == name), None)


def _request_cookies(headers: list[tuple[str, str]]) -> list[dict]:
    out = []
    for n, v in headers:
        if n.lower() == "cookie":
            for part in v.split(";"):
                name, sep, value = part.strip().partition("=")
                if sep and name:
                    out.append({"name": name, "value": value})
    return out


def _response_cookies(headers: list[tuple[str, str]]) -> list[dict]:
    out = []
    for n, v in headers:
        if n.lower() != "set-cookie":
            continue
        name_value, *attrs = [p.strip() for p in v.split(";")]
        name, _, value = name_value.partition("=")
        cookie = {"name": name, "value": value, "httpOnly": False, "secure": False}
        for attr in attrs:
            key, _, val = attr.partition("=")
            k = key.strip().lower()
            if k == "path":
                cookie["path"] = val
            elif k == "domain":
                cookie["domain"] = val
            elif k == "httponly":
                cookie["httpOnly"] = True
            elif k == "secure":
                cookie["secure"] = True
        out.append(cookie)
    return out


def _entry(x: Exchange) -> dict:
    split = urllib.parse.urlsplit(x.url)
    request = {
        "method": x.method,
        "url": urllib.parse.urlunsplit(split._replace(fragment="")),
        "httpVersion": x.http_version,
        "cookies": _request_cookies(x.request_headers),
        "headers": _header_list(x.request_headers),
        "queryString": [{"name": k, "value": v}
                        for k, v in urllib.parse.parse_qsl(split.query, keep_blank_values=True)],
        "headersSize": -1,
        "bodySize": len(x.request_body),
    }
    if x.request_body:
        request["postData"] = {"mimeType": _get(x.request_headers, "content-type") or "",
                               "text": x.request_body.decode("utf-8", errors="replace")}
    response = {
        "status": x.status,
        "statusText": x.reason,
        "httpVersion": x.http_version,
        "cookies": _response_cookies(x.response_headers),
        "headers": _header_list(x.response_headers),
        "content": {"size": len(x.response_body), "mimeType": _get(x.response_headers, "content-type") or "",
                    "text": x.response_body.decode("utf-8", errors="replace")},
        "redirectURL": _get(x.response_headers, "location") or "",
        "headersSize": -1,
        "bodySize": len(x.response_body),
    }
    timings = {"send": round(x.send_ms, 3), "wait": round(x.wait_ms, 3), "receive": round(x.receive_ms, 3)}
    entry = {
        "startedDateTime": x.started.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "time": round(timings["send"] + timings["wait"] + timings["receive"], 3),
        "request": request,
        "response": response,
        "cache": {},
        "timings": timings,
    }
    if x.notes:
        entry["comment"] = "; ".join(x.notes)
    return entry


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
    entries = [_entry(x) for x in sorted(exchanges, key=lambda x: x.started)]
    return {"log": {"version": "1.2", "creator": {"name": creator_name, "version": creator_version},
                    "entries": entries}}


def _mask_json(text: str, fields: set[str]) -> str:
    try:
        data = json.loads(text)
    except ValueError:
        return text

    def walk(node):
        if isinstance(node, dict):
            return {k: (MASK if k.lower() in fields else walk(v)) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return json.dumps(walk(data))


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
    out = copy.deepcopy(har)
    hdrs = {h.lower() for h in header_names}
    flds = {f.lower() for f in fields}
    for entry in out["log"]["entries"]:
        for part in (entry["request"], entry["response"]):
            for h in part["headers"]:
                if h["name"].lower() in hdrs:
                    h["value"] = MASK
            for c in part["cookies"]:
                c["value"] = MASK
        for q in entry["request"]["queryString"]:
            if q["name"].lower() in flds:
                q["value"] = MASK
        post = entry["request"].get("postData")
        if post:
            if post.get("mimeType", "").startswith("application/x-www-form-urlencoded"):
                pairs = urllib.parse.parse_qsl(post["text"], keep_blank_values=True)
                post["text"] = urllib.parse.urlencode([(k, MASK if k.lower() in flds else v) for k, v in pairs])
            else:
                post["text"] = _mask_json(post["text"], flds)
        content = entry["response"]["content"]
        if "text" in content:
            content["text"] = _mask_json(content["text"], flds)
    return out

