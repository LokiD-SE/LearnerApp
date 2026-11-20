"""Checks practice/security/exercises/web/crypto_tls_check.py (testing-cryptography-and-data-exposure lesson)."""

import datetime as dt
import socket

import pytest
from crypto_fixture import cert_facts, serve_tls
from web.crypto_tls_check import audit_protocols, check_certificate, supported_tls_versions

pytestmark = pytest.mark.exercise

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 20, tzinfo=UTC)


def facts(**changes):
    base = {"key_bits": 2048, "signature_algorithm": "sha256WithRSAEncryption",
            "not_before": dt.datetime(2026, 10, 1, tzinfo=UTC), "not_after": dt.datetime(2027, 1, 1, tzinfo=UTC),
            "san": ["pay.sandpay.example", "*.sandpay.example"]}
    return {**base, **changes}


def test_a_good_certificate_has_no_findings():
    assert check_certificate(facts(), "pay.sandpay.example", NOW) == []


def test_weak_key_and_weak_signature():
    assert check_certificate(facts(key_bits=1024), "pay.sandpay.example", NOW) == ["weak-key"]
    for algorithm in ("sha1WithRSAEncryption", "md5WithRSAEncryption", "ecdsa-with-SHA1"):
        assert check_certificate(facts(signature_algorithm=algorithm), "pay.sandpay.example", NOW) == ["weak-signature"]
    assert check_certificate(facts(key_bits=256, signature_algorithm="ecdsa-with-SHA256"),
                             "pay.sandpay.example", NOW) == ["weak-key"]  # the rule is on bits, as WSTG states it


def test_validity_window():
    assert check_certificate(facts(not_after=dt.datetime(2026, 11, 19, tzinfo=UTC)),
                             "pay.sandpay.example", NOW) == ["expired"]
    assert check_certificate(facts(not_before=dt.datetime(2026, 12, 1, tzinfo=UTC), not_after=dt.datetime(2027, 1, 1, tzinfo=UTC)),
                             "pay.sandpay.example", NOW) == ["not-yet-valid"]


def test_398_day_limit_applies_from_september_2020():
    long_new = facts(not_before=dt.datetime(2026, 1, 1, tzinfo=UTC), not_after=dt.datetime(2027, 3, 1, tzinfo=UTC))  # 424 days
    assert check_certificate(long_new, "pay.sandpay.example", NOW) == ["lifetime-over-398-days"]
    exactly = facts(not_before=dt.datetime(2026, 1, 1, tzinfo=UTC), not_after=dt.datetime(2027, 2, 4, tzinfo=UTC))  # 399 days
    assert check_certificate(exactly, "pay.sandpay.example", NOW) == ["lifetime-over-398-days"]
    ok = facts(not_before=dt.datetime(2026, 1, 1, tzinfo=UTC), not_after=dt.datetime(2027, 2, 3, tzinfo=UTC))  # 398 days
    assert check_certificate(ok, "pay.sandpay.example", NOW) == []
    old = facts(not_before=dt.datetime(2019, 1, 1, tzinfo=UTC), not_after=dt.datetime(2027, 1, 1, tzinfo=UTC))
    assert check_certificate(old, "pay.sandpay.example", NOW) == []  # issued before the rule


def test_hostname_matches_san_only():
    assert check_certificate(facts(), "api.sandpay.example", NOW) == []  # wildcard covers one label
    assert check_certificate(facts(), "PAY.SandPay.example", NOW) == []
    assert check_certificate(facts(), "sandpay.example", NOW) == ["hostname-mismatch"]
    assert check_certificate(facts(), "a.b.sandpay.example", NOW) == ["hostname-mismatch"]
    assert check_certificate(facts(), "pay.other.example", NOW) == ["hostname-mismatch"]
    assert check_certificate(facts(san=["127.0.0.1"]), "127.0.0.1", NOW) == []


def test_findings_are_combined_and_sorted():
    bad = facts(key_bits=1024, signature_algorithm="sha1WithRSAEncryption", san=[],
                not_after=dt.datetime(2026, 11, 1, tzinfo=UTC))
    assert check_certificate(bad, "pay.sandpay.example", NOW) == ["expired", "hostname-mismatch", "weak-key", "weak-signature"]


def test_audit_protocols():
    assert audit_protocols(["TLSv1.2", "TLSv1.3"]) == []
    assert audit_protocols(["TLSv1.2"]) == []
    assert audit_protocols(["TLSv1.0", "TLSv1.2", "SSLv3"]) == ["legacy-protocol:SSLv3", "legacy-protocol:TLSv1.0"]
    assert audit_protocols(["TLSv1.1"]) == ["legacy-protocol:TLSv1.1", "no-modern-protocol"]
    assert audit_protocols([]) == ["no-modern-protocol"]
    with pytest.raises(ValueError):
        audit_protocols(["TLSv1.4"])


@pytest.mark.parametrize("variant,expected", [("modern", ["TLSv1.2", "TLSv1.3"]), ("tls12", ["TLSv1.2"]), ("tls13", ["TLSv1.3"])])
def test_probe_reports_what_the_local_server_accepts(variant, expected):
    with serve_tls(variant) as (host, port, cert):
        assert supported_tls_versions(host, port, str(cert)) == expected
        assert audit_protocols(supported_tls_versions(host, port, str(cert))) == []


def test_the_local_certificate_passes_the_certificate_checks():
    with serve_tls("modern") as (host, _, cert):
        found = cert_facts(cert)
    assert found["key_bits"] == 2048 and found["san"] == ["localhost", "127.0.0.1"]
    assert check_certificate(found, "localhost", dt.datetime.now(UTC)) == []
    assert check_certificate(found, "pay.sandpay.example", dt.datetime.now(UTC)) == ["hostname-mismatch"]


def test_the_probe_sends_nothing_to_a_non_loopback_host(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("a socket was opened")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    for host in ("example.com", "10.0.0.5", "192.0.2.1"):
        with pytest.raises(ValueError):
            supported_tls_versions(host, 443, "/nonexistent.pem")


def test_a_closed_port_is_not_accepted_and_not_an_error():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with serve_tls("modern") as (_, _, cert):
        assert supported_tls_versions("127.0.0.1", port, str(cert), timeout=1.0) == []
