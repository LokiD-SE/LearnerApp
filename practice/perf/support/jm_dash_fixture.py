"""Helpers for the jm_dash_ exercises (the JMeter HTML dashboard and CI runs).

- ``make_jtl(out_dir)`` runs the reference assertion plan (``solutions/jmeter/jm_assert_plan.jmx``) once with real
  JMeter against ``jm_assert_fixture``, whose failures come from a request counter. 2 threads x 10 loops always
  give 62 samples and 11 failures: 5 soft errors on ``GET /v1/payments``, 4 x 500 and 2 declined payments on
  ``POST /v1/payments``. ``report_ms`` defaults to 1000, so the ~150 ms settlement report passes.
- ``run_jmeter_args(args, cwd)`` runs a JMeter command line built by a learner (``[jmeter, "-g", ...]``) with
  the same JAVA_HOME and heap settings as ``load_tools.run_jmeter``, and returns the CompletedProcess.
- ``jmeter_binary()`` is the ``bin/jmeter`` script.

Timings in the JTL depend on the machine; the counts do not.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from jm_assert_fixture import serve
from load_tools import ROOT, java_home, jmeter_home, run_jmeter

REFERENCE_PLAN = ROOT / "solutions" / "jmeter" / "jm_assert_plan.jmx"
LABELS = ("POST /auth/token", "GET /v1/payments", "POST /v1/payments", "GET /v1/reports/settlement")


def jmeter_binary() -> Path:
    home = jmeter_home()
    if home is None:
        raise RuntimeError("JMeter not found - run scripts/get-jmeter.sh or set JMETER_HOME")
    return home / "bin" / "jmeter"


def make_jtl(out_dir: Path, report_ms: int = 1000) -> Path:
    with serve() as base:
        props = {"port": base.rsplit(":", 1)[1], "threads": 2, "loops": 10, "report_ms": report_ms}
        return run_jmeter(REFERENCE_PLAN, props, out_dir)


def run_jmeter_args(args: list[str], cwd: Path, timeout: float = 120) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "HEAP": os.environ.get("HEAP", "-Xms256m -Xmx512m")}
    if java_home():
        env["JAVA_HOME"] = java_home()
    return subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
