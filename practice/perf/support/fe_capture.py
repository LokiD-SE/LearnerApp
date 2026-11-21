"""Regenerates support/fe_data/ for the frontend performance lesson. Run it by hand; the tests only read the files.

    cd practice/perf && .venv/bin/python support/fe_capture.py

It starts the local pages (fe_fixture.serve), runs ``fe_capture.mjs`` with the repo's Playwright and a real Google
Chrome (``PW_CHANNEL=chromium`` uses Playwright's own Chromium instead), then reduces the raw output:

* ``har_slow.json`` / ``har_fixed.json`` - one real HAR 1.2 recording of each page, with the request and response
  headers dropped, the port replaced by 8099 and numbers rounded to three decimals;
* ``runs.json`` - per run: first contentful paint, LCP, the layout shift and long task entries, the one-click
  interaction time, when the quote appeared, and the hero image's resource timing - for the slow page, the fixed
  page, and the fixed page while 24 clients load the quote API;
* ``field_samples.json`` - the SYNTHETIC field data from ``fe_fixture.make_field_samples``.

The machine and browser version are written to ``runs.json`` under ``meta``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fe_fixture  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
FIXED_PORT = "8099"


def r3(x):
    return round(x, 3) if isinstance(x, float) else x


def reduce_har(raw: dict, port: str) -> dict:
    log = raw["log"]
    entries = []
    for e in log["entries"]:
        req, res = e["request"], e["response"]
        entries.append(
            {
                "startedDateTime": e["startedDateTime"],
                "time": r3(e["time"]),
                "request": {
                    "method": req["method"],
                    "url": req["url"].replace(f"127.0.0.1:{port}", f"127.0.0.1:{FIXED_PORT}"),
                    "httpVersion": req["httpVersion"],
                    "headersSize": req["headersSize"],
                    "bodySize": req["bodySize"],
                },
                "response": {
                    "status": res["status"],
                    "statusText": res["statusText"],
                    "content": {"size": res["content"]["size"], "mimeType": res["content"]["mimeType"]},
                    "headersSize": res["headersSize"],
                    "bodySize": res["bodySize"],
                    "_transferSize": res.get("_transferSize", -1),
                },
                "timings": {k: r3(v) for k, v in e["timings"].items()},
                "_resourceType": e.get("_resourceType"),
            }
        )
    pages = [
        {
            "startedDateTime": p["startedDateTime"],
            "title": p["title"],
            "pageTimings": {k: r3(v) for k, v in p["pageTimings"].items()},
        }
        for p in log["pages"]
    ]
    return {
        "log": {
            "version": log["version"],
            "creator": log["creator"],
            "browser": log["browser"],
            "pages": pages,
            "entries": entries,
        }
    }


def reduce_run(run: dict) -> dict:
    hero = next(r for r in run["resources"] if r["name"].endswith("/static/hero.svg"))
    shifts = [
        {"startTime": round(s["startTime"], 1), "value": round(s["value"], 4), "hadRecentInput": s["hadRecentInput"]}
        for s in run["shifts"]
    ]
    interactions = [e["duration"] for e in run["events"] if e["interactionId"]]
    return {
        "ttfb": round(run["nav"]["responseStart"], 1),
        "fcp": round(run["fcp"], 1),
        "lcp": round(run["lcp"]["startTime"], 1),
        "lcp_tag": run["lcp"]["tag"],
        "load": round(run["nav"]["load"], 1),
        "quote_shown": round(run["quoteShown"], 1),
        "interaction_ms": round(max(interactions or [0]), 1),
        "shifts": shifts,
        "longtasks": [{"startTime": round(t["startTime"], 1), "duration": round(t["duration"], 1)} for t in run["longtasks"]],
        "hero_request_start": round(hero["requestStart"], 1),
        "hero_response_end": round(hero["responseEnd"], 1),
    }


def main():
    fe_fixture.DATA.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp, fe_fixture.serve() as base:
        subprocess.run(
            ["node", "practice/perf/support/fe_capture.mjs", base, tmp, "5"], cwd=REPO, check=True, timeout=600
        )
        port = base.rsplit(":", 1)[1]
        raw = json.loads((Path(tmp) / "raw.json").read_text())
        for name in ("slow", "fixed"):
            har = json.loads((Path(tmp) / f"har_{name}_raw.json").read_text())
            (fe_fixture.DATA / f"har_{name}.json").write_text(json.dumps(reduce_har(har, port), indent=1) + "\n")
    runs = {
        "meta": {"captured": date.today().isoformat(), "browser": raw["meta"]["browser"], "runs": raw["meta"]["runs"]},
        "slow": [reduce_run(r) for r in raw["slow"]],
        "fixed": [reduce_run(r) for r in raw["fixed"]],
        "fixed_under_load": [reduce_run(r) for r in raw["fixed_under_load"]],
    }
    (fe_fixture.DATA / "runs.json").write_text(json.dumps(runs, indent=1) + "\n")
    (fe_fixture.DATA / "field_samples.json").write_text(json.dumps(fe_fixture.make_field_samples()) + "\n")
    print("wrote", ", ".join(sorted(p.name for p in fe_fixture.DATA.iterdir())))


if __name__ == "__main__":
    main()
