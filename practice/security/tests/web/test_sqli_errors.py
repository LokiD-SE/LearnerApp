import pytest
import requests
from sandpay_vuln import make_app, serve
from web.sqli_detect import portal_sender
from web.sqli_errors import ErrorFinding, classify, evidence_line, probe_error

pytestmark = pytest.mark.exercise

# Real texts: SQLite from this machine; the others from each database's documentation or source, and the
# SQL Server one as quoted in OWASP WSTG-INPV-05.
SAMPLES = {
    "SQLite": 'sqlite3.OperationalError: unrecognized token: "\'captured\'\' ORDER BY id"',
    "PostgreSQL": 'ERROR:  unterminated quoted string at or near "\'captured"',
    "MySQL": "You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version "
             "for the right syntax to use",
    "Oracle": "ORA-01756: quoted string not properly terminated",
    "SQL Server": "[Microsoft][ODBC SQL Server Driver][SQL Server]Unclosed quotation mark before the character string ''.",
}


@pytest.mark.parametrize("dbms", list(SAMPLES))
def test_classifies_each_database(dbms):
    assert classify(SAMPLES[dbms]) == [dbms]


def test_sqlite_syntax_error_form():
    assert classify('sqlite3.OperationalError: near "\' AND \'": syntax error') == ["SQLite"]
    assert classify('near "x": syntax error') == ["SQLite"]


def test_ordinary_words_are_not_signatures():
    for text in ["Check the syntax of your IBAN", "Payment not found", '{"error": "internal error"}',
                 "The quotation mark in the merchant name was removed", "ORA-0175 is not an error code"]:
        assert classify(text) == []


def test_several_matches_in_signature_order_once_each():
    body = SAMPLES["MySQL"] + "\n" + SAMPLES["SQLite"] + "\n" + SAMPLES["SQLite"]
    assert classify(body) == ["SQLite", "MySQL"]


def test_evidence_line_is_the_matching_line_cut_short():
    body = "Traceback (most recent call last):\n  File \"x.py\", line 1\n" + SAMPLES["SQLite"] + "\n"
    assert evidence_line(body) == SAMPLES["SQLite"]
    assert len(evidence_line("x" * 50 + SAMPLES["MySQL"] * 5, limit=80)) == 80
    assert evidence_line("all good") == ""


def test_a_signature_already_on_the_normal_page_is_not_a_finding():
    # A help page that documents error messages: the quote changes nothing.
    page = "<p>Seeing 'syntax error at or near'? Contact support.</p>"
    assert probe_error(lambda v: (200, page), "q", "help") is None


def test_server_error_without_signature_is_an_anomaly():
    send = lambda v: (500, '{"error": "internal error"}') if v.endswith("'") else (200, "{}")  # noqa: E731
    f = probe_error(send, "status", "captured")
    assert isinstance(f, ErrorFinding)
    assert (f.kind, f.databases, f.status) == ("server-error", (), 500)


def test_quote_handled_is_quiet():
    assert probe_error(lambda v: (200, '{"data": []}'), "status", "captured") is None


def alice_token(base):
    r = requests.post(base + "/api/login", json={"email": "alice@shop-a.example", "password": "alice-pass-1"}, timeout=5)
    return r.json()["token"]


def probe_portal(app):
    with serve(app) as base:
        return probe_error(portal_sender(base, alice_token(base)), "status", "captured")


def test_portal_shows_its_database_error():
    f = probe_portal(make_app())
    assert f is not None and (f.kind, f.databases, f.status) == ("sql-error", ("SQLite",), 500)
    assert f.evidence.startswith("sqlite3.OperationalError: unrecognized token")


def test_portal_with_hidden_errors_is_only_an_anomaly():
    f = probe_portal(make_app({"verbose-errors"}))
    assert f is not None and f.kind == "server-error"


def test_portal_with_the_query_fixed_is_quiet():
    assert probe_portal(make_app({"sqli"})) is None
