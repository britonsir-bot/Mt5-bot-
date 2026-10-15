"""Prediction helpers layered on :class:`~ai.engine.MLEngine`.

``MLPredictor`` is the feature-level gate a strategy consults before acting.
``MarketPredictor`` is the symbol-level advisory used by the desktop inference
service; it refuses to invent a trend when nothing has been trained, returning
``"untrained"`` instead of a fabricated neutral reading.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ai.engine import MLEngine
from core.models import Candle


class MLPredictor:
    """Feature-level wrapper: probability and a meta-filter decision."""

    def __init__(self, engine: MLEngine | None = None) -> None:
        self._engine = engine if engine is not None else MLEngine()

    @property
    def engine(self) -> MLEngine:
        return self._engine

    @property
    def is_ready(self) -> bool:
        return self._engine.is_ready

    def predict(self, features: dict[str, float]) -> float:
        return self._engine.predict(features)

    def should_take_trade(
        self, features: dict[str, float], min_probability: float
    ) -> tuple[bool, float]:
        """Gate a long signal on the model's positive-return probability."""
        probability = self.predict(features)
        return probability >= float(min_probability), probability


class MarketPredictor:
    """Symbol-level advisory built from the engine's latest causal feature row."""

    def __init__(
        self,
        engine: MLEngine | None = None,
        predictor: MLPredictor | None = None,
    ) -> None:
        if predictor is not None:
            self._predictor = predictor
            self._engine = predictor.engine
        else:
            self._engine = engine if engine is not None else MLEngine()
            self._predictor = MLPredictor(self._engine)

    @property
    def is_ready(self) -> bool:
        return self._engine.is_ready

    def predict_trend(
        self, symbol: str, candles: Sequence[Candle] | None = None
    ) -> dict[str, Any]:
        if not self._engine.is_ready:
            return self._untrained(symbol, "no model has been trained")
        if candles is None:
            return self._untrained(symbol, "no candles supplied for evaluation")

        features = self._engine.latest_features(candles)
        if features is None:
            return self._untrained(symbol, "not enough bars to form a feature row")

        probability = self._predictor.predict(features)
        return {
            "symbol": symbol,
            "trend": "up" if probability >= 0.5 else "down",
            "confidence": float(abs(probability - 0.5) * 2.0),
            "probability": probability,
            "trained": True,
            "model_version": self._engine.model_version,
        }

    @staticmethod
    def _untrained(symbol: str, reason: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "trend": "untrained",
            "confidence": 0.0,
            "trained": False,
            "note": f"advisory unavailable: {reason}",
        }
