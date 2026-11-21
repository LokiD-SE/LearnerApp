"""EXERCISE - audit a card gateway for card-data leaks and weak tokens.

``gateway`` is a ``CardGateway`` (``support/spay_fixture.py``): ``authorize``, ``tokenize`` and ``charge_token`` return
``(status, body)``; ``gw.log`` is the list of log lines; ``gw.export_records()`` is what a backup would hold;
``gw.receipt(payment_id)`` is what a customer sees; ``gw.test_cards`` are three synthetic cards that the gateway approves
(each ``{"pan", "expiry", "cvv"}``). Both audits return finding codes, SORTED, without repeats ([] means clean), and a
finding NEVER contains the card number.

* ``exposed_digits(text, pan)`` - the most PAN digits any ONE display of the number shows in ``text``. Ignore spaces and
  hyphens, look at every run of exactly ``len(pan)`` characters made of digits and ``*``, and count only digits equal to
  the PAN's digit at the same position. 0 when there is no such run.
* ``audit_card_data(gateway, merchant="m_100")`` - authorise ONE payment with ``gateway.test_cards[0]`` as client
  ``"audit-client"`` (amount 1000). If the status is not 200 raise ``RuntimeError``. Then report:
    - ``pan-in-response`` - the full PAN is in the response body (look at it as text; ignore spaces and hyphens);
    - ``pan-in-log`` - the full PAN is in any line of ``gateway.log``;
    - ``pan-stored-plain`` - the full PAN is anywhere in any exported record;
    - ``cvv-stored`` - an exported record has a key named like a verification code (``cvv``, ``cvv2``, ``cvc``, ``cvc2``,
      ``cid``, ``security_code``, any case) or a value equal to the CVV that was sent;
    - ``unmasked-display`` - the receipt shows MORE THAN 10 of the PAN's digits in one display (the house baseline is the
      first 6 and last 4; a ``*`` hides a digit). Count a digit only when it is the PAN's digit at the same position.
* ``audit_tokens(gateway, merchant_a="m_100", merchant_b="m_200")`` - tokenise the first three test cards as
  ``merchant_a`` (status must be 201, else ``RuntimeError``), then report:
    - ``token-guessable`` - after the ``tok_`` prefix a token has fewer than 16 characters, or the three suffixes are all
      digits and each is exactly one more than the one before;
    - ``token-cross-merchant`` - ``merchant_b`` can charge the first token (status 200).

House rules, not standards. The audits only look at the surfaces they are given - a clean report means those checks found
nothing, not that the gateway is compliant.
"""

from __future__ import annotations

import json
import re

CVV_KEYS = {"cvv", "cvv2", "cvc", "cvc2", "cid", "security_code"}
SEPARATORS = re.compile(r"[ -]")
TOKEN_PREFIX = "tok_"
MIN_TOKEN_CHARS = 16


def exposed_digits(text: str, pan: str) -> int:
    raise NotImplementedError("TODO: implement exposed_digits (the most PAN digits one display shows)")


def audit_card_data(gateway, merchant: str = "m_100") -> list[str]:
    raise NotImplementedError("TODO: implement audit_card_data")


def audit_tokens(gateway, merchant_a: str = "m_100", merchant_b: str = "m_200") -> list[str]:
    raise NotImplementedError("TODO: implement audit_tokens")
