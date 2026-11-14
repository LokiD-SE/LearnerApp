"""Checks exercises/deep_learning/digits_cnn.py - lesson cnns-for-computer-vision."""

import pytest
import torch
from deep_learning.digits_cnn import (
    DigitsCNN,
    ResidualBlock,
    accuracy,
    load_digit_tensors,
    make_transfer_model,
    train_model,
)
from torch import nn

pytestmark = pytest.mark.exercise


@pytest.fixture(scope="module")
def data():
    return load_digit_tensors()


@pytest.fixture(scope="module")
def trained(data):
    X_train, _, y_train, _ = data
    torch.manual_seed(0)
    model = DigitsCNN()
    history = train_model(model, X_train, y_train, epochs=6, lr=0.01, seed=0)
    return model, history


class TestDigitsCNN:
    def test_logit_shape(self):
        torch.manual_seed(0)
        assert DigitsCNN()(torch.zeros(5, 1, 8, 8)).shape == (5, 10)
        assert DigitsCNN(num_classes=3)(torch.zeros(2, 1, 8, 8)).shape == (2, 3)

    def test_feature_shape_and_parameter_count(self):
        torch.manual_seed(0)
        model = DigitsCNN()
        assert model.features(torch.zeros(4, 1, 8, 8)).shape == (4, 128)
        assert isinstance(model.classifier, nn.Linear) and model.classifier.in_features == 128
        # conv1 16*1*9+16, conv2 32*16*9+32, linear 128*10+10
        assert sum(p.numel() for p in model.parameters()) == 160 + 4640 + 1290

    def test_returns_logits_not_probabilities(self):
        torch.manual_seed(0)
        model = DigitsCNN()
        with torch.no_grad():
            nn.init.constant_(model.classifier.bias, 5.0)
            out = model(torch.rand(3, 1, 8, 8))
        assert not torch.allclose(out.sum(dim=1), torch.ones(3)), "forward must not apply softmax"


class TestResidualBlock:
    def test_keeps_shape(self):
        torch.manual_seed(0)
        assert ResidualBlock(8)(torch.randn(2, 8, 5, 5)).shape == (2, 8, 5, 5)

    def test_zero_residual_is_relu_of_input(self):
        torch.manual_seed(0)
        block = ResidualBlock(4)
        nn.init.zeros_(block.bn2.weight)  # the residual branch now outputs bn2.bias = 0
        x = torch.randn(3, 4, 6, 6)
        torch.testing.assert_close(block(x), torch.relu(x))

    def test_matches_formula(self):
        torch.manual_seed(1)
        block = ResidualBlock(3).eval()
        x = torch.randn(2, 3, 4, 4)
        inner = block.bn2(block.conv2(torch.relu(block.bn1(block.conv1(x)))))
        torch.testing.assert_close(block(x), torch.relu(inner + x))

    def test_gradient_reaches_input_through_shortcut(self):
        torch.manual_seed(0)
        block = ResidualBlock(2)
        nn.init.zeros_(block.bn2.weight)
        x = (torch.rand(1, 2, 4, 4) + 0.1).requires_grad_()
        block(x).sum().backward()
        assert torch.all(x.grad == 1.0)


class TestTraining:
    def test_loss_decreases(self, trained):
        _, history = trained
        assert len(history) == 6
        assert history[-1] < 0.25 < history[0]
        assert all(isinstance(v, float) for v in history)

    def test_accuracy_on_held_out_digits(self, trained, data):
        model, _ = trained
        _, X_test, _, y_test = data
        assert accuracy(model, X_test, y_test) > 0.93

    def test_reproducible(self, data):
        X_train, _, y_train, _ = data
        runs = []
        for _ in range(2):
            torch.manual_seed(3)
            model = DigitsCNN()
            runs.append(train_model(model, X_train[:200], y_train[:200], epochs=2, seed=5))
        assert runs[0] == pytest.approx(runs[1])


class TestAccuracy:
    def test_uses_eval_mode_and_no_grad(self, data):
        _, X_test, _, y_test = data
        torch.manual_seed(0)
        model = nn.Sequential(nn.Flatten(), nn.Dropout(0.9), nn.Linear(64, 10))
        model.train()
        first = accuracy(model, X_test, y_test)
        second = accuracy(model, X_test, y_test)
        assert first == second, "dropout was active - evaluate in eval mode"
        assert not model.training
        model.eval()
        with torch.no_grad():
            expected = float((model(X_test).argmax(1) == y_test).float().mean())
        assert first == pytest.approx(expected)

    def test_value(self):
        model = nn.Flatten()  # logits are the 3 inputs themselves
        X = torch.tensor([[[[0.0, 1.0, 0.0]]], [[[2.0, 0.0, 0.0]]], [[[0.0, 0.0, 1.0]]], [[[1.0, 0.0, 0.0]]]])
        assert accuracy(model, X, torch.tensor([1, 0, 0, 0])) == pytest.approx(0.75)


class TestTransfer:
    def test_new_head_and_original_untouched(self, trained):
        model, _ = trained
        before = {k: v.clone() for k, v in model.state_dict().items()}
        new = make_transfer_model(model, num_classes=5)
        assert new is not model
        assert new.classifier.out_features == 5 and new.classifier.in_features == 128
        assert model.classifier.out_features == 10
        assert all(p.requires_grad for p in model.parameters())
        for k, v in model.state_dict().items():
            torch.testing.assert_close(v, before[k])
        torch.testing.assert_close(new.features[0].weight, model.features[0].weight)

    def test_freeze_flags(self, trained):
        model, _ = trained
        frozen = make_transfer_model(model, 5, freeze=True)
        assert not any(p.requires_grad for p in frozen.features.parameters())
        assert all(p.requires_grad for p in frozen.classifier.parameters())
        tuned = make_transfer_model(model, 5, freeze=False)
        assert all(p.requires_grad for p in tuned.parameters())

    def test_training_frozen_model_changes_only_the_head(self, trained, data):
        model, _ = trained
        X_train, _, y_train, _ = data
        torch.manual_seed(0)
        frozen = make_transfer_model(model, 10, freeze=True)
        features_before = [p.clone() for p in frozen.features.parameters()]
        head_before = frozen.classifier.weight.clone()
        train_model(frozen, X_train[:300], y_train[:300], epochs=2, seed=0)
        for p, b in zip(frozen.features.parameters(), features_before):
            torch.testing.assert_close(p, b)
        assert not torch.allclose(frozen.classifier.weight, head_before)
