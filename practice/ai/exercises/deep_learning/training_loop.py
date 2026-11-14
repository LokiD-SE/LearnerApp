"""A careful PyTorch training loop with clipping and early stopping (lesson: training-deep-networks).

The loop is where most silent training bugs live: gradients that are never cleared, a model left in
evaluation mode while training (or in training mode while validating), validation that builds a graph, and
early stopping that returns the last model instead of the best one.

The starting draft below runs without errors - and has all of those bugs. Fix it until the tests pass.
"""

import copy  # noqa: F401 - you will need it

import torch
from torch import nn  # noqa: F401 - you will need it


def iterate_minibatches(X, y, batch_size, generator):
    """Yield ``(X_batch, y_batch)`` pairs covering every row once, in an order shuffled with
    ``torch.randperm(len(X), generator=generator)``. The last batch may be smaller."""
    raise NotImplementedError


def train_one_epoch(model, batches, loss_fn, optimiser, max_grad_norm=None):
    """Train for one pass over ``batches`` and return the mean of the batch losses (a float).

    Put the model in training mode, and for every batch: clear old gradients, compute the loss, backpropagate,
    clip the total gradient norm to ``max_grad_norm`` with ``nn.utils.clip_grad_norm_`` when it is not None,
    and take an optimiser step.
    """
    total, count = 0.0, 0
    for xb, yb in batches:
        loss = loss_fn(model(xb), yb)
        loss.backward()
        optimiser.step()
        total += loss.item()
        count += 1
    return total / count


def evaluate(model, X, y, loss_fn):
    """Return the loss on ``(X, y)`` as a float, with the model in evaluation mode and gradients off."""
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
    best_loss, waited = float("inf"), 0
    for epoch in range(1, max_epochs + 1):
        batches = iterate_minibatches(X_train, y_train, batch_size, generator)
        history["train_loss"].append(train_one_epoch(model, batches, loss_fn, optimiser, max_grad_norm))
        val_loss = evaluate(model, X_val, y_val, loss_fn)
        history["val_loss"].append(val_loss)
        if val_loss < best_loss:
            best_loss, waited = val_loss, 0
            history["best_epoch"] = epoch
        else:
            waited += 1
            if waited >= patience:
                break
    return history
