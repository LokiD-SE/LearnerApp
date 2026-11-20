"""Checks exercises/locust/lc_fund_cli.py, then runs real Locust (headless, in a subprocess) with the command line
and the environment variables it builds."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from lc_fund_fixture import load_exercise, write_locustfile
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

cli = load_exercise("locust/lc_fund_cli.py")
LOCUST = shutil.which("locust", path=str(Path(sys.executable).parent)) or "locust"


@pytest.mark.parametrize("text, seconds", [("20", 20), ("20s", 20), ("3m", 180), ("2h", 7200), ("1h20m", 4800),
                                           ("1h30m", 5400), ("3h30m10s", 12610), ("90", 90)])
def test_run_time_spans(text, seconds):
    assert cli.parse_run_time(text) == seconds


@pytest.mark.parametrize("text", ["", "10x", "1m2h", "abc", "1.5m", "h"])
def test_invalid_run_time_spans(text):
    with pytest.raises(ValueError):
        cli.parse_run_time(text)


def test_command_line_has_every_option_paired_with_its_value():
    argv = cli.headless_command("lf.py", "http://127.0.0.1:8090", 10, 2.5, "5m", "out/run")
    assert argv[0] == "locust" and all(isinstance(a, str) for a in argv)
    pairs = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1) if argv[i].startswith("-")}
    assert pairs["-f"] == "lf.py" and pairs["-u"] == "10" and pairs["-r"] == "2.5" and pairs["-t"] == "5m"
    assert pairs["--host"] == "http://127.0.0.1:8090"
    assert pairs["--csv"] == "out/run" and pairs["--json-file"] == "out/run"
    assert "--headless" in argv and "--only-summary" in argv
    assert "--exit-code-on-error" not in argv and "--stop-timeout" not in argv


def test_optional_flags_and_user_classes():
    argv = cli.headless_command("lf.py", "http://h", 4, 4, "30s", "r", locust="/x/locust", exit_code_on_error=0,
                                stop_timeout=10, user_classes=("WebUser", "MobileUser"))
    assert argv[0] == "/x/locust"
    assert argv[argv.index("--exit-code-on-error") + 1] == "0"
    assert argv[argv.index("--stop-timeout") + 1] == "10"
    assert argv[-2:] == ["WebUser", "MobileUser"]


@pytest.mark.parametrize("kwargs", [{"users": 0}, {"spawn_rate": 0}, {"run_time": "0"}, {"run_time": "soon"}])
def test_command_line_refuses_runs_that_cannot_work(kwargs):
    args = {"locustfile": "lf.py", "host": "http://h", "users": 2, "spawn_rate": 2, "run_time": "10s",
            "out_prefix": "r", **kwargs}
    with pytest.raises(ValueError):
        cli.headless_command(**args)


def test_environment_variables():
    assert cli.locust_env({"spawn-rate": 5, "--headless": True, "run-time": "1m", "only-summary": False}) == {
        "LOCUST_SPAWN_RATE": "5", "LOCUST_HEADLESS": "true", "LOCUST_RUN_TIME": "1m", "LOCUST_ONLY_SUMMARY": "false"}


def _run(argv, env=None):
    return subprocess.run(argv, capture_output=True, text=True, timeout=60, env={**os.environ, **(env or {})})


def test_a_run_with_failures_exits_1_and_still_writes_results(tmp_path):
    locustfile = write_locustfile(tmp_path, "no_login")
    with serve(TargetConfig(latency_ms=2)) as base:
        proc = _run(cli.headless_command(str(locustfile), base, 2, 2, "2s", str(tmp_path / "run"), locust=LOCUST))
    assert proc.returncode == 1, proc.stderr[-2000:]  # every request got 401
    assert (tmp_path / "run.json").exists() and (tmp_path / "run_stats.csv").exists()


def test_environment_alone_configures_a_run(tmp_path):
    locustfile = write_locustfile(tmp_path, "no_login")
    with serve(TargetConfig(latency_ms=2)) as base:
        env = cli.locust_env({"locustfile": str(locustfile), "host": base, "headless": True, "users": 2,
                              "spawn-rate": 2, "run-time": "2s", "csv": str(tmp_path / "env"),
                              "exit-code-on-error": 0})
        proc = _run([LOCUST, "--loglevel", "WARNING"], env=env)
    # The same failing script, but --exit-code-on-error 0 (set through LOCUST_EXIT_CODE_ON_ERROR) makes it exit 0.
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert (tmp_path / "env_stats.csv").exists()  # --json-file has no LOCUST_* variable in the docs; --csv does
