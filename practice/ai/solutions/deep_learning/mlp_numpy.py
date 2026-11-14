"""A two-layer neural network in plain NumPy, with backpropagation by hand - reference solution.

Lesson: Neural networks and backpropagation (#/lesson/neural-networks-and-backprop).

The network is a binary classifier:

    Z1 = X @ W1 + b1          (n, h)   hidden pre-activations
    H  = act(Z1)              (n, h)   hidden activations ("tanh" or "relu")
    s  = H @ W2 + b2          (n, 1) -> returned as logits of shape (n,)
    loss = mean binary cross-entropy of sigmoid(s) against y in {0, 1}

Parameters live in a dict: W1 (d, h), b1 (h,), W2 (h, 1), b2 (1,). Every gradient has the same shape as its
parameter. Nothing here changes the caller's arrays in place unless the docstring says so.
"""

import numpy as np

PARAM_NAMES = ("W1", "b1", "W2", "b2")


def _act(z: np.ndarray, activation: str) -> np.ndarray:
    """Given: the hidden activation."""
    if activation == "tanh":
        return np.tanh(z)
    if activation == "relu":
        return np.maximum(0.0, z)
    raise ValueError(f"unknown activation {activation!r}; use 'tanh' or 'relu'")


def _act_grad(z: np.ndarray, activation: str) -> np.ndarray:
    """Given: the derivative of the hidden activation at z (ReLU uses 0 at exactly 0)."""
    if activation == "tanh":
        t = np.tanh(z)
        return 1.0 - t * t
    if activation == "relu":
        return (z > 0).astype(float)
    raise ValueError(f"unknown activation {activation!r}; use 'tanh' or 'relu'")


def _sigmoid(s: np.ndarray) -> np.ndarray:
    """Given: a numerically stable sigmoid."""
    out = np.empty_like(s, dtype=float)
    pos = s >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-s[pos]))
    e = np.exp(s[~pos])
    out[~pos] = e / (1.0 + e)
    return out


def init_params(n_inputs: int, n_hidden: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """Given: small random weights scaled by 1/sqrt(fan-in), zero biases."""
    return {
        "W1": rng.normal(0.0, 1.0 / np.sqrt(n_inputs), size=(n_inputs, n_hidden)),
        "b1": np.zeros(n_hidden),
        "W2": rng.normal(0.0, 1.0 / np.sqrt(n_hidden), size=(n_hidden, 1)),
        "b2": np.zeros(1),
    }


def forward(
    params: dict[str, np.ndarray], X: np.ndarray, activation: str = "tanh"
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Run the forward pass. Return (logits, cache).

    logits has shape (n,). cache is a dict with the arrays backward() needs: "X" (n, d), "Z1" (n, h) and
    "H" (n, h). Raise ValueError if X is not 2-D or its column count doesn't match W1.
    """
    X = np.asarray(X, dtype=float)
    W1 = params["W1"]
    if X.ndim != 2 or X.shape[1] != W1.shape[0]:
        raise ValueError(f"X must be (n, {W1.shape[0]}), got {X.shape}")
    Z1 = X @ W1 + params["b1"]
    H = _act(Z1, activation)
    logits = (H @ params["W2"] + params["b2"]).reshape(-1)
    return logits, {"X": X, "Z1": Z1, "H": H}


def bce_with_logits(logits: np.ndarray, y: np.ndarray) -> float:
    """Return the mean binary cross-entropy of sigmoid(logits) against y, computed from the logits.

    Use the stable form max(s, 0) - s * y + log(1 + exp(-|s|)) so that a logit of 1000 gives a finite loss and
    no warning.
    """
    s = np.asarray(logits, dtype=float)
    y = np.asarray(y, dtype=float)
    return float(np.mean(np.maximum(s, 0.0) - s * y + np.log1p(np.exp(-np.abs(s)))))


def backward(
    params: dict[str, np.ndarray],
    cache: dict[str, np.ndarray],
    logits: np.ndarray,
    y: np.ndarray,
    activation: str = "tanh",
) -> dict[str, np.ndarray]:
    """Return the gradient of bce_with_logits(logits, y) with respect to every parameter.

    The result has the keys W1, b1, W2, b2, each with the same shape as the parameter. Work backwards with the
    chain rule: d loss / d logits = (sigmoid(logits) - y) / n, then through the output layer, the activation
    and the hidden layer.
    """
    X, Z1, H = cache["X"], cache["Z1"], cache["H"]
    y = np.asarray(y, dtype=float)
    n = X.shape[0]
    d_logits = ((_sigmoid(logits) - y) / n).reshape(-1, 1)  # (n, 1)
    dW2 = H.T @ d_logits  # (h, 1)
    db2 = d_logits.sum(axis=0)  # (1,)
    dH = d_logits @ params["W2"].T  # (n, h)
    dZ1 = dH * _act_grad(Z1, activation)  # (n, h)
    dW1 = X.T @ dZ1  # (d, h)
    db1 = dZ1.sum(axis=0)  # (h,)
    return {"W1": dW1, "b1": db1, "W2": dW2, "b2": db2}


def numerical_gradients(
    params: dict[str, np.ndarray],
    X: np.ndarray,
    y: np.ndarray,
    activation: str = "tanh",
    eps: float = 1e-5,
) -> dict[str, np.ndarray]:
    """Estimate every gradient with centred differences: (L(p + eps/2) - L(p - eps/2)) / eps per entry.

    Work on copies - the caller's params must be unchanged afterwards. Slow (two forward passes per
    parameter), so only for checking backward() on small networks.
    """
    work = {k: np.array(v, dtype=float, copy=True) for k, v in params.items()}
    grads = {}
    for name in PARAM_NAMES:
        p = work[name]
        g = np.zeros_like(p)
        for idx in np.ndindex(p.shape):
            old = p[idx]
            p[idx] = old + eps / 2
            plus = bce_with_logits(forward(work, X, activation)[0], y)
            p[idx] = old - eps / 2
            minus = bce_with_logits(forward(work, X, activation)[0], y)
            p[idx] = old
            g[idx] = (plus - minus) / eps
        grads[name] = g
    return grads


def max_relative_error(a: dict[str, np.ndarray], b: dict[str, np.ndarray]) -> float:
    """Given: the largest |a - b| / max(|a| + |b|, 1e-12) over every entry of every parameter."""
    worst = 0.0
    for name in PARAM_NAMES:
        num = np.abs(a[name] - b[name])
        den = np.maximum(np.abs(a[name]) + np.abs(b[name]), 1e-12)
        worst = max(worst, float(np.max(num / den)))
    return worst


def train_step(
    params: dict[str, np.ndarray],
    X: np.ndarray,
    y: np.ndarray,
    learning_rate: float,
    activation: str = "tanh",
) -> tuple[dict[str, np.ndarray], float]:
    """Do one step of full-batch gradient descent. Return (new_params, loss before the step).

    new_params is a new dict of new arrays: params - learning_rate * gradient. Don't modify params.
    """
    logits, cache = forward(params, X, activation)
    loss = bce_with_logits(logits, y)
    grads = backward(params, cache, logits, y, activation)
    new_params = {name: params[name] - learning_rate * grads[name] for name in PARAM_NAMES}
    return new_params, loss


def fit(
    X: np.ndarray,
    y: np.ndarray,
    n_hidden: int,
    learning_rate: float = 0.5,
    epochs: int = 2000,
    seed: int = 0,
    activation: str = "tanh",
) -> tuple[dict[str, np.ndarray], list[float]]:
    """Given: train from init_params with train_step. Return (params, the loss before every step)."""
    X = np.asarray(X, dtype=float)
    params = init_params(X.shape[1], n_hidden, np.random.default_rng(seed))
    losses = []
    for _ in range(epochs):
        params, loss = train_step(params, X, y, learning_rate, activation)
        losses.append(loss)
    return params, losses


def predict(params: dict[str, np.ndarray], X: np.ndarray, activation: str = "tanh") -> np.ndarray:
    """Given: class 1 where the logit is positive (probability above 0.5), else 0."""
    logits, _ = forward(params, X, activation)
    return (logits > 0).astype(int)
