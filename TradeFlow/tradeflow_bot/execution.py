from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from tradeflow_bot.adaptive import AdaptiveStrategyManager
from tradeflow_bot.backtest import BacktestReport, persist_backtest, run_backtest
from tradeflow_bot.brokers.base import Broker, OrderResult
from tradeflow_bot.config import Settings
from tradeflow_bot.data import DataClient
from tradeflow_bot.ml import ModelManager
from tradeflow_bot.news import NewsScraper, NewsSnapshot
from tradeflow_bot.notifier import Notifier
from tradeflow_bot.sector import SectorSnapshot, SectorStrengthAnalyzer
from tradeflow_bot.strategy import StrategyParams, blended_signal, engineer_features, rule_signal

NY_TZ = ZoneInfo("America/New_York")


def _parse_hhmm(value: str, default: dt_time) -> dt_time:
    try:
        hour_s, minute_s = value.strip().split(":", 1)
        hour = int(hour_s)
        minute = int(minute_s)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return dt_time(hour=hour, minute=minute)
    except Exception:
        pass
    return default


@dataclass
class MarketContext:
    news_sentiment: float = 0.0
    sector_strength: float = 0.0
    headline_count: int = 0
    sector_rank: int = 0
    sector_count: int = 0


@dataclass
class CycleDecision:
    timestamp: str
    symbol: str
    sector: str
    close: float
    rule_signal: float
    ml_probability: float
    final_signal: float
    signal_strength: float
    news_sentiment: float
    sector_strength: float
    stop_price: float | None
    target_price: float | None
    current_qty: float
    target_qty: float
    delta_qty: float
    order_result: OrderResult | None


@dataclass
class PortfolioCycleDecision:
    timestamp: str
    decisions: list[CycleDecision]
    orders_sent: int


class TradingEngine:
    def __init__(
        self,
        settings: Settings,
        data_client: DataClient,
        broker: Broker,
        model_manager: ModelManager,
        notifier: Notifier,
    ) -> None:
        self.settings = settings
        self.data_client = data_client
        self.broker = broker
        self.model_manager = model_manager
        self.notifier = notifier
        self.trades_path = settings.log_dir / "trades_v4.csv"

        self.news_scraper = (
            NewsScraper(
                rss_urls=settings.news_rss_urls or [],
                max_items=settings.news_max_items,
            )
            if settings.news_enabled
            else None
        )
        self.sector_analyzer = (
            SectorStrengthAnalyzer(symbols=settings.sector_symbols or [])
            if settings.sector_enabled
            else None
        )
        self.adaptive = AdaptiveStrategyManager(
            state_path=settings.adaptive_state_path,
            strategy_doc_path=settings.strategy_doc_path,
        )

        self._cached_context: dict[str, MarketContext] = {}
        self._last_context_refresh_at: dict[str, datetime] = {}
        self._event_times_utc = self._parse_event_times(self.settings.event_calendar_utc or [])
        self._ensure_strategy_doc()

    @property
    def strategy_params(self) -> StrategyParams:
        return StrategyParams(
            momentum_window=self.settings.momentum_window,
            mean_reversion_window=self.settings.mean_reversion_window,
            volatility_window=self.settings.volatility_window,
            momentum_threshold=self.settings.momentum_threshold,
            zscore_threshold=self.settings.zscore_threshold,
        )

    def prepare_model(self) -> pd.DataFrame:
        primary = self._primary_symbol()
        raw = self.data_client.fetch_historical(
            symbol=primary,
            interval=self.settings.interval,
            days=self.settings.history_days,
        )
        feat = engineer_features(raw, self.strategy_params)

        if self.model_manager.should_retrain(self.settings.retrain_interval_minutes):
            result = self.model_manager.train(feat)
            msg = (
                f"Model retrained for {primary}: samples={result.samples}, "
                f"accuracy={result.accuracy:.4f}, trained_at={result.trained_at.isoformat()}"
            )
            self.notifier.send("TradeFlow model update", msg)

        probabilities = self.model_manager.predict_bullish_probability(feat)
        self._maybe_tune_strategy(feat, probabilities)
        return feat

    def run_backtest(self) -> tuple[BacktestReport, Path, Path]:
        primary = self._primary_symbol()
        feat = self.prepare_model()
        probabilities = self.model_manager.predict_bullish_probability(feat)
        context = self._get_market_context(primary, force_refresh=True)
        signal = self._contextual_signal(feat, probabilities, context, primary)
        results, report = run_backtest(
            df=feat,
            signal=signal,
            transaction_cost_bps=self.settings.transaction_cost_bps,
            interval=self.settings.interval,
            symbol=primary,
        )
        csv_path, json_path = persist_backtest(results, report, self.settings.report_dir)
        return report, csv_path, json_path

    def run_cycle(self) -> CycleDecision | PortfolioCycleDecision:
        symbols = self._symbols()
        primary = symbols[0]

        if self.model_manager.should_retrain(self.settings.retrain_interval_minutes):
            raw = self.data_client.fetch_historical(
                symbol=primary,
                interval=self.settings.interval,
                days=max(self.settings.history_days, 30),
            )
            feat = engineer_features(raw, self.strategy_params)
            self.model_manager.train(feat)

        if self.adaptive.should_tune(self.settings.strategy_tune_interval_minutes):
            raw = self.data_client.fetch_historical(
                symbol=primary,
                interval=self.settings.interval,
                days=max(self.settings.history_days, 30),
            )
            feat = engineer_features(raw, self.strategy_params)
            probs = self.model_manager.predict_bullish_probability(feat)
            self._maybe_tune_strategy(feat, probs)

        portfolio_decision = self._run_portfolio_cycle(symbols)
        if len(symbols) == 1:
            return portfolio_decision.decisions[0]
        return portfolio_decision

    def _run_portfolio_cycle(self, symbols: list[str]) -> PortfolioCycleDecision:
        summary = self._safe_account_summary()
        positions_map = self._extract_positions_map(summary)
        open_orders = self._safe_open_orders()
        open_pairs = {
            (str(o.get("symbol", "")).upper(), str(o.get("side", "")).lower())
            for o in open_orders
            if str(o.get("symbol", "")).strip() and str(o.get("side", "")).strip()
        }

        decisions: list[CycleDecision] = []
        for symbol in symbols:
            current_qty = float(positions_map.get(symbol, 0.0))
            decisions.append(self._evaluate_symbol(symbol=symbol, current_qty=current_qty))

        top_sectors = self._top_sectors_by_relative_strength()
        self._apply_portfolio_constraints(decisions, summary, top_sectors=top_sectors)

        orders_sent = 0
        new_orders_sent = 0
        for decision in decisions:
            if abs(decision.delta_qty) <= 1e-9:
                self._log_trade(decision)
                continue
            side = "buy" if decision.delta_qty > 0 else "sell"
            opening_new = abs(decision.current_qty) <= 1e-9 and abs(decision.target_qty) > 1e-9
            if opening_new and new_orders_sent >= max(self.settings.max_new_orders_per_cycle, 0):
                decision.order_result = OrderResult(
                    accepted=False,
                    order_id="",
                    side=side,
                    qty=abs(decision.delta_qty),
                    message="Skipped: max new orders per cycle reached.",
                )
                self._log_trade(decision)
                continue
            if (decision.symbol.upper(), side) in open_pairs:
                decision.order_result = OrderResult(
                    accepted=False,
                    order_id="",
                    side=side,
                    qty=abs(decision.delta_qty),
                    message="Skipped duplicate: matching open order already exists.",
                )
                self._log_trade(decision)
                continue
            order_result = self.broker.place_order(decision.symbol, side, abs(decision.delta_qty))
            decision.order_result = order_result
            if order_result.accepted:
                open_pairs.add((decision.symbol.upper(), side))
                orders_sent += 1
                if opening_new:
                    new_orders_sent += 1
            self._log_trade(decision)

        return PortfolioCycleDecision(
            timestamp=datetime.now(timezone.utc).isoformat(),
            decisions=decisions,
            orders_sent=orders_sent,
        )

    def _evaluate_symbol(self, symbol: str, current_qty: float) -> CycleDecision:
        raw = self.data_client.fetch_historical(
            symbol=symbol,
            interval=self.settings.interval,
            days=max(self.settings.history_days, 30),
        ).tail(1200)
        feat = engineer_features(raw, self.strategy_params)

        probabilities = self.model_manager.predict_bullish_probability(feat)
        context = self._get_market_context(symbol, force_refresh=False)
        rules = rule_signal(feat, self.strategy_params)
        final_signal_series = self._contextual_signal(feat, probabilities, context, symbol)

        latest_idx = feat.index[-1]
        latest_close = float(feat["close"].iloc[-1])
        rule_sig = float(rules.iloc[-1])
        ml_prob = float(probabilities.iloc[-1])
        pre_policy_signal = float(final_signal_series.iloc[-1])

        final_sig = self._apply_trade_policies(pre_policy_signal, latest_idx, current_qty, symbol)
        signal_strength = self._signal_strength(rule_sig, ml_prob, context, final_sig)
        stop_price, target_price = self._risk_levels(final_sig, latest_close)

        target_qty = self._target_qty(final_sig, latest_close, signal_strength)
        delta_qty = target_qty - current_qty

        return CycleDecision(
            timestamp=str(latest_idx),
            symbol=symbol,
            sector=self._symbol_sector(symbol),
            close=latest_close,
            rule_signal=rule_sig,
            ml_probability=ml_prob,
            final_signal=final_sig,
            signal_strength=signal_strength,
            news_sentiment=context.news_sentiment,
            sector_strength=context.sector_strength,
            stop_price=stop_price,
            target_price=target_price,
            current_qty=current_qty,
            target_qty=target_qty,
            delta_qty=delta_qty,
            order_result=None,
        )

    def _apply_portfolio_constraints(
        self,
        decisions: list[CycleDecision],
        account_summary: dict,
        top_sectors: set[str] | None = None,
    ) -> None:
        managed_symbols = {d.symbol for d in decisions}
        positions_map = self._extract_positions_map(account_summary)

        final_targets: dict[str, float] = {}
        for d in decisions:
            if abs(d.current_qty) <= 1e-9:
                final_targets[d.symbol] = 0.0
            elif abs(d.target_qty) <= 1e-9:
                final_targets[d.symbol] = 0.0
            elif d.current_qty * d.target_qty > 0:
                final_targets[d.symbol] = d.target_qty
            else:
                final_targets[d.symbol] = 0.0

        unmanaged_open_symbols = {
            symbol
            for symbol, qty in positions_map.items()
            if symbol not in managed_symbols and abs(float(qty)) > 1e-9
        }

        sector_counts: dict[str, int] = {}
        for symbol in unmanaged_open_symbols:
            sector = self._symbol_sector(symbol)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        for d in decisions:
            if abs(final_targets.get(d.symbol, 0.0)) > 1e-9:
                sector_counts[d.sector] = sector_counts.get(d.sector, 0) + 1

        open_count = len(unmanaged_open_symbols) + sum(
            1 for d in decisions if abs(final_targets.get(d.symbol, 0.0)) > 1e-9
        )

        equity = float(account_summary.get("equity") or 0.0)
        if equity <= 0:
            equity = self.settings.max_position_value_usd * max(self.settings.max_concurrent_positions, 1)
        short_limit_value = max(0.0, self.settings.max_short_exposure_fraction) * equity
        short_exposure = self._estimate_short_exposure(account_summary)
        short_exposure += sum(
            abs(final_targets[d.symbol] * d.close)
            for d in decisions
            if final_targets.get(d.symbol, 0.0) < 0
        )

        open_candidates = [
            d
            for d in decisions
            if abs(d.target_qty) > 1e-9 and abs(final_targets.get(d.symbol, 0.0)) <= 1e-9
        ]
        open_candidates.sort(key=lambda x: x.signal_strength, reverse=True)

        for d in open_candidates:
            if open_count >= self.settings.max_concurrent_positions:
                break
            if sector_counts.get(d.sector, 0) >= 1:
                continue
            if top_sectors and d.sector.upper() not in top_sectors:
                continue

            qty = d.target_qty
            if qty < 0:
                proposed_short_value = abs(qty * d.close)
                remaining = short_limit_value - short_exposure
                if remaining <= 0:
                    continue
                if proposed_short_value > remaining:
                    qty = -remaining / max(d.close, 1e-9)
                    proposed_short_value = abs(qty * d.close)
                # Short quantities are already scaled by SHORT_SIZE_MULTIPLIER in _target_qty,
                # so apply the minimum notional against the same scaled baseline.
                effective_min_short_value = self.settings.min_position_value_usd * max(
                    self.settings.short_size_multiplier, 0.0
                )
                if effective_min_short_value > 0 and proposed_short_value < effective_min_short_value:
                    continue

            final_targets[d.symbol] = qty
            open_count += 1
            sector_counts[d.sector] = sector_counts.get(d.sector, 0) + 1
            if qty < 0:
                short_exposure += abs(qty * d.close)

        if self._in_pre_event_reduce_window():
            fraction = max(0.0, min(1.0, self.settings.event_pre_reduce_exposure_fraction))
            for symbol, qty in list(final_targets.items()):
                final_targets[symbol] = qty * fraction

        for d in decisions:
            d.target_qty = final_targets.get(d.symbol, 0.0)
            d.delta_qty = d.target_qty - d.current_qty
            d.final_signal = 1.0 if d.target_qty > 0 else -1.0 if d.target_qty < 0 else 0.0
            if d.final_signal == 0.0:
                d.stop_price, d.target_price = None, None
                d.signal_strength = 0.0

    def run_loop(self) -> None:
        while True:
            try:
                decision = self.run_cycle()
                if isinstance(decision, PortfolioCycleDecision):
                    active = sum(1 for d in decision.decisions if abs(d.target_qty) > 1e-9)
                    self.notifier.send(
                        "TradeFlow portfolio cycle",
                        f"symbols={len(decision.decisions)}, active={active}, orders_sent={decision.orders_sent}",
                    )
                else:
                    self.notifier.send(
                        "TradeFlow cycle",
                        (
                            f"{decision.timestamp} {decision.symbol} close={decision.close:.2f}, "
                            f"signal={decision.final_signal}, strength={decision.signal_strength:.1f}/10, "
                            f"news={decision.news_sentiment:.3f}, "
                            f"sector={decision.sector_strength:.3f}, target_qty={decision.target_qty}, "
                            f"delta={decision.delta_qty}"
                        ),
                    )
            except Exception as exc:
                self.notifier.send("TradeFlow error", str(exc))
            time.sleep(self.settings.poll_interval_seconds)

    def _maybe_tune_strategy(self, feat: pd.DataFrame, probabilities: pd.Series) -> None:
        if not self.settings.tuning_enabled:
            return
        if not self.adaptive.should_tune(self.settings.strategy_tune_interval_minutes):
            return

        result = self.adaptive.tune(
            df=feat,
            probabilities=probabilities,
            symbol=self._primary_symbol(),
            interval=self.settings.interval,
            transaction_cost_bps=self.settings.transaction_cost_bps,
            allow_short=self.settings.allow_short,
            momentum_window=self.settings.momentum_window,
            mean_reversion_window=self.settings.mean_reversion_window,
            volatility_window=self.settings.volatility_window,
            current_momentum_threshold=self.settings.momentum_threshold,
            current_zscore_threshold=self.settings.zscore_threshold,
            current_ml_long_threshold=self.settings.ml_long_threshold,
            current_ml_short_threshold=self.settings.ml_short_threshold,
        )

        self.settings.momentum_threshold = result.momentum_threshold
        self.settings.zscore_threshold = result.zscore_threshold
        self.settings.ml_long_threshold = result.ml_long_threshold
        self.settings.ml_short_threshold = result.ml_short_threshold

        self.notifier.send(
            "TradeFlow strategy tuned",
            (
                f"Updated thresholds: momentum={result.momentum_threshold}, "
                f"zscore={result.zscore_threshold}, ml_long={result.ml_long_threshold}, "
                f"ml_short={result.ml_short_threshold}, objective={result.objective:.4f}. "
                f"Documented in {self.settings.strategy_doc_path}."
            ),
        )

    def _get_market_context(self, symbol: str, force_refresh: bool) -> MarketContext:
        if not force_refresh and not self._should_refresh_context(symbol):
            cached = self._cached_context.get(symbol)
            if cached is not None:
                return cached

        context = MarketContext()

        if self.news_scraper is not None:
            try:
                aliases = list(self.settings.news_aliases or []) + [symbol]
                news: NewsSnapshot = self.news_scraper.fetch(symbol=symbol, aliases=aliases)
                context.news_sentiment = news.score
                context.headline_count = news.headline_count
            except Exception:
                pass

        if self.sector_analyzer is not None:
            try:
                sector: SectorSnapshot = self.sector_analyzer.compute(
                    data_client=self.data_client,
                    interval=self.settings.interval,
                    days=min(max(self.settings.history_days, 60), 365),
                    symbol_sector_etf=self._symbol_sector(symbol),
                )
                context.sector_strength = sector.score
                context.sector_rank = sector.sector_rank
                context.sector_count = sector.sector_count
            except Exception:
                pass

        self._cached_context[symbol] = context
        self._last_context_refresh_at[symbol] = datetime.now(timezone.utc)
        return context

    def _should_refresh_context(self, symbol: str) -> bool:
        last = self._last_context_refresh_at.get(symbol)
        if last is None:
            return True
        now = datetime.now(timezone.utc)
        elapsed_minutes = (now - last).total_seconds() / 60.0
        return elapsed_minutes >= self.settings.context_refresh_minutes

    def _contextual_signal(
        self,
        feat: pd.DataFrame,
        probabilities: pd.Series,
        context: MarketContext,
        symbol: str,
    ) -> pd.Series:
        base_signal = blended_signal(
            features=feat,
            params=self.strategy_params,
            bullish_probability=probabilities,
            long_threshold=self.settings.ml_long_threshold,
            short_threshold=self.settings.ml_short_threshold,
            allow_short=self.settings.allow_short,
        )

        context_direction = self._context_direction(context)
        out = base_signal * context_direction
        out = self._policy_filter_series(out, feat, symbol)
        if not self.settings.allow_short:
            out = out.clip(lower=0)
        return out.rename("signal")

    def _context_direction(self, context: MarketContext) -> float:
        bullish_votes = 0
        bearish_votes = 0

        if self.settings.news_enabled:
            if context.news_sentiment >= self.settings.news_bullish_threshold:
                bullish_votes += 1
            elif context.news_sentiment <= self.settings.news_bearish_threshold:
                bearish_votes += 1

        if self.settings.sector_enabled:
            if context.sector_strength >= self.settings.sector_bullish_threshold:
                bullish_votes += 1
            elif context.sector_strength <= self.settings.sector_bearish_threshold:
                bearish_votes += 1

        if bullish_votes == 0 and bearish_votes == 0:
            return 1.0
        if bullish_votes > bearish_votes:
            return 1.0
        if bearish_votes > bullish_votes:
            return -1.0 if self.settings.allow_short else 0.0
        return 0.0

    def _apply_trade_policies(self, signal: float, ts: pd.Timestamp, current_qty: float, symbol: str) -> float:
        if signal == 0:
            return 0.0

        if self.settings.asset_class.strip().lower() == "crypto" and self.settings.pause_crypto:
            return 0.0

        opening_new_long = signal > 0 and current_qty <= 0
        opening_new_short = signal < 0 and current_qty >= 0

        if opening_new_long and self.settings.require_post_earnings_for_longs:
            if not self._symbol_in_post_earnings_allowlist(symbol):
                return 0.0

        if (opening_new_long or opening_new_short) and self._in_post_event_no_entry_window():
            return 0.0

        if (opening_new_long or opening_new_short) and self._is_after_cutoff(ts):
            return 0.0

        if self.settings.friday_flatten_enabled and self._is_friday_after_flatten(ts):
            return 0.0

        return signal

    def _symbol_in_post_earnings_allowlist(self, symbol: str) -> bool:
        allowlist = {s.upper() for s in (self.settings.post_earnings_allowlist or [])}
        return symbol.upper() in allowlist

    def _is_after_cutoff(self, ts: pd.Timestamp) -> bool:
        cutoff = _parse_hhmm(self.settings.no_new_entries_after_ny, dt_time(hour=10, minute=30))
        local_ts = ts.tz_convert(NY_TZ) if ts.tzinfo else ts.tz_localize("UTC").tz_convert(NY_TZ)
        return local_ts.time() > cutoff

    def _is_friday_after_flatten(self, ts: pd.Timestamp) -> bool:
        flatten_cutoff = _parse_hhmm(self.settings.friday_flatten_after_ny, dt_time(hour=15, minute=0))
        local_ts = ts.tz_convert(NY_TZ) if ts.tzinfo else ts.tz_localize("UTC").tz_convert(NY_TZ)
        return local_ts.weekday() == 4 and local_ts.time() >= flatten_cutoff

    def _target_qty(self, signal: float, close_price: float, signal_strength: float) -> float:
        if signal == 0:
            return 0.0

        px = max(close_price, 1e-9)
        strength = max(0.0, min(10.0, signal_strength)) / 10.0
        desired_value = self.settings.min_position_value_usd + strength * (
            self.settings.max_position_value_usd - self.settings.min_position_value_usd
        )
        qty = desired_value / px

        if signal > 0:
            return qty
        if signal < 0 and self.settings.allow_short:
            return -qty * max(self.settings.short_size_multiplier, 0.0)
        return 0.0

    def _log_trade(self, decision: CycleDecision) -> None:
        self.trades_path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.trades_path.exists()
        with self.trades_path.open("a", encoding="utf-8") as f:
            if is_new:
                f.write(
                    "timestamp,symbol,sector,close,rule_signal,ml_probability,final_signal,signal_strength,news_sentiment,sector_strength,stop_price,target_price,current_qty,target_qty,delta_qty,order_accepted,order_id,order_message\n"
                )
            accepted = decision.order_result.accepted if decision.order_result else ""
            order_id = decision.order_result.order_id if decision.order_result else ""
            message = decision.order_result.message if decision.order_result else ""
            f.write(
                f"{decision.timestamp},{decision.symbol},{decision.sector},{decision.close:.6f},{decision.rule_signal},"
                f"{decision.ml_probability:.6f},{decision.final_signal},{decision.signal_strength:.3f},"
                f"{decision.news_sentiment:.6f},{decision.sector_strength:.6f},"
                f"{decision.stop_price},{decision.target_price},{decision.current_qty},"
                f"{decision.target_qty},{decision.delta_qty},{accepted},{order_id},{message}\n"
            )

    def _ensure_strategy_doc(self) -> None:
        path = self.settings.strategy_doc_path
        if path.exists():
            return
        path.write_text(
            "# Strategy\n\n"
            "TradeFlow strategy combines:\n"
            "- Momentum + mean-reversion rule signal\n"
            "- ML probability gating\n"
            "- News sentiment context\n"
            "- Sector strength context\n"
            "- Asset-aware momentum thresholds and risk caps\n"
            "- Adaptive threshold tuning\n"
            "- Multi-symbol portfolio allocation constraints\n\n"
            "Automatic tuning updates are appended below.\n\n",
            encoding="utf-8",
        )

    def _policy_filter_series(self, signal: pd.Series, feat: pd.DataFrame, symbol: str) -> pd.Series:
        out = signal.copy()
        ret_1 = feat["ret_1"].fillna(0.0)
        long_threshold = self._long_momentum_threshold()
        out[(out > 0) & (ret_1 < long_threshold)] = 0
        out[(out < 0) & (ret_1 > -self.settings.short_breakdown_threshold)] = 0

        if self.settings.asset_class.strip().lower() == "crypto" and self.settings.pause_crypto:
            out[:] = 0

        if self.settings.require_post_earnings_for_longs and not self._symbol_in_post_earnings_allowlist(symbol):
            out[out > 0] = 0

        idx_local = out.index.tz_convert(NY_TZ) if out.index.tz is not None else out.index.tz_localize("UTC").tz_convert(NY_TZ)
        cutoff = _parse_hhmm(self.settings.no_new_entries_after_ny, dt_time(hour=10, minute=30))
        late_entries = idx_local.time > cutoff
        previous = out.shift(1).fillna(0)
        new_entries = (previous == 0) & (out != 0)
        out[new_entries & late_entries] = 0

        if self.settings.friday_flatten_enabled:
            flatten_cutoff = _parse_hhmm(self.settings.friday_flatten_after_ny, dt_time(hour=15, minute=0))
            friday_after = (idx_local.weekday == 4) & (idx_local.time >= flatten_cutoff)
            out[friday_after] = 0
        return out

    def _long_momentum_threshold(self) -> float:
        if self.settings.asset_class.strip().lower() == "crypto":
            return self.settings.crypto_momentum_entry_threshold
        return self.settings.stock_momentum_entry_threshold

    def _stop_loss_pct(self) -> float:
        if self.settings.asset_class.strip().lower() == "crypto":
            return self.settings.crypto_stop_loss_pct
        return self.settings.stock_stop_loss_pct

    def _risk_levels(self, signal: float, close_price: float) -> tuple[float | None, float | None]:
        if signal == 0:
            return None, None
        stop_pct = self._stop_loss_pct()
        rr = max(self.settings.risk_reward_ratio, 0.1)
        if signal > 0:
            stop = close_price * (1.0 - stop_pct)
            target = close_price * (1.0 + stop_pct * rr)
            return round(stop, 6), round(target, 6)
        stop = close_price * (1.0 + stop_pct)
        target = close_price * (1.0 - stop_pct * rr)
        return round(stop, 6), round(target, 6)

    def _signal_strength(
        self,
        rule_signal_value: float,
        ml_probability: float,
        context: MarketContext,
        final_signal: float,
    ) -> float:
        if final_signal == 0:
            return 0.0
        ml_edge = abs(ml_probability - 0.5) * 2.0
        context_edge = 0.5 * abs(context.news_sentiment) + 0.5 * abs(context.sector_strength)
        raw = 0.6 * abs(rule_signal_value) + 0.3 * ml_edge + 0.1 * context_edge
        return round(max(0.0, min(10.0, raw * 10.0)), 2)

    def _safe_account_summary(self) -> dict:
        try:
            return self.broker.get_account_summary()
        except Exception:
            return {"positions": {}}

    def _safe_open_orders(self) -> list[dict]:
        try:
            return self.broker.get_open_orders()
        except Exception:
            return []

    def _now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_event_times(values: list[str]) -> list[datetime]:
        out: list[datetime] = []
        for raw in values:
            value = str(raw or "").strip()
            if not value:
                continue
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(value)
            except ValueError:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            out.append(dt.astimezone(timezone.utc))
        out.sort()
        return out

    def _active_event_time(self) -> datetime | None:
        if not self.settings.event_guard_enabled:
            return None
        now = self._now_utc()
        pre = timedelta(hours=max(self.settings.event_pre_reduce_hours, 0))
        post = timedelta(minutes=max(self.settings.event_post_no_entry_minutes, 0))
        for event_ts in self._event_times_utc:
            if event_ts - pre <= now <= event_ts + post:
                return event_ts
        return None

    def _in_pre_event_reduce_window(self) -> bool:
        event_ts = self._active_event_time()
        if event_ts is None:
            return False
        now = self._now_utc()
        return now <= event_ts

    def _in_post_event_no_entry_window(self) -> bool:
        event_ts = self._active_event_time()
        if event_ts is None:
            return False
        now = self._now_utc()
        return now >= event_ts

    def _top_sectors_by_relative_strength(self) -> set[str]:
        symbols = [s.upper() for s in (self.settings.sector_symbols or []) if s]
        if not symbols:
            return set()

        lookback = max(int(self.settings.sector_rotation_lookback_bars), 1)
        momentum: dict[str, float] = {}
        days = min(max(self.settings.history_days, 60), 365)
        for etf in symbols:
            try:
                df = self.data_client.fetch_historical(symbol=etf, interval=self.settings.interval, days=days)
            except Exception:
                continue
            if df.empty or len(df) <= lookback:
                continue
            ret = float(df["close"].iloc[-1] / df["close"].iloc[-1 - lookback] - 1.0)
            momentum[etf] = ret

        if not momentum:
            return set()

        ranked = sorted(momentum.items(), key=lambda kv: kv[1], reverse=True)
        top_n = max(1, int(self.settings.sector_rotation_top_n))
        return {k for k, _ in ranked[:top_n]}

    def _extract_positions_map(self, summary: dict) -> dict[str, float]:
        positions = summary.get("positions")
        if isinstance(positions, dict):
            return {str(k).upper(): float(v) for k, v in positions.items()}
        if isinstance(positions, list):
            out: dict[str, float] = {}
            for p in positions:
                symbol = str(p.get("symbol", "")).upper()
                qty = float(p.get("qty", 0.0))
                if symbol:
                    out[symbol] = qty
            return out
        return {}

    def _estimate_short_exposure(self, summary: dict) -> float:
        raw = summary.get("positions_raw")
        if not isinstance(raw, list):
            return 0.0
        total = 0.0
        for p in raw:
            side = str(p.get("side", "")).lower()
            if side != "short":
                continue
            mv = p.get("market_value")
            try:
                total += abs(float(mv))
            except Exception:
                pass
        return total

    def _symbols(self) -> list[str]:
        symbols = [s.upper() for s in (self.settings.symbols or [self.settings.symbol]) if s]
        out: list[str] = []
        for symbol in symbols:
            if symbol not in out:
                out.append(symbol)
        return out if out else [self.settings.symbol.upper()]

    def _primary_symbol(self) -> str:
        return self._symbols()[0]

    def _symbol_sector(self, symbol: str) -> str:
        mapping = {k.upper(): v.upper() for k, v in (self.settings.symbol_sector_map or {}).items()}
        sym = symbol.upper()
        if sym in mapping:
            return mapping[sym]
        primary = self._primary_symbol()
        if sym == primary and self.settings.symbol_sector_etf:
            return self.settings.symbol_sector_etf.upper()
        return f"UNMAPPED:{sym}"


def setup_complete_message(report: BacktestReport, decision: CycleDecision | PortfolioCycleDecision) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    if isinstance(decision, PortfolioCycleDecision):
        active = sum(1 for d in decision.decisions if abs(d.target_qty) > 1e-9)
        return (
            f"Setup finished at {ts}. Backtest total_return={report.total_return:.4f}, "
            f"sharpe={report.sharpe:.4f}, max_drawdown={report.max_drawdown:.4f}. "
            f"Portfolio cycle symbols={len(decision.decisions)}, active={active}, "
            f"orders_sent={decision.orders_sent}."
        )

    return (
        f"Setup finished at {ts}. Backtest total_return={report.total_return:.4f}, "
        f"sharpe={report.sharpe:.4f}, max_drawdown={report.max_drawdown:.4f}. "
        f"Initial cycle for {decision.symbol}: close={decision.close:.2f}, "
        f"signal={decision.final_signal}, news={decision.news_sentiment:.3f}, "
        f"sector={decision.sector_strength:.3f}, target_qty={decision.target_qty}, "
        f"delta={decision.delta_qty}."
    )
