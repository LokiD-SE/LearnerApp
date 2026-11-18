import pytest
from prod_cap_fixture import request_meta
from production.cap_server import (
    APPROVAL_KEY,
    RpcError,
    SupportServer,
    args_digest,
    sign_state,
    validate_refund_args,
    verify_state,
)

pytestmark = pytest.mark.exercise

SECRET = b"test-secret"
ELICIT = {"elicitation": {"form": {}}}
ARGS = {"payment_id": "pay_1042", "amount_minor": 2500, "reason": "Item arrived damaged"}
ACCEPT = {APPROVAL_KEY: {"action": "accept", "content": {"approve": True}}}


def call(server, rid, params, caps=ELICIT):
    body = dict(params)
    body["_meta"] = request_meta(caps)
    return server.handle({"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": body})


def refund(server, rid, args=ARGS, caps=ELICIT, **extra):
    return call(server, rid, {"name": "refund_payment", "arguments": args, **extra}, caps)


def text(response):
    return response["result"]["content"][0]["text"]


# --- arguments --------------------------------------------------------------------------------------------------


def test_valid_arguments():
    assert validate_refund_args(ARGS) == []


@pytest.mark.parametrize(
    "args, problems",
    [
        ("pay_1042", ["arguments must be an object"]),
        ({}, ["missing payment_id", "missing amount_minor", "missing reason"]),
        ({**ARGS, "payment_id": "1042"}, ["payment_id must look like pay_1234"]),
        ({**ARGS, "amount_minor": 0}, ["amount_minor must be a whole number of minor units >= 1"]),
        ({**ARGS, "amount_minor": 12.5}, ["amount_minor must be a whole number of minor units >= 1"]),
        ({**ARGS, "amount_minor": True}, ["amount_minor must be a whole number of minor units >= 1"]),
        ({**ARGS, "reason": "no"}, ["reason must be 3 to 200 characters"]),
        ({**ARGS, "reason": "x" * 201}, ["reason must be 3 to 200 characters"]),
        ({**ARGS, "z": 1, "merchant_id": "m_204"}, ["unexpected field merchant_id", "unexpected field z"]),
    ],
)
def test_argument_problems(args, problems):
    assert validate_refund_args(args) == problems


# --- requestState -----------------------------------------------------------------------------------------------


def test_state_round_trip_and_shape():
    state = sign_state(SECRET, {"m": "tools/call:refund_payment", "d": "abc", "n": "n1"})
    body, mac = state.split(".")
    assert "=" not in state and "+" not in state and "/" not in state
    assert len(mac) == 43  # 32 bytes of HMAC-SHA256, base64url without padding
    assert verify_state(SECRET, state) == {"m": "tools/call:refund_payment", "d": "abc", "n": "n1"}


@pytest.mark.parametrize("bad", ["", "not-a-state", "a.b.c", 42, None])
def test_garbage_state_is_rejected(bad):
    with pytest.raises(RpcError) as err:
        verify_state(SECRET, bad)
    assert (err.value.code, err.value.message) == (-32602, "Invalid requestState")


def test_tampered_state_and_wrong_secret_are_rejected():
    state = sign_state(SECRET, {"n": "n1"})
    body, mac = state.split(".")
    forged_body = sign_state(SECRET, {"n": "n9"}).split(".")[0]
    for bad, secret in [(f"{forged_body}.{mac}", SECRET), (state, b"other-secret")]:
        with pytest.raises(RpcError):
            verify_state(secret, bad)


def test_args_digest_ignores_key_order():
    assert args_digest({"a": 1, "b": 2}) == args_digest({"b": 2, "a": 1})
    assert len(args_digest(ARGS)) == 64


# --- envelope and simple tools (given code, checked so the server works end to end) -------------------------------


def test_meta_is_required_and_version_checked():
    server = SupportServer(SECRET)
    missing = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    assert missing["error"]["code"] == -32602
    old = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"_meta": {**request_meta(), "io.modelcontextprotocol/protocolVersion": "2025-11-25"}}})
    assert old["error"]["code"] == -32022
    assert old["error"]["data"] == {"supported": ["2026-07-28"], "requested": "2025-11-25"}


def test_get_payment():
    server = SupportServer(SECRET)
    ok = call(server, 1, {"name": "get_payment", "arguments": {"payment_id": "pay_1043"}})
    assert ok["result"]["structuredContent"]["refunded_minor"] == 2500
    assert ok["result"]["resultType"] == "complete"
    missing = call(server, 2, {"name": "get_payment", "arguments": {"payment_id": "pay_9999"}})
    assert missing["result"]["isError"] is True


# --- the refund flow --------------------------------------------------------------------------------------------


def test_first_call_asks_for_approval_and_refunds_nothing():
    server = SupportServer(SECRET)
    result = refund(server, 1)["result"]
    assert result["resultType"] == "input_required"
    request = result["inputRequests"][APPROVAL_KEY]
    assert request["method"] == "elicitation/create"
    assert request["params"]["mode"] == "form"
    assert request["params"]["message"] == "Refund 25.00 EUR of pay_1042 to the customer? Reason: Item arrived damaged"
    assert request["params"]["requestedSchema"]["required"] == ["approve"]
    assert request["params"]["requestedSchema"]["properties"]["approve"]["type"] == "boolean"
    assert verify_state(SECRET, result["requestState"]) == {"m": "tools/call:refund_payment", "d": args_digest(ARGS), "n": "n1"}
    assert server.refunds == []


def test_accepted_retry_issues_exactly_one_refund():
    server = SupportServer(SECRET)
    state = refund(server, 1)["result"]["requestState"]
    done = refund(server, 2, inputResponses=ACCEPT, requestState=state)["result"]
    expected = {"refund_id": "rf_n1", "payment_id": "pay_1042", "amount_minor": 2500, "currency": "EUR", "status": "refunded"}
    assert done["structuredContent"] == expected and done["isError"] is False
    assert server.refunds == [expected]
    assert server.payments["pay_1042"]["refunded_minor"] == 2500


@pytest.mark.parametrize(
    "answer, action",
    [({"action": "decline"}, "decline"), ({"action": "cancel"}, "cancel"), ({"action": "accept", "content": {"approve": False}}, "accept"), ({"action": "accept", "content": {"approve": "yes"}}, "accept")],
)
def test_anything_but_an_explicit_yes_refunds_nothing(answer, action):
    server = SupportServer(SECRET)
    state = refund(server, 1)["result"]["requestState"]
    result = refund(server, 2, inputResponses={APPROVAL_KEY: answer}, requestState=state)["result"]
    assert result["structuredContent"] == {"status": "not_approved", "payment_id": "pay_1042", "action": action}
    assert result["isError"] is False
    assert server.refunds == []


def test_missing_input_response_is_not_approval():
    server = SupportServer(SECRET)
    state = refund(server, 1)["result"]["requestState"]
    result = refund(server, 2, requestState=state)["result"]
    assert result["structuredContent"]["status"] == "not_approved"
    assert server.refunds == []


def test_a_state_can_be_used_once():
    server = SupportServer(SECRET)
    state = refund(server, 1)["result"]["requestState"]
    refund(server, 2, inputResponses=ACCEPT, requestState=state)
    replay = refund(server, 3, inputResponses=ACCEPT, requestState=state)
    assert replay["error"] == {"code": -32602, "message": "requestState already used"}
    assert len(server.refunds) == 1


def test_state_is_bound_to_the_arguments():
    server = SupportServer(SECRET)
    state = refund(server, 1)["result"]["requestState"]
    swapped = refund(server, 2, args={**ARGS, "amount_minor": 9000}, inputResponses=ACCEPT, requestState=state)
    assert swapped["error"] == {"code": -32602, "message": "requestState does not match this request"}
    assert server.refunds == []


def test_forged_state_is_rejected():
    server = SupportServer(SECRET)
    forged = sign_state(b"attacker", {"m": "tools/call:refund_payment", "d": args_digest(ARGS), "n": "n1"})
    result = refund(server, 1, inputResponses=ACCEPT, requestState=forged)
    assert result["error"] == {"code": -32602, "message": "Invalid requestState"}
    assert server.refunds == []


def test_nonces_count_up():
    server = SupportServer(SECRET)
    states = [refund(server, i)["result"]["requestState"] for i in (1, 2)]
    assert [verify_state(SECRET, s)["n"] for s in states] == ["n1", "n2"]


def test_no_elicitation_capability_means_no_refund():
    server = SupportServer(SECRET)
    result = refund(server, 1, caps={})["result"]
    assert result["resultType"] == "complete" and result["isError"] is True
    assert text({"result": result}) == "refund_payment needs a client that can ask the user to approve (elicitation)."


@pytest.mark.parametrize(
    "args, message",
    [
        ({**ARGS, "payment_id": "pay_9999"}, "No SandPay payment 'pay_9999'."),
        ({**ARGS, "payment_id": "pay_1044", "amount_minor": 100}, "pay_1044 is authorized, not captured - cancel the authorisation instead of refunding."),
        ({**ARGS, "payment_id": "pay_1043", "amount_minor": 2000}, "Refund of 2000 is more than the 1500 left to refund on pay_1043."),
        ({"payment_id": "1042", "amount_minor": 12.5, "reason": "x", "merchant_id": "m_204"}, "Invalid arguments: payment_id must look like pay_1234; amount_minor must be a whole number of minor units >= 1; reason must be 3 to 200 characters; unexpected field merchant_id"),
    ],
)
def test_business_rule_failures_are_tool_errors(args, message):
    server = SupportServer(SECRET)
    response = refund(server, 1, args=args)
    assert response["result"]["isError"] is True
    assert text(response) == message


def test_the_remaining_amount_is_checked_again_on_retry():
    server = SupportServer(SECRET)
    first = refund(server, 1, args={**ARGS, "amount_minor": 10000})["result"]["requestState"]
    second = refund(server, 2, args={**ARGS, "amount_minor": 10000})["result"]["requestState"]
    refund(server, 3, args={**ARGS, "amount_minor": 10000}, inputResponses=ACCEPT, requestState=first)
    late = refund(server, 4, args={**ARGS, "amount_minor": 10000}, inputResponses=ACCEPT, requestState=second)
    assert text(late) == "Refund of 10000 is more than the 2500 left to refund on pay_1042."
    assert len(server.refunds) == 1


def test_unknown_tool_is_a_protocol_error():
    assert call(SupportServer(SECRET), 1, {"name": "delete_merchant", "arguments": {}})["error"]["code"] == -32602
