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
    """Finding codes for one environment's settings, sorted; ``[]`` means nothing to report."""
    found = set()
    if settings.get("debug") is True:
        found.add("debug-enabled")
    if "error_detail" in settings and settings["error_detail"] != "generic":
        found.add("verbose-errors")
    if _has_version(settings.get("server_banner", "")):
        found.add("version-banner")
    for account in settings.get("accounts", []):
        if account.get("name") in DEFAULT_NAMES and account.get("password_changed") is not True:
            found.add("default-credentials")
    if settings.get("directory_listing") is True:
        found.add("directory-listing")
    if settings.get("sample_apps") is True:
        found.add("sample-content")
    if settings.get("admin_public") is True:
        found.add("admin-public")
    if settings.get("admin_auth") is False:
        found.add("admin-no-auth")
    if "TRACE" in [m.upper() for m in settings.get("http_methods", [])]:
        found.add("trace-enabled")
    if settings.get("shared_secrets") is True:
        found.add("shared-secrets")
    return sorted(found)


def harden(settings: dict) -> dict:
    """A hardened copy: every finding of ``review_config`` fixed, everything else (and the input) untouched."""
    out = copy.deepcopy(settings)
    if "debug" in out:
        out["debug"] = False
    if "error_detail" in out:
        out["error_detail"] = "generic"
    if "server_banner" in out:
        out["server_banner"] = "SandPay"
    for account in out.get("accounts", []):
        if account.get("name") in DEFAULT_NAMES:
            account["password_changed"] = True
    for key in ("directory_listing", "sample_apps", "admin_public", "shared_secrets"):
        if key in out:
            out[key] = False
    if "admin_auth" in out:
        out["admin_auth"] = True
    if "http_methods" in out:
        out["http_methods"] = [m for m in out["http_methods"] if m.upper() != "TRACE"]
    return out
