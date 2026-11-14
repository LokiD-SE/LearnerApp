"""Tests for exercises/deep_learning/torch_training_loop.py (lesson: pytorch-fundamentals)."""

import math

import pytest
import torch
from deep_learning.torch_training_loop import (
    FraudNet,
    evaluate,
    fit,
    load_weights,
    make_loaders,
    make_sandpay_transactions,
    save_weights,
    train_one_epoch,
)
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

pytestmark = pytest.mark.exercise


@pytest.fixture(scope="module")
def data():
    return make_sandpay_transactions(2000, seed=0)


def test_fraudnet_outputs_one_logit_per_example():
    torch.manual_seed(0)
    model = FraudNet(5, hidden=16)
    assert model(torch.randn(7, 5)).shape == (7,)
    assert sum(p.numel() for p in model.parameters()) == 5 * 16 + 16 + 16 + 1


def test_fraudnet_uses_dropout_only_in_training_mode():
    torch.manual_seed(0)
    model = FraudNet(5, hidden=64, dropout=0.5)
    x = torch.randn(32, 5)
    model.train()
    assert not torch.equal(model(x), model(x))
    model.eval()
    with torch.no_grad():
        torch.testing.assert_close(model(x), model(x))


def test_make_loaders_split_sizes_and_dtypes(data):
    X, y = data
    train_loader, val_loader = make_loaders(X, y, batch_size=64, val_fraction=0.2, seed=0)
    assert len(train_loader.dataset) == 1600
    assert len(val_loader.dataset) == 400
    xb, yb = next(iter(train_loader))
    assert xb.shape == (64, 5) and yb.shape == (64,)
    assert xb.dtype == torch.float32 and yb.dtype == torch.float32


def test_make_loaders_is_reproducible_and_validation_is_not_shuffled(data):
    X, y = data
    first = next(iter(make_loaders(X, y, seed=3)[0]))[1]
    again = next(iter(make_loaders(X, y, seed=3)[0]))[1]
    torch.testing.assert_close(first, again)
    _, val_loader = make_loaders(X, y, seed=3)
    pass_one = torch.cat([yb for _, yb in val_loader])
    pass_two = torch.cat([yb for _, yb in val_loader])
    torch.testing.assert_close(pass_one, pass_two)


def _one_batch_twice():
    torch.manual_seed(0)
    xb = torch.randn(8, 5)
    yb = (torch.rand(8) < 0.5).float()
    ds = TensorDataset(torch.cat([xb, xb]), torch.cat([yb, yb]))
    return xb, yb, DataLoader(ds, batch_size=8, shuffle=False)


def test_train_one_epoch_resets_gradients_between_steps():
    xb, yb, loader = _one_batch_twice()
    torch.manual_seed(1)
    model = FraudNet(5, hidden=4, dropout=0.0)
    expected = FraudNet(5, hidden=4, dropout=0.0)
    expected.load_state_dict(model.state_dict())
    loss_fn = nn.BCEWithLogitsLoss()
    reference_opt = torch.optim.SGD(expected.parameters(), lr=0.5)
    for _ in range(2):
        reference_opt.zero_grad()
        loss_fn(expected(xb), yb).backward()
        reference_opt.step()
    train_one_epoch(model, loader, loss_fn, torch.optim.SGD(model.parameters(), lr=0.5))
    for got, want in zip(model.parameters(), expected.parameters()):
        torch.testing.assert_close(got, want)


def test_train_one_epoch_returns_mean_loss_and_uses_training_mode():
    xb, yb, loader = _one_batch_twice()
    torch.manual_seed(1)
    model = FraudNet(5, hidden=4, dropout=0.0)
    loss_fn = nn.BCEWithLogitsLoss()
    with torch.no_grad():
        first = loss_fn(model(xb), yb).item()
    model.eval()
    mean_loss = train_one_epoch(model, loader, loss_fn, torch.optim.SGD(model.parameters(), lr=0.0))
    assert model.training
    assert isinstance(mean_loss, float)
    assert mean_loss == pytest.approx(first, rel=1e-6)


def test_evaluate_changes_nothing_and_stores_no_gradients(data):
    X, y = data
    torch.manual_seed(0)
    model = FraudNet(5, hidden=16, dropout=0.5)
    _, val_loader = make_loaders(X, y, seed=0)
    before = {k: v.clone() for k, v in model.state_dict().items()}
    model.train()
    loss_a, acc_a = evaluate(model, val_loader, nn.BCEWithLogitsLoss())
    loss_b, acc_b = evaluate(model, val_loader, nn.BCEWithLogitsLoss())
    assert loss_a == pytest.approx(loss_b, rel=1e-6) and acc_a == acc_b
    assert not model.training
    assert all(p.grad is None for p in model.parameters())
    for k, v in model.state_dict().items():
        torch.testing.assert_close(v, before[k])
    assert 0.0 <= acc_a <= 1.0


def test_evaluate_mean_loss_is_per_example_not_per_batch():
    torch.manual_seed(0)
    model = FraudNet(5, hidden=4, dropout=0.0)
    xs = torch.randn(10, 5)
    ys = (torch.rand(10) < 0.5).float()
    loader = DataLoader(TensorDataset(xs, ys), batch_size=4)
    with torch.no_grad():
        expected = nn.BCEWithLogitsLoss()(model(xs), ys).item()
        accuracy = ((model(xs) > 0).float() == ys).float().mean().item()
    loss, acc = evaluate(model, loader, nn.BCEWithLogitsLoss())
    assert loss == pytest.approx(expected, rel=1e-5)
    assert acc == pytest.approx(accuracy)


def test_fit_beats_the_constant_baseline_on_validation(data):
    X, y = data
    model, history = fit(X, y, epochs=8, learning_rate=0.01, seed=0)
    assert len(history) == 8
    assert set(history[0]) == {"train_loss", "val_loss", "val_accuracy"}
    assert history[-1]["train_loss"] < history[0]["train_loss"]
    _, val_loader = make_loaders(X, y, seed=0)
    train_loader, _ = make_loaders(X, y, seed=0)
    rate = torch.cat([yb for _, yb in train_loader]).mean().item()
    yv = torch.cat([yb for _, yb in val_loader])
    constant = -(yv * math.log(rate) + (1 - yv) * math.log(1 - rate)).mean().item()
    assert history[-1]["val_loss"] < constant - 0.03
    assert isinstance(model, FraudNet)


def test_save_and_load_weights_round_trip(tmp_path, data):
    X, _ = data
    torch.manual_seed(0)
    model = FraudNet(5, hidden=16)
    path = tmp_path / "fraudnet.pt"
    save_weights(model, path)
    assert isinstance(torch.load(path, weights_only=True), dict)
    loaded = load_weights(path, n_features=5, hidden=16)
    assert not loaded.training
    model.eval()
    xb = torch.as_tensor(X[:20])
    with torch.no_grad():
        torch.testing.assert_close(loaded(xb), model(xb))
