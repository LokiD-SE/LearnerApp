"""Exercise: one slice of the data per server (jmeter/jm_dist_split.py). One test makes a real distributed run:
two JMeter servers on 127.0.0.1 (each in its own folder, like two machines), started by support/jm_dist_fixture.py."""

from collections import Counter
from pathlib import Path

import pytest
from jm_dist_fixture import remote_servers, run_remote
from jmeter.jm_dist_split import rows_needed_per_server, split_rows, write_server_files
from load_tools import jmeter_home, read_jtl
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

PLAN = Path(__file__).parent / "fixtures" / "jm_dist_login.jmx"
HEADER = "client_id,client_secret"


def merchants(first, last):
    return [f"merchant-{n},secret-{n}" for n in range(first, last + 1)]


def test_split_rows_is_contiguous_and_even():
    rows = list("abcde")
    assert split_rows(rows, 2) == [["a", "b", "c"], ["d", "e"]]
    assert split_rows(rows, 5) == [["a"], ["b"], ["c"], ["d"], ["e"]]
    assert split_rows(rows, 1) == [rows]


def test_split_rows_never_overlaps_or_loses_a_row():
    rows = [f"r{n}" for n in range(47)]
    for servers in range(1, 10):
        parts = split_rows(rows, servers)
        assert len(parts) == servers
        assert [r for part in parts for r in part] == rows
        sizes = [len(p) for p in parts]
        assert max(sizes) - min(sizes) <= 1 and sizes == sorted(sizes, reverse=True)


@pytest.mark.parametrize("rows, servers", [(["a", "b"], 3), (["a"], 0), ([], 1)])
def test_split_rows_rejects_impossible_splits(rows, servers):
    with pytest.raises(ValueError):
        split_rows(rows, servers)


def test_write_server_files_keeps_the_header_in_every_file(tmp_path):
    source = tmp_path / "all.csv"
    source.write_text(HEADER + "\n" + "\n".join(merchants(1, 5)) + "\n\n")
    dirs = [tmp_path / "s1", tmp_path / "s2"]
    for d in dirs:
        d.mkdir()
    paths = write_server_files(source, dirs)
    assert paths == [dirs[0] / "merchants.csv", dirs[1] / "merchants.csv"]
    assert paths[0].read_text() == HEADER + "\n" + "".join(r + "\n" for r in merchants(1, 3))
    assert paths[1].read_text() == HEADER + "\n" + "".join(r + "\n" for r in merchants(4, 5))
    assert write_server_files(source, dirs, name="m.csv")[0] == dirs[0] / "m.csv"


def test_rows_needed_per_server():
    assert rows_needed_per_server(2, 3) == 6
    assert rows_needed_per_server(250, 40) == 10_000
    with pytest.raises(ValueError):
        rows_needed_per_server(0, 3)


@pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")
def test_a_real_distributed_run_signs_in_every_merchant_once(tmp_path):
    threads, loops = 2, 3
    per_server = rows_needed_per_server(threads, loops)
    source = tmp_path / "all.csv"
    source.write_text(HEADER + "\n" + "\n".join(merchants(1, 2 * per_server)) + "\n")
    with serve(TargetConfig(latency_ms=1)) as base, remote_servers(2, tmp_path / "servers") as servers:
        write_server_files(source, [s.dir for s in servers])
        jtl, _ = run_remote(PLAN, servers, {"port": base.rsplit(":", 1)[1], "threads": threads, "loops": loops},
                            tmp_path / "controller")
    rows = read_jtl(jtl)
    assert {r["responseCode"] for r in rows} == {"200"}
    signed_in = Counter(r["label"].removeprefix("POST /auth/token ") for r in rows)
    assert signed_in == Counter(f"merchant-{n}" for n in range(1, 2 * per_server + 1))  # each exactly once
    by_server = Counter(r["threadName"].split("-", 1)[0] for r in rows)
    assert sorted(by_server) == sorted(s.address for s in servers)
    assert set(by_server.values()) == {per_server}
