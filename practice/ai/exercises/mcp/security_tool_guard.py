"""Client-side defences against tool poisoning and rug pulls.

An MCP client puts every connected server's tool definitions in front of the model. The specification says
tool annotations are untrusted unless they come from a trusted server, and Invariant Labs showed that a tool's
description can carry hidden instructions the user never sees ("tool poisoning"), and that a server can change
a definition after the user approved it ("rug pull"). This module gives a host three controls:

- ``scan_text`` / ``scan_tool`` - flag signals of poisoning in every string of a definition.
- ``tool_fingerprint`` and ``ToolPinStore`` - pin each approved definition by hash; changed or new tools are held.
- ``wrap_untrusted`` - mark tool output as data from a named server before it goes to the model.

A scanner is a tripwire, not a proof: a clean scan does not make a server trustworthy. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

HIDDEN_TAG = re.compile(r"<\s*/?\s*(important|system|instructions?|secret|hidden)\b", re.IGNORECASE)
SENSITIVE_PATH = re.compile(r"~/\.ssh|id_rsa|\.env\b|mcp\.json|\.aws/credentials|/etc/passwd", re.IGNORECASE)
CONCEALMENT = re.compile(
    r"\b(do not|don't|never)\s+(tell|mention|inform|show|reveal)\b|\bwithout (telling|informing) the user\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, order=True)
class Finding:
    """One signal: ``code`` names the rule, ``location`` the string it was found in."""

    location: str
    code: str
    detail: str = field(compare=False)


def scan_text(text: str, location: str, other_tool_names: Iterable[str] = ()) -> list:
    """Return the findings for one string, sorted by (location, code); at most one finding per code.

    Codes: ``hidden-tag`` (a tag such as ``<IMPORTANT>``, ``<system>``, ``</instructions>``), ``invisible-chars``
    (any Unicode format character, category ``Cf`` - zero-width spaces, bidirectional controls, tag characters),
    ``sensitive-path`` (``~/.ssh``, ``id_rsa``, ``.env``, ``mcp.json``, ``.aws/credentials``, ``/etc/passwd``),
    ``concealment`` (``do not tell/mention/...``, ``don't ...``, ``never ...``, ``without telling the user``),
    ``cross-tool`` (the name of another server's tool as a whole word - possible shadowing).
    The ``detail`` is the matched text (for ``invisible-chars``: the code points, e.g. ``U+200B``; for
    ``cross-tool``: the tool names found, sorted, comma-separated).
    """
    raise NotImplementedError("TODO: implement scan_text")


def _strings(value, path: str):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for key in sorted(value):
            yield from _strings(value[key], f"{path}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from _strings(item, f"{path}[{i}]")


def scan_tool(tool: Mapping, other_tool_names: Iterable[str] = ()) -> list:
    """Scan every string in a tool definition - ``description``, ``title``, and every string anywhere inside
    ``inputSchema``, ``outputSchema`` and ``annotations`` (property descriptions, enum values, defaults...).

    Locations are dotted paths from the definition: ``description``, ``inputSchema.properties.note.description``,
    ``inputSchema.required[0]``. The tool's own name is excluded from ``other_tool_names``. Sorted findings.
    """
    raise NotImplementedError("TODO: implement scan_tool")


def tool_fingerprint(tool: Mapping) -> str:
    """SHA-256 (hex) of the whole definition as canonical JSON: keys sorted, separators ``(",", ":")``,
    ``ensure_ascii=False``, UTF-8. Any change - description, schema, annotations, an invisible character - changes it."""
    raise NotImplementedError("TODO: implement tool_fingerprint")


@dataclass
class PinReport:
    allowed: list
    added: list
    removed: list
    changed: list

    @property
    def clean(self) -> bool:
        return not (self.added or self.removed or self.changed)


class ToolPinStore:
    """Remembers the fingerprint of every tool the user approved, per server."""

    def __init__(self):
        self._pins: dict = {}

    def approve(self, server: str, tools: Iterable[Mapping]) -> None:
        """Pin these definitions for ``server`` (adding to, or replacing, earlier pins of the same names)."""
        raise NotImplementedError("TODO: implement approve")

    def check(self, server: str, tools: Iterable[Mapping]) -> PinReport:
        """Compare a fresh ``tools/list`` with the pins.

        ``allowed``: names whose definition is unchanged since approval. ``added``: names never approved.
        ``changed``: approved names whose fingerprint differs. ``removed``: approved names that are missing.
        All four lists sorted. A server with no pins has every tool in ``added``.
        """
        raise NotImplementedError("TODO: implement check")


def wrap_untrusted(server: str, tool: str, text: str) -> str:
    """Wrap tool output as delimited, attributed data for the model::

        <tool-output server="fx-rates" tool="convert_currency" trust="untrusted">
        ...text...
        </tool-output>

    Any ``<tool-output`` or ``</tool-output`` inside ``text`` (any case) gets its ``<`` replaced by ``&lt;`` so the
    output cannot close the wrapper early or open a fake one. Delimiters reduce, but do not remove, the risk of
    prompt injection.
    """
    raise NotImplementedError("TODO: implement wrap_untrusted")
