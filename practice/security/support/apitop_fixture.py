"""Shared pieces for the API Security Top 10 lesson (Track L, owasp-api-security-top-10).

* ``tokens(base_url)`` signs in the three seeded SandPay accounts and returns their bearer tokens.
* ``DOCUMENTED`` is the published inventory of the practice portal - what its (imaginary) OpenAPI document and
  sitemap say exists. It deliberately leaves out two routes the portal really serves, so the inventory
  exercise has something to find.
* ``CANDIDATES`` is the reconnaissance wordlist: documented routes, guessed documentation paths, versioned
  paths and common debug paths. Everything is requested on the loopback practice portal only.
"""

from __future__ import annotations

import requests

ACCOUNTS = {
    "alice": ("alice@shop-a.example", "alice-pass-1"),
    "bob": ("bob@shop-b.example", "bob-pass-2"),
    "ops": ("ops@sandpay.example", "ops-pass-3"),
}

# Method-free on purpose: the inventory exercise asks "does this path exist?", not "which verbs work?".
DOCUMENTED = (
    "/api/login",
    "/api/me",
    "/api/profile",
    "/api/payments",
    "/api/payments/{id}",
    "/api/merchants/{id}",
    "/api/notes",
    "/api/webhooks/test",
    "/health",
    "/login",
    "/search",
    "/notes",
    "/settings",
    "/files",
)

CANDIDATES = (
    "/api/login",
    "/api/me",
    "/api/profile",
    "/api/payments",
    "/api/payments/pay_1001",
    "/api/merchants/m_100",
    "/api/notes",
    "/api/webhooks/test",
    "/health",
    "/login",
    "/search",
    "/notes",
    "/settings",
    "/files",
    "/internal/admin",
    "/boom",
    "/api/v1/payments",
    "/api/v2/payments",
    "/swagger.json",
    "/openapi.json",
    "/api-docs",
    "/admin",
    "/debug",
    "/metrics",
    "/actuator/health",
)


def tokens(base_url: str) -> dict[str, str]:
    """Bearer tokens for alice (m_100), bob (m_200) and ops (admin), by short name."""
    out = {}
    for name, (email, password) in ACCOUNTS.items():
        resp = requests.post(base_url + "/api/login", json={"email": email, "password": password}, timeout=5)
        resp.raise_for_status()
        out[name] = resp.json()["token"]
    return out
