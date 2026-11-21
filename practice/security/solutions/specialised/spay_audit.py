"""SOLUTION - audit a card gateway for card-data leaks and weak tokens."""

from __future__ import annotations

import json
import re

CVV_KEYS = {"cvv", "cvv2", "cvc", "cvc2", "cid", "security_code"}
SEPARATORS = re.compile(r"[ -]")
TOKEN_PREFIX = "tok_"
MIN_TOKEN_CHARS = 16


def _plain(text: str) -> str:
    return SEPARATORS.sub("", text)


def exposed_digits(text: str, pan: str) -> int:
    """The most PAN digits one display of the number shows in ``text`` (a ``*`` hides a digit)."""
    best = 0
    for token in re.findall(r"[0-9*]{%d}" % len(pan), _plain(text)):
        best = max(best, sum(1 for shown, real in zip(token, pan) if shown == real))
    return best


def audit_card_data(gateway, merchant: str = "m_100") -> list[str]:
    card = gateway.test_cards[0]
    pan, cvv = card["pan"], card["cvv"]
    status, body = gateway.authorize(merchant, "audit-client", pan, card["expiry"], cvv, 1000)
    if status != 200:
        raise RuntimeError("the gateway declined the audit card")
    found = set()
    if pan in _plain(json.dumps(body)):
        found.add("pan-in-response")
    if any(pan in _plain(line) for line in gateway.log):
        found.add("pan-in-log")
    records = gateway.export_records()
    if any(pan in _plain(json.dumps(record)) for record in records):
        found.add("pan-stored-plain")
    if any(key.lower() in CVV_KEYS or value == cvv for record in records for key, value in record.items()):
        found.add("cvv-stored")
    if exposed_digits(gateway.receipt(body["payment_id"]), pan) > 10:
        found.add("unmasked-display")
    return sorted(found)


def audit_tokens(gateway, merchant_a: str = "m_100", merchant_b: str = "m_200") -> list[str]:
    tokens = []
    for card in gateway.test_cards[:3]:
        status, body = gateway.tokenize(merchant_a, card["pan"], card["expiry"])
        if status != 201:
            raise RuntimeError("the gateway refused to tokenise the audit card")
        tokens.append(body["token"])
    found = set()
    suffixes = [t[len(TOKEN_PREFIX):] for t in tokens]
    numbers = [int(s) for s in suffixes if s.isdigit()]
    sequential = len(numbers) == len(suffixes) and all(b - a == 1 for a, b in zip(numbers, numbers[1:]))
    if sequential or any(len(s) < MIN_TOKEN_CHARS for s in suffixes):
        found.add("token-guessable")
    status, _ = gateway.charge_token(merchant_b, tokens[0], 100)
    if status == 200:
        found.add("token-cross-merchant")
    return sorted(found)
