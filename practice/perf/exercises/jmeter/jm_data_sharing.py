"""A model of which CSV rows a JMeter CSV Data Set Config hands out - so you can predict a run before you make it.

Rules, from the JMeter component reference (CSV Data Set Config), as of JMeter 5.6.3:

- "Lines are read at the start of each test iteration." One read per iteration per thread.
- Sharing mode "All threads - (the default) the file is shared between all the threads": one file pointer for
  the whole test, so N threads x M iterations read N*M lines in total, in an order that "depends on the order
  in which they execute". With one thread group, "Current thread group" behaves the same.
- "Current thread - each file is opened separately for each thread": every thread reads from line 1.
- "When the end of file (EOF) is reached, and the recycle option is true, reading starts again with the first
  line of the file."
- "If the recycle option is false, and stopThread is false, then all the variables are set to <EOF> when the
  end of file is reached."
- "If the Recycle option is false, and Stop Thread is true, then reaching EOF will cause the thread to be
  stopped." (The iteration that hits EOF sends nothing; checked against real runs.)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

EOF_VALUE = "<EOF>"
MODES = ("all", "group", "thread")


@dataclass(frozen=True)
class Reads:
    """What a run reads. ``per_thread`` maps thread number (1-based) to the values it used, in order - only for
    ``thread`` mode, because in a shared file the order depends on scheduling. ``values`` counts every value
    used (including ``<EOF>``), and ``samples`` is how many iterations actually ran."""

    per_thread: dict[int, list[str]] | None
    values: Counter
    samples: int


def plan_reads(rows: list[str], threads: int, iterations: int, share: str = "all", recycle: bool = True,
               stop_thread: bool = False) -> Reads:
    """Predicts the rows one thread group reads. ``rows`` are the data lines (no header); ``share`` is ``all``,
    ``group`` or ``thread``. Raises ValueError for an unknown mode, an empty file or a count below 1."""
    raise NotImplementedError("TODO: plan_reads - see the docstring and the lesson")


def rows_needed(threads: int, iterations: int, share: str = "all") -> int:
    """How many data rows a run needs so that no row is used twice and nobody reaches EOF: every iteration of
    every thread in a shared file, or one thread's iterations when each thread opens its own copy - which is
    exactly why ``thread`` mode can never give every thread different data from one file."""
    raise NotImplementedError("TODO: rows_needed - see the docstring and the lesson")
