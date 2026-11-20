import ipaddress

import pytest
from web.ssrf_policy import Destination, UnsafeURL, check_webhook_url, is_public, parse_address, safe_next

pytestmark = pytest.mark.exercise

PUBLIC = "8.8.8.8"


def dns(table):
    """A resolver over a fixed table that counts its calls - tests never touch the real network."""

    def resolve(host):
        resolve.calls.append(host)
        return list(table.get(host, []))

    resolve.calls = []
    return resolve


def refused(url, resolver=None, **kw):
    with pytest.raises(UnsafeURL) as info:
        check_webhook_url(url, resolver or dns({}), **kw)
    return info.value.reason


# ---- safe_next: local redirects -----------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["/settings", "/payments?status=captured", "/a/b/c#top", "/"])
def test_local_paths_are_kept(value):
    assert safe_next(value) == value


@pytest.mark.parametrize("value", [
    None,
    "",
    "settings",  # relative: ambiguous, no leading slash
    "https://evil.example/",
    "http://portal.sandpay.example/settings",
    "//evil.example/",
    "/\\evil.example/",
    "\\\\evil.example/",
    "/\t/evil.example/",
    "/\n/evil.example/",
    "javascript:alert(1)",
    "https://shop.example@evil.example/",
])
def test_everything_else_becomes_the_default(value):
    assert safe_next(value) == "/settings"


def test_the_default_can_be_chosen():
    assert safe_next("//evil.example/", default="/home") == "/home"


# ---- parse_address: every way of writing an address ---------------------------------------------------------
@pytest.mark.parametrize("host, expected", [
    ("127.0.0.1", "127.0.0.1"),
    ("127.1", "127.0.0.1"),  # short form
    ("2130706433", "127.0.0.1"),  # decimal
    ("0x7f000001", "127.0.0.1"),  # hex
    ("017700000001", "127.0.0.1"),  # octal
    ("0x7f.0.0.1", "127.0.0.1"),  # mixed
    ("[::1]", "::1"),
    ("::1", "::1"),
    ("::ffff:127.0.0.1", "127.0.0.1"),  # IPv4-mapped IPv6 is judged as its IPv4 address
    ("[::ffff:169.254.169.254]", "169.254.169.254"),
    ("8.8.8.8", "8.8.8.8"),
])
def test_address_literals_in_every_spelling(host, expected):
    assert parse_address(host) == ipaddress.ip_address(expected)


@pytest.mark.parametrize("host", ["localhost", "example.com", "pay.sandpay.example", "127.0.0.1 evil"])
def test_names_are_not_addresses(host):
    assert parse_address(host) is None


def test_the_standard_library_alone_misses_the_legacy_forms():
    # Why parse_address needs more than ipaddress: these raise ValueError, yet resolvers accept them.
    for form in ("127.1", "2130706433", "0x7f000001"):
        with pytest.raises(ValueError):
            ipaddress.ip_address(form)


@pytest.mark.parametrize("address", ["8.8.8.8", "1.1.1.1", "2001:4860:4860::8888"])
def test_public_addresses(address):
    assert is_public(ipaddress.ip_address(address)) is True


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.1.2.3", "172.16.0.5", "192.168.1.1", "169.254.169.254", "100.64.0.1",
    "0.0.0.0", "224.0.0.1", "::1", "fe80::1", "fc00::1",
])
def test_non_public_addresses(address):
    assert is_public(ipaddress.ip_address(address)) is False


# ---- check_webhook_url: what is allowed -----------------------------------------------------------------------
def test_a_public_name_is_allowed_and_pinned():
    resolver = dns({"hooks.partner.example": [PUBLIC]})
    dest = check_webhook_url("https://hooks.partner.example/sandpay?x=1", resolver)
    assert dest == Destination("https", "hooks.partner.example", 443, "/sandpay?x=1", PUBLIC)


def test_a_public_address_literal_needs_no_lookup():
    resolver = dns({})
    dest = check_webhook_url("http://8.8.8.8/hook", resolver)
    assert (dest.connect_ip, dest.port, dest.path) == (PUBLIC, 80, "/hook")
    assert resolver.calls == []


def test_the_name_is_resolved_exactly_once():
    resolver = dns({"hooks.partner.example": [PUBLIC]})
    check_webhook_url("https://hooks.partner.example/", resolver)
    assert resolver.calls == ["hooks.partner.example"]


def test_dns_that_changes_its_answer_cannot_swap_the_destination():
    # A rebinding server answers public the first time and 127.0.0.1 the second. The policy resolves once,
    # validates that answer and returns it as the address to connect to.
    answers = iter([[PUBLIC], ["127.0.0.1"]])
    dest = check_webhook_url("https://rebind.evil.example/", lambda host: next(answers))
    assert dest.connect_ip == PUBLIC


def test_an_allow_list_of_hosts_is_case_insensitive():
    resolver = dns({"hooks.partner.example": [PUBLIC]})
    allowed = frozenset({"hooks.partner.example"})
    assert check_webhook_url("https://HOOKS.partner.example/x", resolver, allowed_hosts=allowed).host == "hooks.partner.example"
    assert refused("https://other.example/x", resolver, allowed_hosts=allowed) == "not-allowed"


# ---- check_webhook_url: what is refused ---------------------------------------------------------------------
@pytest.mark.parametrize("url, reason", [
    ("ftp://8.8.8.8/x", "scheme"),
    ("file:///etc/passwd", "scheme"),
    ("gopher://8.8.8.8:70/_x", "scheme"),
    ("//8.8.8.8/x", "scheme"),
    ("https://shop.example@8.8.8.8/", "userinfo"),
    ("https://user:pw@8.8.8.8/", "userinfo"),
    ("https:///path", "host"),
    ("http://8.8.8.8\\@evil.example/", "host"),
    ("http://8.8.8.8 /x", "host"),
    ("http://8.8.8.8:99999/", "host"),
    ("http://8.8.8.8:8080/", "port"),
    ("https://8.8.8.8:80/", "port"),
])
def test_malformed_and_unusual_urls_are_refused(url, reason):
    assert refused(url) == reason


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",
    "http://localhost/admin",
    "http://[::1]/admin",
    "http://127.1/admin",
    "http://2130706433/admin",
    "http://0x7f000001/admin",
    "http://017700000001/admin",
    "http://[::ffff:127.0.0.1]/admin",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::ffff:169.254.169.254]/latest/meta-data/",
    "http://10.0.0.5/",
    "http://192.168.0.10/",
    "http://0.0.0.0/",
])
def test_internal_addresses_are_refused_in_every_spelling(url):
    assert refused(url, dns({"localhost": ["127.0.0.1", "::1"]})) == "private-address"


def test_a_name_that_resolves_to_a_private_address_is_refused():
    # WSTG: "Registering your own domain that resolves to 127.0.0.1".
    assert refused("https://internal.evil.example/", dns({"internal.evil.example": ["127.0.0.1"]})) == "private-address"


def test_one_private_answer_among_public_ones_refuses_the_name():
    resolver = dns({"mixed.evil.example": [PUBLIC, "10.0.0.8"]})
    assert refused("https://mixed.evil.example/", resolver) == "private-address"


def test_an_unresolvable_name_is_refused():
    assert refused("https://nowhere.example/", dns({})) == "unresolvable"


def test_a_host_outside_the_allow_list_is_refused_before_any_lookup():
    resolver = dns({"hooks.partner.example": [PUBLIC]})
    assert refused("https://hooks.partner.example/", resolver, allowed_hosts=frozenset({"x.example"})) == "not-allowed"
    assert resolver.calls == []
