"""SOLUTION - A small secret scanner: regex rules, an entropy filter, stop words and a line-level allow."""

from __future__ import annotations

import math
import re
from collections import Counter
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
    if not text:
        return 0.0
    counts = Counter(text)
    size = len(text)
    return -sum(n / size * math.log2(n / size) for n in counts.values()) + 0.0  # + 0.0 turns -0.0 into 0.0


def redact(secret: str) -> str:
    """The first four characters and ``***`` - enough to find the secret, not to use it."""
    return secret[:4] + "***" if len(secret) > 4 else "***"


def scan_text(text: str, path: str = "<string>", allow_paths: tuple[str, ...] = ()) -> list[SecretFinding]:
    """Return findings sorted by (line, rule order); the full secret is never stored in a finding."""
    if any(path.startswith(prefix) for prefix in allow_paths):
        return []
    findings = []
    for number, line in enumerate(text.splitlines(), start=1):
        if ALLOW_COMMENT in line:
            continue
        lowered = line.lower()
        reported = set()
        for rule_id, regex, group, min_entropy, keywords in RULES:
            if not any(word in lowered for word in keywords):
                continue
            for match in regex.finditer(line):
                secret = match.group(group)
                if secret in reported:
                    continue
                if any(word in secret.lower() for word in STOPWORDS):
                    continue
                entropy = shannon_entropy(secret)
                if min_entropy is not None and entropy < min_entropy:
                    continue
                reported.add(secret)
                findings.append(SecretFinding(rule_id, path, number, redact(secret), round(entropy, 2)))
    return findings
