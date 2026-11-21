"""EXERCISE - check that what you install is exactly what you reviewed.

* ``check_requirements(text)`` - lint a pip requirements file for hash-checking mode. Join ``\\`` continuation
  lines, drop ``# comments``, skip option lines (they start with ``-``, such as ``--index-url``). Every other
  logical line is one requirement and may give up to two ``Issue`` values, with ``where = "line N"`` (N is the
  line the requirement STARTS on):
    - ``"<name>: not pinned to an exact version with =="`` unless the spec is exactly ``name==1.2.3`` (digits and
      dots; ``>=``, ``~=``, ``==1.*`` and a bare name all fail);
    - ``"<name>: no sha256 --hash"`` unless at least one token is ``--hash=sha256:`` plus 64 lowercase hex
      characters (an ``md5`` hash does not count).
  Return the issues sorted by line number, then reason.
* ``check_lockfile(lock, allowed_hosts)`` - lint an npm ``package-lock.json`` (already parsed into a dict). Look at
  every entry of ``packages`` except the project itself (key ``""``) and links (``"link": true``). ``where`` is the
  package path. Issues, with these exact reasons:
    - no ``resolved``: ``"no resolved URL"``;
    - ``resolved`` starting ``git+``: ``"git dependency not pinned to a commit"`` unless it ends with ``#`` and a
      40-character lowercase hex commit - and a git dependency gets no integrity check;
    - any other ``resolved``: ``"resolved over http, not https"`` unless the scheme is https, and
      ``"resolved from <host>, not an allowed registry"`` unless the host is in ``allowed_hosts``;
    - ``integrity`` missing: ``"no integrity hash"``; not starting ``sha512-``: ``"integrity is not sha512"``
      (a house rule - npm also accepts sha1).
  Return the issues sorted by ``(where, reason)``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    where: str  # "line 3" for a requirements file, the package path for a lockfile
    reason: str


def check_requirements(text: str) -> list[Issue]:
    raise NotImplementedError("TODO: implement check_requirements")


def check_lockfile(lock: dict, allowed_hosts: tuple[str, ...] = ("registry.npmjs.org",)) -> list[Issue]:
    raise NotImplementedError("TODO: implement check_lockfile")
