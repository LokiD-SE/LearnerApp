import posixpath
import urllib.parse

import pytest
from sandpay_vuln import FLAWS, make_app, serve
from web.files_traversal_probe import (
    CONTROL_SUFFIX,
    Finding,
    InconclusiveError,
    portal_sender,
    probe_traversal,
    redact,
    variants,
)

pytestmark = pytest.mark.exercise

TARGET = "internal/keys.txt"
PUBLIC = {"public/terms.txt": "terms of service\n"}
SECRET = {"internal/keys.txt": "KEY=synthetic-secret-value\n"}


def fake_files(extra_decodes: int = 0, backslash: bool = False):
    """A file endpoint over a virtual tree. The HTTP layer decodes the raw query value once (like every server);
    ``extra_decodes`` is how many more times the application decodes it, ``backslash`` whether it treats ``\\``
    as a separator. It climbs out of ``public/`` with ``..`` and ignores ``..`` above the root."""
    tree = {**PUBLIC, **SECRET}

    def send(raw: str) -> tuple[int, str]:
        name = urllib.parse.unquote(raw)
        for _ in range(extra_decodes):
            name = urllib.parse.unquote(name)
        if backslash:
            name = name.replace("\\", "/")
        parts = ["public"]
        for part in name.split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part not in ("", "."):
                parts.append(part)
        key = "/".join(parts)
        return (200, tree[key]) if key in tree else (404, f"file not found: {key}")

    return send


# ---- variants ---------------------------------------------------------------------------------------------------
def test_variants_are_the_documented_encodings_in_order():
    assert variants(TARGET) == [
        ("dot-dot-slash", "../internal/keys.txt"),
        ("deep", "../../../../internal/keys.txt"),
        ("url-encoded", "%2e%2e%2finternal%2fkeys.txt"),
        ("double-encoded", "%252e%252e%252finternal%252fkeys.txt"),
        ("backslash", "..%5cinternal%5ckeys.txt"),
        ("nested-strip", "....//internal/keys.txt"),
        ("absolute", "/internal/keys.txt"),
    ]


def test_variants_keep_every_slash_of_a_deeper_target_encoded_the_same_way():
    by_label = dict(variants("a/b/c.txt"))
    assert by_label["url-encoded"] == "%2e%2e%2fa%2fb%2fc.txt"
    assert by_label["backslash"] == "..%5ca%5cb%5cc.txt"
    assert by_label["nested-strip"] == "....//a/b/c.txt"


@pytest.mark.parametrize("target", ["/internal/keys.txt", "../internal/keys.txt", "internal/../keys.txt"])
def test_variants_reject_a_target_that_already_climbs_or_is_absolute(target):
    with pytest.raises(ValueError):
        variants(target)


def test_redact_keeps_the_size_and_four_characters_not_the_body():
    text = redact("KEY=synthetic-secret-value\n")
    assert "27 bytes" in text and "'KEY='" in text
    assert "synthetic" not in text


# ---- the probe against fakes ----------------------------------------------------------------------------------
def labels(findings):
    return {f.variant for f in findings}


def test_finds_the_encodings_a_single_decode_allows():
    findings = probe_traversal(fake_files(), "terms.txt", TARGET)
    assert labels(findings) == {"dot-dot-slash", "deep", "url-encoded"}
    assert all(isinstance(f, Finding) and f.status == 200 and f.size == len(SECRET[TARGET]) for f in findings)


def test_a_second_decode_and_backslash_separators_add_two_more_variants():
    findings = probe_traversal(fake_files(extra_decodes=1, backslash=True), "terms.txt", TARGET)
    assert labels(findings) == {"dot-dot-slash", "deep", "url-encoded", "double-encoded", "backslash"}


def test_findings_hold_the_raw_value_and_never_the_body():
    for f in probe_traversal(fake_files(), "terms.txt", TARGET):
        assert f.value in dict(variants(TARGET)).values()
        assert f.evidence == redact(SECRET[TARGET])
        assert "secret" not in repr(f)


def test_a_server_that_reads_nothing_outside_gives_no_findings():
    def fixed(raw):
        name = urllib.parse.unquote(raw)
        return (200, PUBLIC["public/" + name]) if "public/" + name in PUBLIC else (404, "file not found")

    assert probe_traversal(fixed, "terms.txt", TARGET) == []


def test_a_catch_all_page_is_not_file_access():
    def catch_all(raw):
        return 200, "<html>welcome to SandPay</html>"

    assert probe_traversal(catch_all, "terms.txt", TARGET) == []


def test_an_echo_page_is_not_file_access():
    # 200 and different from the baseline for every payload - but the control (a name that cannot exist) is a 200 too.
    def echo(raw):
        return 200, f"you asked for {raw}"

    assert probe_traversal(echo, "terms.txt", TARGET) == []


def test_the_control_request_is_the_same_payload_with_the_suffix():
    seen = []
    inner = fake_files()

    def spy(raw):
        seen.append(raw)
        return inner(raw)

    probe_traversal(spy, "terms.txt", TARGET)
    assert "../internal/keys.txt" + CONTROL_SUFFIX in seen
    assert len(seen) <= 2 + 2 * 7


def test_an_unstable_or_failing_baseline_is_inconclusive_not_a_pass():
    calls = iter(range(100))
    with pytest.raises(InconclusiveError):
        probe_traversal(lambda raw: (200, f"page {next(calls)}"), "terms.txt", TARGET)
    with pytest.raises(InconclusiveError):
        probe_traversal(lambda raw: (404, "gone"), "terms.txt", TARGET)
    with pytest.raises(InconclusiveError):
        probe_traversal(lambda raw: (200, ""), "terms.txt", TARGET)


# ---- the practice portal ----------------------------------------------------------------------------------------
PORTAL_TARGET = "internal/settlement-keys.txt"


def probe_portal(app):
    with serve(app) as base:
        return probe_traversal(portal_sender(base), "terms.txt", PORTAL_TARGET)


def test_finds_the_portal_flaw_in_five_encodings():
    findings = probe_portal(make_app())
    # The portal decodes the value again after the server has, so even double encoding works; it accepts
    # backslashes; it does not treat "....//" or a leading "/" as a way out.
    assert labels(findings) == {"dot-dot-slash", "deep", "url-encoded", "double-encoded", "backslash"}


def test_portal_evidence_does_not_contain_the_secret():
    for f in probe_portal(make_app()):
        assert "sk_practice" not in f.evidence and "sk_practice" not in repr(f)
        assert f.evidence.startswith("46 bytes, begins 'SETT'")


def test_quiet_when_path_traversal_is_fixed():
    assert probe_portal(make_app({"path-traversal"})) == []


def test_quiet_when_everything_is_fixed():
    assert probe_portal(make_app(FLAWS)) == []


def test_other_fixes_do_not_hide_it():
    assert probe_portal(make_app({"sqli", "xss-reflected", "open-redirect"}))
