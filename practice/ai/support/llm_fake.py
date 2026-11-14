"""A scripted, offline stand-in for an LLM chat API, so GenAI and agent exercises need no key and no network.

It mimics the *shape* of a hosted messages API (a system prompt, a list of ``{"role", "content"}`` messages,
``max_tokens``, ``temperature``, optional tools; a reply with content blocks, a stop reason and token usage)
without copying any one provider's SDK. Replies come from a script you write, so every test is deterministic.

    llm = ScriptedLLM(["Hello!", lambda req: f"You said {req.messages[-1]['content']}"])
    reply = llm.create(messages=[{"role": "user", "content": "hi"}], max_tokens=50)
    reply.text  -> "Hello!"

A script step can be:
- a string: the reply text;
- a dict ``{"tool": name, "input": {...}}``: a tool-use request (stop_reason ``"tool_use"``);
- an exception instance (e.g. ``RateLimitError(retry_after=2)``): raised for that call;
- a callable ``fn(request) -> step``: decides from the request (useful for graders and routers).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

Step = Any  # str | dict | Exception | Callable[["Request"], Any]


class LLMError(Exception):
    """Base class for API-style errors the fake can raise."""

    status = 500
    retryable = False


class RateLimitError(LLMError):
    """HTTP 429-style: too many requests; ``retry_after`` is seconds to wait."""

    status = 429
    retryable = True

    def __init__(self, retry_after: float = 1.0):
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


class OverloadedError(LLMError):
    """HTTP 5xx-style transient server error."""

    status = 503
    retryable = True


class BadRequestError(LLMError):
    """HTTP 400-style: the request itself is wrong; retrying will not help."""

    status = 400


def count_tokens(text: str) -> int:
    """A toy tokenizer: words and punctuation marks each count as one token. Real tokenizers differ."""
    return len(re.findall(r"\w+|[^\w\s]", text))


@dataclass
class Request:
    messages: list[dict[str, Any]]
    system: str = ""
    max_tokens: int = 256
    temperature: float = 0.0
    tools: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Reply:
    content: list[dict[str, Any]]
    stop_reason: str  # "end_turn" | "max_tokens" | "tool_use"
    input_tokens: int
    output_tokens: int

    @property
    def text(self) -> str:
        return "".join(block["text"] for block in self.content if block["type"] == "text")

    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        return [block for block in self.content if block["type"] == "tool_use"]


class ScriptedLLM:
    """Replays a script of replies; records every request in ``calls``."""

    def __init__(self, script: list[Step] | Callable[[Request], Step]):
        self._script = script
        self._index = 0
        self.calls: list[Request] = []

    def _next_step(self, request: Request) -> Step:
        if callable(self._script):
            step = self._script
        else:
            if self._index >= len(self._script):
                raise AssertionError(f"ScriptedLLM: script exhausted after {len(self._script)} calls")
            step = self._script[self._index]
            self._index += 1
        while callable(step) and not isinstance(step, Exception):
            step = step(request)
        return step

    def create(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        max_tokens: int = 256,
        temperature: float = 0.0,
        tools: list[dict[str, Any]] | None = None,
    ) -> Reply:
        if not messages:
            raise BadRequestError("messages must not be empty")
        if max_tokens < 1:
            raise BadRequestError("max_tokens must be at least 1")
        request = Request([dict(m) for m in messages], system, max_tokens, temperature, list(tools or []))
        self.calls.append(request)
        step = self._next_step(request)
        if isinstance(step, Exception):
            raise step
        prompt_text = system + " ".join(_text_of(m["content"]) for m in messages)
        input_tokens = count_tokens(prompt_text)
        if isinstance(step, dict) and "tool" in step:
            block = {"type": "tool_use", "id": f"call_{len(self.calls)}", "name": step["tool"], "input": step.get("input", {})}
            return Reply([block], "tool_use", input_tokens, count_tokens(str(block["input"])) + 1)
        text = str(step)
        tokens = re.findall(r"\w+|[^\w\s]|\s+", text)
        out, used, stop = [], 0, "end_turn"
        for tok in tokens:
            if not tok.isspace():
                if used == max_tokens:
                    stop = "max_tokens"
                    break
                used += 1
            out.append(tok)
        return Reply([{"type": "text", "text": "".join(out).rstrip()}], stop, input_tokens, used)

    def stream(self, **kwargs: Any) -> Iterator[str]:
        """Yields the reply text in small chunks, like a streaming API's text deltas."""
        reply = self.create(**kwargs)
        text = reply.text
        for start in range(0, len(text), 4):
            yield text[start : start + 4]


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    return " ".join(str(block.get("text", block.get("content", ""))) for block in content)
