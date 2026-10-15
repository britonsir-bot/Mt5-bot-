from __future__ import annotations

from test_ml_data import make_candles
from ai.engine import MLEngine
from ai.inference import InferenceService
from ai.predictor import MarketPredictor


def test_inference_reports_untrained_without_a_model():
    advisory = InferenceService().recommend("EURUSD")

    assert advisory["symbol"] == "EURUSD"
    assert advisory["trend"] == "untrained"
    assert advisory["trained"] is False
    assert advisory["confidence"] == 0.0


def test_inference_accepts_a_custom_predictor():
    class StubPredictor:
        def predict_trend(self, symbol):
            return {"symbol": symbol, "trend": "up", "confidence": 0.9}

    advisory = InferenceService(StubPredictor()).recommend("XAUUSD")
    assert advisory["trend"] == "up"
    assert advisory["trained"] is False


def test_inference_returns_a_real_trend_once_trained():
    candles = make_candles(n=1200, seed=6)
    engine = MLEngine(seed=6)
    engine.train(candles)

    service = InferenceService(MarketPredictor(engine=engine))
    advisory = service.recommend("EURUSD", candles=candles)

    assert advisory["trained"] is True
    assert advisory["trend"] in {"up", "down"}
    assert 0.0 <= advisory["confidence"] <= 1.0


def test_trained_predictor_without_candles_stays_untrained():
    engine = MLEngine(seed=6)
    engine.train(make_candles(n=1200, seed=6))

    advisory = MarketPredictor(engine=engine).predict_trend("EURUSD")
    assert advisory["trend"] == "untrained"
    assert advisory["trained"] is False
