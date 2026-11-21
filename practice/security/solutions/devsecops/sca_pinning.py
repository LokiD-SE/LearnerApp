"""Reference solution - check that what you install is exactly what you reviewed."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Issue:
    where: str  # "line 3" for a requirements file, the package path for a lockfile
    reason: str


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """(first line number, text) of each requirement, with comments removed and ``\\`` continuations joined."""
    lines: list[tuple[int, str]] = []
    buffer, start = "", 0
    for number, raw in enumerate(text.splitlines(), 1):
        line = re.sub(r"(^|\s)#.*$", "", raw).rstrip()
        if not buffer:
            start = number
        if line.endswith("\\"):
            buffer += line[:-1] + " "
            continue
        buffer += line
        if buffer.strip():
            lines.append((start, buffer.strip()))
        buffer = ""
    if buffer.strip():
        lines.append((start, buffer.strip()))
    return lines


def check_requirements(text: str) -> list[Issue]:
    issues: list[Issue] = []
    for number, line in _logical_lines(text):
        tokens = line.split()
        if tokens[0].startswith("-"):  # an option such as --index-url, not a requirement
            continue
        name, rest = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)(.*)$", tokens[0]).groups()
        where = f"line {number}"
        if not re.fullmatch(r"==\d+(\.\d+)*", rest):
            issues.append(Issue(where, f"{name}: not pinned to an exact version with =="))
        if not any(re.fullmatch(r"--hash=sha256:[0-9a-f]{64}", token) for token in tokens[1:]):
            issues.append(Issue(where, f"{name}: no sha256 --hash"))
    return sorted(issues, key=lambda i: (int(i.where.split()[1]), i.reason))


def check_lockfile(lock: dict, allowed_hosts: tuple[str, ...] = ("registry.npmjs.org",)) -> list[Issue]:
    issues: list[Issue] = []
    for path, meta in lock.get("packages", {}).items():
        if path == "" or meta.get("link"):  # the project itself, and a link to a folder on disk
            continue
        resolved, integrity = meta.get("resolved"), meta.get("integrity")
        if not resolved:
            issues.append(Issue(path, "no resolved URL"))
        elif resolved.startswith("git+"):
            if not re.search(r"#[0-9a-f]{40}$", resolved):
                issues.append(Issue(path, "git dependency not pinned to a commit"))
            continue  # a git dependency is identified by its commit, not an integrity string
        else:
            url = urlparse(resolved)
            if url.scheme != "https":
                issues.append(Issue(path, "resolved over http, not https"))
            if url.hostname not in allowed_hosts:
                issues.append(Issue(path, f"resolved from {url.hostname}, not an allowed registry"))
        if not integrity:
            issues.append(Issue(path, "no integrity hash"))
        elif not integrity.startswith("sha512-"):
            issues.append(Issue(path, "integrity is not sha512"))
    return sorted(issues, key=lambda i: (i.where, i.reason))
