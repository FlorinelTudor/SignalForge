import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
import praw

DEFAULT_SUBREDDITS = [
    "Entrepreneur",
    "startups",
    "smallbusiness",
    "SideProject",
    "SaaS",
    "EntrepreneurRideAlong",
    "androidapps",
    "iosapps",
]

PATTERN_GROUPS = {
    "app_request": [
        r"\\bis there (an|a) app\\b",
        r"\\bis there an? (tool|software|service)\\b",
        r"\\bany app (for|that)\\b",
        r"\\bdoes anyone know (an? )?(app|tool|software|service)\\b",
        r"\\blooking for (an? )?(app|tool|software|service)\\b",
        r"\\bneed (an? )?(app|tool|software|service)\\b",
        r"\\bapp that (can|does|will)\\b",
        r"\\balternative to\\b",
    ],
    "pain": [
        r"\\bfrustrat(ed|ing)\\b",
        r"\\bthis (sucks|is awful|is terrible)\\b",
        r"\\bwhy is (there|this) no\\b",
        r"\\bwish there (was|were)\\b",
        r"\\bhate (having|to|that)\\b",
        r"\\bpain point\\b",
        r"\\bproblem is\\b",
        r"\\bstruggling with\\b",
    ],
    "pay": [
        r"\\bi'?d pay\\b",
        r"\\bi would pay\\b",
        r"\\bwilling to pay\\b",
        r"\\bpay for (an? )?(app|tool|software|service)\\b",
        r"\\bhappily pay\\b",
    ],
}

STOPWORDS = {
    "this", "that", "with", "from", "they", "them", "then", "than", "there",
    "here", "have", "has", "had", "your", "yours", "what", "which", "when",
    "where", "would", "could", "should", "their", "about", "into", "just",
    "like", "really", "very", "much", "some", "more", "most", "also", "only",
    "does", "doing", "done", "need", "want", "looking", "app", "apps",
    "tool", "tools", "software", "service", "services", "help", "anyone",
    "know", "find", "use", "using", "used", "make", "making", "made",
}


def compile_patterns():
    compiled = {}
    for name, patterns in PATTERN_GROUPS.items():
        combined = "|".join(patterns)
        compiled[name] = re.compile(combined, re.IGNORECASE)
    return compiled


def load_reddit():
    load_dotenv()
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")

    missing = [
        name
        for name, value in [
            ("REDDIT_CLIENT_ID", client_id),
            ("REDDIT_CLIENT_SECRET", client_secret),
            ("REDDIT_USER_AGENT", user_agent),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )


def idea_key(text):
    words = [w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in STOPWORDS]
    if not words:
        return "uncategorized"
    freq = Counter(words)
    top = [word for word, _ in freq.most_common(6)]
    return " ".join(top)


def match_groups(text, compiled):
    hits = []
    for name, rx in compiled.items():
        if rx.search(text):
            hits.append(name)
    return hits


def iter_comments(submission, limit):
    submission.comment_sort = "new"
    submission.comments.replace_more(limit=0)
    count = 0
    for comment in submission.comments.list():
        if limit and count >= limit:
            break
        yield comment
        count += 1


def scan_subreddits(
    reddit,
    subreddits,
    post_limit,
    since_days,
    include_comments,
    comment_limit,
    require_app_request,
):
    compiled = compile_patterns()
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    rows = []
    stats = {
        "fetched_total": 0,
        "fetched_submissions": 0,
        "fetched_comments": 0,
        "matched": 0,
    }
    summary = defaultdict(lambda: {
        "mentions": 0,
        "pay_mentions": 0,
        "sources": set(),
        "subreddits": set(),
        "sample_title": "",
        "sample_url": "",
    })

    for name in subreddits:
        subreddit = reddit.subreddit(name)
        for submission in subreddit.new(limit=post_limit):
            created = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
            if created < cutoff:
                continue
            stats["fetched_total"] += 1
            stats["fetched_submissions"] += 1

            text = " ".join(part for part in [submission.title or "", submission.selftext or ""] if part)
            groups = match_groups(text, compiled)
            if require_app_request and "app_request" not in groups:
                groups = []

            if groups:
                key = idea_key(text)
                pay = "pay" in groups
                rows.append({
                    "source": "Reddit",
                    "subreddit": name,
                    "type": "submission",
                    "id": submission.id,
                    "created_utc": created.isoformat(),
                    "score": submission.score,
                    "title": submission.title,
                    "url": submission.url,
                    "permalink": f"https://www.reddit.com{submission.permalink}",
                    "match_groups": ";".join(groups),
                    "willing_to_pay": "yes" if pay else "no",
                    "idea_key": key,
                    "snippet": (submission.selftext or "")[:220].replace("\n", " ").strip(),
                })

                bucket = summary[key]
                bucket["mentions"] += 1
                if pay:
                    bucket["pay_mentions"] += 1
                bucket["sources"].add("Reddit")
                bucket["subreddits"].add(name)
                if not bucket["sample_title"]:
                    bucket["sample_title"] = submission.title
                    bucket["sample_url"] = f"https://www.reddit.com{submission.permalink}"
                stats["matched"] += 1

            if include_comments:
                for comment in iter_comments(submission, comment_limit):
                    created_c = datetime.fromtimestamp(comment.created_utc, tz=timezone.utc)
                    if created_c < cutoff:
                        continue
                    stats["fetched_total"] += 1
                    stats["fetched_comments"] += 1
                    text_c = comment.body or ""
                    groups_c = match_groups(text_c, compiled)
                    if require_app_request and "app_request" not in groups_c:
                        continue

                    if groups_c:
                        key = idea_key(text_c)
                        pay = "pay" in groups_c
                        rows.append({
                            "source": "Reddit",
                            "subreddit": name,
                            "type": "comment",
                            "id": comment.id,
                            "created_utc": created_c.isoformat(),
                            "score": comment.score,
                            "title": submission.title,
                            "url": submission.url,
                            "permalink": f"https://www.reddit.com{comment.permalink}",
                            "match_groups": ";".join(groups_c),
                            "willing_to_pay": "yes" if pay else "no",
                            "idea_key": key,
                            "snippet": text_c[:220].replace("\n", " ").strip(),
                        })

                        bucket = summary[key]
                        bucket["mentions"] += 1
                        if pay:
                            bucket["pay_mentions"] += 1
                        bucket["sources"].add("Reddit")
                        bucket["subreddits"].add(name)
                        if not bucket["sample_title"]:
                            bucket["sample_title"] = submission.title
                            bucket["sample_url"] = f"https://www.reddit.com{comment.permalink}"
                        stats["matched"] += 1

    return rows, summary, stats
