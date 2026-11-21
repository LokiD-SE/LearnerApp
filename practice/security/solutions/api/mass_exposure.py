"""SOLUTION - Find excessive data exposure in a JSON response without ever printing the secret."""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

SENSITIVE_KEY = re.compile(r"(secret|password|passwd|hash|token|api_?key|private)", re.I)
FULL_IBAN = re.compile(r"^[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?$")


@dataclass(frozen=True)
class Exposure:
    path: str    # JSONPath-like, e.g. "$.api_secret" or "$.items[0].password_hash"
    reason: str  # "sensitive key name" | "full IBAN" | "not in the contract"


def find_sensitive(value, path: str = "$") -> list[Exposure]:
    """Walk dicts and lists; flag keys that name a secret and string values shaped like a full IBAN.

    Never include the value in the result. A masked IBAN such as ``****0001`` is not flagged.
    """
    found: list[Exposure] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if SENSITIVE_KEY.search(key):
                found.append(Exposure(child, "sensitive key name"))
            else:
                found.extend(find_sensitive(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(find_sensitive(item, f"{path}[{index}]"))
    elif isinstance(value, str) and FULL_IBAN.match(value.strip()):
        found.append(Exposure(path, "full IBAN"))
    return found


def outside_contract(body: dict, documented: set[str]) -> list[Exposure]:
    """Top-level properties the response carries that the API contract does not list, in sorted order."""
    return [Exposure(f"$.{key}", "not in the contract") for key in sorted(set(body) - documented)]


def check_merchant_exposure(base_url: str, token: str, documented: set[str], timeout: float = 5) -> list[Exposure]:
    """Read the caller's own merchant object and return every exposure, contract breaches first."""
    headers = {"Authorization": f"Bearer {token}"}
    me = requests.get(base_url + "/api/me", headers=headers, timeout=timeout)
    if me.status_code != 200:
        raise RuntimeError(f"GET /api/me returned {me.status_code}: no verdict possible")
    resp = requests.get(f"{base_url}/api/merchants/{me.json()['merchant_id']}", headers=headers, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"merchant read returned {resp.status_code}: no verdict possible")
    body = resp.json()
    breaches = outside_contract(body, documented)
    flagged = {e.path for e in breaches}
    return breaches + [e for e in find_sensitive(body) if e.path not in flagged]
