"""Reading a HAR file: phases, sizes, a waterfall and a budget (standard library only).

``har`` is a HAR 1.2 dict as saved by a browser or Playwright: ``har["log"]["pages"][0]["startedDateTime"]`` and
``har["log"]["entries"]``, each entry with ``startedDateTime``, ``time``, ``request.url``, ``response.content``
(``size``, ``mimeType``), ``response.bodySize``, optional ``response._transferSize`` and ``timings``.

1. ``phases(entry)`` - the timings as floats for ``blocked, dns, connect, ssl, send, wait, receive``. A missing key
   or a ``-1`` ("does not apply", in the HAR specification) is ``0.0``.
2. ``total_time(entry)`` - the sum of ``phases(entry)`` (the specification: the entry ``time`` is the sum of all
   timings that are not -1).
3. ``size(entry)`` - the bytes the response took on the wire: ``response._transferSize`` when present and not
   negative, else ``response.bodySize`` when not negative, else ``response.content.size``.
4. ``kind(entry)`` - from ``response.content.mimeType`` (ignore parameters after ``;``): ``"html"`` for
   ``text/html``, ``"css"`` for ``text/css``, ``"js"`` for ``application/javascript`` or ``text/javascript``,
   ``"image"`` for ``image/*``, ``"api"`` for ``application/json``, otherwise ``"other"``.
5. ``summarise(har)`` - ``{"requests": n, "bytes": total, "by_kind": {kind: {"requests", "bytes"}}, "slowest": path}``
   where ``slowest`` is the URL path (no scheme or host) of the entry with the largest ``total_time``.
6. ``waterfall(har)`` - one dict per entry ``{"path", "start", "end"}`` sorted by ``start``: ``start`` is the
   milliseconds from the page's ``startedDateTime`` to the entry's, ``end`` is ``start + total_time``. Round both to
   one decimal.
7. ``check_budget(summary, budget)`` - ``budget`` may hold ``requests``, ``bytes``, ``js_bytes`` and ``image_bytes``
   as upper limits (a limit equal to the value passes). Return a sorted list of ``"<name>: <actual> > <limit>"``
   strings for the limits that are exceeded (``js_bytes`` and ``image_bytes`` are ``summary["by_kind"]`` bytes, 0 when
   the kind is absent). An empty list means the budget holds.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

PHASES = ("blocked", "dns", "connect", "ssl", "send", "wait", "receive")


def phases(entry):
    timings = entry.get("timings", {})
    out = {}
    for name in PHASES:
        value = timings.get(name)
        out[name] = 0.0 if value is None or value < 0 else float(value)
    return out


def total_time(entry):
    return sum(phases(entry).values())


def size(entry):
    response = entry["response"]
    transfer = response.get("_transferSize")
    if transfer is not None and transfer >= 0:
        return transfer
    if response.get("bodySize", -1) >= 0:
        return response["bodySize"]
    return response["content"]["size"]


def kind(entry):
    mime = entry["response"]["content"]["mimeType"].split(";")[0].strip().lower()
    if mime == "text/html":
        return "html"
    if mime == "text/css":
        return "css"
    if mime in ("application/javascript", "text/javascript"):
        return "js"
    if mime.startswith("image/"):
        return "image"
    if mime == "application/json":
        return "api"
    return "other"


def _path(entry):
    return urlsplit(entry["request"]["url"]).path


def summarise(har):
    entries = har["log"]["entries"]
    by_kind = {}
    for e in entries:
        slot = by_kind.setdefault(kind(e), {"requests": 0, "bytes": 0})
        slot["requests"] += 1
        slot["bytes"] += size(e)
    slowest = max(entries, key=total_time) if entries else None
    return {
        "requests": len(entries),
        "bytes": sum(size(e) for e in entries),
        "by_kind": by_kind,
        "slowest": _path(slowest) if slowest else None,
    }


def waterfall(har):
    page_start = datetime.fromisoformat(har["log"]["pages"][0]["startedDateTime"])
    rows = []
    for e in har["log"]["entries"]:
        start = (datetime.fromisoformat(e["startedDateTime"]) - page_start).total_seconds() * 1000
        rows.append({"path": _path(e), "start": round(start, 1), "end": round(start + total_time(e), 1)})
    return sorted(rows, key=lambda r: r["start"])


def check_budget(summary, budget):
    actual = {
        "requests": summary["requests"],
        "bytes": summary["bytes"],
        "js_bytes": summary["by_kind"].get("js", {}).get("bytes", 0),
        "image_bytes": summary["by_kind"].get("image", {}).get("bytes", 0),
    }
    return sorted(f"{name}: {actual[name]} > {limit}" for name, limit in budget.items() if actual[name] > limit)
