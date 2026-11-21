"""Prints every number the frontend performance lesson shows, from the captured files and the SOLUTIONS.

    cd practice/perf && PERF_TARGET=solutions .venv/bin/python support/fe_demo.py
"""

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path[:0] = [str(HERE), str(HERE.parent / "solutions" / "analysis")]
import fe_har as har  # noqa: E402
import fe_lab as lab  # noqa: E402
import fe_vitals as vitals  # noqa: E402

DATA = HERE / "fe_data"
runs = json.loads((DATA / "runs.json").read_text())
field = json.loads((DATA / "field_samples.json").read_text())
med = statistics.median


def column(name, key, f=lambda v: v):
    return [f(r[key]) for r in runs[name]]


print("== lab runs (5 each): median [min-max]")
print(runs["meta"])
for name in ("slow", "fixed", "fixed_under_load"):
    rs = runs[name]
    row = {
        "fcp": [r["fcp"] for r in rs],
        "lcp": [r["lcp"] for r in rs],
        "quote": [r["quote_shown"] for r in rs],
        "click": [r["interaction_ms"] for r in rs],
        "cls": [round(vitals.cls(r["shifts"]), 3) for r in rs],
        "tbt": [lab.total_blocking_time(r["longtasks"], r["fcp"], until=r["load"]) for r in rs],
    }
    print(name, {k: f"{med(v):g} [{min(v):g}-{max(v):g}]" for k, v in row.items()})

print("\n== LCP parts, first run")
for name in ("slow", "fixed"):
    r = runs[name][0]
    parts = lab.lcp_parts(r["ttfb"], r["hero_request_start"], r["hero_response_end"], r["lcp"])
    print(name, "lcp", r["lcp"], parts, "dominant:", lab.dominant(parts))

print("\n== long tasks, slow run 0 (fcp %s, load %s)" % (runs["slow"][0]["fcp"], runs["slow"][0]["load"]))
print(runs["slow"][0]["longtasks"], "TBT in [fcp, load):", lab.total_blocking_time(runs["slow"][0]["longtasks"], runs["slow"][0]["fcp"], until=runs["slow"][0]["load"]))
print("TBT with no window:", lab.total_blocking_time(runs["slow"][0]["longtasks"], runs["slow"][0]["fcp"]))

print("\n== field (SYNTHETIC)", len(field), "visits")
for k, v in vitals.segment(field).items():
    print(k, {m: (v[m]["p75"], v[m]["rating"], v[m]["n"]) for m in ("lcp", "inp", "cls")}, "passes", v["passes"])
blended = vitals.assess(field)
print("blended", {m: (blended[m]["p75"], blended[m]["rating"]) for m in ("lcp", "inp", "cls")}, "passes", blended["passes"])
print("lcp distribution", {k: round(v, 3) for k, v in vitals.distribution(field, "lcp").items()})
mobile = [s for s in field if s["device"] == "mobile"]
print("mobile lcp distribution", {k: round(v, 3) for k, v in vitals.distribution(mobile, "lcp").items()})

print("\n== lab against field (mobile p75)")
mp75 = vitals.assess(mobile)["lcp"]["p75"]
for name in ("slow", "fixed"):
    print(name, lab.lab_vs_field([r["lcp"] for r in runs[name]], mp75))

print("\n== HAR")
for name in ("slow", "fixed"):
    h = json.loads((DATA / f"har_{name}.json").read_text())
    s = har.summarise(h)
    print(name, json.dumps(s))
    for w in har.waterfall(h):
        print("   ", w)
budget = {"requests": 6, "js_bytes": 290000, "bytes": 340000}
for name in ("slow", "fixed"):
    h = json.loads((DATA / f"har_{name}.json").read_text())
    print("budget", budget, name, har.check_budget(har.summarise(h), budget))

print("\n== layout shift entry (slow run 0)", runs["slow"][0]["shifts"], "->", vitals.cls(runs["slow"][0]["shifts"]))
