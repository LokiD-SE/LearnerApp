"""Checks exercises/analysis/fe_har.py on hand-made HAR entries and on two real HAR 1.2 recordings (Chrome through
Playwright, local checkout page, 21 November 2026) in support/fe_data/har_slow.json and har_fixed.json."""

import pytest
from fe_fixture import load_exercise, load_json

pytestmark = pytest.mark.exercise

har = load_exercise("analysis/fe_har.py")


def entry(url="http://h/x.js", mime="application/javascript", started="2026-01-01T00:00:00.100Z", **kw):
    response = {"status": 200, "content": {"size": kw.pop("content", 500), "mimeType": mime}, "bodySize": kw.pop("body", 400)}
    if "transfer" in kw:
        response["_transferSize"] = kw.pop("transfer")
    return {
        "startedDateTime": started,
        "time": 0,
        "request": {"method": "GET", "url": url},
        "response": response,
        "timings": kw.pop("timings", {"send": 0, "wait": 10, "receive": 5}),
    }


def doc(*entries, page="2026-01-01T00:00:00.000Z"):
    return {"log": {"pages": [{"startedDateTime": page}], "entries": list(entries)}}


def test_phases_turn_minus_one_and_missing_into_zero():
    timings = {"dns": -1, "connect": 4, "ssl": -1, "send": 0.5, "wait": 20, "receive": 3}
    result = har.phases(entry(timings=timings))
    assert result == {"blocked": 0.0, "dns": 0.0, "connect": 4.0, "ssl": 0.0, "send": 0.5, "wait": 20.0, "receive": 3.0}


def test_total_time_is_the_sum_of_the_phases():
    assert har.total_time(entry(timings={"blocked": 2, "dns": -1, "send": 1, "wait": 10, "receive": 4})) == pytest.approx(17)


def test_size_prefers_the_transfer_size_then_the_body_size_then_the_content_size():
    assert har.size(entry(transfer=900, body=400, content=500)) == 900
    assert har.size(entry(body=400, content=500)) == 400
    assert har.size(entry(transfer=-1, body=-1, content=500)) == 500
    assert har.size(entry(body=0, content=500)) == 0  # a cached response has a body size of 0


def test_kind_is_read_from_the_mime_type_without_parameters():
    cases = {
        "text/html; charset=utf-8": "html",
        "text/css": "css",
        "application/javascript": "js",
        "text/javascript": "js",
        "image/svg+xml": "image",
        "image/png": "image",
        "application/json": "api",
        "font/woff2": "other",
    }
    assert {m: har.kind(entry(mime=m)) for m in cases} == cases


def test_summarise_counts_requests_bytes_and_kinds_and_names_the_slowest_path():
    d = doc(
        entry("http://h/", "text/html", transfer=1000, timings={"wait": 5, "receive": 1}),
        entry("http://h/a.js", transfer=3000, timings={"wait": 50, "receive": 10}),
        entry("http://h/b.js", transfer=2000, timings={"wait": 20, "receive": 5}),
    )
    s = har.summarise(d)
    assert s["requests"] == 3
    assert s["bytes"] == 6000
    assert s["by_kind"] == {"html": {"requests": 1, "bytes": 1000}, "js": {"requests": 2, "bytes": 5000}}
    assert s["slowest"] == "/a.js"


def test_waterfall_starts_from_the_page_and_is_sorted():
    d = doc(
        entry("http://h/late.js", started="2026-01-01T00:00:00.250Z", timings={"wait": 40, "receive": 10}),
        entry("http://h/", "text/html", started="2026-01-01T00:00:00.010Z", timings={"wait": 2, "receive": 1}),
    )
    assert har.waterfall(d) == [
        {"path": "/", "start": 10.0, "end": 13.0},
        {"path": "/late.js", "start": 250.0, "end": 300.0},
    ]


def test_check_budget_lists_only_the_limits_that_are_exceeded_and_a_limit_equal_to_the_value_passes():
    s = {"requests": 7, "bytes": 350000, "by_kind": {"js": {"requests": 3, "bytes": 300000}}}
    assert har.check_budget(s, {"requests": 7, "bytes": 400000}) == []
    assert har.check_budget(s, {"requests": 6, "js_bytes": 250000, "image_bytes": 0, "bytes": 400000}) == [
        "js_bytes: 300000 > 250000",
        "requests: 7 > 6",
    ]


def test_the_real_recordings_show_the_late_hero_and_the_extra_requests_of_the_slow_page():
    slow, fixed = load_json("har_slow.json"), load_json("har_fixed.json")
    s, f = har.summarise(slow), har.summarise(fixed)
    assert s["requests"] == 7 and f["requests"] == 5
    assert s["slowest"] == f["slowest"] == "/static/hero.svg"
    assert s["by_kind"]["js"]["bytes"] > f["by_kind"]["js"]["bytes"]
    hero = {w["path"]: w for w in har.waterfall(slow)}["/static/hero.svg"]
    hero_fixed = {w["path"]: w for w in har.waterfall(fixed)}["/static/hero.svg"]
    # the slow page discovers the image only after its script ran; the fixed page asks for it at once
    assert hero["start"] - hero_fixed["start"] > 200
    assert hero["end"] > hero_fixed["end"]


def test_a_budget_built_from_the_fixed_page_catches_the_slow_page():
    s = har.summarise(load_json("har_slow.json"))
    f = har.summarise(load_json("har_fixed.json"))
    budget = {"requests": f["requests"], "js_bytes": f["by_kind"]["js"]["bytes"]}
    assert har.check_budget(f, budget) == []
    assert len(har.check_budget(s, budget)) == 2


def test_total_time_matches_the_time_field_of_the_real_entries():
    for name in ("har_slow.json", "har_fixed.json"):
        for e in load_json(name)["log"]["entries"]:
            assert har.total_time(e) == pytest.approx(e["time"], abs=0.01)
