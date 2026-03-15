from __future__ import annotations

import requests

from tradeflow_bot.brokers.base import Broker, OrderResult


class AlpacaBroker(Broker):
    def __init__(self, api_key: str, secret_key: str, base_url: str) -> None:
        if not api_key or not secret_key:
            raise ValueError("Missing Alpaca credentials.")
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": secret_key,
                "accept": "application/json",
                "content-type": "application/json",
            }
        )

    def get_position_qty(self, symbol: str) -> float:
        r = self.session.get(f"{self.base_url}/v2/positions/{symbol}", timeout=20)
        if r.status_code == 404:
            return 0.0
        r.raise_for_status()
        payload = r.json()
        return float(payload.get("qty", 0.0))

    def place_order(self, symbol: str, side: str, qty: float) -> OrderResult:
        qty_float = float(qty)
        if qty_float <= 0:
            return OrderResult(False, "", side, qty, "Quantity must be positive.")

        # Alpaca does not allow opening/increasing short positions with fractional shares.
        # We keep fractional sells only when closing an existing long position.
        if side == "sell":
            current_qty = 0.0
            try:
                current_qty = self.get_position_qty(symbol)
            except Exception:
                current_qty = 0.0
            opening_or_adding_short = current_qty <= 0
            if opening_or_adding_short:
                whole_qty = int(qty_float)
                if whole_qty < 1:
                    return OrderResult(
                        False,
                        "",
                        side,
                        qty,
                        "Short orders require at least 1 whole share on Alpaca.",
                    )
                qty_float = float(whole_qty)

        is_fractional = abs(qty_float - round(qty_float)) > 1e-9
        tif = "day" if is_fractional else "gtc"
        payload = {
            "symbol": symbol,
            "qty": str(qty_float),
            "side": side,
            "type": "market",
            "time_in_force": tif,
        }
        r = self.session.post(f"{self.base_url}/v2/orders", json=payload, timeout=20)
        if r.status_code >= 400:
            msg = r.text[:300]
            return OrderResult(False, "", side, qty_float, f"Alpaca error: {msg}")

        data = r.json()
        return OrderResult(True, data.get("id", ""), side, qty_float, "Alpaca order accepted")

    def get_account_summary(self) -> dict:
        r = self.session.get(f"{self.base_url}/v2/account", timeout=20)
        r.raise_for_status()
        data = r.json()
        positions_resp = self.session.get(f"{self.base_url}/v2/positions", timeout=20)
        positions: list[dict] = []
        positions_map: dict[str, float] = {}
        if positions_resp.status_code < 400:
            positions = positions_resp.json()
            for p in positions:
                symbol = str(p.get("symbol", "")).upper()
                qty = float(p.get("qty", 0.0))
                if symbol:
                    positions_map[symbol] = qty
        return {
            "broker": "alpaca",
            "equity": data.get("equity"),
            "cash": data.get("cash"),
            "buying_power": data.get("buying_power"),
            "status": data.get("status"),
            "positions": positions_map,
            "positions_raw": positions,
        }

    def get_open_orders(self) -> list[dict]:
        r = self.session.get(
            f"{self.base_url}/v2/orders",
            params={"status": "open", "direction": "desc", "nested": "false", "limit": 500},
            timeout=20,
        )
        if r.status_code >= 400:
            return []
        payload = r.json()
        if not isinstance(payload, list):
            return []
        return payload
