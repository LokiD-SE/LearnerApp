"""Checks exercises/web/sess_fixation.py against the loopback sign-in service (support/sess_fixture.py)."""

import pytest
from sess_fixture import make_app, serve
from web.sess_fixation import probe_fixation, probe_url_session, session_id_from

pytestmark = pytest.mark.exercise

ALICE = ("alice@shop-a.example", "alice-pass-1")


def test_fixation_found_when_the_id_survives_sign_in():
    with serve(make_app()) as base:
        r = probe_fixation(base, *ALICE)
    assert r.pre_login_id and r.post_login_id == r.pre_login_id
    assert r.rotated is False
    assert r.old_id_authenticated is True and r.vulnerable is True


def test_no_fixation_once_the_id_is_rotated():
    with serve(make_app({"fixation"})) as base:
        r = probe_fixation(base, *ALICE)
    assert r.pre_login_id and r.post_login_id and r.post_login_id != r.pre_login_id
    assert r.rotated is True
    assert r.old_id_authenticated is False and r.vulnerable is False


def test_fixation_probe_rejects_a_failed_sign_in():
    with serve(make_app()) as base:
        with pytest.raises(RuntimeError):
            probe_fixation(base, "alice@shop-a.example", "wrong-password")


def test_url_session_found():
    with serve(make_app()) as base:
        r = probe_url_session(base, *ALICE)
    assert r.id_in_links is True and r.accepted_from_url is True and r.vulnerable is True


def test_url_session_quiet_when_fixed():
    # Fix both: the url flaw alone, and with fixation also fixed (rotation must not hide the check).
    for fixed in ({"url-session"}, {"url-session", "fixation"}):
        with serve(make_app(fixed)) as base:
            r = probe_url_session(base, *ALICE)
        assert (r.id_in_links, r.accepted_from_url, r.vulnerable) == (False, False, False), fixed


def test_session_id_from_ignores_a_clearing_cookie():
    import requests

    with serve(make_app()) as base:
        sid = requests.post(f"{base}/login", data={"email": ALICE[0], "password": ALICE[1]}).cookies["sid"]
        out = requests.post(f"{base}/logout", cookies={"sid": sid})
        assert session_id_from(out) is None
        assert session_id_from(requests.get(f"{base}/login")) is not None
