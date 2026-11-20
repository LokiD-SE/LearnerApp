"""Find what a portal gives away when it fails - the WSTG-ERRH-01 test, as code.

Exercise - fill in the TODOs; ``tests/web/test_misconf_errors.py`` checks your work. What each code means:

- ``stack-trace``: a Python ``Traceback (most recent call last)`` block or ``File "...", line N`` frame, a Java
  ``at pkg.Class(File.java:12)`` frame, or a JavaScript ``at fn (file.js:1:2)`` frame.
- ``file-path``: an absolute path under a common filesystem root (``/home``, ``/var``, ``/usr``, ``/etc``,
  ``/opt``, ``/srv``, ``/tmp``, ``/app``, ``/root``, ``/Users``) or a Windows drive path (``C:\\...``).
  Application URLs such as ``/api/payments/9`` are not file paths.
- ``connection-string``: ``scheme://...`` for postgres, postgresql, mysql, mongodb, redis, sqlite or amqp.
- ``secret``: a ``key``, ``secret``, ``password``, ``token`` or ``api_key`` assignment (``name=value`` or
  ``name: value``, value of six or more characters), or an ``sk_`` style key.
- ``sql-error``: a database error message or an echoed ``SELECT ... FROM`` statement.

``banner_discloses`` is the version-disclosure half of the ``missing-headers`` flaw: RFC 9110 section 10.2.4 says
a server "SHOULD NOT generate a Server header field containing needlessly fine-grained detail", and the OWASP
HTTP Headers Cheat Sheet says to "Remove all ``X-Powered-By`` headers".
"""

from __future__ import annotations

import re
import urllib.request
from urllib.error import HTTPError

STACK_TRACE = re.compile(
    r"Traceback \(most recent call last\)|^\s+File \".+\", line \d+|\bat [\w.$]+\([\w$]+\.java:\d+\)"
    r"|\bat .+ \(.+:\d+:\d+\)", re.M)
FILE_PATH = re.compile(
    r"(?<![\w:/.])(?:/(?:home|var|usr|etc|opt|srv|tmp|app|root|Users)/[\w.\-/]+|[A-Za-z]:\\[\w.\-\\ ]+)")
CONNECTION = re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb|redis|sqlite|amqp)://\S*", re.I)
SECRET = re.compile(
    r"(?i)(?<!\w)(?:secret|password|passwd|pwd|api[_-]?key|access[_-]?key|private[_-]?key|key|token)"
    r"\s*[=:]\s*[\"']?[^\s\"',;]{6,}|\bsk_[A-Za-z0-9_]{6,}")
SQL_ERROR = re.compile(
    r"(?i)\bsqlite3?\.OperationalError|syntax error at or near|error in your SQL syntax|SQLSTATE\[|\bORA-\d{5}"
    r"|unrecognized token|\bSELECT\b.+\bFROM\b")


def classify_leaks(body: str) -> list[str]:
    """Codes for everything an error body gives away, sorted; ``[]`` for a generic message.

    TODO: test ``body`` against the five patterns above and return the codes (``stack-trace``, ``file-path``,
    ``connection-string``, ``secret``, ``sql-error``) whose pattern matches, sorted.
    """
    raise NotImplementedError("classify_leaks")


def banner_discloses(headers: dict[str, str]) -> bool:
    """True when ``Server`` carries a product version, or any ``X-Powered-By`` header is present.

    TODO: lower-case the header names; any ``X-Powered-By`` -> True; otherwise True when the ``Server`` value has
    a ``/`` followed by a digit, or a dotted number such as ``3.12``. ``Server: SandPay`` is fine.
    """
    raise NotImplementedError("banner_discloses")


def fetch(url: str) -> tuple[int, dict[str, str], str]:
    """GET ``url`` (loopback practice target only) and return status, headers and body - for 4xx/5xx too."""
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - loopback practice target
            return resp.status, dict(resp.headers), resp.read(65536).decode(errors="replace")
    except HTTPError as err:
        return err.code, dict(err.headers), err.read(65536).decode(errors="replace")


def probe_errors(base_url: str, paths: list[str]) -> dict[str, list[str]]:
    """GET each path; return ``{path: codes}`` for the paths whose response leaks something (none -> omitted).

    TODO: use ``fetch`` (it also returns the body of 4xx and 5xx responses) and ``classify_leaks``.
    """
    raise NotImplementedError("probe_errors")


def scan(base_url: str, paths: list[str]) -> dict:
    """``{"leaks": probe_errors(...), "banner": banner_discloses(<headers of the first path>)}``.

    TODO: one call to ``fetch`` for the headers of ``paths[0]``, plus ``probe_errors`` for the leaks.
    """
    raise NotImplementedError("scan")
