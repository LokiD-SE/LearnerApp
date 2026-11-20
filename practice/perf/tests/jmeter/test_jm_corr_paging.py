"""Runs the learner's JMeter plan (exercises/jmeter/jm_corr_paging.jmx) against the SandPay practice API."""

import xml.etree.ElementTree as ET
from collections import defaultdict
from urllib.parse import parse_qs, urlsplit

import pytest
from load_tools import jmeter_home, practice_file, read_jtl, run_jmeter
from sandpay_target import TargetConfig, serve

pytestmark = [pytest.mark.exercise,
              pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")]

PLAN = practice_file("jmeter/jm_corr_paging.jmx")
THREADS, PAGES = 2, 3


@pytest.fixture(scope="module")
def rows(tmp_path_factory):
    out = tmp_path_factory.mktemp("jm_corr")
    with serve(TargetConfig(latency_ms=1)) as base:
        port = base.rsplit(":", 1)[1]
        jtl = run_jmeter(PLAN, {"port": port, "threads": THREADS, "pages": PAGES,
                                "jmeter.save.saveservice.url": "true"}, out)
    return [r for r in read_jtl(jtl) if r["label"] != "vars after page"]


def cursors(rows):
    """starting_after values per thread, in request order ('' for the first page)."""
    per_thread = defaultdict(list)
    for r in rows:
        if r["label"] == "GET /v1/payments":
            per_thread[r["threadName"]].append(parse_qs(urlsplit(r["URL"]).query, keep_blank_values=True)["starting_after"][0])
    return dict(per_thread)


def test_sign_in_succeeds(rows):
    tokens = [r for r in rows if r["label"] == "POST /auth/token"]
    assert len(tokens) == THREADS and {r["responseCode"] for r in tokens} == {"200"}


def test_every_page_is_authorised(rows):
    pages = [r for r in rows if r["label"] == "GET /v1/payments"]
    assert len(pages) == THREADS * PAGES
    assert {r["responseCode"] for r in pages} == {"200"}, "401 means the bearer token is not extracted and sent"


def test_each_page_uses_the_previous_pages_last_id(rows):
    for thread, values in cursors(rows).items():
        assert values[0] == "", thread
        later = values[1:]
        assert all(v.startswith("pay_") for v in later), f"{thread}: {values} - is the cursor extracted?"
        assert len(set(later)) == len(later), f"{thread} requested the same page twice: {values}"
        assert [int(v[4:]) for v in later] == sorted(int(v[4:]) for v in later)


def test_threads_do_not_share_cursors(rows):
    # Variables are per thread: each merchant pages through its own payments.
    per_thread = [set(v[1:]) for v in cursors(rows).values()]
    assert len(per_thread) == THREADS and not set.intersection(*per_thread)


def test_extractors_have_defaults():
    root = ET.parse(PLAN).getroot()
    defaults = {}
    for el in root.iter("JSONPostProcessor"):
        names = el.findtext("stringProp[@name='JSONPostProcessor.referenceNames']") or ""
        values = el.findtext("stringProp[@name='JSONPostProcessor.defaultValues']") or ""
        defaults.update(zip(names.split(";"), values.split(";")))
    for el in root.iter("BoundaryExtractor"):
        defaults[el.findtext("stringProp[@name='BoundaryExtractor.refname']") or ""] = (
            el.findtext("stringProp[@name='BoundaryExtractor.default']") or "")
    for name in ("token", "after", "has_more"):
        assert defaults.get(name), f"no extractor with a default value sets ${{{name}}}"
