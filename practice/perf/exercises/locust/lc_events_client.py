"""A Locust client for a service that does not speak HTTP - EXERCISE.

The SandPay ledger (support/lc_events_fixture.py) is a TCP service: you send one text line, it answers one text
line, ``\\n`` ends each.

    BALANCE <merchant>                 -> OK <minor units>
    TRANSFER <from> <to> <amount>      -> OK tx_<n>   or   ERR insufficient_funds
    (anything else)                    -> ERR unknown_command

Locust has no client for that, so a call is only recorded if YOUR client reports it. Build ``LedgerClient``:

- ``LedgerClient(host, request_event, timeout=5.0)``: ``host`` is ``"127.0.0.1:<port>"``; open one TCP
  connection (``socket.create_connection``). ``request_event`` is Locust's ``environment.events.request`` (a test
  passes a stand-in that records what is fired). Do not import Locust here.
- ``balance(merchant)`` and ``transfer(source, target, amount_minor)`` send the line and return the reply text
  (``"OK ..."``), or None when the call failed.
- Every call fires ONE request event with these arguments (see Locust's "Testing other systems/protocols"):
    request_type="LEDGER", name="BALANCE" or "TRANSFER" (never the merchant or amounts - that would make a
    statistics row per value), response_time in MILLISECONDS measured with ``time.perf_counter()``,
    response_length=len(reply), response=reply, context={}, start_time=time.time(), and
    exception=None for ``OK ...``, ``LedgerError(<reason>)`` for ``ERR <reason>``.
  A socket error (timeout, reset, the server closing the connection) is a failed request too: fire it with that
  exception instead of letting it crash the user.
- ``close()`` closes the connection.

Test: .venv/bin/python -m pytest tests/locust/test_lc_events_client.py   (also needs lc_events_ledger_locustfile.py)
"""

import socket  # noqa: F401
import time  # noqa: F401


class LedgerError(Exception):
    """The ledger answered ``ERR <reason>``; ``str(error)`` is the reason."""


class LedgerClient:
    def __init__(self, host: str, request_event, timeout: float = 5.0) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def balance(self, merchant: str) -> str | None:
        raise NotImplementedError

    def transfer(self, source: str, target: str, amount_minor: int) -> str | None:
        raise NotImplementedError
