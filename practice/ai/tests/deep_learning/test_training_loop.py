"""Tests for exercises/deep_learning/training_loop.py (lesson: training-deep-networks)."""

import pytest
import torch
from deep_learning.training_loop import evaluate, fit, iterate_minibatches, train_one_epoch
from torch import nn

pytestmark = pytest.mark.exercise


def sandpay_data(n, seed=0):
    """Synthetic SandPay transactions: 20 standardised features and a non-linear fraud rule."""
    g = torch.Generator().manual_seed(seed)
    X = torch.randn(n, 20, generator=g)
    score = 1.5 * X[:, 0] * X[:, 1] + torch.sin(2 * X[:, 2]) + X[:, 3] ** 2 - 1.2 + 0.5 * torch.randn(n, generator=g)
    return X, (score > 0).float().unsqueeze(1)


class ModeRecorder(nn.Module):
    """Passes its input through and records the mode and grad state of every forward call."""

    def __init__(self):
        super().__init__()
        self.calls = []

    def forward(self, x):
        self.calls.append((self.training, torch.is_grad_enabled()))
        return x


def small_model(dropout=0.0, seed=0):
    torch.manual_seed(seed)
    return nn.Sequential(nn.Linear(20, 32), nn.ReLU(), nn.Dropout(dropout), nn.Linear(32, 1))


def test_minibatches_cover_every_row_once():
    X = torch.arange(10).float().unsqueeze(1)
    y = torch.arange(10).float()
    batches = list(iterate_minibatches(X, y, 4, torch.Generator().manual_seed(0)))
    assert [len(xb) for xb, _ in batches] == [4, 4, 2]
    seen = torch.cat([yb for _, yb in batches])
    assert sorted(seen.tolist()) == list(range(10))
    assert seen.tolist() != list(range(10))
    torch.testing.assert_close(torch.cat([xb for xb, _ in batches]).squeeze(1), seen)


def test_train_one_epoch_clears_gradients_between_batches():
    X, y = sandpay_data(64)
    model = small_model()
    optimiser = torch.optim.SGD(model.parameters(), lr=0.0)
    batches = [(X[:32], y[:32]), (X[32:], y[32:])]
    train_one_epoch(model, batches, nn.BCEWithLogitsLoss(), optimiser)
    reference = small_model()
    nn.BCEWithLogitsLoss()(reference(X[32:]), y[32:]).backward()
    for p, q in zip(model.parameters(), reference.parameters()):
        torch.testing.assert_close(p.grad, q.grad)


def test_train_one_epoch_uses_training_mode_and_returns_the_mean_loss():
    recorder = ModeRecorder()
    model = nn.Sequential(nn.Linear(20, 1), recorder)
    model.eval()
    X, y = sandpay_data(40)
    optimiser = torch.optim.SGD(model.parameters(), lr=0.0)
    loss_fn = nn.BCEWithLogitsLoss()
    expected = sum(loss_fn(model[0](X[i : i + 20]), y[i : i + 20]).item() for i in (0, 20)) / 2
    mean_loss = train_one_epoch(model, [(X[:20], y[:20]), (X[20:], y[20:])], loss_fn, optimiser)
    assert recorder.calls == [(True, True), (True, True)]
    assert mean_loss == pytest.approx(expected)


def test_train_one_epoch_clips_the_gradient_norm():
    X, y = sandpay_data(32)
    model = small_model()
    before = torch.cat([p.detach().flatten().clone() for p in model.parameters()])
    optimiser = torch.optim.SGD(model.parameters(), lr=1.0)
    train_one_epoch(model, [(X, y * 50)], nn.MSELoss(), optimiser, max_grad_norm=0.25)
    after = torch.cat([p.detach().flatten() for p in model.parameters()])
    assert torch.linalg.vector_norm(after - before).item() == pytest.approx(0.25, rel=1e-4)


def test_evaluate_uses_eval_mode_without_gradients():
    recorder = ModeRecorder()
    model = nn.Sequential(nn.Linear(20, 1), nn.Dropout(0.5), recorder)
    model.train()
    X, y = sandpay_data(100)
    first = evaluate(model, X, y, nn.BCEWithLogitsLoss())
    second = evaluate(model, X, y, nn.BCEWithLogitsLoss())
    assert recorder.calls == [(False, False), (False, False)]
    assert first == second
    with torch.no_grad():
        assert first == pytest.approx(nn.BCEWithLogitsLoss()(model[0](X), y).item())


def test_fit_learns_and_stops_early_with_the_best_weights():
    X, y = sandpay_data(1300)
    X_train, y_train, X_val, y_val = X[:300], y[:300], X[300:], y[300:]
    torch.manual_seed(0)
    model = nn.Sequential(nn.Linear(20, 128), nn.ReLU(), nn.Linear(128, 128), nn.ReLU(), nn.Linear(128, 1))
    optimiser = torch.optim.Adam(model.parameters(), lr=0.003)
    loss_fn = nn.BCEWithLogitsLoss()
    history = fit(model, X_train, y_train, X_val, y_val, loss_fn, optimiser, max_epochs=60, patience=5)
    epochs_run = len(history["val_loss"])
    best = history["best_epoch"]
    assert epochs_run < 60, "a model this large overfits 300 rows, so early stopping must trigger"
    assert epochs_run == best + 5
    assert history["val_loss"][best - 1] == min(history["val_loss"])
    assert history["train_loss"][-1] < history["train_loss"][0]
    assert evaluate(model, X_val, y_val, loss_fn) == pytest.approx(history["val_loss"][best - 1], rel=1e-6)
