import pytest
from mcp.multi_aggregator import ToolCatalog, namespaced

pytestmark = pytest.mark.exercise

SCHEMA = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}


def tool(name, description="d"):
    return {"name": name, "description": description, "inputSchema": SCHEMA}


def two_servers(mode="always"):
    cat = ToolCatalog(mode=mode)
    cat.add_server("ledger", [tool("search", "Search ledger entries."), tool("get_payout", "One payout.")])
    cat.add_server("support", [tool("search", "Search support tickets."), tool("create_ticket", "Open a ticket.")])
    return cat


def test_namespaced_joins_with_double_underscore():
    assert namespaced("ledger", "search") == "ledger__search"
    assert namespaced("kb-2", "admin.tools.list") == "kb-2__admin.tools.list"


@pytest.mark.parametrize("server_id", ["", "Ledger", "led_ger", "-ledger", "a" * 33, "led ger"])
def test_namespaced_rejects_bad_server_ids(server_id):
    with pytest.raises(ValueError):
        namespaced(server_id, "search")


def test_namespaced_rejects_names_over_128_characters():
    assert len(namespaced("ledger", "x" * 120)) == 128
    with pytest.raises(ValueError, match="128"):
        namespaced("ledger", "x" * 121)


def test_namespaced_rejects_bad_characters_in_the_tool_name():
    with pytest.raises(ValueError):
        namespaced("ledger", "search tickets")


def test_always_mode_prefixes_every_tool_in_a_deterministic_order():
    names = [t["name"] for t in two_servers().exposed()]
    assert names == ["ledger__search", "ledger__get_payout", "support__search", "support__create_ticket"]


def test_exposed_keeps_schema_and_tags_the_description_with_the_server():
    first = two_servers().exposed()[0]
    assert first["inputSchema"] == SCHEMA
    assert first["description"] == "[ledger] Search ledger entries."


def test_resolve_maps_back_to_server_and_original_name():
    cat = two_servers()
    assert cat.resolve("support__search") == ("support", "search")
    assert cat.resolve("ledger__get_payout") == ("ledger", "get_payout")
    with pytest.raises(KeyError):
        cat.resolve("search")


def test_collision_mode_prefixes_only_colliding_names():
    names = [t["name"] for t in two_servers("collision").exposed()]
    assert names == ["ledger__search", "get_payout", "support__search", "create_ticket"]


def test_collision_mode_renames_an_existing_tool_when_a_new_server_collides():
    cat = ToolCatalog(mode="collision")
    cat.add_server("ledger", [tool("search")])
    assert [t["name"] for t in cat.exposed()] == ["search"]
    cat.add_server("support", [tool("search")])
    assert [t["name"] for t in cat.exposed()] == ["ledger__search", "support__search"]
    with pytest.raises(KeyError):
        cat.resolve("search")


def test_bad_and_duplicate_tools_are_skipped_with_warnings_not_errors():
    cat = ToolCatalog()
    accepted = cat.add_server("ledger", [tool("search"), tool("search"), tool("bad name"), tool("get_payout")])
    assert accepted == 2
    assert [t["name"] for t in cat.exposed()] == ["ledger__search", "ledger__get_payout"]
    assert len(cat.warnings) == 2
    assert any("duplicate" in w and "search" in w for w in cat.warnings)
    assert any("bad name" in w for w in cat.warnings)


def test_duplicate_server_id_is_a_configuration_error():
    cat = ToolCatalog()
    cat.add_server("ledger", [tool("search")])
    with pytest.raises(ValueError):
        cat.add_server("ledger", [tool("other")])


def test_remove_server_drops_its_tools():
    cat = two_servers()
    cat.remove_server("support")
    assert [t["name"] for t in cat.exposed()] == ["ledger__search", "ledger__get_payout"]
    with pytest.raises(KeyError):
        cat.resolve("support__search")


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        ToolCatalog(mode="sometimes")
