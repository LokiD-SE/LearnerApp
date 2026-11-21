"""Checks exercises/devsecops/sast_triage.py: stable fingerprints, suppressions, a baseline and the gate."""

import pytest
from devsecops.sast_triage import fingerprint, gate, is_suppressed, make_baseline

pytestmark = pytest.mark.exercise


def finding(rule="sql-built-from-string", path="app/pay.py", line=10, severity="HIGH", text="db.execute(f'{x}')"):
    return {"rule_id": rule, "path": path, "line": line, "severity": severity, "text": text}


def test_fingerprint_is_16_hex_characters_and_ignores_the_line_number():
    a = fingerprint("r", "app/pay.py", "db.execute(f'{x}')")
    assert len(a) == 16 and int(a, 16) >= 0
    assert a == fingerprint("r", "app/pay.py", "   db.execute(f'{x}')  ")  # indentation and trailing space
    assert a == fingerprint("r", "app/pay.py", "db.execute(f'{x}')".replace(" ", "  "))  # inner whitespace
    assert a != fingerprint("other", "app/pay.py", "db.execute(f'{x}')")
    assert a != fingerprint("r", "app/refund.py", "db.execute(f'{x}')")
    assert a != fingerprint("r", "app/pay.py", "db.execute(f'{y}')")


def test_fingerprint_follows_the_documented_recipe():
    import hashlib
    assert fingerprint("r", "a.py", "x  =  1") == hashlib.sha256(b"r:a.py:x = 1").hexdigest()[:16]


LINES = [
    "def a():",                                          # 1
    "    # nosemgrep",                                   # 2
    "    eval(x)",                                       # 3
    "",                                                  # 4
    "    eval(y)  # nosemgrep: eval-exec",               # 5
    "",                                                  # 6
    "    eval(z)  # nosemgrep: weak-hash, tls-verify-off",  # 7
    "",                                                  # 8
    "    eval(w)  # nosemgrep: weak-hash, eval-exec",    # 9
    "",                                                  # 10
    "    eval(v)",                                       # 11
]


@pytest.mark.parametrize("line_no, rule, expected", [
    (3, "eval-exec", True),    # a bare comment on the line above suppresses every rule
    (3, "weak-hash", True),
    (5, "eval-exec", True),    # a same-line comment naming the rule
    (5, "weak-hash", False),   # ... does not suppress other rules
    (7, "eval-exec", False),   # a comment that names two OTHER rules
    (9, "eval-exec", True),    # the rule is second in the list
    (11, "eval-exec", False),  # no comment on the line or above
    (2, "eval-exec", True),    # the comment line itself
    (1, "eval-exec", False),
    (6, "eval-exec", True),    # a comment also covers the line AFTER it - the "preceding line" rule
])
def test_is_suppressed(line_no, rule, expected):
    assert is_suppressed(LINES, line_no, rule) is expected


def test_is_suppressed_ignores_line_numbers_outside_the_file():
    assert is_suppressed(LINES, 0, "x") is False
    assert is_suppressed(LINES, 99, "x") is False
    assert is_suppressed([], 1, "x") is False


def test_the_baseline_is_sorted_and_deduplicated():
    a, b = finding(text="one"), finding(text="two")
    baseline = make_baseline([b, a, a])
    assert baseline == sorted(baseline) and len(baseline) == 2
    assert baseline == sorted({fingerprint(f["rule_id"], f["path"], f["text"]) for f in (a, b)})


def test_a_baselined_finding_does_not_block_even_after_it_moves():
    old = finding(line=10)
    baseline = make_baseline([old])
    moved = finding(line=42)  # someone inserted 32 lines above it
    result = gate([moved], baseline)
    assert result == {"exit_code": 0, "blocking": [], "new": [], "known": 1}


def test_a_new_high_finding_blocks():
    baseline = make_baseline([finding(text="old")])
    fresh = finding(text="db.execute(f'{status}')", line=7)
    result = gate([finding(text="old"), fresh], baseline)
    assert result["exit_code"] == 1
    assert result["blocking"] == [fresh] and result["new"] == [fresh] and result["known"] == 1


def test_new_findings_below_the_threshold_are_reported_but_do_not_block():
    low = finding(rule="weak-hash", severity="MEDIUM", text="hashlib.md5(x)")
    result = gate([low], [], fail_on="HIGH")
    assert (result["exit_code"], result["blocking"], result["new"]) == (0, [], [low])
    assert gate([low], [], fail_on="MEDIUM")["exit_code"] == 1
    assert gate([low], [], fail_on="CRITICAL")["exit_code"] == 0


def test_the_baseline_can_be_a_set_or_a_list():
    f = finding()
    assert gate([f], set(make_baseline([f])))["exit_code"] == 0
    assert gate([f], make_baseline([f]))["exit_code"] == 0


def test_no_findings_passes():
    assert gate([], []) == {"exit_code": 0, "blocking": [], "new": [], "known": 0}


def test_a_typo_never_opens_the_gate():
    with pytest.raises(ValueError):
        gate([finding()], [], fail_on="SEVERE")
    with pytest.raises(ValueError):
        gate([finding(severity="High")], [])
