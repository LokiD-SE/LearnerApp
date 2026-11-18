"""Authorization discovery for a protected MCP server - both sides - reference solution.

Server side (the SandPay MCP server):

- ``metadata_url`` - where the Protected Resource Metadata document lives (RFC 9728 well-known URI, path inserted).
- ``protected_resource_metadata`` - that document, with at least one authorization server (MCP requires it).
- ``www_authenticate`` - the ``WWW-Authenticate`` challenge for 401 and 403 responses (RFC 6750, RFC 9728 5.1).

Client side (an MCP client meeting the server for the first time):

- ``parse_www_authenticate`` - read the challenge.
- ``is_safe_oauth_url`` - refuse dangerous schemes and internal addresses before fetching any discovered URL.
- ``validate_resource_metadata`` - RFC 9728 section 3.3: ``resource`` must match exactly.
- ``as_metadata_urls`` - the authorization server metadata URLs to try, in the order MCP requires.
- ``select_scopes`` and ``step_up_scopes`` - MCP's scope selection strategy and step-up union.

Standard library only; nothing here makes a network request.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable, Mapping
from urllib.parse import urlsplit

WELL_KNOWN_RESOURCE = "/.well-known/oauth-protected-resource"
LOOPBACK_NAMES = ("localhost",)


class MetadataError(ValueError):
    """Discovered metadata that the client must not use."""


# --- server side -------------------------------------------------------------------------------------------


def metadata_url(resource: str) -> str:
    """Return the Protected Resource Metadata URL for a resource URI.

    The well-known path goes between the host and the resource's path:
    ``https://mcp.sandpay.example/mcp`` -> ``https://mcp.sandpay.example/.well-known/oauth-protected-resource/mcp``;
    a resource at the root (no path, or ``/``) gets ``.../.well-known/oauth-protected-resource``.
    """
    parts = urlsplit(resource)
    path = parts.path.rstrip("/")
    return f"{parts.scheme}://{parts.netloc}{WELL_KNOWN_RESOURCE}{path}"


def protected_resource_metadata(
    resource: str,
    authorization_servers: Iterable[str],
    scopes_supported: Iterable[str],
    resource_name: str | None = None,
) -> dict:
    """Build the metadata document (RFC 9728 section 2).

    Keys, in this order: ``resource``, ``authorization_servers`` (list), ``scopes_supported`` (list),
    ``bearer_methods_supported`` (always ``["header"]``), then ``resource_name`` if given.
    Raise ``ValueError`` if there is no authorization server (MCP requires at least one) or if
    ``offline_access`` is listed (MCP servers SHOULD NOT advertise it - refresh tokens are not a resource need).
    """
    servers = list(authorization_servers)
    scopes = list(scopes_supported)
    if not servers:
        raise ValueError("authorization_servers must list at least one authorization server")
    if "offline_access" in scopes:
        raise ValueError("do not advertise offline_access in scopes_supported")
    doc = {
        "resource": resource,
        "authorization_servers": servers,
        "scopes_supported": scopes,
        "bearer_methods_supported": ["header"],
    }
    if resource_name is not None:
        doc["resource_name"] = resource_name
    return doc


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def www_authenticate(
    resource_metadata: str,
    *,
    error: str | None = None,
    scope: Iterable[str] = (),
    description: str | None = None,
) -> str:
    """Return the ``WWW-Authenticate`` header value.

    Format: ``Bearer `` then the parameters that are present, separated by ``", "``, in this order:
    ``error``, ``scope`` (space-separated), ``resource_metadata``, ``error_description``. Every value is a quoted
    string (escape ``\\`` and ``"``). With no ``error`` (the request had no token) ``error_description`` is left out
    too - RFC 6750 says not to include error information then.
    """
    params = []
    if error:
        params.append(("error", error))
    scope = list(scope)
    if scope:
        params.append(("scope", " ".join(scope)))
    params.append(("resource_metadata", resource_metadata))
    if error and description:
        params.append(("error_description", description))
    return "Bearer " + ", ".join(f"{k}={_quote(v)}" for k, v in params)


# --- client side -------------------------------------------------------------------------------------------

_PARAM = re.compile(r'([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(?:"((?:[^"\\]|\\.)*)"|([^\s,"]+))')


def parse_www_authenticate(header: str) -> dict:
    """Parse a ``Bearer`` challenge into ``{"scheme": "bearer", <param>: <value>, ...}``.

    Parameter names are lowercased; quoted values are unescaped; unquoted values (tokens) are accepted too.
    Raise ``ValueError`` if the scheme is not ``Bearer`` (case-insensitive).
    """
    scheme, _, rest = header.strip().partition(" ")
    if scheme.lower() != "bearer":
        raise ValueError(f"not a Bearer challenge: {scheme!r}")
    result = {"scheme": "bearer"}
    for match in _PARAM.finditer(rest):
        name, quoted, token = match.groups()
        value = re.sub(r"\\(.)", r"\1", quoted) if quoted is not None else token
        result[name.lower()] = value
    return result


def is_safe_oauth_url(url: str, *, allow_loopback_http: bool = False) -> bool:
    """Decide whether the client may fetch or open a URL it discovered during authorization.

    - Only ``https`` - or ``http`` to a loopback host (``localhost``, ``127.0.0.0/8``, ``::1``) when
      ``allow_loopback_http`` is set for local development. Every other scheme (``javascript:``, ``data:``,
      ``file:``...) is refused.
    - A host that is an IP literal must not be private, loopback, link-local, reserved, multicast or unspecified
      (loopback is allowed only with ``allow_loopback_http``). ``localhost`` follows the loopback rule.
    - No host: refused.

    Hostnames are not resolved here: a name that resolves to an internal address needs a check at connection
    time (or an egress proxy). Parsing addresses uses the ``ipaddress`` module rather than hand-written rules.
    """
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False
    scheme = parts.scheme.lower()
    if not host:
        return False
    host = host.lower()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    is_loopback = host in LOOPBACK_NAMES or (address is not None and address.is_loopback)
    if scheme == "http":
        return allow_loopback_http and is_loopback
    if scheme != "https":
        return False
    if is_loopback:
        return allow_loopback_http
    if address is not None:
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
            address = address.ipv4_mapped
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            return False
    return True


def validate_resource_metadata(doc: Mapping, *, expected_resource: str, allow_loopback_http: bool = False) -> list:
    """Check a fetched metadata document and return its authorization servers.

    Raise ``MetadataError`` when ``doc["resource"]`` is not identical to ``expected_resource`` (exact string
    comparison, RFC 9728 section 3.3), when ``authorization_servers`` is missing or empty, or when any
    authorization server URL fails ``is_safe_oauth_url``.
    """
    if doc.get("resource") != expected_resource:
        raise MetadataError(f"resource {doc.get('resource')!r} does not match {expected_resource!r}")
    servers = doc.get("authorization_servers")
    if not isinstance(servers, list) or not servers:
        raise MetadataError("no authorization_servers")
    for server in servers:
        if not isinstance(server, str) or not is_safe_oauth_url(server, allow_loopback_http=allow_loopback_http):
            raise MetadataError(f"unsafe authorization server URL {server!r}")
    return list(servers)


def as_metadata_urls(issuer: str) -> list:
    """Return the authorization server metadata URLs to try, in MCP's priority order.

    With a path (``https://auth.sandpay.example/tenant1``):
    ``/.well-known/oauth-authorization-server/tenant1``, ``/.well-known/openid-configuration/tenant1``,
    ``/tenant1/.well-known/openid-configuration``. Without a path: ``/.well-known/oauth-authorization-server``,
    ``/.well-known/openid-configuration``.
    """
    parts = urlsplit(issuer)
    origin = f"{parts.scheme}://{parts.netloc}"
    path = parts.path.rstrip("/")
    if path:
        return [
            f"{origin}/.well-known/oauth-authorization-server{path}",
            f"{origin}/.well-known/openid-configuration{path}",
            f"{origin}{path}/.well-known/openid-configuration",
        ]
    return [f"{origin}/.well-known/oauth-authorization-server", f"{origin}/.well-known/openid-configuration"]


def select_scopes(challenge_scope: str | None, scopes_supported: Iterable[str] | None) -> str | None:
    """MCP's scope selection strategy for the first authorization.

    Use the challenge's ``scope`` if it has one; otherwise every scope in ``scopes_supported``, space-separated;
    otherwise ``None`` (leave the ``scope`` parameter out).
    """
    if challenge_scope:
        return challenge_scope
    if scopes_supported:
        return " ".join(scopes_supported)
    return None


def step_up_scopes(previous: str | None, challenged: str | None) -> str:
    """Scopes for re-authorization after ``insufficient_scope``: the union of what was requested before and what
    the challenge asks for, each scope once, sorted, space-separated - so earlier permissions are not lost."""
    return " ".join(sorted(set((previous or "").split()) | set((challenged or "").split())))
