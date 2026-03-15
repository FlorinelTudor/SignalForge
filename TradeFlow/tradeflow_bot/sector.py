from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tradeflow_bot.data import DataClient


@dataclass
class SectorSnapshot:
    score: float
    sector_rank: int
    sector_count: int
    sector_symbol: str
    breadth: float
    momentum_map: dict[str, float]


class SectorStrengthAnalyzer:
    def __init__(self, symbols: list[str], lookback_bars: int = 20):
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.lookback_bars = lookback_bars

    def compute(
        self,
        data_client: DataClient,
        interval: str,
        days: int,
        symbol_sector_etf: str,
    ) -> SectorSnapshot:
        momentum_map: dict[str, float] = {}
        for etf in self.symbols:
            try:
                df = data_client.fetch_historical(symbol=etf, interval=interval, days=days)
            except Exception:
                continue
            if df.empty or len(df) <= self.lookback_bars:
                continue
            ret = float(df["close"].iloc[-1] / df["close"].iloc[-1 - self.lookback_bars] - 1.0)
            momentum_map[etf] = ret

        if not momentum_map:
            return SectorSnapshot(
                score=0.0,
                sector_rank=0,
                sector_count=0,
                sector_symbol=symbol_sector_etf,
                breadth=0.0,
                momentum_map={},
            )

        ranked = sorted(momentum_map.items(), key=lambda x: x[1], reverse=True)
        keys = [k for k, _ in ranked]
        sector_symbol = symbol_sector_etf.upper()
        if sector_symbol not in momentum_map:
            sector_symbol = keys[0]

        rank = keys.index(sector_symbol) + 1
        count = len(keys)
        rank_percentile = (count - rank) / max(count - 1, 1)
        rank_score = 2.0 * rank_percentile - 1.0

        values = np.array(list(momentum_map.values()), dtype=float)
        breadth = float(np.mean(np.sign(values)))
        score = float(0.7 * rank_score + 0.3 * breadth)

        return SectorSnapshot(
            score=max(-1.0, min(1.0, score)),
            sector_rank=rank,
            sector_count=count,
            sector_symbol=sector_symbol,
            breadth=breadth,
            momentum_map=momentum_map,
        )
