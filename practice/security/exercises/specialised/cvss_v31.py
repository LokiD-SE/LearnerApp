"""EXERCISE - score a CVSS v3.1 vector by hand, the way FIRST's specification defines it (section 7).

* ``parse_vector(text)`` - ``"CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"`` becomes
  ``{"AV": "N", "AC": "L", "PR": "L", "UI": "N", "S": "U", "C": "H", "I": "N", "A": "N"}``. The prefix must be
  exactly ``CVSS:3.1/``; all eight base metrics must appear, each once, in ANY order (the specification allows a
  non-preferred order); names and values are case sensitive and must be in ``V31_VALUES``. Anything else -
  another version, a missing, repeated or unknown metric, a temporal metric such as ``E:F`` - raises ``ValueError``.
* ``roundup(value)`` - the smallest number with one decimal place that is >= value. Do NOT use ``math.ceil(x * 10) / 10``:
  floating point noise turns 4.000000000001 into 4.1. Follow Appendix A: ``i = round(value * 100000)``; if
  ``i % 10000 == 0`` return ``i / 100000``; otherwise return ``(i // 10000 + 1) / 10``.
* ``base_score(vector)`` - the Base Score. With the weights below:
      ISS = 1 - (1 - C) * (1 - I) * (1 - A)
      Impact = 6.42 * ISS                                   (Scope Unchanged)
             = 7.52 * (ISS - 0.029) - 3.25 * (ISS - 0.02) ** 15     (Scope Changed)
      Exploitability = 8.22 * AV * AC * PR * UI
      if Impact <= 0: 0.0
      Unchanged: roundup(min(Impact + Exploitability, 10))
      Changed:   roundup(min(1.08 * (Impact + Exploitability), 10))
  Weights - AV: N 0.85, A 0.62, L 0.55, P 0.2; AC: L 0.77, H 0.44; UI: N 0.85, R 0.62; C/I/A: H 0.56, L 0.22,
  N 0; PR: N 0.85, L 0.62 (0.68 if Scope is Changed), H 0.27 (0.5 if Scope is Changed).
"""

from __future__ import annotations

from cvss_fixture import V31_ORDER, V31_VALUES  # the eight metric names and their allowed values

PREFIX = "CVSS:3.1/"


def parse_vector(text: str) -> dict[str, str]:
    raise NotImplementedError("TODO: implement parse_vector")


def roundup(value: float) -> float:
    raise NotImplementedError("TODO: implement roundup (Appendix A of the specification)")


def base_score(vector: str) -> float:
    raise NotImplementedError("TODO: implement base_score")
