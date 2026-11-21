"""Audit a GitHub Actions workflow file as text (CI/CD lesson).

Exercise - fill in the TODOs; ``tests/devsecops/test_cicd_audit.py`` checks your work. There is no YAML library:
read the file line by line, the way a quick linter does.

Rules (``rule_id``, severity):

* ``unpinned-action`` - a ``uses:`` line whose ref is not a full 40-character lowercase-hex commit SHA. Severity
  ``high`` for a moving ref (``main``, ``master``, ``HEAD``, or no ``@ref`` at all), ``medium`` for a tag or a short
  SHA. A ``docker://`` image needs ``@sha256:`` and 64 hex characters, else ``medium``. A local path (``./...``) is fine.
* ``no-permissions`` - no top-level ``permissions:`` line (column 0) and at least one job without its own
  ``permissions:`` line (four spaces in). ``medium``, reported on the FIRST job that lacks one; nothing when there is
  no ``jobs:`` section.
* ``write-all`` - ``permissions: write-all`` on any line. ``high``.
* ``script-injection`` - inside shell script text (the value of ``run:``, or the indented body of ``run: |``), a
  ``${{ ... }}`` expression that contains one of ``UNTRUSTED``. ``high``. An expression that starts with
  ``contains(``, ``startsWith(`` or ``endsWith(`` returns a boolean and is fine. The same expression in ``env:`` or
  ``with:`` is NOT script text.
* ``pwn-request`` - the file triggers on ``pull_request_target`` or ``workflow_run`` AND a ``ref: ${{ ... }}`` line
  contains one of ``HEAD_CHECKOUTS``. ``high``, reported on the ``ref:`` line. A plain ``pull_request`` trigger is fine.
* ``plaintext-secret`` - a line ``NAME: value`` where NAME is UPPER_CASE with ``TOKEN``, ``SECRET``, ``PASSWORD``,
  ``API_KEY`` or ``PRIVATE_KEY`` in it and the value is a literal (not empty, not ``${{ ... }}``, not a ``$VAR``,
  not ``true``/``false``). ``high``. The message names the variable and NEVER contains the value.

Comment lines (first non-blank character ``#``) are ignored everywhere, and a trailing `` # comment`` is not part of a
value.
"""

from __future__ import annotations

from dataclasses import dataclass

UNTRUSTED = (
    "github.event.issue.title",
    "github.event.issue.body",
    "github.event.pull_request.title",
    "github.event.pull_request.body",
    "github.event.pull_request.head.ref",
    "github.event.comment.body",
    "github.event.review.body",
    "github.event.head_commit.message",
    "github.head_ref",
)
HEAD_CHECKOUTS = (
    "github.event.pull_request.head.sha",
    "github.event.pull_request.head.ref",
    "github.head_ref",
    "github.event.workflow_run.head_sha",
    "github.event.workflow_run.head_branch",
)


@dataclass(frozen=True)
class Finding:
    rule_id: str
    line: int  # 1-based
    severity: str
    message: str


def audit_workflow(text: str, path: str = "workflow.yml") -> list[Finding]:
    """Every finding in ``text``, sorted by ``(line, rule_id)``. ``path`` is only for the caller's reports.

    TODO: split into lines and apply the six rules above. Hints in the lesson: find the script lines first (a helper
    that returns ``{line number: text}``), use ``re.findall(r"\\$\\{\\{\\s*(.*?)\\s*\\}\\}", text)`` for expressions, and strip
    a trailing comment with ``re.split(r"\\s+#", value)[0]``.
    """
    raise NotImplementedError("audit_workflow")
