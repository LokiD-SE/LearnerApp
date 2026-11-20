"""Lint the scripting in a JMeter plan - the JSR223 advice of the JMeter manual as code (jm_groovy_ exercise 2).

Rules, each reported as ``(rule, element testname)``:

- ``beanshell``: a BeanShell element (BeanShellSampler, BeanShellPreProcessor, ...). Best Practices 16.9:
  "Since JMeter 3.1, we advise switching from BeanShell to JSR223 Test Elements".
- ``not-compilable``: a JSR223 element whose language is not ``groovy``; only a Compilable engine can be
  compiled and cached ("Groovy is one of these, java, beanshell and javascript are not").
- ``uncached``: a JSR223 element with an inline script and ``cacheKey`` ``false`` - compiled on every run.
  (A script FILE is compiled and cached anyway, so it is not reported.)
- ``interpolation``: a cached JSR223 inline script that contains ``${`` - "caching would take only first value
  of ${varName}". Use ``vars.get("varName")`` or Parameters.
- ``script-function``: ``${__BeanShell(`` or ``${__javaScript(`` in any property of an element - interpreted on
  every call; ``${__groovy(`` or a cached JSR223 element is the advised replacement.

Disabled elements (``enabled="false"``) are skipped.
"""

from __future__ import annotations

from pathlib import Path


def lint(plan: Path | str) -> list[tuple[str, str]]:
    """Return the sorted, de-duplicated findings of ``plan`` as ``(rule, testname)`` tuples.

    TODO:
    - parse the .jmx with xml.etree.ElementTree and walk every element that has a ``testname`` attribute;
    - skip disabled elements;
    - read the JSR223 settings from the stringProps ``scriptLanguage``, ``filename``, ``cacheKey`` and ``script``
      (only ``cacheKey`` ``false`` turns caching off);
    - search every stringProp of an element for the slow script functions.
    """
    raise NotImplementedError("TODO: implement lint()")
