import pytest
import requests
from idor_fixture import serve_invoices
from sandpay_vuln import make_app, serve
from web.idor_oracle import Reply, check_existence_oracle, classify, normalise

pytestmark = pytest.mark.exercise

OK = Reply(200, '{"id": "inv_501"}')


def test_normalise_replaces_every_occurrence():
    assert normalise('{"error": "invoice inv_9 not found (inv_9)"}', "inv_9") == '{"error": "invoice {id} not found ({id})"}'


@pytest.mark.parametrize("foreign, missing, verdict", [
    (Reply(200, "{}"), Reply(404, "x"), "readable"),
    (Reply(403, "forbidden"), Reply(404, "not found"), "oracle"),
    (Reply(404, "invoice inv_601 is not yours"), Reply(404, "invoice inv_999 not found"), "oracle"),
    (Reply(404, "invoice inv_601 not found"), Reply(404, "invoice inv_999 not found"), "indistinguishable"),
])
def test_classify(foreign, missing, verdict):
    assert classify(OK, foreign, missing, "inv_601", "inv_999") == verdict


def test_a_failed_control_proves_nothing():
    with pytest.raises(ValueError):
        classify(Reply(401, "auth"), Reply(404, "a"), Reply(404, "a"), "inv_601", "inv_999")


@pytest.mark.parametrize("mode, verdict", [("uniform", "indistinguishable"), ("status", "oracle"),
                                           ("message", "oracle"), ("leaky", "readable")])
def test_invoices_api_in_each_mode(mode, verdict):
    with serve_invoices(mode) as base:
        got = check_existence_oracle(base, "/invoices/{id}", "tok-shop-a", "inv_501", "inv_601", "inv_999")
    assert got == verdict


def test_the_portal_before_and_after_the_idor_fix():
    for fixed, verdict in ((set(), "readable"), ({"idor"}, "indistinguishable")):
        with serve(make_app(fixed)) as base:
            r = requests.post(base + "/api/login", json={"email": "alice@shop-a.example", "password": "alice-pass-1"},
                              timeout=5)
            got = check_existence_oracle(base, "/api/payments/{id}", r.json()["token"], "pay_1001", "pay_2001",
                                         "pay_9999")
        assert got == verdict, fixed
