"""Authorization discovery for a protected MCP server - both sides.

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
    raise NotImplementedError("TODO: implement metadata_url")


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
    raise NotImplementedError("TODO: implement protected_resource_metadata")


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
    raise NotImplementedError("TODO: implement www_authenticate")


# --- client side -------------------------------------------------------------------------------------------

_PARAM = re.compile(r'([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(?:"((?:[^"\\]|\\.)*)"|([^\s,"]+))')


def parse_www_authenticate(header: str) -> dict:
    """Parse a ``Bearer`` challenge into ``{"scheme": "bearer", <param>: <value>, ...}``.

    Parameter names are lowercased; quoted values are unescaped; unquoted values (tokens) are accepted too.
    Raise ``ValueError`` if the scheme is not ``Bearer`` (case-insensitive).
    """
    raise NotImplementedError("TODO: implement parse_www_authenticate")


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
    raise NotImplementedError("TODO: implement is_safe_oauth_url")


def validate_resource_metadata(doc: Mapping, *, expected_resource: str, allow_loopback_http: bool = False) -> list:
    """Check a fetched metadata document and return its authorization servers.

    Raise ``MetadataError`` when ``doc["resource"]`` is not identical to ``expected_resource`` (exact string
    comparison, RFC 9728 section 3.3), when ``authorization_servers`` is missing or empty, or when any
    authorization server URL fails ``is_safe_oauth_url``.
    """
    raise NotImplementedError("TODO: implement validate_resource_metadata")


def as_metadata_urls(issuer: str) -> list:
    """Return the authorization server metadata URLs to try, in MCP's priority order.

    With a path (``https://auth.sandpay.example/tenant1``):
    ``/.well-known/oauth-authorization-server/tenant1``, ``/.well-known/openid-configuration/tenant1``,
    ``/tenant1/.well-known/openid-configuration``. Without a path: ``/.well-known/oauth-authorization-server``,
    ``/.well-known/openid-configuration``.
    """
    raise NotImplementedError("TODO: implement as_metadata_urls")


def select_scopes(challenge_scope: str | None, scopes_supported: Iterable[str] | None) -> str | None:
    """MCP's scope selection strategy for the first authorization.

    Use the challenge's ``scope`` if it has one; otherwise every scope in ``scopes_supported``, space-separated;
    otherwise ``None`` (leave the ``scope`` parameter out).
    """
    raise NotImplementedError("TODO: implement select_scopes")


def step_up_scopes(previous: str | None, challenged: str | None) -> str:
    """Scopes for re-authorization after ``insufficient_scope``: the union of what was requested before and what
    the challenge asks for, each scope once, sorted, space-separated - so earlier permissions are not lost."""
    raise NotImplementedError("TODO: implement step_up_scopes")
