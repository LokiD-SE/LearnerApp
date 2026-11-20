"""JMeter's Regular Expression Extractor, emulated in Python - reference solution.

The rules come from the JMeter Component Reference, "Regular Expression Extractor" (JMeter 5.6.3), and were
checked against a real JMeter 5.6.3 run with a Debug Sampler (lesson jmeter-correlation-and-extractors):

- The template turns one match into a string: ``$1$`` is group 1, ``$2$`` group 2, ``$0$`` the whole match;
  any other text is copied as it is.
- Match number N > 0: use the N-th match. 0: a random match. Negative: every match (for a ForEach Controller).
- Non-negative and a match found: ``ref`` = the template value, ``ref_gN`` = group N (0 = whole match) and
  ``ref_g`` = the number of groups (excluding 0).
- Non-negative and no match: ``ref`` = the default (left unchanged when there is no default), and ``ref_g0``,
  ``ref_g1`` ... and ``ref_g`` are removed.
- Negative: ``ref_matchNr`` = the number of matches (could be 0), ``ref_n`` = the template for match n,
  ``ref_n_gm`` = group m of match n, ``ref_n_g`` = the number of groups (seen in the real run), and ``ref`` is
  always set to the default.

JMeter uses Java regular expressions ("Perl-type"); Python's ``re`` agrees on everything these exercises use.
"""

from __future__ import annotations

import random
import re

_TEMPLATE_PART = re.compile(r"\$(\d+)\$")


def render_template(template: str, match: re.Match) -> str:
    """Replaces every ``$N$`` in the template with group N of the match; other text is kept."""
    return _TEMPLATE_PART.sub(lambda m: match.group(int(m.group(1))) or "", template)


def extract(
    variables: dict[str, str],
    text: str,
    ref: str,
    regex: str,
    template: str = "$1$",
    match_no: int = 1,
    default: str | None = None,
    rng: random.Random | None = None,
) -> dict[str, str]:
    """Returns a NEW variables dict after applying one extractor to ``text`` (the input is not changed)."""
    out = dict(variables)
    pattern = re.compile(regex)
    matches = list(pattern.finditer(text))
    groups = pattern.groups

    if match_no < 0:
        out[f"{ref}_matchNr"] = str(len(matches))
        for n, m in enumerate(matches, start=1):
            out[f"{ref}_{n}"] = render_template(template, m)
            out[f"{ref}_{n}_g"] = str(groups)
            for g in range(groups + 1):
                out[f"{ref}_{n}_g{g}"] = m.group(g) or ""
        if default is not None:
            out[ref] = default
        return out

    if match_no == 0:
        chosen = (rng or random.Random()).choice(matches) if matches else None
    else:
        chosen = matches[match_no - 1] if match_no <= len(matches) else None

    if chosen is None:
        if default is not None:
            out[ref] = default
        for name in [k for k in out if k == f"{ref}_g" or re.fullmatch(re.escape(ref) + r"_g\d+", k)]:
            del out[name]
        return out

    out[ref] = render_template(template, chosen)
    out[f"{ref}_g"] = str(groups)
    for g in range(groups + 1):
        out[f"{ref}_g{g}"] = chosen.group(g) or ""
    return out
