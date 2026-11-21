"""Shared pieces for the payment security lesson (Track L, payments-security-testing).

``CardGateway`` is a tiny, in-process model of a SandPay card gateway. The practice portal in ``sandpay_vuln.py`` has no
card endpoints, so this fixture holds the card-data flaws the lesson needs. It opens no socket and sends nothing.

**No real card number appears anywhere in this repository.** Test numbers are built when the code runs: a prefix, some
digits from a seeded generator and a Luhn check digit (``make_test_pan``). They are not issued to anyone, and no
output in the lesson ever prints one in full.

Each flaw has an id. ``CardGateway(fixed={...})`` fixes those flaws, exactly like ``make_app(fixed=...)``:

| flaw id              | rule that is not enforced                                                             |
| -------------------- | ------------------------------------------------------------------------------------- |
| ``pan-in-response``  | an API response never returns the full PAN (brand and last four only)                 |
| ``pan-in-log``       | the full PAN is never written to a log line                                           |
| ``pan-stored-plain`` | a stored record holds no readable PAN (a token, the first six and last four at most)  |
| ``cvv-stored``       | the card verification code is never stored after authorisation                        |
| ``unmasked-display`` | a receipt shows a masked PAN (at most the first six and last four digits)             |
| ``token-guessable``  | a token is random, long and not sequential                                            |
| ``token-cross-merchant`` | a token only works for the merchant that created it                               |
| ``no-velocity``      | a client that keeps failing authorisations is stopped (HTTP 429)                      |

``authorize`` / ``tokenize`` / ``charge_token`` return ``(status, body)`` like an HTTP handler would. The gateway knows
a few seeded test cards (``gw.test_cards``); anything else is declined with the same generic error, so a card tester
learns nothing from the message.
"""

from __future__ import annotations

import itertools
import json
import random
import secrets

FLAWS = (
    "pan-in-response", "pan-in-log", "pan-stored-plain", "cvv-stored", "unmasked-display",
    "token-guessable", "token-cross-merchant", "no-velocity",
)
VELOCITY_LIMIT = 5  # declines from one client before it is stopped, when no-velocity is fixed


def luhn_check_digit(partial: str) -> str:
    """The digit that makes ``partial + digit`` pass the Luhn check (used only to build synthetic test numbers)."""
    total = 0
    for index, ch in enumerate(reversed(partial)):
        d = int(ch)
        if index % 2 == 0:  # these positions are doubled once the check digit is appended
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def make_test_pan(prefix: str = "4", length: int = 16, seed: int = 1) -> str:
    """A synthetic, Luhn-valid test number of ``length`` digits starting with ``prefix``. Deterministic for a seed."""
    rng = random.Random(f"{prefix}/{length}/{seed}")
    body = prefix + "".join(str(rng.randrange(10)) for _ in range(length - 1 - len(prefix)))
    return body + luhn_check_digit(body)


def break_luhn(pan: str) -> str:
    """The same number with its last digit changed, so it fails the Luhn check."""
    return pan[:-1] + str((int(pan[-1]) + 1) % 10)


class CardGateway:
    def __init__(self, fixed=()):
        unknown = set(fixed) - set(FLAWS)
        if unknown:
            raise ValueError(f"unknown flaw ids: {sorted(unknown)}; known: {FLAWS}")
        self.fixed = frozenset(fixed)
        self.log: list[str] = []
        self._records: list[dict] = []
        self._vault: dict[str, str] = {}  # payment id -> PAN, internal to the processor; never exported
        self._tokens: dict[str, dict] = {}
        self._declines: dict[str, int] = {}
        self._token_counter = itertools.count(1)
        self.test_cards = [
            {"pan": make_test_pan("4", 16, seed), "expiry": "1230", "cvv": f"{(seed * 137) % 900 + 100}"}
            for seed in (1, 2, 3)
        ]

    # --- authorisation ---------------------------------------------------------------------------------------
    def authorize(self, merchant: str, client: str, pan: str, expiry: str, cvv: str, amount_minor: int):
        self.log.append(self._log_line(f"authorize merchant={merchant} client={client}", pan))
        if "no-velocity" in self.fixed and self._declines.get(client, 0) >= VELOCITY_LIMIT:
            return 429, {"error": "too_many_declines"}
        card = next((c for c in self.test_cards if c["pan"] == pan and c["expiry"] == expiry and c["cvv"] == cvv), None)
        if card is None:
            self._declines[client] = self._declines.get(client, 0) + 1
            return 402, {"error": "card_declined"}
        payment_id = f"pay_{len(self._records) + 1}"
        record = {"payment_id": payment_id, "merchant": merchant, "amount_minor": amount_minor,
                  "last4": pan[-4:], "first6": pan[:6]}
        if "pan-stored-plain" not in self.fixed:
            record["pan"] = pan
        if "cvv-stored" not in self.fixed:
            record["cvv"] = cvv
        self._records.append(record)
        self._vault[payment_id] = pan
        body = {"payment_id": payment_id, "status": "approved", "amount_minor": amount_minor,
                "card": {"brand": "synthetic", "last4": pan[-4:]}}
        if "pan-in-response" not in self.fixed:
            body["card"] = {"brand": "synthetic", "number": pan, "last4": pan[-4:]}
        return 200, body

    def _log_line(self, text: str, pan: str) -> str:
        if "pan-in-log" not in self.fixed:
            return f"{text} card={pan}"
        return f"{text} card={pan[:6]}{'*' * (len(pan) - 10)}{pan[-4:]}"

    # --- what a stored record and a receipt show ----------------------------------------------------------------
    def export_records(self) -> list[dict]:
        """What a backup, a report or a database dump would contain."""
        return [dict(r) for r in self._records]

    def receipt(self, payment_id: str) -> str:
        record = next((r for r in self._records if r["payment_id"] == payment_id), None)
        if record is None:
            return "receipt not found"
        if "unmasked-display" not in self.fixed:
            shown = self._vault[payment_id]
        else:
            shown = f"{record['first6']}{'*' * 6}{record['last4']}"
        return f"SandPay receipt {payment_id}: {record['amount_minor']} minor units, card {shown}"

    # --- tokens ------------------------------------------------------------------------------------------------
    def tokenize(self, merchant: str, pan: str, expiry: str):
        self.log.append(self._log_line(f"tokenize merchant={merchant}", pan))
        if "token-guessable" in self.fixed:
            token = "tok_" + secrets.token_hex(12)
        else:
            token = f"tok_{next(self._token_counter):04d}"
        self._tokens[token] = {"merchant": merchant, "pan": pan, "expiry": expiry}
        return 201, {"token": token, "last4": pan[-4:]}

    def charge_token(self, merchant: str, token: str, amount_minor: int):
        entry = self._tokens.get(token)
        if entry is None:
            return 404, {"error": "token_not_found"}
        if "token-cross-merchant" in self.fixed and entry["merchant"] != merchant:
            return 403, {"error": "token_not_yours"}
        return 200, {"status": "approved", "amount_minor": amount_minor, "card": {"last4": entry["pan"][-4:]}}


def flat_text(body) -> str:
    """A response body as one string, the way a scanner would look at it."""
    return json.dumps(body, sort_keys=True)


# --- synthetic authorisation events for the card-testing detector ---------------------------------------------
def shopper_events(client: str, start: int, count: int, step: int = 40, cards: int = 2) -> list[dict]:
    """A real customer: a few attempts, one or two cards, almost all approved, spread out."""
    return [
        {"t": start + i * step, "client": client, "card": f"c_{client}_{i % cards}", "outcome": "approved" if i % 7 else "declined",
         "amount_minor": 2500 + 100 * i}
        for i in range(count)
    ]


def tester_events(client: str, start: int, count: int, step: int = 2, small: int = 100) -> list[dict]:
    """A card tester: many different cards in a short time, mostly declined, small amounts."""
    return [
        {"t": start + i * step, "client": client, "card": f"c_{client}_{i}", "outcome": "approved" if i % 9 == 8 else "declined",
         "amount_minor": small}
        for i in range(count)
    ]


def busy_merchant_events(client: str, start: int, count: int, step: int = 1) -> list[dict]:
    """A heavy but legitimate client: many attempts in a short time, one stored card per customer, all approved."""
    return [
        {"t": start + i * step, "client": client, "card": f"c_{client}_{i % 3}", "outcome": "approved", "amount_minor": 4000}
        for i in range(count)
    ]
