"""Checks exercises/devsecops/cicd_audit.py: a line-based audit of GitHub Actions workflow files."""

import pytest
from cicd_fixture import BAD_WORKFLOW, GOOD_WORKFLOW
from devsecops.cicd_audit import audit_workflow

pytestmark = pytest.mark.exercise

SHA = "0123456789abcdef0123456789abcdef01234567"


def line_of(text, fragment):
    for number, line in enumerate(text.splitlines(), 1):
        if fragment in line:
            return number
    raise AssertionError(fragment)


def rules(text):
    return [(f.rule_id, f.line) for f in audit_workflow(text)]


def wf(steps, header="on: push\npermissions:\n  contents: read\n"):
    return f"name: t\n{header}jobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n{steps}"


def test_the_bad_workflow_has_each_flaw_on_its_line():
    assert rules(BAD_WORKFLOW) == [
        ("plaintext-secret", line_of(BAD_WORKFLOW, "SANDPAY_API_TOKEN")),
        ("no-permissions", line_of(BAD_WORKFLOW, "  scan:")),
        ("unpinned-action", line_of(BAD_WORKFLOW, "actions/checkout@v4")),
        ("pwn-request", line_of(BAD_WORKFLOW, "ref: ${{")),
        ("unpinned-action", line_of(BAD_WORKFLOW, "scan-action@main")),
        ("script-injection", line_of(BAD_WORKFLOW, 'echo "Title is ${{')),
    ]


def test_the_good_workflow_is_quiet():
    assert audit_workflow(GOOD_WORKFLOW) == []


def test_findings_are_sorted_and_carry_a_severity_and_a_message():
    found = audit_workflow(BAD_WORKFLOW)
    assert [(f.line, f.rule_id) for f in found] == sorted((f.line, f.rule_id) for f in found)
    assert {f.severity for f in found} == {"high", "medium"}
    assert all(f.message for f in found)


@pytest.mark.parametrize(
    ("uses", "severity"),
    [
        ("actions/checkout@v4", "medium"),
        ("actions/checkout@v4.1.7", "medium"),
        ("actions/checkout@abc1234", "medium"),  # a short SHA is not a full-length SHA
        ("actions/checkout@" + SHA[:39], "medium"),
        ("actions/checkout@main", "high"),
        ("actions/checkout@master", "high"),
        ("actions/checkout", "high"),
        ("docker://alpine:3.20", "medium"),
        ("owner/repo/.github/workflows/ci.yml@v1", "medium"),
    ],
)
def test_actions_that_are_not_pinned_to_a_full_sha_are_reported(uses, severity):
    found = audit_workflow(wf(f"      - uses: {uses}\n"))
    assert [(f.rule_id, f.severity) for f in found] == [("unpinned-action", severity)]


@pytest.mark.parametrize(
    "uses",
    [
        f"actions/checkout@{SHA}",
        f"actions/checkout@{SHA} # v4",
        f"'actions/checkout@{SHA}'",
        "./.github/actions/local-helper",
        "docker://alpine@sha256:" + "ab" * 32,
    ],
)
def test_pinned_and_local_actions_are_quiet(uses):
    assert audit_workflow(wf(f"      - uses: {uses}\n")) == []


def test_commented_out_lines_are_ignored():
    steps = "      # - uses: actions/checkout@v4\n      - run: echo ok\n"
    assert audit_workflow(wf(steps)) == []


def test_missing_permissions_is_reported_on_the_first_job_that_lacks_them():
    text = "on: push\njobs:\n  lint:\n    permissions:\n      contents: read\n    runs-on: x\n  test:\n    runs-on: x\n  deploy:\n    runs-on: x\n"
    assert rules(text) == [("no-permissions", 7)]


@pytest.mark.parametrize("top", ["permissions: read-all", "permissions: {}", "permissions:\n  contents: read"])
def test_a_top_level_permissions_key_is_enough(top):
    assert audit_workflow(f"on: push\n{top}\njobs:\n  a:\n    runs-on: x\n") == []


def test_permissions_on_every_job_is_enough():
    text = "on: push\njobs:\n  a:\n    permissions: read-all\n    runs-on: x\n  b:\n    permissions: {}\n    runs-on: x\n"
    assert audit_workflow(text) == []


def test_write_all_is_reported_where_it_is_and_is_not_also_missing_permissions():
    assert rules("on: push\npermissions: write-all\njobs:\n  a:\n    runs-on: x\n") == [("write-all", 2)]
    job = "on: push\njobs:\n  a:\n    permissions: write-all\n    runs-on: x\n"
    assert rules(job) == [("write-all", 4)]


def test_a_file_without_jobs_has_nothing_to_say_about_permissions():
    assert audit_workflow("name: x\non: push\n") == []


def test_untrusted_text_expanded_into_a_script_is_injection():
    steps = '      - run: |\n          echo "${{ github.event.issue.title }}"\n          echo "${{ github.head_ref }}"\n'
    assert [(f.rule_id, f.line) for f in audit_workflow(wf(steps))] == [("script-injection", 10), ("script-injection", 11)]


def test_a_one_line_run_is_script_text_too():
    found = audit_workflow(wf("      - run: echo ${{ github.event.comment.body }}\n"))
    assert [f.rule_id for f in found] == ["script-injection"]


def test_wrapping_the_expression_does_not_hide_it():
    steps = "      - run: |\n          echo ${{ format('{0}', github.event.pull_request.body) }}\n"
    assert [f.rule_id for f in audit_workflow(wf(steps))] == ["script-injection"]


def test_the_environment_variable_form_is_quiet():
    steps = (
        "      - env:\n          TITLE: ${{ github.event.pull_request.title }}\n"
        '        run: |\n          echo "$TITLE"\n'
    )
    assert audit_workflow(wf(steps)) == []


def test_boolean_functions_and_safe_contexts_are_quiet():
    steps = (
        "      - run: |\n"
        "          echo ${{ contains(github.event.pull_request.title, 'fix') }}\n"
        "          echo ${{ github.sha }} ${{ github.repository }}\n"
    )
    assert audit_workflow(wf(steps)) == []


def test_an_expression_in_with_is_not_script_text():
    steps = f"      - uses: actions/checkout@{SHA}\n        with:\n          ref: ${{{{ github.event.pull_request.title }}}}\n"
    assert audit_workflow(wf(steps)) == []


def test_text_after_a_run_block_is_not_script_text():
    steps = (
        "      - run: |\n          echo hi\n"
        "      - uses: ./local\n        with:\n          title: ${{ github.event.pull_request.title }}\n"
    )
    assert audit_workflow(wf(steps)) == []


CHECKOUT_HEAD = f"      - uses: actions/checkout@{SHA}\n        with:\n          ref: ${{{{ github.event.pull_request.head.sha }}}}\n"


@pytest.mark.parametrize(
    "header",
    [
        "on: pull_request_target\n",
        "on: [push, pull_request_target]\n",
        "on:\n  pull_request_target:\n    types: [opened]\n",
        "on:\n  - pull_request_target\n",
        "on:\n  workflow_run:\n    workflows: [CI]\n",
    ],
)
def test_a_privileged_trigger_that_checks_out_the_head_is_a_pwn_request(header):
    found = audit_workflow(wf(CHECKOUT_HEAD, header=header + "permissions:\n  contents: read\n"))
    assert [f.rule_id for f in found] == ["pwn-request"]


def test_the_plain_pull_request_trigger_may_check_out_the_head():
    assert audit_workflow(wf(CHECKOUT_HEAD, header="on: pull_request\npermissions:\n  contents: read\n")) == []


def test_a_privileged_trigger_without_an_untrusted_checkout_is_quiet():
    steps = f"      - uses: actions/checkout@{SHA}\n"
    assert audit_workflow(wf(steps, header="on: pull_request_target\npermissions:\n  contents: read\n")) == []


def test_workflow_run_checkout_of_its_head_is_reported():
    steps = f"      - uses: actions/checkout@{SHA}\n        with:\n          ref: ${{{{ github.event.workflow_run.head_sha }}}}\n"
    found = audit_workflow(wf(steps, header="on:\n  workflow_run:\n    workflows: [CI]\npermissions:\n  contents: read\n"))
    assert [f.rule_id for f in found] == ["pwn-request"]


def test_literal_credentials_are_reported_without_printing_them():
    secret = "sp_test_Hq7mW2xT9vLc4NdKz8RbY3Ps"
    header = f"on: push\npermissions:\n  contents: read\nenv:\n  SANDPAY_API_TOKEN: {secret}\n  DB_PASSWORD: \"{secret}\" # temporary\n"
    found = audit_workflow(wf("      - run: echo ok\n", header=header))
    assert [(f.rule_id, f.line) for f in found] == [("plaintext-secret", 6), ("plaintext-secret", 7)]
    assert all(secret not in f.message for f in found)
    assert "SANDPAY_API_TOKEN" in found[0].message


@pytest.mark.parametrize(
    "line",
    [
        "NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}",
        "GH_TOKEN: ${{ github.token }}",
        "API_TOKEN: $FROM_SHELL",
        "CACHE_KEY: npm-linux-v1",
        "NODE_VERSION: 24",
        "TOKEN_LIFETIME_NOTE:",
        "api_token: lowercase-names-are-not-env-variables",
        "# DB_PASSWORD: hunter2hunter2",
    ],
)
def test_references_ordinary_variables_and_comments_are_quiet(line):
    header = f"on: push\npermissions:\n  contents: read\nenv:\n  {line}\n"
    assert audit_workflow(wf("      - run: echo ok\n", header=header)) == []
