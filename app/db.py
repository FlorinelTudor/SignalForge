import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")


def _get_db_path():
    return os.getenv("DATABASE_URL", DEFAULT_DB_PATH)


def ensure_db_dir():
    db_path = _get_db_path()
    db_dir = os.path.dirname(db_path)
    os.makedirs(db_dir, exist_ok=True)


@contextmanager
def get_conn():
    ensure_db_dir()
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_utc TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS orgs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_utc TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS memberships (
        user_id INTEGER NOT NULL,
        org_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        PRIMARY KEY (user_id, org_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (org_id) REFERENCES orgs(id)
    );

    CREATE TABLE IF NOT EXISTS scan_configs (
        org_id INTEGER PRIMARY KEY,
        subreddits TEXT NOT NULL,
        since_days INTEGER NOT NULL,
        post_limit INTEGER NOT NULL,
        include_comments INTEGER NOT NULL,
        comment_limit INTEGER NOT NULL,
        require_app_request INTEGER NOT NULL,
        x_enabled INTEGER NOT NULL DEFAULT 0,
        x_queries TEXT NOT NULL DEFAULT '',
        x_since_days INTEGER NOT NULL DEFAULT 7,
        x_post_limit INTEGER NOT NULL DEFAULT 100,
        x_language TEXT NOT NULL DEFAULT 'en',
        x_include_retweets INTEGER NOT NULL DEFAULT 0,
        bsky_enabled INTEGER NOT NULL DEFAULT 0,
        bsky_queries TEXT NOT NULL DEFAULT '',
        bsky_post_limit INTEGER NOT NULL DEFAULT 100,
        bsky_base_url TEXT NOT NULL DEFAULT 'https://public.api.bsky.app',
        mastodon_enabled INTEGER NOT NULL DEFAULT 0,
        mastodon_instance TEXT NOT NULL DEFAULT 'https://mastodon.social',
        mastodon_queries TEXT NOT NULL DEFAULT '',
        mastodon_post_limit INTEGER NOT NULL DEFAULT 40,
        mastodon_since_days INTEGER NOT NULL DEFAULT 7,
        updated_utc TEXT NOT NULL,
        FOREIGN KEY (org_id) REFERENCES orgs(id)
    );

    CREATE TABLE IF NOT EXISTS schedules (
        org_id INTEGER PRIMARY KEY,
        interval_hours INTEGER NOT NULL,
        last_run_utc TEXT,
        updated_utc TEXT NOT NULL,
        FOREIGN KEY (org_id) REFERENCES orgs(id)
    );

    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id INTEGER NOT NULL,
        created_utc TEXT NOT NULL,
        reddit_rate_limit TEXT,
        x_rate_limit TEXT,
        reddit_fetched INTEGER,
        reddit_matched INTEGER,
        x_fetched INTEGER,
        x_matched INTEGER,
        warnings TEXT,
        bsky_rate_limit TEXT,
        bsky_fetched INTEGER,
        bsky_matched INTEGER,
        mastodon_rate_limit TEXT,
        mastodon_fetched INTEGER,
        mastodon_matched INTEGER,
        FOREIGN KEY (org_id) REFERENCES orgs(id)
    );

    CREATE TABLE IF NOT EXISTS scan_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER NOT NULL,
        source TEXT NOT NULL,
        subreddit TEXT NOT NULL,
        item_type TEXT NOT NULL,
        item_id TEXT NOT NULL,
        created_utc TEXT NOT NULL,
        score INTEGER NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        permalink TEXT NOT NULL,
        match_groups TEXT NOT NULL,
        willing_to_pay TEXT NOT NULL,
        idea_key TEXT NOT NULL,
        snippet TEXT NOT NULL,
        FOREIGN KEY (scan_id) REFERENCES scans(id)
    );

    CREATE TABLE IF NOT EXISTS idea_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER NOT NULL,
        idea_key TEXT NOT NULL,
        mentions INTEGER NOT NULL,
        pay_mentions INTEGER NOT NULL,
        sources TEXT NOT NULL,
        subreddits TEXT NOT NULL,
        sample_title TEXT NOT NULL,
        sample_url TEXT NOT NULL,
        FOREIGN KEY (scan_id) REFERENCES scans(id)
    );

    CREATE INDEX IF NOT EXISTS idx_scan_results_scan ON scan_results(scan_id);
    CREATE INDEX IF NOT EXISTS idx_idea_summaries_scan ON idea_summaries(scan_id);
    CREATE INDEX IF NOT EXISTS idx_scans_org ON scans(org_id);
    """
    with get_conn() as conn:
        conn.executescript(schema)
        _ensure_columns(conn)


def _ensure_columns(conn):
    ensure_column(conn, "scan_configs", "x_enabled INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "scan_configs", "x_queries TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "scan_configs", "x_since_days INTEGER NOT NULL DEFAULT 7")
    ensure_column(conn, "scan_configs", "x_post_limit INTEGER NOT NULL DEFAULT 100")
    ensure_column(conn, "scan_configs", "x_language TEXT NOT NULL DEFAULT 'en'")
    ensure_column(conn, "scan_configs", "x_include_retweets INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "scan_configs", "bsky_enabled INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "scan_configs", "bsky_queries TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "scan_configs", "bsky_post_limit INTEGER NOT NULL DEFAULT 100")
    ensure_column(conn, "scan_configs", "bsky_base_url TEXT NOT NULL DEFAULT 'https://public.api.bsky.app'")
    ensure_column(conn, "scan_configs", "mastodon_enabled INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "scan_configs", "mastodon_instance TEXT NOT NULL DEFAULT 'https://mastodon.social'")
    ensure_column(conn, "scan_configs", "mastodon_queries TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "scan_configs", "mastodon_post_limit INTEGER NOT NULL DEFAULT 40")
    ensure_column(conn, "scan_configs", "mastodon_since_days INTEGER NOT NULL DEFAULT 7")
    ensure_column(conn, "scans", "reddit_rate_limit TEXT")
    ensure_column(conn, "scans", "x_rate_limit TEXT")
    ensure_column(conn, "scans", "reddit_fetched INTEGER")
    ensure_column(conn, "scans", "reddit_matched INTEGER")
    ensure_column(conn, "scans", "x_fetched INTEGER")
    ensure_column(conn, "scans", "x_matched INTEGER")
    ensure_column(conn, "scans", "warnings TEXT")
    ensure_column(conn, "scans", "bsky_rate_limit TEXT")
    ensure_column(conn, "scans", "bsky_fetched INTEGER")
    ensure_column(conn, "scans", "bsky_matched INTEGER")
    ensure_column(conn, "scans", "mastodon_rate_limit TEXT")
    ensure_column(conn, "scans", "mastodon_fetched INTEGER")
    ensure_column(conn, "scans", "mastodon_matched INTEGER")


def ensure_column(conn, table, column_def):
    column_name = column_def.strip().split()[0]
    cur = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def fetch_one(query, params=None):
    with get_conn() as conn:
        cur = conn.execute(query, params or [])
        row = cur.fetchone()
        return dict(row) if row else None


def fetch_all(query, params=None):
    with get_conn() as conn:
        cur = conn.execute(query, params or [])
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def execute(query, params=None):
    with get_conn() as conn:
        cur = conn.execute(query, params or [])
        return cur.lastrowid
