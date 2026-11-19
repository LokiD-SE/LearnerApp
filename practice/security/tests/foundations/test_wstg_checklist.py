import pytest
from foundations.wstg_checklist import Coverage, Item, category_of, coverage, failing, parse_checklist
from wstg_fixture import WSTG_V42_CHECKLIST

pytestmark = pytest.mark.exercise

FILLED = """\
| Test ID           | Test Name                                  | Status | Notes |
|-------------------|--------------------------------------------|--------|-------|
| **WSTG-INFO**     | **Information Gathering**                  |        |       |
| WSTG-INFO-02      | Fingerprint Web Server                     | Fail   | Server: SandPayPortal/0.9 Python/3.12 |
| WSTG-INFO-03      | Review Webserver Metafiles for Information Leakage | Pass |  |
| WSTG-INFO-04      | Enumerate Applications on Webserver        | n/a    | single app |
| **WSTG-ATHZ**     | **Authorization Testing**                  |        |       |
| WSTG-ATHZ-04      | Testing for Insecure Direct Object References | FAIL | pay_2001 readable by m_100 |
| WSTG-ATHZ-03      | Testing for Privilege Escalation           |        |       |
| **WSTG-BUSLOGIC** | **Business Logic Testing**                 |        |       |
| WSTG-BUSL-01      | Test Business Logic Data Validation        | Pass   |       |
"""


def test_parses_the_real_v42_checklist():
    items = parse_checklist(WSTG_V42_CHECKLIST)
    assert len(items) == 97
    assert items[0] == Item("WSTG-INFO-01", "Conduct Search Engine Discovery and Reconnaissance for Information Leakage",
                            "Not tested", "")
    assert items[-1].test_id == "WSTG-APIT-01"
    assert all(i.status == "Not tested" for i in items)


def test_normalises_status_and_keeps_notes():
    items = parse_checklist(FILLED)
    assert [(i.test_id, i.status) for i in items] == [
        ("WSTG-INFO-02", "Fail"), ("WSTG-INFO-03", "Pass"), ("WSTG-INFO-04", "N/A"),
        ("WSTG-ATHZ-04", "Fail"), ("WSTG-ATHZ-03", "Not tested"), ("WSTG-BUSL-01", "Pass")]
    assert items[0].notes == "Server: SandPayPortal/0.9 Python/3.12"
    assert items[3].name == "Testing for Insecure Direct Object References"


def test_category_comes_from_the_test_id_not_the_bold_row():
    assert category_of("WSTG-ATHN-03") == "WSTG-ATHN"
    cov = coverage(parse_checklist(FILLED))
    assert list(cov) == ["WSTG-INFO", "WSTG-ATHZ", "WSTG-BUSL"]
    assert "WSTG-BUSLOGIC" not in cov


def test_coverage_counts_and_percent():
    cov = coverage(parse_checklist(FILLED))
    assert cov["WSTG-INFO"] == Coverage(total=3, passed=1, failed=1, not_applicable=1, not_tested=0, percent_done=100.0)
    assert cov["WSTG-ATHZ"] == Coverage(total=2, passed=0, failed=1, not_applicable=0, not_tested=1, percent_done=50.0)


def test_real_checklist_categories_start_at_zero():
    cov = coverage(parse_checklist(WSTG_V42_CHECKLIST))
    assert len(cov) == 12
    assert cov["WSTG-INPV"].total == 19 and cov["WSTG-CLNT"].total == 13
    assert all(c.percent_done == 0.0 for c in cov.values())


def test_percent_is_rounded_to_one_decimal():
    rows = "\n".join(f"| WSTG-CONF-0{n} | t | {'Pass' if n == 1 else ''} | |" for n in range(1, 4))
    assert coverage(parse_checklist(rows))["WSTG-CONF"].percent_done == 33.3


def test_failing_in_checklist_order():
    assert failing(parse_checklist(FILLED)) == ["WSTG-INFO-02", "WSTG-ATHZ-04"]


@pytest.mark.parametrize("row, word", [
    ("| WSTG-INF-02 | Fingerprint | Pass | |", "WSTG-INF-02"),
    ("| OTG-INFO-002 | Fingerprint | Pass | |", "OTG-INFO-002"),
    ("| WSTG-INFO-02 | Fingerprint | Done | |", "Done"),
])
def test_rejects_bad_ids_and_statuses(row, word):
    with pytest.raises(ValueError, match=word):
        parse_checklist(row)


def test_category_of_rejects_a_category_id():
    with pytest.raises(ValueError):
        category_of("WSTG-INFO")
