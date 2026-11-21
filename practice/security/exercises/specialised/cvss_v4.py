"""EXERCISE - read a CVSS v4.0 vector strictly and find its macro vector. FIRST's scoring does the rest.

CVSS v4.0 does not use a formula. The metrics are sorted into six equivalence classes (EQ1..EQ6); their digits form a
"macro vector" such as ``"000200"``; FIRST's table gives that macro vector a score, and the vector's distance to the
highest severity vectors of its group moves the score down a little. ``cvss_fixture.interpolate(metrics, macro)`` does
that last step for you (a port of FIRST's published algorithm). You write the two steps before it.

* ``parse_vector(text)`` - ``"CVSS:4.0/AV:N/AC:L/AT:N/PR:H/UI:N/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N"`` becomes a dict of the
  eleven base metrics plus ``"E"`` (Exploit Maturity, default ``"X"`` when absent). The rules (specification
  Table 23): the prefix is exactly ``CVSS:4.0/``; the base metrics appear in the order of ``V4_ORDER``, each once,
  with a value from ``V4_VALUES``; after them an optional ``E`` with a value from ``V4_THREAT_VALUES``. Raise
  ``ValueError`` for a wrong prefix, a repeated metric, an unknown metric name (case matters: ``ui`` is wrong), an
  invalid value, a missing mandatory metric or the wrong order. Metrics beyond ``E`` are not supported here.
* ``macrovector(m)`` - the six digits, from a parsed vector (Requirements CR/IR/AR are Not Defined, i.e. High;
  ``E`` Not Defined counts as Attacked):
      EQ1: 0 if AV:N and PR:N and UI:N;
           1 if (AV:N or PR:N or UI:N) and not AV:P (and not all three);
           2 otherwise (AV:P, or none of the three is N)
      EQ2: 0 if AC:L and AT:N, else 1
      EQ3: 0 if VC:H and VI:H; 1 if not that but any of VC, VI, VA is H; 2 if none is H
      EQ4: 1 if any of SC, SI, SA is H, else 2          (Safety is not a base metric)
      EQ5: E:A or E:X -> 0, E:P -> 1, E:U -> 2
      EQ6: 0 if any of VC, VI, VA is H, else 1          (because CR, IR and AR default to High)
* ``score(vector)`` - parse, find the macro vector, and return ``interpolate(metrics, macro)``.
"""

from __future__ import annotations

from cvss_fixture import V4_ORDER, V4_THREAT_VALUES, V4_VALUES, interpolate

PREFIX = "CVSS:4.0/"


def parse_vector(text: str) -> dict[str, str]:
    raise NotImplementedError("TODO: implement parse_vector")


def macrovector(m: dict[str, str]) -> str:
    raise NotImplementedError("TODO: implement macrovector")


def score(vector: str) -> float:
    raise NotImplementedError("TODO: implement score (use interpolate)")
