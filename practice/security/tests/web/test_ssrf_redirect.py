import pytest
from sandpay_vuln import FLAWS, make_app, serve
from web.ssrf_redirect import (
    Finding,
    PAYLOADS,
    leaves_origin,
    portal_redirect_sender,
    probe_open_redirect,
    redirect_location,
)

pytestmark = pytest.mark.exercise

BASE = "https://portal.sandpay.example"


# ---- in-memory fakes: a redirect handler with a different check each ---------------------------------------
def redirecting(check):
    """A ``send`` for a handler that redirects to the value unless ``check`` rewrites it."""

    def send(value):
        return 302, {"Location": check(value), "Content-Length": "0"}

    return send


def no_check(value):
    return value


def prefix_check(value):  # "must start with /" - the classic half-fix
    return value if value.startswith("/") else "/settings"


def portal_check(value):  # the practice portal's own fix: starts with / but not //
    return value if value.startswith("/") and not value.startswith("//") and "@" not in value else "/settings"


def strict_check(value):  # one slash, no backslash, no control characters
    ok = value.startswith("/") and not value.startswith("//") and "\\" not in value and value.isprintable()
    return value if ok else "/settings"


def names(findings):
    return [f.payload for f in findings]


# ---- the pieces --------------------------------------------------------------------------------------
def test_redirect_location_reads_any_header_case():
    assert redirect_location(302, {"location": "/settings"}) == "/settings"
    assert redirect_location(307, {"LOCATION": "/x"}) == "/x"


def test_redirect_location_ignores_non_redirects():
    assert redirect_location(200, {"Location": "/settings"}) is None
    assert redirect_location(404, {}) is None
    assert redirect_location(302, {"Content-Length": "0"}) is None


@pytest.mark.parametrize("location", [
    "https://evil.example/",
    "//evil.example/",
    "/\\evil.example/",
    "https://portal.sandpay.example@evil.example/",
    "/\t/evil.example/",  # browsers drop the tab and read //evil.example/
    "http://portal.sandpay.example/",  # same host, other scheme: another origin
    "https://portal.sandpay.example:8443/",  # same host, other port: another origin
])
def test_these_locations_leave_the_origin(location):
    assert leaves_origin(location, BASE) is True


@pytest.mark.parametrize("location", [
    "/settings",
    "settings",
    "/settings?tab=email",
    "https://portal.sandpay.example/settings",
    "?next=/x",
])
def test_these_locations_stay_on_the_origin(location):
    assert leaves_origin(location, BASE) is False


# ---- the probe against fakes -----------------------------------------------------------------------------
def test_flags_an_unchecked_redirect_with_every_payload():
    findings = probe_open_redirect(redirecting(no_check), BASE)
    assert names(findings) == [name for name, _ in PAYLOADS]
    assert all(isinstance(f, Finding) for f in findings)
    first = findings[0]
    assert (first.payload, first.value, first.location) == ("absolute", "https://evil.example/", "https://evil.example/")


def test_a_prefix_check_still_lets_two_forms_through():
    assert names(probe_open_redirect(redirecting(prefix_check), BASE)) == ["protocol-relative", "backslash"]


def test_the_portal_style_check_still_lets_the_backslash_through():
    assert names(probe_open_redirect(redirecting(portal_check), BASE)) == ["backslash"]


def test_quiet_on_a_strict_check():
    assert probe_open_redirect(redirecting(strict_check), BASE) == []


def test_quiet_when_the_parameter_is_not_a_redirect():
    assert probe_open_redirect(lambda value: (200, {"Content-Type": "text/html"}), BASE) == []


def test_quiet_when_even_the_control_value_leaves_the_origin():
    # A handler that always redirects offsite is not a parameter bug and the payloads prove nothing.
    assert probe_open_redirect(lambda value: (302, {"Location": "https://other.example/"}), BASE) == []


def test_the_probe_sends_a_local_control_first_and_only_reads_headers():
    sent = []

    def spy(value):
        sent.append(value)
        return 302, {"Location": "/settings"}

    probe_open_redirect(spy, BASE)
    assert sent[0] == "/settings"
    assert len(sent) == 1 + len(PAYLOADS)


# ---- the probe against the practice portal -------------------------------------------------------------
def probe_portal(app):
    with serve(app) as base:
        return probe_open_redirect(portal_redirect_sender(base), base)


def test_finds_every_form_on_the_vulnerable_portal():
    assert names(probe_portal(make_app())) == ["absolute", "protocol-relative", "backslash", "userinfo"]


def test_fixing_the_flaw_closes_three_forms_but_not_the_backslash():
    # make_app({"open-redirect"}) rejects absolute and // values, but its check accepts "/\evil.example/",
    # which browsers read as //evil.example/. The probe reports the residual gap.
    findings = probe_portal(make_app({"open-redirect"}))
    assert names(findings) == ["backslash"]
    assert findings[0].location == "/\\evil.example/"


def test_the_fully_fixed_portal_still_has_the_backslash_gap():
    assert names(probe_portal(make_app(FLAWS))) == ["backslash"]
