#!/usr/bin/env python3
import argparse
import csv

from app.scanning import DEFAULT_SUBREDDITS, load_reddit, scan_subreddits


def write_matches(path, rows):
    fieldnames = [
        "source",
        "subreddit",
        "type",
        "id",
        "created_utc",
        "score",
        "title",
        "url",
        "permalink",
        "match_groups",
        "willing_to_pay",
        "idea_key",
        "snippet",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_summary(path, summary):
    fieldnames = [
        "idea_key",
        "mentions",
        "pay_mentions",
        "sources",
        "subreddits",
        "sample_title",
        "sample_url",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for key, data in sorted(summary.items(), key=lambda item: item[1]["mentions"], reverse=True):
            writer.writerow({
                "idea_key": key,
                "mentions": data["mentions"],
                "pay_mentions": data["pay_mentions"],
                "sources": ";".join(sorted(data["sources"])),
                "subreddits": ";".join(sorted(data["subreddits"])),
                "sample_title": data["sample_title"],
                "sample_url": data["sample_url"],
            })


def parse_args():
    parser = argparse.ArgumentParser(description="Scan Reddit for app-request pain points.")
    parser.add_argument(
        "--subreddits",
        default=",".join(DEFAULT_SUBREDDITS),
        help="Comma-separated list of subreddits to scan.",
    )
    parser.add_argument("--post-limit", type=int, default=200, help="Posts per subreddit to scan.")
    parser.add_argument("--since-days", type=int, default=30, help="Only include items newer than this.")
    parser.add_argument("--include-comments", action="store_true", help="Scan comments too.")
    parser.add_argument("--comment-limit", type=int, default=200, help="Comments per submission.")
    parser.add_argument(
        "--require-app-request",
        action="store_true",
        help="Only keep matches that include explicit app/tool requests.",
    )
    parser.add_argument("--out-matches", default="matches.csv", help="CSV output for matched items.")
    parser.add_argument("--out-summary", default="summary.csv", help="CSV output for idea summary.")
    return parser.parse_args()


def main():
    args = parse_args()
    subreddits = [name.strip() for name in args.subreddits.split(",") if name.strip()]

    reddit = load_reddit()
    rows, summary, _stats = scan_subreddits(
        reddit=reddit,
        subreddits=subreddits,
        post_limit=args.post_limit,
        since_days=args.since_days,
        include_comments=args.include_comments,
        comment_limit=args.comment_limit,
        require_app_request=args.require_app_request,
    )

    write_matches(args.out_matches, rows)
    write_summary(args.out_summary, summary)

    print(f"Wrote {len(rows)} matches to {args.out_matches}")
    print(f"Wrote {len(summary)} idea summaries to {args.out_summary}")


if __name__ == "__main__":
    main()
