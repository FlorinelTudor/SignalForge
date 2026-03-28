from __future__ import annotations

from tradeflow_bot.config import Settings
from tradeflow_bot.strategy import StrategyParams

# This is the single strategy surface that autoresearch is expected to edit.
# Keep execution, evaluator, and promotion logic outside this file.
CANDIDATE_MOMENTUM_THRESHOLD_MULTIPLIER = 0.85
CANDIDATE_ZSCORE_THRESHOLD_MULTIPLIER = 0.90
CANDIDATE_MOMENTUM_SIGNAL_WEIGHT = 0.70
CANDIDATE_MEAN_REVERSION_SIGNAL_WEIGHT = 0.30


def build_candidate_params(settings: Settings) -> StrategyParams:
    return StrategyParams(
        momentum_window=settings.momentum_window,
        mean_reversion_window=settings.mean_reversion_window,
        volatility_window=settings.volatility_window,
        momentum_threshold=max(settings.momentum_threshold * CANDIDATE_MOMENTUM_THRESHOLD_MULTIPLIER, 0.002),
        zscore_threshold=max(settings.zscore_threshold * CANDIDATE_ZSCORE_THRESHOLD_MULTIPLIER, 0.40),
        momentum_signal_weight=CANDIDATE_MOMENTUM_SIGNAL_WEIGHT,
        mean_reversion_signal_weight=CANDIDATE_MEAN_REVERSION_SIGNAL_WEIGHT,
    )
