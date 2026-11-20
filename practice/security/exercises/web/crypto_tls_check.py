"""EXERCISE - Check a TLS service the way WSTG-CRYP-01 describes, against a local server only.

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


def check_certificate(facts: dict, hostname: str, now: dt.datetime) -> list[str]:
    """Returns the sorted finding codes for a certificate.

    ``facts`` keys: ``key_bits`` (int), ``signature_algorithm`` (str, for example ``sha256WithRSAEncryption``),
    ``not_before`` and ``not_after`` (timezone-aware datetimes), ``san`` (list of DNS names and IP addresses).

    Codes: ``weak-key``, ``weak-signature`` (MD5 or SHA-1 in the algorithm name, any case), ``expired``,
    ``not-yet-valid``, ``lifetime-over-398-days`` (only when ``not_before`` is on or after 2020-09-01),
    ``hostname-mismatch`` (the hostname must equal a SAN entry, case-insensitively; a wildcard ``*.example.org``
    covers exactly one label, so ``a.example.org`` but not ``example.org`` or ``a.b.example.org``).
    """
    # TODO: apply each rule from the docstring and return sorted(codes).
    raise NotImplementedError("check_certificate")


def supported_tls_versions(host: str, port: int, cafile: str, timeout: float = 5.0) -> list[str]:
    """Returns the subset of ``MODERN`` that the server at ``host:port`` completes a handshake with.

    Raises ``ValueError`` for any host that is not loopback BEFORE any socket is opened. Trusts only ``cafile``
    and verifies the certificate and the host name; a failed handshake, a reset connection or a timeout means
    "not accepted" for that version.
    """
    # TODO: refuse non-loopback hosts; for each version build an SSLContext with minimum_version == maximum_version,
    # load_verify_locations(cafile), connect with create_connection and wrap_socket(server_hostname=host).
    raise NotImplementedError("supported_tls_versions")


def audit_protocols(accepted: Iterable[str]) -> list[str]:
    """Returns sorted finding codes for the protocol versions a server accepted.

    ``legacy-protocol:<version>`` for each accepted version in ``LEGACY``; ``no-modern-protocol`` when neither
    TLS 1.2 nor TLS 1.3 is accepted. An unknown version name raises ``ValueError``.
    """
    # TODO: validate the names, then build the codes.
    raise NotImplementedError("audit_protocols")
