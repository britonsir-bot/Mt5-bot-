from __future__ import annotations

import copy

import numpy as np

from test_ml_data import make_candles
from ai.features import FeatureEngineer
from core.models import Candle


def test_feature_names_are_declared_and_unique():
    names = FeatureEngineer.FEATURE_NAMES
    assert isinstance(names, tuple)
    assert len(names) == len(set(names))
    assert names


def test_build_returns_row_aligned_finite_arrays():
    engineer = FeatureEngineer()
    candles = make_candles(n=400)
    X, y, indices = engineer.build_with_indices(candles, horizon=1)

    assert X.shape[1] == len(FeatureEngineer.FEATURE_NAMES)
    assert X.shape[0] == y.shape[0] == indices.shape[0]
    assert np.isfinite(X).all()
    assert set(np.unique(y)).issubset({0, 1})
    assert np.all(np.diff(indices) > 0)
    assert indices[-1] <= len(candles) - 2


def test_labels_are_exactly_the_forward_direction():
    engineer = FeatureEngineer()
    candles = make_candles(n=300)
    close = np.array([candle.close for candle in candles])

    for horizon in (1, 3):
        _, y, indices = engineer.build_with_indices(candles, horizon=horizon)
        expected = np.array(
            [int(close[bar + horizon] > close[bar]) for bar in indices]
        )
        assert np.array_equal(y, expected)


def test_features_are_unchanged_by_mutating_a_future_bar():
    engineer = FeatureEngineer()
    candles = make_candles(n=300)
    baseline = engineer.feature_matrix(candles)

    mutated = copy.deepcopy(candles)
    last = mutated[-1]
    mutated[-1] = Candle(
        timestamp=last.timestamp,
        open=last.open * 5.0,
        high=last.high * 5.0,
        low=last.low * 0.2,
        close=last.close * 5.0,
        volume=last.volume * 100,
    )

    changed = engineer.feature_matrix(mutated)
    assert np.array_equal(baseline[:-1], changed[:-1], equal_nan=True)


def test_features_are_unchanged_by_truncating_the_series():
    engineer = FeatureEngineer()
    candles = make_candles(n=300)
    keep = 200

    full = engineer.feature_matrix(candles)
    truncated = engineer.feature_matrix(candles[:keep])
    assert np.array_equal(full[: keep - 1], truncated[: keep - 1], equal_nan=True)


def test_warmup_and_unlabelled_rows_are_dropped():
    engineer = FeatureEngineer()
    candles = make_candles(n=200, seed=3)
    X, y, indices = engineer.build_with_indices(candles, horizon=1)

    assert indices[0] > 0
    assert indices[-1] == len(candles) - 2
    assert X.shape[0] == len(candles) - 1 - indices[0]
    assert y.shape[0] == X.shape[0]


def test_short_series_returns_empty_aligned_arrays():
    engineer = FeatureEngineer()
    candles = make_candles(n=1)
    X, y = engineer.build(candles, horizon=1)
    assert X.shape[0] == 0
    assert y.shape[0] == 0
