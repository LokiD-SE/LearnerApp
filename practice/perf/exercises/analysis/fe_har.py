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

PHASES = ("blocked", "dns", "connect", "ssl", "send", "wait", "receive")


def phases(entry):
    raise NotImplementedError("TODO: floats for the seven phases, -1 or missing is 0.0")


def total_time(entry):
    raise NotImplementedError("TODO: sum of phases(entry)")


def size(entry):
    raise NotImplementedError("TODO: _transferSize, else bodySize, else content.size (skip negatives)")


def kind(entry):
    raise NotImplementedError("TODO: html, css, js, image, api or other from the mime type")


def summarise(har):
    raise NotImplementedError("TODO: requests, bytes, by_kind and the slowest path")


def waterfall(har):
    raise NotImplementedError("TODO: start and end in ms from the page start, sorted by start")


def check_budget(summary, budget):
    raise NotImplementedError("TODO: sorted '<name>: <actual> > <limit>' strings")
