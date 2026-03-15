from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

POSITIVE_WORDS = {
    "beat",
    "beats",
    "bullish",
    "growth",
    "gains",
    "gain",
    "surge",
    "strong",
    "upgrade",
    "upgrades",
    "optimistic",
    "record",
    "profit",
    "profits",
    "rebound",
    "rally",
    "outperform",
}

NEGATIVE_WORDS = {
    "miss",
    "misses",
    "bearish",
    "decline",
    "drop",
    "drops",
    "weak",
    "downgrade",
    "downgrades",
    "loss",
    "losses",
    "slump",
    "warning",
    "lawsuit",
    "risk",
    "selloff",
    "underperform",
}


@dataclass
class NewsSnapshot:
    score: float
    headline_count: int
    fetched_at: datetime
    headlines: list[str]



def score_sentiment(text: str) -> float:
    words = re.findall(r"[a-zA-Z]+", text.lower())
    if not words:
        return 0.0
    pos = sum(1 for word in words if word in POSITIVE_WORDS)
    neg = sum(1 for word in words if word in NEGATIVE_WORDS)
    if pos == 0 and neg == 0:
        return 0.0
    score = (pos - neg) / max(pos + neg, 1)
    return max(-1.0, min(1.0, score))


class NewsScraper:
    def __init__(self, rss_urls: list[str], timeout_seconds: int = 12, max_items: int = 40):
        self.rss_urls = [url.strip() for url in rss_urls if url.strip()]
        self.timeout_seconds = timeout_seconds
        self.max_items = max_items

    def fetch(self, symbol: str, aliases: list[str] | None = None) -> NewsSnapshot:
        aliases = aliases or []
        keys = {symbol.lower(), *(x.lower() for x in aliases if x)}

        all_headlines: list[str] = []
        scores: list[float] = []

        for url in self.rss_urls:
            try:
                resp = requests.get(url, timeout=self.timeout_seconds)
                resp.raise_for_status()
            except Exception:
                continue

            headlines = self._extract_headlines(resp.text)
            for text in headlines:
                if keys and not any(k in text.lower() for k in keys):
                    continue
                all_headlines.append(text)
                scores.append(score_sentiment(text))
                if len(all_headlines) >= self.max_items:
                    break
            if len(all_headlines) >= self.max_items:
                break

        avg_score = float(sum(scores) / len(scores)) if scores else 0.0
        return NewsSnapshot(
            score=avg_score,
            headline_count=len(all_headlines),
            fetched_at=datetime.now(timezone.utc),
            headlines=all_headlines[:8],
        )

    @staticmethod
    def _extract_headlines(rss_text: str) -> list[str]:
        try:
            root = ET.fromstring(rss_text)
        except ET.ParseError:
            return []

        headlines: list[str] = []
        for item in root.findall(".//item"):
            title = item.findtext("title") or ""
            description = item.findtext("description") or ""
            text = f"{title} {description}".strip()
            if text:
                headlines.append(text)
        return headlines
