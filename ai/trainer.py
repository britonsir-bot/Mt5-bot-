from __future__ import annotations

from pathlib import Path


class ModelTrainer:
    def train(self, dataset_path: Path) -> dict[str, str]:
        return {
            "status": "skipped",
            "dataset": str(dataset_path),
            "message": "Training is not implemented in the initial scaffold.",
        }
