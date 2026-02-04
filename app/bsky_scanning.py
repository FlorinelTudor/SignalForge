import requests

from app.scanning import compile_patterns, idea_key, match_groups

DEFAULT_BSKY_BASE_URL = "https://public.api.bsky.app"


def fetch_search_posts(base_url, query, limit):
    url = f"{base_url.rstrip('/')}/xrpc/app.bsky.feed.searchPosts"
    params = {
        "q": query,
        "limit": min(limit, 100),
        "sort": "latest",
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "SignalForge/0.1 (contact: local)",
    }
    response = requests.get(url, params=params, headers=headers, timeout=20)
    if response.status_code != 200:
        if response.status_code == 401:
            raise RuntimeError("BSKY_AUTH_ERROR: Unauthorized")
        if response.status_code == 403:
            raise RuntimeError("BSKY_FORBIDDEN: Access blocked (check VPN or base URL)")
        if response.status_code == 429:
            raise RuntimeError("BSKY_RATE_LIMIT: Too Many Requests")
        raise RuntimeError(f"BSKY_API_ERROR: {response.status_code} {response.text}")

    rate_info = {
        "limit": response.headers.get("ratelimit-limit"),
        "remaining": response.headers.get("ratelimit-remaining"),
        "reset": response.headers.get("ratelimit-reset"),
    }

    payload = response.json()
    posts = payload.get("posts", [])
    return posts, rate_info


def build_post_url(post):
    uri = post.get("uri", "")
    author = post.get("author", {}) or {}
    handle = author.get("handle")
    if uri and handle and "/app.bsky.feed.post/" in uri:
        rkey = uri.split("/")[-1]
        return f"https://bsky.app/profile/{handle}/post/{rkey}"
    return uri or ""


def scan_bsky_queries(queries, limit_per_query, base_url):
    compiled = compile_patterns()

    rows = []
    summary = {}
    meta = {"queries": []}
    fetched_total = 0

    for raw_query in queries:
        posts, rate_info = fetch_search_posts(base_url, raw_query, limit_per_query)
        fetched_total += len(posts)
        meta["queries"].append({"query": raw_query, "rate_limit": rate_info})

        for post in posts:
            record = post.get("record", {}) or {}
            text = record.get("text") or post.get("text") or ""
            if not text:
                continue
            groups = match_groups(text, compiled)
            if not groups:
                continue

            created_at = record.get("createdAt") or post.get("indexedAt")
            url = build_post_url(post)
            key = idea_key(text)
            pay = "pay" in groups
            score = 0
            for field in ("likeCount", "repostCount", "replyCount"):
                score += int(post.get(field, 0) or 0)

            row = {
                "source": "Bluesky",
                "subreddit": f"bsky:{raw_query}",
                "type": "post",
                "id": post.get("cid") or post.get("uri") or "",
                "created_utc": created_at or "",
                "score": score,
                "title": text[:80] + ("..." if len(text) > 80 else ""),
                "url": url or "",
                "permalink": url or "",
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
            bucket["sources"].add("Bluesky")
            bucket["subreddits"].add(f"bsky:{raw_query}")
            if not bucket["sample_title"]:
                bucket["sample_title"] = row["title"]
                bucket["sample_url"] = row["permalink"]

    stats = {"fetched_total": fetched_total, "matched": len(rows)}
    return rows, summary, meta, stats
