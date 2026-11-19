import pytest
from foundations.fund_scope import Decision, GuardedClient, OutOfScope, Scope, check, parse_scope

pytestmark = pytest.mark.exercise

DOC = {"hosts": ["127.0.0.1", "localhost"], "ports": [8765], "excluded_paths": ["/internal/"],
       "methods": ["GET", "POST"]}


@pytest.fixture
def scope():
    return parse_scope(DOC)


def test_parse_scope_normalises_and_defaults():
    s = parse_scope({"hosts": ["LocalHost"]})
    assert s.hosts == frozenset({"localhost"})
    assert s.ports == frozenset()
    assert s.methods == frozenset({"GET", "HEAD", "OPTIONS"})
    assert parse_scope({"hosts": ["127.0.0.1"], "methods": ["post"]}).methods == frozenset({"POST"})


@pytest.mark.parametrize("doc", [{}, {"hosts": []}, {"hosts": ["127.0.0.1"], "ports": [0]},
                                 {"hosts": ["127.0.0.1"], "ports": [70000]}])
def test_parse_scope_rejects_bad_documents(doc):
    with pytest.raises(ValueError):
        parse_scope(doc)


def test_in_scope_request_is_allowed(scope):
    assert check(scope, "http://127.0.0.1:8765/api/payments?status=captured") == Decision(True, "in scope")
    assert check(scope, "http://localhost:8765/search", "post").allowed


@pytest.mark.parametrize("url,method,word", [
    ("ftp://127.0.0.1:8765/", "GET", "scheme"),
    ("http://127.0.0.1@evil.example:8765/", "GET", "user info"),
    ("http://evil.example:8765/", "GET", "host"),
    ("http://127.0.0.1.evil.example:8765/", "GET", "host"),
    ("http://127.0.0.1:9999/", "GET", "port"),
    ("http://127.0.0.1/", "GET", "port"),
    ("http://127.0.0.1:8765/internal/admin", "GET", "excluded"),
    ("http://127.0.0.1:8765/%69nternal/admin", "GET", "excluded"),
    ("http://127.0.0.1:8765/api/profile", "PATCH", "method"),
])
def test_out_of_scope_requests_are_refused_with_a_reason(scope, url, method, word):
    d = check(scope, url, method)
    assert not d.allowed
    assert word in d.reason


def test_listed_host_that_is_not_loopback_is_still_refused():
    s = parse_scope({"hosts": ["portal.sandpay.example"]})
    d = check(s, "https://portal.sandpay.example/")
    assert not d.allowed and "loopback" in d.reason


def test_guarded_client_never_sends_a_refused_request(scope):
    sent = []
    client = GuardedClient(scope, send=lambda method, url, **kw: sent.append((method, url)) or "response")
    assert client.request("GET", "http://127.0.0.1:8765/health") == "response"
    with pytest.raises(OutOfScope):
        client.request("GET", "http://evil.example/")
    assert sent == [("GET", "http://127.0.0.1:8765/health")]
    assert [d.allowed for _, _, d in client.log] == [True, False]
