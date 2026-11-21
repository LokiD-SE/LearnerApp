"""Prints every number and table the security testing mock interview lesson shows (reference solutions).

Run from practice/security:  .venv/bin/python support/smi_demo.py
Nothing here is random and nothing leaves the machine; the portal is only imported to count its routes.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "solutions"))
sys.path.insert(0, str(ROOT / "support"))

from sandpay_vuln import make_app  # noqa: E402
from smi_fixture import PRACTICE_RATES, SCAN_REPORT, Feature, Inventory  # noqa: E402
from specialised.smi_estimate import calendar_days, effort_hours, estimate, person_days  # noqa: E402
from specialised.smi_plan import category_of, plan_gaps, required_areas  # noqa: E402
from specialised.smi_triage import classify, next_step, report_order, triage  # noqa: E402
from wstg_fixture import FLAW_MAP  # noqa: E402

FEATURES = (
    Feature("payments list", has_login=True, keeps_session=True, has_roles=True, object_ids_in_urls=True,
            json_api=True, uses_sql=True, handles_sensitive_data=True),
    Feature("webhook test", has_login=True, json_api=True, fetches_urls=True),
    Feature("login with next", has_login=True, keeps_session=True, redirects_to_param=True),
    Feature("notes", has_login=True, keeps_session=True, json_api=True, renders_user_input=True),
)


def plan_part():
    print("== plan: required areas per feature ==")
    for f in FEATURES:
        print(f.name)
        for category, reasons in required_areas(f).items():
            print(f"  {category:<14} {', '.join(reasons)}")
    print("\n== plan: a candidate's answer for 'webhook test' ==")
    answer = ["WSTG-INPV-19", "WSTG-ATHN-03", "WSTG-BUSL-05", "WSTG-CLNT-04"]
    gaps = plan_gaps(FEATURES[1], answer)
    print("planned  ", answer)
    print("missing  ", list(gaps.missing))
    print("unneeded ", list(gaps.unneeded))
    print("\n== plan: do the four features cover the categories of the portal's flaws? ==")
    needed = set()
    for f in FEATURES:
        needed |= set(required_areas(f))
    print("categories asked for by the four features:", len(needed))
    uncovered = []
    for flaw, row in FLAW_MAP.items():
        cats = {category_of(t) for t in row["wstg"]}
        if not row["wstg"]:
            uncovered.append(f"{flaw}: no v4.2 test")
        elif not cats <= needed:
            uncovered.append(f"{flaw}: {sorted(cats - needed)}")
    for line in uncovered:
        print("  not covered ->", line)
    print("flaws with a v4.2 test whose category is covered:",
          sum(1 for r in FLAW_MAP.values() if r["wstg"] and {category_of(t) for t in r["wstg"]} <= needed),
          "of", sum(1 for r in FLAW_MAP.values() if r["wstg"]))


def triage_part():
    print("\n== triage: the scanner report ==")
    for f in SCAN_REPORT:
        print(f"{f.id}  {f.claimed:<8} {classify(f):<15} {f.title}")
    counts = triage(SCAN_REPORT)
    print("\ncounts:", counts)
    print("next:  ", next_step(counts))
    print("report order:", report_order(SCAN_REPORT))
    in_scope = [f for f in SCAN_REPORT if f.in_scope]
    print("\nafter the two out-of-scope findings are handed back:")
    print("next:  ", next_step(triage(in_scope)))


def estimate_part():
    print("\n== estimate ==")
    routes = len(make_app().routes)
    print("routes in the portal's table:", routes)
    inv = Inventory(endpoints=routes, roles=2, uploads=0, integrations=1)
    print("effort_hours:", round(effort_hours(inv, PRACTICE_RATES), 3))
    e = estimate(inv, PRACTICE_RATES)
    for name in ("test_hours", "report_hours", "retest_hours", "contingency_hours", "total_hours"):
        print(f"  {name:<18} {getattr(e, name):7.3f}")
    days = person_days(e.total_hours, PRACTICE_RATES.hours_per_day)
    print("person days:", days)
    for testers in (1, 2, 3):
        print(f"  {testers} tester(s) at 80% -> {calendar_days(days, testers)} working days")
    print("\nwhat changes the answer most:")
    for label, other in (
        ("a third role", Inventory(routes, 3, 0, 1)),
        ("a file upload", Inventory(routes, 2, 1, 1)),
        ("no integrations", Inventory(routes, 2, 0, 0)),
    ):
        t = estimate(other, PRACTICE_RATES).total_hours
        print(f"  {label:<16} {t:7.3f} h  ({person_days(t, 6.0)} person days)")
    naive = routes * PRACTICE_RATES.hours_per_endpoint
    print(f"\nthe naive answer (endpoints x hours, nothing else): {naive} h = {person_days(naive, 6.0)} person days")


if __name__ == "__main__":
    plan_part()
    triage_part()
    estimate_part()
