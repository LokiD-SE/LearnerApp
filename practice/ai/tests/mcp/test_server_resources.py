import json

import pytest
from mcp.server_resources import (
    PAYOUTS_TEMPLATE,
    SUBSCRIPTION_ID,
    Prompt,
    demo_server,
    match_template,
)
from mcp.server_tools import INVALID_PARAMS, ProtocolError

pytestmark = pytest.mark.exercise

PAYOUTS_204 = "sandpay://merchants/m_204/payouts"


def error_of(fn, *args):
    with pytest.raises(ProtocolError) as info:
        fn(*args)
    return info.value


# --- match_template -----------------------------------------------------------------------------------------


def test_match_template_extracts_variables():
    assert match_template(PAYOUTS_TEMPLATE, PAYOUTS_204) == {"merchant_id": "m_204"}
    assert match_template("sandpay://docs/{name}", "sandpay://docs/refund-policy") == {"name": "refund-policy"}
    assert match_template("x://{a}/{b}", "x://1/2") == {"a": "1", "b": "2"}


@pytest.mark.parametrize(
    "uri",
    [
        "sandpay://merchants/m_204/payouts/extra",
        "sandpay://merchants//payouts",
        "sandpay://merchants/a/b/payouts",
        "sandpay://merchantsXm_204/payouts",
        "other://merchants/m_204/payouts",
    ],
)
def test_match_template_rejects_near_misses(uri):
    assert match_template(PAYOUTS_TEMPLATE, uri) is None


def test_template_literals_are_not_regex():
    assert match_template("a.b/{x}", "aXb/1") is None
    assert match_template("a.b/{x}", "a.b/1") == {"x": "1"}


# --- resources ----------------------------------------------------------------------------------------------


def test_list_resources_sorted_with_cache_hints():
    result = demo_server().list_resources()
    assert [r["uri"] for r in result["resources"]] == ["sandpay://docs/payout-schedule", "sandpay://docs/refund-policy"]
    assert all(r["mimeType"] == "text/markdown" and r["name"] for r in result["resources"])
    assert result["resultType"] == "complete" and result["cacheScope"] == "public" and result["ttlMs"] > 0


def test_templates_list_names_the_payouts_template():
    result = demo_server().list_templates()
    assert result["resourceTemplates"][0]["uriTemplate"] == PAYOUTS_TEMPLATE
    assert result["resultType"] == "complete" and "ttlMs" in result and "cacheScope" in result


def test_read_doc_is_public():
    result = demo_server().read({"uri": "sandpay://docs/refund-policy"})
    (item,) = result["contents"]
    assert item["uri"] == "sandpay://docs/refund-policy" and item["mimeType"] == "text/markdown"
    assert item["text"].startswith("# Refund policy")
    assert result["cacheScope"] == "public" and result["resultType"] == "complete"


def test_read_payouts_is_private_json():
    result = demo_server().read({"uri": PAYOUTS_204})
    (item,) = result["contents"]
    assert item["mimeType"] == "application/json"
    assert [p["id"] for p in json.loads(item["text"])] == ["po_1039", "po_1031"]
    assert result["cacheScope"] == "private" and result["ttlMs"] == 60_000


@pytest.mark.parametrize(
    "uri",
    [
        "sandpay://docs/missing",
        "sandpay://docs/..%2F..%2Fetc%2Fpasswd",
        "sandpay://docs/Refund-Policy",
        "sandpay://merchants/m_999/payouts",
        "sandpay://merchants/m_204;drop/payouts",
        "file:///etc/passwd",
    ],
)
def test_read_unknown_or_invalid_uri_is_not_found_with_the_uri(uri):
    err = error_of(demo_server().read, {"uri": uri})
    assert err.code == INVALID_PARAMS and err.message == "Resource not found" and err.data == {"uri": uri}


@pytest.mark.parametrize("params", [None, {}, {"uri": 5}])
def test_read_without_a_uri_is_invalid_params(params):
    err = error_of(demo_server().read, params)
    assert err.code == INVALID_PARAMS and err.data is None


# --- prompts ------------------------------------------------------------------------------------------------


def test_prompts_list_hides_server_only_defaults():
    result = demo_server().list_prompts()
    (prompt,) = result["prompts"]
    assert prompt["name"] == "summarise_payouts" and prompt["title"] == "Summarise payouts"
    assert prompt["arguments"][1] == {"name": "tone", "description": "plain or formal", "required": False}
    assert result["resultType"] == "complete" and "ttlMs" in result


def test_get_prompt_renders_one_user_message_with_defaults():
    result = demo_server().get_prompt({"name": "summarise_payouts", "arguments": {"merchant_id": "m_204"}})
    assert result["resultType"] == "complete"
    assert result["messages"] == [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": "Summarise the recent payouts of SandPay merchant m_204 in plain language. "
                "Use only the payouts resource for that merchant.",
            },
        }
    ]


def test_get_prompt_errors():
    server = demo_server()
    assert error_of(server.get_prompt, {"name": "nope"}).message == "Unknown prompt: nope"
    missing = error_of(server.get_prompt, {"name": "summarise_payouts", "arguments": {"tone": "formal"}})
    assert missing.code == INVALID_PARAMS and missing.data == {"missing": ["merchant_id"]}
    assert error_of(server.get_prompt, {"name": "summarise_payouts", "arguments": {"merchant_id": 204}}).code == INVALID_PARAMS
    assert error_of(server.get_prompt, {}).code == INVALID_PARAMS


# --- subscriptions ------------------------------------------------------------------------------------------


def test_listen_acknowledges_only_what_the_server_honours():
    server = demo_server()
    ack = server.listen(7, {
        "toolsListChanged": True,
        "promptsListChanged": True,
        "resourcesListChanged": False,
        "resourceSubscriptions": [PAYOUTS_204, "sandpay://merchants/m_999/payouts"],
    })
    assert ack == {
        "jsonrpc": "2.0",
        "method": "notifications/subscriptions/acknowledged",
        "params": {
            "_meta": {SUBSCRIPTION_ID: 7},
            "notifications": {"promptsListChanged": True, "resourceSubscriptions": [PAYOUTS_204]},
        },
    }
    assert "id" not in ack


def test_listen_drops_an_empty_resource_list():
    ack = demo_server().listen("s1", {"resourceSubscriptions": ["sandpay://docs/missing"]})
    assert ack["params"]["notifications"] == {}


def test_prompt_change_notifies_only_subscribers_that_asked():
    server = demo_server()
    server.listen(1, {"promptsListChanged": True})
    server.listen(2, {"resourceSubscriptions": [PAYOUTS_204]})
    server.listen(3, {"promptsListChanged": True})
    sent = server.add_prompt(Prompt("explain_decline", "Explain a decline code.", "Explain decline {code}."))
    assert [n["params"]["_meta"][SUBSCRIPTION_ID] for n in sent] == [1, 3]
    assert all(n["method"] == "notifications/prompts/list_changed" and "id" not in n for n in sent)
    assert "explain_decline" in [p["name"] for p in server.list_prompts()["prompts"]]


def test_payout_notifies_watchers_of_that_uri_and_read_sees_it():
    server = demo_server()
    server.listen(1, {"resourceSubscriptions": [PAYOUTS_204]})
    server.listen(2, {"promptsListChanged": True})
    sent = server.record_payout("m_204", {"id": "po_1044", "amount_minor": 50000, "currency": "EUR", "status": "paid"})
    assert sent == [{
        "jsonrpc": "2.0",
        "method": "notifications/resources/updated",
        "params": {"_meta": {SUBSCRIPTION_ID: 1}, "uri": PAYOUTS_204},
    }]
    first = json.loads(server.read({"uri": PAYOUTS_204})["contents"][0]["text"])[0]
    assert first["id"] == "po_1044"
    assert server.record_payout("m_311", {"id": "po_2", "amount_minor": 1, "currency": "GBP", "status": "paid"}) == []


def test_cancelled_subscription_gets_nothing():
    server = demo_server()
    server.listen(1, {"promptsListChanged": True})
    server.cancel(1)
    server.cancel(99)  # unknown id: ignored
    assert server.add_prompt(Prompt("p", "d", "t")) == []
