from __future__ import annotations

from ai.predictor import MarketPredictor


class InferenceService:
    def __init__(self, predictor: MarketPredictor | None = None) -> None:
        self._predictor = predictor or MarketPredictor()

    def recommend(self, symbol: str) -> dict[str, str | float]:
        return self._predictor.predict_trend(symbol)
