"""EXERCISE - spot card testing in authorisation events, and probe for a velocity limit.

OWASP's Automated Threats handbook calls it OAT-001 Carding: "multiple payment authorisation attempts to verify the
validity of bulk stolen payment card data". From the merchant's side it looks like one client trying many different
cards in a short time, mostly declined, usually for small amounts.

An event is a dict: ``{"t": seconds, "client": str, "card": str (an opaque card fingerprint), "outcome": "approved" |
"declined", "amount_minor": int}``.

* ``detect_card_testing(events, window_s=60, min_attempts=10, min_cards=5, min_decline_ratio=0.6)`` - for each client, in
  time order, look at the window that STARTS at each of its events and holds the events with ``t`` from that start up
  to, but not including, ``start + window_s``. The client is a suspect at the FIRST start where the window has at least
  ``min_attempts`` events, at least ``min_cards`` different cards, and ``declines / events >= min_decline_ratio``. Return
  one ``Suspect(client, first_t, attempts, cards, declines)`` per suspect client (the numbers are those of that first
  qualifying window), sorted by client. ``events`` may be in any order. Raise ``ValueError`` when ``window_s <= 0`` or
  ``min_attempts < 1``. Never modify ``events``.
* ``probe_velocity_limit(gateway, client="probe", max_attempts=30)`` - send authorisations that must be declined (a
  synthetic 16-digit number that changes on each attempt, expiry ``"1230"``, CVV ``"000"``, merchant ``"m_100"``, amount
  100). Return the 1-based attempt number at which the gateway first answers 429, or ``None`` if it never does within
  ``max_attempts``. If a probe card is ever approved, raise ``RuntimeError``; any status other than 402 or 429 is also
  an error. Only ever use it on the practice ``CardGateway``.

House rules, not standards. A window rule catches a fast tester and misses a slow one - the lesson shows both.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Suspect:
    client: str
    first_t: int
    attempts: int
    cards: int
    declines: int


def detect_card_testing(events, window_s: int = 60, min_attempts: int = 10, min_cards: int = 5,
                        min_decline_ratio: float = 0.6) -> list[Suspect]:
    raise NotImplementedError("TODO: implement detect_card_testing")


def probe_velocity_limit(gateway, client: str = "probe", max_attempts: int = 30):
    raise NotImplementedError("TODO: implement probe_velocity_limit")
