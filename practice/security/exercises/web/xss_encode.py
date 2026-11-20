"""Context-aware output encoding, following the OWASP Cross Site Scripting Prevention Cheat Sheet.

EXERCISE: implement every function marked TODO. Check with: .venv/bin/python -m pytest tests/web/test_xss_encode.py

In real code, use your framework's auto-escaping or a maintained encoder library - the cheat sheet says so,
and so does this lesson. Writing a small encoder once is how a tester learns what "the right encoding for
the context" means, and how to check that a fix used it.

- ``encode_html_text`` - HTML entity encoding for text between tags (the cheat sheet's table:
  ``&`` ``&amp;``, ``<`` ``&lt;``, ``>`` ``&gt;``, ``"`` ``&quot;``, ``'`` ``&#x27;``).
- ``render_attribute`` - a quoted attribute with a FIXED, allow-listed name and an encoded value ("Always
  surround attribute values with double (") or single (') quotation marks"; "Keep element and attribute
  names fixed").
- ``encode_url_param`` - percent-encoding for one query parameter value (the cheat sheet's URL context).
- ``safe_href`` - an untrusted URL for ``href``/``src``: canonicalise, allow-list http and https (and local
  paths), then attribute-encode ("Allow-list http and HTTPS URLs only ... Attribute encoder").
"""

from __future__ import annotations

import re
import urllib.parse

_HTML = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;"}
ALLOWED_ATTRIBUTES = frozenset({"title", "value", "alt", "placeholder", "class", "id", "name", "href"})
_TAB_OR_NEWLINE = re.compile(r"[\t\n\r]")


def encode_html_text(value: str) -> str:
    """Entity-encodes the five characters the cheat sheet lists. ``&`` first, so nothing is encoded twice."""
    raise NotImplementedError("TODO: encode_html_text")


def render_attribute(name: str, value: str) -> str:
    """``name="encoded value"``. The name must be one of ``ALLOWED_ATTRIBUTES`` - names are never taken from
    input - and the value is always double-quoted and encoded (so neither quote can end it)."""
    raise NotImplementedError("TODO: render_attribute")


def encode_url_param(value: str) -> str:
    """Percent-encodes one parameter value: every byte except unreserved letters, digits and ``-._~``."""
    raise NotImplementedError("TODO: encode_url_param")


def safe_href(url: str, fallback: str = "#") -> str:
    """An attribute-encoded URL that is safe to put in ``href``, or ``fallback`` (encoded) if it is not.

    Canonicalise first, as browsers do (WHATWG URL Standard, basic URL parser): strip leading and trailing
    C0 control or space characters, and remove every ASCII tab or newline - so ``" java\\tscript:..."`` is
    still ``javascript:``. Then allow only ``http``, ``https`` and paths on this site: ``/...`` but not
    ``//host`` or ``/\\host`` (browsers treat a backslash like a slash in http(s) URLs, so both are
    protocol-relative)."""
    raise NotImplementedError("TODO: safe_href")
