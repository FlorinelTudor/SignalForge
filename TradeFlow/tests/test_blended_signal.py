import pandas as pd

from tradeflow_bot.strategy import StrategyParams, blended_signal


def test_blended_signal_does_not_invert_short_direction():
    idx = pd.date_range("2026-01-01", periods=3, freq="1h", tz="UTC")
    features = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0],
            "high": [101.0, 101.0, 101.0],
            "low": [99.0, 99.0, 99.0],
            "close": [100.0, 100.0, 100.0],
            "volume": [1000, 1000, 1000],
            "ret_1": [0.0, 0.0, 0.0],
            "ret_5": [0.0, 0.0, 0.0],
            "momentum": [0.03, -0.03, -0.03],
            "zscore": [0.0, 0.0, 0.0],
            "volatility": [0.01, 0.01, 0.01],
            "hl_spread": [0.01, 0.01, 0.01],
            "oc_spread": [0.0, 0.0, 0.0],
        },
        index=idx,
    )

    params = StrategyParams(
        momentum_window=20,
        mean_reversion_window=30,
        volatility_window=20,
        momentum_threshold=0.02,
        zscore_threshold=1.2,
    )
    probs = pd.Series([0.8, 0.2, 0.6], index=idx)

    out = blended_signal(
        features=features,
        params=params,
        bullish_probability=probs,
        long_threshold=0.55,
        short_threshold=0.45,
        allow_short=True,
    )

    assert out.iloc[0] == 1.0
    assert out.iloc[1] == -1.0
    assert out.iloc[2] == 0.0
