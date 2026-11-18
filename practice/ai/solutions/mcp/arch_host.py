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

# Who decides when each server primitive is used (spec 2026-07-28, server overview).
CONTROL = {"tools": "model", "resources": "application", "prompts": "user"}


def controller(primitive: str) -> str:
    """Return "model", "application" or "user" for "tools", "resources" or "prompts"."""
    if primitive not in CONTROL:
        raise ValueError(f"not a server primitive: {primitive!r}")
    return CONTROL[primitive]


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
        body = dict(params or {})
        body["_meta"] = {
            META + "protocolVersion": PROTOCOL_VERSION,
            META + "clientInfo": self.client_info,
            META + "clientCapabilities": self.capabilities,
        }
        msg_id = self.new_id()
        reply = self.server.handle({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": body})
        if reply is None or reply.get("id") != msg_id:
            raise McpError(-32603, "response does not match the request id")
        if "error" in reply:
            e = reply["error"]
            raise McpError(e["code"], e["message"], e.get("data"))
        return reply["result"]

    def discover(self) -> dict:
        result = self.request("server/discover")
        self.server_capabilities = result["capabilities"]
        return result


class Host:
    """Owns the clients, merges their tools for the model and routes the model's calls."""

    def __init__(self, approve: Callable[[str, str, dict], bool], capabilities: dict | None = None):
        self.approve = approve  # (server name, tool name, arguments) -> user said yes?
        self.capabilities = capabilities if capabilities is not None else {}
        self.clients: dict[str, Client] = {}

    def connect(self, name: str, server) -> Client:
        if SEPARATOR in name:
            raise ValueError(f"server name must not contain {SEPARATOR!r}")
        if name in self.clients:
            raise ValueError(f"already connected: {name}")
        client = Client(server, {"name": "sandpay-host", "version": "1.0.0"}, self.capabilities, name)
        client.discover()
        self.clients[name] = client
        return client

    def all_tools(self) -> list[dict]:
        tools = []
        for name, client in self.clients.items():
            if "tools" not in (client.server_capabilities or {}):
                continue  # never ask a server for a primitive it did not declare
            for tool in client.request("tools/list")["tools"]:
                tools.append({**tool, "name": f"{name}{SEPARATOR}{tool['name']}"})
        return tools

    def call_tool(self, qualified_name: str, arguments: dict) -> dict:
        server_name, sep, tool_name = qualified_name.partition(SEPARATOR)
        if not sep or server_name not in self.clients:
            raise KeyError(f"no server for tool {qualified_name!r}")
        if not self.approve(server_name, tool_name, arguments):
            return {"resultType": "complete", "content": [{"type": "text", "text": "User denied the tool call."}], "isError": True}
        return self.clients[server_name].request("tools/call", {"name": tool_name, "arguments": arguments})
