"""Shared data for the security testing mock interview lesson (security-testing-mock-interview) - not an exercise.

Everything here is synthetic. SandPay is fictional, and so is every finding, host and number below.

- ``Feature`` / ``CATEGORIES`` / ``RULES`` / ``BASELINE`` - the "how would you test this feature?" model of
  ``smi_plan``. ``CATEGORIES`` are the twelve category heading ids of the OWASP Web Security Testing Guide v4.2
  testing checklist (``checklist/Testing_Checklist.md`` at tag ``v4.2``; the same table is in ``wstg_fixture``).
  ``RULES`` - which feature flag calls for which categories - is this lesson's judgement, not OWASP's.
- ``ScanFinding`` / ``LABELS`` / ``NEXT_STEP`` / ``SEVERITY_ORDER`` / ``SCAN_REPORT`` - the "this scanner reported
  twelve findings, what now?" model of ``smi_triage``.
- ``Inventory`` / ``Rates`` / ``Estimate`` - the "how long would this assessment take?" model of ``smi_estimate``.
  The rates are ASSUMPTIONS made up for practice; they are not benchmarks of any firm or tool.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

# --------------------------------------------------------------------------------------------- smi_plan

CATEGORIES = (
    "WSTG-INFO", "WSTG-CONF", "WSTG-IDNT", "WSTG-ATHN", "WSTG-ATHZ", "WSTG-SESS",
    "WSTG-INPV", "WSTG-ERRH", "WSTG-CRYP", "WSTG-BUSLOGIC", "WSTG-CLIENT", "WSTG-APIT",
)
# In the v4.2 checklist the heading of Business Logic Testing is WSTG-BUSLOGIC but its tests are WSTG-BUSL-01..09;
# the heading of Client-side Testing is WSTG-CLIENT and its tests are WSTG-CLNT-01..14.
PREFIX_ALIASES = {"BUSL": "BUSLOGIC", "CLNT": "CLIENT"}
BASELINE = ("WSTG-INFO", "WSTG-CONF", "WSTG-ERRH")  # every web feature: what it exposes, how it is configured, how it fails


@dataclass(frozen=True)
class Feature:
    """What a feature does, as flags. Say yes only to what the feature really has."""

    name: str
    has_login: bool = False
    keeps_session: bool = False
    has_roles: bool = False
    object_ids_in_urls: bool = False
    renders_user_input: bool = False
    uses_sql: bool = False
    fetches_urls: bool = False
    redirects_to_param: bool = False
    accepts_uploads: bool = False
    moves_money: bool = False
    json_api: bool = False
    handles_sensitive_data: bool = False


FLAGS = tuple(f.name for f in fields(Feature) if f.name != "name")

RULES: dict[str, tuple[str, ...]] = {  # flag -> the categories it calls for (the lesson's judgement)
    "has_login": ("WSTG-IDNT", "WSTG-ATHN"),
    "keeps_session": ("WSTG-SESS",),
    "has_roles": ("WSTG-ATHZ",),
    "object_ids_in_urls": ("WSTG-ATHZ",),
    "renders_user_input": ("WSTG-INPV", "WSTG-CLIENT"),
    "uses_sql": ("WSTG-INPV",),
    "fetches_urls": ("WSTG-INPV",),
    "redirects_to_param": ("WSTG-CLIENT",),
    "accepts_uploads": ("WSTG-ATHZ", "WSTG-BUSLOGIC", "WSTG-INPV"),
    "moves_money": ("WSTG-BUSLOGIC",),
    "json_api": ("WSTG-APIT", "WSTG-INPV"),
    "handles_sensitive_data": ("WSTG-CRYP",),
}


@dataclass(frozen=True)
class Gaps:
    missing: tuple[str, ...]  # needed by the feature, absent from the plan (in CATEGORIES order)
    unneeded: tuple[str, ...]  # in the plan, but no flag of the feature calls for it (in CATEGORIES order)


# ------------------------------------------------------------------------------------------ smi_triage

REPRO = ("reproduced", "not_reproduced", "not_tried")
SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")  # most severe first
LABELS = ("out_of_scope", "invalid_test", "unverified", "confirmed", "false_positive", "duplicate")

NEXT_STEP = {
    "out_of_scope": "Stop testing those targets today and tell the engagement owner; do not send another request.",
    "invalid_test": "Repair the tests first: a result without a working positive control proves nothing either way.",
    "unverified": "Verify the findings next, most severe claim first, with a control and a note of what you sent.",
    "confirmed": "Report the confirmed findings in severity order, each with evidence, impact and a fix.",
    "false_positive": "Close the false positives, keeping the evidence of the attempt so the scanner can be tuned.",
    "duplicate": "Merge the duplicates into their parent findings.",
}


@dataclass(frozen=True)
class ScanFinding:
    id: str
    title: str
    host: str
    in_scope: bool  # is the host in the written scope?
    claimed: str  # the scanner's severity, one of SEVERITY_ORDER
    repro: str = "not_tried"  # one of REPRO: what happened when a tester tried to reproduce it
    control_ok: bool = True  # did the positive control of that reproduction work? (meaningless when not_tried)
    duplicate_of: str | None = None  # the id of the finding it repeats


SCAN_REPORT = (
    ScanFinding("F-01", "Reflected XSS in /search", "portal.sandpay.example", True, "high", "reproduced", True),
    ScanFinding("F-02", "SQL injection in /api/payments", "portal.sandpay.example", True, "critical", "reproduced", True),
    ScanFinding("F-03", "Missing X-Content-Type-Options", "portal.sandpay.example", True, "low", "reproduced", True),
    ScanFinding("F-04", "IDOR on /api/payments/{id}", "portal.sandpay.example", True, "high", "not_reproduced", True),
    ScanFinding("F-05", "Open redirect on /login", "portal.sandpay.example", True, "medium", "not_reproduced", False),
    ScanFinding("F-06", "Directory listing on /files/", "portal.sandpay.example", True, "medium"),
    ScanFinding("F-07", "Weak TLS cipher accepted", "portal.sandpay.example", True, "medium"),
    ScanFinding("F-08", "Reflected XSS in /search (again)", "portal.sandpay.example", True, "high", duplicate_of="F-01"),
    ScanFinding("F-09", "Default credentials on admin console", "admin.partner-bank.example", False, "critical"),
    ScanFinding("F-10", "Outdated jQuery on /notes", "portal.sandpay.example", True, "low", "reproduced", True),
    ScanFinding("F-11", "Session cookie without Secure", "portal.sandpay.example", True, "medium", "reproduced", False),
    ScanFinding("F-12", "Server banner discloses version", "cdn.vendor-cdn.example", False, "info"),
)

# ----------------------------------------------------------------------------------------- smi_estimate


@dataclass(frozen=True)
class Inventory:
    endpoints: int  # routes or operations to test
    roles: int  # user roles that see different things
    uploads: int = 0  # file upload features
    integrations: int = 0  # outgoing calls to other systems (webhooks, providers)


@dataclass(frozen=True)
class Rates:
    hours_per_endpoint: float  # testing one endpoint as one role
    role_uplift: float  # each extra role adds this fraction of the endpoint effort (access control is retested)
    hours_per_upload: float
    hours_per_integration: float
    setup_hours: float  # accounts, scope, tooling, reading the documentation
    report_fraction: float  # reporting, as a fraction of the testing hours
    retest_fraction: float  # re-testing the fixes, as a fraction of the testing hours
    contingency_fraction: float  # of everything above
    hours_per_day: float = 6.0  # productive hours in a person-day


@dataclass(frozen=True)
class Estimate:
    test_hours: float  # per-endpoint, upload and integration testing plus setup
    report_hours: float
    retest_hours: float
    contingency_hours: float
    total_hours: float


# Made-up practice rates used by the tests and the lesson.
PRACTICE_RATES = Rates(
    hours_per_endpoint=1.5, role_uplift=0.4, hours_per_upload=6.0, hours_per_integration=4.0,
    setup_hours=8.0, report_fraction=0.25, retest_fraction=0.15, contingency_fraction=0.15,
)
