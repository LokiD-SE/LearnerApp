"""Finding ungrouped request names in Locust statistics - reference solution.

When a locustfile forgets ``name=`` on a URL with an id or a query value in it, Locust makes one statistics
row per distinct URL: thousands of rows with a handful of requests each, and percentiles that mean nothing.
These functions find such rows in Locust's ``--json-file`` output (as read by
``load_tools.read_locust_stats``: a dict of request name -> entry with ``method``, ``num_requests``,
``num_failures`` ...) and regroup them.

Rules for ``group_name(method, url)``:
- a path segment is an id when it is all digits, a UUID (8-4-4-4-12 hex), or ``<letters>_<digits>`` such as
  ``pay_7001`` or ``ch_7003``; it becomes ``{id}``;
- query parameters are kept, sorted by name, each value replaced by ``{<name>}``;
- the result is ``"<METHOD> <path>"`` plus ``?<params>`` if there were any.
"""

import re

_ID = re.compile(r"^(\d+|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[A-Za-z]+_\d+)$")


def group_name(method: str, url: str) -> str:
    """``group_name("GET", "/v1/payments/pay_7001")`` -> ``"GET /v1/payments/{id}"``;
    ``group_name("GET", "/v1/payments?starting_after=pay_9&limit=25")`` ->
    ``"GET /v1/payments?limit={limit}&starting_after={starting_after}"``."""
    path, _, query = url.partition("?")
    parts = ["{id}" if _ID.match(seg) else seg for seg in path.split("/")]
    name = f"{method.upper()} {'/'.join(parts)}"
    if query:
        params = sorted({p.partition("=")[0] for p in query.split("&") if p})
        name += "?" + "&".join(f"{p}={{{p}}}" for p in params)
    return name


def ungrouped(stats: dict[str, dict]) -> dict[str, list[str]]:
    """Group name -> the sorted row names that collapse into it, for every group made from more than one row
    or from a row whose name changes. Rows are keyed by their name; the method is in ``entry["method"]``.
    A row that already has a hand-written name (one that does not start with ``/``) is left alone."""
    groups: dict[str, list[str]] = {}
    for name, entry in stats.items():
        if not name.startswith("/"):
            continue
        groups.setdefault(group_name(entry["method"], name), []).append(name)
    return {g: sorted(names) for g, names in groups.items()
            if len(names) > 1 or names[0] != g.split(" ", 1)[1]}


def regroup(stats: dict[str, dict]) -> dict[str, dict[str, int]]:
    """Merged counts: group name -> ``{"num_requests": ..., "num_failures": ...}``. URL rows (names starting
    with ``/``) go under ``group_name``; hand-named rows keep their name."""
    out: dict[str, dict[str, int]] = {}
    for name, entry in stats.items():
        key = group_name(entry["method"], name) if name.startswith("/") else name
        row = out.setdefault(key, {"num_requests": 0, "num_failures": 0})
        row["num_requests"] += int(entry["num_requests"])
        row["num_failures"] += int(entry["num_failures"])
    return out
