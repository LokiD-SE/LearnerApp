"""Checks exercises/locust/lc_valid_names.py: naming dynamic URLs and regrouping Locust statistics.

The topic folder is called ``locust``, the same name as the Locust package, so this test loads the module from
its file instead of ``from locust.lc_valid_names import ...`` (which would find the real Locust package)."""

import importlib.util

import pytest
from load_tools import practice_file

pytestmark = pytest.mark.exercise


def _load():
    spec = importlib.util.spec_from_file_location("lc_valid_names", practice_file("locust/lc_valid_names.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


names = _load()


def entry(method: str, requests: int, failures: int = 0) -> dict:
    return {"method": method, "num_requests": requests, "num_failures": failures}


# Shaped like a real ungrouped run: rows from Locust's --json-file, keyed by name (see the lesson's output).
STATS = {
    "/gateway/login": entry("POST", 2),
    "/gateway/charges": entry("POST", 961),
    "/gateway/charges/ch_7001": entry("GET", 1),
    "/gateway/charges/ch_7002": entry("GET", 1, 1),
    "/gateway/charges/ch_7003": entry("GET", 1),
    "/v1/payments?limit=25&starting_after=pay_9": entry("GET", 3),
    "/v1/payments?starting_after=pay_40&limit=25": entry("GET", 2),
    "/v1/payments/8d7c6a2e-1f3b-4c5d-9e8f-0a1b2c3d4e5f/refunds/12": entry("POST", 1),
    "GET /v1/payments/{id}": entry("GET", 40, 2),
}


@pytest.mark.parametrize(("method", "url", "expected"), [
    ("GET", "/gateway/charges/ch_7001", "GET /gateway/charges/{id}"),
    ("get", "/v1/payments/pay_7", "GET /v1/payments/{id}"),
    ("GET", "/v1/payments?starting_after=pay_9&limit=25",
     "GET /v1/payments?limit={limit}&starting_after={starting_after}"),
    ("POST", "/v1/payments/8d7c6a2e-1f3b-4c5d-9e8f-0a1b2c3d4e5f/refunds/12", "POST /v1/payments/{id}/refunds/{id}"),
    ("GET", "/v1/reports/settlement", "GET /v1/reports/settlement"),
    ("GET", "/v2/payments", "GET /v2/payments"),
])
def test_group_name(method, url, expected):
    assert names.group_name(method, url) == expected


def test_ungrouped_finds_rows_that_collapse_into_one_name():
    found = names.ungrouped(STATS)
    assert found == {
        "GET /gateway/charges/{id}": ["/gateway/charges/ch_7001", "/gateway/charges/ch_7002",
                                      "/gateway/charges/ch_7003"],
        "GET /v1/payments?limit={limit}&starting_after={starting_after}": [
            "/v1/payments?limit=25&starting_after=pay_9", "/v1/payments?starting_after=pay_40&limit=25"],
        "POST /v1/payments/{id}/refunds/{id}": ["/v1/payments/8d7c6a2e-1f3b-4c5d-9e8f-0a1b2c3d4e5f/refunds/12"],
    }


def test_regroup_merges_counts_and_keeps_hand_named_rows():
    merged = names.regroup(STATS)
    assert merged["GET /gateway/charges/{id}"] == {"num_requests": 3, "num_failures": 1}
    assert merged["GET /v1/payments?limit={limit}&starting_after={starting_after}"]["num_requests"] == 5
    assert merged["POST /gateway/charges"] == {"num_requests": 961, "num_failures": 0}
    assert merged["GET /v1/payments/{id}"] == {"num_requests": 40, "num_failures": 2}
    assert sum(r["num_requests"] for r in merged.values()) == sum(e["num_requests"] for e in STATS.values())
