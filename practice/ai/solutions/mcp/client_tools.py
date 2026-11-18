"""Tool discovery for an MCP client: page through tools/list, cache it, and turn MCP tools into model tools.

Reference solution. Works with any object that has ``request(method, params) -> result`` (``RpcClient`` from
``client_rpc``, or a fake in the tests).
"""

from __future__ import annotations

import re
from typing import Any, Callable

from mcp.client_rpc import ProtocolError

# Anthropic's Messages API tool-name rule ("Must match the regex ^[a-zA-Z0-9_-]{1,128}$"). MCP tool names may
# also contain dots, so a host must map names before it offers them to this provider.
PROVIDER_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
SEPARATOR = "__"


def list_tool_pages(client, max_pages: int = 50) -> list[dict]:
    """Every ``tools/list`` result, following ``nextCursor`` until it is absent.

    Cursors are opaque: an empty string is a valid cursor, not the end. A cursor seen twice, or more than
    ``max_pages`` pages, raises ProtocolError (a client-side guard against a looping server)."""
    pages: list[dict] = []
    seen: set[str] = set()
    cursor: str | None = None
    for _ in range(max_pages):
        result = client.request("tools/list", {} if cursor is None else {"cursor": cursor})
        pages.append(result)
        cursor = result.get("nextCursor")
        if cursor is None:
            return pages
        if cursor in seen:
            raise ProtocolError(f"server repeated cursor {cursor!r}")
        seen.add(cursor)
    raise ProtocolError(f"more than {max_pages} pages of tools")


def list_all_tools(client, max_pages: int = 50) -> list[dict]:
    """The tools of every page, in the server's order."""
    return [tool for page in list_tool_pages(client, max_pages) for tool in page.get("tools", [])]


def check_tool(tool: Any) -> str | None:
    """Why a tool definition cannot be offered to a model, or None if it can."""
    if not isinstance(tool, dict):
        return "not an object"
    name = tool.get("name")
    if not isinstance(name, str) or not name:
        return "missing name"
    schema = tool.get("inputSchema")
    if not isinstance(schema, dict):
        return f"{name}: inputSchema must be a JSON Schema object"
    if schema.get("type") not in (None, "object"):
        return f"{name}: inputSchema must describe an object"
    return None


def provider_name(server_key: str, tool_name: str) -> str:
    """``<server_key>__<tool name>`` with characters the provider rejects replaced by ``_``."""
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", f"{server_key}{SEPARATOR}{tool_name}")
    if not PROVIDER_NAME.match(name):
        raise ValueError(f"tool name {name!r} cannot be offered to the model (1-128 characters)")
    return name


def to_provider_tools(server_key: str, tools: list[dict]) -> tuple[list[dict], dict[str, tuple[str, str]], list[str]]:
    """Converts MCP tools to Messages-API tools.

    Returns ``(provider_tools, routes, skipped)``: ``routes`` maps each provider name back to
    ``(server_key, MCP tool name)`` - the original name, dots and all - and ``skipped`` holds a reason for
    every definition that was left out. Two MCP tools that map to the same provider name are both skipped."""
    provider_tools: list[dict] = []
    routes: dict[str, tuple[str, str]] = {}
    skipped: list[str] = []
    clashes: set[str] = set()
    for tool in tools:
        problem = check_tool(tool)
        if problem:
            skipped.append(problem)
            continue
        name = provider_name(server_key, tool["name"])
        if name in routes:
            clashes.add(name)
            continue
        routes[name] = (server_key, tool["name"])
        provider_tools.append(
            {
                "name": name,
                "description": tool.get("description") or tool.get("title") or tool["name"],
                "input_schema": tool["inputSchema"],
            }
        )
    for name in sorted(clashes):
        skipped.append(f"{name}: two MCP tools map to this name")
        del routes[name]
    provider_tools = [t for t in provider_tools if t["name"] not in clashes]
    return provider_tools, routes, skipped


class ToolCatalog:
    """Caches one server's tool list using the result's ``ttlMs`` hint and list_changed invalidation."""

    def __init__(self, client, clock: Callable[[], float]):
        self.client = client
        self.clock = clock  # seconds, like time.monotonic
        self._tools: list[dict] | None = None
        self._fresh_until = 0.0
        self.fetches = 0

    def tools(self) -> list[dict]:
        """The cached list while fresh (``now < t_received + ttlMs``), otherwise a new fetch of every page.

        The TTL comes from the first page; an absent or negative ``ttlMs`` counts as 0 (stale at once)."""
        now = self.clock()
        if self._tools is not None and now < self._fresh_until:
            return self._tools
        pages = list_tool_pages(self.client)
        ttl_ms = pages[0].get("ttlMs")
        ttl_ms = ttl_ms if isinstance(ttl_ms, (int, float)) and ttl_ms > 0 else 0
        tools = [tool for page in pages for tool in page.get("tools", [])]
        self.fetches += 1
        received = self.clock()
        self._tools = tools
        self._fresh_until = received + ttl_ms / 1000
        return tools

    def on_notification(self, message: dict) -> None:
        """Pass server notifications here; ``notifications/tools/list_changed`` makes the cache stale."""
        if message.get("method") == "notifications/tools/list_changed":
            self._fresh_until = 0.0

