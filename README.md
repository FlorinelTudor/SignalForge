# SignalForge (Reddit Pain Point Scanner)

A lightweight web app that scans Reddit and X for pain points and explicit app/tool requests, then turns them into clear, detailed SaaS idea briefs with mention counts and source evidence.

## Features

- Workspace-based auth (solo or team ready)
- Reddit scanning with configurable subreddits
- X connector with keyword queries
- Bluesky connector (public AppView API)
- Mastodon connector (instance search)
- Idea clustering with mention counts + “willingness to pay” signals
- Onboarding wizard for first scan profile
- Filters and sorting by signal, momentum, and source
- Evidence table with direct links to source posts/comments
- Scheduled scans (daily or weekly)

## Setup

1. Create a Reddit app to get API credentials.
2. Create an X developer app and a bearer token for search.
3. Optional: Add a Mastodon access token if your instance requires it.
4. Copy `.env.example` to `.env` and fill in values.

Note: the X recent search endpoint only returns Posts from the last 7 days, so X lookback is capped at 7 days.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

If you see an `argon2` backend error, rerun the install to ensure `argon2-cffi` is available.

## Run the web app

```bash
uvicorn app.main:app --reload
```

Then open: `http://127.0.0.1:8000`

## Run the CLI scan

```bash
python reddit_scan.py --since-days 30 --post-limit 200 --include-comments
```

Outputs:

- `matches.csv`: Every matched post/comment with metadata and a short snippet
- `summary.csv`: Idea clusters with mention counts
