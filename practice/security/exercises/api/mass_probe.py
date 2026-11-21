"""EXERCISE - Probe PATCH /api/profile for mass assignment without changing anything.

Mass assignment (API3:2023, Broken Object Property Level Authorization): the API binds the client's JSON to an
object and lets it set properties it should never control, such as ``role``.

Write ``read_profile`` and ``probe_mass_assignment``. The probe must:

1. read the caller's profile with ``GET /api/me`` (raise ``RuntimeError`` if that is not a 200 - the control);
2. PATCH ``display_name`` (a field the user may edit) with its current value - the control; raise
   ``RuntimeError`` unless it is a 200;
3. PATCH each of ``PRIVILEGED`` alone, with the value the caller ALREADY has, so nothing changes. A field is
   *accepted* when the answer is 200 and the response shows that property with the same value; otherwise
   record the status code in ``refused``;
4. read the profile again and raise ``RuntimeError`` if it differs from step 1;
5. fill in ``vulnerable`` (any accepted) and a one-line ``evidence``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

PRIVILEGED = ("role", "merchant_id")
CONTROL = "display_name"


@dataclass
class MassAssignmentResult:
    vulnerable: bool = False
    control_ok: bool = False
    accepted: list[str] = field(default_factory=list)
    refused: dict[str, int] = field(default_factory=dict)  # field -> status code
    evidence: str = ""


def read_profile(base_url: str, token: str, timeout: float = 5) -> dict:
    """GET /api/me as the caller; raise RuntimeError unless the answer is 200."""
    raise NotImplementedError("TODO: implement read_profile")


def probe_mass_assignment(base_url: str, token: str, timeout: float = 5) -> MassAssignmentResult:
    """Send each privileged property alone, with its current value, and report which the server accepts."""
    raise NotImplementedError("TODO: implement probe_mass_assignment")
