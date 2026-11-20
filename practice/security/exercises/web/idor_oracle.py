"""EXERCISE - Does a denied response reveal that the object exists? (an existence oracle)

When access is denied, the server should not tell an attacker *which* ids exist. Compare three answers for
the same caller:

- ``own``: an object the caller owns - the **control**; it must be readable, or the comparison proves nothing;
- ``foreign``: an object that exists but belongs to someone else;
- ``missing``: an id that does not exist at all.

Verdicts:

- ``readable``: the foreign object came back with a 2xx - that is an IDOR, worse than any oracle;
- ``oracle``: foreign and missing differ in status (403 against 404) or in the body text once each id is
  replaced by a placeholder (``invoice inv_601 is not yours`` against ``invoice inv_999 not found``) - an
  attacker can enumerate which ids exist;
- ``indistinguishable``: same status and same body - nothing leaks through the reply.

Response time can be an oracle too (a database lookup for a real id, none for a missing one); this check does
not measure it, and a single timing proves little - that needs many samples.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class Reply:
    status: int
    body: str


def fetch(base_url: str, path: str, token: str) -> Reply:
    """GET ``path`` with ``Authorization: Bearer <token>``; no redirects."""
    resp = requests.get(base_url + path, headers={"Authorization": f"Bearer {token}"},
                        allow_redirects=False, timeout=5)
    return Reply(resp.status_code, resp.text)


def normalise(body: str, object_id: str) -> str:
    """The body with every occurrence of ``object_id`` replaced by ``{id}``, so two error messages that only
    echo different ids compare equal."""
    raise NotImplementedError("TODO: implement normalise")


def classify(own: Reply, foreign: Reply, missing: Reply, foreign_id: str, missing_id: str) -> str:
    """Return ``readable``, ``oracle`` or ``indistinguishable`` (see the module docstring).

    Raise ``ValueError`` when the control ``own`` is not a 2xx.
    """
    raise NotImplementedError("TODO: implement classify")


def check_existence_oracle(base_url: str, path_template: str, token: str, own_id: str, foreign_id: str,
                           missing_id: str) -> str:
    """Fetch ``path_template`` (with ``{id}``) for the three ids as one caller and classify the replies."""
    raise NotImplementedError("TODO: implement check_existence_oracle")
