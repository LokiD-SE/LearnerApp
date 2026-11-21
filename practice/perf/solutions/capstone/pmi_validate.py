"""Check your own estimate against a run - reference solution.

A good interview answer ends with "and I would check the estimate with a short run". The check has three
outcomes, and each one points somewhere different.
"""


def compare(predicted_rps: float, measured_rps: float, tolerance: float = 0.1) -> str:
    """``as_predicted`` when the measured rate is within ``tolerance`` (a fraction) of the prediction,
    ``below_prediction`` when it is lower, ``above_prediction`` when it is higher."""
    if predicted_rps <= 0:
        raise ValueError("predicted_rps must be > 0")
    if measured_rps < 0 or not 0 <= tolerance < 1:
        raise ValueError("measured_rps must be >= 0 and tolerance in [0, 1)")
    ratio = measured_rps / predicted_rps
    if ratio < 1 - tolerance:
        return "below_prediction"
    if ratio > 1 + tolerance:
        return "above_prediction"
    return "as_predicted"


EXPLANATIONS = {
    "as_predicted": "The model holds for this run: the response time and think time you assumed are the ones you got.",
    "below_prediction": "Users spent longer waiting than you assumed: the system queued (saturation), the "
                        "generator is too slow, or the real response time is above the plan.",
    "above_prediction": "Users cycled faster than you assumed: the think time or response time in the model is "
                        "too high, or requests are failing fast.",
}


def explain(verdict: str) -> str:
    """One sentence on where to look for each verdict."""
    try:
        return EXPLANATIONS[verdict]
    except KeyError:
        raise ValueError(f"unknown verdict: {verdict!r}") from None
