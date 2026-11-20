"""The fix for path traversal: allow-list the name, resolve the path, check containment, use what you checked.

The OWASP Path Traversal Prevention Cheat Sheet: "The most reliable defense is to never put user input into a
path"; when a name must be accepted, "restrict it to a simple allowlist of characters ... This is an extra layer,
not a replacement for the containment check", and "resolve the full path first and then check that the result is
still inside the intended base directory", comparing path components - not string prefixes - so that
``/srv/uploads-old`` does not pass a check for ``/srv/uploads``. "Don't try to remove ``../`` from the input
instead."

``naive_read`` is the vulnerable original, kept for comparison. ``resolve_inside`` is the fix and ``read_public``
the handler built on it. The name has already been URL-decoded exactly once by the web framework; these
functions never decode it again (the cheat sheet: "don't decode it again afterwards").
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# A segment starts with a letter, digit, "_" or "-" - so never "." or ".." and never a hidden file - and continues
# with letters, digits, "." "_" "-". No separators, no ":" (NTFS streams), no spaces, no "%".
SEGMENT = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]{0,99}")
MAX_SEGMENTS = 4


class PathRejected(ValueError):
    """The name is not an acceptable file name, or it resolves outside the base folder."""


def naive_read(base: str | Path, name: str) -> str:
    """VULNERABLE - 'removes' ../ and joins. ``....//`` becomes ``../``; an absolute name replaces the base."""
    cleaned = name.replace("../", "")
    return Path(os.path.join(base, cleaned)).read_text()


def resolve_inside(base: str | Path, name: str) -> Path:
    """The real path of the file ``name`` inside ``base``, or an exception.

    1. Reject (PathRejected) a name that is empty, has more than ``MAX_SEGMENTS`` parts when split on ``/``, or
       has any part that does not fully match ``SEGMENT``. This also rejects ``..``, ``\\``, ``:``, ``%``,
       NUL, absolute paths and drive letters.
    2. Resolve with ``os.path.realpath`` - the base and the joined path - which also follows symbolic links.
    3. Reject (PathRejected) unless the resolved path is strictly inside the resolved base: compare whole
       components with ``os.path.commonpath`` (catch ValueError as a rejection) and refuse the base itself.
    4. Raise FileNotFoundError unless it is an existing regular file, and return the resolved path.
    """
    raise NotImplementedError("TODO: resolve_inside")


def read_public(base: str | Path, name: str) -> tuple[int, str]:
    """``(200, text)`` for a file inside ``base``; ``(404, "file not found")`` for everything else.

    A rejected name, an escape and a missing file must look identical, and the message must not repeat the
    input or the resolved path - otherwise the response tells a tester which folders exist.
    """
    raise NotImplementedError("TODO: read_public")