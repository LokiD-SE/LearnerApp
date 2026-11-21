"""Audit a GitHub Actions workflow file as text (CI/CD lesson).

Solution. A line-based scanner (no YAML library): it finds the six workflow flaws the lesson teaches and never
prints a secret value. It is a teaching scanner, not a replacement for the tools named in the lesson.

Rules (``rule_id``, severity):

* ``unpinned-action`` - ``uses:`` of an action whose ref is not a full 40-character commit SHA (``high`` for a branch
  such as ``main`` or no ref at all, ``medium`` for a tag or a short SHA); a ``docker://`` image without an
  ``@sha256:`` digest. Local ``./`` paths are fine.
* ``no-permissions`` - no top-level ``permissions:`` and some job without its own (``medium``), reported on the first
  such job.
* ``write-all`` - ``permissions: write-all`` anywhere (``high``).
* ``script-injection`` - a ``${{ ... }}`` expression holding attacker-controlled text inside a ``run:`` script
  (``high``). Expressions that return a boolean (``contains``, ``startsWith``, ``endsWith``) are quiet.
* ``pwn-request`` - a privileged trigger (``pull_request_target``, ``workflow_run``) together with a checkout of the
  pull request's head (``high``).
* ``plaintext-secret`` - an UPPER_CASE variable named like a credential that holds a literal value (``high``).
"""

from __future__ import annotations

import re
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
BOOLEAN_FUNCTIONS = ("contains(", "startswith(", "endswith(")
PRIVILEGED_TRIGGERS = ("pull_request_target", "workflow_run")
HEAD_CHECKOUTS = (
    "github.event.pull_request.head.sha",
    "github.event.pull_request.head.ref",
    "github.head_ref",
    "github.event.workflow_run.head_sha",
    "github.event.workflow_run.head_branch",
)
SECRET_WORDS = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "PRIVATE_KEY")


@dataclass(frozen=True)
class Finding:
    rule_id: str
    line: int
    severity: str
    message: str


def _clean(value: str) -> str:
    """A YAML scalar without its trailing comment and quotes."""
    return re.split(r"\s+#", value, maxsplit=1)[0].strip().strip("'\"")


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def _script_lines(lines: list[str]) -> dict[int, str]:
    """``{line number: text}`` of every line that is shell script: a ``run:`` value or the body of a ``run: |`` block."""
    scripts: dict[int, str] = {}
    i = 0
    while i < len(lines):
        match = re.match(r"^(\s*)(-\s+)?run:\s*(.*)$", lines[i])
        if match and not _is_comment(lines[i]):
            key_col = len(match.group(1)) + (len(match.group(2)) if match.group(2) else 0)
            value = match.group(3).strip()
            if value[:1] in ("|", ">"):
                j = i + 1
                while j < len(lines):
                    body = lines[j]
                    if body.strip() and len(body) - len(body.lstrip()) <= key_col:
                        break
                    if body.strip():
                        scripts[j + 1] = body
                    j += 1
                i = j
                continue
            scripts[i + 1] = value
        i += 1
    return scripts


def _pinning(lines: list[str]) -> list[Finding]:
    found = []
    for number, line in enumerate(lines, 1):
        match = re.match(r"^\s*(?:-\s+)?uses:\s*(\S.*)$", line)
        if not match or _is_comment(line):
            continue
        value = _clean(match.group(1))
        if value.startswith("./"):
            continue
        if value.startswith("docker://"):
            if not re.search(r"@sha256:[0-9a-f]{64}$", value):
                found.append(Finding("unpinned-action", number, "medium", f"image {value} has no @sha256 digest"))
            continue
        action, _, ref = value.partition("@")
        if re.fullmatch(r"[0-9a-f]{40}", ref):
            continue
        if not ref or ref in ("main", "master", "HEAD"):
            found.append(Finding("unpinned-action", number, "high", f"{action} follows a moving ref ({ref or 'none'})"))
        else:
            found.append(Finding("unpinned-action", number, "medium", f"{action}@{ref} is not a full commit SHA"))
    return found


def _permissions(lines: list[str]) -> list[Finding]:
    found = []
    for number, line in enumerate(lines, 1):
        if not _is_comment(line) and re.match(r"^\s*permissions:\s*write-all\b", line):
            found.append(Finding("write-all", number, "high", "permissions: write-all grants every permission"))
    if any(re.match(r"^permissions:", line) for line in lines):
        return found
    jobs_at = next((i for i, line in enumerate(lines) if re.match(r"^jobs:\s*$", line)), None)
    if jobs_at is None:
        return found
    keys = [i for i in range(jobs_at + 1, len(lines)) if re.match(r"^  [A-Za-z0-9_-]+:\s*$", lines[i])]
    for n, start in enumerate(keys):
        end = keys[n + 1] if n + 1 < len(keys) else len(lines)
        if not any(re.match(r"^    permissions:", lines[k]) for k in range(start, end)):
            found.append(Finding("no-permissions", start + 1, "medium", "no permissions: key, so the token keeps its default"))
            break
    return found


def _injection(lines: list[str]) -> list[Finding]:
    found = []
    for number, text in _script_lines(lines).items():
        for expression in re.findall(r"\$\{\{\s*(.*?)\s*\}\}", text):
            if expression.lower().startswith(BOOLEAN_FUNCTIONS):
                continue
            hit = next((c for c in UNTRUSTED if c in expression), None)
            if hit:
                found.append(Finding("script-injection", number, "high", f"{hit} is expanded into the script text"))
    return found


def _pwn_request(lines: list[str]) -> list[Finding]:
    live = [line for line in lines if not _is_comment(line)]
    privileged = any(
        re.search(rf"(^\s*on:.*\b{t}\b|^\s*{t}:|^\s*-\s*{t}\b)", line) for t in PRIVILEGED_TRIGGERS for line in live
    )
    if not privileged:
        return []
    found = []
    for number, line in enumerate(lines, 1):
        if _is_comment(line):
            continue
        match = re.match(r"^\s*ref:\s*\$\{\{\s*(.*?)\s*\}\}", line)
        if match and any(h in match.group(1) for h in HEAD_CHECKOUTS):
            found.append(Finding("pwn-request", number, "high", "a privileged trigger checks out the pull request's head"))
    return found


def _plaintext_secrets(lines: list[str]) -> list[Finding]:
    found = []
    for number, line in enumerate(lines, 1):
        match = re.match(r"^\s*([A-Z][A-Z0-9_]*):\s*(\S.*)$", line)
        if not match or _is_comment(line):
            continue
        name, value = match.group(1), _clean(match.group(2))
        if not any(w in name for w in SECRET_WORDS):
            continue
        if not value or value.startswith(("${{", "$")) or value.lower() in ("true", "false"):
            continue
        found.append(Finding("plaintext-secret", number, "high", f"{name} holds a literal value; use a secret"))
    return found


def audit_workflow(text: str, path: str = "workflow.yml") -> list[Finding]:
    """Every finding in ``text``, sorted by line then rule id. ``path`` is only for the caller's reports."""
    lines = text.splitlines()
    findings = (
        _pinning(lines) + _permissions(lines) + _injection(lines) + _pwn_request(lines) + _plaintext_secrets(lines)
    )
    return sorted(findings, key=lambda f: (f.line, f.rule_id))
