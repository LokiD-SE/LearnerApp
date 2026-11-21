"""Checks exercises/specialised/mob_storage.py: where a file lives and what sensitive data it holds."""

import pytest
import mob_fixture as fx
from specialised.mob_storage import location, mask, scan_dump

pytestmark = pytest.mark.exercise

PKG = fx.PKG


def test_the_dump_gives_exactly_the_expected_findings():
    assert scan_dump(fx.DUMP) == [
        (f"{PKG}/files/cache.json", "password", "private"),
        (f"{PKG}/files/keystore.pem", "private-key", "private"),
        (f"{PKG}/shared_prefs/session.xml", "token", "private"),
        ("/data/local/tmp/logcat.txt", "token", "log"),
        ("/sdcard/Download/export.csv", "token", "shared"),
    ]


def test_a_clean_dump_has_no_findings():
    assert scan_dump(fx.CLEAN_DUMP) == []
    assert scan_dump({}) == []


def test_the_result_never_contains_a_secret_value():
    text = str(scan_dump(fx.DUMP))
    for secret in ("FAKE", "demo-pass", "PRIVATE KEY", "ZGVtby"):
        assert secret not in text


def test_every_finding_kind_has_a_weakness_in_the_fixture_table():
    for _path, kind, _where in scan_dump(fx.DUMP):
        assert fx.WEAKNESS_OF[kind][0] == "MASWE-0001"


@pytest.mark.parametrize("path, expected", [
    ("/sdcard/Download/a.txt", "shared"),
    ("/storage/emulated/0/Android/data/x/files/a", "shared"),
    ("/mnt/sdcard/a", "shared"),
    ("/data/data/example.sandpay.merchant/files/a", "private"),
    ("/data/user/0/example.sandpay.merchant/files/a", "private"),
    ("/data/local/tmp/logcat.txt", "log"),
    ("/tmp/LogCat-2026.txt", "log"),
    ("/data/data/example.sandpay.merchant/files/app.log", "private"),
    ("/somewhere/else.txt", "unknown"),
])
def test_location_is_decided_by_the_path(path, expected):
    assert location(path) == expected


def test_mask_keeps_only_the_length():
    assert mask("abcdef") == "[REDACTED:6 chars]"
    assert mask("") == "[REDACTED:0 chars]"
    assert "abc" not in mask("abcdef")


@pytest.mark.parametrize("text, kind", [
    ('<string name="auth_token">abcd1234</string>', "token"),
    ('{"API_KEY": "abcd1234"}', "token"),
    ("client-secret=abcd1234", "token"),
    ("apikey: abcd1234", "token"),
    ('{"password":"abcd1234"}', "password"),
    ("db.passwd=abcd1234", "password"),
    ("PWD = abcd1234", "password"),
    ("Authorization: Bearer abcdefgh.ijkl", "token"),
    ("eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl", "token"),
])
def test_each_kind_is_recognised_in_the_shapes_apps_use(text, kind):
    assert scan_dump({f"{PKG}/files/x": text}) == [(f"{PKG}/files/x", kind, "private")]


@pytest.mark.parametrize("text", [
    '<string name="access_token">[REDACTED]</string>',
    "password=[redacted]",
    "token=null",
    "secret=NONE",
    "password=true",
    "token=abc",
    "Authorization: Bearer [REDACTED]",
    "Bearer short",
    "language=en",
    "refresh_interval=30",
    "eyJhbGciOi.notajwt.c2lnbmF0dXJl",
])
def test_redacted_empty_short_and_unrelated_values_are_not_findings(text):
    assert scan_dump({f"{PKG}/files/x": text}) == []


def test_one_file_can_produce_several_kinds_and_repeats_collapse():
    text = "password=abcd1234\npassword=efgh5678\ntoken=ijkl9012\n"
    assert scan_dump({f"{PKG}/files/x": text}) == [
        (f"{PKG}/files/x", "password", "private"),
        (f"{PKG}/files/x", "token", "private"),
    ]


def test_the_same_secret_in_a_shared_file_is_reported_with_that_location():
    assert scan_dump({"/sdcard/a.txt": "token=abcd1234"}) == [("/sdcard/a.txt", "token", "shared")]


def test_the_input_is_not_modified():
    files = dict(fx.DUMP)
    scan_dump(files)
    assert files == fx.DUMP
