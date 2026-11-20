"""Exercise: results of a distributed run (jmeter/jm_dist_results.py). Rows follow the shape of a real two-server
run made on 20 November 2026; timestamps are small numbers instead of epoch milliseconds."""

import csv
from collections import Counter

import pytest
from jmeter.jm_dist_results import merge_jtls, peak_threads, samples_per_server, server_of

pytestmark = pytest.mark.exercise

S1, S2 = "127.0.0.1:21091", "127.0.0.1:21092"
HEADER = ["timeStamp", "elapsed", "label", "responseCode", "threadName", "success", "grpThreads", "allThreads"]


def row(ts, thread, all_threads, label="GET /health"):
    return {"timeStamp": str(ts), "elapsed": "3", "label": label, "responseCode": "200", "threadName": thread,
            "success": "true", "grpThreads": str(all_threads), "allThreads": str(all_threads)}


REMOTE = [row(1000, f"{S2}-Merchants 1-1", 2), row(1000, f"{S2}-Merchants 1-2", 2), row(1004, f"{S1}-Merchants 1-1", 2),
          row(1005, f"{S1}-Merchants 1-2", 2), row(1101, f"{S2}-Merchants 1-1", 1), row(1102, f"{S1}-Merchants 1-2", 1)]


def write(path, rows, header=HEADER):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return path


def test_server_of():
    assert server_of(f"{S2}-Merchants 1-2") == S2
    assert server_of("loadgen-3.example.internal:1099-Checkout 2-15") == "loadgen-3.example.internal:1099"
    assert server_of("Merchants 1-2") is None
    assert server_of("setUp Thread Group 1-1") is None


def test_samples_per_server():
    assert samples_per_server(REMOTE) == Counter({S1: 3, S2: 3})
    assert samples_per_server([row(1, "Merchants 1-1", 1)]) == Counter({None: 1})


def test_peak_threads_adds_up_each_servers_own_peak():
    assert max(int(r["allThreads"]) for r in REMOTE) == 2  # what the file seems to say
    assert peak_threads(REMOTE) == 4  # the most the system under test can have had at once


def test_peak_threads_of_a_local_run():
    assert peak_threads([row(1, "Merchants 1-1", 3), row(2, "Merchants 1-2", 5), row(3, "Merchants 1-3", 4)]) == 5


def test_merge_jtls_prefixes_sorts_and_writes_one_header(tmp_path):
    a = write(tmp_path / "a.jtl", [row(10, "Merchants 1-1", 1), row(30, "Merchants 1-1", 1)])
    b = write(tmp_path / "b.jtl", [row(20, "Merchants 1-1", 1), row(30, "Merchants 1-2", 2)])
    out = tmp_path / "merged.jtl"
    assert merge_jtls({"gen-1": a, "gen-2": b}, out) == 4
    lines = out.read_text().splitlines()
    assert lines[0] == ",".join(HEADER) and lines.count(lines[0]) == 1
    with open(out, newline="") as f:
        merged = list(csv.DictReader(f))
    assert [(r["timeStamp"], r["threadName"]) for r in merged] == [
        ("10", "gen-1-Merchants 1-1"), ("20", "gen-2-Merchants 1-1"),
        ("30", "gen-1-Merchants 1-1"), ("30", "gen-2-Merchants 1-2")]


def test_merge_jtls_sorts_timestamps_as_numbers(tmp_path):
    a = write(tmp_path / "a.jtl", [row(999, "Merchants 1-1", 1), row(1000, "Merchants 1-1", 1)])
    b = write(tmp_path / "b.jtl", [row(100, "Merchants 1-1", 1)])
    out = tmp_path / "m.jtl"
    merge_jtls({"g1": a, "g2": b}, out)
    with open(out, newline="") as f:
        assert [r["timeStamp"] for r in csv.DictReader(f)] == ["100", "999", "1000"]


def test_merge_jtls_refuses_different_headers(tmp_path):
    a = write(tmp_path / "a.jtl", [row(1, "Merchants 1-1", 1)])
    b = write(tmp_path / "b.jtl", [row(2, "Merchants 1-1", 1)], header=HEADER[:-1])
    with pytest.raises(ValueError):
        merge_jtls({"g1": a, "g2": b}, tmp_path / "m.jtl")
