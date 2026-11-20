import pytest
from api.apitop_inventory import matches_template, probe_paths, route_exists, undocumented
from apitop_fixture import CANDIDATES, DOCUMENTED
from sandpay_vuln import make_app, serve

pytestmark = pytest.mark.exercise


def test_a_missing_route_is_the_portals_own_404_and_nothing_else_is():
    assert route_exists(404, {"error": "not found"}) is False
    assert route_exists(404, {"error": "file not found: public"}) is True  # a handler answered
    for status in (200, 401, 403, 405, 500):
        assert route_exists(status, None) is True


@pytest.mark.parametrize("path, template, expected", [
    ("/api/payments/pay_1001", "/api/payments/{id}", True),
    ("/api/payments", "/api/payments/{id}", False),
    ("/api/payments/pay_1001/refunds", "/api/payments/{id}", False),
    ("/api/payments", "/api/payments", True),
    ("/api/notes", "/api/payments", False),
    ("/api/merchants/m_100", "/api/merchants/{id}", True),
])
def test_template_matching(path, template, expected):
    assert matches_template(path, template) is expected


def test_probe_paths_keeps_only_routes_that_exist():
    with serve(make_app()) as base:
        found = probe_paths(base, CANDIDATES)
    assert found["/health"] == 200
    assert found["/api/me"] == 401                     # exists, needs a token
    assert found["/api/payments/pay_1001"] == 401      # a prefix route, still a handler
    assert found["/files"] == 404                      # a 404 from the handler, not from the router
    assert found["/internal/admin"] == 200
    assert found["/boom"] == 500
    for guess in ("/swagger.json", "/openapi.json", "/api-docs", "/api/v1/payments", "/admin", "/metrics"):
        assert guess not in found
    assert list(found) == [p for p in CANDIDATES if p in found]  # candidate order is kept


def test_probe_paths_does_not_follow_redirects():
    with serve(make_app()) as base:
        assert probe_paths(base, ["/login?next=/settings"]) == {"/login?next=/settings": 302}


def test_the_shadow_endpoints_of_the_portal():
    with serve(make_app()) as base:
        observed = probe_paths(base, CANDIDATES)
    assert undocumented(observed, DOCUMENTED) == ["/boom", "/internal/admin"]


def test_documenting_a_route_removes_it_from_the_findings():
    observed = {"/boom": 500, "/internal/admin": 200, "/health": 200}
    assert undocumented(observed, ["/health"]) == ["/boom", "/internal/admin"]
    assert undocumented(observed, ["/health", "/internal/admin"]) == ["/boom"]
    assert undocumented({}, DOCUMENTED) == []


def test_the_probe_finds_the_same_shadow_routes_on_a_fully_fixed_portal():
    # the flaw-fixes do not touch inventory: only the documentation or the route itself can change this
    fixed = {"idor", "jwt-none", "no-rate-limit", "mass-assignment", "data-exposure", "ssrf", "verbose-errors",
             "missing-headers"}
    with serve(make_app(fixed)) as base:
        observed = probe_paths(base, CANDIDATES)
    assert undocumented(observed, DOCUMENTED) == ["/boom", "/internal/admin"]
