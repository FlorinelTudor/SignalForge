from tradeflow_bot.brokers.alpaca import AlpacaBroker


class _Resp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_short_order_fractional_is_rounded_to_whole_share():
    broker = AlpacaBroker("key", "secret", "https://paper-api.alpaca.markets")
    broker.get_position_qty = lambda _symbol: 0.0

    captured = {}

    def fake_post(url, json=None, timeout=20):
        captured["url"] = url
        captured["payload"] = json
        return _Resp(200, {"id": "order-1"})

    broker.session.post = fake_post
    result = broker.place_order("LMT", "sell", 1.9)

    assert result.accepted is True
    assert result.qty == 1.0
    assert captured["payload"]["qty"] == "1.0"
    assert captured["payload"]["time_in_force"] == "gtc"


def test_short_order_rejects_sub_share():
    broker = AlpacaBroker("key", "secret", "https://paper-api.alpaca.markets")
    broker.get_position_qty = lambda _symbol: 0.0
    result = broker.place_order("LMT", "sell", 0.7)

    assert result.accepted is False
    assert "whole share" in result.message.lower()


def test_fractional_sell_allowed_when_closing_long():
    broker = AlpacaBroker("key", "secret", "https://paper-api.alpaca.markets")
    broker.get_position_qty = lambda _symbol: 2.5

    captured = {}

    def fake_post(url, json=None, timeout=20):
        captured["payload"] = json
        return _Resp(200, {"id": "order-2"})

    broker.session.post = fake_post
    result = broker.place_order("LUV", "sell", 1.25)

    assert result.accepted is True
    assert result.qty == 1.25
    assert captured["payload"]["qty"] == "1.25"
    assert captured["payload"]["time_in_force"] == "day"
