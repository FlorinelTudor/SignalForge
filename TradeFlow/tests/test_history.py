from pathlib import Path
from datetime import datetime, timedelta, timezone

from tradeflow_bot.config import Settings
from tradeflow_bot.history import AlpacaHistoryImprover


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        alpaca_api_key="key",
        alpaca_secret_key="secret",
        alpaca_base_url="https://paper-api.alpaca.markets",
        log_dir=tmp_path / "logs",
        report_dir=tmp_path / "reports",
        model_path=tmp_path / "models" / "model.joblib",
        adaptive_state_path=tmp_path / "models" / "adaptive_state.json",
        strategy_doc_path=tmp_path / "Strategy.md",
    )


def test_analyze_history_creates_closed_fills(tmp_path: Path):
    improver = AlpacaHistoryImprover(_settings(tmp_path))
    fills = [
        {"symbol": "AAPL", "side": "buy", "qty": "1", "price": "100", "transaction_time": "2026-01-01T10:00:00Z"},
        {"symbol": "AAPL", "side": "sell", "qty": "1", "price": "110", "transaction_time": "2026-01-02T10:00:00Z"},
        {"symbol": "MSFT", "side": "sell", "qty": "1", "price": "200", "transaction_time": "2026-01-03T10:00:00Z"},
        {"symbol": "MSFT", "side": "buy", "qty": "1", "price": "180", "transaction_time": "2026-01-04T10:00:00Z"},
    ]
    summary, closed = improver.analyze(fills)

    assert summary.closed_count == 2
    assert summary.wins == 2
    assert len(closed) == 2


def test_suggest_history_changes_when_performance_strong(tmp_path: Path):
    settings = _settings(tmp_path)
    settings.ml_long_threshold = 0.55
    settings.ml_short_threshold = 0.45
    settings.short_size_multiplier = 0.5
    improver = AlpacaHistoryImprover(settings)

    class S:
        closed_count = 20
        win_rate = 0.7
        short_closed = 10
        long_closed = 10
        short_win_rate = 0.9
        long_win_rate = 0.5
        profit_factor = 1.4

    suggestions = improver.suggest(S())
    keys = {x.key for x in suggestions}
    assert "ML_LONG_THRESHOLD" in keys
    assert "ML_SHORT_THRESHOLD" in keys
    assert "SHORT_SIZE_MULTIPLIER" in keys


def test_fetch_history_records_falls_back_to_filled_orders(tmp_path: Path):
    improver = AlpacaHistoryImprover(_settings(tmp_path))

    class Resp:
        def __init__(self, code: int, payload):
            self.status_code = code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=30):
        if url.endswith("/v2/account/activities"):
            return Resp(200, [])
        if url.endswith("/v2/orders"):
            return Resp(
                200,
                [
                    {
                        "status": "filled",
                        "symbol": "AAPL",
                        "side": "buy",
                        "filled_qty": "1.5",
                        "filled_avg_price": "190.25",
                        "filled_at": "2026-02-10T15:00:00Z",
                    },
                    {
                        "status": "canceled",
                        "symbol": "MSFT",
                        "side": "buy",
                        "filled_qty": "0",
                        "filled_avg_price": "0",
                    },
                ],
            )
        return Resp(404, {})

    improver.session.get = fake_get

    records = improver.fetch_history_records()
    assert len(records) == 1
    assert records[0]["symbol"] == "AAPL"
    assert records[0]["side"] == "buy"
    assert records[0]["qty"] == 1.5
    assert records[0]["price"] == 190.25


def test_fetch_filled_orders_respects_lookback(tmp_path: Path):
    settings = _settings(tmp_path)
    settings.alpaca_history_lookback_days = 30
    improver = AlpacaHistoryImprover(settings)

    now = datetime.now(timezone.utc)
    recent = now - timedelta(days=1)
    old = now - timedelta(days=120)

    class Resp:
        def __init__(self, code: int, payload):
            self.status_code = code
            self._payload = payload

        def json(self):
            return self._payload

    calls = {"count": 0}

    def fake_get(url, params=None, timeout=30):
        if url.endswith("/v2/orders"):
            calls["count"] += 1
            return Resp(
                200,
                [
                    {
                        "id": "ord-recent",
                        "status": "filled",
                        "symbol": "AAPL",
                        "side": "buy",
                        "filled_qty": "1",
                        "filled_avg_price": "100",
                        "filled_at": recent.isoformat().replace("+00:00", "Z"),
                        "submitted_at": recent.isoformat().replace("+00:00", "Z"),
                    },
                    {
                        "id": "ord-old",
                        "status": "filled",
                        "symbol": "MSFT",
                        "side": "buy",
                        "filled_qty": "1",
                        "filled_avg_price": "200",
                        "filled_at": old.isoformat().replace("+00:00", "Z"),
                        "submitted_at": old.isoformat().replace("+00:00", "Z"),
                    },
                ],
            )
        return Resp(404, {})

    improver.session.get = fake_get

    records = improver.fetch_filled_orders(max_pages=2, page_size=100)
    assert calls["count"] >= 1
    assert len(records) == 1
    assert records[0]["id"] == "ord-recent"
