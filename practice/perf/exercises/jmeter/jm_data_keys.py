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


def payment_samples(xml_jtl: Path, label: str = "POST /v1/payments") -> list[dict]:
    """One dict per sample with this label, in file order: ``thread`` (``tn``), ``code`` (``rc``), ``key`` (the
    Idempotency-Key request header, or None) and ``replayed`` (True when the response had
    ``Idempotent-Replayed: true``). Raises ValueError when the file has samples but no request headers - the run
    was not saved with ``requestHeaders=true``, so nothing can be proved."""
    raise NotImplementedError("TODO: payment_samples - see the docstring and the lesson")


def key_report(samples: list[dict]) -> dict:
    """Summarises ``payment_samples``: ``requests``, ``unique_keys``, ``missing_keys`` (requests without a key),
    ``duplicates`` (key -> times used, only keys used more than once), ``replayed`` and ``created`` (201 and not
    replayed - the payments that really exist)."""
    raise NotImplementedError("TODO: key_report - see the docstring and the lesson")
