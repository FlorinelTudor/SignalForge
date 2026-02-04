import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
import requests

from app.scanning import compile_patterns, idea_key, match_groups

X_API_BASE = "https://api.x.com/2"


def load_x_token():
    load_dotenv()
    token = os.getenv("X_BEARER_TOKEN")
    if not token:
        raise RuntimeError("Missing environment variable: X_BEARER_TOKEN")
    return token


def build_query(raw_query: str, language: str, include_retweets: bool):
    parts = [raw_query.strip()]
    if language:
        parts.append(f"lang:{language}")
    if not include_retweets:
        parts.append("-is:retweet")
    return " ".join(part for part in parts if part)


def fetch_recent_tweets(token, query, limit, since_days):
    headers = {"Authorization": f"Bearer {token}"}
    max_days = min(max(since_days, 1), 7)
    start_time = (datetime.now(timezone.utc) - timedelta(days=max_days)).isoformat().replace("+00:00", "Z")

    url = f"{X_API_BASE}/tweets/search/recent"
    params = {
        "query": query,
        "max_results": min(limit, 100),
        "tweet.fields": "created_at,public_metrics",
        "start_time": start_time,
    }

    collected = []
    rate_info = {}
    next_token = None

    while True:
        if next_token:
            params["next_token"] = next_token
        response = requests.get(url, headers=headers, params=params, timeout=20)
        if response.status_code != 200:
            payload = {}
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            title = payload.get("title", "")
            detail = payload.get("detail", "")
            error_type = payload.get("type", "")
            error_text = f"{title} {detail} {error_type}".lower()
            if "creditsdepleted" in error_text or "credits" in error_text:
                raise RuntimeError(f"X_CREDITS_DEPLETED: {detail or title or response.text}")
            if response.status_code == 401:
                raise RuntimeError("X_AUTH_ERROR: Unauthorized")
            raise RuntimeError(f"X API error {response.status_code}: {response.text}")

        rate_info = {
            "limit": response.headers.get("x-rate-limit-limit"),
            "remaining": response.headers.get("x-rate-limit-remaining"),
            "reset": response.headers.get("x-rate-limit-reset"),
        }

        payload = response.json()
        data = payload.get("data", [])
        collected.extend(data)

        meta = payload.get("meta", {})
        next_token = meta.get("next_token")
        if not next_token or len(collected) >= limit:
            break

    return collected[:limit], rate_info


def scan_x_queries(
    queries,
    limit_per_query,
    since_days,
    language,
    include_retweets,
):
    token = load_x_token()
    compiled = compile_patterns()

    rows = []
    summary = {}
    meta = {"queries": []}
    fetched_total = 0

    for raw_query in queries:
        query = build_query(raw_query, language, include_retweets)
        tweets, rate_info = fetch_recent_tweets(token, query, limit_per_query, since_days)
        fetched_total += len(tweets)
        meta["queries"].append({"query": raw_query, "rate_limit": rate_info})
        for tweet in tweets:
            text = tweet.get("text", "")
            groups = match_groups(text, compiled)
            if not groups:
                continue

            created_at = tweet.get("created_at") or datetime.now(timezone.utc).isoformat()
            metrics = tweet.get("public_metrics") or {}
            score = metrics.get("like_count", 0) + metrics.get("retweet_count", 0)
            key = idea_key(text)
            pay = "pay" in groups

            row = {
                "source": "X",
                "subreddit": f"query:{raw_query}",
                "type": "tweet",
                "id": tweet.get("id"),
                "created_utc": created_at,
                "score": score,
                "title": (text[:80] + "...") if len(text) > 80 else text,
                "url": f"https://x.com/i/web/status/{tweet.get('id')}",
                "permalink": f"https://x.com/i/web/status/{tweet.get('id')}",
                "match_groups": ";".join(groups),
                "willing_to_pay": "yes" if pay else "no",
                "idea_key": key,
                "snippet": text[:220].replace("\n", " ").strip(),
            }
            rows.append(row)

            bucket = summary.get(key)
            if not bucket:
                bucket = {
                    "mentions": 0,
                    "pay_mentions": 0,
                    "sources": set(),
                    "subreddits": set(),
                    "sample_title": "",
                    "sample_url": "",
                }
                summary[key] = bucket

            bucket["mentions"] += 1
            if pay:
                bucket["pay_mentions"] += 1
            bucket["sources"].add("X")
            bucket["subreddits"].add(f"query:{raw_query}")
            if not bucket["sample_title"]:
                bucket["sample_title"] = row["title"]
                bucket["sample_url"] = row["permalink"]

    stats = {"fetched_total": fetched_total, "matched": len(rows)}
    return rows, summary, meta, stats
