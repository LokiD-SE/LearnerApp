"""EXERCISE - API9 Improper Inventory Management: compare what is documented with what answers.

OWASP API9:2023: "Inventory all API hosts and document important aspects of each one", and an API has a
"documentation blindspot" when "there is no documentation or the existing documentation is not updated". The
WSTG's API reconnaissance page (WSTG-APIT-01) asks the tester to "find all API endpoints supported by the
backend server code, documented or undocumented".

This exercise does the comparison on the practice portal:

1. ``probe_paths`` requests a wordlist of candidate paths WITHOUT signing in and keeps the ones that exist.
   The portal's answer for a route it does not have is ``404`` with the body ``{"error": "not found"}``. Any
   other answer - 200, 401, 403, 405, 500, or even a 404 with a different message such as "file not found" -
   means a handler answered, so the route exists. Status alone is not enough: ``/files`` answers 404 too.
2. ``undocumented`` compares what exists with the documented templates (``/api/payments/{id}`` matches exactly
   one extra path segment) and returns the difference - the shadow endpoints.
"""

from __future__ import annotations

import requests  # noqa: F401 - used by probe_paths

MISSING_ROUTE_BODY = {"error": "not found"}


def route_exists(status: int, body: object) -> bool:
    """True when the answer came from a handler, False for the portal's "no such route" answer."""
    raise NotImplementedError("TODO: implement route_exists")


def probe_paths(base_url: str, candidates: list[str] | tuple[str, ...]) -> dict[str, int]:
    """``{path: status}`` for every candidate path that exists, in the order given.

    Send an unauthenticated GET without following redirects (a 302 is an answer, not a path to chase).
    """
    raise NotImplementedError("TODO: implement probe_paths")


def matches_template(path: str, template: str) -> bool:
    """``/api/payments/pay_1001`` matches ``/api/payments/{id}``: same segment count, ``{...}`` matches any one."""
    raise NotImplementedError("TODO: implement matches_template")


def undocumented(observed: dict[str, int], documented: list[str] | tuple[str, ...]) -> list[str]:
    """The observed paths that match no documented template, sorted."""
    raise NotImplementedError("TODO: implement undocumented")
