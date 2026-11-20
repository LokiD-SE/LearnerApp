"""A CSRF probe for one state-changing form (WSTG-SESS-05), with a control, evidence and clean-up.

Exercise - fill in the TODOs; ``tests/web/test_csrf_probe.py`` checks your work. The idea of the probe:

1. **Control.** Submit the form exactly as the application's own page would (every field, including any
   token). If even that fails, the probe proves nothing - the verdict is ``inconclusive``, never "safe".
2. **Forgeries.** Replay the same request as a cross-site page could send it: the victim's cookie rides along
   (the browser adds it), but the attacker cannot read the page, so any token is missing or wrong. The probe
   also sends ``Origin: https://evil.example`` - what a browser would send for a cross-site form POST - so a
   server that checks Origin gets the chance to refuse.
3. **Evidence.** After every request, read the account back (``GET /api/me``) - a 200 status alone does not
   prove the change happened, and a 403 alone does not prove it did not.
4. **Clean-up.** Whenever a request changed the email, put the original back at once with a legitimate
   submission, so the victim account is left as it was found.

The probe sends the ``Cookie`` header itself rather than relying on a cookie jar: once the portal's
``weak-session`` flaw is fixed the cookie is ``Secure``, and HTTP clients will not send a Secure cookie over
plain ``http://`` - a browser would not either, but the probe is testing the CSRF defence, not the transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

ATTACKER_ORIGIN = "https://evil.example"
TOKEN_HINTS = ("csrf", "xsrf", "token", "authenticity")


@dataclass
class Form:
    action: str
    method: str
    fields: dict[str, str]  # every named input, with its value (hidden fields included)


@dataclass
class Attempt:
    name: str  # "control", "no-token", "empty-token", "wrong-token"
    status: int
    changed: bool  # did GET /api/me show the new email afterwards?


@dataclass
class CsrfResult:
    verdict: str  # "vulnerable", "not-vulnerable" or "inconclusive"
    token_fields: list[str]
    attempts: list[Attempt] = field(default_factory=list)
    restored: bool = True  # the original email is back


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[Form] = []
        self._current: Form | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "form":
            self._current = Form(a.get("action", ""), (a.get("method") or "get").upper(), {})
        elif tag in ("input", "textarea", "select") and self._current is not None and a.get("name"):
            if a.get("type", "").lower() in ("submit", "button", "image", "reset"):
                return
            self._current.fields[a["name"]] = a.get("value", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._current is not None:
            self.forms.append(self._current)
            self._current = None


def parse_form(html: str) -> Form:
    """The first ``<form>`` in ``html``: action, upper-case method (default GET) and named fields."""
    parser = _FormParser()
    parser.feed(html)
    parser.close()
    if not parser.forms:
        raise ValueError("no <form> in the page")
    return parser.forms[0]


def token_fields(form: Form) -> list[str]:
    """Names of fields that look like anti-CSRF tokens (name contains csrf, xsrf, token or authenticity).

    TODO: return the sorted names of fields whose lower-case name contains any of TOKEN_HINTS.
    """
    raise NotImplementedError("token_fields")


def forged_bodies(form: Form, changes: dict[str, str]) -> dict[str, dict[str, str]]:
    """The bodies a cross-site attacker could send: the form's fields with ``changes`` applied and the token
    removed, emptied or replaced. Without a token field there is only one forgery, ``no-token``.

    TODO: start from the form's fields with ``changes`` applied. Always return ``no-token`` (token fields
    removed); when the form has token fields, also ``empty-token`` (each set to "") and ``wrong-token`` (each
    set to a made-up value).
    """
    raise NotImplementedError("forged_bodies")


def _me(base_url: str, cookie: str) -> dict:
    r = requests.get(base_url + "/api/me", headers={"Cookie": cookie}, timeout=5)
    r.raise_for_status()
    return r.json()


def _settings_form(base_url: str, cookie: str) -> Form:
    r = requests.get(base_url + "/settings", headers={"Cookie": cookie}, timeout=5)
    r.raise_for_status()
    return parse_form(r.text)


def _submit(base_url: str, form: Form, body: dict[str, str], cookie: str, origin: str | None) -> int:
    headers = {"Cookie": cookie}
    if origin:
        headers["Origin"] = origin
    url = urljoin(base_url + "/settings", form.action)
    r = requests.request(form.method, url, data=body, headers=headers, timeout=5, allow_redirects=False)
    return r.status_code


def _restore(base_url: str, cookie: str, original: str) -> bool:
    form = _settings_form(base_url, cookie)  # a fresh, legitimate page - with its token, if it has one
    _submit(base_url, form, {**form.fields, "email": original}, cookie, origin=base_url)
    return _me(base_url, cookie)["email"] == original


def probe_csrf(base_url: str, cookie: str, new_email: str) -> CsrfResult:
    """Probe ``POST /settings/email`` of the portal at ``base_url`` as the signed-in victim ``cookie``
    (``"sid=..."``). ``new_email`` is the value the forgeries try to set. See the module docstring.

    TODO, in this order (the module docstring says why):
    1. read the original email with ``_me`` and the form with ``_settings_form``;
    2. control - submit every field with the new email (``origin=base_url``); record an Attempt; restore with
       ``_restore`` if it changed; if it did not change (or could not be restored) return ``inconclusive``;
    3. for each body from ``forged_bodies``: submit with ``origin=ATTACKER_ORIGIN``, read back, record an
       Attempt, restore if it changed;
    4. verdict ``vulnerable`` if any forgery changed the email, else ``not-vulnerable``.
    """
    raise NotImplementedError("probe_csrf")
