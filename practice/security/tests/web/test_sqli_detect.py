import json
import re
import sqlite3

import pytest
import requests
from sandpay_vuln import FLAWS, make_app, serve
from web.sqli_detect import (
    Finding,
    InconclusiveError,
    boolean_pairs,
    fingerprint,
    portal_sender,
    probe_boolean,
)

pytestmark = pytest.mark.exercise


# ---- in-memory fakes: the same table queried unsafely (concatenation) and safely (binding) ----------------
def make_db():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE p (id TEXT, status TEXT, amount INTEGER)")
    con.executemany("INSERT INTO p VALUES (?, ?, ?)",
                    [("pay_1", "captured", 2500), ("pay_2", "refunded", 990), ("pay_3", "captured", 4999)])
    return con


def answer(run):
    try:
        return 200, json.dumps({"data": [r[0] for r in run()]})
    except sqlite3.Error:
        return 500, json.dumps({"error": "internal error"})


def string_unsafe(con):
    return lambda v: answer(lambda: con.execute(f"SELECT id FROM p WHERE status = '{v}' ORDER BY id").fetchall())


def string_safe(con):
    return lambda v: answer(lambda: con.execute("SELECT id FROM p WHERE status = ? ORDER BY id", (v,)).fetchall())


def numeric_unsafe(con):
    return lambda v: answer(lambda: con.execute(f"SELECT id FROM p WHERE amount = {v} ORDER BY id").fetchall())


class Spy:
    def __init__(self, send):
        self.send, self.values = send, []

    def __call__(self, value):
        self.values.append(value)
        return self.send(value)


# ---- the pieces ------------------------------------------------------------------------------------
def test_string_pair_closes_the_quote_and_differs_only_in_the_condition():
    pairs = boolean_pairs("captured")
    assert pairs[0] == ("string", "captured' AND '1'='1", "captured' AND '1'='2")
    assert [c for c, _, _ in pairs] == ["string"]


def test_numeric_pair_only_for_digits():
    assert ("numeric", "2500 AND 1=1", "2500 AND 1=2") in boolean_pairs("2500")
    assert boolean_pairs("2500")[0][0] == "string"  # string context is still tried first


def test_fingerprint_ignores_volatile_keys_and_key_order():
    a = fingerprint(500, json.dumps({"error": "internal error", "reference": "ec57c95a"}))
    b = fingerprint(500, json.dumps({"reference": "0b11d2f4", "error": "internal error"}))
    assert a == b
    nested = fingerprint(200, json.dumps({"data": [{"id": 1, "request_id": "x"}]}))
    assert nested == fingerprint(200, json.dumps({"data": [{"id": 1, "request_id": "y"}]}))


def test_fingerprint_keeps_status_and_real_differences():
    assert fingerprint(200, '{"data": []}') != fingerprint(404, '{"data": []}')
    assert fingerprint(200, '{"data": ["pay_1"]}') != fingerprint(200, '{"data": []}')
    assert fingerprint(200, "<p>hi</p>") == (200, "<p>hi</p>")  # not JSON: compared as text


# ---- the probe against fakes ---------------------------------------------------------------------------
def test_flags_string_concatenation():
    f = probe_boolean(string_unsafe(make_db()), "status", "captured")
    assert isinstance(f, Finding)
    assert (f.parameter, f.technique, f.context) == ("status", "boolean", "string")
    assert (f.true_value, f.false_value) == ("captured' AND '1'='1", "captured' AND '1'='2")
    assert len(f.evidence) == 3 and "same as baseline" in f.evidence[1] and "different" in f.evidence[2]


def test_quiet_on_bound_parameters():
    assert probe_boolean(string_safe(make_db()), "status", "captured") is None


def test_flags_numeric_context():
    f = probe_boolean(numeric_unsafe(make_db()), "amount", "2500")
    assert f is not None and f.context == "numeric"


def test_reflected_input_is_not_injection():
    # A page that echoes the value changes with every input, so "true" never equals the baseline.
    echo = lambda v: (200, json.dumps({"query": v, "data": []}))  # noqa: E731
    assert probe_boolean(echo, "q", "captured") is None


def test_unstable_page_is_inconclusive_not_a_finding():
    counter = iter(range(1000))
    noisy = lambda v: (200, json.dumps({"served": next(counter)}))  # noqa: E731
    with pytest.raises(InconclusiveError):
        probe_boolean(noisy, "status", "captured")


def test_probe_is_read_only_and_small():
    spy = Spy(string_unsafe(make_db()))
    probe_boolean(spy, "status", "captured")
    assert len(spy.values) <= 8
    for v in spy.values:
        assert ";" not in v and "--" not in v
        assert not re.search(r"\b(DROP|DELETE|UPDATE|INSERT|SLEEP|UNION)\b", v, re.I)


# ---- the probe against the practice portal --------------------------------------------------------
def alice_token(base):
    r = requests.post(base + "/api/login", json={"email": "alice@shop-a.example", "password": "alice-pass-1"}, timeout=5)
    return r.json()["token"]


def probe_portal(app):
    with serve(app) as base:
        return probe_boolean(portal_sender(base, alice_token(base)), "status", "captured")


def test_finds_the_portal_flaw():
    f = probe_portal(make_app())
    assert f is not None and f.context == "string"


def test_finds_it_blind_when_errors_are_hidden():
    # verbose-errors fixed: a quote now gives a generic 500, but the true/false pair still differs.
    assert probe_portal(make_app({"verbose-errors"})) is not None


def test_quiet_when_the_query_is_fixed():
    assert probe_portal(make_app({"sqli"})) is None


def test_quiet_on_the_fully_fixed_portal():
    assert probe_portal(make_app(FLAWS)) is None
