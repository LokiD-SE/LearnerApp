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
    result = ApproachResult(name)
    for case in cases:
        reply = client.create(**build_request(case))
        result.correct.append(bool(grade(case, reply.text)))
        result.input_tokens += reply.input_tokens
        result.output_tokens += reply.output_tokens
    return result


def discordant(baseline, candidate):
    """(wins, losses): cases only the candidate got right, and cases only the baseline got right.

    Raises ValueError if the two results do not cover the same number of cases.
    """
    if len(baseline.correct) != len(candidate.correct):
        raise ValueError("results cover different numbers of cases")
    wins = sum(1 for b, c in zip(baseline.correct, candidate.correct) if c and not b)
    losses = sum(1 for b, c in zip(baseline.correct, candidate.correct) if b and not c)
    return wins, losses


def sign_test_p(wins, losses):
    """Exact two-sided sign test: the probability, if both approaches were equally good (each disagreement a
    fair coin), of a split at least as uneven as wins : losses. Returns 1.0 when there are no disagreements."""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    tail = sum(comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def cost_per_1k_requests(result, price_in, price_out):
    """Cost of 1,000 requests at the result's average token counts; prices are per million tokens."""
    n = len(result.correct)
    if n == 0:
        return 0.0
    per_request = (result.input_tokens * price_in + result.output_tokens * price_out) / n / 1_000_000
    return per_request * 1000


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
    by_name = {r.name: r for r in results}
    base = by_name[baseline]
    accepted, reasons = [], []
    for r in results:
        if r.name == baseline:
            continue
        wins, losses = discordant(base, r)
        p = sign_test_p(wins, losses)
        if wins <= losses or p >= alpha:
            reasons.append(f"{r.name}: {wins} wins / {losses} losses, p={p:.3f} - not better than {baseline}")
        elif guard is not None and guard[baseline] - guard[r.name] > max_regression:
            drop = guard[baseline] - guard[r.name]
            reasons.append(f"{r.name}: better (p={p:.3f}) but regression set drops {drop:.3f}")
        else:
            accepted.append(r)
            reasons.append(f"{r.name}: {wins} wins / {losses} losses, p={p:.3f} - accepted")
    if not accepted:
        return Decision(baseline, reasons)
    best = min(accepted, key=lambda r: (-r.accuracy, cost_per_1k_requests(r, *prices[r.name])))
    return Decision(best.name, reasons)
