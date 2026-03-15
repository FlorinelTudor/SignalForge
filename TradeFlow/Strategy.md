# Strategy

TradeFlow strategy combines:
- Momentum + mean-reversion rule signal
- ML probability gating
- News sentiment context from RSS sources
- Sector-strength regime context from sector ETFs
- Adaptive threshold tuning

Automatic tuning updates are appended below by the bot.
## 2026-02-11T20:08:28.765126+00:00
- momentum_threshold: 0.015
- zscore_threshold: 0.9
- ml_long_threshold: 0.55
- ml_short_threshold: 0.4275
- objective: 1.006242
- backtest_total_return: 0.023263
- backtest_sharpe: 1.002907
- backtest_max_drawdown: -0.004391

## Imported External Learnings (build.twin.so)

### Evolution Snapshot

| Version | Dates | Key Rules |
|---|---|---|
| v1.0 | Jan 28, 2026 | >3% stock momentum, >2% crypto momentum, 5% stock stop, 8% crypto stop, 2:1 reward-risk |
| v1.1 | Jan 30, 2026 | Added sector tracking, entry timing, chart patterns |
| v1.2 | Feb 2, 2026 | Reduced position value to $1.2k-$1.8k, paused crypto, sector diversification |
| v1.3 | Feb 6, 2026 | Tightened stock stops to 4%, Friday risk management, breakdown focus |
| v1.4 | Feb 8, 2026 | Post-earnings longs only, 50% short allocation, no entries after 10:30 ET, max 1 position per sector |

### Imported Performance Notes

- Portfolio change: +$234.94 (+0.23%) on ~$25+ trades
- Win rate improved from 25% to 61.5%
- Profit factor: 1.19
- Max drawdown: 1.05%
- Practical lessons:
  - stocks outperformed crypto in this sample
  - smaller position sizing had the strongest positive impact
  - post-earnings longs and catalyst-driven shorts outperformed
  - Friday de-risking reduced gap risk

### How These Learnings Are Applied In TradeFlow

- Enforced via policy layer in code:
  - `STOCK_MOMENTUM_ENTRY_THRESHOLD`, `CRYPTO_MOMENTUM_ENTRY_THRESHOLD`
  - `SHORT_BREAKDOWN_THRESHOLD`
  - `MIN_POSITION_VALUE_USD`, `MAX_POSITION_VALUE_USD`
  - `STOCK_STOP_LOSS_PCT`, `CRYPTO_STOP_LOSS_PCT`, `RISK_REWARD_RATIO`
  - `PAUSE_CRYPTO`, `NO_NEW_ENTRIES_AFTER_NY`
  - `FRIDAY_FLATTEN_ENABLED`, `FRIDAY_FLATTEN_AFTER_NY`
  - `REQUIRE_POST_EARNINGS_FOR_LONGS`, `POST_EARNINGS_ALLOWLIST`
  - `SHORT_SIZE_MULTIPLIER`
- Current scope note:
  - live engine now supports multi-symbol allocation via `SYMBOLS` with portfolio constraints:
    - max one open position per sector (`SYMBOL_SECTOR_MAP`)
    - max concurrent open positions
    - short exposure cap

### Open Tracking Questions

- Do post-earnings longs still outperform over next 50 trades?
- Does Friday flatten improve expectancy after costs?
- Are breakdown shorts still higher quality than longs by signal strength?
- Which sector+time combinations produce the best risk-adjusted returns?

## Live Profile (2026-02-11)

- Multi-symbol universe enabled:
  - `AAPL,LMT,LUV,CAT,DVA,MOH,IT,CRVL`
- Sector map enabled for portfolio constraints:
  - `AAPL:XLK,LMT:XLI,LUV:XLY,CAT:XLI,DVA:XLV,MOH:XLV,IT:XLK,CRVL:XLV`
- Portfolio limits:
  - max 8 concurrent positions
  - max 1 open position per sector
  - short exposure cap 50% of equity
- Entry windows and risk:
  - no new entries after 15:30 NY
  - Friday flatten at 15:30 NY
  - post-earnings long gate enabled with allowlist: `AAPL,LUV,CAT,DVA,LMT`
  - position value band: $1.2k-$1.8k

## 2026-02-11T21:22:59+00:00

- action: `backtest-improve` (Alpaca data source)
- backtest symbol: `AAPL`
- backtest total_return: `0.040530`
- backtest sharpe: `4.857363`
- backtest max_drawdown: `-0.033588`
- backtest trades: `44`
- alpaca_history_records_processed: `0`
- alpaca_closed_trades: `0`
- env_suggestions_applied: `0`
- note: Alpaca account returned no fills/orders to learn from in this run.

## 2026-02-11T21:25:05+00:00

- action: `backtest-improve` (Alpaca data source, elevated network run)
- backtest symbol: `AAPL`
- backtest total_return: `0.040530`
- backtest sharpe: `4.857363`
- backtest max_drawdown: `-0.033588`
- backtest trades: `44`
- alpaca_history_records_processed: `0`
- alpaca_closed_trades: `0`
- env_suggestions_applied: `0`
- note: history learner now falls back from account fills to filled orders; this account currently has no filled history to optimize from.

## 2026-02-11T21:40:03+00:00

- change_type: live-trading enablement for paper-history accumulation
- ML_LONG_THRESHOLD: `0.50 -> 0.30`
- ML_SHORT_THRESHOLD: `0.50 -> 0.35`
- execution_policy_fix: short notional floor now respects `SHORT_SIZE_MULTIPLIER` scaling (prevents all shorts being filtered out when using 0.5x short sizing)
- objective: increase trade throughput so Alpaca filled history can be learned from in subsequent `backtest-improve` runs

## 2026-02-11T21:44:25+00:00

- broker_execution_fix: fractional short sells are rounded to whole-share quantities for Alpaca (fractional short opens are rejected by Alpaca API)
- paper_cycle_validation: `orders_sent=3` with accepted orders on `LMT` (short), `LUV` (long), `MOH` (short)
- continuous_operation: run-loop started and confirmed active with live cycle notifications and trade log updates

## 2026-02-11T22:36:35+00:00

- history_engine_update: Alpaca history fetch now scans up to configured lookback (`ALPACA_HISTORY_LOOKBACK_DAYS=730`) using deep pagination and UTC cutoff filtering.
- diagnostic: account currently reports orders in `accepted` state only and zero `filled`/`FILL` activities, so no closed-trade learning updates can be applied yet.
- next_trigger_for_learning: first completed fills/round-trips appearing in Alpaca history.

## 2026-02-11T23:15:08+00:00

- duplicate_order_protection: run-cycle now skips placement when a matching open order (`symbol` + `side`) already exists at broker.
- validation_result: with many existing open orders, cycle returned `orders_sent=0` and logged `Skipped duplicate: matching open order already exists.` for duplicate candidates.

## 2026-03-05T13:20:00+00:00

- strategy_upgrade: added event-driven guard rails (`EVENT_*`) for NFP/CPI/FOMC windows.
- pre_event_risk: supports automatic exposure reduction in the configured pre-event window.
- post_event_gate: blocks new entries during the configured minutes after event release.
- sector_rotation: new-entry filtering supports top-N sector momentum gate (`SECTOR_ROTATION_TOP_N`, `SECTOR_ROTATION_LOOKBACK_BARS`).
- execution_guard: added `MAX_NEW_ORDERS_PER_CYCLE` cap to avoid over-deployment.

## 2026-02-12T00:09:28.520909+00:00
- momentum_threshold: 0.0187
- zscore_threshold: 1.0
- ml_long_threshold: 0.5
- ml_short_threshold: 0.3675
- objective: 10.021400
- backtest_total_return: 0.062075
- backtest_sharpe: 10.014262
- backtest_max_drawdown: -0.017591


## 2026-03-05T13:15:36.561169+00:00
- momentum_threshold: 0.0112
- zscore_threshold: 0.75
- ml_long_threshold: 0.5
- ml_short_threshold: 0.35
- objective: 9.222410
- backtest_total_return: 0.194477
- backtest_sharpe: 9.205360
- backtest_max_drawdown: -0.072816

## 2026-03-05T14:48:56.785017+00:00
- momentum_threshold: 0.015
- zscore_threshold: 0.75
- ml_long_threshold: 0.5
- ml_short_threshold: 0.35
- objective: 7.918246
- backtest_total_return: 0.051620
- backtest_sharpe: 7.913426
- backtest_max_drawdown: -0.018348


## 2026-03-08T16:00:51.344886+00:00
- momentum_threshold: 0.015
- zscore_threshold: 0.75
- ml_long_threshold: 0.5
- ml_short_threshold: 0.35
- objective: 11.738646
- backtest_total_return: 0.072212
- backtest_sharpe: 11.728589
- backtest_max_drawdown: -0.014616

## 2026-03-11T10:04:57+00:00

- change_type: latest-news defensive update (macro event week)
- macro_context:
  - BLS Employment Situation (Feb 2026, released Mar 6): payroll contraction and higher unemployment -> slower growth signal.
  - CPI release day (Mar 11) + PPI (Mar 12) + FOMC (Mar 18) -> elevated event risk cluster.
- parameter_changes:
  - `ML_LONG_THRESHOLD`: `0.50 -> 0.55` (stricter long confirmation)
  - `ML_SHORT_THRESHOLD`: `0.35 -> 0.40` (stricter short confirmation)
  - `MAX_NEW_ORDERS_PER_CYCLE`: `3 -> 1` (lower intraday deployment)
  - `EVENT_CALENDAR_UTC`: now prioritizes `2026-03-11`, `2026-03-12`, `2026-03-18`
  - `EVENT_PRE_REDUCE_HOURS`: `24 -> 36`
  - `EVENT_POST_NO_ENTRY_MINUTES`: `5 -> 30`
  - `EVENT_PRE_REDUCE_EXPOSURE_FRACTION`: `0.50 -> 0.35`
  - `SECTOR_ROTATION_TOP_N`: `2 -> 1`
- objective: preserve capital through macro data/FOMC week, then re-expand risk after event volatility normalizes.

## 2026-03-11T10:06:34.591387+00:00
- momentum_threshold: 0.0112
- zscore_threshold: 0.9375
- ml_long_threshold: 0.5225
- ml_short_threshold: 0.4
- objective: 12.752757
- backtest_total_return: 0.069033
- backtest_sharpe: 12.742983
- backtest_max_drawdown: -0.013441

