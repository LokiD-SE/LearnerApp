"""A PyTorch training loop for SandPay's fraud model - exercise.

Reference solution: solutions/deep_learning/torch_training_loop.py. Lesson: PyTorch fundamentals (#/lesson/pytorch-fundamentals).
The data is synthetic: ``make_sandpay_transactions`` draws fictional card payments from a known model.
FraudNet, train_one_epoch and evaluate are first drafts that run but are wrong; the rest raise NotImplementedError.
Run: .venv/bin/python -m pytest tests/deep_learning/test_torch_training_loop.py
"""

from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, random_split

N_FEATURES = 5


def make_sandpay_transactions(n: int = 2000, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Return synthetic SandPay features X (n, 5) and fraud labels y (n,), both float32 (given, already correct).

    Columns: standardised log amount, hour of day / 23, card not present (0/1), new device (0/1), merchant risk.
    """
    rng = np.random.default_rng(seed)
    amount = rng.lognormal(mean=3.5, sigma=1.0, size=n)
    hour = rng.integers(0, 24, size=n)
    card_not_present = rng.random(n) < 0.4
    new_device = rng.random(n) < 0.15
    merchant_risk = rng.beta(2, 8, size=n)
    night = (hour < 6).astype(float)
    logit = (
        -4.0
        + 0.6 * (np.log(amount) - 3.5)
        + 1.2 * card_not_present
        + 1.5 * new_device
        + 3.0 * merchant_risk
        + 0.8 * night
    )
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(np.float32)
    X = np.column_stack([np.log(amount) - 3.5, hour / 23.0, card_not_present, new_device, merchant_risk])
    return X.astype(np.float32), y


class FraudNet(nn.Module):
    """Linear(n_features, hidden) -> ReLU -> Dropout(dropout) -> Linear(hidden, 1).

    ``forward`` returns one logit per example, shape (N,) - not a probability.
    """

    def __init__(self, n_features: int = N_FEATURES, hidden: int = 16, dropout: float = 0.2):
        super().__init__()
        self.hidden = nn.Linear(n_features, hidden)
        self.dropout = nn.Dropout(p=dropout)
        self.out = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # First draft - compare the shape it returns with the docstring.
        return self.out(self.dropout(torch.relu(self.hidden(x))))


def make_loaders(
    X: np.ndarray, y: np.ndarray, batch_size: int = 64, val_fraction: float = 0.2, seed: int = 0
) -> tuple[DataLoader, DataLoader]:
    """Split into training and validation sets and return (train_loader, val_loader).

    - Both yield float32 batches (xb of shape (B, n_features), yb of shape (B,)).
    - The split uses ``torch.Generator().manual_seed(seed)``; the validation set has round(n * val_fraction) rows.
    - The training loader reshuffles every epoch with its own generator seeded with ``seed``; the validation
      loader does not shuffle.
    """
    raise NotImplementedError


def train_one_epoch(
    model: nn.Module, loader: DataLoader, loss_fn: nn.Module, optimizer: torch.optim.Optimizer
) -> float:
    """Run one pass over ``loader`` in training mode, updating the model; return the mean loss per example."""
    # First draft. It trains - a bit. Three things are missing or wrong.
    losses = []
    for xb, yb in loader:
        loss = loss_fn(model(xb), yb)
        loss.backward()
        optimizer.step()
        losses.append(loss)
    return float(sum(losses) / len(losses))


def evaluate(model: nn.Module, loader: DataLoader, loss_fn: nn.Module) -> tuple[float, float]:
    """Return (mean loss per example, accuracy at logit > 0) on ``loader`` without changing the model.

    Evaluation mode (dropout off), no graph recorded, no gradients stored.
    """
    # First draft.
    total, correct, count = 0.0, 0, 0
    for xb, yb in loader:
        logits = model(xb)
        loss = loss_fn(logits, yb)
        loss.backward()
        total += loss.item()
        correct += ((logits > 0).float() == yb).sum().item()
        count += len(yb)
    return total / len(loader), correct / count


def fit(
    X: np.ndarray, y: np.ndarray, epochs: int = 10, learning_rate: float = 0.01, seed: int = 0
) -> tuple[FraudNet, list[dict[str, float]]]:
    """Train a FraudNet with Adam and BCEWithLogitsLoss; return (model, history).

    Call ``torch.manual_seed(seed)`` before building the model. history[i] has the keys
    "train_loss", "val_loss" and "val_accuracy" for epoch i + 1.
    """
    raise NotImplementedError


def save_weights(model: nn.Module, path: str | Path) -> None:
    """Save only the model's state_dict (not the pickled module) to ``path``."""
    raise NotImplementedError


def load_weights(path: str | Path, n_features: int = N_FEATURES, hidden: int = 16) -> FraudNet:
    """Build a new FraudNet, load the saved state_dict into it (weights_only) and return it in evaluation mode."""
    raise NotImplementedError
