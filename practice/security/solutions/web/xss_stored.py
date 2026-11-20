"""Stored XSS probe (WSTG-INPV-02): write a harmless marker through one request, read it back through another.

Stored XSS "typically involves at least two requests" (WSTG-INPV-02): the write and every later read. So the
probe needs two endpoints - where input is stored and where it is displayed - and a marker it can recognise
among everything else on the page.

Harmless by design: the marker is a made-up element (``<xq...>``) with a made-up attribute. If it comes back
raw, the page lets a user add markup - the precondition for script - without the probe ever storing script
that a real colleague's browser might run. Testers on shared environments should work this way.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

import requests

BREAKOUT_TEXT = "<"  # the character that starts markup in an HTML text context


def make_marker() -> tuple[str, str]:
    """(canary, payload): a unique canary and a payload that is markup only if ``<`` survives.

    The payload is ``<CANARY data-probe="CANARY">`` - an unknown element with an inert attribute: no
    script, no event handler, no URL."""
    canary = f"xq{secrets.token_hex(5)}"
    return canary, f'<{canary} data-probe="{canary}">'


@dataclass
class StoredFinding:
    write_path: str
    read_path: str
    payload: str
    evidence: str  # the page fragment where the payload appears unencoded


def probe_stored(base_url: str, token: str, write_path: str = "/api/notes", read_path: str = "/notes",
                 field: str = "body", session: requests.Session | None = None) -> StoredFinding | None:
    """Stores the marker with ``POST write_path {field: payload}`` and reads ``read_path``, both with the
    bearer ``token``. Returns a finding if the payload comes back raw; ``None`` if it comes back encoded.

    Raises ``RuntimeError`` if the write fails or the canary is not on the read page at all - then the
    probe has proved nothing either way, and saying "not vulnerable" would be a false negative."""
    s = session or requests.Session()
    auth = {"Authorization": f"Bearer {token}"}
    canary, payload = make_marker()
    w = s.post(base_url + write_path, json={field: payload}, headers=auth, timeout=5)
    if w.status_code >= 300:
        raise RuntimeError(f"write failed: {w.status_code} {w.text[:200]}")
    page = s.get(base_url + read_path, headers=auth, timeout=5).text
    if canary not in page:
        raise RuntimeError(f"the marker {canary} is not on {read_path}: nothing proved")
    at = page.find(payload)
    if at < 0:
        return None  # stored, displayed, but encoded
    return StoredFinding(write_path, read_path, payload, page[max(0, at - 20): at + len(payload) + 20])
