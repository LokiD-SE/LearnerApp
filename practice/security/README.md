# Security testing practice project (Track L)

Security tests in Python (pytest + requests) against **`support/sandpay_vuln.py`, a deliberately vulnerable
SandPay merchant portal**. It binds to `127.0.0.1` only and refuses any other address. Never deploy it or expose
it, and test only systems you own or have written permission to test.

Each of its 17 flaws (IDOR, SQL injection, XSS, CSRF, SSRF, JWT `alg: none`, ...) has an id, and
`make_app(fixed={...})` builds the same portal with those flaws fixed. Exercises use both: a good security test
finds the flaw **and** stays quiet once it is fixed. The flaw table is at the top of `support/sandpay_vuln.py`.

- `exercises/<topic>/` - the files you change; `solutions/<topic>/` - reference solutions.
- `tests/<topic>/test_*.py` - the tests that check your work; `pytestmark = pytest.mark.exercise`.
- `tests/support/` checks the portal itself: every flaw is exploitable, and closed when fixed.

```bash
cd practice/security
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/support
.venv/bin/python support/sandpay_vuln.py --port 8765            # explore it (add --fix sqli, --fix-all)
SEC_TARGET=solutions .venv/bin/python -m pytest                  # every test against the solutions
.venv/bin/python scripts/verify.py                               # what CI runs
```

"Fixed" means that flaw's test passes, not that the portal meets a standard: the fixed headers still send HSTS
over plain HTTP (RFC 6797 section 7.2 says not to) and the CSP lacks `object-src` and `base-uri` (ASVS 5.0.0
3.4.3) - the WSTG/ASVS lesson uses both as teaching points.

Two behaviours to expect: `/settings` and `/settings/email` need the cookie session (`sid`), not a bearer
token; and once `weak-session` is fixed the cookie is `Secure`, so clients such as `requests` will not send it
back over plain `http://` - send the `Cookie` header yourself when testing the fixed portal.

Seeded accounts (synthetic): `alice@shop-a.example` / `alice-pass-1`, `bob@shop-b.example` / `bob-pass-2`,
`ops@sandpay.example` / `ops-pass-3` (admin).
