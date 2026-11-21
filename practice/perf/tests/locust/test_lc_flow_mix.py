"""Checks exercises/locust/lc_flow_mix.py: turning a workload model into Locust weights, and a run's request
counts back into a comparison with the model.

The topic folder is called ``locust``, the same name as the Locust package, so this test loads the module from
its file instead of ``from locust.lc_flow_mix import ...`` (which would find the real Locust package)."""

import importlib.util

import pytest
from load_tools import practice_file

pytestmark = pytest.mark.exercise


def _load():
    spec = importlib.util.spec_from_file_location("lc_flow_mix", practice_file("locust/lc_flow_mix.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mix = _load()

CONSOLE = {"browse": 0.6, "pay": 0.3, "report": 0.1}


def test_a_clean_model_becomes_the_smallest_integers():
    assert mix.mix_to_weights(CONSOLE) == {"browse": 6, "pay": 3, "report": 1}
    assert mix.mix_to_weights({"a": 0.5, "b": 0.5}) == {"a": 1, "b": 1}
    assert mix.mix_to_weights({"a": 0.75, "b": 0.25}) == {"a": 3, "b": 1}


def test_a_rare_action_keeps_at_least_weight_one():
    weights = mix.mix_to_weights({"browse": 0.94, "pay": 0.05, "report": 0.01}, tolerance=0.005)
    assert weights["report"] >= 1
    total = sum(weights.values())
    for name, share in {"browse": 0.94, "pay": 0.05, "report": 0.01}.items():
        assert abs(weights[name] / total - share) <= 0.005


def test_looser_tolerance_gives_smaller_weights():
    model = {"browse": 0.55, "pay": 0.3, "report": 0.15}
    tight = mix.mix_to_weights(model, tolerance=0.001)
    loose = mix.mix_to_weights(model, tolerance=0.05)
    assert sum(loose.values()) < sum(tight.values())
    assert tight == {"browse": 11, "pay": 6, "report": 3}


def test_bad_models_are_rejected():
    with pytest.raises(ValueError):
        mix.mix_to_weights({"a": 0.5, "b": 0.4})  # adds up to 0.9
    with pytest.raises(ValueError):
        mix.mix_to_weights({"a": 1.0, "b": 0.0})  # a share of zero is not a task
    with pytest.raises(ValueError):
        mix.mix_to_weights({"a": 0.9991, "b": 0.0009}, tolerance=0.0001, max_total=20)  # does not fit


def test_weights_are_picks_not_requests():
    # a pay flow is 3 requests per pick, browse and report are 1: equal weights do NOT give equal requests
    shares = mix.request_shares({"browse": 1, "pay": 1, "report": 1}, {"browse": 1, "pay": 3, "report": 1})
    assert shares == pytest.approx({"browse": 0.2, "pay": 0.6, "report": 0.2})
    shares = mix.request_shares({"browse": 3, "pay": 1}, {"browse": 1, "pay": 3})
    assert shares == pytest.approx({"browse": 0.5, "pay": 0.5})


def test_deviations_are_signed_and_cover_missing_names():
    dev = mix.mix_deviations({"browse": 70, "pay": 30}, {"browse": 0.6, "pay": 0.3, "report": 0.1})
    assert dev == pytest.approx({"browse": 0.1, "pay": 0.0, "report": -0.1})
    assert list(dev) == ["browse", "pay", "report"], "sorted by name"
    dev = mix.mix_deviations({"browse": 5, "surprise": 5}, {"browse": 1.0})
    assert dev == pytest.approx({"browse": -0.5, "surprise": 0.5})


def test_an_empty_run_deviates_by_the_whole_model():
    assert mix.mix_deviations({}, {"a": 0.4, "b": 0.6}) == pytest.approx({"a": -0.4, "b": -0.6})
