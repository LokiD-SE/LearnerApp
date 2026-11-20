"""Exercise - give every JMeter server its own slice of the test data.

From the JMeter user manual, 13. Remote Testing, Step 0: "If the test uses any data files, note that these are not
sent across by the client so make sure that these are available in the appropriate directory on each server. ...
(e.g. if each server must use unique ids, divide these between the data files)". And from the CSV Data Set Config
reference: "the CSV file must be stored on the server host system in the correct relative directory to where the
JMeter server is started."

Every server runs the same plan, so a plan that reads ``merchants.csv`` reads the ``merchants.csv`` in EACH
server's directory. Copy one file to every server and every row is used once per server; split it, and each
server signs in its own merchants.
"""

from __future__ import annotations

from pathlib import Path


def split_rows(rows: list[str], servers: int) -> list[list[str]]:
    """Split data rows (no header) into ``servers`` contiguous, non-overlapping slices in their original order,
    whose sizes differ by at most one - the first ``len(rows) % servers`` slices get the extra row.
    Example: 5 rows, 2 servers -> [rows[0:3], rows[3:5]].
    Raises ValueError if ``servers`` < 1 or there are fewer rows than servers (a server with no data would
    either send ``<EOF>`` or stop at once)."""
    raise NotImplementedError("TODO: split_rows")


def write_server_files(source: Path, server_dirs: list[Path], name: str = "merchants.csv") -> list[Path]:
    """Read ``source`` (a CSV whose first line is a header), split its data rows with ``split_rows`` and write
    ``<server_dir>/<name>`` for each server - every file starts with the same header line, so a CSV Data Set
    Config with empty Variable Names works unchanged on every server. Lines end with ``\\n``; blank lines in the
    source are ignored. Returns the paths written, in ``server_dirs`` order."""
    raise NotImplementedError("TODO: write_server_files")


def rows_needed_per_server(threads_per_server: int, loops: int) -> int:
    """Rows each server's file needs so that, with a shared CSV Data Set Config ("All threads") and recycle off,
    no server reaches end of file: one row per thread per iteration on that server."""
    raise NotImplementedError("TODO: rows_needed_per_server")
