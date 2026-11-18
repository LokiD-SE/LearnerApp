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
    raise NotImplementedError("TODO: namespaced")


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
        raise NotImplementedError("TODO: add_server")

    def remove_server(self, server_id: str) -> None:
        self._servers.pop(server_id, None)

    def _counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for tools in self._servers.values():
            for tool in tools:
                counts[tool["name"]] = counts.get(tool["name"], 0) + 1
        return counts

    def _exposed_name(self, server_id: str, name: str, counts: dict[str, int]) -> str:
        """The name the model sees: always namespaced in mode "always"; in mode "collision" only when
        ``counts[name] > 1`` (more than one server offers that name)."""
        raise NotImplementedError("TODO: _exposed_name")

    def exposed(self) -> list[dict[str, Any]]:
        """Tool definitions for the model, in a deterministic order (server order, then each server's order).

        Each keeps its ``inputSchema``; the description is prefixed with ``[server_id] `` so the model can
        tell where a tool comes from.
        """
        raise NotImplementedError("TODO: exposed")

    def resolve(self, exposed_name: str) -> tuple[str, str]:
        """Map a name the model used back to ``(server_id, original tool name)``; KeyError if unknown."""
        raise NotImplementedError("TODO: resolve")
