import pytest
from sandpay_vuln import make_app, serve
from web.idor_matrix import Result, Rule, decide, parse_matrix, report, run_matrix, violations

pytestmark = pytest.mark.exercise

CREDENTIALS = {"alice": ("alice@shop-a.example", "alice-pass-1"), "bob": ("bob@shop-b.example", "bob-pass-2"),
               "ops": ("ops@sandpay.example", "ops-pass-3")}

MATRIX = """
# actor     method  path                     expected
alice       GET     /api/payments/pay_1001   allow    # own payment
alice       GET     /api/payments/pay_2001   deny     # bob's - horizontal
alice       GET     /api/payments/pay_2002   deny
bob         GET     /api/payments/pay_2001   allow
bob         GET     /api/payments/pay_1001   deny
ops         GET     /api/payments/pay_1001   allow    # admin reads any payment
ops         GET     /api/payments/pay_2002   allow
alice       GET     /api/merchants/m_100     allow
alice       GET     /api/merchants/m_200     deny
anonymous   GET     /api/payments/pay_1001   deny
anonymous   GET     /api/me                  deny
"""


def tokens_for(base):
    import requests
    out = {}
    for actor, (email, pw) in CREDENTIALS.items():
        r = requests.post(base + "/api/login", json={"email": email, "password": pw}, timeout=5)
        assert r.status_code == 200, r.text
        out[actor] = r.json()["token"]
    return out


# ---- parse_matrix -----------------------------------------------------------------------------------------
def test_parses_rules_and_skips_comments_and_blanks():
    rules = parse_matrix(MATRIX)
    assert len(rules) == 11
    assert rules[1] == Rule("alice", "GET", "/api/payments/pay_2001", "deny")
    assert parse_matrix("ops head /api/me allow") == [Rule("ops", "HEAD", "/api/me", "allow")]


@pytest.mark.parametrize("text, line", [
    ("alice GET /x allow\nbob GET /y", 2),
    ("# header\n\nalice POST /api/notes deny", 3),
    ("alice GET api/me allow", 1),
    ("alice GET /api/me maybe", 1),
])
def test_rejects_bad_lines_with_their_line_number(text, line):
    with pytest.raises(ValueError, match=f"line {line}"):
        parse_matrix(text)


# ---- decide ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("status, expected", [(200, "allow"), (204, "allow"), (401, "deny"), (403, "deny"),
                                              (404, "deny"), (302, "error"), (405, "error"), (500, "error")])
def test_decide(status, expected):
    assert decide(status) == expected


# ---- against the portal -------------------------------------------------------------------------------------
def test_finds_the_horizontal_violations_on_the_vulnerable_portal():
    with serve(make_app()) as base:
        results = run_matrix(base, parse_matrix(MATRIX), tokens_for(base))
    bad = [(r.rule.actor, r.rule.path, r.status, r.actual) for r in violations(results)]
    assert bad == [("alice", "/api/payments/pay_2001", 200, "allow"),
                   ("alice", "/api/payments/pay_2002", 200, "allow"),
                   ("bob", "/api/payments/pay_1001", 200, "allow")]
    assert report(results).splitlines()[0] == ("VIOLATION alice GET /api/payments/pay_2001 expected deny, "
                                               "got allow (200)")


def test_no_violations_once_idor_is_fixed():
    with serve(make_app({"idor"})) as base:
        results = run_matrix(base, parse_matrix(MATRIX), tokens_for(base))
    assert violations(results) == []
    assert report(results) == "ok: 11 rules match"
    assert [r.status for r in results if r.rule.actor == "anonymous"] == [401, 401]


def test_an_unknown_actor_is_an_error_not_an_anonymous_request():
    with serve(make_app()) as base:
        with pytest.raises(KeyError):
            run_matrix(base, parse_matrix("mallory GET /api/me deny"), tokens_for(base))


def test_redirects_are_not_followed():
    with serve(make_app()) as base:
        results = run_matrix(base, [Rule("anonymous", "GET", "/login?next=/settings", "allow")], {})
    assert results[0].status == 302 and results[0].actual == "error"
    assert violations(results) == results and isinstance(results[0], Result)
