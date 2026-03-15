from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from tradeflow_bot.config import Settings


@dataclass
class ClosedFill:
    symbol: str
    direction: str  # long | short
    qty: float
    entry_price: float
    exit_price: float
    pnl: float
    return_pct: float
    closed_at: str


@dataclass
class TradeHistorySummary:
    fills_processed: int
    closed_count: int
    wins: int
    losses: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    avg_return_pct: float
    long_closed: int
    short_closed: int
    long_win_rate: float
    short_win_rate: float


@dataclass
class ImprovementSuggestion:
    key: str
    old: str
    new: str
    reason: str


@dataclass
class ImprovementReport:
    generated_at: str
    summary: TradeHistorySummary
    suggestions: list[ImprovementSuggestion]
    sample_closed_fills: list[ClosedFill]


class AlpacaHistoryImprover:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
                "accept": "application/json",
            }
        )

    def fetch_fills(self, max_pages: int = 200, page_size: int = 100) -> list[dict]:
        if not self.settings.alpaca_api_key or not self.settings.alpaca_secret_key:
            return []

        url = f"{self.settings.alpaca_base_url.rstrip('/')}/v2/account/activities"
        page_token: str | None = None
        out: list[dict] = []
        cutoff = self._history_cutoff()

        for _ in range(max_pages):
            params = {
                "activity_types": "FILL",
                "direction": "desc",
                "page_size": max(1, min(page_size, 100)),
            }
            if page_token:
                params["page_token"] = page_token

            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code >= 400:
                break

            page = resp.json()
            if not isinstance(page, list) or not page:
                break

            recent_in_page = 0
            for item in page:
                ts = self._activity_timestamp(item)
                if ts is None or ts >= cutoff:
                    out.append(item)
                    if ts is not None:
                        recent_in_page += 1

            page_token = page[-1].get("id")
            if not page_token:
                break
            if recent_in_page == 0:
                break

        return out

    def fetch_filled_orders(self, max_pages: int = 40, page_size: int = 500) -> list[dict]:
        if not self.settings.alpaca_api_key or not self.settings.alpaca_secret_key:
            return []

        url = f"{self.settings.alpaca_base_url.rstrip('/')}/v2/orders"
        cutoff = self._history_cutoff()
        until: str | None = None
        seen_ids: set[str] = set()
        out: list[dict] = []

        for _ in range(max_pages):
            params = {
                "status": "all",
                "direction": "desc",
                "nested": "false",
                "limit": max(1, min(page_size, 500)),
            }
            if until:
                params["until"] = until

            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code >= 400:
                break

            page = resp.json()
            if not isinstance(page, list) or not page:
                break

            oldest_ts: datetime | None = None
            new_ids = 0
            for item in page:
                order_id = str(item.get("id") or "")
                if order_id and order_id in seen_ids:
                    continue
                if order_id:
                    seen_ids.add(order_id)
                    new_ids += 1

                ts = self._order_timestamp(item)
                if ts is not None and (oldest_ts is None or ts < oldest_ts):
                    oldest_ts = ts

                if str(item.get("status", "")).lower() != "filled":
                    continue
                filled_ts = self._filled_order_timestamp(item)
                if filled_ts is not None and filled_ts < cutoff:
                    continue
                qty = self._safe_float(item.get("filled_qty"))
                price = self._safe_float(item.get("filled_avg_price"))
                if qty <= 0 or price <= 0:
                    continue
                out.append(item)

            if new_ids == 0 or oldest_ts is None:
                break
            if oldest_ts < cutoff:
                break
            until = (oldest_ts - timedelta(microseconds=1)).isoformat().replace("+00:00", "Z")

        return out

    def fetch_history_records(self, max_pages: int = 200, page_size: int = 100) -> list[dict]:
        fills = self.fetch_fills(max_pages=max_pages, page_size=page_size)
        if fills:
            return fills

        orders = self.fetch_filled_orders(max_pages=max_pages, page_size=500)
        normalized: list[dict] = []
        for order in orders:
            record = self._order_to_fill_record(order)
            if record is not None:
                normalized.append(record)
        return normalized

    def _history_cutoff(self) -> datetime:
        days = max(int(self.settings.alpaca_history_lookback_days), 1)
        return datetime.now(timezone.utc) - timedelta(days=days)

    @staticmethod
    def _parse_ts(value: str | None) -> datetime | None:
        if not value:
            return None
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(raw).astimezone(timezone.utc)
        except ValueError:
            return None

    def _activity_timestamp(self, activity: dict) -> datetime | None:
        return self._parse_ts(str(activity.get("transaction_time") or activity.get("date") or ""))

    def _filled_order_timestamp(self, order: dict) -> datetime | None:
        return self._parse_ts(str(order.get("filled_at") or order.get("updated_at") or order.get("submitted_at") or ""))

    def _order_timestamp(self, order: dict) -> datetime | None:
        return self._parse_ts(str(order.get("submitted_at") or order.get("created_at") or order.get("updated_at") or ""))

    def analyze(self, fills: list[dict]) -> tuple[TradeHistorySummary, list[ClosedFill]]:
        # Process oldest first so position accounting is deterministic.
        records = list(reversed(fills))

        pos_qty: dict[str, float] = {}
        pos_avg: dict[str, float] = {}
        closed: list[ClosedFill] = []

        for item in records:
            symbol = str(item.get("symbol", "")).upper()
            side = str(item.get("side", "")).lower()
            qty = float(item.get("qty") or 0.0)
            price = float(item.get("price") or 0.0)
            closed_at = str(item.get("transaction_time") or item.get("date") or "")

            if not symbol or qty <= 0 or price <= 0 or side not in {"buy", "sell"}:
                continue

            q = pos_qty.get(symbol, 0.0)
            a = pos_avg.get(symbol, 0.0)

            if side == "buy":
                if q >= 0:
                    new_qty = q + qty
                    new_avg = ((q * a) + (qty * price)) / max(new_qty, 1e-12)
                    pos_qty[symbol] = new_qty
                    pos_avg[symbol] = new_avg
                else:
                    close_qty = min(abs(q), qty)
                    pnl = (a - price) * close_qty
                    notional = max(a * close_qty, 1e-12)
                    closed.append(
                        ClosedFill(
                            symbol=symbol,
                            direction="short",
                            qty=close_qty,
                            entry_price=a,
                            exit_price=price,
                            pnl=pnl,
                            return_pct=pnl / notional,
                            closed_at=closed_at,
                        )
                    )
                    remaining = qty - close_qty
                    q_after = q + close_qty
                    if abs(q_after) < 1e-9:
                        q_after = 0.0
                        a_after = 0.0
                    else:
                        a_after = a

                    if remaining > 0:
                        q_after = remaining
                        a_after = price

                    pos_qty[symbol] = q_after
                    pos_avg[symbol] = a_after

            else:  # side == sell
                if q <= 0:
                    short_qty = abs(q)
                    new_short_qty = short_qty + qty
                    new_avg = ((short_qty * a) + (qty * price)) / max(new_short_qty, 1e-12)
                    pos_qty[symbol] = -new_short_qty
                    pos_avg[symbol] = new_avg
                else:
                    close_qty = min(q, qty)
                    pnl = (price - a) * close_qty
                    notional = max(a * close_qty, 1e-12)
                    closed.append(
                        ClosedFill(
                            symbol=symbol,
                            direction="long",
                            qty=close_qty,
                            entry_price=a,
                            exit_price=price,
                            pnl=pnl,
                            return_pct=pnl / notional,
                            closed_at=closed_at,
                        )
                    )
                    remaining = qty - close_qty
                    q_after = q - close_qty
                    if abs(q_after) < 1e-9:
                        q_after = 0.0
                        a_after = 0.0
                    else:
                        a_after = a

                    if remaining > 0:
                        q_after = -remaining
                        a_after = price

                    pos_qty[symbol] = q_after
                    pos_avg[symbol] = a_after

        summary = self._summarize(fills_processed=len(records), closed=closed)
        return summary, closed

    @staticmethod
    def _order_to_fill_record(order: dict) -> dict | None:
        symbol = str(order.get("symbol", "")).upper()
        side = str(order.get("side", "")).lower()
        qty = AlpacaHistoryImprover._safe_float(order.get("filled_qty"))
        price = AlpacaHistoryImprover._safe_float(order.get("filled_avg_price"))
        closed_at = str(order.get("filled_at") or order.get("updated_at") or order.get("submitted_at") or "")

        if not symbol or side not in {"buy", "sell"} or qty <= 0 or price <= 0:
            return None

        return {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "transaction_time": closed_at,
        }

    @staticmethod
    def _safe_float(value) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def suggest(self, summary: TradeHistorySummary) -> list[ImprovementSuggestion]:
        s: list[ImprovementSuggestion] = []

        def add(key: str, old: str, new: str, reason: str):
            if old != new:
                s.append(ImprovementSuggestion(key=key, old=old, new=new, reason=reason))

        # Reliability guard.
        if summary.closed_count < 8:
            return s

        # Win-rate based gating adjustments.
        if summary.win_rate < 0.45:
            new_long = min(self.settings.ml_long_threshold + 0.01, 0.65)
            new_short = max(self.settings.ml_short_threshold - 0.01, 0.30)
            add(
                "ML_LONG_THRESHOLD",
                f"{self.settings.ml_long_threshold:.4f}",
                f"{new_long:.4f}",
                "Win rate is below 45%; tighten long ML gate.",
            )
            add(
                "ML_SHORT_THRESHOLD",
                f"{self.settings.ml_short_threshold:.4f}",
                f"{new_short:.4f}",
                "Win rate is below 45%; tighten short ML gate.",
            )

        if summary.win_rate > 0.60:
            new_long = max(self.settings.ml_long_threshold - 0.01, 0.50)
            new_short = min(self.settings.ml_short_threshold + 0.01, 0.50)
            add(
                "ML_LONG_THRESHOLD",
                f"{self.settings.ml_long_threshold:.4f}",
                f"{new_long:.4f}",
                "Win rate is above 60%; slightly relax long ML gate.",
            )
            add(
                "ML_SHORT_THRESHOLD",
                f"{self.settings.ml_short_threshold:.4f}",
                f"{new_short:.4f}",
                "Win rate is above 60%; slightly relax short ML gate.",
            )

        # Directional bias sizing.
        if summary.short_closed >= 5 and summary.long_closed >= 5:
            diff = summary.short_win_rate - summary.long_win_rate
            if diff > 0.10:
                new_short_mult = min(self.settings.short_size_multiplier + 0.1, 1.0)
                add(
                    "SHORT_SIZE_MULTIPLIER",
                    f"{self.settings.short_size_multiplier:.3f}",
                    f"{new_short_mult:.3f}",
                    "Short win rate materially exceeds long win rate; increase short size multiplier.",
                )
            elif diff < -0.10:
                new_short_mult = max(self.settings.short_size_multiplier - 0.1, 0.1)
                add(
                    "SHORT_SIZE_MULTIPLIER",
                    f"{self.settings.short_size_multiplier:.3f}",
                    f"{new_short_mult:.3f}",
                    "Long win rate materially exceeds short win rate; reduce short size multiplier.",
                )

        # Profit-factor sanity tuning.
        if summary.profit_factor < 1.0:
            new_stock_mom = min(self.settings.stock_momentum_entry_threshold + 0.0025, 0.08)
            add(
                "STOCK_MOMENTUM_ENTRY_THRESHOLD",
                f"{self.settings.stock_momentum_entry_threshold:.4f}",
                f"{new_stock_mom:.4f}",
                "Profit factor < 1.0; require stronger momentum for new long entries.",
            )

        return s

    def persist_report(
        self,
        summary: TradeHistorySummary,
        suggestions: list[ImprovementSuggestion],
        closed: list[ClosedFill],
        report_dir: Path,
    ) -> Path:
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = report_dir / f"alpaca_history_improvement_{stamp}.json"

        payload = ImprovementReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary=summary,
            suggestions=suggestions,
            sample_closed_fills=closed[-20:],
        )
        path.write_text(json.dumps(asdict(payload), indent=2), encoding="utf-8")
        return path

    @staticmethod
    def _summarize(fills_processed: int, closed: list[ClosedFill]) -> TradeHistorySummary:
        if not closed:
            return TradeHistorySummary(
                fills_processed=fills_processed,
                closed_count=0,
                wins=0,
                losses=0,
                win_rate=0.0,
                gross_profit=0.0,
                gross_loss=0.0,
                profit_factor=0.0,
                avg_return_pct=0.0,
                long_closed=0,
                short_closed=0,
                long_win_rate=0.0,
                short_win_rate=0.0,
            )

        wins = sum(1 for x in closed if x.pnl > 0)
        losses = sum(1 for x in closed if x.pnl < 0)
        gross_profit = sum(x.pnl for x in closed if x.pnl > 0)
        gross_loss = -sum(x.pnl for x in closed if x.pnl < 0)

        long_closed = [x for x in closed if x.direction == "long"]
        short_closed = [x for x in closed if x.direction == "short"]
        long_wins = sum(1 for x in long_closed if x.pnl > 0)
        short_wins = sum(1 for x in short_closed if x.pnl > 0)

        return TradeHistorySummary(
            fills_processed=fills_processed,
            closed_count=len(closed),
            wins=wins,
            losses=losses,
            win_rate=wins / max(len(closed), 1),
            gross_profit=float(gross_profit),
            gross_loss=float(gross_loss),
            profit_factor=float(gross_profit / gross_loss) if gross_loss > 0 else float("inf"),
            avg_return_pct=float(sum(x.return_pct for x in closed) / len(closed)),
            long_closed=len(long_closed),
            short_closed=len(short_closed),
            long_win_rate=float(long_wins / max(len(long_closed), 1)),
            short_win_rate=float(short_wins / max(len(short_closed), 1)),
        )
