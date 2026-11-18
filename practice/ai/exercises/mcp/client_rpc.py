"""The JSON-RPC layer of an MCP client: one stdio connection, requests matched to responses by id.

Exercise: fill in every function that raises NotImplementedError; the tests
in tests/mcp/test_client_rpc.py say what each must do. Reference solution: solutions/mcp/client_rpc.py. Protocol revision 2026-07-28 (stateless: no ``initialize`` handshake; every request
carries its protocol version and client capabilities in ``params._meta``).
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from typing import Any, Callable

PROTOCOL_VERSION = "2026-07-28"
META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CLIENT = "io.modelcontextprotocol/clientInfo"
META_CAPS = "io.modelcontextprotocol/clientCapabilities"
KNOWN_RESULT_TYPES = {"complete", "input_required"}


class McpError(Exception):
    """A JSON-RPC error response from the server (a protocol error, not a tool execution error)."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.data = data


class RequestTimeout(Exception):
    """No response arrived in time; the client has already sent notifications/cancelled."""


class ProtocolError(Exception):
    """The peer broke the protocol (bad JSON, an unknown resultType, the connection closed)."""


class StdioTransport:
    """Launches a server subprocess and exchanges newline-delimited JSON-RPC messages with it."""

    def __init__(self, command: list[str]):
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._lines: queue.Queue[str | None] = queue.Queue()
        self.stderr_lines: list[str] = []
        threading.Thread(target=self._pump, args=(self.process.stdout, self._lines.put), daemon=True).start()
        threading.Thread(target=self._pump, args=(self.process.stderr, self.stderr_lines.append), daemon=True).start()

    @staticmethod
    def _pump(stream, sink: Callable[[Any], None]) -> None:
        for line in stream:
            sink(line.rstrip("\n"))
        sink(None)

    def send(self, line: str) -> None:
        if "\n" in line:
            raise ValueError("a stdio message must not contain a newline")
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()

    def receive(self, timeout: float) -> str | None:
        """The next line from the server's stdout, or None if nothing arrives within ``timeout`` seconds.

        Raises ProtocolError when the server has closed its stdout (exited)."""
        try:
            line = self._lines.get(timeout=max(timeout, 0))
        except queue.Empty:
            return None
        if line is None:
            self._lines.put(None)  # keep reporting the closed stream
            raise ProtocolError("server closed its output stream")
        return line

    def close(self, grace: float = 1.0) -> int:
        """Shuts the server down as the stdio transport page says: close its stdin, wait, then terminate,
        then kill. Returns the exit code."""
        raise NotImplementedError("TODO: close stdin, wait up to `grace` seconds, then terminate(), wait again, then kill(); return the exit code.")


def request_meta(client_info: dict, capabilities: dict, protocol_version: str = PROTOCOL_VERSION) -> dict:
    """The per-request protocol fields every 2026-07-28 request carries in ``params._meta``."""
    raise NotImplementedError("TODO: return the three io.modelcontextprotocol/* fields as a dict.")


class RpcClient:
    """Sends requests and notifications over a transport and matches responses to requests by id."""

    def __init__(
        self,
        transport,
        client_info: dict | None = None,
        capabilities: dict | None = None,
        protocol_version: str = PROTOCOL_VERSION,
        on_notification: Callable[[dict], None] | None = None,
    ):
        self.transport = transport
        self.client_info = client_info or {"name": "sandpay-support-host", "version": "1.0.0"}
        self.capabilities = capabilities if capabilities is not None else {}
        self.protocol_version = protocol_version
        self.on_notification = on_notification or (lambda message: None)
        self._next_id = 0
        self.cancelled: set[int] = set()
        self.ignored: list[dict] = []  # responses nobody was waiting for (late replies to cancelled requests)

    def new_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def notify(self, method: str, params: dict | None = None) -> None:
        raise NotImplementedError('TODO: write {"jsonrpc": "2.0", "method": ..., "params": ...} (no "id") as one line.')

    def request(self, method: str, params: dict | None = None, timeout: float = 5.0, meta: dict | None = None) -> dict:
        """Sends one request and returns its ``result``.

        - adds the per-request ``_meta`` (plus any extra ``meta`` keys, such as ``progressToken``);
        - passes notifications that arrive meanwhile to ``on_notification``;
        - skips responses to other ids (recording them in ``ignored``);
        - raises McpError for an error response, ProtocolError for an unknown ``resultType``;
        - on timeout sends ``notifications/cancelled`` for the id and raises RequestTimeout.
        A result without ``resultType`` (an earlier-revision server) is treated as ``"complete"``.
        """
        raise NotImplementedError("TODO: new id, params with _meta, send one line, then read lines until the response with this id.")
