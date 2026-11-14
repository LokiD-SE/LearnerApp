"""Checks exercises/deep_learning/rnn.py - lesson sequence-models-and-embeddings."""

import pytest
import torch
from deep_learning.rnn import LSTMClassifier, input_gradient_norms, rnn_forward, train_classifier
from torch import nn

pytestmark = pytest.mark.exercise


def padded(seqs, pad_id=0):
    lengths = torch.tensor([len(s) for s in seqs])
    ids = torch.full((len(seqs), int(lengths.max())), pad_id, dtype=torch.long)
    for i, s in enumerate(seqs):
        ids[i, : len(s)] = torch.tensor(s)
    return ids, lengths


def first_token_task(n, seed, lo=5, hi=12):
    """Synthetic sequences of ids 2..19; the label is 1 when the FIRST id is below 11 - it must be remembered."""
    g = torch.Generator().manual_seed(seed)
    seqs, labels = [], []
    for _ in range(n):
        length = int(torch.randint(lo, hi + 1, (1,), generator=g))
        s = torch.randint(2, 20, (length,), generator=g).tolist()
        seqs.append(s)
        labels.append(int(s[0] < 11))
    ids, lengths = padded(seqs)
    return ids, lengths, torch.tensor(labels)


class TestRnnForward:
    def make(self):
        torch.manual_seed(0)
        rnn = nn.RNN(3, 4, dtype=torch.float64)
        x = torch.randn(6, 2, 3, dtype=torch.float64)
        h0 = torch.randn(2, 4, dtype=torch.float64)
        return rnn, x, h0

    def test_matches_nn_rnn(self):
        rnn, x, h0 = self.make()
        out, h_n = rnn_forward(x, h0, rnn.weight_ih_l0, rnn.weight_hh_l0, rnn.bias_ih_l0, rnn.bias_hh_l0)
        ref_out, ref_h = rnn(x, h0.unsqueeze(0))
        assert out.shape == (6, 2, 4) and h_n.shape == (2, 4)
        torch.testing.assert_close(out, ref_out)
        torch.testing.assert_close(h_n, ref_h[0])

    def test_last_output_is_the_final_state(self):
        rnn, x, h0 = self.make()
        out, h_n = rnn_forward(x, h0, rnn.weight_ih_l0, rnn.weight_hh_l0, rnn.bias_ih_l0, rnn.bias_hh_l0)
        torch.testing.assert_close(out[-1], h_n)

    def test_gradients_match_nn_rnn(self):
        rnn, x, h0 = self.make()
        out, _ = rnn_forward(x, h0, rnn.weight_ih_l0, rnn.weight_hh_l0, rnn.bias_ih_l0, rnn.bias_hh_l0)
        (mine,) = torch.autograd.grad(out.sum(), rnn.weight_hh_l0)
        ref_out, _ = rnn(x, h0.unsqueeze(0))
        (ref,) = torch.autograd.grad(ref_out.sum(), rnn.weight_hh_l0)
        torch.testing.assert_close(mine, ref)


class TestInputGradientNorms:
    def test_matches_autograd_by_hand(self):
        torch.manual_seed(1)
        rnn = nn.RNN(3, 5, dtype=torch.float64)
        x = torch.randn(7, 2, 3, dtype=torch.float64)
        norms = input_gradient_norms(rnn, x)
        xr = x.clone().requires_grad_(True)
        _, h_n = rnn(xr)
        h_n[-1].sum().backward()
        expected = torch.stack([xr.grad[t].norm() for t in range(7)])
        assert norms.shape == (7,)
        torch.testing.assert_close(norms, expected)

    def test_leaves_the_input_alone(self):
        rnn = nn.RNN(3, 5)
        x = torch.randn(4, 1, 3)
        before = x.clone()
        input_gradient_norms(rnn, x)
        assert not x.requires_grad and x.grad is None
        torch.testing.assert_close(x, before)

    def test_works_for_an_lstm(self):
        torch.manual_seed(2)
        lstm = nn.LSTM(3, 5, dtype=torch.float64)
        x = torch.randn(5, 2, 3, dtype=torch.float64)
        xr = x.clone().requires_grad_(True)
        _, (h_n, _) = lstm(xr)
        h_n[-1].sum().backward()
        expected = xr.grad.flatten(start_dim=1).norm(dim=1)
        torch.testing.assert_close(input_gradient_norms(lstm, x), expected)

    def test_small_recurrent_weights_make_early_gradients_vanish(self):
        torch.manual_seed(3)
        rnn = nn.RNN(4, 8)
        with torch.no_grad():
            rnn.weight_hh_l0.mul_(0.1)
        norms = input_gradient_norms(rnn, torch.randn(20, 1, 4))
        assert norms[-1] > 0
        assert norms[0] < 1e-6 * norms[-1]


class TestLSTMClassifier:
    def test_output_shape(self):
        torch.manual_seed(0)
        model = LSTMClassifier(vocab_size=20, embed_dim=8, hidden_size=16, num_classes=3)
        ids, lengths = padded([[4, 5, 6], [7, 8]])
        assert model(ids, lengths).shape == (2, 3)

    def test_padding_vector_is_zero(self):
        torch.manual_seed(0)
        model = LSTMClassifier(vocab_size=20, embed_dim=8, hidden_size=16, num_classes=2, pad_id=0)
        found = [m for m in model.modules() if isinstance(m, nn.Embedding)]
        assert len(found) == 1 and found[0].padding_idx == 0
        torch.testing.assert_close(found[0].weight[0], torch.zeros(8))

    def test_prediction_ignores_padding(self):
        torch.manual_seed(0)
        model = LSTMClassifier(vocab_size=20, embed_dim=8, hidden_size=16, num_classes=2).eval()
        short = [4, 9, 13]
        with torch.no_grad():
            alone = model(*padded([short]))
            with_long_partner = model(*padded([short, list(range(2, 17))]))
        torch.testing.assert_close(with_long_partner[0], alone[0])

    def test_learns_a_task_that_needs_memory(self):
        torch.manual_seed(0)
        ids, lengths, labels = first_token_task(128, seed=1)
        model = LSTMClassifier(vocab_size=20, embed_dim=8, hidden_size=16, num_classes=2)
        losses = train_classifier(model, ids, lengths, labels, epochs=50, lr=0.02)
        assert losses[-1] < 0.1 < losses[0]
        test_ids, test_lengths, test_labels = first_token_task(256, seed=2)
        model.eval()
        with torch.no_grad():
            accuracy = (model(test_ids, test_lengths).argmax(dim=1) == test_labels).float().mean().item()
        assert accuracy > 0.75
