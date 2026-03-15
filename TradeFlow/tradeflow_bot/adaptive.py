from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from tradeflow_bot.backtest import run_backtest
from tradeflow_bot.strategy import StrategyParams, blended_signal


@dataclass
class TuneResult:
    momentum_threshold: float
    zscore_threshold: float
    ml_long_threshold: float
    ml_short_threshold: float
    objective: float
    total_return: float
    sharpe: float
    max_drawdown: float
    tuned_at: datetime


class AdaptiveStrategyManager:
    def __init__(self, state_path: Path, strategy_doc_path: Path):
        self.state_path = state_path
        self.strategy_doc_path = strategy_doc_path
        self.last_tuned_at = self._load_last_tuned_at()

    def should_tune(self, interval_minutes: int) -> bool:
        if self.last_tuned_at is None:
            return True
        now = datetime.now(timezone.utc)
        return now - self.last_tuned_at >= timedelta(minutes=interval_minutes)

    def tune(
        self,
        df: pd.DataFrame,
        probabilities: pd.Series,
        symbol: str,
        interval: str,
        transaction_cost_bps: float,
        allow_short: bool,
        momentum_window: int,
        mean_reversion_window: int,
        volatility_window: int,
        current_momentum_threshold: float,
        current_zscore_threshold: float,
        current_ml_long_threshold: float,
        current_ml_short_threshold: float,
    ) -> TuneResult:
        momentum_candidates = self._neighbors(current_momentum_threshold, [0.75, 1.0, 1.25], minimum=0.002)
        zscore_candidates = self._neighbors(current_zscore_threshold, [0.75, 1.0, 1.25], minimum=0.4)
        ml_long_candidates = self._neighbors(current_ml_long_threshold, [0.95, 1.0, 1.05], minimum=0.50)
        ml_short_candidates = self._neighbors(current_ml_short_threshold, [0.95, 1.0, 1.05], minimum=0.35)

        best: TuneResult | None = None
        for mt in momentum_candidates:
            for zt in zscore_candidates:
                for mlt in ml_long_candidates:
                    for mst in ml_short_candidates:
                        params = StrategyParams(
                            momentum_window=momentum_window,
                            mean_reversion_window=mean_reversion_window,
                            volatility_window=volatility_window,
                            momentum_threshold=mt,
                            zscore_threshold=zt,
                        )
                        signal = blended_signal(
                            features=df,
                            params=params,
                            bullish_probability=probabilities,
                            long_threshold=mlt,
                            short_threshold=mst,
                            allow_short=allow_short,
                        )
                        _, report = run_backtest(
                            df=df,
                            signal=signal,
                            transaction_cost_bps=transaction_cost_bps,
                            interval=interval,
                            symbol=symbol,
                        )
                        objective = report.sharpe + 0.2 * report.total_return - 0.3 * abs(report.max_drawdown)
                        candidate = TuneResult(
                            momentum_threshold=mt,
                            zscore_threshold=zt,
                            ml_long_threshold=mlt,
                            ml_short_threshold=mst,
                            objective=float(objective),
                            total_return=report.total_return,
                            sharpe=report.sharpe,
                            max_drawdown=report.max_drawdown,
                            tuned_at=datetime.now(timezone.utc),
                        )
                        if best is None or candidate.objective > best.objective:
                            best = candidate

        if best is None:
            raise RuntimeError("Unable to tune strategy with provided data.")

        self.last_tuned_at = best.tuned_at
        self._save_state(best)
        self._append_strategy_doc(best)
        return best

    @staticmethod
    def _neighbors(base: float, factors: list[float], minimum: float) -> list[float]:
        vals = sorted({round(max(base * factor, minimum), 4) for factor in factors})
        return vals

    def _load_last_tuned_at(self) -> datetime | None:
        if not self.state_path.exists():
            return None
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            ts = payload.get("last_tuned_at")
            if ts:
                return datetime.fromisoformat(ts)
        except Exception:
            return None
        return None

    def _save_state(self, result: TuneResult) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_tuned_at": result.tuned_at.isoformat(),
            "params": {
                "momentum_threshold": result.momentum_threshold,
                "zscore_threshold": result.zscore_threshold,
                "ml_long_threshold": result.ml_long_threshold,
                "ml_short_threshold": result.ml_short_threshold,
            },
            "metrics": {
                "objective": result.objective,
                "total_return": result.total_return,
                "sharpe": result.sharpe,
                "max_drawdown": result.max_drawdown,
            },
        }
        self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _append_strategy_doc(self, result: TuneResult) -> None:
        self.strategy_doc_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.strategy_doc_path.exists():
            self.strategy_doc_path.write_text(
                "# Strategy\n\n"
                "This file is automatically maintained by TradeFlow's adaptive strategy manager.\n"
                "Each tuning event appends a new entry below.\n\n",
                encoding="utf-8",
            )

        entry = (
            f"\n## {result.tuned_at.isoformat()}\n"
            f"- momentum_threshold: {result.momentum_threshold}\n"
            f"- zscore_threshold: {result.zscore_threshold}\n"
            f"- ml_long_threshold: {result.ml_long_threshold}\n"
            f"- ml_short_threshold: {result.ml_short_threshold}\n"
            f"- objective: {result.objective:.6f}\n"
            f"- backtest_total_return: {result.total_return:.6f}\n"
            f"- backtest_sharpe: {result.sharpe:.6f}\n"
            f"- backtest_max_drawdown: {result.max_drawdown:.6f}\n\n"
        )
        with self.strategy_doc_path.open("a", encoding="utf-8") as f:
            f.write(entry)
