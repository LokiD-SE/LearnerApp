"""EXERCISE - A small secret scanner: regex rules, an entropy filter, stop words and a line-level allow.

This is the shape of a Gitleaks rule: a regex finds candidates, the *keywords* make it cheap, a minimum
*entropy* and *stop words* remove the noise, and an allow comment records a known test value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# (rule id, regex, capture group holding the secret, minimum entropy or None, keywords for the cheap pre-check)
RULES = [
    ("sandpay-api-key", re.compile(r"\bsp_(?:live|test)_[A-Za-z0-9]{20,}\b"), 0, None, ("sp_",)),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), 0, None, ("private key",)),
    ("generic-secret",
     re.compile(r"""(?i)\b[\w.-]*(?:secret|token|passw(?:or)?d|api[_-]?key)[\w.-]*\s*[:=]\s*b?["']([^"'\s]{8,})["']"""),
     1, 3.5, ("secret", "token", "passw", "api_key", "api-key", "apikey")),
]
STOPWORDS = ("example", "placeholder", "changeme", "your_", "dummy", "practice", "xxxx")
ALLOW_COMMENT = "scanner:allow"


@dataclass(frozen=True)
class SecretFinding:
    rule_id: str
    path: str
    line: int
    redacted: str
    entropy: float


def shannon_entropy(text: str) -> float:
    """Bits per character: ``-sum(p * log2(p))`` over the characters of ``text``; 0.0 for an empty string."""
    raise NotImplementedError("TODO: count the characters and apply Shannon's formula")


def redact(secret: str) -> str:
    """The first four characters and ``***`` (just ``***`` when the secret has four characters or fewer)."""
    raise NotImplementedError("TODO: keep four characters, hide the rest")


def scan_text(text: str, path: str = "<string>", allow_paths: tuple[str, ...] = ()) -> list[SecretFinding]:
    """Return findings sorted by (line, rule order). The full secret must never be stored in a finding.

    For each line (numbered from 1):

    * a path that starts with any of ``allow_paths`` is skipped entirely (return ``[]``);
    * a line containing ``ALLOW_COMMENT`` is skipped;
    * a rule is tried only if one of its keywords appears in the lowercased line;
    * the secret is ``match.group(group)``; it is dropped if it contains a stop word (case-insensitive) or, when
      the rule has a minimum entropy, if ``shannon_entropy(secret)`` is below it;
    * the same secret on the same line is reported once, by the FIRST rule that finds it (the specific rule
      wins over the generic one);
    * ``SecretFinding.redacted`` is ``redact(secret)`` and ``entropy`` is the entropy rounded to 2 places.
    """
    raise NotImplementedError("TODO: loop over the lines, apply the rules, filter, redact")
