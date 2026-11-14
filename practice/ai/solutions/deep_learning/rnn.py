"""Recurrent networks by hand and with PyTorch: an RNN step loop, gradients through time, and an LSTM
classifier that ignores padding.

Lesson: sequence-models-and-embeddings. Reference solution.
"""

import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence


def rnn_forward(
    x: torch.Tensor,
    h0: torch.Tensor,
    W_ih: torch.Tensor,
    W_hh: torch.Tensor,
    b_ih: torch.Tensor,
    b_hh: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Run a one-layer Elman RNN (tanh) over a batch, one time step at a time.

    Shapes follow ``nn.RNN`` with ``batch_first=False``: ``x`` is (L, N, H_in), ``h0`` is (N, H),
    ``W_ih`` is (H, H_in), ``W_hh`` is (H, H), ``b_ih`` and ``b_hh`` are (H,). Each step computes

        h_t = tanh(x_t W_ih^T + b_ih + h_{t-1} W_hh^T + b_hh)

    Returns ``(output, h_n)``: ``output`` stacks every h_t, shape (L, N, H); ``h_n`` is the last h_t, (N, H).
    Use only tensor operations (no ``nn.RNN``), so autograd can differentiate through the loop.
    """
    h = h0
    outputs = []
    for t in range(x.shape[0]):
        h = torch.tanh(x[t] @ W_ih.T + b_ih + h @ W_hh.T + b_hh)
        outputs.append(h)
    return torch.stack(outputs), h


def input_gradient_norms(rnn: nn.Module, x: torch.Tensor) -> torch.Tensor:
    """How strongly the final hidden state depends on each input step.

    ``rnn`` is an ``nn.RNN``, ``nn.GRU`` or ``nn.LSTM`` with ``batch_first=False``; ``x`` is (L, N, H_in).
    Take the loss to be the sum of the last layer's final hidden state, back-propagate it to the input,
    and return a tensor of shape (L,) whose entry t is the L2 norm of d(loss)/d(x_t) over the whole batch.
    ``x`` itself must not be changed and must not keep ``requires_grad`` afterwards.
    """
    x = x.detach().clone().requires_grad_(True)
    _, state = rnn(x)
    h_n = state[0] if isinstance(state, tuple) else state  # an LSTM returns (h_n, c_n)
    h_n[-1].sum().backward()
    return x.grad.flatten(start_dim=1).norm(dim=1)


class LSTMClassifier(nn.Module):
    """Embedding -> LSTM -> linear: one label per variable-length token sequence.

    ``forward(ids, lengths)`` takes right-padded ids of shape (B, T) and each sequence's real length (B,),
    and returns logits of shape (B, num_classes). The prediction for a sequence must not depend on how
    much padding it has, so classify from the hidden state after each sequence's **last real token**:
    embed with ``padding_idx=pad_id``, pack with ``pack_padded_sequence(..., batch_first=True,
    enforce_sorted=False)``, run the LSTM and use the final hidden state ``h_n[-1]``.
    """

    def __init__(self, vocab_size: int, embed_dim: int, hidden_size: int, num_classes: int, pad_id: int = 0):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=pad_id)
        self.lstm = nn.LSTM(embed_dim, hidden_size, batch_first=True)
        self.head = nn.Linear(hidden_size, num_classes)

    def forward(self, ids: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        embedded = self.embedding(ids)
        packed = pack_padded_sequence(embedded, lengths.cpu(), batch_first=True, enforce_sorted=False)
        _, (h_n, _) = self.lstm(packed)
        return self.head(h_n[-1])


def train_classifier(
    model: nn.Module,
    ids: torch.Tensor,
    lengths: torch.Tensor,
    labels: torch.Tensor,
    epochs: int = 60,
    lr: float = 0.02,
    max_grad_norm: float = 1.0,
) -> list[float]:
    """Full-batch Adam with gradient-norm clipping; returns the loss of every epoch. (Provided - not an exercise.)"""
    optimiser = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    losses = []
    model.train()
    for _ in range(epochs):
        optimiser.zero_grad()
        loss = loss_fn(model(ids, lengths), labels)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
        optimiser.step()
        losses.append(loss.item())
    return losses
