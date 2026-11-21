"""SOLUTION - Probe PATCH /api/profile for mass assignment, without changing anything."""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

# Properties a client has no business setting: the server decides them. Each is sent with the value the
# caller ALREADY has, so a vulnerable portal accepts it and nothing changes.
PRIVILEGED = ("role", "merchant_id")
CONTROL = "display_name"


@dataclass
class MassAssignmentResult:
    vulnerable: bool = False
    control_ok: bool = False
    accepted: list[str] = field(default_factory=list)
    refused: dict[str, int] = field(default_factory=dict)  # field -> status code
    evidence: str = ""


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def read_profile(base_url: str, token: str, timeout: float = 5) -> dict:
    resp = requests.get(base_url + "/api/me", headers=_auth(token), timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"GET /api/me returned {resp.status_code}: the token does not work, no verdict possible")
    return resp.json()


def probe_mass_assignment(base_url: str, token: str, timeout: float = 5) -> MassAssignmentResult:
    """Send each privileged property alone, with its current value, and report which ones the server accepts.

    The control is ``display_name``, a field the user may edit: it must be accepted, otherwise a refusal of
    the other fields would only mean that PATCH does not work for this caller.
    """
    before = read_profile(base_url, token, timeout)
    result = MassAssignmentResult()

    def patch(name: str) -> requests.Response:
        return requests.patch(base_url + "/api/profile", json={name: before[name]}, headers=_auth(token),
                              timeout=timeout)

    control = patch(CONTROL)
    result.control_ok = control.status_code == 200
    if not result.control_ok:
        raise RuntimeError(f"control PATCH of {CONTROL} returned {control.status_code}: no verdict possible")

    for name in PRIVILEGED:
        resp = patch(name)
        if resp.status_code == 200 and resp.json().get(name) == before[name]:
            result.accepted.append(name)
        else:
            result.refused[name] = resp.status_code

    after = read_profile(base_url, token, timeout)
    if after != before:
        raise RuntimeError("the probe changed the profile; it must send only the values the caller already has")
    result.vulnerable = bool(result.accepted)
    result.evidence = (f"PATCH /api/profile accepted {', '.join(result.accepted)}" if result.vulnerable
                       else f"PATCH /api/profile refused {result.refused}")
    return result
