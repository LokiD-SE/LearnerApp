"""One tool list for the model, built from the tools of many MCP servers.

A host keeps one MCP client per server. Each server's ``tools/list`` result names its tools; names are unique
only *within* a server (MCP 2026-07-28, Tools, "Tool Names"), so two servers may both offer ``search``. The
spec says an aggregating client "SHOULD implement a disambiguation strategy such as prefixing tool names with
a server identifier", and that the server's own ``name`` from ``serverInfo`` "SHOULD NOT be relied upon for
disambiguation" - so the host uses its own configured server id.

This catalog prefixes every tool as ``<server_id>__<tool>`` (mode ``"always"``) or only colliding tools (mode
``"collision"``), keeps a reverse map to route calls, and records a warning instead of failing when one
server sends a bad definition.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SEPARATOR = "__"
MAX_NAME = 128  # the spec's SHOULD: 1 to 128 characters
TOOL_NAME = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")  # the spec's SHOULD character set
SERVER_ID = re.compile(r"^[a-z0-9][a-z0-9\-]{0,31}$")  # host-chosen: no "_", so "__" splits unambiguously


def namespaced(server_id: str, tool_name: str) -> str:
    """``server_id + "__" + tool_name``; ValueError if the server id or the result breaks the naming rules."""
    if not SERVER_ID.match(server_id):
        raise ValueError(f"invalid server id {server_id!r}: use 1-32 of a-z, 0-9 and '-', starting with a letter or digit")
    name = f"{server_id}{SEPARATOR}{tool_name}"
    if len(name) > MAX_NAME:
        raise ValueError(f"namespaced name is {len(name)} characters; the limit is {MAX_NAME}")
    if not TOOL_NAME.match(name):
        raise ValueError(f"namespaced name {name!r} has characters outside A-Z a-z 0-9 _ - .")
    return name


@dataclass
class ToolCatalog:
    mode: str = "always"  # "always" or "collision"
    warnings: list[str] = field(default_factory=list)
    _servers: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in ("always", "collision"):
            raise ValueError("mode must be 'always' or 'collision'")

    def add_server(self, server_id: str, tools: list[dict[str, Any]]) -> int:
        """Register one server's ``tools/list`` tools; returns how many were accepted.

        Skips (with a warning) tools whose name breaks the character rules, and later duplicates of a name
        within the same server. A duplicate *server id* is a configuration error: ValueError.
        """
        namespaced(server_id, "x")  # validates the id
        if server_id in self._servers:
            raise ValueError(f"server id {server_id!r} is already registered")
        accepted: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tool in tools:
            name = tool.get("name", "")
            if not isinstance(name, str) or not TOOL_NAME.match(name):
                self.warnings.append(f"{server_id}: skipped tool {name!r} - invalid name")
                continue
            if name in seen:
                self.warnings.append(f"{server_id}: skipped duplicate tool {name!r}")
                continue
            try:
                namespaced(server_id, name)
            except ValueError as err:
                self.warnings.append(f"{server_id}: skipped tool {name!r} - {err}")
                continue
            seen.add(name)
            accepted.append(tool)
        self._servers[server_id] = accepted
        return len(accepted)

    def remove_server(self, server_id: str) -> None:
        self._servers.pop(server_id, None)

    def _counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for tools in self._servers.values():
            for tool in tools:
                counts[tool["name"]] = counts.get(tool["name"], 0) + 1
        return counts

    def _exposed_name(self, server_id: str, name: str, counts: dict[str, int]) -> str:
        if self.mode == "always" or counts[name] > 1:
            return namespaced(server_id, name)
        return name

    def exposed(self) -> list[dict[str, Any]]:
        """Tool definitions for the model, in a deterministic order (server order, then each server's order).

        Each keeps its ``inputSchema``; the description is prefixed with ``[server_id] `` so the model can
        tell where a tool comes from.
        """
        counts = self._counts()
        out = []
        for server_id, tools in self._servers.items():
            for tool in tools:
                out.append(
                    {
                        "name": self._exposed_name(server_id, tool["name"], counts),
                        "description": f"[{server_id}] {tool.get('description', '')}".rstrip(),
                        "inputSchema": tool.get("inputSchema", {"type": "object"}),
                    }
                )
        return out

    def resolve(self, exposed_name: str) -> tuple[str, str]:
        """Map a name the model used back to ``(server_id, original tool name)``; KeyError if unknown."""
        counts = self._counts()
        for server_id, tools in self._servers.items():
            for tool in tools:
                if self._exposed_name(server_id, tool["name"], counts) == exposed_name:
                    return server_id, tool["name"]
        raise KeyError(exposed_name)
