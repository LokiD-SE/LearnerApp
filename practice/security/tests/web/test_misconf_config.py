import copy

import pytest
from web.misconf_config import harden, review_config

pytestmark = pytest.mark.exercise

BAD = {
    "debug": True,
    "error_detail": "full",
    "server_banner": "SandPayPortal/0.9 Python/3.12",
    "accounts": [{"name": "admin", "password_changed": False}, {"name": "ana", "password_changed": False}],
    "directory_listing": True,
    "sample_apps": True,
    "admin_public": True,
    "admin_auth": False,
    "http_methods": ["GET", "POST", "TRACE"],
    "shared_secrets": True,
    "region": "eu-west",
}
ALL = [
    "admin-no-auth", "admin-public", "debug-enabled", "default-credentials", "directory-listing",
    "sample-content", "shared-secrets", "trace-enabled", "verbose-errors", "version-banner",
]


def test_empty_settings_have_nothing_to_report():
    assert review_config({}) == []


def test_every_finding_is_reported():
    assert review_config(BAD) == ALL


@pytest.mark.parametrize("key, value, code", [
    ("debug", True, "debug-enabled"),
    ("error_detail", "full", "verbose-errors"),
    ("error_detail", "trace", "verbose-errors"),
    ("server_banner", "nginx/1.25.3", "version-banner"),
    ("directory_listing", True, "directory-listing"),
    ("sample_apps", True, "sample-content"),
    ("admin_public", True, "admin-public"),
    ("admin_auth", False, "admin-no-auth"),
    ("http_methods", ["get", "trace"], "trace-enabled"),
    ("shared_secrets", True, "shared-secrets"),
])
def test_one_setting_one_finding(key, value, code):
    assert review_config({key: value}) == [code]


@pytest.mark.parametrize("settings", [
    {"debug": False, "error_detail": "generic", "server_banner": "SandPay", "admin_auth": True},
    {"accounts": [{"name": "admin", "password_changed": True}, {"name": "ana"}]},
    {"http_methods": ["GET", "HEAD", "OPTIONS"], "directory_listing": False},
])
def test_secure_settings_are_quiet(settings):
    assert review_config(settings) == []


def test_default_account_names_need_a_changed_password():
    assert review_config({"accounts": [{"name": "root"}]}) == ["default-credentials"]
    assert review_config({"accounts": [{"name": "guest", "password_changed": False}]}) == ["default-credentials"]
    assert review_config({"accounts": [{"name": "ana", "password_changed": False}]}) == []


def test_missing_keys_never_produce_findings():
    assert review_config({"region": "eu-west"}) == []
    assert review_config({"admin_public": False}) == []


def test_harden_fixes_everything_and_keeps_the_rest():
    fixed = harden(BAD)
    assert review_config(fixed) == []
    assert fixed["region"] == "eu-west"
    assert fixed["http_methods"] == ["GET", "POST"]
    assert [a["name"] for a in fixed["accounts"]] == ["admin", "ana"]


def test_harden_does_not_edit_its_argument_and_adds_no_keys():
    before = copy.deepcopy(BAD)
    harden(BAD)
    assert BAD == before
    assert harden({"debug": True}) == {"debug": False}
