"""Review a deployment's settings for security misconfiguration (WSTG-CONFIG, Top 10 A05) and harden them.

Exercise - fill in the TODOs; ``tests/web/test_misconf_config.py`` checks your work. ``settings`` is a plain dict
describing one environment; a missing key means "nothing to report" for that check. The findings, and where each
comes from:

- ``debug-enabled``: ``debug`` is true. WSTG-CONFIG-02: no "debug modes ... left enabled in production".
- ``verbose-errors``: ``error_detail`` is ``"full"`` (anything other than ``"generic"`` counts when present).
  Top 10 A05: "Error handling reveals stack traces or other overly informative error messages to users."
- ``version-banner``: ``server_banner`` contains a version number (RFC 9110 section 10.2.4).
- ``default-credentials``: an entry in ``accounts`` whose ``name`` is one of ``admin``, ``root``, ``test``,
  ``guest`` and whose ``password_changed`` is not true. Top 10 A05: "Default accounts and their passwords are
  still enabled and unchanged."
- ``directory-listing``: ``directory_listing`` is true (Top 10 A05 scenario 2).
- ``sample-content``: ``sample_apps`` is true (Top 10 A05 scenario 1: "sample applications not removed").
- ``admin-public``: ``admin_public`` is true. WSTG-CONFIG-05: check for "exposure to networks/users beyond those
  intended".
- ``admin-no-auth``: ``admin_auth`` is false.
- ``trace-enabled``: ``"TRACE"`` is in ``http_methods`` (WSTG-CONFIG-06: suggests the server "has not been
  properly hardened").
- ``shared-secrets``: ``shared_secrets`` is true - Top 10 A05: "different credentials used in each environment".
"""

from __future__ import annotations

import copy
import re

DEFAULT_NAMES = {"admin", "root", "test", "guest"}


def _has_version(banner: str) -> bool:
    return bool(re.search(r"/\s*\d|\d+\.\d+", banner))


def review_config(settings: dict) -> list[str]:
    """Finding codes for one environment's settings, sorted; ``[]`` means nothing to report.

    TODO: apply each rule in the module docstring. Test booleans with ``is True`` / ``is False`` so that a
    missing key never produces a finding, and use ``_has_version`` for the banner.
    """
    raise NotImplementedError("review_config")


def harden(settings: dict) -> dict:
    """A hardened copy: every finding of ``review_config`` fixed, everything else (and the input) untouched.

    TODO: ``copy.deepcopy`` first (never edit the argument). Turn off debug, directory listing, sample apps,
    public admin and shared secrets; set ``error_detail`` to ``"generic"``, ``server_banner`` to ``"SandPay"``,
    ``admin_auth`` to true; mark default accounts' ``password_changed``; drop ``TRACE`` from ``http_methods``.
    Only touch keys that are present.
    """
    raise NotImplementedError("harden")
