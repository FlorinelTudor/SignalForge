from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from tradeflow_bot.brokers.paper import PaperBroker
from tradeflow_bot.config import Settings
from tradeflow_bot.data import DataClient
from tradeflow_bot.execution import CycleDecision, TradingEngine
from tradeflow_bot.ml import ModelManager
from tradeflow_bot.notifier import Notifier


def _engine(tmp_path: Path, **kwargs) -> TradingEngine:
    settings = Settings(
        log_dir=tmp_path / "logs",
        report_dir=tmp_path / "reports",
        model_path=tmp_path / "models" / "model.joblib",
        adaptive_state_path=tmp_path / "models" / "adaptive_state.json",
        strategy_doc_path=tmp_path / "Strategy.md",
        **kwargs,
    )
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    settings.report_dir.mkdir(parents=True, exist_ok=True)
    settings.model_path.parent.mkdir(parents=True, exist_ok=True)
    settings.adaptive_state_path.parent.mkdir(parents=True, exist_ok=True)

    return TradingEngine(
        settings=settings,
        data_client=DataClient(source="synthetic"),
        broker=PaperBroker(state_path=tmp_path / "paper_state.json"),
        model_manager=ModelManager(settings.model_path),
        notifier=Notifier(settings),
    )


def test_policy_filter_pauses_crypto(tmp_path: Path):
    engine = _engine(tmp_path, asset_class="crypto", pause_crypto=True)
    idx = pd.date_range("2026-02-10", periods=3, freq="1h", tz="UTC")
    signal = pd.Series([1.0, -1.0, 1.0], index=idx)
    feat = pd.DataFrame({"ret_1": [0.05, -0.06, 0.07]}, index=idx)

    out = engine._policy_filter_series(signal, feat, symbol="BTCUSD")
    assert float(out.abs().sum()) == 0.0


def test_apply_trade_policies_time_cutoff(tmp_path: Path):
    engine = _engine(tmp_path, no_new_entries_after_ny="10:30")
    ts = pd.Timestamp("2026-02-10 16:00:00+00:00")  # 11:00 ET

    out = engine._apply_trade_policies(1.0, ts, current_qty=0.0, symbol="AAPL")
    assert out == 0.0


def test_apply_trade_policies_keep_existing_after_cutoff(tmp_path: Path):
    engine = _engine(tmp_path, no_new_entries_after_ny="10:30")
    ts = pd.Timestamp("2026-02-10 16:00:00+00:00")  # 11:00 ET

    out = engine._apply_trade_policies(1.0, ts, current_qty=1.0, symbol="AAPL")
    assert out == 1.0


def test_risk_levels_stock_defaults(tmp_path: Path):
    engine = _engine(tmp_path, asset_class="stock", stock_stop_loss_pct=0.04, risk_reward_ratio=2.0)
    stop, target = engine._risk_levels(1.0, 100.0)

    assert stop == 96.0
    assert target == 108.0


def test_apply_trade_policies_blocks_new_entries_in_event_post_window(tmp_path: Path):
    engine = _engine(
        tmp_path,
        event_guard_enabled=True,
        event_post_no_entry_minutes=10,
        event_pre_reduce_hours=24,
    )
    event_ts = datetime(2026, 3, 6, 13, 30, tzinfo=timezone.utc)
    engine._event_times_utc = [event_ts]
    engine._now_utc = lambda: datetime(2026, 3, 6, 13, 35, tzinfo=timezone.utc)  # type: ignore[method-assign]
    ts = pd.Timestamp("2026-03-06 13:35:00+00:00")

    out = engine._apply_trade_policies(1.0, ts, current_qty=0.0, symbol="AAPL")
    assert out == 0.0


def test_pre_event_reduce_scales_targets(tmp_path: Path):
    engine = _engine(
        tmp_path,
        event_guard_enabled=True,
        event_pre_reduce_hours=24,
        event_pre_reduce_exposure_fraction=0.5,
    )
    event_ts = datetime(2026, 3, 6, 13, 30, tzinfo=timezone.utc)
    engine._event_times_utc = [event_ts]
    engine._now_utc = lambda: datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc)  # type: ignore[method-assign]

    decision = CycleDecision(
        timestamp="2026-03-06 12:00:00+00:00",
        symbol="AAPL",
        sector="XLK",
        close=100.0,
        rule_signal=1.0,
        ml_probability=0.8,
        final_signal=1.0,
        signal_strength=7.0,
        news_sentiment=0.0,
        sector_strength=0.0,
        stop_price=96.0,
        target_price=108.0,
        current_qty=2.0,
        target_qty=2.0,
        delta_qty=0.0,
        order_result=None,
    )
    engine._apply_portfolio_constraints([decision], {"positions": {"AAPL": 2.0}})

    assert decision.target_qty == 1.0
