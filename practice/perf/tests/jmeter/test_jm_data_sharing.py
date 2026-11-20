"""Exercise: jm_data_sharing.py - predict which rows a CSV Data Set Config hands out, then check a real run."""

import re
from collections import Counter
from pathlib import Path

import pytest
from jmeter.jm_data_sharing import EOF_VALUE, Reads, plan_reads, rows_needed
from load_tools import jmeter_home, read_jtl, run_jmeter
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

ROWS = ["m1", "m2", "m3", "m4"]
PLAN = Path(__file__).parent / "fixtures" / "jm_data_share.jmx"


def test_all_threads_share_one_pointer_and_recycle():
    reads = plan_reads(ROWS, threads=3, iterations=2)
    assert reads == Reads(None, Counter({"m1": 2, "m2": 2, "m3": 1, "m4": 1}), 6)


def test_group_mode_with_one_thread_group_is_the_same_as_all():
    assert plan_reads(ROWS, 2, 3, share="group") == plan_reads(ROWS, 2, 3, share="all")


def test_shared_file_without_recycle_hands_out_eof():
    reads = plan_reads(ROWS, threads=2, iterations=3, recycle=False)
    assert reads.values == Counter({"m1": 1, "m2": 1, "m3": 1, "m4": 1, EOF_VALUE: 2})
    assert reads.samples == 6


def test_stop_thread_ends_the_run_at_the_last_row():
    reads = plan_reads(ROWS, threads=5, iterations=2, recycle=False, stop_thread=True)
    assert reads.values == Counter(ROWS) and reads.samples == 4


def test_stop_thread_is_ignored_while_recycle_is_on():
    assert plan_reads(ROWS, 1, 6, recycle=True, stop_thread=True).samples == 6


def test_current_thread_mode_starts_every_thread_at_line_one():
    reads = plan_reads(ROWS, threads=2, iterations=5, share="thread")
    assert reads.per_thread == {1: ["m1", "m2", "m3", "m4", "m1"], 2: ["m1", "m2", "m3", "m4", "m1"]}
    assert reads.values == Counter({"m1": 4, "m2": 2, "m3": 2, "m4": 2}) and reads.samples == 10
    reads = plan_reads(ROWS, threads=2, iterations=5, share="thread", recycle=False, stop_thread=True)
    assert reads.per_thread == {1: ROWS, 2: ROWS} and reads.samples == 8


def test_shared_modes_do_not_predict_an_order():
    assert plan_reads(ROWS, 3, 2).per_thread is None


def test_rows_needed():
    assert rows_needed(10, 3) == 30
    assert rows_needed(10, 3, share="group") == 30
    assert rows_needed(10, 3, share="thread") == 3


@pytest.mark.parametrize("kwargs", [dict(share="random"), dict(rows=[]), dict(threads=0), dict(iterations=0)])
def test_rejects_impossible_inputs(kwargs):
    args = dict(rows=ROWS, threads=1, iterations=1) | kwargs
    with pytest.raises(ValueError):
        plan_reads(**args)


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_the_model_matches_a_real_jmeter_run(tmp_path):
    data = tmp_path / "rows.csv"
    data.write_text("client_id,client_secret\n" + "".join(f"merchant-{n},secret-{n}\n" for n in range(1, 5)))
    with serve(TargetConfig(latency_ms=1)) as base:
        jtl = run_jmeter(PLAN, {"port": base.rsplit(":", 1)[1], "csv": data}, tmp_path)
    per_thread: dict[str, dict[int, list[str]]] = {"PerThread": {}, "Shared": {}}
    for r in read_jtl(jtl):  # thread names look like "PerThread 1-3": group, group number, thread number
        group, number = re.fullmatch(r"(\w+) \d+-(\d+)", r["threadName"]).groups()
        per_thread[group].setdefault(int(number), []).append(r["label"].removeprefix("POST /auth/token "))
    rows = [f"merchant-{n}" for n in range(1, 5)]
    # PerThread: 3 threads x 5 iterations, each thread opens its own copy, recycle on
    assert per_thread["PerThread"] == plan_reads(rows, 3, 5, share="thread", recycle=True).per_thread
    # Shared: 2 threads x 5 iterations from one pointer, recycle and stop thread off
    shared = Counter(v for seq in per_thread["Shared"].values() for v in seq)
    assert shared == plan_reads(rows, 2, 5, share="all", recycle=False, stop_thread=False).values
