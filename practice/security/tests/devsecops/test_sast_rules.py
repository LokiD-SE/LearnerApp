"""Checks exercises/devsecops/sast_rules.py: five rules that find the flaw and stay quiet when it is fixed."""

import pytest
from devsecops.sast_rules import RULES, Finding, scan_source
from sast_fixture import FIXED_HANDLERS, PORTAL_SOURCE, VULNERABLE_HANDLERS

pytestmark = pytest.mark.exercise


def found(source):
    return [(f.line, f.rule_id) for f in scan_source(source, "handlers.py")]


def test_every_flaw_in_the_vulnerable_handlers_is_found_on_its_line():
    assert found(VULNERABLE_HANDLERS) == [
        (8, "sql-built-from-string"),   # f-string
        (12, "sql-built-from-string"),  # + concatenation
        (16, "sql-built-from-string"),  # .format
        (20, "sql-built-from-string"),  # % formatting
        (24, "eval-exec"),
        (28, "shell-true"),
        (32, "weak-hash"),
        (36, "tls-verify-off"),
    ]


def test_the_fixed_handlers_are_quiet():
    assert scan_source(FIXED_HANDLERS, "handlers.py") == []


def test_findings_carry_the_severity_and_message_of_the_rule():
    finding = scan_source(VULNERABLE_HANDLERS)[0]
    assert isinstance(finding, Finding)
    assert (finding.severity, finding.message) == RULES["sql-built-from-string"]
    weak = [f for f in scan_source(VULNERABLE_HANDLERS) if f.rule_id == "weak-hash"][0]
    assert weak.severity == "MEDIUM"


@pytest.mark.parametrize("code", [
    'db.execute("SELECT 1")',
    'db.execute(QUERY, (status,))',
    'db.execute("SELECT * FROM t WHERE a = ?", (status,))',
    'db.execute("SELECT id " + "FROM t")',
    'db.execute("SELECT {}".format("1"))',
    'ast.literal_eval(text)',
    'subprocess.run(["ls", "-l"], shell=False)',
    'hashlib.sha256(blob).hexdigest()',
    'hashlib.md5(blob, usedforsecurity=False)',
    'requests.get(url, verify=True)',
    'requests.get(url, verify=ca_bundle)',
])
def test_safe_shapes_are_not_reported(code):
    assert scan_source(code) == []


@pytest.mark.parametrize("code, rule", [
    ('cursor.executemany(f"INSERT INTO t VALUES ({cols})", rows)', "sql-built-from-string"),
    ('self.query("SELECT * FROM t WHERE a = " + a)', "sql-built-from-string"),
    ('exec(code)', "eval-exec"),
    ('subprocess.check_output(cmd, shell=True)', "shell-true"),
    ('hashlib.sha1(data).hexdigest()', "weak-hash"),
    ('session.post(url, json=body, verify=False)', "tls-verify-off"),
])
def test_other_risky_shapes_are_reported_once(code, rule):
    assert [f.rule_id for f in scan_source(code)] == [rule]


def test_a_multi_line_call_is_reported_on_the_line_where_it_starts():
    code = 'rows = self.query(\n    f"SELECT * FROM t WHERE a = \'{a}\'")\n'
    assert [(f.line, f.rule_id) for f in scan_source(code)] == [(1, "sql-built-from-string")]


def test_one_call_can_trip_two_rules_in_rule_order():
    code = 'subprocess.run(cmd, shell=True, verify=False)\n'
    assert [f.rule_id for f in scan_source(code)] == ["shell-true", "tls-verify-off"]


def test_an_unparseable_file_raises_instead_of_looking_clean():
    with pytest.raises(ValueError) as err:
        scan_source("def broken(:\n", "bad.py")
    assert str(err.value).startswith("cannot parse bad.py:")


def test_the_practice_portal_has_a_weak_hash_and_two_string_built_queries():
    source = PORTAL_SOURCE.read_text()
    lines = source.splitlines()
    hits = [(f.rule_id, lines[f.line - 1].strip()) for f in scan_source(source, "sandpay_vuln.py")]
    assert [rule for rule, _ in hits] == ["weak-hash", "sql-built-from-string", "sql-built-from-string"]
    assert "hashlib.md5" in hits[0][1]
    # one is the real injection (status comes from the query string), one only formats an allow-listed column
    assert any("UPDATE users SET {key}" in text for _, text in hits)
    assert any(text.startswith("rows = self.query(") for _, text in hits)
