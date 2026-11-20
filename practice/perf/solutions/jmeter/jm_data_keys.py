"""Proving every payment request carried its own Idempotency-Key - from an XML results file.

A CSV results file has no headers. To check keys, save the run as XML with the request and response headers:
``-Jjmeter.save.saveservice.output_format=xml -Jjmeter.save.saveservice.requestHeaders=true
-Jjmeter.save.saveservice.responseHeaders=true`` (property names from ``bin/jmeter.properties``). Each sample is
an ``<httpSample>`` element: attribute ``lb`` is the label, ``rc`` the response code, ``tn`` the thread name, and
the child elements ``requestHeader`` and ``responseHeader`` hold the raw header blocks.

The practice API answers a repeated key with the first response - same status (201), same payment - plus the
header ``Idempotent-Replayed: true``. JMeter counts that as a success, so only the headers show that the payment
was never created.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


def _header(block: str, name: str) -> str | None:
    for line in block.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip().lower() == name.lower():
            return value.strip()
    return None


def payment_samples(xml_jtl: Path, label: str = "POST /v1/payments") -> list[dict]:
    """One dict per sample with this label, in file order: ``thread`` (``tn``), ``code`` (``rc``), ``key`` (the
    Idempotency-Key request header, or None) and ``replayed`` (True when the response had
    ``Idempotent-Replayed: true``). Raises ValueError when the file has samples but no request headers - the run
    was not saved with ``requestHeaders=true``, so nothing can be proved."""
    root = ET.parse(xml_jtl).getroot()
    out: list[dict] = []
    saw_headers = False
    for sample in root.iter("httpSample"):
        if sample.get("lb") != label:
            continue
        request = sample.findtext("requestHeader")
        response = sample.findtext("responseHeader") or ""
        saw_headers = saw_headers or request is not None
        out.append({
            "thread": sample.get("tn"),
            "code": sample.get("rc"),
            "key": _header(request or "", "Idempotency-Key"),
            "replayed": (_header(response, "Idempotent-Replayed") or "").lower() == "true",
        })
    if out and not saw_headers:
        raise ValueError("no request headers in the results file - save with "
                         "jmeter.save.saveservice.requestHeaders=true")
    return out


def key_report(samples: list[dict]) -> dict:
    """Summarises ``payment_samples``: ``requests``, ``unique_keys``, ``missing_keys`` (requests without a key),
    ``duplicates`` (key -> times used, only keys used more than once), ``replayed`` and ``created`` (201 and not
    replayed - the payments that really exist)."""
    keys = Counter(s["key"] for s in samples if s["key"])
    return {
        "requests": len(samples),
        "unique_keys": len(keys),
        "missing_keys": sum(1 for s in samples if not s["key"]),
        "duplicates": {k: n for k, n in sorted(keys.items()) if n > 1},
        "replayed": sum(1 for s in samples if s["replayed"]),
        "created": sum(1 for s in samples if s["code"] == "201" and not s["replayed"]),
    }
