from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tradeflow_bot.backtest import run_backtest
from tradeflow_bot.config import Settings
from tradeflow_bot.strategy import StrategyParams, engineer_features, rule_signal


@dataclass
class AggregateMetrics:
    objective: float
    total_return: float
    sharpe: float
    max_drawdown: float
    trades: int


@dataclass
class AutoresearchEvaluation:
    baseline_train: AggregateMetrics
    candidate_train: AggregateMetrics
    baseline_holdout: AggregateMetrics
    candidate_holdout: AggregateMetrics
    promotable: bool
    symbols: list[str]
    baseline_params: dict
    candidate_params: dict
    evaluated_at: str
    window_count: int = 1
    windows: list[dict] | None = None


class AutoresearchEvaluator:
    def __init__(
        self,
        holdout_fraction: float = 0.25,
        min_trades: int = 3,
        max_drawdown_gap: float = 0.05,
    ) -> None:
        self.holdout_fraction = holdout_fraction
        self.min_trades = min_trades
        self.max_drawdown_gap = max_drawdown_gap

    def evaluate_basket(
        self,
        frames: dict[str, pd.DataFrame],
        baseline: StrategyParams,
        candidate: StrategyParams,
        interval: str,
        transaction_cost_bps: float,
    ) -> AutoresearchEvaluation:
        baseline_train_scores: list[AggregateMetrics] = []
        candidate_train_scores: list[AggregateMetrics] = []
        baseline_holdout_scores: list[AggregateMetrics] = []
        candidate_holdout_scores: list[AggregateMetrics] = []

        for symbol, frame in frames.items():
            train_df, holdout_df = self._split_frame(frame)
            baseline_train_scores.append(
                self._evaluate_frame(train_df, baseline, interval, symbol, transaction_cost_bps)
            )
            candidate_train_scores.append(
                self._evaluate_frame(train_df, candidate, interval, symbol, transaction_cost_bps)
            )
            baseline_holdout_scores.append(
                self._evaluate_frame(holdout_df, baseline, interval, symbol, transaction_cost_bps)
            )
            candidate_holdout_scores.append(
                self._evaluate_frame(holdout_df, candidate, interval, symbol, transaction_cost_bps)
            )

        baseline_train = self._aggregate(baseline_train_scores)
        candidate_train = self._aggregate(candidate_train_scores)
        baseline_holdout = self._aggregate(baseline_holdout_scores)
        candidate_holdout = self._aggregate(candidate_holdout_scores)
        promotable = self.can_promote(baseline_holdout, candidate_holdout)

        return AutoresearchEvaluation(
            baseline_train=baseline_train,
            candidate_train=candidate_train,
            baseline_holdout=baseline_holdout,
            candidate_holdout=candidate_holdout,
            promotable=promotable,
            symbols=sorted(frames.keys()),
            baseline_params=asdict(baseline),
            candidate_params=asdict(candidate),
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            window_count=1,
            windows=[],
        )

    def evaluate_walkforward_basket(
        self,
        frames: dict[str, pd.DataFrame],
        baseline: StrategyParams,
        candidate: StrategyParams,
        interval: str,
        transaction_cost_bps: float,
        windows: int = 3,
    ) -> AutoresearchEvaluation:
        if windows <= 1:
            return self.evaluate_basket(
                frames=frames,
                baseline=baseline,
                candidate=candidate,
                interval=interval,
                transaction_cost_bps=transaction_cost_bps,
            )

        window_results: list[AutoresearchEvaluation] = []
        for window_idx in range(windows):
            window_frames = {
                symbol: self._window_slice(frame, windows=windows, window_idx=window_idx)
                for symbol, frame in frames.items()
            }
            window_results.append(
                self.evaluate_basket(
                    frames=window_frames,
                    baseline=baseline,
                    candidate=candidate,
                    interval=interval,
                    transaction_cost_bps=transaction_cost_bps,
                )
            )

        return AutoresearchEvaluation(
            baseline_train=self._aggregate([item.baseline_train for item in window_results]),
            candidate_train=self._aggregate([item.candidate_train for item in window_results]),
            baseline_holdout=self._aggregate([item.baseline_holdout for item in window_results]),
            candidate_holdout=self._aggregate([item.candidate_holdout for item in window_results]),
            promotable=all(item.promotable for item in window_results),
            symbols=sorted(frames.keys()),
            baseline_params=asdict(baseline),
            candidate_params=asdict(candidate),
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            window_count=windows,
            windows=[
                {
                    "window_index": idx,
                    "baseline_holdout": asdict(item.baseline_holdout),
                    "candidate_holdout": asdict(item.candidate_holdout),
                    "promotable": item.promotable,
                }
                for idx, item in enumerate(window_results)
            ],
        )

    def can_promote(self, baseline: AggregateMetrics, candidate: AggregateMetrics) -> bool:
        if candidate.objective <= baseline.objective:
            return False
        if candidate.trades < self.min_trades:
            return False
        return candidate.max_drawdown >= (baseline.max_drawdown - self.max_drawdown_gap)

    def _split_frame(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        split_idx = max(int(len(frame) * (1 - self.holdout_fraction)), 1)
        train_df = frame.iloc[:split_idx].copy()
        holdout_df = frame.iloc[split_idx:].copy()
        return train_df, holdout_df

    @staticmethod
    def _window_slice(frame: pd.DataFrame, windows: int, window_idx: int) -> pd.DataFrame:
        if windows <= 1:
            return frame.copy()
        segment = max(len(frame) // windows, 1)
        start = window_idx * segment
        end = len(frame) if window_idx == windows - 1 else min((window_idx + 1) * segment, len(frame))
        sliced = frame.iloc[start:end].copy()
        if len(sliced) < 20:
            return frame.copy()
        return sliced

    def _evaluate_frame(
        self,
        frame: pd.DataFrame,
        params: StrategyParams,
        interval: str,
        symbol: str,
        transaction_cost_bps: float,
    ) -> AggregateMetrics:
        features = engineer_features(frame, params)
        signal = rule_signal(features, params)
        _, report = run_backtest(
            df=frame,
            signal=signal,
            transaction_cost_bps=transaction_cost_bps,
            interval=interval,
            symbol=symbol,
        )
        objective = report.sharpe + (0.2 * report.total_return) - (0.3 * abs(report.max_drawdown)) - (0.002 * report.trades)
        return AggregateMetrics(
            objective=float(objective),
            total_return=report.total_return,
            sharpe=report.sharpe,
            max_drawdown=report.max_drawdown,
            trades=report.trades,
        )

    @staticmethod
    def _aggregate(metrics: list[AggregateMetrics]) -> AggregateMetrics:
        if not metrics:
            return AggregateMetrics(objective=0.0, total_return=0.0, sharpe=0.0, max_drawdown=0.0, trades=0)
        return AggregateMetrics(
            objective=float(sum(m.objective for m in metrics) / len(metrics)),
            total_return=float(sum(m.total_return for m in metrics) / len(metrics)),
            sharpe=float(sum(m.sharpe for m in metrics) / len(metrics)),
            max_drawdown=float(sum(m.max_drawdown for m in metrics) / len(metrics)),
            trades=int(sum(m.trades for m in metrics)),
        )


def persist_best_candidate(result: AutoresearchEvaluation, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "autoresearch_best.json"
    payload = asdict(result)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def append_experiment_log(result: AutoresearchEvaluation, report_dir: Path, label: str = "candidate") -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "autoresearch_experiments.jsonl"
    payload = asdict(result)
    payload["label"] = label
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
    return path


def promote_best_candidate(settings: Settings, env_file: Path, artifact_path: Path) -> list[str]:
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not payload.get("promotable"):
        raise RuntimeError("Best candidate is not promotable.")

    params = payload["candidate_params"]
    updated = _apply_env_updates(
        env_file=env_file,
        updates={
            "MOMENTUM_THRESHOLD": params["momentum_threshold"],
            "ZSCORE_THRESHOLD": params["zscore_threshold"],
            "MOMENTUM_SIGNAL_WEIGHT": params["momentum_signal_weight"],
            "MEAN_REVERSION_SIGNAL_WEIGHT": params["mean_reversion_signal_weight"],
        },
    )
    _append_strategy_doc(settings.strategy_doc_path, payload)
    return updated


def _apply_env_updates(env_file: Path, updates: dict[str, float]) -> list[str]:
    if not env_file.exists():
        env_file.write_text("", encoding="utf-8")

    lines = env_file.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    for key, value in updates.items():
        rendered = f"{key}={value}"
        replaced = False
        for idx, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[idx] = rendered
                replaced = True
                break
        if not replaced:
            lines.append(rendered)
        updated.append(rendered)
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated


def _append_strategy_doc(strategy_doc_path: Path, payload: dict) -> None:
    strategy_doc_path.parent.mkdir(parents=True, exist_ok=True)
    if not strategy_doc_path.exists():
        strategy_doc_path.write_text("# Strategy\n\n", encoding="utf-8")

    candidate = payload["candidate_holdout"]
    baseline = payload["baseline_holdout"]
    params = payload["candidate_params"]
    entry = (
        f"\n## Autoresearch promotion {payload['evaluated_at']}\n"
        f"- symbols: {', '.join(payload['symbols'])}\n"
        f"- baseline_holdout_objective: {baseline['objective']:.6f}\n"
        f"- candidate_holdout_objective: {candidate['objective']:.6f}\n"
        f"- momentum_threshold: {params['momentum_threshold']}\n"
        f"- zscore_threshold: {params['zscore_threshold']}\n"
        f"- momentum_signal_weight: {params['momentum_signal_weight']}\n"
        f"- mean_reversion_signal_weight: {params['mean_reversion_signal_weight']}\n"
    )
    with strategy_doc_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)
