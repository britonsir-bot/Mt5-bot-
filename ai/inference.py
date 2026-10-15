"""Desktop-facing advisory service.

The service is intentionally thin: it forwards to a predictor that exposes
``predict_trend(symbol)``. The default predictor reports an ``"untrained"``
trend until a model has actually been fitted, so the UI can never present a
neutral reading that was never computed.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from ai.predictor import MarketPredictor
from core.models import Candle


@runtime_checkable
class TrendPredictor(Protocol):
    def predict_trend(self, symbol: str) -> dict[str, Any]: ...


class InferenceService:
    def __init__(self, predictor: TrendPredictor | None = None) -> None:
        self._predictor: TrendPredictor = (
            predictor if predictor is not None else MarketPredictor()
        )

    @property
    def predictor(self) -> TrendPredictor:
        return self._predictor

    def recommend(
        self, symbol: str, candles: Sequence[Candle] | None = None
    ) -> dict[str, Any]:
        """Return the advisory for ``symbol``.

        ``candles`` is optional so existing ``recommend(symbol)`` callers keep
        working; without it the built-in predictor reports the advisory as
        untrained rather than guessing.
        """
        if candles is not None and isinstance(self._predictor, MarketPredictor):
            advisory = dict(self._predictor.predict_trend(symbol, candles))
        else:
            advisory = dict(self._predictor.predict_trend(symbol))
        advisory.setdefault("symbol", symbol)
        advisory.setdefault("trained", False)
        return advisory
