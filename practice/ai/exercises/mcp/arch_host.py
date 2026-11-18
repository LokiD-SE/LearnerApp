"""A minimal MCP host: one client per server, per-request _meta, a merged tool list and routing.

Plain Python against in-process servers (``handle(message) -> response``); no transport, no SDK.
Follows the architecture of the MCP specification 2026-07-28: the host owns the clients, the
conversation and the consent decisions; each client talks to exactly one server.
"""

from __future__ import annotations

from typing import Callable

PROTOCOL_VERSION = "2026-07-28"
META = "io.modelcontextprotocol/"
SEPARATOR = "__"


def controller(primitive: str) -> str:
    """Who decides when a server primitive is used: "model", "application" or "user".

    TODO: tools, resources and prompts (the spec's control hierarchy); anything else raises ValueError.
    """
    raise NotImplementedError("controller")


class McpError(Exception):
    def __init__(self, code: int, message: str, data=None):
        super().__init__(f"{code} {message}")
        self.code, self.message, self.data = code, message, data


class Client:
    """Talks to exactly one server and attaches the per-request _meta to every request."""

    def __init__(self, server, client_info: dict, capabilities: dict, id_prefix: str):
        self.server = server
        self.client_info = client_info
        self.capabilities = capabilities
        self._prefix = id_prefix
        self._next = 0
        self.server_capabilities: dict | None = None

    def new_id(self) -> str:
        self._next += 1
        return f"{self._prefix}-{self._next}"

    def request(self, method: str, params: dict | None = None) -> dict:
        """Send one request and return its ``result``.

        TODO: copy params (never change the caller's dict) and add ``_meta`` with META + "protocolVersion",
        META + "clientInfo" and META + "clientCapabilities"; use a new id; pass the message to
        ``self.server.handle``; raise McpError(-32603, ...) if the reply is missing or its id differs;
        raise McpError(code, message, data) for an error reply; otherwise return reply["result"].
        """
        raise NotImplementedError("Client.request")

    def discover(self) -> dict:
        """TODO: send server/discover, keep result["capabilities"] in server_capabilities, return the result."""
        raise NotImplementedError("Client.discover")


class Host:
    """Owns the clients, merges their tools for the model and routes the model's calls."""

    def __init__(self, approve: Callable[[str, str, dict], bool], capabilities: dict | None = None):
        self.approve = approve  # (server name, tool name, arguments) -> user said yes?
        self.capabilities = capabilities if capabilities is not None else {}
        self.clients: dict[str, Client] = {}

    def connect(self, name: str, server) -> Client:
        """TODO: reject names containing SEPARATOR and duplicate names (ValueError); create a Client with
        client_info {"name": "sandpay-host", "version": "1.0.0"}, the host's capabilities and ``name`` as
        id prefix; discover BEFORE storing it (a failed discover must not leave a client behind)."""
        raise NotImplementedError("Host.connect")

    def all_tools(self) -> list[dict]:
        """TODO: tools/list on every client whose server declared the ``tools`` capability (skip the
        others - never send them tools/list); rename each tool "<server name>__<tool name>"."""
        raise NotImplementedError("Host.all_tools")

    def call_tool(self, qualified_name: str, arguments: dict) -> dict:
        """TODO: split "<server>__<tool>" (KeyError if no separator or unknown server); ask ``approve``;
        if denied, return a complete result with isError True and a text containing "denied" WITHOUT
        contacting the server; else send tools/call with the server's own tool name and the arguments."""
        raise NotImplementedError("Host.call_tool")
