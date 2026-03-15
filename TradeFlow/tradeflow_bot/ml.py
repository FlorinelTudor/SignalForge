from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = [
    "ret_1",
    "ret_5",
    "momentum",
    "zscore",
    "volatility",
    "hl_spread",
    "oc_spread",
]


@dataclass
class TrainResult:
    samples: int
    accuracy: float
    trained_at: datetime


class ModelManager:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self._model: Pipeline | None = None
        self.last_trained_at: datetime | None = None

    @property
    def model(self) -> Pipeline | None:
        if self._model is None and self.model_path.exists():
            payload = joblib.load(self.model_path)
            self._model = payload["model"]
            self.last_trained_at = payload.get("trained_at")
        return self._model

    def train(self, features: pd.DataFrame) -> TrainResult:
        data = features.copy()
        data["target"] = (data["close"].shift(-1) > data["close"]).astype(int)
        data = data.dropna(subset=FEATURE_COLUMNS + ["target"])
        if len(data) < 120:
            raise RuntimeError("Not enough clean data points to train model. Need at least 120 rows.")

        split_idx = int(len(data) * 0.8)
        train_df = data.iloc[:split_idx]
        test_df = data.iloc[split_idx:]

        x_train, y_train = train_df[FEATURE_COLUMNS], train_df["target"]
        x_test, y_test = test_df[FEATURE_COLUMNS], test_df["target"]

        model = Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=500, n_jobs=1)),
            ]
        )
        model.fit(x_train, y_train)

        pred = model.predict(x_test)
        acc = float(accuracy_score(y_test, pred)) if len(test_df) else np.nan

        trained_at = datetime.now(timezone.utc)
        self._model = model
        self.last_trained_at = trained_at
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": model, "trained_at": trained_at}, self.model_path)

        return TrainResult(samples=len(data), accuracy=acc, trained_at=trained_at)

    def should_retrain(self, retrain_interval_minutes: int) -> bool:
        if self.model is None or self.last_trained_at is None:
            return True
        now = datetime.now(timezone.utc)
        return now - self.last_trained_at >= timedelta(minutes=retrain_interval_minutes)

    def predict_bullish_probability(self, features: pd.DataFrame) -> pd.Series:
        model = self.model
        if model is None:
            return pd.Series(0.5, index=features.index, name="bullish_probability")

        x = features[FEATURE_COLUMNS].copy()
        x = x.ffill().bfill()
        x = x.replace([np.inf, -np.inf], np.nan).fillna(0)

        probs = model.predict_proba(x)[:, 1]
        return pd.Series(probs, index=features.index, name="bullish_probability")
