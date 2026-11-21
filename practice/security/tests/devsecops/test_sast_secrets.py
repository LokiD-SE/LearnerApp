"""Checks exercises/devsecops/sast_secrets.py: regex + entropy + stop words, and never the full secret."""

import math

import pytest
from devsecops.sast_secrets import SecretFinding, redact, scan_text, shannon_entropy
from sast_fixture import PORTAL_SOURCE, SETTINGS_FILE

pytestmark = pytest.mark.exercise

KEY = "sp_live_Zk3pQ9vL2mXa7TdRw4Ns8BhY"


def test_entropy_of_known_strings():
    assert shannon_entropy("") == 0.0
    assert shannon_entropy("aaaa") == 0.0
    assert shannon_entropy("abcd") == pytest.approx(2.0)
    assert shannon_entropy("aabb") == pytest.approx(1.0)
    assert shannon_entropy("Zk3pQ9vL2mXa7TdRw4Ns8BhY") == pytest.approx(math.log2(24))


def test_redact_keeps_four_characters():
    assert redact(KEY) == "sp_l***"
    assert redact("abcd") == "***"
    assert redact("") == "***"


def test_the_settings_file_has_exactly_three_findings():
    got = [(f.line, f.rule_id, f.redacted) for f in scan_text(SETTINGS_FILE, "settings.py")]
    assert got == [
        (1, "sandpay-api-key", "sp_l***"),
        (2, "generic-secret", "r7Q!***"),
        (8, "private-key-block", "----***"),
    ]


def test_what_is_ignored_and_why():
    text = SETTINGS_FILE
    lines = {f.line for f in scan_text(text)}
    assert 3 not in lines  # stop word: YOUR_API_KEY_HERE
    assert 4 not in lines  # stop word: changeme (and low entropy)
    assert 5 not in lines  # the scanner:allow comment
    assert 6 not in lines  # the value is a header NAME: too little entropy to be a secret
    assert 7 not in lines  # no secret-looking key name


def test_a_finding_never_holds_the_secret():
    findings = scan_text(SETTINGS_FILE, "settings.py")
    assert findings and all(isinstance(f, SecretFinding) for f in findings)
    text = repr(findings)
    for secret in (KEY, "r7Q!mZ2x#Lw9vKp4", "Zk3pQ9vL2mXa7TdRw4Ns8BhY"):
        assert secret not in text
    assert findings[0].entropy == pytest.approx(shannon_entropy(KEY), abs=0.01)


def test_the_specific_rule_wins_over_the_generic_one():
    findings = scan_text(f'api_key = "{KEY}"\n')
    assert [(f.line, f.rule_id) for f in findings] == [(1, "sandpay-api-key")]


def test_allow_paths_skip_whole_files():
    assert scan_text(SETTINGS_FILE, "tests/fixtures/settings.py", allow_paths=("tests/",)) == []
    assert len(scan_text(SETTINGS_FILE, "src/settings.py", allow_paths=("tests/",))) == 3


def test_low_entropy_values_are_dropped_by_the_entropy_filter():
    assert scan_text('db_password = "aaaaaaaaaaaa"\n') == []
    assert scan_text('db_password = "k9X#vQ2mLp7z"\n')[0].rule_id == "generic-secret"


def test_line_numbers_count_from_one_across_blank_lines():
    assert [f.line for f in scan_text(f'\n\nTOKEN = "{KEY}"\n')] == [3]


def test_the_practice_portal_has_one_false_positive_and_no_real_secret():
    findings = scan_text(PORTAL_SOURCE.read_text(), "sandpay_vuln.py")
    lines = PORTAL_SOURCE.read_text().splitlines()
    assert [lines[f.line - 1].split("=")[0].strip() for f in findings] == ["SECRET_FILE"]
