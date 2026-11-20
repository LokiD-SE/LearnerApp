"""Choose exactly the JTL (CSV) columns a run needs, as JMeter properties.

JMeter writes CSV columns in a fixed order, and each column (or pair of columns) is switched on or off by one
``jmeter.save.saveservice.*`` property. Pass the result to JMeter as ``-J`` properties or in
``user.properties``.

Run: .venv/bin/python -m pytest tests/jmeter/test_jm_assert_saveservice.py
"""

from __future__ import annotations

PREFIX = "jmeter.save.saveservice."

# (columns, property) in the order JMeter 5.6.3 writes them. One property can control two columns.
# TODO: complete the list. Get the order from a real run's header with every column switched on (the lesson
# shows one); the property names are in bin/jmeter.properties under "Results file configuration".
COLUMN_GROUPS: list[tuple[tuple[str, ...], str]] = [
    (("timeStamp",), "timestamp_format"),  # special: "none" removes it, otherwise it is the format
    (("elapsed",), "time"),
    # ... label, responseCode, responseMessage, threadName, dataType, success, failureMessage, bytes, sentBytes,
    # grpThreads + allThreads, URL, Filename, Latency, Encoding, SampleCount + ErrorCount, Hostname, IdleTime,
    # Connect
]
KNOWN = {c for cols, _ in COLUMN_GROUPS for c in cols}


def csv_save_properties(keep: set[str], timestamp_format: str = "yyyy/MM/dd HH:mm:ss.SSS") -> dict[str, str]:
    """Properties for a CSV JTL with a header row and exactly the columns in ``keep`` (plus the partner of any
    paired column): ``output_format`` csv, ``print_field_names`` true, and every column property "true" or
    "false". ``timeStamp`` is special: its property is ``timestamp_format`` - the given format when kept,
    ``"none"`` when not. Unknown column names raise ValueError.

    TODO"""
    raise NotImplementedError("csv_save_properties")


def expected_header(keep: set[str]) -> list[str]:
    """The header JMeter will write for ``csv_save_properties(keep)``, in JMeter's order; ValueError for unknown
    columns.

    TODO"""
    raise NotImplementedError("expected_header")


def missing_columns(header: list[str], needed: list[str]) -> list[str]:
    """Columns from ``needed`` that ``header`` lacks, in the order of ``needed``.

    TODO"""
    raise NotImplementedError("missing_columns")
