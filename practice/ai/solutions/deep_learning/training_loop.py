"""A careful PyTorch training loop with clipping and early stopping (lesson: training-deep-networks).

The loop is where most silent training bugs live: gradients that are never cleared, a model left in
evaluation mode while training (or in training mode while validating), validation that builds a graph, and
early stopping that returns the last model instead of the best one.
"""

import copy

import torch
from torch import nn


def iterate_minibatches(X, y, batch_size, generator):
    """Yield ``(X_batch, y_batch)`` pairs covering every row once, in an order shuffled with
    ``torch.randperm(len(X), generator=generator)``. The last batch may be smaller."""
    order = torch.randperm(len(X), generator=generator)
    for start in range(0, len(X), batch_size):
        idx = order[start : start + batch_size]
        yield X[idx], y[idx]


def train_one_epoch(model, batches, loss_fn, optimiser, max_grad_norm=None):
    """Train for one pass over ``batches`` and return the mean of the batch losses (a float).

    Put the model in training mode, and for every batch: clear old gradients, compute the loss, backpropagate,
    clip the total gradient norm to ``max_grad_norm`` with ``nn.utils.clip_grad_norm_`` when it is not None,
    and take an optimiser step.
    """
    model.train()
    total, count = 0.0, 0
    for xb, yb in batches:
        optimiser.zero_grad()
        loss = loss_fn(model(xb), yb)
        loss.backward()
        if max_grad_norm is not None:
            nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
        optimiser.step()
        total += loss.item()
        count += 1
    return total / count


def evaluate(model, X, y, loss_fn):
    """Return the loss on ``(X, y)`` as a float, with the model in evaluation mode and gradients off."""
    model.eval()
    with torch.no_grad():
        return loss_fn(model(X), y).item()


def fit(model, X_train, y_train, X_val, y_val, loss_fn, optimiser, *, max_epochs, patience, batch_size=32,
        seed=0, max_grad_norm=None):
    """Train with early stopping and return a history dict.

    Each epoch: train on shuffled minibatches (one ``torch.Generator`` seeded with ``seed`` for the whole run),
    then evaluate on the validation set. Keep a deep copy of the ``state_dict`` from the epoch with the lowest
    validation loss; stop after ``patience`` epochs without improvement or at ``max_epochs``. Before
    returning, load the best state back into ``model``.

    History keys: ``train_loss`` and ``val_loss`` (one float per epoch run) and ``best_epoch`` (1-based).
    """
    generator = torch.Generator().manual_seed(seed)
    history = {"train_loss": [], "val_loss": [], "best_epoch": 0}
    best_loss, best_state, waited = float("inf"), None, 0
    for epoch in range(1, max_epochs + 1):
        batches = iterate_minibatches(X_train, y_train, batch_size, generator)
        history["train_loss"].append(train_one_epoch(model, batches, loss_fn, optimiser, max_grad_norm))
        val_loss = evaluate(model, X_val, y_val, loss_fn)
        history["val_loss"].append(val_loss)
        if val_loss < best_loss:
            best_loss, best_state, waited = val_loss, copy.deepcopy(model.state_dict()), 0
            history["best_epoch"] = epoch
        else:
            waited += 1
            if waited >= patience:
                break
    model.load_state_dict(best_state)
    return history
