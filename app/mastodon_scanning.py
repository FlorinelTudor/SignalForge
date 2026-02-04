import html
import re
import requests
from datetime import datetime, timezone, timedelta

from app.scanning import compile_patterns, idea_key, match_groups

DEFAULT_MASTODON_INSTANCE = "https://mastodon.social"


def strip_html(value: str) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", "", value)
    return html.unescape(text).strip()


def fetch_statuses(instance_url, query, limit, token=None):
    base = instance_url.rstrip("/")
    url = f"{base}/api/v2/search"
    params = {
        "q": query,
        "type": "statuses",
        "limit": min(limit, 40),
    }
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(url, params=params, headers=headers, timeout=20)
    if response.status_code != 200:
        if response.status_code == 401:
            raise RuntimeError("MASTODON_AUTH_ERROR: Unauthorized")
        if response.status_code == 429:
            raise RuntimeError("MASTODON_RATE_LIMIT: Too Many Requests")
        raise RuntimeError(f"MASTODON_API_ERROR: {response.status_code} {response.text}")

    rate_info = {
        "limit": response.headers.get("X-RateLimit-Limit"),
        "remaining": response.headers.get("X-RateLimit-Remaining"),
        "reset": response.headers.get("X-RateLimit-Reset"),
    }

    payload = response.json()
    statuses = payload.get("statuses", [])
    return statuses, rate_info


def scan_mastodon_queries(queries, limit_per_query, instance_url, since_days=0, token=None):
    compiled = compile_patterns()

    rows = []
    summary = {}
    meta = {"queries": [], "instance": instance_url}
    fetched_total = 0

    cutoff = None
    if since_days and since_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)

    for raw_query in queries:
        statuses, rate_info = fetch_statuses(instance_url, raw_query, limit_per_query, token=token)
        fetched_total += len(statuses)
        meta["queries"].append({"query": raw_query, "rate_limit": rate_info})

        for status in statuses:
            created_at = status.get("created_at")
            if cutoff and created_at:
                try:
                    created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if created_dt < cutoff:
                        continue
                except ValueError:
                    pass

            text = strip_html(status.get("content", ""))
            if not text:
                continue
            groups = match_groups(text, compiled)
            if not groups:
                continue

            key = idea_key(text)
            pay = "pay" in groups
            score = 0
            for field in ("favourites_count", "reblogs_count", "replies_count"):
                score += int(status.get(field, 0) or 0)

            url = status.get("url") or status.get("uri") or ""

            row = {
                "source": "Mastodon",
                "subreddit": f"mastodon:{raw_query}",
                "type": "status",
                "id": status.get("id") or "",
                "created_utc": created_at or "",
                "score": score,
                "title": text[:80] + ("..." if len(text) > 80 else ""),
                "url": url,
                "permalink": url,
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
            bucket["sources"].add("Mastodon")
            bucket["subreddits"].add(f"mastodon:{raw_query}")
            if not bucket["sample_title"]:
                bucket["sample_title"] = row["title"]
                bucket["sample_url"] = row["permalink"]

    stats = {"fetched_total": fetched_total, "matched": len(rows)}
    return rows, summary, meta, stats
