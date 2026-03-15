import pandas as pd

from tradeflow_bot.strategy import StrategyParams, engineer_features, rule_signal


def test_rule_signal_returns_same_length():
    idx = pd.date_range("2025-01-01", periods=200, freq="1h", tz="UTC")
    close = pd.Series(range(100, 300), index=idx, dtype=float)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1000,
        }
    )

    params = StrategyParams(
        momentum_window=20,
        mean_reversion_window=30,
        volatility_window=20,
        momentum_threshold=0.01,
        zscore_threshold=1.0,
    )
    feat = engineer_features(df, params)
    sig = rule_signal(feat, params)

    assert len(sig) == len(df)
