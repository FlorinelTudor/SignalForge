# TradeFlow: Self-Learning Trading Bot

TradeFlow is an end-to-end Python trading bot with:
- Historical + near real-time data collection
- Combined momentum + mean-reversion strategy
- ML-based decision gating with periodic retraining
- Internet news scraping + sentiment context (RSS)
- Sector-strength regime context from sector ETFs
- Adaptive threshold tuning with automatic strategy journaling
- Backtesting pipeline with report artifacts
- Paper/live broker abstraction (paper + Alpaca implemented)
- Monitoring + completion notifications (webhook/email)

## 1) Environment Setup

```bash
./scripts/setup.sh
cp .env.example .env
```

Edit `.env` with your symbol, risk settings, and broker credentials.
For portfolio mode, set `SYMBOLS` (comma-separated) and `SYMBOL_SECTOR_MAP` (`SYM:SECTOR_ETF` pairs).

## 2) Run Full Setup + Initial Trade Cycle

```bash
source .venv/bin/activate
python -m tradeflow_bot --action setup --data-source yfinance
```

This command will:
1. Train/retrain the ML model.
2. Backtest the blended strategy.
3. Refresh news + sector context.
4. Run one initial trade cycle.
5. Send `TradeFlow setup complete` notification.

## 3) Backtest Only

```bash
python -m tradeflow_bot --action backtest --data-source yfinance
```

Artifacts are saved in `reports/`.

## 3b) Backtest + Improve From Alpaca Trade History

```bash
python -m tradeflow_bot --action backtest-improve --data-source alpaca
```

This will:
- run backtest
- pull Alpaca fill history (fallback to filled orders if fills are empty)
- scan history across the configured lookback window (`ALPACA_HISTORY_LOOKBACK_DAYS`, default 730)
- compute realized trade metrics
- apply strategy parameter suggestions into `.env`
- save a JSON improvement report in `reports/`

## 3c) Strategy-Only Autoresearch

TradeFlow includes a constrained `autoresearch` sandbox:

- `autoresearch_trading/candidate_strategy.py`
- `autoresearch_trading/evaluator.py`
- `autoresearch_trading/program.md`

This follows the fixed-evaluator pattern:

- the candidate strategy file is the editable surface
- evaluator and promotion rules stay fixed
- live execution code is not editable by the research loop

Evaluate the current candidate strategy on the configured live basket:

```bash
python -m tradeflow_bot --action autoresearch-eval --data-source synthetic
```

If the candidate clears the promotion gate, the best artifact is written to:

- `reports/autoresearch_best.json`

Promote approved strategy parameters into `.env` and journal the result:

```bash
python -m tradeflow_bot --action autoresearch-promote
```

## 4) Continuous Operation

```bash
python -m tradeflow_bot --action run-loop --data-source yfinance
```

Cycle-level logs and notifications are written to `logs/`.
Trade decisions are written to `logs/trades_v4.csv`.

## Broker Notes

- `BROKER_NAME=paper`: fully local simulated execution.
- `BROKER_NAME=alpaca`: live/paper account execution through Alpaca API keys.
- `BROKER_NAME=etoro`: stub only. eToro does not currently expose a public official retail trading API in this implementation.

## Data Source Notes

- `--data-source yfinance`: no credentials required, but can be rate-limited.
- `--data-source alpaca`: authenticated market data via Alpaca (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_DATA_URL`).
- `--data-source synthetic`: offline test mode for local validation.

## Self-Learning + Strategy Documentation

- Adaptive tuning runs every `STRATEGY_TUNE_INTERVAL_MINUTES` (if `TUNING_ENABLED=true`).
- Tuned thresholds are persisted in `models/adaptive_state.json`.
- Every tuning event appends an entry to `Strategy.md`.
- Every successful autoresearch promotion also appends an entry to `Strategy.md`.
- News/sector context settings are controlled with `NEWS_*` and `SECTOR_*` env variables.
- Imported policy layer supports:
  - asset-aware momentum thresholds (`STOCK_MOMENTUM_ENTRY_THRESHOLD`, `CRYPTO_MOMENTUM_ENTRY_THRESHOLD`)
  - breakdown shorts (`SHORT_BREAKDOWN_THRESHOLD`)
  - position value range (`MIN_POSITION_VALUE_USD`, `MAX_POSITION_VALUE_USD`)
  - stop/target policy (`STOCK_STOP_LOSS_PCT`, `CRYPTO_STOP_LOSS_PCT`, `RISK_REWARD_RATIO`)
  - crypto pause (`PAUSE_CRYPTO`), time gate (`NO_NEW_ENTRIES_AFTER_NY`)
  - Friday flattening (`FRIDAY_FLATTEN_ENABLED`, `FRIDAY_FLATTEN_AFTER_NY`)
  - post-earnings long gate (`REQUIRE_POST_EARNINGS_FOR_LONGS`, `POST_EARNINGS_ALLOWLIST`)
  - multi-symbol portfolio controls (`SYMBOLS`, `SYMBOL_SECTOR_MAP`, `MAX_CONCURRENT_POSITIONS`, `MAX_SHORT_EXPOSURE_FRACTION`)
  - event guard rails (`EVENT_*`) and per-cycle cap (`MAX_NEW_ORDERS_PER_CYCLE`)
  - sector-rotation gate (`SECTOR_ROTATION_TOP_N`, `SECTOR_ROTATION_LOOKBACK_BARS`)

## Multi-Symbol Allocation

- The engine now evaluates all symbols in `SYMBOLS` each cycle.
- Candidates are ranked by computed signal strength and then filtered by:
  - max concurrent positions
  - max one open position per sector (from `SYMBOL_SECTOR_MAP`)
  - max short exposure fraction
  - per-position USD sizing band
- Portfolio-level cycle summary notifications are emitted in run-loop mode.

## Notifications

Configure either:
- `WEBHOOK_URL` for webhook notifications (Slack/Discord-compatible payload), or
- SMTP values (`NOTIFY_EMAIL_TO`, `SMTP_*`) for email.

## Safety Notes

- No strategy can guarantee profit.
- Run with paper mode first and validate behavior before live deployment.
- Tune costs/slippage and position sizing for your market.
