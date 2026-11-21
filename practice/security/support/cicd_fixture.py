"""Synthetic pipeline data for the security-in-CI/CD lesson (prefix cicd_). Nothing here is real or fetched.

Three pieces, one per exercise:

* ``Check`` / ``Trigger`` / ``CHECKS`` - the security checks of a fictional pipeline (SandPay), how long each takes
  and what it needs, and the four moments a pipeline can run them (``TRIGGERS``).
* ``BAD_WORKFLOW`` / ``GOOD_WORKFLOW`` - two small GitHub Actions workflow files, written for this lesson. The
  "SHAs" in ``GOOD_WORKFLOW`` are invented 40-character strings, not commits of any real repository, and the
  ``sandpay-example`` actions do not exist. The token in ``BAD_WORKFLOW`` was never issued.
* ``Alert`` / ``Report`` - what three scanners hand to a gate, each in its own severity vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------- 1. where each check runs


@dataclass(frozen=True)
class Check:
    name: str
    kind: str  # "secrets", "sast", "sca" or "dast"
    seconds: int  # typical run time on the pipeline's runners
    needs_app: bool = False  # needs a running, deployed copy of the application
    needs_secrets: bool = False  # needs credentials, for example a test account or a signing key


@dataclass(frozen=True)
class Trigger:
    name: str
    budget_s: int  # how long people will wait at this moment
    has_app: bool  # a deployed test environment exists at this moment
    secrets_ok: bool  # the code is trusted enough to be given credentials


TRIGGERS = (
    Trigger("pre-commit", 15, False, False),  # a laptop: seconds, no deployed app, no deploy credentials
    Trigger("pull-request", 600, False, False),  # code from a branch or a fork: untrusted, so no credentials
    Trigger("merge", 3600, True, True),  # code that was reviewed and merged: trusted, a test environment exists
    Trigger("nightly", 28800, True, True),  # scheduled: the slow, thorough scans
)

CHECKS = [
    Check("secret-scan-staged", "secrets", 5),
    Check("secret-scan-history", "secrets", 400),
    Check("sast-changed-files", "sast", 90),
    Check("sast-full", "sast", 1500),
    Check("sca-lockfile-audit", "sca", 60),
    Check("sbom-and-sign", "sca", 240, needs_secrets=True),
    Check("zap-baseline", "dast", 900, needs_app=True),
    Check("zap-authenticated", "dast", 1200, needs_app=True, needs_secrets=True),
    Check("zap-full-active", "dast", 7200, needs_app=True),
]

# --------------------------------------------------------------------------- 2. two workflow files

BAD_WORKFLOW = """\
name: PR checks
on:
  pull_request_target:
    types: [opened, synchronize]

env:
  SANDPAY_API_TOKEN: sp_test_Hq7mW2xT9vLc4NdKz8RbY3Ps

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - uses: sandpay-example/scan-action@main
      - name: Check the PR title
        run: |
          echo "Title is ${{ github.event.pull_request.title }}"
      - uses: ./.github/actions/local-helper
"""

# The same workflow with every finding fixed. The 40-character values are invented, not real commits.
GOOD_WORKFLOW = """\
name: PR checks
on:
  pull_request:

permissions:
  contents: read

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567 # v4
      - uses: sandpay-example/scan-action@fedcba9876543210fedcba9876543210fedcba98 # v2
      - name: Check the PR title
        env:
          TITLE: ${{ github.event.pull_request.title }}
        run: |
          echo "Title is $TITLE"
      - uses: ./.github/actions/local-helper
"""

# --------------------------------------------------------------------------- 3. what scanners hand to a gate

SEVERITIES = ("info", "low", "medium", "high", "critical")  # the gate's own scale, lowest first


@dataclass(frozen=True)
class Alert:
    tool: str  # "zap", "sca" or "sast"
    id: str  # a stable identifier (a fingerprint, as in the SAST lesson)
    severity: str  # in the tool's own vocabulary, any letter case


@dataclass
class Report:
    tool: str
    alerts: list[Alert] = field(default_factory=list)
    complete: bool = True  # False when the tool crashed or timed out part-way
