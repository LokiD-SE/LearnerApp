"""Access-token checks at a protected MCP server (an OAuth 2.1 resource server) - reference solution.

The SandPay merchant MCP server at ``https://mcp.sandpay.example/mcp`` accepts only access tokens that its
own authorization server (``https://auth.sandpay.example``) issued **for it**. This module is the part of the
server that runs before any JSON-RPC message is handled:

- ``canonical_resource`` - the canonical server URI (MCP authorization, "Canonical Server URI"; RFC 8707 section 2).
- ``bearer_token`` - the token from the ``Authorization: Bearer`` header, never from the query string.
- ``TokenValidator.validate`` - the RFC 9068 section 4 checks: type, algorithm, signature, issuer, audience, expiry.
- ``TokenValidator.require`` - scope checks that account for scope hierarchies; all missing scopes in one error.

Teaching tokens: JWT-shaped (``header.payload.signature`` in base64url) and signed with HMAC-SHA256 ("HS256")
using a shared secret, so the tests need only the standard library. Real authorization servers usually sign
with an asymmetric key published at ``jwks_uri`` (RFC 9068 recommends asymmetric signing) and real servers use
a maintained JWT library or token introspection (RFC 7662). The checks are the same.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

ACCEPTED_TYPES = ("at+jwt", "application/at+jwt")


class InvalidResourceURI(ValueError):
    """A string that cannot be an MCP server's canonical URI."""


class AuthError(Exception):
    """An authorization failure, carrying what the HTTP response needs.

    ``error`` is ``None`` when the request carried no usable credentials at all: RFC 6750 section 3.1 says the
    server SHOULD NOT include an error code then. Otherwise it is ``invalid_request`` (400), ``invalid_token``
    (401) or ``insufficient_scope`` (403).
    """

    def __init__(self, status: int, error: str | None, description: str = "", scope: Iterable[str] = ()):
        super().__init__(f"{status} {error or 'no credentials'}: {description}".strip())
        self.status = status
        self.error = error
        self.description = description
        self.scope = tuple(scope)


# --- helpers (given; not part of the exercise) -------------------------------------------------------------


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign_token(claims: Mapping, secret: bytes, *, alg: str = "HS256", typ: str = "at+jwt") -> str:
    """Mint a teaching token the way the authorization server would (the tests use this)."""
    header = b64url_encode(json.dumps({"alg": alg, "typ": typ}, separators=(",", ":")).encode())
    payload = b64url_encode(json.dumps(dict(claims), separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = b64url_encode(hmac.new(secret, signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


# --- the exercise ------------------------------------------------------------------------------------------


def canonical_resource(uri: str) -> str:
    """Return the canonical form of an MCP server URI.

    - It must be absolute with an ``https`` or ``http`` scheme and a host, else ``InvalidResourceURI``.
    - It must not contain a fragment (any ``#``), else ``InvalidResourceURI``.
    - Scheme and host are lowercased; the port, path and query are kept as given.
    - One trailing ``/`` is removed from the path (``https://mcp.example.com/`` -> ``https://mcp.example.com``).
    """
    if "#" in uri:
        raise InvalidResourceURI(f"{uri!r} has a fragment")
    parts = urlsplit(uri)
    scheme = parts.scheme.lower()
    if scheme not in ("https", "http") or not parts.hostname:
        raise InvalidResourceURI(f"{uri!r} is not an absolute http(s) URI")
    netloc = parts.hostname.lower()
    if parts.port is not None:
        netloc = f"{netloc}:{parts.port}"
    path = parts.path[:-1] if parts.path.endswith("/") else parts.path
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def bearer_token(authorization: str | None, url: str = "") -> str:
    """Return the access token from an ``Authorization`` header value.

    - A token in the request URL's query string (``access_token=``) is refused with
      ``AuthError(400, "invalid_request")`` - MCP forbids tokens in the URI query string.
    - No header, or a scheme other than ``Bearer`` (case-insensitive): ``AuthError(401, None)``.
    - ``Bearer`` with no token, or more than one token: ``AuthError(400, "invalid_request")``.
    """
    if "access_token=" in urlsplit(url).query:
        raise AuthError(400, "invalid_request", "access tokens must not be sent in the query string")
    if not authorization:
        raise AuthError(401, None)
    scheme, _, rest = authorization.strip().partition(" ")
    if scheme.lower() != "bearer":
        raise AuthError(401, None)
    pieces = rest.split()
    if len(pieces) != 1:
        raise AuthError(400, "invalid_request", "expected exactly one bearer token")
    return pieces[0]


class TokenValidator:
    """Validates tokens for one resource server.

    ``resource`` is this server's URI (canonicalised on construction), ``issuer`` the authorization server's
    issuer identifier, ``secret`` the HS256 key. ``implies`` maps a broad scope to the narrower scopes it
    includes, for example ``{"refunds:write": {"payments:read"}}``. ``clock`` returns the current Unix time.
    """

    def __init__(
        self,
        resource: str,
        issuer: str,
        secret: bytes,
        *,
        leeway_s: int = 60,
        implies: Mapping[str, Iterable[str]] | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.resource = canonical_resource(resource)
        self.issuer = issuer
        self.secret = secret
        self.leeway_s = leeway_s
        self.implies = {k: set(v) for k, v in (implies or {}).items()}
        self.clock = clock

    def validate(self, token: str) -> dict:
        """Return the token's claims, or raise ``AuthError(401, "invalid_token", <reason>)``.

        Check, in this order: three dot-separated parts that decode to JSON objects ("malformed token");
        ``typ`` is ``at+jwt`` or ``application/at+jwt`` ("wrong token type"); ``alg`` is ``HS256`` ("unsupported
        algorithm"); the signature, compared in constant time ("bad signature"); ``iss`` equals the issuer exactly
        ("wrong issuer"); ``aud`` (a string or a list) contains this server's canonical URI ("token not issued for
        this server"); ``exp`` is a number and now < exp + leeway ("token expired").
        """

        def reject(reason: str) -> AuthError:
            return AuthError(401, "invalid_token", reason)

        parts = token.split(".")
        if len(parts) != 3:
            raise reject("malformed token")
        try:
            header = json.loads(b64url_decode(parts[0]))
            claims = json.loads(b64url_decode(parts[1]))
            signature = b64url_decode(parts[2])
        except ValueError:
            raise reject("malformed token") from None
        if not isinstance(header, dict) or not isinstance(claims, dict):
            raise reject("malformed token")
        if header.get("typ") not in ACCEPTED_TYPES:
            raise reject("wrong token type")
        if header.get("alg") != "HS256":
            raise reject("unsupported algorithm")
        expected = hmac.new(self.secret, f"{parts[0]}.{parts[1]}".encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, signature):
            raise reject("bad signature")
        if claims.get("iss") != self.issuer:
            raise reject("wrong issuer")
        audiences = claims.get("aud")
        if isinstance(audiences, str):
            audiences = [audiences]
        if not isinstance(audiences, list) or not any(self._is_me(a) for a in audiences):
            raise reject("token not issued for this server")
        exp = claims.get("exp")
        if isinstance(exp, bool) or not isinstance(exp, (int, float)) or self.clock() >= exp + self.leeway_s:
            raise reject("token expired")
        return claims

    def _is_me(self, audience: object) -> bool:
        if not isinstance(audience, str):
            return False
        try:
            return canonical_resource(audience) == self.resource
        except InvalidResourceURI:
            return False

    def require(self, claims: Mapping, needed: Iterable[str]) -> None:
        """Raise ``AuthError(403, "insufficient_scope", scope=<every needed scope, sorted>)`` unless the token's
        space-separated ``scope`` claim, expanded through ``implies``, covers every needed scope."""
        needed = set(needed)
        granted = set(str(claims.get("scope", "")).split())
        effective = set(granted)
        for scope in granted:
            effective |= self.implies.get(scope, set())
        if not needed <= effective:
            raise AuthError(403, "insufficient_scope", "additional scope required", scope=sorted(needed))

    def authenticate(self, authorization: str | None, needed: Iterable[str], url: str = "") -> dict:
        """The whole check for one request: ``bearer_token``, then ``validate``, then ``require``."""
        claims = self.validate(bearer_token(authorization, url))
        self.require(claims, needed)
        return claims
