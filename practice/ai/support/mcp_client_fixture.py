"""A small MCP server over stdio for the client exercises (lesson: Building an MCP client).

It speaks the stateless 2026-07-28 revision of the Model Context Protocol by hand - no SDK - so the client
tests have a real subprocess to talk to:

- newline-delimited JSON-RPC 2.0 on stdin/stdout, logs on stderr, exits when stdin closes;
- every request must carry ``_meta`` with ``io.modelcontextprotocol/protocolVersion`` and
  ``io.modelcontextprotocol/clientCapabilities``; a missing field is ``-32602``, an unknown version is
  ``-32022`` (UnsupportedProtocolVersion) with the supported list;
- ``server/discover``, ``tools/list`` (two tools per page, opaque cursors) and ``tools/call``;
- tool execution errors come back as ``isError: true``; an unknown tool is a protocol error (``-32602``);
- ``confirm_refund`` asks for the user's confirmation with a multi round-trip ``InputRequiredResult``
  (an ``elicitation/create`` input request plus ``requestState``);
- ``slow_report`` takes ``seconds`` to answer and sends ``notifications/progress`` when the request has a
  ``progressToken``; it stops on ``notifications/cancelled`` unless started with ``--ignore-cancel``.

SandPay is fictional and every id here is synthetic. Run it by hand to watch the wire:

    printf '%s\\n' '{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{...}}}' | python mcp_client_fixture.py

Command-line flags (tests only): ``--ignore-cancel`` answers cancelled requests anyway (a late reply);
``--ignore-eof`` keeps running after stdin closes (a server that must be terminated); ``--legacy`` behaves
like a 2025-11-25 server that only knows the ``initialize`` handshake.
"""

from __future__ import annotations

import base64
import json
import os
import select
import sys
import time

PROTOCOL_VERSION = "2026-07-28"
SUPPORTED = [PROTOCOL_VERSION]
SERVER_INFO = {"name": "sandpay-payouts", "version": "0.3.0"}
META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CAPS = "io.modelcontextprotocol/clientCapabilities"
PAGE_SIZE = 2

PAYOUTS = {
    "po_1039": {"payout_id": "po_1039", "merchant_id": "m-204", "amount_minor": 125000, "currency": "EUR", "status": "paid"},
    "po_1042": {"payout_id": "po_1042", "merchant_id": "m-204", "amount_minor": 98050, "currency": "EUR", "status": "in_transit"},
    "po_2001": {"payout_id": "po_2001", "merchant_id": "m-311", "amount_minor": 4300, "currency": "GBP", "status": "failed"},
}
REFUNDS = {"rf_7": {"refund_id": "rf_7", "payment_id": "pay_88", "amount_minor": 8400, "currency": "EUR", "status": "pending"}}

ID_SCHEMA = {"type": "string", "pattern": "^po_[0-9]+$", "description": "SandPay payout id, for example po_1039."}
TOOLS = [
    {
        "name": "get_payout",
        "title": "Payout lookup",
        "description": "Look up one SandPay payout by id: merchant, amount in minor units, currency and status.",
        "inputSchema": {"type": "object", "properties": {"payout_id": ID_SCHEMA}, "required": ["payout_id"], "additionalProperties": False},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "list_payouts",
        "description": "List the payouts of one SandPay merchant, newest first.",
        "inputSchema": {
            "type": "object",
            "properties": {"merchant_id": {"type": "string", "description": "Merchant id, for example m-204."}},
            "required": ["merchant_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "refunds.status",
        "description": "Return the status of one SandPay refund by id, for example rf_7.",
        "inputSchema": {
            "type": "object",
            "properties": {"refund_id": {"type": "string", "description": "Refund id."}},
            "required": ["refund_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "confirm_refund",
        "description": "Ask the user to confirm, then mark a pending SandPay refund as approved. Moves money.",
        "inputSchema": {
            "type": "object",
            "properties": {"refund_id": {"type": "string", "description": "Refund id."}},
            "required": ["refund_id"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": True},
    },
    {
        "name": "slow_report",
        "description": "Build a payout reconciliation report; takes the given number of seconds.",
        "inputSchema": {
            "type": "object",
            "properties": {"seconds": {"type": "number", "minimum": 0, "maximum": 2}},
            "required": ["seconds"],
            "additionalProperties": False,
        },
    },
]

IGNORE_CANCEL = "--ignore-cancel" in sys.argv
IGNORE_EOF = "--ignore-eof" in sys.argv
LEGACY = "--legacy" in sys.argv
_backlog: list[str] = []


class LineReader:
    """Reads stdin lines straight from the file descriptor, so select() never misses buffered lines."""

    def __init__(self, fd: int):
        self.fd = fd
        self.buffer = b""
        self.eof = False

    def readline(self, timeout: float | None = None) -> str | None:
        """The next line; "" at end of input; None if ``timeout`` seconds pass first."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while b"\n" not in self.buffer and not self.eof:
            left = None if deadline is None else max(deadline - time.monotonic(), 0)
            ready, _, _ = select.select([self.fd], [], [], left)
            if not ready:
                return None
            chunk = os.read(self.fd, 65536)
            if not chunk:
                self.eof = True
            self.buffer += chunk
        if b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            return line.decode("utf-8") + "\n"
        line, self.buffer = self.buffer, b""
        return line.decode("utf-8")


STDIN = LineReader(sys.stdin.fileno())


def log(text: str) -> None:
    print(f"[sandpay-payouts] {text}", file=sys.stderr, flush=True)


def send(message: dict) -> None:
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def error(req_id, code: int, message: str, data=None) -> dict:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def result(req_id, body: dict) -> dict:
    body = {"resultType": "complete", **body}
    body.setdefault("_meta", {})["io.modelcontextprotocol/serverInfo"] = SERVER_INFO
    return {"jsonrpc": "2.0", "id": req_id, "result": body}


def text_result(req_id, text: str, structured=None, is_error: bool = False) -> dict:
    body: dict = {"content": [{"type": "text", "text": text}], "isError": is_error}
    if structured is not None:
        body["structuredContent"] = structured
    return result(req_id, body)


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).decode()


def decode_cursor(cursor: str) -> int:
    offset = json.loads(base64.urlsafe_b64decode(cursor.encode()))["o"]
    if not isinstance(offset, int) or offset < 0 or offset >= len(TOOLS):
        raise ValueError(cursor)
    return offset


def wait(seconds: float, req_id) -> bool:
    """Sleeps up to ``seconds`` while reading stdin; returns False if ``req_id`` was cancelled meanwhile."""
    deadline = time.monotonic() + seconds
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            return True
        line = STDIN.readline(timeout=left)
        if line is None or line == "":
            if line == "":
                _backlog.append("")
            return True
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _backlog.append(line)
            continue
        if msg.get("method") == "notifications/cancelled":
            cancelled = msg.get("params", {}).get("requestId")
            log(f"cancel received for {cancelled!r}")
            if cancelled == req_id and not IGNORE_CANCEL:
                return False
        else:
            _backlog.append(line)


def call_tool(req_id, params: dict, meta: dict) -> dict | None:
    name = params.get("name")
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        return error(req_id, -32602, "arguments must be an object")
    if name == "get_payout":
        payout = PAYOUTS.get(args.get("payout_id", ""))
        if payout is None:
            return text_result(req_id, f"Payout {args.get('payout_id')!r} not found. Ids look like po_1039.", is_error=True)
        return text_result(req_id, json.dumps(payout), structured=payout)
    if name == "list_payouts":
        rows = [p for p in PAYOUTS.values() if p["merchant_id"] == args.get("merchant_id")]
        if not rows:
            return text_result(req_id, f"No payouts for merchant {args.get('merchant_id')!r}.", is_error=True)
        return text_result(req_id, json.dumps(rows), structured=rows)
    if name == "refunds.status":
        refund = REFUNDS.get(args.get("refund_id", ""))
        if refund is None:
            return text_result(req_id, f"Refund {args.get('refund_id')!r} not found.", is_error=True)
        return text_result(req_id, f"Refund {refund['refund_id']} is {refund['status']}.", structured=refund)
    if name == "confirm_refund":
        return confirm_refund(req_id, params, args, meta)
    if name == "slow_report":
        progress = meta.get("progressToken")
        seconds = float(args.get("seconds", 0))
        if progress is not None:
            send({"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progressToken": progress, "progress": 0, "total": 1}})
        if not wait(seconds, req_id):
            log(f"request {req_id!r} cancelled; no response sent")
            return None
        return text_result(req_id, "Reconciliation report: 3 payouts, 0 differences.")
    return error(req_id, -32602, f"Unknown tool: {name}")


def confirm_refund(req_id, params: dict, args: dict, meta: dict) -> dict:
    refund_id = args.get("refund_id", "")
    refund = REFUNDS.get(refund_id)
    if refund is None:
        return text_result(req_id, f"Refund {refund_id!r} not found.", is_error=True)
    answers = params.get("inputResponses") or {}
    state = params.get("requestState")
    answer = answers.get("confirm")
    if answer is None:
        if "elicitation" not in (meta.get(META_CAPS) or {}):
            return error(req_id, -32021, "Missing required client capability", {"requiredCapabilities": {"elicitation": {}}})
        # Teaching fixture: real servers MUST integrity-protect requestState (HMAC or AEAD) - see the MRTR page.
        state = base64.urlsafe_b64encode(json.dumps({"refund_id": refund_id}).encode()).decode()
        body = {
            "resultType": "input_required",
            "inputRequests": {
                "confirm": {
                    "method": "elicitation/create",
                    "params": {
                        "mode": "form",
                        "message": f"Approve refund {refund_id} of {refund['amount_minor'] / 100:.2f} {refund['currency']}?",
                        "requestedSchema": {
                            "type": "object",
                            "properties": {"approve": {"type": "boolean", "title": "Approve the refund"}},
                            "required": ["approve"],
                        },
                    },
                }
            },
            "requestState": state,
        }
        return {"jsonrpc": "2.0", "id": req_id, "result": body}
    try:
        echoed = json.loads(base64.urlsafe_b64decode((state or "").encode()))
    except ValueError:
        echoed = None
    if not echoed or echoed.get("refund_id") != refund_id:
        return error(req_id, -32602, "requestState missing or does not match this request")
    if answer.get("action") != "accept":
        return text_result(req_id, f"Refund {refund_id} not approved: the user chose {answer.get('action')!r}.", is_error=True)
    if (answer.get("content") or {}).get("approve") is not True:
        return text_result(req_id, f"Refund {refund_id} not approved: the user said no.", is_error=True)
    return text_result(req_id, f"Refund {refund_id} approved.", structured={"refund_id": refund_id, "status": "approved"})


def handle(msg: dict) -> dict | None:
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
    method = msg["method"]
    req_id = msg.get("id")
    if req_id is None:  # a notification: never answered
        return None  # a late notifications/cancelled is ignored: that request was already answered
    params = msg.get("params") or {}
    if LEGACY:
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO}}
        return error(req_id, -32600, "Server not initialized")
    meta = params.get("_meta") or {}
    if META_VERSION not in meta or META_CAPS not in meta:
        return error(req_id, -32602, "Invalid params: _meta must include protocolVersion and clientCapabilities")
    if meta[META_VERSION] not in SUPPORTED:
        return error(req_id, -32022, "Unsupported protocol version", {"supported": SUPPORTED, "requested": meta[META_VERSION]})
    if method == "server/discover":
        return result(req_id, {"supportedVersions": SUPPORTED, "capabilities": {"tools": {"listChanged": True}}, "ttlMs": 60000, "cacheScope": "public"})
    if method == "tools/list":
        cursor = params.get("cursor")
        try:
            start = 0 if cursor is None else decode_cursor(cursor)
        except (ValueError, KeyError, TypeError):
            return error(req_id, -32602, "Invalid cursor")
        page = TOOLS[start : start + PAGE_SIZE]
        body = {"tools": page, "ttlMs": 60000, "cacheScope": "public"}
        if start + PAGE_SIZE < len(TOOLS):
            body["nextCursor"] = encode_cursor(start + PAGE_SIZE)
        return result(req_id, body)
    if method == "tools/call":
        return call_tool(req_id, params, meta)
    return error(req_id, -32601, f"Method not found: {method}")


def main() -> None:
    log(f"started (protocol {PROTOCOL_VERSION}{', legacy' if LEGACY else ''})")
    while True:
        line = _backlog.pop(0) if _backlog else STDIN.readline()
        if not line:
            break
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            send(error(None, -32700, "Parse error"))
            continue
        reply = handle(msg)
        if reply is not None:
            send(reply)
    log("stdin closed")
    if IGNORE_EOF:
        while True:  # a misbehaving server: the client has to terminate it
            time.sleep(0.05)


if __name__ == "__main__":
    main()
