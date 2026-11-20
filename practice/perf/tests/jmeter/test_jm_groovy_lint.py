"""jm_groovy_ exercise 2: exercises/jmeter/jm_groovy_lint.py finds costly or stale scripting in a .jmx."""

from pathlib import Path

import pytest
from load_tools import practice_file

from jmeter.jm_groovy_lint import lint

pytestmark = pytest.mark.exercise

FIXTURES = Path(__file__).parent / "fixtures"
LEGACY = FIXTURES / "jm_groovy_legacy.jmx"


def element(tag: str, name: str, script: str = "", language: str = "groovy", cache: str = "true",
            filename: str = "", enabled: str = "true") -> str:
    return f"""<{tag} guiclass="TestBeanGUI" testclass="{tag}" testname="{name}" enabled="{enabled}">
      <stringProp name="scriptLanguage">{language}</stringProp>
      <stringProp name="filename">{filename}</stringProp>
      <stringProp name="cacheKey">{cache}</stringProp>
      <stringProp name="script">{script}</stringProp>
    </{tag}><hashTree/>"""


def plan(tmp_path: Path, *elements: str) -> Path:
    path = tmp_path / "plan.jmx"
    path.write_text('<?xml version="1.0" encoding="UTF-8"?><jmeterTestPlan version="1.2"><hashTree>'
                    '<TestPlan testclass="TestPlan" testname="p"/><hashTree>' + "".join(elements) +
                    "</hashTree></hashTree></jmeterTestPlan>")
    return path


def test_legacy_plan_findings():
    assert lint(LEGACY) == [
        ("beanshell", "legacy signer"),
        ("interpolation", "save payment id"),
        ("not-compilable", "js helper"),
        ("script-function", "POST /v1/payments"),
        ("uncached", "build body"),
    ]


def test_clean_groovy_is_quiet(tmp_path):
    p = plan(tmp_path, element("JSR223PreProcessor", "sign", 'vars.put("k", vars.get("n"))'),
             element("JSR223Assertion", "check", "AssertionResult.setFailure(false)", cache="true"))
    assert lint(p) == []


def test_only_false_turns_the_cache_off(tmp_path):
    # JMeter 5.6.3 caches with "true", an empty key or a legacy unique string; only "false" disables it.
    p = plan(tmp_path, element("JSR223Sampler", "a", "1", cache=""), element("JSR223Sampler", "b", "1", cache="key-1"),
             element("JSR223Sampler", "c", "1", cache="false"))
    assert lint(p) == [("uncached", "c")]


def test_interpolation_only_matters_when_cached(tmp_path):
    p = plan(tmp_path, element("JSR223Sampler", "cached", "x = '${n}'"),
             element("JSR223Sampler", "slow", "x = '${n}'", cache="false"))
    assert lint(p) == [("interpolation", "cached"), ("uncached", "slow")]


def test_script_files_and_disabled_elements_are_skipped(tmp_path):
    p = plan(tmp_path, element("JSR223Sampler", "file", cache="false", filename="lib/sign.groovy"),
             element("BeanShellSampler", "off", "x", enabled="false"))
    assert lint(p) == []


def test_findings_are_unique_and_sorted(tmp_path):
    p = plan(tmp_path, element("JSR223Sampler", "z", "${__javaScript(1)} ${__BeanShell(2)}", language="beanshell"),
             element("BeanShellTimer", "a", "100"))
    assert lint(p) == [("beanshell", "a"), ("interpolation", "z"), ("not-compilable", "z"), ("script-function", "z")]


def test_your_signing_plan_is_clean():
    # Passes once exercise 1 (jm_groovy_sign.jmx) is fixed.
    assert lint(practice_file("jmeter/jm_groovy_sign.jmx")) == []
