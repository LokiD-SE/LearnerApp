"""Choose exactly the JTL (CSV) columns a run needs, as JMeter properties - reference solution.

JMeter writes CSV columns in a fixed order, and each column (or pair of columns) is switched on or off by one
``jmeter.save.saveservice.*`` property. The order and the column-to-property map below were read from real
JMeter 5.6.3 runs (the user manual's list in section 12.4 orders the last columns differently). Pass the result
to JMeter as ``-J`` properties, or put it in ``user.properties``.
"""

from __future__ import annotations

PREFIX = "jmeter.save.saveservice."

# (columns, property) in the order JMeter 5.6.3 writes them. One property can control two columns.
COLUMN_GROUPS: list[tuple[tuple[str, ...], str]] = [
    (("timeStamp",), "timestamp_format"),  # special: "none" removes it, otherwise it is the format
    (("elapsed",), "time"),
    (("label",), "label"),
    (("responseCode",), "response_code"),
    (("responseMessage",), "response_message"),
    (("threadName",), "thread_name"),
    (("dataType",), "data_type"),
    (("success",), "successful"),
    (("failureMessage",), "assertion_results_failure_message"),
    (("bytes",), "bytes"),
    (("sentBytes",), "sent_bytes"),
    (("grpThreads", "allThreads"), "thread_counts"),
    (("URL",), "url"),
    (("Filename",), "filename"),
    (("Latency",), "latency"),
    (("Encoding",), "encoding"),
    (("SampleCount", "ErrorCount"), "sample_count"),
    (("Hostname",), "hostname"),
    (("IdleTime",), "idle_time"),
    (("Connect",), "connect_time"),
]
KNOWN = {c for cols, _ in COLUMN_GROUPS for c in cols}


def _check(keep: set[str]) -> None:
    unknown = sorted(set(keep) - KNOWN)
    if unknown:
        raise ValueError(f"unknown JTL columns {unknown}; known: {sorted(KNOWN)}")


def csv_save_properties(keep: set[str], timestamp_format: str = "yyyy/MM/dd HH:mm:ss.SSS") -> dict[str, str]:
    """JMeter properties that write a CSV JTL with a header row and the columns in ``keep`` (plus the partner of
    any paired column) and nothing else. ``timeStamp`` uses ``timestamp_format``; without it the property is
    ``"none"``. Unknown column names raise ValueError."""
    _check(keep)
    props = {PREFIX + "output_format": "csv", PREFIX + "print_field_names": "true"}
    for cols, prop in COLUMN_GROUPS:
        wanted = any(c in keep for c in cols)
        if prop == "timestamp_format":
            props[PREFIX + prop] = timestamp_format if wanted else "none"
        else:
            props[PREFIX + prop] = "true" if wanted else "false"
    return props


def expected_header(keep: set[str]) -> list[str]:
    """The header row JMeter will write for ``csv_save_properties(keep)``, in JMeter's fixed column order."""
    _check(keep)
    return [c for cols, _ in COLUMN_GROUPS if any(x in keep for x in cols) for c in cols]


def missing_columns(header: list[str], needed: list[str]) -> list[str]:
    """Columns from ``needed`` that ``header`` lacks, in the order of ``needed``."""
    return [c for c in needed if c not in header]
