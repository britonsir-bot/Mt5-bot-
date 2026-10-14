from __future__ import annotations

from ai.inference import InferenceService
from ai.trainer import ModelTrainer


def test_inference_returns_a_neutral_advisory():
    advisory = InferenceService().recommend("EURUSD")
    assert advisory["symbol"] == "EURUSD"
    assert advisory["trend"] == "neutral"
    assert 0.0 <= float(advisory["confidence"]) <= 1.0


def test_inference_accepts_a_custom_predictor():
    class StubPredictor:
        def predict_trend(self, symbol):
            return {"symbol": symbol, "trend": "up", "confidence": 0.9}

    assert InferenceService(StubPredictor()).recommend("XAUUSD")["trend"] == "up"


def test_trainer_reports_that_training_is_not_implemented(tmp_path):
    result = ModelTrainer().train(tmp_path / "dataset.csv")
    assert result["status"] == "skipped"
    assert str(tmp_path) in result["dataset"]
