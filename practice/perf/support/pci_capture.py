"""Captures the real runs behind the lesson "Performance testing in CI/CD".

    cd practice/perf && .venv/bin/python support/pci_capture.py

Runs real Locust (8 users, 4 s each) against the practice API and writes ``pci_data/history.json``:
``main`` 12 runs of the baseline build (20 ms service time), ``same`` 3 runs of it again, ``small`` 3 runs at 22 ms,
``slower`` 3 runs at 26 ms and ``failing`` 3 runs at 20 ms with ``error_rate=0.2``. It also converts the repo's
``.github/workflows/pages.yml`` to ``pci_data/pages.workflow.json`` with the ``yaml`` npm package (run from the
repository root's Node). Takes about two minutes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pci_fixture as fx  # noqa: E402

REPO = HERE.parent.parent.parent
SECONDS = 4


def batch(prefix: str, count: int, **config) -> list[dict]:
    return [fx.run_summary(f"{prefix}-{i:02d}", seconds=SECONDS, **config) for i in range(1, count + 1)]


def main() -> None:
    fx.DATA.mkdir(exist_ok=True)
    data = {
        "seconds_per_run": SECONDS,
        "main": batch("main", 12, latency_ms=20),
        "same": batch("same", 3, latency_ms=20),
        "small": batch("small", 3, latency_ms=22),
        "slower": batch("slower", 3, latency_ms=26),
        "failing": batch("failing", 3, latency_ms=20, error_rate=0.2),
    }
    (fx.DATA / "history.json").write_text(json.dumps(data, indent=1) + "\n")
    js = ("const fs=require('fs');const y=require('yaml');"
          "const d=y.parse(fs.readFileSync('.github/workflows/pages.yml','utf8'));"
          "process.stdout.write(JSON.stringify(d,null,1)+'\\n')")
    out = subprocess.run(["node", "-e", js], cwd=REPO, capture_output=True, text=True, check=True).stdout
    (fx.DATA / "pages.workflow.json").write_text(out)
    for name in ("main", "same", "small", "slower", "failing"):
        print(name, [(r["p95_ms"], r["errors"], r["samples"]) for r in data[name]])


if __name__ == "__main__":
    main()
