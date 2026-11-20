"""A last-resort error handler that fails safe - ASVS 5.0.0 requirements 16.5.1 and 16.5.4.

Exercise - fill in the TODOs; ``tests/web/test_misconf_handler.py`` checks your work. The OWASP Error Handling
Cheat Sheet's target: "when an unexpected error occurs then a generic response is returned by the application
but the error details are logged server side for investigation, and not returned to the user."

- ASVS 16.5.1: "a generic message is returned to the consumer when an unexpected or security-sensitive error
  occurs, ensuring no exposure of sensitive internal system data such as stack traces, queries, secret keys,
  and tokens".
- ASVS 16.5.4: a "last resort" handler "catch[es] all unhandled exceptions ... to avoid losing error details
  that must go to log files".

``ClientError`` is an error the caller caused and may be told about (400, 401, 403, 404, 409 ...): its message
is written for the client. Anything else is unexpected.
"""

from __future__ import annotations

import traceback


class ClientError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def make_handler(log: list[dict]):
    """Return ``handle(exc, reference) -> (status, body)``; unexpected errors are logged to ``log``.

    TODO: ``handle`` returns ``(exc.status, {"error": exc.message})`` for a ``ClientError`` whose status is
    4xx. For everything else (including a ``ClientError`` with a 5xx status, whose message is not vetted)
    append ``{"reference", "type", "message", "traceback"}`` to ``log`` - the full detail, for the team - and
    return ``(500, {"error": "internal error", "reference": reference})`` with nothing from the exception in it.
    ``traceback.format_exception`` gives the traceback text.
    """
    raise NotImplementedError("make_handler")
