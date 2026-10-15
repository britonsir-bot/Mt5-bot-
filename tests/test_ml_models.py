from __future__ import annotations

import numpy as np
import pytest

from test_ml_data import make_candles
from ai.features import FeatureEngineer
from ai.models import ModelWrapper, available_models, create_model


def _dataset():
    X, y = FeatureEngineer().build(make_candles(n=400), horizon=1)
    return X, y


def test_available_models_include_the_required_types():
    models = available_models()
    for required in ("random_forest", "extra_trees", "gradient_boosting", "logistic_regression"):
        assert required in models
    assert models[0] == "random_forest"


def test_create_model_rejects_an_unknown_type():
    with pytest.raises(ValueError):
        create_model("not_a_model")


def test_fit_requires_both_classes():
    X, y = _dataset()
    model = create_model("random_forest", n_estimators=10)
    with pytest.raises(ValueError):
        model.fit(X, np.zeros_like(y))


def test_predict_proba_has_two_columns():
    X, y = _dataset()
    model = create_model("random_forest", n_estimators=30).fit(X, y)
    probabilities = model.predict_proba(X[:5])

    assert probabilities.shape == (5, 2)
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert model.is_fitted


def test_untrained_model_refuses_to_predict():
    X, _ = _dataset()
    model = create_model("random_forest", n_estimators=10)
    assert not model.is_fitted
    with pytest.raises(RuntimeError):
        model.predict_proba(X[:1])


def test_same_seed_is_deterministic():
    X, y = _dataset()
    first = create_model("random_forest", seed=123, n_estimators=40).fit(X, y)
    second = create_model("random_forest", seed=123, n_estimators=40).fit(X, y)
    assert np.array_equal(first.predict_proba(X), second.predict_proba(X))


def test_save_then_load_preserves_predictions(tmp_path):
    X, y = _dataset()
    model = create_model("random_forest", seed=9, n_estimators=40).fit(X, y)
    path = model.save(tmp_path / "model.joblib")

    assert path.exists()
    restored = ModelWrapper.load(path)
    assert restored.is_fitted
    assert np.array_equal(model.predict_proba(X), restored.predict_proba(X))


def test_feature_importances_sum_to_one_and_match_feature_width():
    X, y = _dataset()
    names = FeatureEngineer.FEATURE_NAMES
    model = create_model("random_forest", seed=1, n_estimators=40, feature_names=names).fit(X, y)
    importances = model.feature_importances_

    assert importances.shape == (len(names),)
    assert importances.min() >= 0.0
    assert np.isclose(importances.sum(), 1.0)


def test_logistic_regression_exposes_importances():
    X, y = _dataset()
    model = create_model("logistic_regression", seed=2).fit(X, y)
    importances = model.feature_importances_
    assert importances.shape == (len(FeatureEngineer.FEATURE_NAMES),)
    assert np.isclose(importances.sum(), 1.0)


def test_metadata_reports_configuration():
    names = FeatureEngineer.FEATURE_NAMES
    model = create_model("extra_trees", seed=5, n_estimators=10, feature_names=names).fit(*_dataset())
    metadata = model.metadata()

    assert metadata["model_type"] == "extra_trees"
    assert metadata["seed"] == 5
    assert metadata["n_features"] == len(names)
    assert metadata["is_fitted"] is True
    assert metadata["feature_names"] == list(names)
