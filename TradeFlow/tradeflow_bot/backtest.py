from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class BacktestReport:
    symbol: str
    interval: str
    start: str
    end: str
    total_return: float
    annualized_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    trades: int



def run_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    transaction_cost_bps: float,
    interval: str,
    symbol: str,
) -> tuple[pd.DataFrame, BacktestReport]:
    out = df.copy()
    out["signal"] = signal.reindex(out.index).fillna(0)
    out["returns"] = out["close"].pct_change().fillna(0)

    out["position"] = out["signal"].shift(1).fillna(0)
    turnover = out["position"].diff().abs().fillna(0)
    costs = turnover * (transaction_cost_bps / 10_000.0)

    out["strategy_return"] = out["position"] * out["returns"] - costs
    out["equity_curve"] = (1.0 + out["strategy_return"]).cumprod()
    out["peak"] = out["equity_curve"].cummax()
    out["drawdown"] = out["equity_curve"] / out["peak"] - 1.0

    total_return = float(out["equity_curve"].iloc[-1] - 1.0)
    n = len(out)
    periods_per_year = _periods_per_year(interval)
    annualized_return = float((1 + total_return) ** (periods_per_year / max(n, 1)) - 1)

    ret_std = out["strategy_return"].std(ddof=0)
    sharpe = float((out["strategy_return"].mean() / ret_std) * np.sqrt(periods_per_year)) if ret_std else 0.0

    max_drawdown = float(out["drawdown"].min())
    trades = int((turnover > 0).sum())
    wins = int((out["strategy_return"] > 0).sum())
    non_zero = int((out["strategy_return"] != 0).sum())
    win_rate = float(wins / non_zero) if non_zero else 0.0

    report = BacktestReport(
        symbol=symbol,
        interval=interval,
        start=str(out.index[0]),
        end=str(out.index[-1]),
        total_return=total_return,
        annualized_return=annualized_return,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        trades=trades,
    )
    return out, report


def persist_backtest(results: pd.DataFrame, report: BacktestReport, report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    csv_path = report_dir / f"backtest_{report.symbol}_{stamp}.csv"
    json_path = report_dir / f"backtest_{report.symbol}_{stamp}.json"

    results.to_csv(csv_path)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2)

    return csv_path, json_path


def _periods_per_year(interval: str) -> int:
    mapping = {
        "1m": 60 * 24 * 252,
        "2m": 30 * 24 * 252,
        "5m": 12 * 24 * 252,
        "15m": 4 * 24 * 252,
        "30m": 2 * 24 * 252,
        "60m": 24 * 252,
        "1h": 24 * 252,
        "90m": int((24 / 1.5) * 252),
        "1d": 252,
        "1wk": 52,
    }
    if interval not in mapping:
        return 252
    return mapping[interval]
