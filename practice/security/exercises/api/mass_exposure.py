"""EXERCISE - Find excessive data exposure in a JSON response without ever printing the secret.

Write three functions, then ``check_merchant_exposure`` which uses them on the portal.

* ``find_sensitive(value)`` walks dicts and lists and returns an ``Exposure`` for every key whose NAME matches
  ``SENSITIVE_KEY`` (do not look inside that key's value) and every string value shaped like a full IBAN
  (``FULL_IBAN``). Paths look like ``$.owner.password_hash`` and ``$.items[0].token``. The result must never
  contain the value itself. A masked value such as ``****0001`` is not an exposure.
* ``outside_contract(body, documented)`` lists the top-level properties the response has that the API
  contract (``documented``) does not, sorted by name, reason ``"not in the contract"``.
* ``check_merchant_exposure(base_url, token, documented)`` reads ``/api/me``, then the caller's own
  ``/api/merchants/<id>``, and returns the contract breaches first, then the other sensitive findings whose
  path was not already listed. Raise ``RuntimeError`` when either call is not a 200.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

SENSITIVE_KEY = re.compile(r"(secret|password|passwd|hash|token|api_?key|private)", re.I)
FULL_IBAN = re.compile(r"^[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?$")


@dataclass(frozen=True)
class Exposure:
    path: str    # "$.api_secret" or "$.items[0].password_hash"
    reason: str  # "sensitive key name" | "full IBAN" | "not in the contract"


def find_sensitive(value, path: str = "$") -> list[Exposure]:
    raise NotImplementedError("TODO: implement find_sensitive")


def outside_contract(body: dict, documented: set[str]) -> list[Exposure]:
    raise NotImplementedError("TODO: implement outside_contract")


def check_merchant_exposure(base_url: str, token: str, documented: set[str], timeout: float = 5) -> list[Exposure]:
    raise NotImplementedError("TODO: implement check_merchant_exposure")
