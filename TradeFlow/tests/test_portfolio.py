from pathlib import Path

from tradeflow_bot.brokers.paper import PaperBroker
from tradeflow_bot.brokers.base import OrderResult
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


def _decision(symbol: str, sector: str, strength: float) -> CycleDecision:
    return CycleDecision(
        timestamp="2026-02-12 15:00:00+00:00",
        symbol=symbol,
        sector=sector,
        close=100.0,
        rule_signal=1.0,
        ml_probability=0.6,
        final_signal=1.0,
        signal_strength=strength,
        news_sentiment=0.0,
        sector_strength=0.0,
        stop_price=96.0,
        target_price=108.0,
        current_qty=0.0,
        target_qty=10.0,
        delta_qty=10.0,
        order_result=None,
    )


def _short_decision(symbol: str, sector: str, strength: float) -> CycleDecision:
    return CycleDecision(
        timestamp="2026-02-12 15:00:00+00:00",
        symbol=symbol,
        sector=sector,
        close=100.0,
        rule_signal=-1.0,
        ml_probability=0.2,
        final_signal=-1.0,
        signal_strength=strength,
        news_sentiment=0.0,
        sector_strength=0.0,
        stop_price=104.0,
        target_price=92.0,
        current_qty=0.0,
        target_qty=-6.0,  # $600 notional at $100
        delta_qty=-6.0,
        order_result=None,
    )


def test_sector_cap_only_one_position_per_sector(tmp_path: Path):
    engine = _engine(
        tmp_path,
        max_concurrent_positions=5,
        symbol_sector_map={"AAPL": "XLK", "MSFT": "XLK"},
    )

    decisions = [_decision("AAPL", "XLK", 8.0), _decision("MSFT", "XLK", 7.0)]
    engine._apply_portfolio_constraints(decisions, {"positions": {}})

    active = [d for d in decisions if abs(d.target_qty) > 1e-9]
    assert len(active) == 1
    assert active[0].symbol == "AAPL"


def test_max_concurrent_positions_respected(tmp_path: Path):
    engine = _engine(
        tmp_path,
        max_concurrent_positions=2,
        symbol_sector_map={"AAPL": "XLK", "JPM": "XLF", "XOM": "XLE"},
    )

    decisions = [
        _decision("AAPL", "XLK", 9.0),
        _decision("JPM", "XLF", 8.0),
        _decision("XOM", "XLE", 7.0),
    ]
    engine._apply_portfolio_constraints(decisions, {"positions": {}})

    active = [d for d in decisions if abs(d.target_qty) > 1e-9]
    assert len(active) == 2
    assert {d.symbol for d in active} == {"AAPL", "JPM"}


def test_short_scaled_min_notional_allows_half_size_shorts(tmp_path: Path):
    engine = _engine(
        tmp_path,
        min_position_value_usd=1200,
        short_size_multiplier=0.5,
        max_concurrent_positions=5,
        symbol_sector_map={"LMT": "XLI"},
    )

    decisions = [_short_decision("LMT", "XLI", 8.0)]
    engine._apply_portfolio_constraints(decisions, {"positions": {}, "equity": 100000.0, "positions_raw": []})

    assert decisions[0].target_qty < 0
    assert abs(decisions[0].delta_qty) > 1e-9


def test_run_portfolio_cycle_skips_duplicate_open_orders(tmp_path: Path):
    engine = _engine(
        tmp_path,
        symbols=["LUV", "LMT"],
        symbol_sector_map={"LUV": "XLY", "LMT": "XLI"},
    )

    decisions_by_symbol = {
        "LUV": CycleDecision(
            timestamp="2026-02-12 15:00:00+00:00",
            symbol="LUV",
            sector="XLY",
            close=40.0,
            rule_signal=1.0,
            ml_probability=0.7,
            final_signal=1.0,
            signal_strength=8.0,
            news_sentiment=0.0,
            sector_strength=0.0,
            stop_price=38.4,
            target_price=43.2,
            current_qty=0.0,
            target_qty=10.0,
            delta_qty=10.0,
            order_result=None,
        ),
        "LMT": CycleDecision(
            timestamp="2026-02-12 15:00:00+00:00",
            symbol="LMT",
            sector="XLI",
            close=500.0,
            rule_signal=-1.0,
            ml_probability=0.2,
            final_signal=-1.0,
            signal_strength=8.0,
            news_sentiment=0.0,
            sector_strength=0.0,
            stop_price=520.0,
            target_price=460.0,
            current_qty=0.0,
            target_qty=-2.0,
            delta_qty=-2.0,
            order_result=None,
        ),
    }

    engine._evaluate_symbol = lambda symbol, current_qty: decisions_by_symbol[symbol]  # type: ignore[method-assign]
    engine._apply_portfolio_constraints = lambda decisions, summary, top_sectors=None: None  # type: ignore[method-assign]
    engine.broker.get_open_orders = lambda: [{"symbol": "LUV", "side": "buy", "status": "accepted"}]  # type: ignore[method-assign]

    call_count = {"place": 0}

    def fake_place_order(symbol: str, side: str, qty: float) -> OrderResult:
        call_count["place"] += 1
        return OrderResult(True, "test-order", side, qty, "ok")

    engine.broker.place_order = fake_place_order  # type: ignore[method-assign]

    result = engine._run_portfolio_cycle(["LUV", "LMT"])
    assert result.orders_sent == 1
    assert call_count["place"] == 1
    assert decisions_by_symbol["LUV"].order_result is not None
    assert decisions_by_symbol["LUV"].order_result.accepted is False
    assert "duplicate" in decisions_by_symbol["LUV"].order_result.message.lower()


def test_top_sector_filter_blocks_new_entries_outside_top_n(tmp_path: Path):
    engine = _engine(
        tmp_path,
        max_concurrent_positions=5,
        symbol_sector_map={"AAPL": "XLK", "JPM": "XLF"},
    )

    decisions = [_decision("AAPL", "XLK", 9.0), _decision("JPM", "XLF", 8.0)]
    engine._apply_portfolio_constraints(decisions, {"positions": {}}, top_sectors={"XLK"})

    assert decisions[0].target_qty > 0
    assert decisions[1].target_qty == 0.0


def test_run_portfolio_cycle_honors_max_new_orders_per_cycle(tmp_path: Path):
    engine = _engine(
        tmp_path,
        symbols=["AAPL", "JPM", "XOM"],
        symbol_sector_map={"AAPL": "XLK", "JPM": "XLF", "XOM": "XLE"},
        max_new_orders_per_cycle=1,
    )

    decisions_by_symbol = {
        "AAPL": _decision("AAPL", "XLK", 9.0),
        "JPM": _decision("JPM", "XLF", 8.0),
        "XOM": _decision("XOM", "XLE", 7.0),
    }
    engine._evaluate_symbol = lambda symbol, current_qty: decisions_by_symbol[symbol]  # type: ignore[method-assign]
    engine._apply_portfolio_constraints = lambda decisions, summary, top_sectors=None: None  # type: ignore[method-assign]
    engine._top_sectors_by_relative_strength = lambda: {"XLK", "XLF", "XLE"}  # type: ignore[method-assign]
    engine.broker.get_open_orders = lambda: []  # type: ignore[method-assign]

    call_count = {"place": 0}

    def fake_place_order(symbol: str, side: str, qty: float) -> OrderResult:
        call_count["place"] += 1
        return OrderResult(True, f"order-{symbol}", side, qty, "ok")

    engine.broker.place_order = fake_place_order  # type: ignore[method-assign]

    result = engine._run_portfolio_cycle(["AAPL", "JPM", "XOM"])
    assert result.orders_sent == 1
    assert call_count["place"] == 1
