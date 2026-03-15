from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class StrategyParams:
    momentum_window: int
    mean_reversion_window: int
    volatility_window: int
    momentum_threshold: float
    zscore_threshold: float


def engineer_features(df: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
    out = df.copy()
    out["ret_1"] = out["close"].pct_change()
    out["ret_5"] = out["close"].pct_change(5)
    out["momentum"] = out["close"].pct_change(params.momentum_window)

    rolling_mean = out["close"].rolling(params.mean_reversion_window).mean()
    rolling_std = out["close"].rolling(params.mean_reversion_window).std(ddof=0)
    out["zscore"] = (out["close"] - rolling_mean) / rolling_std.replace(0, np.nan)

    out["volatility"] = out["ret_1"].rolling(params.volatility_window).std(ddof=0)
    out["hl_spread"] = (out["high"] - out["low"]) / out["close"].replace(0, np.nan)
    out["oc_spread"] = (out["close"] - out["open"]) / out["open"].replace(0, np.nan)
    return out


def rule_signal(features: pd.DataFrame, params: StrategyParams) -> pd.Series:
    momentum = features["momentum"]
    zscore = features["zscore"]

    mom_sig = np.where(momentum > params.momentum_threshold, 1, 0)
    mom_sig = np.where(momentum < -params.momentum_threshold, -1, mom_sig)

    mr_sig = np.where(zscore < -params.zscore_threshold, 1, 0)
    mr_sig = np.where(zscore > params.zscore_threshold, -1, mr_sig)

    combined = 0.6 * mom_sig + 0.4 * mr_sig
    signal = np.sign(combined)
    return pd.Series(signal, index=features.index, name="rule_signal").fillna(0)


def blended_signal(
    features: pd.DataFrame,
    params: StrategyParams,
    bullish_probability: pd.Series,
    long_threshold: float,
    short_threshold: float,
    allow_short: bool,
) -> pd.Series:
    base = rule_signal(features, params)

    out = pd.Series(0.0, index=features.index)
    long_ok = bullish_probability >= long_threshold
    out[(base > 0) & long_ok] = 1.0
    if allow_short:
        short_ok = bullish_probability <= short_threshold
        out[(base < 0) & short_ok] = -1.0

    if not allow_short:
        out = out.clip(lower=0)
    return out.rename("signal").fillna(0)
