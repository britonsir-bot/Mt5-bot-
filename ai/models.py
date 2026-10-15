"""Scikit-learn estimator wrappers for the advisory direction model.

The wrapper exists so the rest of the advisory stack never touches an estimator
directly: fitting, probability output, feature importances, persistence and the
determinism guarantee are all enforced in one place. Every estimator is built
with a fixed ``random_state`` so two runs with the same seed produce identical
models, which is required for reproducible backtests.
"""

from __future__ import annotations

import pickle
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression

try:
    import joblib

    _HAVE_JOBLIB = True
except ImportError:  # pragma: no cover - joblib ships with scikit-learn
    _HAVE_JOBLIB = False

DEFAULT_SEED = 42

def _forest_defaults(params: dict[str, Any]) -> dict[str, Any]:
    defaults: dict[str, Any] = {"n_estimators": 300, "min_samples_leaf": 5, "n_jobs": 1}
    defaults.update(params)
    return defaults


_FACTORIES: dict[str, Callable[..., Any]] = {
    "random_forest": lambda seed, **params: RandomForestClassifier(
        random_state=seed, **_forest_defaults(params)
    ),
    "extra_trees": lambda seed, **params: ExtraTreesClassifier(
        random_state=seed, **_forest_defaults(params)
    ),
    "gradient_boosting": lambda seed, **params: GradientBoostingClassifier(
        random_state=seed, **params
    ),
    "logistic_regression": lambda seed, **params: LogisticRegression(
        max_iter=2000, random_state=seed, **params
    ),
}


def available_models() -> list[str]:
    """Return the supported model type names, ``random_forest`` first."""
    return list(_FACTORIES)


class ModelWrapper:
    """Uniform interface over the supported scikit-learn classifiers."""

    def __init__(
        self,
        estimator: Any,
        model_type: str,
        seed: int = DEFAULT_SEED,
        feature_names: Sequence[str] | None = None,
    ) -> None:
        self._estimator = estimator
        self._model_type = model_type
        self._seed = seed
        self._feature_names = tuple(feature_names) if feature_names is not None else ()
        self._fitted = False

    @property
    def model_type(self) -> str:
        return self._model_type

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def feature_names(self) -> tuple[str, ...]:
        return self._feature_names

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def fit(self, X: np.ndarray, y: np.ndarray) -> "ModelWrapper":
        features = np.asarray(X, dtype=float)
        labels = np.asarray(y).astype(int).ravel()
        if features.ndim != 2:
            raise ValueError("X must be a 2-D array")
        if features.shape[0] != labels.shape[0]:
            raise ValueError("X and y must share the same number of rows")
        if np.unique(labels).size < 2:
            raise ValueError("training requires both classes to be present")
        self._estimator.fit(features, labels)
        self._fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return an ``(n, 2)`` array of ``[P(class 0), P(class 1)]``."""
        if not self._fitted:
            raise RuntimeError("model is not fitted")
        features = np.asarray(X, dtype=float)
        if features.ndim == 1:
            features = features.reshape(1, -1)
        probabilities = self._estimator.predict_proba(features)
        classes = list(self._estimator.classes_)
        positive = probabilities[:, classes.index(1)] if 1 in classes else np.zeros(len(features))
        negative = probabilities[:, classes.index(0)] if 0 in classes else np.zeros(len(features))
        return np.column_stack([negative, positive])

    @property
    def feature_importances_(self) -> np.ndarray:
        """Non-negative importances normalised to sum to 1."""
        if not self._fitted:
            raise RuntimeError("model is not fitted")
        if hasattr(self._estimator, "feature_importances_"):
            values = np.asarray(self._estimator.feature_importances_, dtype=float)
        elif hasattr(self._estimator, "coef_"):
            values = np.abs(np.asarray(self._estimator.coef_, dtype=float)).ravel()
        else:
            raise AttributeError(f"{self._model_type} exposes no feature importances")
        total = float(values.sum())
        if total > 0.0:
            values = values / total
        return values

    def metadata(self) -> dict[str, Any]:
        n_features = len(self._feature_names)
        if self._fitted and n_features == 0:
            n_features = int(np.asarray(self._estimator.n_features_in_))
        return {
            "model_type": self._model_type,
            "seed": self._seed,
            "feature_names": list(self._feature_names),
            "n_features": n_features,
            "is_fitted": self._fitted,
        }

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if _HAVE_JOBLIB:
            joblib.dump(self, target)
        else:  # pragma: no cover - exercised only without joblib
            with target.open("wb") as handle:
                pickle.dump(self, handle)
        return target

    @classmethod
    def load(cls, path: str | Path) -> "ModelWrapper":
        source = Path(path)
        if _HAVE_JOBLIB:
            loaded = joblib.load(source)
        else:  # pragma: no cover - exercised only without joblib
            with source.open("rb") as handle:
                loaded = pickle.load(handle)
        if not isinstance(loaded, cls):
            raise TypeError(f"expected a ModelWrapper, got {type(loaded)!r}")
        return loaded


def create_model(
    model_type: str = "random_forest",
    *,
    seed: int = DEFAULT_SEED,
    feature_names: Sequence[str] | None = None,
    **params: Any,
) -> ModelWrapper:
    """Build an unfitted :class:`ModelWrapper` for the requested model type."""
    if model_type not in _FACTORIES:
        raise ValueError(
            f"unknown model type {model_type!r}; available: {sorted(_FACTORIES)}"
        )
    estimator = _FACTORIES[model_type](seed, **params)
    return ModelWrapper(estimator, model_type, seed, feature_names)
