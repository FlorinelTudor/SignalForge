from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests


REQUIRED_COLS = ["open", "high", "low", "close", "volume"]


@dataclass
class DataClient:
    source: str = "yfinance"  # yfinance | alpaca | synthetic
    seed: int = 7
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_data_url: str = "https://data.alpaca.markets"

    def fetch_historical(self, symbol: str, interval: str, days: int) -> pd.DataFrame:
        if self.source == "synthetic":
            return self._synthetic(symbol=symbol, interval=interval, days=days)
        if self.source == "alpaca":
            return self._alpaca(symbol=symbol, interval=interval, days=days)
        return self._yfinance(symbol=symbol, interval=interval, days=days)

    def fetch_latest(self, symbol: str, interval: str) -> pd.DataFrame:
        return self.fetch_historical(symbol=symbol, interval=interval, days=5).tail(300)

    def _yfinance(self, symbol: str, interval: str, days: int) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "yfinance is not installed. Install dependencies or run with --data-source synthetic."
            ) from exc

        period = f"{max(days, 5)}d"
        interval = self._normalize_interval(interval)
        df = pd.DataFrame()
        backoff_seconds = [0, 2, 5]
        for wait in backoff_seconds:
            if wait:
                time.sleep(wait)
            df = yf.download(
                symbol,
                period=period,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if df is not None and not df.empty:
                break
        if df is None or df.empty:
            raise RuntimeError(
                f"No market data returned for {symbol}. Check ticker, interval, network connectivity, or provider rate limits."
            )

        df = df.rename(columns=str.lower)
        df = df[[c for c in REQUIRED_COLS if c in df.columns]].copy()
        if len(df.columns) != len(REQUIRED_COLS):
            raise RuntimeError(
                f"Market data for {symbol} missing required columns. Got {list(df.columns)}"
            )
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
        df = df.sort_index()
        return df

    def _alpaca(self, symbol: str, interval: str, days: int) -> pd.DataFrame:
        if not self.alpaca_api_key or not self.alpaca_secret_key:
            raise RuntimeError("Missing Alpaca credentials for alpaca data source.")

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        timeframe = self._to_alpaca_timeframe(interval)
        url = f"{self.alpaca_data_url.rstrip('/')}/v2/stocks/{symbol}/bars"
        headers = {
            "APCA-API-KEY-ID": self.alpaca_api_key,
            "APCA-API-SECRET-KEY": self.alpaca_secret_key,
            "accept": "application/json",
        }
        params = {
            "timeframe": timeframe,
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "limit": 10000,
            "adjustment": "raw",
            "feed": "iex",
        }
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"Alpaca data error ({response.status_code}): {response.text[:250]}")

        payload = response.json()
        bars = payload.get("bars", [])
        if not bars:
            raise RuntimeError("No Alpaca bars returned. Check symbol, interval, subscription, or market hours.")

        df = pd.DataFrame.from_records(bars)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "t": "time"})
        df = df[["time", "open", "high", "low", "close", "volume"]]
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df = df.set_index("time").sort_index()
        return df

    def _synthetic(self, symbol: str, interval: str, days: int) -> pd.DataFrame:
        freq = self._to_pandas_freq(interval)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        index = pd.date_range(start=start, end=end, freq=freq)
        n = len(index)
        if n < 100:
            raise RuntimeError("Synthetic dataset is too short. Increase history_days.")

        rng = np.random.default_rng(self.seed)
        drift = 0.0002
        shock = rng.normal(loc=0.0, scale=0.01, size=n)
        trend = np.linspace(0.0, 0.03, n)
        returns = drift + trend / max(n, 1) + shock
        close = 100.0 * np.exp(np.cumsum(returns))

        high = close * (1 + rng.uniform(0.0005, 0.005, size=n))
        low = close * (1 - rng.uniform(0.0005, 0.005, size=n))
        open_ = np.roll(close, 1)
        open_[0] = close[0]
        volume = rng.integers(1000, 100000, size=n)

        df = pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=index,
        )
        df.index = df.index.tz_convert("UTC")
        return df

    @staticmethod
    def _normalize_interval(interval: str) -> str:
        mapping = {
            "1m": "1m",
            "2m": "2m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "60m": "60m",
            "90m": "90m",
            "1h": "60m",
            "1d": "1d",
            "1wk": "1wk",
        }
        if interval not in mapping:
            raise ValueError(f"Unsupported interval '{interval}'.")
        return mapping[interval]

    @staticmethod
    def _to_pandas_freq(interval: str) -> str:
        mapping = {
            "1m": "1min",
            "2m": "2min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "60m": "60min",
            "1h": "60min",
            "90m": "90min",
            "1d": "1D",
            "1wk": "1W",
        }
        if interval not in mapping:
            raise ValueError(f"Unsupported interval '{interval}'.")
        return mapping[interval]

    @staticmethod
    def _to_alpaca_timeframe(interval: str) -> str:
        mapping = {
            "1m": "1Min",
            "2m": "2Min",
            "5m": "5Min",
            "15m": "15Min",
            "30m": "30Min",
            "60m": "1Hour",
            "1h": "1Hour",
            "1d": "1Day",
        }
        if interval not in mapping:
            raise ValueError(
                f"Unsupported interval '{interval}' for alpaca source. "
                "Supported: 1m,2m,5m,15m,30m,60m,1h,1d"
            )
        return mapping[interval]
