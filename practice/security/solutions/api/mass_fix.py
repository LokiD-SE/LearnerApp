"""SOLUTION - The two fixes: an allow-list for what goes in, a response model for what comes out."""

from __future__ import annotations

EDITABLE = {"display_name": str}
MAX_NAME = 60


def apply_profile_update(user: dict, payload: dict) -> dict:
    """Return a NEW user dict with the update applied. Never change ``user`` in place.

    Raise ``ValueError("fields not allowed: [...]")`` (names sorted) when the payload has any key outside the
    allow-list - reject, do not silently drop. Raise ``ValueError`` for a ``display_name`` that is not a
    string, is blank, or is longer than 60 characters.
    """
    unknown = sorted(set(payload) - set(EDITABLE))
    if unknown:
        raise ValueError(f"fields not allowed: {unknown}")
    updated = dict(user)
    for name, kind in EDITABLE.items():
        if name in payload:
            value = payload[name]
            if not isinstance(value, kind) or not value.strip() or len(value) > MAX_NAME:
                raise ValueError(f"{name} must be a non-blank string of at most {MAX_NAME} characters")
            updated[name] = value.strip()
    return updated


def merchant_view(row: dict) -> dict:
    """The response model for a merchant: ``id``, ``name`` and ``payout_iban_last4`` - nothing else."""
    iban = row["payout_iban"].replace(" ", "")
    return {"id": row["id"], "name": row["name"], "payout_iban_last4": iban[-4:]}
