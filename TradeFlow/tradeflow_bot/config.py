from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Settings:
    symbol: str = "AAPL"
    symbols: list[str] | None = None
    symbol_sector_map: dict[str, str] | None = None
    interval: str = "1h"
    history_days: int = 365
    momentum_window: int = 20
    mean_reversion_window: int = 30
    volatility_window: int = 20
    momentum_threshold: float = 0.02
    zscore_threshold: float = 1.2
    momentum_signal_weight: float = 0.6
    mean_reversion_signal_weight: float = 0.4
    ml_long_threshold: float = 0.55
    ml_short_threshold: float = 0.45
    transaction_cost_bps: float = 5.0
    order_size: float = 1.0
    allow_short: bool = False
    asset_class: str = "stock"  # stock | crypto

    mode: str = "paper"  # backtest | paper | live
    broker_name: str = "paper"  # paper | alpaca | etoro
    poll_interval_seconds: int = 60
    retrain_interval_minutes: int = 60
    strategy_tune_interval_minutes: int = 240

    # Credentials
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"
    alpaca_history_lookback_days: int = 730

    etoro_api_key: str = ""
    etoro_secret_key: str = ""

    # Market context (news + sector strength)
    news_enabled: bool = True
    news_rss_urls: list[str] | None = None
    news_aliases: list[str] | None = None
    news_max_items: int = 40
    news_bullish_threshold: float = 0.05
    news_bearish_threshold: float = -0.05

    sector_enabled: bool = True
    symbol_sector_etf: str = "XLK"
    sector_symbols: list[str] | None = None
    sector_bullish_threshold: float = 0.10
    sector_bearish_threshold: float = -0.10
    context_refresh_minutes: int = 30
    sector_rotation_top_n: int = 2
    sector_rotation_lookback_bars: int = 5

    # Adaptive strategy state
    tuning_enabled: bool = True
    adaptive_state_path: Path = Path("models/adaptive_state.json")
    strategy_doc_path: Path = Path("Strategy.md")

    # Imported risk policy (Twin notes)
    stock_momentum_entry_threshold: float = 0.03
    crypto_momentum_entry_threshold: float = 0.02
    short_breakdown_threshold: float = 0.05
    min_position_value_usd: float = 1200.0
    max_position_value_usd: float = 5000.0
    max_concurrent_positions: int = 10
    stock_stop_loss_pct: float = 0.05
    crypto_stop_loss_pct: float = 0.08
    risk_reward_ratio: float = 2.0
    pause_crypto: bool = False
    no_new_entries_after_ny: str = "10:30"
    friday_flatten_enabled: bool = False
    friday_flatten_after_ny: str = "15:00"
    require_post_earnings_for_longs: bool = False
    post_earnings_allowlist: list[str] | None = None
    short_size_multiplier: float = 0.5
    max_short_exposure_fraction: float = 0.5
    max_new_orders_per_cycle: int = 3

    # Event guard rails (UTC event timestamps)
    event_guard_enabled: bool = True
    event_calendar_utc: list[str] | None = None
    event_pre_reduce_hours: int = 24
    event_post_no_entry_minutes: int = 5
    event_pre_reduce_exposure_fraction: float = 0.5

    # Notifications
    webhook_url: str = ""
    notify_email_to: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    model_path: Path = Path("models/model.joblib")
    report_dir: Path = Path("reports")
    log_dir: Path = Path("logs")



def _as_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_list(value: str | None, default: list[str]) -> list[str]:
    if value is None:
        return default
    out = [x.strip() for x in value.split(",") if x.strip()]
    return out if out else default


def _as_map(value: str | None, default: dict[str, str]) -> dict[str, str]:
    if value is None:
        return default
    out: dict[str, str] = {}
    for token in value.split(","):
        token = token.strip()
        if not token or ":" not in token:
            continue
        key, val = token.split(":", 1)
        key = key.strip().upper()
        val = val.strip().upper()
        if key and val:
            out[key] = val
    return out if out else default


def load_settings(env_file: str = ".env") -> Settings:
    load_dotenv(env_file)

    default_news_urls = [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.reuters.com/news/wealth",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    ]
    default_sector_symbols = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
    default_symbol_sector_map = {"AAPL": "XLK"}
    default_event_calendar_utc = [
        "2026-03-06T13:30:00Z",  # US jobs (NFP) release
        "2026-03-11T12:30:00Z",  # US CPI release
        "2026-03-18T18:00:00Z",  # FOMC statement/press conference
    ]

    settings = Settings(
        symbol=os.getenv("SYMBOL", "AAPL"),
        symbols=_as_list(os.getenv("SYMBOLS"), [os.getenv("SYMBOL", "AAPL")]),
        symbol_sector_map=_as_map(os.getenv("SYMBOL_SECTOR_MAP"), default_symbol_sector_map),
        interval=os.getenv("INTERVAL", "1h"),
        history_days=int(os.getenv("HISTORY_DAYS", "365")),
        momentum_window=int(os.getenv("MOMENTUM_WINDOW", "20")),
        mean_reversion_window=int(os.getenv("MEAN_REVERSION_WINDOW", "30")),
        volatility_window=int(os.getenv("VOLATILITY_WINDOW", "20")),
        momentum_threshold=float(os.getenv("MOMENTUM_THRESHOLD", "0.02")),
        zscore_threshold=float(os.getenv("ZSCORE_THRESHOLD", "1.2")),
        momentum_signal_weight=float(os.getenv("MOMENTUM_SIGNAL_WEIGHT", "0.6")),
        mean_reversion_signal_weight=float(os.getenv("MEAN_REVERSION_SIGNAL_WEIGHT", "0.4")),
        ml_long_threshold=float(os.getenv("ML_LONG_THRESHOLD", "0.55")),
        ml_short_threshold=float(os.getenv("ML_SHORT_THRESHOLD", "0.45")),
        transaction_cost_bps=float(os.getenv("TRANSACTION_COST_BPS", "5.0")),
        order_size=float(os.getenv("ORDER_SIZE", "1.0")),
        allow_short=_as_bool(os.getenv("ALLOW_SHORT"), False),
        asset_class=os.getenv("ASSET_CLASS", "stock"),
        mode=os.getenv("MODE", "paper"),
        broker_name=os.getenv("BROKER_NAME", "paper"),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "60")),
        retrain_interval_minutes=int(os.getenv("RETRAIN_INTERVAL_MINUTES", "60")),
        strategy_tune_interval_minutes=int(os.getenv("STRATEGY_TUNE_INTERVAL_MINUTES", "240")),
        alpaca_api_key=os.getenv("ALPACA_API_KEY", ""),
        alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
        alpaca_base_url=os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
        alpaca_data_url=os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets"),
        alpaca_history_lookback_days=int(os.getenv("ALPACA_HISTORY_LOOKBACK_DAYS", "730")),
        etoro_api_key=os.getenv("ETORO_API_KEY", ""),
        etoro_secret_key=os.getenv("ETORO_SECRET_KEY", ""),
        news_enabled=_as_bool(os.getenv("NEWS_ENABLED"), True),
        news_rss_urls=_as_list(os.getenv("NEWS_RSS_URLS"), default_news_urls),
        news_aliases=_as_list(os.getenv("NEWS_ALIASES"), [os.getenv("SYMBOL", "AAPL")]),
        news_max_items=int(os.getenv("NEWS_MAX_ITEMS", "40")),
        news_bullish_threshold=float(os.getenv("NEWS_BULLISH_THRESHOLD", "0.05")),
        news_bearish_threshold=float(os.getenv("NEWS_BEARISH_THRESHOLD", "-0.05")),
        sector_enabled=_as_bool(os.getenv("SECTOR_ENABLED"), True),
        symbol_sector_etf=os.getenv("SYMBOL_SECTOR_ETF", "XLK"),
        sector_symbols=_as_list(os.getenv("SECTOR_SYMBOLS"), default_sector_symbols),
        sector_bullish_threshold=float(os.getenv("SECTOR_BULLISH_THRESHOLD", "0.10")),
        sector_bearish_threshold=float(os.getenv("SECTOR_BEARISH_THRESHOLD", "-0.10")),
        context_refresh_minutes=int(os.getenv("CONTEXT_REFRESH_MINUTES", "30")),
        sector_rotation_top_n=int(os.getenv("SECTOR_ROTATION_TOP_N", "2")),
        sector_rotation_lookback_bars=int(os.getenv("SECTOR_ROTATION_LOOKBACK_BARS", "5")),
        tuning_enabled=_as_bool(os.getenv("TUNING_ENABLED"), True),
        adaptive_state_path=Path(os.getenv("ADAPTIVE_STATE_PATH", "models/adaptive_state.json")),
        strategy_doc_path=Path(os.getenv("STRATEGY_DOC_PATH", "Strategy.md")),
        stock_momentum_entry_threshold=float(os.getenv("STOCK_MOMENTUM_ENTRY_THRESHOLD", "0.03")),
        crypto_momentum_entry_threshold=float(os.getenv("CRYPTO_MOMENTUM_ENTRY_THRESHOLD", "0.02")),
        short_breakdown_threshold=float(os.getenv("SHORT_BREAKDOWN_THRESHOLD", "0.05")),
        min_position_value_usd=float(os.getenv("MIN_POSITION_VALUE_USD", "1200")),
        max_position_value_usd=float(os.getenv("MAX_POSITION_VALUE_USD", "5000")),
        max_concurrent_positions=int(os.getenv("MAX_CONCURRENT_POSITIONS", "10")),
        stock_stop_loss_pct=float(os.getenv("STOCK_STOP_LOSS_PCT", "0.05")),
        crypto_stop_loss_pct=float(os.getenv("CRYPTO_STOP_LOSS_PCT", "0.08")),
        risk_reward_ratio=float(os.getenv("RISK_REWARD_RATIO", "2.0")),
        pause_crypto=_as_bool(os.getenv("PAUSE_CRYPTO"), False),
        no_new_entries_after_ny=os.getenv("NO_NEW_ENTRIES_AFTER_NY", "10:30"),
        friday_flatten_enabled=_as_bool(os.getenv("FRIDAY_FLATTEN_ENABLED"), False),
        friday_flatten_after_ny=os.getenv("FRIDAY_FLATTEN_AFTER_NY", "15:00"),
        require_post_earnings_for_longs=_as_bool(os.getenv("REQUIRE_POST_EARNINGS_FOR_LONGS"), False),
        post_earnings_allowlist=_as_list(os.getenv("POST_EARNINGS_ALLOWLIST"), []),
        short_size_multiplier=float(os.getenv("SHORT_SIZE_MULTIPLIER", "0.5")),
        max_short_exposure_fraction=float(os.getenv("MAX_SHORT_EXPOSURE_FRACTION", "0.5")),
        max_new_orders_per_cycle=int(os.getenv("MAX_NEW_ORDERS_PER_CYCLE", "3")),
        event_guard_enabled=_as_bool(os.getenv("EVENT_GUARD_ENABLED"), True),
        event_calendar_utc=_as_list(os.getenv("EVENT_CALENDAR_UTC"), default_event_calendar_utc),
        event_pre_reduce_hours=int(os.getenv("EVENT_PRE_REDUCE_HOURS", "24")),
        event_post_no_entry_minutes=int(os.getenv("EVENT_POST_NO_ENTRY_MINUTES", "5")),
        event_pre_reduce_exposure_fraction=float(os.getenv("EVENT_PRE_REDUCE_EXPOSURE_FRACTION", "0.5")),
        webhook_url=os.getenv("WEBHOOK_URL", ""),
        notify_email_to=os.getenv("NOTIFY_EMAIL_TO", ""),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        model_path=Path(os.getenv("MODEL_PATH", "models/model.joblib")),
        report_dir=Path(os.getenv("REPORT_DIR", "reports")),
        log_dir=Path(os.getenv("LOG_DIR", "logs")),
    )

    settings.model_path.parent.mkdir(parents=True, exist_ok=True)
    settings.adaptive_state_path.parent.mkdir(parents=True, exist_ok=True)
    settings.report_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    return settings
