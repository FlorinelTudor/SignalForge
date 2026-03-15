from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OrderResult:
    accepted: bool
    order_id: str
    side: str
    qty: float
    message: str


class Broker(ABC):
    @abstractmethod
    def get_position_qty(self, symbol: str) -> float:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, symbol: str, side: str, qty: float) -> OrderResult:
        raise NotImplementedError

    @abstractmethod
    def get_account_summary(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_open_orders(self) -> list[dict]:
        raise NotImplementedError
