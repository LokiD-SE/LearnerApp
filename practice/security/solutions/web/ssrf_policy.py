"""The fix side: decide which URLs a server may fetch or redirect to (SSRF Prevention + Unvalidated Redirects
cheat sheets, ASVS-style allow-listing).

Two small pure functions you can unit-test without a network:

* ``safe_next`` - a local-redirect check: only a path on this site is allowed, anything else becomes the
  default. The cheat sheet's advice: "Compare the parsed scheme, canonical host, and effective port against
  an explicit allowlist ... Reject userinfo and ambiguous input".
* ``check_webhook_url`` - the "any external address" case of the SSRF cheat sheet: allow only http(s) on
  expected ports, parse the host in every form an address can be written, resolve names **once**, require
  every resolved address to be public, and return the validated address to connect to, so a second DNS lookup
  cannot swap it ("A second, unchecked DNS lookup between validation and connection can bypass these checks").

The resolver is passed in (``resolve(host) -> list of address strings``), so tests control DNS.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

Resolver = Callable[[str], list[str]]
DEFAULT_NEXT = "/settings"
DEFAULT_PORTS = {"http": 80, "https": 443}


class UnsafeURL(Exception):
    """The URL was refused; ``reason`` is one of the codes below."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason  # scheme, userinfo, host, port, not-allowed, unresolvable, private-address


@dataclass(frozen=True)
class Destination:
    scheme: str
    host: str  # the name from the URL - keep it for the Host header and TLS server name
    port: int
    path: str  # path and query, as given
    connect_ip: str  # the validated address to connect to


def safe_next(value: str | None, default: str = DEFAULT_NEXT) -> str:
    """``value`` if it is a path on this site, otherwise ``default``.

    Accept only a value that starts with exactly one ``/`` and has no scheme, host, backslash or control
    character (browsers read ``/\\evil.example/`` as ``//evil.example/`` and drop tab, CR and LF from a URL
    before parsing it). ``None`` and the empty string give the default.
    """
    if not value or not value.startswith("/") or value.startswith("//"):
        return default
    if "\\" in value or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        return default
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return default
    return value


def parse_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """The IP address ``host`` stands for, or None if it is a name.

    Handles ``[::1]`` brackets, IPv4-mapped IPv6 (unmapped to IPv4 so ``::ffff:127.0.0.1`` is judged as
    ``127.0.0.1``) and the legacy IPv4 spellings that ``ipaddress`` refuses but resolvers accept: ``127.1``,
    ``2130706433``, ``0x7f000001``, ``017700000001`` (WSTG "Common Filter Bypass"). ``socket.inet_aton``
    reads those the way the C library does.
    """
    bare = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    if any(ch.isspace() for ch in bare):
        return None  # inet_aton ignores everything after a space; a host never contains one
    try:
        ip: ipaddress.IPv4Address | ipaddress.IPv6Address = ipaddress.ip_address(bare)
    except ValueError:
        try:
            ip = ipaddress.IPv4Address(socket.inet_aton(bare))
        except OSError:
            return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True only for globally routable addresses (not loopback, private, link-local, shared, multicast...)."""
    return ip.is_global and not ip.is_multicast


def check_webhook_url(url: str, resolve: Resolver, allowed_hosts: frozenset[str] | None = None,
                      allowed_ports: dict[str, int] | None = None) -> Destination:
    """Returns the validated destination or raises ``UnsafeURL``.

    1. Scheme must be http or https, else ``scheme``.
    2. The URL must contain no whitespace or backslash (parsers disagree about them), else ``host``. It must
       have no userinfo (``user@host``), else ``userinfo``, and it must have a host, else ``host``.
    3. The port (default for the scheme if absent) must be the scheme's standard one, else ``port``.
    4. If ``allowed_hosts`` is given, the lower-cased host must be in it, else ``not-allowed``.
    5. Address literals are parsed with ``parse_address``; a name is resolved **once** with ``resolve``.
       No address -> ``unresolvable``. Every address must be public, else ``private-address``.
    6. Return a ``Destination`` whose ``connect_ip`` is the first validated address.
    """
    ports = allowed_ports or DEFAULT_PORTS
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise UnsafeURL("host") from None
    if parts.scheme not in ports:
        raise UnsafeURL("scheme")
    if "\\" in url or any(ch.isspace() for ch in url):
        raise UnsafeURL("host")
    if parts.username is not None or parts.password is not None:
        raise UnsafeURL("userinfo")
    host = parts.hostname
    if not host:
        raise UnsafeURL("host")
    if (port or ports[parts.scheme]) != ports[parts.scheme]:
        raise UnsafeURL("port")
    if allowed_hosts is not None and host.lower() not in allowed_hosts:
        raise UnsafeURL("not-allowed")
    literal = parse_address(host)
    addresses = [literal] if literal is not None else [a for a in map(parse_address, resolve(host)) if a is not None]
    if not addresses:
        raise UnsafeURL("unresolvable")
    if not all(is_public(a) for a in addresses):
        raise UnsafeURL("private-address")
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return Destination(parts.scheme, host, ports[parts.scheme], path, str(addresses[0]))
