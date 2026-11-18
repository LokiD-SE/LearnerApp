"""Three workflow patterns from Anthropic's "Building effective agents" (2024) - lesson
agent-loops-and-workflow-patterns. In a workflow your code fixes the path; the model only fills in each step.

- ``chain``: prompt chaining - each step's output is the next step's input, with a programmatic gate after each step;
- ``classify`` / ``route``: routing - classify the input, then hand it to the prompt written for that class, with a
  fallback when the label is not one you know;
- ``parallel_sections`` / ``vote``: parallelisation - independent prompts at the same time (sectioning), or the same
  prompt several times with the majority deciding (voting).

``map_fn`` is injectable so tests can run the parallel calls in order; the default runs them on threads.
"""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterable


class GateError(Exception):
    """A chain step's output failed its gate; later steps were not run."""

    def __init__(self, step: int, output: str):
        super().__init__(f"gate failed after step {step}")
        self.step = step
        self.output = output


def ask(client: Any, prompt: str, max_tokens: int = 300, temperature: float = 0.0) -> str:
    """One user message, the reply text."""
    reply = client.create(messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens, temperature=temperature)
    return reply.text


def thread_map(fn: Callable[[Any], Any], items: Iterable[Any]) -> list[Any]:
    """map() on a thread pool, results in input order."""
    items = list(items)
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=len(items)) as pool:
        return list(pool.map(fn, items))


def chain(
    client: Any,
    prompts: list[str],
    text: str,
    gate: Callable[[int, str], bool] | None = None,
) -> list[str]:
    """Run the prompts in order. Each is a template with ``{input}``: step 0 gets ``text``, step i gets the output of
    step i-1. After each step call ``gate(i, output)``; if it returns False raise ``GateError(i, output)`` and make no
    further calls. Return every step's output."""
    outputs, current = [], text
    for i, template in enumerate(prompts):
        current = ask(client, template.format(input=current))
        if gate is not None and not gate(i, current):
            raise GateError(i, current)
        outputs.append(current)
    return outputs


def classify(client: Any, text: str, labels: list[str]) -> str | None:
    """Ask for exactly one label at temperature 0.

    Prompt: ``"Classify the message into exactly one of: a, b, c. Reply with the label only."`` followed by the
    message inside ``<message>`` / ``</message>`` lines. Normalise the reply (strip spaces and a trailing full
    stop, lower-case) and return it if it is one of ``labels``, else None.
    """
    prompt = (
        f"Classify the message into exactly one of: {', '.join(labels)}. Reply with the label only.\n"
        f"<message>\n{text}\n</message>"
    )
    label = ask(client, prompt, max_tokens=10).strip().rstrip(".").strip().lower()
    return label if label in labels else None


def route(client: Any, text: str, handlers: dict[str, str], fallback: str = "human") -> tuple[str, str | None]:
    """Classify with the handler names as labels, then run that handler's prompt template (``{input}`` = text).
    An unknown label returns ``(fallback, None)`` without a second call."""
    label = classify(client, text, list(handlers))
    if label is None:
        return fallback, None
    return label, ask(client, handlers[label].format(input=text))


def parallel_sections(
    client: Any, text: str, prompts: dict[str, str], map_fn: Callable[..., list[Any]] = thread_map
) -> dict[str, str]:
    """Run every prompt template (``{input}`` = text) independently, through ``map_fn``; return name -> output in
    the order of ``prompts``."""
    names = list(prompts)
    outputs = map_fn(lambda name: ask(client, prompts[name].format(input=text)), names)
    return dict(zip(names, outputs))


def vote(
    client: Any,
    prompt: str,
    labels: list[str],
    n: int = 5,
    temperature: float = 1.0,
    map_fn: Callable[..., list[Any]] = thread_map,
) -> dict[str, Any]:
    """Ask the same prompt ``n`` times at ``temperature`` and count the normalised replies (as in ``classify``);
    replies that are not a label count as ``"invalid"``.

    Returns ``{"label": winner or None, "votes": {label: count}, "n": n}``. The winner needs MORE than half of all
    ``n`` votes; otherwise ``label`` is None (no majority - escalate). ``votes`` has only labels that got a vote.
    """
    replies = map_fn(lambda _: ask(client, prompt, max_tokens=10, temperature=temperature), range(n))
    counts: Counter[str] = Counter()
    for reply in replies:
        label = reply.strip().rstrip(".").strip().lower()
        counts[label if label in labels else "invalid"] += 1
    winner = None
    for label in labels:
        if counts[label] * 2 > n:
            winner = label
    return {"label": winner, "votes": dict(counts), "n": n}
