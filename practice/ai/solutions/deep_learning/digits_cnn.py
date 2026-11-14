"""A small convolutional network for scikit-learn's 8x8 handwritten digits: the model, a residual block, a
training loop, honest evaluation and transfer learning by freezing the feature extractor.

Lesson: cnns-for-computer-vision. Reference solution.
The data is ``sklearn.datasets.load_digits`` (1,797 grey-scale 8x8 images, pixel values 0-16), which ships
inside scikit-learn - nothing is downloaded.
"""

import copy

import torch
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from torch import nn


def load_digit_tensors(test_size: float = 0.25, seed: int = 0):
    """Return ``X_train, X_test, y_train, y_test`` (given, already correct).

    Images are float32 tensors shaped (N, 1, 8, 8) - one channel - scaled to 0-1 by dividing by 16; labels
    are int64 tensors of digits 0-9. The split is stratified and fixed by ``seed``.
    """
    digits = load_digits()
    X = torch.tensor(digits.images, dtype=torch.float32).unsqueeze(1) / 16.0
    y = torch.tensor(digits.target, dtype=torch.long)
    idx_train, idx_test = train_test_split(
        torch.arange(len(y)).numpy(), test_size=test_size, stratify=digits.target, random_state=seed
    )
    return X[idx_train], X[idx_test], y[idx_train], y[idx_test]


class DigitsCNN(nn.Module):
    """Two convolution blocks and a linear classifier for (N, 1, 8, 8) images.

    ``self.features`` is an ``nn.Sequential`` of, in order:
        Conv2d(1, 16, 3, padding=1), ReLU, MaxPool2d(2)    -> (N, 16, 4, 4)
        Conv2d(16, 32, 3, padding=1), ReLU, MaxPool2d(2)   -> (N, 32, 2, 2)
        Flatten()                                          -> (N, 128)
    ``self.classifier`` is ``nn.Linear(128, num_classes)``. ``forward`` returns the logits (N, num_classes) -
    no softmax, because ``nn.CrossEntropyLoss`` applies log-softmax itself.
    """

    def __init__(self, num_classes: int = 10):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Flatten(),
        )
        self.classifier = nn.Linear(32 * 2 * 2, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x))


class ResidualBlock(nn.Module):
    """The basic block of ResNet (He et al., 2015), keeping the shape (N, channels, H, W).

    ``self.conv1``, ``self.bn1``, ``self.conv2``, ``self.bn2`` are Conv2d(channels, channels, 3, padding=1,
    bias=False) and BatchNorm2d(channels) layers. ``forward`` computes

        out = relu(bn2(conv2(relu(bn1(conv1(x))))) + x)

    - the stacked layers learn a residual F(x) and the identity shortcut adds x back before the last ReLU.
    """

    def __init__(self, channels: int):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = torch.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return torch.relu(out + x)


def train_model(
    model: nn.Module,
    X: torch.Tensor,
    y: torch.Tensor,
    epochs: int = 10,
    lr: float = 0.01,
    batch_size: int = 64,
    seed: int = 0,
) -> list[float]:
    """Train ``model`` with Adam and cross-entropy on mini-batches; return the mean loss of each epoch.

    Put the model in training mode, seed ``torch.manual_seed(seed)`` so the shuffling is reproducible, and
    each epoch visit every row once in a new random order (``torch.randperm``). Give the optimiser only the
    parameters that require gradients, so frozen layers stay frozen. The epoch loss is the average of the
    batch losses weighted by batch size.
    """
    torch.manual_seed(seed)
    model.train()
    params = [p for p in model.parameters() if p.requires_grad]
    optimiser = torch.optim.Adam(params, lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    history = []
    for _ in range(epochs):
        order = torch.randperm(len(y))
        total = 0.0
        for start in range(0, len(y), batch_size):
            idx = order[start : start + batch_size]
            optimiser.zero_grad()
            loss = loss_fn(model(X[idx]), y[idx])
            loss.backward()
            optimiser.step()
            total += loss.item() * len(idx)
        history.append(total / len(y))
    return history


def accuracy(model: nn.Module, X: torch.Tensor, y: torch.Tensor) -> float:
    """Return the fraction of rows whose highest logit is the true label.

    Evaluate the way the model will be used: in evaluation mode (``model.eval()`` - dropout off, batch
    normalisation uses its running statistics) and without building a graph (``torch.no_grad()``).
    """
    model.eval()
    with torch.no_grad():
        predictions = model(X).argmax(dim=1)
    return float((predictions == y).float().mean())


def make_transfer_model(pretrained: DigitsCNN, num_classes: int, freeze: bool = True) -> DigitsCNN:
    """Return a new model that reuses ``pretrained``'s feature extractor for a new task.

    Deep-copy ``pretrained`` (the original must not change), replace the copy's ``classifier`` with a fresh
    ``nn.Linear`` with ``num_classes`` outputs, and when ``freeze`` is True set ``requires_grad = False`` on
    every parameter of the copy's ``features``. With ``freeze=False`` every parameter stays trainable
    (fine-tuning).
    """
    model = copy.deepcopy(pretrained)
    model.classifier = nn.Linear(model.classifier.in_features, num_classes)
    if freeze:
        for param in model.features.parameters():
            param.requires_grad = False
    return model
