from __future__ import annotations

import numpy as np
import pytest

from test_ml_data import make_candles
from ai.engine import MLEngine
from ai.features import FeatureEngineer
from ai.models import create_model

# Chance accuracy for the balanced two-class next-bar problem is 0.50. The
# injected AR(1) momentum signal produces roughly 0.70 validation accuracy, so a
# 0.60 floor sits far above chance while leaving headroom above sampling noise.
CHANCE = 0.50
LEARNING_FLOOR = 0.60
SHUFFLED_CEILING = 0.58


def test_pipeline_learns_the_injected_signal():
    engine = MLEngine(model_type="random_forest", horizon=1, validation_fraction=0.25, seed=7)
    metrics = engine.train(make_candles(n=1500, seed=7))

    assert metrics["accuracy"] > LEARNING_FLOOR, metrics["accuracy"]
    assert metrics["roc_auc"] > LEARNING_FLOOR, metrics["roc_auc"]
    assert metrics["accuracy"] > CHANCE
    assert engine.is_ready


def test_split_is_chronological():
    candles = make_candles(n=1200, seed=5)
    _, _, indices = FeatureEngineer().build_with_indices(candles, horizon=1)

    engine = MLEngine(validation_fraction=0.25, seed=5)
    metrics = engine.train(candles)

    split = metrics["split_index"]
    assert split == int(metrics["n_samples"] * 0.75)
    assert metrics["train_size"] + metrics["validation_size"] == metrics["n_samples"]
    assert indices[:split].max() < indices[split:].min()


def test_shuffled_labels_do_not_generalise():
    X, y = FeatureEngineer().build(make_candles(n=1200, seed=8), horizon=1)
    split = int(len(y) * 0.75)

    rng = np.random.default_rng(0)
    shuffled = rng.permutation(y)
    model = create_model("random_forest", seed=8, n_estimators=200).fit(
        X[:split], shuffled[:split]
    )
    predictions = (model.predict_proba(X[split:])[:, 1] >= 0.5).astype(int)
    accuracy = float((predictions == y[split:]).mean())

    assert accuracy < SHUFFLED_CEILING, accuracy


def test_same_seed_produces_identical_metrics():
    candles = make_candles(n=1000, seed=13)
    first = MLEngine(model_type="random_forest", seed=13).train(candles)
    second = MLEngine(model_type="random_forest", seed=13).train(candles)

    for key in ("accuracy", "precision", "recall", "f1", "roc_auc", "split_index"):
        assert first[key] == second[key], key


def test_warmup_rows_are_dropped_and_sizes_add_up():
    candles = make_candles(n=800, seed=2)
    _, _, indices = FeatureEngineer().build_with_indices(candles, horizon=1)

    metrics = MLEngine(seed=2).train(candles)
    assert metrics["n_samples"] == len(indices)
    assert metrics["train_size"] + metrics["validation_size"] == len(indices)
    assert metrics["n_features"] == len(FeatureEngineer.FEATURE_NAMES)


def test_feature_importances_cover_every_declared_feature():
    engine = MLEngine(seed=3)
    engine.train(make_candles(n=900, seed=3), model_type="extra_trees")

    importances = engine.feature_importances()
    assert set(importances) == set(FeatureEngineer.FEATURE_NAMES)
    assert np.isclose(sum(importances.values()), 1.0)
    assert all(value >= 0.0 for value in importances.values())


def test_walk_forward_reports_out_of_sample_folds():
    engine = MLEngine(seed=4)
    result = engine.walk_forward(make_candles(n=1500, seed=4), n_folds=4)

    assert result["n_folds"] >= 2
    assert result["mean_accuracy"] > LEARNING_FLOOR
    assert all(fold["train_size"] < fold["train_size"] + fold["validation_size"] for fold in result["folds"])
    training_sizes = [fold["train_size"] for fold in result["folds"]]
    assert training_sizes == sorted(training_sizes)


def test_untrained_engine_reports_and_refuses():
    engine = MLEngine()
    assert not engine.is_ready
    assert engine.model_version == "untrained"
    with pytest.raises(RuntimeError):
        engine.predict({name: 0.0 for name in FeatureEngineer.FEATURE_NAMES})
    with pytest.raises(RuntimeError):
        engine.feature_importances()


def test_predict_uses_the_latest_feature_row():
    candles = make_candles(n=1200, seed=6)
    engine = MLEngine(seed=6)
    engine.train(candles)

    features = engine.latest_features(candles)
    assert features is not None
    probability = engine.predict(features)
    assert 0.0 <= probability <= 1.0

    with pytest.raises(KeyError):
        engine.predict({})


def test_save_then_load_keeps_predictions(tmp_path):
    candles = make_candles(n=1000, seed=9)
    engine = MLEngine(seed=9)
    engine.train(candles)
    engine.save(tmp_path)

    features = engine.latest_features(candles)
    assert features is not None
    expected = engine.predict(features)

    restored = MLEngine(seed=999)
    assert restored.load(tmp_path) is True
    assert restored.is_ready
    assert restored.predict(features) == expected


def test_load_returns_false_when_no_model_present(tmp_path):
    assert MLEngine().load(tmp_path) is False


def test_train_rejects_too_few_samples():
    with pytest.raises(ValueError):
        MLEngine().train(make_candles(n=40))
