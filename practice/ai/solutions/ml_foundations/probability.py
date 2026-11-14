"""Probability for machine learning - reference solution.

Lesson: The maths of machine learning (ml-maths-essentials).
"""

import numpy as np


def posterior(prior, true_positive_rate, false_positive_rate):
    """P(condition | positive test) by Bayes' rule.

    prior               = P(condition)            e.g. P(fraud)
    true_positive_rate  = P(positive | condition) e.g. P(flagged | fraud)
    false_positive_rate = P(positive | no condition)
    P(positive) comes from the law of total probability. All three must be in [0, 1]; raise ValueError
    otherwise, and also when P(positive) is 0 (the posterior is undefined).
    """
    for name, p in (("prior", prior), ("true_positive_rate", true_positive_rate),
                    ("false_positive_rate", false_positive_rate)):
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"{name} must be a probability in [0, 1], got {p}")
    evidence = true_positive_rate * prior + false_positive_rate * (1 - prior)
    if evidence == 0:
        raise ValueError("P(positive) is 0, so the posterior is undefined")
    return float(true_positive_rate * prior / evidence)


def expectation_and_variance(values, probs):
    """Expected value and variance of a discrete random variable.

    values[i] occurs with probability probs[i]. Return (mean, variance) as Python floats, where
    variance = E[(X - E[X])^2]. Raise ValueError if the arrays differ in length, any probability is
    negative, or the probabilities do not sum to 1 (within 1e-9).
    """
    values = np.asarray(values, dtype=float)
    probs = np.asarray(probs, dtype=float)
    if values.shape != probs.shape:
        raise ValueError(f"values and probs differ in shape: {values.shape} and {probs.shape}")
    if (probs < 0).any():
        raise ValueError("probabilities cannot be negative")
    if not np.isclose(probs.sum(), 1.0, rtol=0.0, atol=1e-9):
        raise ValueError(f"probabilities must sum to 1, got {probs.sum()}")
    mean = values @ probs
    variance = ((values - mean) ** 2) @ probs
    return float(mean), float(variance)


def normal_pdf(x, mu=0.0, sigma=1.0):
    """Density of the normal distribution N(mu, sigma^2) at x (a number or an array).

    p(x) = exp(-(x - mu)^2 / (2 sigma^2)) / (sigma * sqrt(2 pi))
    Works element-wise on arrays (no loops). Raise ValueError if sigma <= 0.
    """
    if sigma <= 0:
        raise ValueError(f"sigma must be positive, got {sigma}")
    x = np.asarray(x, dtype=float)
    z = (x - mu) / sigma
    return np.exp(-0.5 * z**2) / (sigma * np.sqrt(2 * np.pi))
