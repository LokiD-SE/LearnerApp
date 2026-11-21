"""A Locust client for a service that does not speak HTTP - SOLUTION.

The SandPay ledger (support/lc_events_fixture.py) answers one text line per request line. Locust has no client
for it, so this one measures each call itself and reports it with the ``request`` event - exactly what
``HttpSession`` does for HTTP. ``LedgerClient`` never imports Locust (``request_event`` is passed in), so its tests
run without Locust; the user class is in lc_events_ledger_locustfile.py.
"""

import socket
import time


class LedgerError(Exception):
    """The ledger answered ``ERR <reason>``; ``str(error)`` is the reason."""


class LedgerClient:
    def __init__(self, host: str, request_event, timeout: float = 5.0) -> None:
        address, _, port = host.rpartition(":")
        self._request_event = request_event
        self._sock = socket.create_connection((address, int(port)), timeout=timeout)
        self._reader = self._sock.makefile("rb")

    def close(self) -> None:
        self._reader.close()
        self._sock.close()

    def balance(self, merchant: str) -> str | None:
        return self._call("BALANCE", f"BALANCE {merchant}")

    def transfer(self, source: str, target: str, amount_minor: int) -> str | None:
        return self._call("TRANSFER", f"TRANSFER {source} {target} {amount_minor}")

    def _call(self, name: str, line: str) -> str | None:
        meta = {"request_type": "LEDGER", "name": name, "start_time": time.time(), "response": None,
                "response_length": 0, "context": {}, "exception": None}
        started = time.perf_counter()
        try:
            self._sock.sendall(line.encode() + b"\n")
            reply = self._reader.readline().decode().rstrip("\n")
            if not reply:
                raise ConnectionError("the ledger closed the connection")
            meta["response"], meta["response_length"] = reply, len(reply)
            if reply.startswith("ERR "):
                meta["exception"] = LedgerError(reply[4:])
        except OSError as error:  # timeouts and resets are failed requests too, not crashes
            meta["exception"] = error
        meta["response_time"] = (time.perf_counter() - started) * 1000
        self._request_event.fire(**meta)
        return meta["response"] if meta["exception"] is None else None
