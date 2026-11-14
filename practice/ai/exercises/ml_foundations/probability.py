"""Probability for machine learning - exercise.

Lesson: The maths of machine learning (ml-maths-essentials).
Run: .venv/bin/python -m pytest tests/ml_foundations/test_probability.py
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
    # A first draft that confuses P(flagged | fraud) with P(fraud | flagged).
    return true_positive_rate


def expectation_and_variance(values, probs):
    """Expected value and variance of a discrete random variable.

    values[i] occurs with probability probs[i]. Return (mean, variance) as Python floats, where
    variance = E[(X - E[X])^2]. Raise ValueError if the arrays differ in length, any probability is
    negative, or the probabilities do not sum to 1 (within 1e-9).
    """
    raise NotImplementedError


def normal_pdf(x, mu=0.0, sigma=1.0):
    """Density of the normal distribution N(mu, sigma^2) at x (a number or an array).

    p(x) = exp(-(x - mu)^2 / (2 sigma^2)) / (sigma * sqrt(2 pi))
    Works element-wise on arrays (no loops). Raise ValueError if sigma <= 0.
    """
    raise NotImplementedError
