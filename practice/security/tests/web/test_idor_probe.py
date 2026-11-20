import pytest
import requests
from sandpay_vuln import make_app, serve
from web.idor_probe import Leak, list_own_ids, two_account_probe

pytestmark = pytest.mark.exercise


def token(base, email, pw):
    r = requests.post(base + "/api/login", json={"email": email, "password": pw}, timeout=5)
    assert r.status_code == 200
    return r.json()["token"]


def accounts(base):
    return (token(base, "alice@shop-a.example", "alice-pass-1"), token(base, "bob@shop-b.example", "bob-pass-2"),
            token(base, "ops@sandpay.example", "ops-pass-3"))


def test_lists_only_the_callers_own_payments():
    with serve(make_app()) as base:
        alice, bob, _ = accounts(base)
        assert list_own_ids(base, alice) == ["pay_1001", "pay_1002", "pay_1003"]
        assert list_own_ids(base, bob) == ["pay_2001", "pay_2002"]
        with pytest.raises(RuntimeError):
            list_own_ids(base, "not-a-token")


def test_finds_every_cross_account_read_in_both_directions():
    with serve(make_app()) as base:
        alice, bob, _ = accounts(base)
        a_to_b = two_account_probe(base, alice, bob)
        b_to_a = two_account_probe(base, bob, alice)
    assert [leak.object_id for leak in a_to_b] == ["pay_2001", "pay_2002"]
    assert [leak.object_id for leak in b_to_a] == ["pay_1001", "pay_1002", "pay_1003"]
    assert a_to_b[0] == Leak("pay_2001", 200, "m_200",
                             ("amount_minor", "card_last4", "currency", "id", "merchant_id", "status"))


def test_reports_nothing_once_idor_is_fixed():
    with serve(make_app({"idor"})) as base:
        alice, bob, _ = accounts(base)
        assert two_account_probe(base, alice, bob) == []
        assert two_account_probe(base, bob, alice) == []


def test_refuses_an_account_with_no_objects_of_its_own():
    # ops is an admin with no merchant, so it owns no payments: no control, no probe
    with serve(make_app()) as base:
        alice, _, ops = accounts(base)
        with pytest.raises(ValueError):
            two_account_probe(base, ops, alice)


def test_refuses_two_sessions_of_the_same_account():
    with serve(make_app()) as base:
        alice, _, _ = accounts(base)
        alice_again = token(base, "alice@shop-a.example", "alice-pass-1")
        with pytest.raises(ValueError):
            two_account_probe(base, alice, alice_again)
