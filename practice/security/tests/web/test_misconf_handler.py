import pytest
from web.misconf_handler import ClientError, make_handler

pytestmark = pytest.mark.exercise

SECRET_MESSAGE = "settlement batch failed; db=sqlite:///var/sandpay/portal.db key=sandpay-practice-only-jwt-key"


def failing(message: str = SECRET_MESSAGE) -> RuntimeError:
    try:
        raise RuntimeError(message)
    except RuntimeError as exc:
        return exc


def test_client_errors_pass_their_own_message_through():
    log: list[dict] = []
    handle = make_handler(log)
    assert handle(ClientError(404, "payment not found"), "ref1") == (404, {"error": "payment not found"})
    assert handle(ClientError(403, "forbidden"), "ref2") == (403, {"error": "forbidden"})
    assert log == []


def test_unexpected_errors_get_a_generic_body_with_a_reference():
    status, body = make_handler([])(failing(), "a1b2c3d4")
    assert status == 500
    assert body == {"error": "internal error", "reference": "a1b2c3d4"}


def test_nothing_from_the_exception_reaches_the_client():
    _, body = make_handler([])(failing(), "a1b2c3d4")
    text = str(body)
    for leak in ("settlement", "sqlite", "sandpay-practice", "Traceback", "RuntimeError", "File "):
        assert leak not in text


def test_the_full_detail_is_logged_for_the_team():
    log: list[dict] = []
    make_handler(log)(failing(), "a1b2c3d4")
    assert len(log) == 1
    entry = log[0]
    assert entry["reference"] == "a1b2c3d4"
    assert entry["type"] == "RuntimeError"
    assert entry["message"] == SECRET_MESSAGE
    assert "Traceback (most recent call last)" in entry["traceback"]


def test_a_server_error_marked_as_client_error_is_not_trusted():
    log: list[dict] = []
    status, body = make_handler(log)(ClientError(500, "db password is hunter2hunter2"), "r9")
    assert status == 500 and "hunter2" not in str(body)
    assert log and log[0]["reference"] == "r9"


def test_an_exception_without_a_traceback_still_works():
    log: list[dict] = []
    status, body = make_handler(log)(ValueError("bad"), "r1")  # never raised, so __traceback__ is None
    assert (status, body["reference"]) == (500, "r1")
    assert log[0]["type"] == "ValueError"


def test_one_log_entry_per_unexpected_error():
    log: list[dict] = []
    handle = make_handler(log)
    handle(failing("one"), "r1")
    handle(failing("two"), "r2")
    handle(ClientError(400, "bad input"), "r3")
    assert [e["reference"] for e in log] == ["r1", "r2"]
