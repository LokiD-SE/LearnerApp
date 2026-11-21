"""SOLUTION - look for sensitive data in a dump of an app's files, without ever repeating the value."""

from __future__ import annotations

import re

KEYVAL = re.compile(
    r"""(?ix)
    (?P<key>[\w.-]*(?:token|secret|api[_-]?key|password|passwd|pwd)[\w.-]*)
    (?:["']?\s*[:=]\s*["']?|["']\s*>)
    (?P<val>[^\s"'<>,}&]{4,})"""
)
BEARER = re.compile(r"Bearer\s+(?!\[REDACTED)[A-Za-z0-9._~+/=-]{8,}")
JWT = re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")
EMPTY_VALUES = {"null", "none", "true", "false", "undefined"}
PRIVATE_PREFIXES = ("/data/data/", "/data/user/")
SHARED_PREFIXES = ("/sdcard/", "/storage/", "/mnt/sdcard/")


def location(path: str) -> str:
    if path.startswith(SHARED_PREFIXES):
        return "shared"
    if path.startswith(PRIVATE_PREFIXES):
        return "private"
    if path.rsplit("/", 1)[-1].lower().startswith("logcat"):
        return "log"
    return "unknown"


def mask(value: str) -> str:
    return f"[REDACTED:{len(value)} chars]"


def kinds_in(text: str) -> set[str]:
    kinds: set[str] = set()
    for match in KEYVAL.finditer(text):
        value = match.group("val")
        if value.upper().startswith("[REDACTED") or value.lower() in EMPTY_VALUES:
            continue
        key = match.group("key").lower()
        kinds.add("password" if re.search(r"password|passwd|pwd", key) else "token")
    if BEARER.search(text) or JWT.search(text):
        kinds.add("token")
    if PRIVATE_KEY.search(text):
        kinds.add("private-key")
    return kinds


def scan_dump(files: dict[str, str]) -> list[tuple[str, str, str]]:
    found = set()
    for path, text in files.items():
        for kind in kinds_in(text):
            found.add((path, kind, location(path)))
    return sorted(found)
