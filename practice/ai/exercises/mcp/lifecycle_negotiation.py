"""Protocol versions in both MCP eras: per-request metadata (modern) and the initialize handshake (legacy).

Running example: SandPay's support-desk client must talk to new MCP servers and to older ones that still
expect a handshake, and SandPay's own server must reject requests it cannot serve.

Sources (MCP specification):

- 2026-07-28 Basic, ``_meta``: every client request carries ``io.modelcontextprotocol/protocolVersion``
  (string, required) and ``io.modelcontextprotocol/clientCapabilities`` (object, required). "A request
  missing any required field is malformed; the server MUST reject it with JSON-RPC error code -32602".
- 2026-07-28 Versioning: if the server does not implement the requested version it "MUST respond with an
  UnsupportedProtocolVersionError" - code -32022, ``data: {"supported": [...], "requested": ...}``. The
  client "SHOULD select a mutually supported version from the supported list and retry".
- 2026-07-28 stdio, Backward Compatibility: probe with ``server/discover``. A DiscoverResult means modern;
  a recognized modern error (such as -32022) means modern - "Do not fall back to initialize"; "any other
  error, or does not respond within a reasonable timeout" means legacy. "The fallback MUST NOT be keyed to
  one specific error code".
- 2025-11-25 Lifecycle, Version Negotiation: the client sends a version (its latest); "If the server
  supports the requested protocol version, it MUST respond with the same version. Otherwise, the server
  MUST respond with another protocol version it supports. This SHOULD be the latest version supported by
  the server." If the client does not support that version "it SHOULD disconnect".

Version strings are dates (YYYY-MM-DD), so for valid versions string order is date order.

Exercise: implement every function that raises NotImplementedError, then run
``.venv/bin/python -m pytest tests/mcp/test_lifecycle_negotiation.py`` and fix the first failure until all pass.
"""

from __future__ import annotations

from typing import Any

PROTOCOL_VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_KEY = "io.modelcontextprotocol/clientInfo"

INVALID_PARAMS = -32602
HEADER_MISMATCH = -32020
MISSING_REQUIRED_CLIENT_CAPABILITY = -32021
UNSUPPORTED_PROTOCOL_VERSION = -32022
# The codes the 2026-07-28 specification defines in its reserved sub-range: a reply carrying one of them
# can only come from a modern server.
MODERN_ERROR_CODES = frozenset({HEADER_MISMATCH, MISSING_REQUIRED_CLIENT_CAPABILITY, UNSUPPORTED_PROTOCOL_VERSION})


def _error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def check_request_meta(request: dict[str, Any], supported: list[str]) -> dict[str, Any] | None:
    """Server side: return ``None`` if ``request`` may be processed, else the JSON-RPC error response.

    - ``params._meta`` missing, not an object, or missing either required key, or the version is not a
      string, or the capabilities are not an object -> -32602, message ``"Invalid params"``, ``data`` =
      ``{"missing": [...]}`` listing the problem keys in the order protocolVersion, clientCapabilities.
    - version not in ``supported`` -> -32022, message ``"Unsupported protocol version"``, ``data`` =
      ``{"supported": supported, "requested": version}``.
    The error response uses the request's ``id``.
    """
    raise NotImplementedError("TODO: check_request_meta - see the docstring")


def choose_version(client_supported: list[str], server_supported: list[str]) -> str | None:
    """Client side: the newest version both sides support, or ``None`` when they share none."""
    raise NotImplementedError("TODO: choose_version - see the docstring")


def classify_probe_reply(reply: dict[str, Any] | None) -> str:
    """Client side, stdio: what a reply to the ``server/discover`` probe says about the server's era.

    ``reply`` is the JSON-RPC response, or ``None`` if none arrived within the timeout.

    - a result containing ``supportedVersions`` -> ``"modern"``
    - an error whose code is in ``MODERN_ERROR_CODES`` -> ``"modern-retry"`` (pick from ``data.supported``)
    - anything else, including ``None``, -32601, -32602 or a result without ``supportedVersions`` ->
      ``"legacy"`` (fall back to ``initialize``)
    """
    raise NotImplementedError("TODO: classify_probe_reply - see the docstring")


def negotiate_legacy(requested: str, server_supported: list[str]) -> str:
    """Server side, legacy ``initialize``: the version to answer with.

    The requested version if supported, otherwise the server's latest supported version.
    """
    raise NotImplementedError("TODO: negotiate_legacy - see the docstring")


def client_accepts_legacy(answered: str, client_supported: list[str]) -> bool:
    """Client side, legacy: ``True`` to continue, ``False`` when the client should disconnect."""
    raise NotImplementedError("TODO: client_accepts_legacy - see the docstring")
