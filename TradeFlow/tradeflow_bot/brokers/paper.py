from __future__ import annotations

import json
from pathlib import Path

from tradeflow_bot.brokers.base import Broker, OrderResult


class PaperBroker(Broker):
    def __init__(self, state_path: Path = Path("logs/paper_broker_state.json")) -> None:
        self.state_path = state_path
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def get_position_qty(self, symbol: str) -> float:
        return float(self.state.get("positions", {}).get(symbol, 0.0))

    def place_order(self, symbol: str, side: str, qty: float) -> OrderResult:
        qty = float(qty)
        if qty <= 0:
            return OrderResult(False, "", side, qty, "Quantity must be > 0")

        positions = self.state.setdefault("positions", {})
        current = float(positions.get(symbol, 0.0))
        if side == "buy":
            current += qty
        elif side == "sell":
            current -= qty
        else:
            return OrderResult(False, "", side, qty, f"Unsupported side '{side}'")

        positions[symbol] = current
        self.state.setdefault("orders", []).append(
            {"symbol": symbol, "side": side, "qty": qty, "new_position": current}
        )
        self._save_state()

        order_id = f"paper-{len(self.state['orders'])}"
        return OrderResult(True, order_id, side, qty, "Paper order filled")

    def get_account_summary(self) -> dict:
        return {
            "broker": "paper",
            "positions": self.state.get("positions", {}),
            "orders": len(self.state.get("orders", [])),
        }

    def get_open_orders(self) -> list[dict]:
        return []

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            return {"positions": {}, "orders": []}
        try:
            with self.state_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"positions": {}, "orders": []}

    def _save_state(self) -> None:
        with self.state_path.open("w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)
