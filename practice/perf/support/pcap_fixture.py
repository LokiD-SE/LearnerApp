"""Fixtures for the capstone "A load test engagement for the SandPay API" (exercises under capstone/pcap_*).

The capstone ASSEMBLES what the earlier lessons taught, so it reuses their code instead of copying it:

- ``ref`` - the reference solutions of the earlier lessons, loaded from ``solutions/fundamentals`` by file path
  (``slo_spec`` and ``slo_evaluate`` from the SLO lesson, ``little_calc`` from the Little's law lesson). They are
  loaded under private module names, so the capstone runs the same whether you solved those lessons or not.
- ``engagement_config()`` - the practice API as the engagement configures it: 20 ms service time (+/- 5 ms), 8
  workers. The API's own rules make a payment creation cost twice that and a settlement report ten times.
- ``MIX`` / ``SERVICE_FACTOR`` - the workload mix (weights out of 20) and each transaction's service-time factor.
- ``PLAN`` - the JMeter plan ``pcap_plan.jmx`` (the same workload as ``solutions/capstone/pcap_locustfile.py``).
- ``run_engagement_tools(...)`` - run the JMeter plan and the Locust file against one fresh API each.
- ``read_rows(name)`` / ``read_stats(name)`` / ``RUNS`` - the captured runs in ``pcap_data/`` (real JMeter and
  Locust results, ``timeStamp`` rebased to ms since the first sample), written by ``pcap_capture.py``.
- ``load_exercise(relative)`` imports an exercise module by file path (the folder name ``locust`` rule does not
  apply here, but the other fixtures do the same).
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from load_tools import practice_file
from sandpay_target import TargetConfig

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "pcap_data"
PLAN = HERE / "pcap_plan.jmx"

MIX = {
    "POST /v1/payments": 8,
    "GET /v1/payments": 6,
    "GET /v1/payments/{id}": 5,
    "GET /v1/reports/settlement": 1,
}
# How many times the API's base service time each transaction costs (see sandpay_target.py).
SERVICE_FACTOR = {"POST /v1/payments": 2.0, "GET /v1/payments": 1.0, "GET /v1/payments/{id}": 1.0,
                  "GET /v1/reports/settlement": 10.0}
BASE_SERVICE_MS = 20.0
WORKERS = 8
NOT_USER_TRAFFIC = ("POST /auth/token", "setup: GET /v1/payments")


def engagement_config(**overrides) -> TargetConfig:
    cfg = dict(latency_ms=BASE_SERVICE_MS, jitter_ms=5.0, capacity=WORKERS, queue_limit=1000)
    cfg.update(overrides)
    return TargetConfig(**cfg)


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _reference() -> SimpleNamespace:
    folder = ROOT / "solutions" / "fundamentals"
    spec_mod = _load("pcap_ref_slo_spec", folder / "slo_spec.py")
    # slo_evaluate imports ``fundamentals.slo_spec``; point that name at the reference copy while it loads, then
    # put back whatever was there (the exercise stub, when the exercises are under test).
    saved = sys.modules.get("fundamentals.slo_spec")
    sys.modules["fundamentals.slo_spec"] = spec_mod
    try:
        evaluate_mod = _load("pcap_ref_slo_evaluate", folder / "slo_evaluate.py")
    finally:
        if saved is None:
            sys.modules.pop("fundamentals.slo_spec", None)
        else:
            sys.modules["fundamentals.slo_spec"] = saved
    little = _load("pcap_ref_little_calc", folder / "little_calc.py")
    return SimpleNamespace(
        Requirement=spec_mod.Requirement, parse_requirement=spec_mod.parse_requirement,
        Sample=evaluate_mod.Sample, Verdict=evaluate_mod.Verdict, from_jtl=evaluate_mod.from_jtl,
        evaluate=evaluate_mod.evaluate, overall=evaluate_mod.overall, percentile=evaluate_mod.percentile,
        achieved_rate=evaluate_mod.achieved_rate, users_needed=little.users_needed)


ref = _reference()


def load_exercise(relative: str) -> ModuleType:
    path = practice_file(relative)
    spec = importlib.util.spec_from_file_location(Path(relative).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_rows(name: str) -> list[dict[str, str]]:
    with open(DATA / f"{name}.csv", newline="") as f:
        return list(csv.DictReader(f))


def read_stats(name: str) -> dict[str, dict]:
    return json.loads((DATA / f"{name}.json").read_text())


RUN_FILE = DATA / "runs.json"
RUNS: dict = json.loads(RUN_FILE.read_text()) if RUN_FILE.exists() else {}
