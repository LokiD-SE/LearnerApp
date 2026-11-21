"""EXERCISE - The two fixes for API3: an allow-list for what goes in, a response model for what comes out.

* ``apply_profile_update(user, payload)`` returns a NEW dict with the update applied and never changes ``user``.
  Only ``display_name`` is editable (``EDITABLE``). Any other key raises
  ``ValueError("fields not allowed: [...]")`` with the names sorted - reject, do not silently drop - and
  nothing is applied. ``display_name`` must be a string that is not blank and at most ``MAX_NAME`` characters,
  otherwise ``ValueError``; store it stripped.
* ``merchant_view(row)`` is the response model for a merchant database row: exactly ``id``, ``name`` and
  ``payout_iban_last4`` (the last four characters of the IBAN with spaces removed).
"""

from __future__ import annotations

EDITABLE = {"display_name": str}
MAX_NAME = 60


def apply_profile_update(user: dict, payload: dict) -> dict:
    raise NotImplementedError("TODO: implement apply_profile_update")


def merchant_view(row: dict) -> dict:
    raise NotImplementedError("TODO: implement merchant_view")
