from __future__ import annotations

from tradeflow_bot.brokers.base import Broker, OrderResult


class EtoroBroker(Broker):
    def __init__(self, api_key: str, secret_key: str) -> None:
        self.api_key = api_key
        self.secret_key = secret_key

    def get_position_qty(self, symbol: str) -> float:
        raise NotImplementedError(
            "eToro does not currently provide a public official retail trading API. "
            "Use a supported broker adapter (e.g., Alpaca) or implement a private gateway adapter."
        )

    def place_order(self, symbol: str, side: str, qty: float) -> OrderResult:
        raise NotImplementedError(
            "eToro execution is not available via official public API in this adapter."
        )

    def get_account_summary(self) -> dict:
        raise NotImplementedError(
            "eToro account summary unavailable in this adapter without private gateway integration."
        )

    def get_open_orders(self) -> list[dict]:
        raise NotImplementedError(
            "eToro open orders unavailable in this adapter without private gateway integration."
        )
