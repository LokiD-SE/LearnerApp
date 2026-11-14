"""Compare prompting, RAG and fine-tuned candidates on the same eval set - lesson fine-tuning-vs-rag-vs-prompting.

Every candidate answers the same cases; a grader marks each answer right or wrong; the comparison uses the
PAIRED results (same case, two approaches) and a sign test on the cases where they disagree, then adds cost
and a regression guard. Clients are passed in, so tests use the offline ScriptedLLM.
"""

from dataclasses import dataclass, field
from math import comb


@dataclass
class ApproachResult:
    name: str
    correct: list = field(default_factory=list)  # one bool per case, in case order
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def accuracy(self):
        return sum(self.correct) / len(self.correct) if self.correct else 0.0


@dataclass
class Decision:
    choice: str
    reasons: list = field(default_factory=list)


def run_approach(name, client, cases, build_request, grade):
    """Ask client about every case and grade the answers.

    build_request(case) returns the keyword arguments for client.create (messages, system, max_tokens...).
    grade(case, text) returns True when the reply text is right. Token counts are summed from reply.input_tokens
    and reply.output_tokens.
    """
    raise NotImplementedError("run_approach")


def discordant(baseline, candidate):
    """(wins, losses): cases only the candidate got right, and cases only the baseline got right.

    Raises ValueError if the two results do not cover the same number of cases.
    """
    raise NotImplementedError("discordant")


def sign_test_p(wins, losses):
    """Exact two-sided sign test: the probability, if both approaches were equally good (each disagreement a
    fair coin), of a split at least as uneven as wins : losses. Returns 1.0 when there are no disagreements."""
    raise NotImplementedError("sign_test_p")


def cost_per_1k_requests(result, price_in, price_out):
    """Cost of 1,000 requests at the result's average token counts; prices are per million tokens."""
    raise NotImplementedError("cost_per_1k_requests")


def choose(results, baseline, prices, alpha=0.05, guard=None, max_regression=0.02):
    """Pick the approach to ship.

    results  - ApproachResult list (one per approach, same cases); baseline is the name of the current approach
    prices   - name -> (price_in, price_out) per million tokens
    guard    - optional name -> accuracy on a regression set (what must not get worse, e.g. old tasks)

    A candidate is accepted when it wins more disagreements than it loses, sign_test_p < alpha, and (with a
    guard) guard[baseline] - guard[candidate] <= max_regression. Among accepted candidates pick the highest
    accuracy, then the lowest cost per 1k requests. With none accepted, keep the baseline. reasons gets one line
    per candidate, in results order.
    """
    raise NotImplementedError("choose")
