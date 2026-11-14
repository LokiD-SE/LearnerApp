"""Keep a conversation inside a model's context window, and notice when the reply was cut off.

Lesson: how-llms-work. Exercise: implement the functions marked TODO.

The context window holds everything in one request: the system prompt, every message AND the reply the
model will write. So the budget is ``input tokens + max_output_tokens <= context_window``. Messages are
``{"role": "user" | "assistant", "content": str}`` dicts; ``count`` is a tokenizer function (the tests pass
``llm_fake.count_tokens``, a toy tokenizer - real providers' tokenizers differ, so count with theirs).
"""

from typing import Any, Callable

from llm_fake import count_tokens


def fit_to_window(
    system: str,
    messages: list[dict[str, Any]],
    context_window: int,
    max_output_tokens: int,
    count: Callable[[str], int] = count_tokens,
) -> tuple[list[dict[str, Any]], int]:
    """Drop the OLDEST messages until the request fits; return ``(kept_messages, input_tokens)``.

    - ``input_tokens`` = ``count(system)`` + ``count(content)`` of every kept message.
    - The request fits when ``input_tokens + max_output_tokens <= context_window``.
    - Drop whole messages from the front, one at a time. The newest message is never dropped.
    - After dropping, the kept list must start with a ``"user"`` message: drop a leading ``"assistant"``
      message too.
    - If even the system prompt plus the newest message does not fit, raise ``ValueError``.
    - Return new lists; never modify ``messages``.
    """
    raise NotImplementedError  # TODO


def ask_within_window(
    client: Any,
    system: str,
    messages: list[dict[str, Any]],
    context_window: int,
    max_output_tokens: int,
) -> dict[str, Any]:
    """Fit the conversation with ``fit_to_window`` (default tokenizer), send it, and report what happened.

    Calls ``client.create(messages=kept, system=system, max_tokens=max_output_tokens)`` once and returns
    ``{"text": reply.text, "dropped": <number of messages left out>, "truncated": <True when the reply's
    stop_reason is "max_tokens">}``.
    """
    raise NotImplementedError  # TODO
