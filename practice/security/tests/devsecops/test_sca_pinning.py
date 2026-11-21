"""Checks exercises/devsecops/sca_pinning.py: pinned, hashed requirements and an intact lockfile."""

import copy

import pytest
import sca_fixture as fx
from devsecops.sca_pinning import Issue, check_lockfile, check_requirements

pytestmark = pytest.mark.exercise


def test_a_pinned_and_hashed_requirements_file_is_clean():
    assert check_requirements(fx.GOOD_REQUIREMENTS) == []


def test_bad_requirements_are_reported_with_the_line_they_start_on():
    assert check_requirements(fx.BAD_REQUIREMENTS) == [
        Issue("line 2", "sandpay-log: no sha256 --hash"),
        Issue("line 2", "sandpay-log: not pinned to an exact version with =="),
        Issue("line 3", "sandpay-crypto: not pinned to an exact version with =="),
        Issue("line 4", "sandpay-idna: no sha256 --hash"),
        Issue("line 4", "sandpay-idna: not pinned to an exact version with =="),
        Issue("line 5", "sandpay-template: no sha256 --hash"),  # md5 does not count, and the hash is on line 6
    ]


@pytest.mark.parametrize("spec", ["pkg>=1.0", "pkg~=1.0", "pkg==1.*", "pkg", "pkg<2", "pkg!=1.0"])
def test_only_an_exact_pin_passes(spec):
    sha = "a" * 64
    issues = check_requirements(f"{spec} --hash=sha256:{sha}\n")
    assert [i.reason for i in issues] == ["pkg: not pinned to an exact version with =="]


def test_a_hash_must_be_sha256_and_64_hex_characters():
    for bad in ("--hash=sha256:abc", "--hash=sha1:" + "a" * 40, "--hash=sha256:" + "A" * 64, ""):
        issues = check_requirements(f"pkg==1.0.0 {bad}\n")
        assert [i.reason for i in issues] == ["pkg: no sha256 --hash"], bad


def test_options_comments_and_blank_lines_are_not_requirements():
    text = "# a comment\n\n--index-url https://pypi.sandpay.example/simple\n-r other.txt\n"
    assert check_requirements(text) == []


def test_continuation_lines_and_trailing_comments():
    sha = "b" * 64
    text = f"pkg==1.0.0 \\\n    --hash=sha256:{sha}  # pinned\n"
    assert check_requirements(text) == []


def test_a_good_lockfile_is_clean():
    assert check_lockfile(fx.GOOD_LOCK) == []


def test_bad_lockfile_findings():
    assert check_lockfile(fx.BAD_LOCK) == [
        Issue("node_modules/a-plain-http", "resolved over http, not https"),
        Issue("node_modules/b-other-host", "resolved from mirror.sandpay.example, not an allowed registry"),
        Issue("node_modules/c-no-integrity", "no integrity hash"),
        Issue("node_modules/d-sha1", "integrity is not sha512"),
        Issue("node_modules/e-git-branch", "git dependency not pinned to a commit"),
        Issue("node_modules/g-no-resolved", "no resolved URL"),
    ]


def test_allowed_hosts_can_include_a_private_mirror():
    issues = check_lockfile(fx.BAD_LOCK, allowed_hosts=("registry.npmjs.org", "mirror.sandpay.example"))
    assert Issue("node_modules/b-other-host", "resolved from mirror.sandpay.example, not an allowed registry") not in issues


def test_a_pinned_git_dependency_needs_no_integrity_and_a_link_is_skipped():
    lock = {"packages": {
        "": {"name": "root"},
        "node_modules/pinned": {"resolved": "git+https://git.sandpay.example/p.git#" + "ab" * 20},
        "node_modules/linked": {"resolved": "tools/local", "link": True},
    }}
    assert check_lockfile(lock) == []


def test_http_from_the_wrong_host_gives_two_issues():
    lock = copy.deepcopy(fx.GOOD_LOCK)
    lock["packages"]["node_modules/sandpay-widgets"]["resolved"] = "http://cdn.sandpay.example/w.tgz"
    reasons = [i.reason for i in check_lockfile(lock)]
    assert reasons == ["resolved from cdn.sandpay.example, not an allowed registry",
                       "resolved over http, not https"]
