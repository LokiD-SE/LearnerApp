"""Checks exercises/specialised/scap_scope.py: the HTTP wrapper that enforces the rules of engagement."""

from types import SimpleNamespace

import pytest
import requests
from sandpay_vuln import make_app, serve
from scap_fixture import BudgetExhausted, OutOfScope, make_scope
from specialised.scap_scope import GuardedHttp

pytestmark = pytest.mark.exercise

BASE = "http://127.0.0.1:8765"


class FakeSession:
    """Records what would have been sent; nothing touches the network."""

    def __init__(self, status=200):
        self.calls = []
        self.status = status

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        return SimpleNamespace(status_code=self.status, headers={})


def guarded(**scope_changes):
    session = FakeSession()
    return GuardedHttp(make_scope(BASE, **scope_changes), session=session), session


def test_a_path_is_joined_onto_the_base_url_and_sent_once():
    http, session = guarded()
    resp = http.request("get", "/api/me")
    assert resp.status_code == 200
    assert [(m, u) for m, u, _ in session.calls] == [("GET", BASE + "/api/me")]


def test_an_absolute_url_of_the_target_is_allowed():
    http, session = guarded()
    http.request("GET", BASE + "/health")
    assert session.calls[0][1] == BASE + "/health"


def test_redirects_are_never_followed_and_the_caller_cannot_switch_that_on():
    http, session = guarded()
    http.request("GET", "/login", allow_redirects=True)
    assert session.calls[0][2]["allow_redirects"] is False


def test_a_timeout_is_always_set_and_a_callers_timeout_is_kept():
    http, session = guarded()
    http.request("GET", "/health")
    http.request("GET", "/health", timeout=1)
    assert session.calls[0][2]["timeout"] == 5
    assert session.calls[1][2]["timeout"] == 1


def test_the_log_records_method_path_and_status_but_never_the_query():
    http, _ = guarded()
    http.request("GET", "/api/payments?status=captured")
    http.request("post", "/api/login", json={"email": "x"})
    assert [(e.method, e.path, e.status) for e in http.log] == [
        ("GET", "/api/payments", 200),
        ("POST", "/api/login", 200),
    ]
    assert http.used == 2


@pytest.mark.parametrize("method, target", [
    ("GET", "http://localhost:8765/health"),  # a loopback name the scope does not name
    ("GET", "http://127.0.0.1:9999/health"),  # another port
    ("GET", "https://127.0.0.1:8765/health"),  # another scheme
    ("GET", "http://127.0.0.1:8765@evil.example/"),  # user info hides the real host
    ("GET", "http://evil.example/health"),
    ("DELETE", "/api/payments/pay_1001"),  # a method the engagement does not allow
    ("GET", "/internal/admin"),
    ("GET", "/%69nternal/admin"),  # percent-encoded
    ("GET", "/public/../internal/admin"),  # folded with ..
    ("GET", "/internal"),
])
def test_a_request_outside_the_rules_is_refused_before_it_is_sent(method, target):
    http, session = guarded()
    with pytest.raises(OutOfScope):
        http.request(method, target)
    assert session.calls == []
    assert http.used == 0
    assert len(http.refused) == 1
    assert http.refused[0][0] == method


def test_the_refusal_names_the_rule():
    http, _ = guarded()
    with pytest.raises(OutOfScope, match="excluded"):
        http.request("GET", "/internal/admin")
    with pytest.raises(OutOfScope, match="DELETE"):
        http.request("DELETE", "/api/me")


def test_the_budget_stops_the_next_request_and_nothing_is_sent_after_it():
    http, session = guarded(max_requests=3)
    for _ in range(3):
        http.request("GET", "/health")
    assert http.remaining == 0
    with pytest.raises(BudgetExhausted):
        http.request("GET", "/health")
    assert len(session.calls) == 3


def test_budget_exhausted_is_an_out_of_scope_error():
    assert issubclass(BudgetExhausted, OutOfScope)


def test_refused_requests_do_not_use_budget():
    http, session = guarded(max_requests=2)
    for _ in range(5):
        with pytest.raises(OutOfScope):
            http.request("GET", "/internal/admin")
    http.request("GET", "/health")
    http.request("GET", "/health")
    assert len(session.calls) == 2
    assert len(http.refused) == 5


def test_the_budget_is_checked_before_the_scope():
    http, _ = guarded(max_requests=1)
    http.request("GET", "/health")
    with pytest.raises(BudgetExhausted):
        http.request("GET", "/internal/admin")


def test_a_real_redirect_comes_back_as_data_not_as_a_second_request():
    with serve(make_app()) as base:
        http = GuardedHttp(make_scope(base))
        resp = http.request("GET", "/login", params={"next": "https://evil.example/"})
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://evil.example/"
        assert http.used == 1  # the redirect target was never contacted


def test_the_default_session_is_a_real_requests_session():
    http = GuardedHttp(make_scope(BASE))
    assert isinstance(http.session, requests.Session)
