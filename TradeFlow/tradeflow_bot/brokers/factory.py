from __future__ import annotations

from tradeflow_bot.brokers.alpaca import AlpacaBroker
from tradeflow_bot.brokers.base import Broker
from tradeflow_bot.brokers.etoro import EtoroBroker
from tradeflow_bot.brokers.paper import PaperBroker
from tradeflow_bot.config import Settings


def build_broker(settings: Settings) -> Broker:
    broker_name = settings.broker_name.strip().lower()
    if broker_name == "paper":
        return PaperBroker()
    if broker_name == "alpaca":
        return AlpacaBroker(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            base_url=settings.alpaca_base_url,
        )
    if broker_name == "etoro":
        return EtoroBroker(api_key=settings.etoro_api_key, secret_key=settings.etoro_secret_key)

    raise ValueError(f"Unsupported broker '{settings.broker_name}'")
