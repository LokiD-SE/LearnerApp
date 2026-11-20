"""SOLUTION - Check a TLS service the way WSTG-CRYP-01 describes, against a local server only.

Three pieces:

- ``check_certificate`` - a certificate's facts (key size, signature algorithm, validity, names) -> finding codes.
  WSTG-CRYP-01: the key should be at least 2048 bits; the signature at least SHA-256 (not MD5 or SHA-1);
  certificates issued after 1 September 2020 must not live longer than 398 days; the name must match a Subject
  Alternative Name (the Common Name is ignored by modern browsers).
- ``supported_tls_versions`` - really handshakes with each of TLS 1.2 and TLS 1.3 against ``host:port`` and says
  which the server accepted. Loopback only: it refuses any other host before opening a socket.
- ``audit_protocols`` - the accepted versions -> finding codes. SSL 3.0, TLS 1.0 and TLS 1.1 are legacy
  (RFC 8996 deprecates TLS 1.0 and 1.1).

A client that cannot TRY a version tells you nothing about the server: the OpenSSL on this machine refuses
TLS 1.0 and 1.1, so ``supported_tls_versions`` only probes 1.2 and 1.3 - that is why ``audit_protocols`` takes
the accepted list from whatever tool could try the old versions (``nmap``, ``testssl.sh``, ``sslyze``).
"""

from __future__ import annotations

import datetime as dt
import socket
import ssl
from typing import Iterable

LEGACY = ("SSLv2", "SSLv3", "TLSv1.0", "TLSv1.1")
MODERN = ("TLSv1.2", "TLSv1.3")
MIN_KEY_BITS = 2048
MAX_LIFETIME_DAYS = 398
LIFETIME_RULE_FROM = dt.datetime(2020, 9, 1, tzinfo=dt.timezone.utc)
LOOPBACK = ("127.0.0.1", "localhost", "::1")


_VERSIONS = {"TLSv1.2": ssl.TLSVersion.TLSv1_2, "TLSv1.3": ssl.TLSVersion.TLSv1_3}


def _matches(hostname: str, pattern: str) -> bool:
    hostname, pattern = hostname.lower(), pattern.lower()
    if pattern.startswith("*."):
        head, _, rest = hostname.partition(".")
        return bool(head) and rest == pattern[2:]
    return hostname == pattern


def check_certificate(facts: dict, hostname: str, now: dt.datetime) -> list[str]:
    """Returns the sorted finding codes for a certificate."""
    codes: set[str] = set()
    if facts["key_bits"] < MIN_KEY_BITS:
        codes.add("weak-key")
    algorithm = facts["signature_algorithm"].lower()
    if "md5" in algorithm or "sha1" in algorithm:
        codes.add("weak-signature")
    if now > facts["not_after"]:
        codes.add("expired")
    if now < facts["not_before"]:
        codes.add("not-yet-valid")
    if facts["not_before"] >= LIFETIME_RULE_FROM and (facts["not_after"] - facts["not_before"]).days > MAX_LIFETIME_DAYS:
        codes.add("lifetime-over-398-days")
    if not any(_matches(hostname, name) for name in facts["san"]):
        codes.add("hostname-mismatch")
    return sorted(codes)


def supported_tls_versions(host: str, port: int, cafile: str, timeout: float = 5.0) -> list[str]:
    """Returns the subset of ``MODERN`` that the server at ``host:port`` completes a handshake with."""
    if host not in LOOPBACK:
        raise ValueError("this probe only talks to the loopback interface")
    accepted = []
    for name in MODERN:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = context.maximum_version = _VERSIONS[name]
        context.load_verify_locations(cafile)
        try:
            with socket.create_connection((host, port), timeout=timeout) as raw:
                with context.wrap_socket(raw, server_hostname=host) as tls:
                    if tls.version() == name:
                        accepted.append(name)
        except (ssl.SSLError, OSError):
            continue
    return accepted


def audit_protocols(accepted: Iterable[str]) -> list[str]:
    """Returns sorted finding codes for the protocol versions a server accepted."""
    names = set(accepted)
    unknown = names - set(LEGACY) - set(MODERN)
    if unknown:
        raise ValueError(f"unknown protocol names: {sorted(unknown)}")
    codes = {f"legacy-protocol:{name}" for name in names if name in LEGACY}
    if not names & set(MODERN):
        codes.add("no-modern-protocol")
    return sorted(codes)
