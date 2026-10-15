"""Training and evaluation engine for the advisory direction model.

The engine owns the train/validation protocol. Two rules are non-negotiable and
are why this module exists rather than calling scikit-learn directly:

* The split is chronological. Financial bars are not exchangeable, so a random
  split would let the validation set contain bars that precede training bars and
  would report an accuracy the model could never achieve live.
* Warm-up and unlabelled rows are removed before splitting, and the split index
  is reported, so a validation score can always be traced back to the exact bar
  range it was measured on.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from ai.features import FeatureEngineer
from ai.models import DEFAULT_SEED, ModelWrapper, create_model
from core.models import Candle

MODEL_FILENAME = "advisory_model.joblib"
MIN_SAMPLES = 60


class MLEngine:
    """Trains, evaluates and persists the advisory classifier."""

    def __init__(
        self,
        model_type: str = "random_forest",
        *,
        horizon: int = 1,
        validation_fraction: float = 0.25,
        seed: int = DEFAULT_SEED,
        model_dir: str | Path | None = None,
        feature_engineer: FeatureEngineer | None = None,
    ) -> None:
        if not 0.0 < validation_fraction < 1.0:
            raise ValueError("validation_fraction must be in (0, 1)")
        self._model_type = model_type
        self._horizon = int(horizon)
        self._validation_fraction = float(validation_fraction)
        self._seed = seed
        self._model_dir = Path(model_dir) if model_dir is not None else None
        self._feature_engineer = feature_engineer or FeatureEngineer()
        self._model: ModelWrapper | None = None
        self._train_count = 0

    @property
    def feature_engineer(self) -> FeatureEngineer:
        return self._feature_engineer

    @property
    def is_ready(self) -> bool:
        return self._model is not None and self._model.is_fitted

    @property
    def model_version(self) -> str:
        if not self.is_ready:
            return "untrained"
        return f"{self._model_type}-h{self._horizon}-s{self._seed}-v{self._train_count}"

    def feature_importances(self) -> dict[str, float]:
        if not self.is_ready:
            raise RuntimeError("model is not trained")
        values = self._model.feature_importances_
        return {
            name: float(value)
            for name, value in zip(self._feature_engineer.FEATURE_NAMES, values)
        }

    def train(
        self,
        candles: Sequence[Candle],
        model_type: str | None = None,
        horizon: int | None = None,
        validation_fraction: float | None = None,
    ) -> dict[str, Any]:
        """Fit on the past and score on the future; never the other way round."""
        model_type = model_type or self._model_type
        horizon = self._horizon if horizon is None else int(horizon)
        fraction = (
            self._validation_fraction
            if validation_fraction is None
            else float(validation_fraction)
        )
        if not 0.0 < fraction < 1.0:
            raise ValueError("validation_fraction must be in (0, 1)")

        X, y, _ = self._feature_engineer.build_with_indices(candles, horizon)
        n_samples = int(X.shape[0])
        if n_samples < MIN_SAMPLES:
            raise ValueError(
                f"need at least {MIN_SAMPLES} usable samples, got {n_samples}"
            )

        split_index = int(n_samples * (1.0 - fraction))
        if split_index <= 0 or split_index >= n_samples:
            raise ValueError("validation_fraction leaves an empty train or validation set")

        X_train, y_train = X[:split_index], y[:split_index]
        X_validation, y_validation = X[split_index:], y[split_index:]

        model = create_model(
            model_type,
            seed=self._seed,
            feature_names=self._feature_engineer.FEATURE_NAMES,
        )
        model.fit(X_train, y_train)

        metrics = _evaluate(model, X_validation, y_validation)
        self._model = model
        self._model_type = model_type
        self._horizon = horizon
        self._train_count += 1

        if self._model_dir is not None:
            self.save(self._model_dir)

        importances = {
            name: float(value)
            for name, value in zip(
                self._feature_engineer.FEATURE_NAMES, model.feature_importances_
            )
        }
        return {
            "model_type": model_type,
            "horizon": horizon,
            "n_samples": n_samples,
            "n_features": int(X.shape[1]),
            "train_size": int(split_index),
            "validation_size": int(n_samples - split_index),
            "split_index": int(split_index),
            "accuracy": metrics["accuracy"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "roc_auc": metrics["roc_auc"],
            "feature_importances": importances,
            "model_version": self.model_version,
        }

    def walk_forward(
        self,
        candles: Sequence[Candle],
        n_folds: int = 5,
        model_type: str | None = None,
        horizon: int | None = None,
    ) -> dict[str, Any]:
        """Anchored expanding-window validation.

        The sample series is cut into ``n_folds + 1`` contiguous blocks. Fold
        ``k`` trains on blocks ``0..k-1`` and validates on block ``k``, so the
        training window only ever grows and every validation bar sits strictly
        after the data used to fit its model.
        """
        if n_folds < 1:
            raise ValueError("n_folds must be at least 1")
        model_type = model_type or self._model_type
        horizon = self._horizon if horizon is None else int(horizon)

        X, y, _ = self._feature_engineer.build_with_indices(candles, horizon)
        n_samples = int(X.shape[0])
        boundary_count = n_folds + 1
        if n_samples < boundary_count * 2:
            raise ValueError(
                f"need at least {boundary_count * 2} usable samples for {n_folds} folds"
            )

        boundaries = np.linspace(0, n_samples, boundary_count).astype(int)
        folds: list[dict[str, Any]] = []
        for fold_index in range(1, boundary_count):
            train_end = int(boundaries[fold_index - 1])
            validation_end = int(boundaries[fold_index])
            if train_end <= 0 or validation_end <= train_end:
                continue
            X_train, y_train = X[:train_end], y[:train_end]
            X_validation = X[train_end:validation_end]
            y_validation = y[train_end:validation_end]
            if np.unique(y_train).size < 2 or np.unique(y_validation).size < 2:
                continue
            model = create_model(
                model_type,
                seed=self._seed,
                feature_names=self._feature_engineer.FEATURE_NAMES,
            )
            model.fit(X_train, y_train)
            metrics = _evaluate(model, X_validation, y_validation)
            folds.append(
                {
                    "fold": fold_index,
                    "train_size": int(train_end),
                    "validation_size": int(validation_end - train_end),
                    "accuracy": metrics["accuracy"],
                    "roc_auc": metrics["roc_auc"],
                }
            )

        if not folds:
            raise ValueError("no fold had enough labelled samples on both sides")

        accuracies = np.array([fold["accuracy"] for fold in folds], dtype=float)
        aucs = np.array([fold["roc_auc"] for fold in folds], dtype=float)
        return {
            "model_type": model_type,
            "horizon": horizon,
            "n_folds": len(folds),
            "folds": folds,
            "mean_accuracy": float(np.nanmean(accuracies)),
            "mean_roc_auc": float(np.nanmean(aucs)),
        }

    def predict(self, features: dict[str, float]) -> float:
        """Return ``P(next return is positive)`` for one feature row."""
        if not self.is_ready:
            raise RuntimeError("model is not trained")
        missing = [
            name
            for name in self._feature_engineer.FEATURE_NAMES
            if name not in features
        ]
        if missing:
            raise KeyError(f"missing feature values: {missing}")
        vector = np.array(
            [float(features[name]) for name in self._feature_engineer.FEATURE_NAMES],
            dtype=float,
        ).reshape(1, -1)
        return float(self._model.predict_proba(vector)[0, 1])

    def latest_features(self, candles: Sequence[Candle]) -> dict[str, float] | None:
        """Return the most recent fully-formed feature row, or ``None``."""
        matrix = self._feature_engineer.feature_matrix(candles)
        for index in range(matrix.shape[0] - 1, -1, -1):
            row = matrix[index]
            if np.isfinite(row).all():
                return {
                    name: float(value)
                    for name, value in zip(self._feature_engineer.FEATURE_NAMES, row)
                }
        return None

    def save(self, directory: str | Path) -> Path:
        if not self.is_ready:
            raise RuntimeError("cannot save an untrained model")
        target_dir = Path(directory)
        target_dir.mkdir(parents=True, exist_ok=True)
        assert self._model is not None
        return self._model.save(target_dir / MODEL_FILENAME)

    def load(self, directory: str | Path) -> bool:
        """Load a persisted model; return ``False`` when none is present."""
        path = Path(directory) / MODEL_FILENAME
        if not path.exists():
            return False
        self._model = ModelWrapper.load(path)
        self._model_type = self._model.model_type
        self._seed = self._model.seed
        self._train_count = max(self._train_count, 1)
        return True


def _evaluate(model: ModelWrapper, X: np.ndarray, y: np.ndarray) -> dict[str, float]:
    positive_probability = model.predict_proba(X)[:, 1]
    predictions = (positive_probability >= 0.5).astype(int)
    metrics = {
        "accuracy": float(accuracy_score(y, predictions)),
        "precision": float(precision_score(y, predictions, zero_division=0)),
        "recall": float(recall_score(y, predictions, zero_division=0)),
        "f1": float(f1_score(y, predictions, zero_division=0)),
    }
    try:
        metrics["roc_auc"] = float(roc_auc_score(y, positive_probability))
    except ValueError:
        metrics["roc_auc"] = float("nan")
    return metrics
