"""Stored XSS probe (WSTG-INPV-02): write a harmless marker through one request, read it back through another.

EXERCISE: implement every function marked TODO. Check with: .venv/bin/python -m pytest tests/web/test_xss_stored.py

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
    raise NotImplementedError("TODO: make_marker")


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
    raise NotImplementedError("TODO: probe_stored")
