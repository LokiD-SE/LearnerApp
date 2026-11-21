"""Checks exercises/devsecops/sca_inventory.py: two SBOM formats, one inventory, and the dependency graph."""

import copy

import pytest
import sca_fixture as fx
from devsecops.sca_inventory import (
    Component,
    minimum_gaps,
    parse_cyclonedx,
    parse_spdx,
    split_direct_transitive,
    transitive_closure,
)

pytestmark = pytest.mark.exercise


def test_cyclonedx_lists_every_component_including_nested_ones():
    names = [c.name for c in parse_cyclonedx(fx.CYCLONEDX_BOM)]
    assert names == sorted(names)
    assert "sandpay-widgets-core" in names  # nested inside sandpay-widgets
    assert len(names) == 8
    assert "sandpay-checkout" not in names  # metadata.component is the application, not a dependency


def test_cyclonedx_fields():
    json = next(c for c in parse_cyclonedx(fx.CYCLONEDX_BOM) if c.name == "sandpay-json")
    assert json == Component("sandpay-json", "1.4.0", "pkg:pypi/sandpay-json@1.4.0", "SandPay Open Source")


def test_cyclonedx_missing_fields_are_empty_strings():
    by_name = {c.name: c for c in parse_cyclonedx(fx.CYCLONEDX_BOM)}
    assert by_name["sandpay-idna"].supplier == ""
    assert by_name["sandpay-template"].purl == ""


def test_cyclonedx_rejects_another_format():
    with pytest.raises(ValueError):
        parse_cyclonedx(fx.SPDX_DOC)


def test_spdx_skips_the_described_package_and_reads_the_purl():
    found = parse_spdx(fx.SPDX_DOC)
    assert "sandpay-checkout" not in [c.name for c in found]
    http = next(c for c in found if c.name == "sandpay-http")
    assert http == Component("sandpay-http", "2.3.1", "pkg:pypi/sandpay-http@2.3.1", "SandPay Open Source")


def test_spdx_noassertion_supplier_is_empty():
    by_name = {c.name: c for c in parse_spdx(fx.SPDX_DOC)}
    assert by_name["sandpay-idna"].supplier == ""
    assert by_name["sandpay-template"].purl == ""


def test_spdx_person_prefix_and_document_describes():
    doc = copy.deepcopy(fx.SPDX_DOC)
    doc["relationships"] = [r for r in doc["relationships"] if r["relationshipType"] != "DESCRIBES"]
    doc["documentDescribes"] = ["SPDXRef-Package-sandpay-checkout"]
    doc["packages"][1]["supplier"] = "Person: Dana Tester (dana@sandpay.example)"
    found = parse_spdx(doc)
    assert "sandpay-checkout" not in [c.name for c in found]
    assert next(c for c in found if c.name == "sandpay-http").supplier == "Dana Tester (dana@sandpay.example)"


def test_spdx_rejects_another_format():
    with pytest.raises(ValueError):
        parse_spdx(fx.CYCLONEDX_BOM)


def test_both_formats_describe_the_same_inventory():
    assert parse_cyclonedx(fx.CYCLONEDX_BOM) == parse_spdx(fx.SPDX_DOC)


def test_transitive_closure_follows_edges_and_excludes_the_start():
    graph = {"a": ["b", "c"], "b": ["d"], "c": [], "d": [], "x": ["a"]}
    assert transitive_closure(graph, "a") == {"b", "c", "d"}
    assert transitive_closure(graph, "d") == set()
    assert transitive_closure(graph, "unknown") == set()


def test_transitive_closure_survives_a_cycle():
    graph = {"a": ["b"], "b": ["c"], "c": ["a", "b"]}
    assert transitive_closure(graph, "a") == {"b", "c"}


def test_split_direct_transitive():
    direct, transitive = split_direct_transitive(fx.CYCLONEDX_BOM)
    assert direct == ["pkg:npm/sandpay-widgets@3.2.0", "pkg:pypi/sandpay-crypto@0.9.2",
                      "pkg:pypi/sandpay-http@2.3.1", "pkg:pypi/sandpay-log@3.1.0"]
    assert transitive == ["pkg:npm/sandpay-widgets-core@1.0.3", "pkg:pypi/sandpay-idna@2.9.0",
                          "pkg:pypi/sandpay-json@1.4.0", "sandpay-template@5.0.1"]


def test_a_direct_dependency_that_is_also_needed_by_another_stays_direct():
    doc = copy.deepcopy(fx.CYCLONEDX_BOM)
    root = doc["metadata"]["component"]["bom-ref"]
    next(d for d in doc["dependencies"] if d["ref"] == root)["dependsOn"].append("pkg:pypi/sandpay-json@1.4.0")
    direct, transitive = split_direct_transitive(doc)
    assert "pkg:pypi/sandpay-json@1.4.0" in direct
    assert "pkg:pypi/sandpay-json@1.4.0" not in transitive


def test_minimum_gaps_reports_what_is_missing():
    assert minimum_gaps(parse_cyclonedx(fx.CYCLONEDX_BOM)) == {
        "sandpay-idna@2.9.0": ["supplier"],
        "sandpay-template@5.0.1": ["purl"],
    }


def test_minimum_gaps_orders_fields_and_handles_a_missing_version():
    items = [Component("bare", "", "", ""), Component("ok", "1.0.0", "pkg:pypi/ok@1.0.0", "Acme")]
    assert minimum_gaps(items) == {"bare": ["supplier", "version", "purl"]}
    assert minimum_gaps([]) == {}
