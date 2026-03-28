from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import autoresearch_trading.loop as loop_module
from autoresearch_trading.evaluator import AggregateMetrics, AutoresearchEvaluation
from autoresearch_trading.loop import run_autoresearch_loop
from tradeflow_bot.config import Settings
from tradeflow_bot.strategy import StrategyParams


def _bars(seed: int, slope: float = 0.25, periods: int = 300) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=periods, freq="1h", tz="UTC")
    rng = np.random.default_rng(seed)
    close = 100 + np.linspace(0, slope * periods, periods) + rng.normal(0, 0.2, periods).cumsum()
    close = pd.Series(close, index=index)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 10_000,
        }
    )


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        symbols=["AAPL", "LMT"],
        interval="1h",
        history_days=365,
        momentum_window=20,
        mean_reversion_window=30,
        volatility_window=20,
        momentum_threshold=0.015,
        zscore_threshold=0.75,
        transaction_cost_bps=0.0,
        report_dir=tmp_path / "reports",
        strategy_doc_path=tmp_path / "Strategy.md",
    )


def test_run_autoresearch_loop_persists_winner_and_experiment_log(tmp_path: Path):
    settings = _settings(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text("MOMENTUM_THRESHOLD=0.015\nZSCORE_THRESHOLD=0.75\n", encoding="utf-8")

    frames = {
        "AAPL": _bars(seed=1, slope=0.30),
        "LMT": _bars(seed=2, slope=0.22),
    }

    def frame_provider():
        return frames

    result = run_autoresearch_loop(
        settings=settings,
        frame_provider=frame_provider,
        env_file=env_file,
        duration_hours=0.0001,
        candidates_per_iteration=4,
        max_iterations=2,
        sleep_seconds=0.0,
        auto_promote=False,
    )

    assert result.iterations >= 1
    assert result.candidates_evaluated >= 4
    assert result.best_artifact_path.exists()
    assert result.experiment_log_path.exists()

    winner = json.loads(result.best_artifact_path.read_text(encoding="utf-8"))
    assert "candidate_holdout" in winner
    assert len(result.experiment_log_path.read_text(encoding="utf-8").splitlines()) >= 1


def test_run_autoresearch_loop_auto_promotes_promotable_winner(tmp_path: Path, monkeypatch):
    settings = _settings(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text("MOMENTUM_THRESHOLD=0.5\nZSCORE_THRESHOLD=2.0\n", encoding="utf-8")
    settings.momentum_threshold = 0.5
    settings.zscore_threshold = 2.0

    frames = {
        "AAPL": _bars(seed=1, slope=0.30),
        "LMT": _bars(seed=2, slope=0.22),
    }

    candidate = StrategyParams(
        momentum_window=20,
        mean_reversion_window=30,
        volatility_window=20,
        momentum_threshold=0.01,
        zscore_threshold=1.0,
        momentum_signal_weight=0.8,
        mean_reversion_signal_weight=0.2,
    )

    monkeypatch.setattr(loop_module, "generate_candidate_params", lambda settings, limit=12: [candidate])

    def fake_eval(self, frames, baseline, candidate, interval, transaction_cost_bps, windows=3):
        return AutoresearchEvaluation(
            baseline_train=AggregateMetrics(objective=1.0, total_return=0.0, sharpe=1.0, max_drawdown=-0.05, trades=10),
            candidate_train=AggregateMetrics(objective=1.5, total_return=0.1, sharpe=1.6, max_drawdown=-0.04, trades=12),
            baseline_holdout=AggregateMetrics(objective=1.0, total_return=0.0, sharpe=1.0, max_drawdown=-0.05, trades=10),
            candidate_holdout=AggregateMetrics(objective=1.5, total_return=0.1, sharpe=1.6, max_drawdown=-0.04, trades=12),
            promotable=True,
            symbols=["AAPL", "LMT"],
            baseline_params={"momentum_threshold": 0.5, "zscore_threshold": 2.0, "momentum_signal_weight": 0.6, "mean_reversion_signal_weight": 0.4},
            candidate_params={
                "momentum_window": 20,
                "mean_reversion_window": 30,
                "volatility_window": 20,
                "momentum_threshold": 0.01,
                "zscore_threshold": 1.0,
                "momentum_signal_weight": 0.8,
                "mean_reversion_signal_weight": 0.2,
            },
            evaluated_at="2026-03-28T00:00:00+00:00",
            window_count=3,
            windows=[],
        )

    monkeypatch.setattr(loop_module.AutoresearchEvaluator, "evaluate_walkforward_basket", fake_eval)

    result = run_autoresearch_loop(
        settings=settings,
        frame_provider=lambda: frames,
        env_file=env_file,
        duration_hours=0.0001,
        candidates_per_iteration=1,
        max_iterations=1,
        sleep_seconds=0.0,
        auto_promote=True,
    )

    assert result.promoted is True
    env_text = env_file.read_text(encoding="utf-8")
    assert "MOMENTUM_SIGNAL_WEIGHT=" in env_text
