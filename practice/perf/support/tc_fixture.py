"""Fixtures for the lesson "JMeter, Locust and other tools compared" (exercises under analysis/tc_*).

The same scenario - a merchant signs in once, then loops *list payments, create a payment, read it back, think* -
exists in two tools: ``tc_checkout.jmx`` (JMeter) and ``tc_checkout_locustfile.py`` (Locust, ``HttpUser`` or, with
``TC_CLIENT=fast``, ``FastHttpUser``). The four request names are the same in both, so results can be compared.

- ``measure(cmd, env, timeout)`` runs a command in a tiny wrapper process and returns what the operating system
  recorded for it: wall time, user and system CPU seconds and the peak resident memory (``resource.getrusage`` for
  child processes; for JMeter that is the whole Java process). The load tool's own numbers say nothing about its
  own cost; this does.
- ``run_jmeter_scenario`` / ``run_locust_scenario`` run one scenario against a fresh practice API and return the
  measurements plus the path of the tool's result file (a JTL, or Locust's ``--json-file``).
- ``captured()`` returns the runs behind the lesson (``tc_data/runs.json``, made by ``tc_capture.py`` on 21 November
  2026); ``jtl_rows()`` and ``locust_entries()`` return one saved JMeter result file and one saved Locust result
  file of the same scenario.

Never import ``locust`` in the pytest process (gevent patches everything): the tools run in subprocesses.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from load_tools import ROOT, java_home, jmeter_home, read_jtl  # noqa: F401  (read_jtl is re-exported for tests)
from sandpay_target import TargetConfig, serve

HERE = Path(__file__).resolve().parent
DATA = HERE / "tc_data"
PLAN = HERE / "tc_checkout.jmx"
LOCUSTFILE = HERE / "tc_checkout_locustfile.py"

_WRAPPER = r"""
import json, os, resource, subprocess, sys, time
cmd = json.loads(sys.argv[1])
start = time.monotonic()
proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
wall = time.monotonic() - start
ru = resource.getrusage(resource.RUSAGE_CHILDREN)
print(json.dumps({"returncode": proc.returncode, "wall_s": wall, "cpu_user_s": ru.ru_utime,
                  "cpu_sys_s": ru.ru_stime, "rss_peak_mb": ru.ru_maxrss / 1024}))
"""


def captured() -> dict:
    return json.loads((DATA / "runs.json").read_text())


def jtl_rows() -> list[dict[str, str]]:
    with open(DATA / "jmeter_checkout.csv", newline="") as f:
        return list(csv.DictReader(f))


def locust_entries() -> dict[str, dict]:
    return {e["name"]: e for e in json.loads((DATA / "locust_checkout.json").read_text())}


def measure(cmd: list[str], env: dict[str, str] | None = None, timeout: float = 180) -> dict:
    """Run ``cmd`` and return {returncode, wall_s, cpu_user_s, cpu_sys_s, rss_peak_mb} as the OS recorded them."""
    proc = subprocess.run([sys.executable, "-I", "-c", _WRAPPER, json.dumps(cmd)], capture_output=True, text=True,
                          timeout=timeout, env={**os.environ, **(env or {})})
    if proc.returncode != 0:
        raise RuntimeError(f"measure failed ({proc.returncode}): {proc.stderr}")
    return json.loads(proc.stdout)


def jmeter_command(out_dir: Path, port: int, threads: int, seconds: float, wait_ms: int, ramp_s: int = 0):
    home = jmeter_home()
    if home is None:
        raise RuntimeError("JMeter not found - run scripts/get-jmeter.sh or set JMETER_HOME")
    out_dir.mkdir(parents=True, exist_ok=True)
    jtl = out_dir / "results.jtl"
    jtl.unlink(missing_ok=True)
    cmd = [str(home / "bin" / "jmeter"), "-n", "-t", str(PLAN), "-l", str(jtl), "-j", str(out_dir / "jmeter.log"),
           f"-Jport={port}", f"-Jthreads={threads}", f"-Jduration={seconds}", f"-Jwait={wait_ms}", f"-Jramp={ramp_s}"]
    env = {}
    if java_home():
        env["JAVA_HOME"] = java_home()
    return cmd, env, jtl


def run_jmeter_scenario(out_dir: Path, port: int, threads: int, seconds: float, wait_ms: int, ramp_s: int = 0,
                        heap: str | None = None) -> tuple[dict, Path]:
    """One JMeter CLI run of the checkout plan. ``heap`` sets JMeter's HEAP variable (its own default is
    ``-Xms1g -Xmx1g -XX:MaxMetaspaceSize=256m``)."""
    cmd, env, jtl = jmeter_command(out_dir, port, threads, seconds, wait_ms, ramp_s)
    if heap:
        env["HEAP"] = heap
    result = measure(cmd, env)
    if not jtl.exists():
        raise RuntimeError(f"JMeter wrote no results (return code {result['returncode']})")
    return result, jtl


def run_locust_scenario(out_dir: Path, port: int, users: int, seconds: float, wait_s: float, ramp_s: float = 0,
                        client: str = "http", locustfile: Path | None = None) -> tuple[dict, Path]:
    """One headless Locust run of the checkout scenario; the second value is the ``--json-file`` path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / "locust"
    locust = shutil.which("locust", path=str(Path(sys.executable).parent)) or "locust"
    spawn = users / ramp_s if ramp_s else users
    cmd = [locust, "-f", str(locustfile or LOCUSTFILE), "--headless", "-u", str(users), "-r", str(spawn),
           "-t", f"{int(seconds)}s", "--host", f"http://127.0.0.1:{port}", "--json-file", str(prefix),
           "--only-summary", "--loglevel", "WARNING"]
    result = measure(cmd, {"TC_WAIT": str(wait_s), "TC_CLIENT": client})
    if not Path(f"{prefix}.json").exists():
        raise RuntimeError(f"Locust wrote no results (return code {result['returncode']})")
    return result, Path(f"{prefix}.json")


def with_target(**config):
    """The practice API every run in the lesson uses: 10 ms service time, room for 64 requests at once."""
    return serve(TargetConfig(latency_ms=10, capacity=64, **config))


def repo_path(p: Path) -> str:
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
