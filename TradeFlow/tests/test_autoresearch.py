from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from tradeflow_bot.config import Settings
from tradeflow_bot.main import parse_args
from tradeflow_bot.strategy import StrategyParams

from autoresearch_trading.evaluator import (
    AggregateMetrics,
    AutoresearchEvaluator,
    append_experiment_log,
    persist_best_candidate,
    promote_best_candidate,
)


def _bars(seed: int, slope: float = 0.25, periods: int = 240) -> pd.DataFrame:
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


def test_autoresearch_evaluator_prefers_candidate_with_better_holdout():
    frames = {
        "AAPL": _bars(seed=1, slope=0.30),
        "LMT": _bars(seed=2, slope=0.22),
    }
    baseline = StrategyParams(
        momentum_window=10,
        mean_reversion_window=12,
        volatility_window=10,
        momentum_threshold=0.50,
        zscore_threshold=2.0,
    )
    candidate = StrategyParams(
        momentum_window=10,
        mean_reversion_window=12,
        volatility_window=10,
        momentum_threshold=0.01,
        zscore_threshold=1.0,
        momentum_signal_weight=0.8,
        mean_reversion_signal_weight=0.2,
    )

    evaluator = AutoresearchEvaluator(holdout_fraction=0.25, min_trades=1, max_drawdown_gap=0.10)
    result = evaluator.evaluate_basket(
        frames=frames,
        baseline=baseline,
        candidate=candidate,
        interval="1h",
        transaction_cost_bps=0.0,
    )

    assert result.promotable is True
    assert result.candidate_holdout.objective > result.baseline_holdout.objective
    assert result.candidate_holdout.trades >= 1


def test_promote_check_rejects_non_improving_candidate():
    evaluator = AutoresearchEvaluator(holdout_fraction=0.25, min_trades=2, max_drawdown_gap=0.02)
    baseline = AggregateMetrics(
        objective=1.2,
        total_return=0.10,
        sharpe=1.5,
        max_drawdown=-0.05,
        trades=4,
    )
    candidate = AggregateMetrics(
        objective=1.1,
        total_return=0.09,
        sharpe=1.4,
        max_drawdown=-0.10,
        trades=1,
    )

    assert evaluator.can_promote(baseline, candidate) is False


def test_persist_and_promote_best_candidate_updates_env_and_strategy_doc(tmp_path: Path):
    frames = {
        "AAPL": _bars(seed=3, slope=0.30),
        "LMT": _bars(seed=4, slope=0.22),
    }
    baseline = StrategyParams(
        momentum_window=10,
        mean_reversion_window=12,
        volatility_window=10,
        momentum_threshold=0.50,
        zscore_threshold=2.0,
    )
    candidate = StrategyParams(
        momentum_window=10,
        mean_reversion_window=12,
        volatility_window=10,
        momentum_threshold=0.01,
        zscore_threshold=1.0,
        momentum_signal_weight=0.8,
        mean_reversion_signal_weight=0.2,
    )
    evaluator = AutoresearchEvaluator(holdout_fraction=0.25, min_trades=1, max_drawdown_gap=0.10)
    result = evaluator.evaluate_basket(
        frames=frames,
        baseline=baseline,
        candidate=candidate,
        interval="1h",
        transaction_cost_bps=0.0,
    )

    best_path = persist_best_candidate(result, tmp_path)
    payload = json.loads(best_path.read_text(encoding="utf-8"))
    assert payload["promotable"] is True

    env_file = tmp_path / ".env"
    env_file.write_text("MOMENTUM_THRESHOLD=0.5\nZSCORE_THRESHOLD=2.0\n", encoding="utf-8")
    strategy_doc = tmp_path / "Strategy.md"
    settings = Settings(strategy_doc_path=strategy_doc)

    updated = promote_best_candidate(settings=settings, env_file=env_file, artifact_path=best_path)

    assert "MOMENTUM_THRESHOLD=0.01" in updated
    env_text = env_file.read_text(encoding="utf-8")
    assert "MOMENTUM_SIGNAL_WEIGHT=0.8" in env_text
    assert "MEAN_REVERSION_SIGNAL_WEIGHT=0.2" in env_text
    assert "Autoresearch promotion" in strategy_doc.read_text(encoding="utf-8")


def test_parse_args_accepts_autoresearch_actions(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["tradeflow_bot", "--action", "autoresearch-eval"])
    assert parse_args().action == "autoresearch-eval"

    monkeypatch.setattr(sys, "argv", ["tradeflow_bot", "--action", "autoresearch-promote"])
    assert parse_args().action == "autoresearch-promote"


def test_walkforward_eval_returns_multiple_windows():
    frames = {
        "AAPL": _bars(seed=1, slope=0.30, periods=300),
        "LMT": _bars(seed=2, slope=0.22, periods=300),
    }
    baseline = StrategyParams(
        momentum_window=10,
        mean_reversion_window=12,
        volatility_window=10,
        momentum_threshold=0.50,
        zscore_threshold=2.0,
    )
    candidate = StrategyParams(
        momentum_window=10,
        mean_reversion_window=12,
        volatility_window=10,
        momentum_threshold=0.01,
        zscore_threshold=1.0,
        momentum_signal_weight=0.8,
        mean_reversion_signal_weight=0.2,
    )

    evaluator = AutoresearchEvaluator(holdout_fraction=0.25, min_trades=1, max_drawdown_gap=0.10)
    result = evaluator.evaluate_walkforward_basket(
        frames=frames,
        baseline=baseline,
        candidate=candidate,
        interval="1h",
        transaction_cost_bps=0.0,
        windows=3,
    )

    assert len(result.windows) == 3
    assert result.window_count == 3
    assert result.candidate_holdout.trades >= 1


def test_append_experiment_log_writes_jsonl(tmp_path: Path):
    frames = {"AAPL": _bars(seed=1, slope=0.30)}
    baseline = StrategyParams(
        momentum_window=10,
        mean_reversion_window=12,
        volatility_window=10,
        momentum_threshold=0.50,
        zscore_threshold=2.0,
    )
    candidate = StrategyParams(
        momentum_window=10,
        mean_reversion_window=12,
        volatility_window=10,
        momentum_threshold=0.01,
        zscore_threshold=1.0,
        momentum_signal_weight=0.8,
        mean_reversion_signal_weight=0.2,
    )
    evaluator = AutoresearchEvaluator(holdout_fraction=0.25, min_trades=1, max_drawdown_gap=0.10)
    result = evaluator.evaluate_basket(
        frames=frames,
        baseline=baseline,
        candidate=candidate,
        interval="1h",
        transaction_cost_bps=0.0,
    )

    log_path = append_experiment_log(result, tmp_path, label="alpaca-pass-1")
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["label"] == "alpaca-pass-1"
    assert "candidate_holdout" in payload
