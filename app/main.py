import json
import os
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.auth import hash_password, verify_password
from app.db import execute, fetch_all, fetch_one, get_conn, init_db, utc_now
from app.scanning import DEFAULT_SUBREDDITS, load_reddit, scan_subreddits
from app.bsky_scanning import DEFAULT_BSKY_BASE_URL, scan_bsky_queries
from app.mastodon_scanning import DEFAULT_MASTODON_INSTANCE, scan_mastodon_queries
from app.x_scanning import scan_x_queries

app = FastAPI()
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

secret_key = os.getenv("SECRET_KEY", "dev-secret-key")
app.add_middleware(SessionMiddleware, secret_key=secret_key)

scheduler = BackgroundScheduler()

PERSONA_MAP = {
    "entrepreneur": "Founders",
    "startups": "Founders",
    "entrepreneurridealong": "Builders",
    "sideproject": "Indie builders",
    "saas": "SaaS founders",
    "smallbusiness": "Small business owners",
    "androidapps": "Android users",
    "iosapps": "iOS users",
}


def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
    return user


def require_user(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return user


def get_user_org(user_id: int):
    return fetch_one(
        """
        SELECT orgs.* FROM orgs
        JOIN memberships ON memberships.org_id = orgs.id
        WHERE memberships.user_id = ?
        """,
        [user_id],
    )


def ensure_org_config(org_id: int):
    config = fetch_one("SELECT * FROM scan_configs WHERE org_id = ?", [org_id])
    schedule = fetch_one("SELECT * FROM schedules WHERE org_id = ?", [org_id])
    if config and schedule:
        return config

    if config and not schedule:
        execute(
            """
            INSERT INTO schedules (org_id, interval_hours, last_run_utc, updated_utc)
            VALUES (?, ?, ?, ?)
            """,
            [org_id, 0, None, utc_now()],
        )
        return config

    now = utc_now()
    subreddits = ",".join(DEFAULT_SUBREDDITS)
    execute(
        """
        INSERT INTO scan_configs
        (org_id, subreddits, since_days, post_limit, include_comments, comment_limit, require_app_request,
         x_enabled, x_queries, x_since_days, x_post_limit, x_language, x_include_retweets,
         bsky_enabled, bsky_queries, bsky_post_limit, bsky_base_url,
         mastodon_enabled, mastodon_instance, mastodon_queries, mastodon_post_limit, mastodon_since_days,
         updated_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            org_id,
            subreddits,
            30,
            200,
            1,
            200,
            0,
            0,
            "app for,tool for,looking for",
            7,
            100,
            "en",
            0,
            0,
            "app for,looking for",
            100,
            DEFAULT_BSKY_BASE_URL,
            0,
            DEFAULT_MASTODON_INSTANCE,
            "app for,looking for",
            40,
            7,
            now,
        ],
    )
    execute(
        """
        INSERT INTO schedules (org_id, interval_hours, last_run_utc, updated_utc)
        VALUES (?, ?, ?, ?)
        """,
        [org_id, 0, None, now],
    )
    return fetch_one("SELECT * FROM scan_configs WHERE org_id = ?", [org_id])

def _new_summary_bucket():
    return {
        "mentions": 0,
        "pay_mentions": 0,
        "sources": set(),
        "subreddits": set(),
        "sample_title": "",
        "sample_url": "",
    }


def merge_summaries(target, incoming):
    for key, data in incoming.items():
        bucket = target.get(key)
        if not bucket:
            bucket = _new_summary_bucket()
            target[key] = bucket
        bucket["mentions"] += data["mentions"]
        bucket["pay_mentions"] += data["pay_mentions"]
        bucket["sources"].update(data["sources"])
        bucket["subreddits"].update(data["subreddits"])
        if not bucket["sample_title"] and data.get("sample_title"):
            bucket["sample_title"] = data["sample_title"]
            bucket["sample_url"] = data["sample_url"]


def run_scan_for_org(org_id: int):
    config = fetch_one("SELECT * FROM scan_configs WHERE org_id = ?", [org_id])
    if not config:
        config = ensure_org_config(org_id)

    rows = []
    summary = {}
    reddit_meta = {}
    x_meta = {}
    bsky_meta = {}
    mastodon_meta = {}
    reddit_stats = {"fetched_total": 0, "matched": 0}
    x_stats = {"fetched_total": 0, "matched": 0}
    bsky_stats = {"fetched_total": 0, "matched": 0}
    mastodon_stats = {"fetched_total": 0, "matched": 0}

    subreddits = [name.strip() for name in config["subreddits"].split(",") if name.strip()]

    warnings = []
    if subreddits:
        try:
            reddit = load_reddit()
            reddit_rows, reddit_summary, reddit_stats = scan_subreddits(
                reddit=reddit,
                subreddits=subreddits,
                post_limit=config["post_limit"],
                since_days=config["since_days"],
                include_comments=bool(config["include_comments"]),
                comment_limit=config["comment_limit"],
                require_app_request=bool(config["require_app_request"]),
            )
            rows.extend(reddit_rows)
            merge_summaries(summary, reddit_summary)
            try:
                reddit_meta = reddit.auth.limits or {}
            except Exception:
                reddit_meta = {}
        except Exception as exc:
            warnings.append(f"Reddit scan skipped: {exc}")
    if bool(config["x_enabled"]) and config.get("x_queries"):
        queries = [q.strip() for q in config["x_queries"].split(",") if q.strip()]
        if queries:
            try:
                x_rows, x_summary, x_meta, x_stats = scan_x_queries(
                    queries=queries,
                    limit_per_query=config["x_post_limit"],
                    since_days=config["x_since_days"],
                    language=config["x_language"],
                    include_retweets=bool(config["x_include_retweets"]),
                )
                rows.extend(x_rows)
                merge_summaries(summary, x_summary)
            except Exception as exc:
                message = str(exc)
                if "X_CREDITS_DEPLETED" in message:
                    warnings.append("X credits depleted. Add credits in your X developer portal to fetch data.")
                elif "X_AUTH_ERROR" in message or "401" in message:
                    warnings.append("X authentication failed. Check your bearer token and plan access.")
                else:
                    warnings.append(f"X scan skipped: {exc}")

    if bool(config.get("bsky_enabled")) and config.get("bsky_queries"):
        queries = [q.strip() for q in config["bsky_queries"].split(",") if q.strip()]
        base_url = config.get("bsky_base_url") or DEFAULT_BSKY_BASE_URL
        if queries:
            try:
                bsky_rows, bsky_summary, bsky_meta, bsky_stats = scan_bsky_queries(
                    queries=queries,
                    limit_per_query=config["bsky_post_limit"],
                    base_url=base_url,
                )
                rows.extend(bsky_rows)
                merge_summaries(summary, bsky_summary)
            except Exception as exc:
                message = str(exc)
                if "BSKY_RATE_LIMIT" in message:
                    warnings.append("Bluesky rate limit reached. Try again later.")
                elif "BSKY_AUTH_ERROR" in message:
                    warnings.append("Bluesky auth failed. Check your endpoint.")
                elif "BSKY_FORBIDDEN" in message:
                    warnings.append("Bluesky request blocked (403). Check VPN, firewall, or base URL.")
                else:
                    warnings.append(f"Bluesky scan skipped: {exc}")

    if bool(config.get("mastodon_enabled")) and config.get("mastodon_queries"):
        queries = [q.strip() for q in config["mastodon_queries"].split(",") if q.strip()]
        instance_url = config.get("mastodon_instance") or DEFAULT_MASTODON_INSTANCE
        token = os.getenv("MASTODON_TOKEN")
        if queries:
            try:
                mastodon_rows, mastodon_summary, mastodon_meta, mastodon_stats = scan_mastodon_queries(
                    queries=queries,
                    limit_per_query=config["mastodon_post_limit"],
                    instance_url=instance_url,
                    since_days=config.get("mastodon_since_days", 0),
                    token=token,
                )
                rows.extend(mastodon_rows)
                merge_summaries(summary, mastodon_summary)
            except Exception as exc:
                message = str(exc)
                if "MASTODON_RATE_LIMIT" in message:
                    warnings.append("Mastodon rate limit reached. Try again later.")
                elif "MASTODON_AUTH_ERROR" in message:
                    warnings.append("Mastodon auth failed. Check your token or instance.")
                else:
                    warnings.append(f"Mastodon scan skipped: {exc}")

    with get_conn() as conn:
        scan_id = conn.execute(
            """
            INSERT INTO scans
            (org_id, created_utc, reddit_rate_limit, x_rate_limit, reddit_fetched, reddit_matched, x_fetched, x_matched, warnings,
             bsky_rate_limit, bsky_fetched, bsky_matched, mastodon_rate_limit, mastodon_fetched, mastodon_matched)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                org_id,
                utc_now(),
                json.dumps(reddit_meta) if reddit_meta else None,
                json.dumps(x_meta) if x_meta else None,
                reddit_stats.get("fetched_total", 0),
                reddit_stats.get("matched", 0),
                x_stats.get("fetched_total", 0),
                x_stats.get("matched", 0),
                json.dumps(warnings) if warnings else None,
                json.dumps(bsky_meta) if bsky_meta else None,
                bsky_stats.get("fetched_total", 0),
                bsky_stats.get("matched", 0),
                json.dumps(mastodon_meta) if mastodon_meta else None,
                mastodon_stats.get("fetched_total", 0),
                mastodon_stats.get("matched", 0),
            ],
        ).lastrowid

        conn.executemany(
            """
            INSERT INTO scan_results
            (scan_id, source, subreddit, item_type, item_id, created_utc, score, title, url, permalink, match_groups,
             willing_to_pay, idea_key, snippet)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scan_id,
                    row["source"],
                    row["subreddit"],
                    row["type"],
                    row["id"],
                    row["created_utc"],
                    row["score"],
                    row["title"],
                    row["url"],
                    row["permalink"],
                    row["match_groups"],
                    row["willing_to_pay"],
                    row["idea_key"],
                    row["snippet"],
                )
                for row in rows
            ],
        )

        conn.executemany(
            """
            INSERT INTO idea_summaries
            (scan_id, idea_key, mentions, pay_mentions, sources, subreddits, sample_title, sample_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scan_id,
                    key,
                    data["mentions"],
                    data["pay_mentions"],
                    ";".join(sorted(data["sources"])),
                    ";".join(sorted(data["subreddits"])),
                    data["sample_title"],
                    data["sample_url"],
                )
                for key, data in summary.items()
            ],
        )

    return scan_id, len(rows), len(summary), warnings


def parse_json(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def infer_persona(subreddits_text):
    if not subreddits_text:
        return "General"
    parts = [part.strip() for part in subreddits_text.split(";") if part.strip()]
    scores = {}
    for part in parts:
        if part.startswith("query:") or part.startswith("x:"):
            scores["X audience"] = scores.get("X audience", 0) + 1
            continue
        if part.startswith("bsky:"):
            scores["Bluesky audience"] = scores.get("Bluesky audience", 0) + 1
            continue
        if part.startswith("mastodon:"):
            scores["Mastodon audience"] = scores.get("Mastodon audience", 0) + 1
            continue
        key = part.lower()
        persona = PERSONA_MAP.get(key, "General")
        scores[persona] = scores.get(persona, 0) + 1
    if not scores:
        return "General"
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)[0][0]


def build_problem_statement(idea_key, persona):
    if idea_key == "uncategorized":
        return f"{persona} report recurring workflow friction that currently lacks a simple tool."
    return f"{persona} struggle with {idea_key} and want a faster, simpler workflow."


def build_mvp_angle(idea_key, persona):
    if idea_key == "uncategorized":
        return f"Start with a focused capture + automation flow for {persona.lower()}."
    return f"Ship a lightweight tool that solves {idea_key} for {persona.lower()} with a 5-minute setup."


def build_pricing_hypothesis(pay_ratio, mentions):
    if pay_ratio >= 12 or mentions >= 15:
        return "Test $29–$79/mo with a founder-friendly annual discount."
    if pay_ratio >= 6 or mentions >= 8:
        return "Test $12–$39/mo with a free trial and strong onboarding."
    return "Test freemium or a $9–$19 starter tier to validate demand."


def enrich_summary(rows, since_days, previous_map=None):
    enriched = []
    for row in rows:
        mentions = row.get("mentions", 0) or 0
        pay_mentions = row.get("pay_mentions", 0) or 0
        if pay_mentions >= 2 or mentions >= 12:
            signal = "High"
        elif pay_mentions >= 1 or mentions >= 5:
            signal = "Medium"
        else:
            signal = "Low"
        row["signal"] = signal
        row["pay_ratio"] = round((pay_mentions / mentions) * 100, 1) if mentions else 0.0
        row["mentions_per_day"] = round(mentions / since_days, 2) if since_days else 0.0
        row["persona"] = infer_persona(row.get("subreddits", ""))

        delta_mentions = None
        delta_pay = None
        momentum = "New"
        if previous_map is not None:
            prev = previous_map.get(row.get("idea_key"))
            if prev:
                delta_mentions = mentions - prev.get("mentions", 0)
                delta_pay = pay_mentions - prev.get("pay_mentions", 0)
                if delta_mentions >= 3:
                    momentum = "Up"
                elif delta_mentions <= -3:
                    momentum = "Down"
                else:
                    momentum = "Flat"
        row["delta_mentions"] = delta_mentions
        row["delta_pay"] = delta_pay
        row["momentum"] = momentum
        sources_text = row.get("sources", "Reddit")
        momentum_note = {
            "Up": "Momentum is rising in the latest scan.",
            "Down": "Momentum cooled in the latest scan.",
            "Flat": "Momentum is steady in the latest scan.",
            "New": "Newly detected in the latest scan.",
        }.get(momentum, "")
        row["brief"] = (
            f"{row['persona']} mention this pain {mentions} times over the last {since_days} days across {sources_text}. "
            f"Pay signals show up in {row['pay_ratio']}% of mentions. {momentum_note}"
        )
        row["problem_statement"] = build_problem_statement(row.get("idea_key"), row.get("persona", "Users"))
        row["mvp_angle"] = build_mvp_angle(row.get("idea_key"), row.get("persona", "Users"))
        row["pricing_hypothesis"] = build_pricing_hypothesis(row["pay_ratio"], mentions)
        enriched.append(row)
    return enriched


def sort_summary(rows, sort_by):
    if sort_by == "pay_ratio":
        return sorted(rows, key=lambda row: row.get("pay_ratio", 0), reverse=True)
    if sort_by == "pay_mentions":
        return sorted(rows, key=lambda row: row.get("pay_mentions", 0), reverse=True)
    if sort_by == "momentum":
        order = {"Up": 3, "New": 2, "Flat": 1, "Down": 0}
        return sorted(rows, key=lambda row: order.get(row.get("momentum"), 0), reverse=True)
    if sort_by == "signal":
        order = {"High": 3, "Medium": 2, "Low": 1}
        return sorted(rows, key=lambda row: order.get(row.get("signal"), 0), reverse=True)
    return sorted(rows, key=lambda row: row.get("mentions", 0), reverse=True)


def run_due_scans():
    schedules = fetch_all("SELECT * FROM schedules")
    for schedule in schedules:
        interval = schedule["interval_hours"]
        if interval <= 0:
            continue
        last_run = schedule["last_run_utc"]
        now = datetime.now(timezone.utc)
        if last_run:
            last_dt = datetime.fromisoformat(last_run)
            delta_hours = (now - last_dt).total_seconds() / 3600
            if delta_hours < interval:
                continue
        try:
            run_scan_for_org(schedule["org_id"])
            execute(
                "UPDATE schedules SET last_run_utc = ?, updated_utc = ? WHERE org_id = ?",
                [now.isoformat(), utc_now(), schedule["org_id"]],
            )
        except Exception:
            continue


@app.on_event("startup")
def on_startup():
    init_db()
    scheduler.add_job(run_due_scans, "interval", minutes=15, id="schedule-tick")
    scheduler.start()


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown()


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse(
        "landing.html",
        {
            "request": request,
            "user": None,
            "plans": [
                {
                    "name": "Free",
                    "price": "$0",
                    "note": "Starter access",
                    "features": [
                        "1 workspace",
                        "Manual scans",
                        "Top 25 ideas",
                        "Export CSV",
                    ],
                },
                {
                    "name": "Solo",
                    "price": "$29/mo",
                    "note": "Indie founders",
                    "features": [
                        "Unlimited scans",
                        "Daily scheduler",
                        "Full idea detail",
                        "Saved watchlists",
                    ],
                },
                {
                    "name": "Team",
                    "price": "$149/mo",
                    "note": "Studios & teams",
                    "features": [
                        "Shared workspace",
                        "Weekly reporting",
                        "Idea briefs",
                        "Priority support",
                    ],
                },
            ],
        },
    )


@app.get("/register", response_class=HTMLResponse)
def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "error": "", "user": None})


@app.post("/register")
def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    org_name: str = Form(...),
):
    if fetch_one("SELECT id FROM users WHERE email = ?", [email]):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email already exists.", "user": None},
        )

    now = utc_now()
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": str(exc),
                "user": None,
            },
        )
    user_id = execute(
        "INSERT INTO users (email, password_hash, created_utc) VALUES (?, ?, ?)",
        [email, password_hash, now],
    )
    org_id = execute(
        "INSERT INTO orgs (name, created_utc) VALUES (?, ?)",
        [org_name, now],
    )
    execute(
        "INSERT INTO memberships (user_id, org_id, role) VALUES (?, ?, ?)",
        [user_id, org_id, "owner"],
    )

    ensure_org_config(org_id)

    request.session["user_id"] = user_id
    return RedirectResponse("/start", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": "", "user": None})


@app.post("/login")
def login_post(request: Request, email: str = Form(...), password: str = Form(...)):
    user = fetch_one("SELECT * FROM users WHERE email = ?", [email])
    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password.", "user": None},
        )

    request.session["user_id"] = user["id"]
    return RedirectResponse("/app", status_code=302)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)


@app.get("/app", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user=Depends(require_user),
    sort_by: str = "mentions",
    min_mentions: int = 0,
    source: str = "all",
):
    if isinstance(user, RedirectResponse):
        return user

    org = get_user_org(user["id"])
    config = ensure_org_config(org["id"])
    lookback_days = max(config["since_days"], config.get("x_since_days", 0))
    latest_scan = fetch_one(
        "SELECT * FROM scans WHERE org_id = ? ORDER BY created_utc DESC LIMIT 1",
        [org["id"]],
    )
    summary = []
    if latest_scan:
        previous_scan = fetch_one(
            "SELECT * FROM scans WHERE org_id = ? ORDER BY created_utc DESC LIMIT 1 OFFSET 1",
            [org["id"]],
        )
        previous_map = None
        if previous_scan:
            previous_rows = fetch_all(
                "SELECT idea_key, mentions, pay_mentions FROM idea_summaries WHERE scan_id = ?",
                [previous_scan["id"]],
            )
            previous_map = {row["idea_key"]: row for row in previous_rows}
        summary = fetch_all(
            """
            SELECT * FROM idea_summaries
            WHERE scan_id = ?
            ORDER BY mentions DESC
            LIMIT 15
            """,
            [latest_scan["id"]],
        )
        summary = enrich_summary(summary, lookback_days, previous_map)
        if min_mentions > 0:
            summary = [row for row in summary if row.get("mentions", 0) >= min_mentions]
        if source != "all":
            summary = [row for row in summary if source.lower() in row.get("sources", "").lower()]
        summary = sort_summary(summary, sort_by)

    flash = request.session.pop("flash", "") if request.session else ""

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "config": config,
            "latest_scan": latest_scan,
            "summary": summary,
            "flash": flash,
            "sort_by": sort_by,
            "min_mentions": min_mentions,
            "source": source,
        },
    )


@app.post("/app/scan/run")
def run_scan(request: Request, user=Depends(require_user)):
    if isinstance(user, RedirectResponse):
        return user
    org = get_user_org(user["id"])

    try:
        scan_id, match_count, idea_count, warnings = run_scan_for_org(org["id"])
        message = f"Scan complete: {match_count} matches across {idea_count} ideas."
        if warnings:
            message = message + " " + " ".join(warnings)
        request.session["flash"] = message
        return RedirectResponse(f"/app/scan/{scan_id}", status_code=302)
    except Exception as exc:
        request.session["flash"] = f"Scan failed: {exc}"
        return RedirectResponse("/app", status_code=302)


@app.get("/app/scan/{scan_id}", response_class=HTMLResponse)
def scan_detail(
    scan_id: int,
    request: Request,
    user=Depends(require_user),
    sort_by: str = "mentions",
    source: str = "all",
    idea: str = "",
    min_score: int = 0,
):
    if isinstance(user, RedirectResponse):
        return user
    org = get_user_org(user["id"])
    scan = fetch_one("SELECT * FROM scans WHERE id = ? AND org_id = ?", [scan_id, org["id"]])
    if not scan:
        return RedirectResponse("/app", status_code=302)

    config = ensure_org_config(org["id"])
    lookback_days = max(config["since_days"], config.get("x_since_days", 0))

    previous_scan = fetch_one(
        "SELECT * FROM scans WHERE org_id = ? AND created_utc < ? ORDER BY created_utc DESC LIMIT 1",
        [org["id"], scan["created_utc"]],
    )
    previous_map = None
    if previous_scan:
        previous_rows = fetch_all(
            "SELECT idea_key, mentions, pay_mentions FROM idea_summaries WHERE scan_id = ?",
            [previous_scan["id"]],
        )
        previous_map = {row["idea_key"]: row for row in previous_rows}

    summary = fetch_all(
        "SELECT * FROM idea_summaries WHERE scan_id = ? ORDER BY mentions DESC",
        [scan_id],
    )
    summary = enrich_summary(summary, lookback_days, previous_map)
    results = fetch_all(
        "SELECT * FROM scan_results WHERE scan_id = ? ORDER BY score DESC LIMIT 200",
        [scan_id],
    )

    if source != "all":
        summary = [row for row in summary if source.lower() in row.get("sources", "").lower()]
        results = [row for row in results if source.lower() in row.get("source", "").lower()]
    if idea:
        summary = [row for row in summary if idea.lower() in row.get("idea_key", "").lower()]
        results = [row for row in results if idea.lower() in row.get("idea_key", "").lower()]
    if min_score > 0:
        results = [row for row in results if row.get("score", 0) >= min_score]

    summary = sort_summary(summary, sort_by)

    evidence_map = {}
    for row in results:
        items = evidence_map.setdefault(row["idea_key"], [])
        if len(items) < 2:
            items.append({
                "snippet": row["snippet"],
                "permalink": row["permalink"],
                "score": row["score"],
            })

    for row in summary:
        row["evidence_samples"] = evidence_map.get(row["idea_key"], [])

    warnings = parse_json(scan.get("warnings")) or []
    flash = request.session.pop("flash", "") if request.session else ""

    return templates.TemplateResponse(
        "scan_detail.html",
        {
            "request": request,
            "user": user,
            "scan": scan,
            "summary": summary,
            "results": results,
            "flash": flash,
            "warnings": warnings,
            "sort_by": sort_by,
            "source": source,
            "idea": idea,
            "min_score": min_score,
        },
    )


@app.get("/app/settings", response_class=HTMLResponse)
def settings_get(request: Request, user=Depends(require_user)):
    if isinstance(user, RedirectResponse):
        return user
    org = get_user_org(user["id"])
    config = ensure_org_config(org["id"])
    schedule = fetch_one("SELECT * FROM schedules WHERE org_id = ?", [org["id"]])

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "config": config,
            "schedule": schedule,
        },
    )

@app.get("/start", response_class=HTMLResponse)
def start(request: Request, user=Depends(require_user)):
    if isinstance(user, RedirectResponse):
        return user
    org = get_user_org(user["id"])
    config = ensure_org_config(org["id"])
    schedule = fetch_one("SELECT * FROM schedules WHERE org_id = ?", [org["id"]])
    latest_scan = fetch_one(
        "SELECT * FROM scans WHERE org_id = ? ORDER BY created_utc DESC LIMIT 1",
        [org["id"]],
    )

    match_count = 0
    idea_count = 0
    reddit_fetched = 0
    reddit_matched = 0
    x_fetched = 0
    x_matched = 0
    bsky_fetched = 0
    bsky_matched = 0
    mastodon_fetched = 0
    mastodon_matched = 0
    warnings = []
    reddit_limits = None
    x_limits = None
    bsky_limits = None
    mastodon_limits = None
    x_reset = "Unknown"
    reddit_reset = "Unknown"
    bsky_reset = "Unknown"
    mastodon_reset = "Unknown"

    if latest_scan:
        match_row = fetch_one(
            "SELECT COUNT(*) AS count FROM scan_results WHERE scan_id = ?",
            [latest_scan["id"]],
        )
        idea_row = fetch_one(
            "SELECT COUNT(*) AS count FROM idea_summaries WHERE scan_id = ?",
            [latest_scan["id"]],
        )
        match_count = match_row["count"] if match_row else 0
        idea_count = idea_row["count"] if idea_row else 0

        reddit_limits = parse_json(latest_scan.get("reddit_rate_limit"))
        x_meta = parse_json(latest_scan.get("x_rate_limit"))
        bsky_meta = parse_json(latest_scan.get("bsky_rate_limit"))
        mastodon_meta = parse_json(latest_scan.get("mastodon_rate_limit"))
        warnings = parse_json(latest_scan.get("warnings")) or []
        if reddit_limits:
            reset_ts = reddit_limits.get("reset_timestamp")
            if reset_ts:
                reddit_reset = datetime.fromtimestamp(reset_ts, tz=timezone.utc).isoformat()
        if x_meta and x_meta.get("queries"):
            latest_query = x_meta["queries"][-1]
            x_limits = latest_query.get("rate_limit")
            if x_limits:
                reset_ts = x_limits.get("reset")
                if reset_ts:
                    try:
                        x_reset = datetime.fromtimestamp(int(reset_ts), tz=timezone.utc).isoformat()
                    except ValueError:
                        x_reset = str(reset_ts)

        if bsky_meta and bsky_meta.get("queries"):
            latest_query = bsky_meta["queries"][-1]
            bsky_limits = latest_query.get("rate_limit")
            if bsky_limits:
                reset_ts = bsky_limits.get("reset")
                if reset_ts:
                    bsky_reset = str(reset_ts)

        if mastodon_meta and mastodon_meta.get("queries"):
            latest_query = mastodon_meta["queries"][-1]
            mastodon_limits = latest_query.get("rate_limit")
            if mastodon_limits:
                reset_ts = mastodon_limits.get("reset")
                if reset_ts:
                    mastodon_reset = str(reset_ts)

        reddit_fetched = latest_scan.get("reddit_fetched") or 0
        reddit_matched = latest_scan.get("reddit_matched") or 0
        x_fetched = latest_scan.get("x_fetched") or 0
        x_matched = latest_scan.get("x_matched") or 0
        bsky_fetched = latest_scan.get("bsky_fetched") or 0
        bsky_matched = latest_scan.get("bsky_matched") or 0
        mastodon_fetched = latest_scan.get("mastodon_fetched") or 0
        mastodon_matched = latest_scan.get("mastodon_matched") or 0

        if (reddit_matched == 0 or x_matched == 0) and latest_scan:
            source_counts = fetch_all(
                "SELECT source, COUNT(*) AS count FROM scan_results WHERE scan_id = ? GROUP BY source",
                [latest_scan["id"]],
            )
            counts = {row["source"]: row["count"] for row in source_counts}
            if reddit_matched == 0:
                reddit_matched = counts.get("Reddit", 0)
            if x_matched == 0:
                x_matched = counts.get("X", 0)
            if bsky_matched == 0:
                bsky_matched = counts.get("Bluesky", 0)
            if mastodon_matched == 0:
                mastodon_matched = counts.get("Mastodon", 0)

    reddit_id = os.getenv("REDDIT_CLIENT_ID")
    reddit_secret = os.getenv("REDDIT_CLIENT_SECRET")
    reddit_connected = (
        bool(reddit_id)
        and bool(reddit_secret)
        and "your_" not in reddit_id.lower()
        and "your_" not in reddit_secret.lower()
    )
    x_connected = bool(os.getenv("X_BEARER_TOKEN"))
    bsky_connected = bool(config.get("bsky_base_url"))
    mastodon_connected = bool(config.get("mastodon_instance"))
    schedule_label = "Off"
    if schedule and schedule["interval_hours"] == 24:
        schedule_label = "Daily"
    elif schedule and schedule["interval_hours"] == 168:
        schedule_label = "Weekly"

    return templates.TemplateResponse(
        "start.html",
        {
            "request": request,
            "user": user,
            "config": config,
            "latest_scan": latest_scan,
            "match_count": match_count,
            "idea_count": idea_count,
            "reddit_limits": reddit_limits,
            "x_limits": x_limits,
            "reddit_reset": reddit_reset,
            "x_reset": x_reset,
            "bsky_limits": bsky_limits,
            "bsky_reset": bsky_reset,
            "mastodon_limits": mastodon_limits,
            "mastodon_reset": mastodon_reset,
            "warnings": warnings,
            "reddit_fetched": reddit_fetched,
            "reddit_matched": reddit_matched,
            "x_fetched": x_fetched,
            "x_matched": x_matched,
            "bsky_fetched": bsky_fetched,
            "bsky_matched": bsky_matched,
            "mastodon_fetched": mastodon_fetched,
            "mastodon_matched": mastodon_matched,
            "reddit_connected": reddit_connected,
            "x_connected": x_connected,
            "bsky_connected": bsky_connected,
            "mastodon_connected": mastodon_connected,
            "schedule_label": schedule_label,
        },
    )


@app.get("/onboarding", response_class=HTMLResponse)
def onboarding_get(request: Request, user=Depends(require_user)):
    if isinstance(user, RedirectResponse):
        return user
    org = get_user_org(user["id"])
    config = ensure_org_config(org["id"])
    schedule = fetch_one("SELECT * FROM schedules WHERE org_id = ?", [org["id"]])
    return templates.TemplateResponse(
        "onboarding.html",
        {
            "request": request,
            "user": user,
            "config": config,
            "schedule": schedule,
        },
    )


@app.post("/onboarding")
def onboarding_post(
    request: Request,
    user=Depends(require_user),
    subreddits: str = Form(...),
    since_days: int = Form(...),
    post_limit: int = Form(...),
    include_comments: str = Form(None),
    comment_limit: int = Form(200),
    require_app_request: str = Form(None),
    schedule: str = Form(...),
    x_enabled: str = Form(None),
    x_queries: str = Form(""),
    x_since_days: int = Form(7),
    x_post_limit: int = Form(100),
    x_language: str = Form("en"),
    x_include_retweets: str = Form(None),
    bsky_enabled: str = Form(None),
    bsky_queries: str = Form(""),
    bsky_post_limit: int = Form(100),
    bsky_base_url: str = Form(DEFAULT_BSKY_BASE_URL),
    mastodon_enabled: str = Form(None),
    mastodon_instance: str = Form(DEFAULT_MASTODON_INSTANCE),
    mastodon_queries: str = Form(""),
    mastodon_post_limit: int = Form(40),
    mastodon_since_days: int = Form(7),
):
    if isinstance(user, RedirectResponse):
        return user
    org = get_user_org(user["id"])
    include_comments_value = 1 if include_comments == "on" else 0
    require_app_request_value = 1 if require_app_request == "on" else 0
    x_enabled_value = 1 if x_enabled == "on" else 0
    x_include_retweets_value = 1 if x_include_retweets == "on" else 0
    bsky_enabled_value = 1 if bsky_enabled == "on" else 0
    mastodon_enabled_value = 1 if mastodon_enabled == "on" else 0

    execute(
        """
        UPDATE scan_configs
        SET subreddits = ?, since_days = ?, post_limit = ?, include_comments = ?, comment_limit = ?,
            require_app_request = ?, x_enabled = ?, x_queries = ?, x_since_days = ?, x_post_limit = ?,
            x_language = ?, x_include_retweets = ?,
            bsky_enabled = ?, bsky_queries = ?, bsky_post_limit = ?, bsky_base_url = ?,
            mastodon_enabled = ?, mastodon_instance = ?, mastodon_queries = ?, mastodon_post_limit = ?, mastodon_since_days = ?,
            updated_utc = ?
        WHERE org_id = ?
        """,
        [
            subreddits,
            since_days,
            post_limit,
            include_comments_value,
            comment_limit,
            require_app_request_value,
            x_enabled_value,
            x_queries,
            x_since_days,
            x_post_limit,
            x_language,
            x_include_retweets_value,
            bsky_enabled_value,
            bsky_queries,
            bsky_post_limit,
            bsky_base_url,
            mastodon_enabled_value,
            mastodon_instance,
            mastodon_queries,
            mastodon_post_limit,
            mastodon_since_days,
            utc_now(),
            org["id"],
        ],
    )

    interval_hours = {"off": 0, "daily": 24, "weekly": 168}.get(schedule, 0)
    execute(
        "UPDATE schedules SET interval_hours = ?, updated_utc = ? WHERE org_id = ?",
        [interval_hours, utc_now(), org["id"]],
    )

    return RedirectResponse("/app", status_code=302)


@app.post("/app/settings")
def settings_post(
    request: Request,
    user=Depends(require_user),
    subreddits: str = Form(...),
    since_days: int = Form(...),
    post_limit: int = Form(...),
    include_comments: str = Form(None),
    comment_limit: int = Form(...),
    require_app_request: str = Form(None),
    schedule: str = Form(...),
    x_enabled: str = Form(None),
    x_queries: str = Form(""),
    x_since_days: int = Form(7),
    x_post_limit: int = Form(100),
    x_language: str = Form("en"),
    x_include_retweets: str = Form(None),
    bsky_enabled: str = Form(None),
    bsky_queries: str = Form(""),
    bsky_post_limit: int = Form(100),
    bsky_base_url: str = Form(DEFAULT_BSKY_BASE_URL),
    mastodon_enabled: str = Form(None),
    mastodon_instance: str = Form(DEFAULT_MASTODON_INSTANCE),
    mastodon_queries: str = Form(""),
    mastodon_post_limit: int = Form(40),
    mastodon_since_days: int = Form(7),
):
    if isinstance(user, RedirectResponse):
        return user
    org = get_user_org(user["id"])
    include_comments_value = 1 if include_comments == "on" else 0
    require_app_request_value = 1 if require_app_request == "on" else 0
    x_enabled_value = 1 if x_enabled == "on" else 0
    x_include_retweets_value = 1 if x_include_retweets == "on" else 0
    bsky_enabled_value = 1 if bsky_enabled == "on" else 0
    mastodon_enabled_value = 1 if mastodon_enabled == "on" else 0

    execute(
        """
        UPDATE scan_configs
        SET subreddits = ?, since_days = ?, post_limit = ?, include_comments = ?, comment_limit = ?,
            require_app_request = ?, x_enabled = ?, x_queries = ?, x_since_days = ?, x_post_limit = ?,
            x_language = ?, x_include_retweets = ?,
            bsky_enabled = ?, bsky_queries = ?, bsky_post_limit = ?, bsky_base_url = ?,
            mastodon_enabled = ?, mastodon_instance = ?, mastodon_queries = ?, mastodon_post_limit = ?, mastodon_since_days = ?,
            updated_utc = ?
        WHERE org_id = ?
        """,
        [
            subreddits,
            since_days,
            post_limit,
            include_comments_value,
            comment_limit,
            require_app_request_value,
            x_enabled_value,
            x_queries,
            x_since_days,
            x_post_limit,
            x_language,
            x_include_retweets_value,
            bsky_enabled_value,
            bsky_queries,
            bsky_post_limit,
            bsky_base_url,
            mastodon_enabled_value,
            mastodon_instance,
            mastodon_queries,
            mastodon_post_limit,
            mastodon_since_days,
            utc_now(),
            org["id"],
        ],
    )

    interval_hours = {"off": 0, "daily": 24, "weekly": 168}.get(schedule, 0)
    execute(
        "UPDATE schedules SET interval_hours = ?, updated_utc = ? WHERE org_id = ?",
        [interval_hours, utc_now(), org["id"]],
    )

    return RedirectResponse("/app/settings", status_code=302)


@app.get("/app/test/bluesky")
def test_bluesky(request: Request, user=Depends(require_user)):
    if isinstance(user, RedirectResponse):
        return user
    org = get_user_org(user["id"])
    config = ensure_org_config(org["id"])
    base_url = config.get("bsky_base_url") or DEFAULT_BSKY_BASE_URL
    queries = [q.strip() for q in (config.get("bsky_queries") or "").split(",") if q.strip()]
    test_query = queries[0] if queries else "app for"

    try:
        _rows, _summary, _meta, stats = scan_bsky_queries(
            queries=[test_query],
            limit_per_query=5,
            base_url=base_url,
        )
        request.session["flash"] = (
            f"Bluesky test OK: fetched {stats.get('fetched_total', 0)}, "
            f"matched {stats.get('matched', 0)}."
        )
    except Exception as exc:
        request.session["flash"] = f"Bluesky test failed: {exc}"

    return RedirectResponse("/start", status_code=302)


@app.get("/health")
def health():
    return {"status": "ok"}
