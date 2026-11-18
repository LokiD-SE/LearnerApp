"""Verifies the practice project, like practice/verify.sh does for the other projects:

1. every test passes against the reference solutions (PERF_TARGET=solutions);
2. every exercise test file (tests/**/test_*.py) fails against the unsolved exercises - otherwise its
   tests don't check the learner's work.

Run from practice/perf with the project's virtual environment: .venv/bin/python scripts/verify.py
"""

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pytest(target: str, *args: str, **kwargs) -> subprocess.CompletedProcess:
    env = {**os.environ, "PERF_TARGET": target}
    return subprocess.run([sys.executable, "-m", "pytest", *args], cwd=ROOT, env=env, **kwargs)


def step(title: str) -> None:
    print(f"\n== perf: {title}", flush=True)


def main() -> int:
    step("reference solutions must pass every test")
    if pytest("solutions").returncode != 0:
        print("FAIL: solutions fail", file=sys.stderr)
        return 1

    step("unsolved exercises must fail every exercise test file")
    with tempfile.TemporaryDirectory(prefix="learnerapp-perf-report-") as tmp:
        report = Path(tmp) / "report.xml"
        pytest("exercises", "-m", "exercise", f"--junitxml={report}", "-p", "no:cacheprovider",
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not report.exists():
            print("FAIL: pytest wrote no report", file=sys.stderr)
            return 1
        tree = ET.parse(report)

    # Group test cases by file; a file that fails to import is reported as one error case.
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for case in tree.iter("testcase"):
        # importlib mode reports classname as the dotted path, e.g. tests.ml_foundations.test_arrays; a
        # module that fails to import is one error case with an empty classname and the path as its name.
        classname = case.get("classname") or case.get("name", "")
        file = classname
        parts = classname.split(".")
        names = [p for p in parts if p.startswith("test_")]
        if names:
            index = parts.index(names[0])
            file = "/".join(parts[: index + 1]) + ".py"
        failed = any(case.find(tag) is not None for tag in ("failure", "error"))
        totals[file][0] += 1
        totals[file][1] += int(failed)

    # tests/support checks the shared helpers, not a learner exercise.
    expected = sorted(
        str(p.relative_to(ROOT)) for p in (ROOT / "tests").rglob("test_*.py") if "support" not in p.parts
    )
    if not expected:
        print("FAIL: no exercise tests found", file=sys.stderr)
        return 1
    ok = True
    for file in expected:
        total, failed = totals.get(file, [0, 0])
        if total == 0:
            print(f"FAIL: {file} has no tests marked exercise", file=sys.stderr)
            ok = False
        elif failed == 0:
            print(f"FAIL: {file} passes against the unsolved exercise, so it does not check the work",
                  file=sys.stderr)
            ok = False
        else:
            print(f"ok: {file} fails against the unsolved exercise ({failed} of {total} tests)")
    if not ok:
        return 1
    print("\nverify: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
