"""EXERCISE - look for sensitive data in a dump of an app's files, without ever repeating the value.

The input is a dict ``{path: text}`` pulled from a test device you own (see ``DUMP`` and ``CLEAN_DUMP`` in
``support/mob_fixture.py``; every secret in them is fake).

* ``location(path)`` - where the file lives, by its path: ``"shared"`` when it starts with ``/sdcard/``, ``/storage/``
  or ``/mnt/sdcard/``; ``"private"`` when it starts with ``/data/data/`` or ``/data/user/``; ``"log"`` when its file name
  (case-insensitive) starts with ``logcat``; otherwise ``"unknown"``. Check them in that order.
* ``mask(value)`` - the text to put in a report instead of a secret: ``"[REDACTED:<n> chars]"`` with the value's length.
* ``scan_dump(files)`` - a SORTED list of ``(path, kind, location)`` tuples without repeats, ``kind`` being:
    - ``token``: a key whose name holds ``token``, ``secret`` or ``api_key`` (also ``api-key``, ``apikey``) followed by ``=``,
      ``:`` or an XML ``">`` and a value of 4 or more characters; a ``Bearer <8 or more token characters>`` header; or a
      JWT-shaped string (three dot-separated parts, the first two starting ``eyJ``);
    - ``password``: a key whose name holds ``password``, ``passwd`` or ``pwd`` with such a value;
    - ``private-key``: a ``-----BEGIN ... PRIVATE KEY-----`` line.
  A value that starts with ``[REDACTED`` or is ``null``, ``none``, ``true``, ``false`` or ``undefined`` (any case) is not a secret.
  The result must NEVER contain a secret value, only the path, the kind and the location. Key names are matched
  case-insensitively; a file can produce several kinds. House rules for a first pass, not a complete scanner.
"""

from __future__ import annotations

import re


def location(path: str) -> str:
    raise NotImplementedError("TODO: classify the path")


def mask(value: str) -> str:
    raise NotImplementedError("TODO: mask a value")


def scan_dump(files: dict[str, str]) -> list[tuple[str, str, str]]:
    raise NotImplementedError("TODO: scan every file")
