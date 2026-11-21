"""SOLUTION - spot card testing in authorisation events, and probe for a velocity limit."""

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
    if window_s <= 0 or min_attempts < 1:
        raise ValueError("window_s must be positive and min_attempts at least 1")
    by_client: dict[str, list[dict]] = {}
    for event in events:
        by_client.setdefault(event["client"], []).append(event)
    suspects = []
    for client, items in by_client.items():
        items.sort(key=lambda e: e["t"])
        for i, first in enumerate(items):
            window = [e for e in items[i:] if e["t"] < first["t"] + window_s]
            cards = len({e["card"] for e in window})
            declines = sum(1 for e in window if e["outcome"] == "declined")
            if len(window) >= min_attempts and cards >= min_cards and declines / len(window) >= min_decline_ratio:
                suspects.append(Suspect(client, first["t"], len(window), cards, declines))
                break
    return sorted(suspects, key=lambda s: s.client)


def probe_velocity_limit(gateway, client: str = "probe", max_attempts: int = 30):
    for attempt in range(1, max_attempts + 1):
        pan = str(4 * 10**15 + attempt)
        status, _ = gateway.authorize("m_100", client, pan, "1230", "000", 100)
        if status == 429:
            return attempt
        if status != 402:
            raise RuntimeError(f"unexpected status {status}: a probe card must be declined")
    return None
