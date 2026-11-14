"""A LoRA linear layer, parameter counting and adding adapters to a model - lesson fine-tuning-vs-rag-vs-prompting.

LoRA (Hu et al. 2021, arXiv 2106.09685, section 4.1) freezes a pretrained weight W0 and learns a low-rank update
delta_W = B @ A, with B of shape (out, r) and A of shape (r, in). The forward pass is

    h = W0 x + (alpha / r) * B A x

A starts random and B starts at zero, so delta_W = 0 and the adapted model starts exactly at the base model.
"""

import math

import torch
from torch import nn


class LoRALinear(nn.Module):
    """Wraps an existing nn.Linear with a trainable low-rank update; the wrapped layer is frozen.

    Attributes (names matter - the tests read them):
      base     - the wrapped nn.Linear; every parameter has requires_grad == False
      lora_A   - nn.Parameter of shape (r, in_features), Kaiming-uniform initialised (like nn.Linear's weight)
      lora_B   - nn.Parameter of shape (out_features, r), all zeros
      scaling  - alpha / r (alpha defaults to r, so scaling defaults to 1.0)
      enabled  - when False the layer behaves exactly like base (the adapter is switched off)
    Raises ValueError unless 1 <= r <= min(in_features, out_features).
    """

    def __init__(self, base, r=4, alpha=None):
        super().__init__()
        # Draft: runs, and is wrong in more than one place. Compare it with the docstring and section 4.1.
        self.base = base
        self.r = r
        self.scaling = (r if alpha is None else alpha) / r
        self.lora_A = nn.Parameter(torch.empty(r, base.in_features, dtype=base.weight.dtype))
        self.lora_B = nn.Parameter(torch.empty(base.out_features, r, dtype=base.weight.dtype))
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        nn.init.kaiming_uniform_(self.lora_B, a=math.sqrt(5))
        self.enabled = True

    def delta_weight(self):
        """The update scaling * B @ A, shape (out_features, in_features) - the same shape as base.weight."""
        raise NotImplementedError("delta_weight")

    def forward(self, x):
        out = self.base(x)
        if self.enabled:
            out = out + (x @ self.lora_A.T @ self.lora_B.T)
        return out

    def merged(self):
        """A new, plain nn.Linear whose weight is W0 + delta_W (bias copied). base itself is not changed."""
        raise NotImplementedError("merged")


def count_parameters(model):
    """Return (trainable, total): numbers of parameter elements with and without requires_grad."""
    raise NotImplementedError("count_parameters")


def add_lora(model, targets, r=4, alpha=None):
    """Freeze every parameter of model, then replace each named nn.Linear in targets with a LoRALinear.

    targets are names as model.named_modules() reports them ("2", "encoder.q_proj", ...). The model is changed
    in place and returned. Raises KeyError for a name that does not exist and TypeError for one that is not an
    nn.Linear. Afterwards only the lora_A / lora_B parameters are trainable.
    """
    raise NotImplementedError("add_lora")
