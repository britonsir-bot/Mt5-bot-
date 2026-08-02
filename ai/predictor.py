from __future__ import annotations


class MarketPredictor:
    def predict_trend(self, symbol: str) -> dict[str, str | float]:
        return {
            "symbol": symbol,
            "trend": "neutral",
            "confidence": 0.5,
            "note": "AI module is advisory-only in this scaffold.",
        }
