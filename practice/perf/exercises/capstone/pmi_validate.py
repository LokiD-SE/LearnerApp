"""Check your own estimate against a run - your turn.

A good interview answer ends with "and I would check the estimate with a short run". Implement the comparison.
Run: .venv/bin/python -m pytest tests/capstone/test_pmi_validate.py
"""


def compare(predicted_rps: float, measured_rps: float, tolerance: float = 0.1) -> str:
    """"as_predicted" when the measured rate is within ``tolerance`` (a fraction, 0.1 = 10 %) of the prediction,
    "below_prediction" when it is lower than that, "above_prediction" when it is higher.

    TODO: raise ValueError when predicted_rps <= 0, measured_rps < 0, or tolerance is outside [0, 1).
    """
    raise NotImplementedError("TODO")


def explain(verdict: str) -> str:
    """One sentence on where to look for each verdict (a different sentence for each).

    - below_prediction: users waited longer than assumed - saturation, a slow generator, or a real response time
      above the plan.
    - above_prediction: users cycled faster than assumed - think or response time too high in the model, or
      requests failing fast.

    TODO: raise ValueError for an unknown verdict.
    """
    raise NotImplementedError("TODO")
