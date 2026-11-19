"""Runs the real load tools headless for tests and lessons: JMeter (non-GUI mode) and Locust (--headless).

- ``jmeter_home()`` finds JMeter: ``$JMETER_HOME`` or ``tools/apache-jmeter-*`` (``scripts/get-jmeter.sh``).
- ``run_jmeter(plan, props, out_dir)`` runs ``jmeter -n -t plan -l results.jtl`` with ``-J`` properties and
  returns the JTL (CSV) path. Command-line options are from the JMeter user manual, "Getting Started" 2.4.
- ``run_locust(locustfile, host, users, spawn_rate, run_time, out_dir)`` runs
  ``locust -f ... --headless -u -r -t --csv --json-file`` and returns the prefix (``<prefix>_stats.csv``,
  ``<prefix>.json`` ...). Read final totals with ``read_locust_stats(prefix)`` (the JSON): Locust rewrites the
  CSV files about once a second during the run, so ``_stats.csv`` can miss the last second of requests.
- ``read_jtl(path)`` parses a CSV JTL into dicts (header row on, JMeter's default CSV output).
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def jmeter_home() -> Path | None:
    env = os.environ.get("JMETER_HOME")
    if env and (Path(env) / "bin" / "jmeter").exists():
        return Path(env)
    found = sorted((ROOT / "tools").glob("apache-jmeter-*/bin/jmeter"))
    return found[-1].parent.parent if found else None


def java_home() -> str | None:
    """JAVA_HOME if set, else a JDK 17/21 in the usual Debian/Ubuntu place, else None (use PATH java)."""
    if os.environ.get("JAVA_HOME"):
        return os.environ["JAVA_HOME"]
    for candidate in ("/usr/lib/jvm/java-17-openjdk-amd64", "/usr/lib/jvm/java-21-openjdk-amd64"):
        if Path(candidate, "bin", "java").exists():
            return candidate
    return None


def run_jmeter(plan: Path, props: dict[str, object], out_dir: Path, timeout: float = 120) -> Path:
    home = jmeter_home()
    if home is None:
        raise RuntimeError("JMeter not found - run scripts/get-jmeter.sh or set JMETER_HOME")
    out_dir.mkdir(parents=True, exist_ok=True)
    jtl = out_dir / "results.jtl"
    jtl.unlink(missing_ok=True)
    cmd = [str(home / "bin" / "jmeter"), "-n", "-t", str(plan), "-l", str(jtl), "-j", str(out_dir / "jmeter.log")]
    cmd += [f"-J{k}={v}" for k, v in props.items()]
    env = {**os.environ, "HEAP": os.environ.get("HEAP", "-Xms256m -Xmx512m")}
    if java_home():
        env["JAVA_HOME"] = java_home()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    if proc.returncode != 0 or not jtl.exists():
        raise RuntimeError(f"jmeter failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
    return jtl


def read_jtl(path: Path) -> list[dict[str, str]]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def run_locust(locustfile: Path, host: str, users: int, spawn_rate: float, run_time: str, out_dir: Path,
               extra: list[str] | None = None, timeout: float = 120) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / "locust"
    locust = shutil.which("locust", path=str(Path(sys.executable).parent)) or "locust"
    cmd = [locust, "-f", str(locustfile), "--headless", "-u", str(users), "-r", str(spawn_rate), "-t", run_time,
           "--host", host, "--csv", str(prefix), "--json-file", str(prefix), "--only-summary", "--loglevel", "WARNING", *(extra or [])]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if not Path(f"{prefix}_stats.csv").exists():
        raise RuntimeError(f"locust failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")
    return prefix


def read_locust_stats(prefix: Path) -> dict[str, dict]:
    """Final per-request totals from ``<prefix>.json`` (``--json-file``), keyed by the request name as Locust
    shows it, e.g. ``{"GET /v1/payments": {"num_requests": 61, "num_failures": 0, ...}}``. The JSON is written
    once, when the run ends, so its counts are complete."""
    import json

    with open(f"{prefix}.json") as f:
        entries = json.load(f)
    return {e["name"]: e for e in entries}


def practice_file(relative: str) -> Path:
    """A non-Python exercise file (a JMeter plan, a CSV) in the folder under test: ``exercises/`` by default,
    ``solutions/`` with ``PERF_TARGET=solutions`` - the same switch conftest.py uses for imports.
    Example: ``practice_file("jmeter/jm_plan.jmx")``."""
    return ROOT / os.environ.get("PERF_TARGET", "exercises") / relative
