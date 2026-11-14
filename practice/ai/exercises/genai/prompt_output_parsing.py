"""Reason-then-answer prompts and robust answer extraction - lesson prompt-engineering.

A manual chain-of-thought prompt asks the model to write its reasoning first and the final answer last, in
tags a program can find. The program then has to cope with replies that are cut off (``max_tokens``) or
that forget the tags. The client is injected, so tests drive it with the offline ``ScriptedLLM``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SYSTEM = (
    "You answer questions about SandPay merchant fees.\n"
    "Work through the problem step by step inside <reasoning> tags first. "
    "Then give only the final amount inside <answer> tags, for example <answer>12.50</answer>."
)

REMINDER = "Your reply had no <answer> tags. Reply again with the final amount inside <answer> tags."


class TruncatedReply(Exception):
    """The reply stopped at max_tokens, so any answer in it may be incomplete."""


class NoAnswer(Exception):
    """Every attempt came back without a usable <answer>."""


@dataclass
class Answer:
    answer: str
    reasoning: str
    attempts: int


def extract(reply) -> tuple[str, str] | None:
    """Return ``(answer, reasoning)`` from a reply, or ``None`` when there is no ``<answer>`` tag.

    - ``stop_reason == "max_tokens"`` raises ``TruncatedReply`` - never trust a cut-off answer;
    - with several ``<answer>`` tags, the **last** one wins (the final conclusion);
    - text is stripped; an empty answer counts as no answer;
    - reasoning is the text of ``<reasoning>`` if present, else ``""``.
    """
    raise NotImplementedError


def ask_with_reasoning(llm, question: str, max_tokens: int = 200, max_attempts: int = 3) -> Answer:
    """Ask once; repair and retry up to ``max_attempts`` calls in total.

    - truncated reply: retry the **same** messages with ``max_tokens`` doubled;
    - reply without an answer: append that reply as an assistant turn and the ``REMINDER`` as a user turn,
      then retry with the same ``max_tokens``;
    - temperature is 0 on every call; give up with ``NoAnswer`` after ``max_attempts`` calls.
    """
    raise NotImplementedError
