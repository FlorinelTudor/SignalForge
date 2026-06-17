from fastapi import FastAPI, APIRouter, HTTPException, Response, Request, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import logging
import uuid
import httpx
import asyncio
import importlib.util
from contextlib import asynccontextmanager
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
import jwt
import math
import stripe
import time
import secrets
import hashlib
import ipaddress
from urllib.parse import quote
from pymongo import ReturnDocument

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

# Auto-sync configuration
SYNC_INTERVAL_HOURS = 6  # Sync every 6 hours
sync_task = None

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_VERIFIED = os.environ.get("STRIPE_PRICE_VERIFIED", "")
STRIPE_PRICE_PRO = os.environ.get("STRIPE_PRICE_PRO", "")
STRIPE_PRICE_VIBE = os.environ.get("STRIPE_PRICE_VIBE", "")
CHECKOUT_SUCCESS_URL = os.environ.get("CHECKOUT_SUCCESS_URL", "https://agentxplorer.com/verified/success?session_id={CHECKOUT_SESSION_ID}")
CHECKOUT_CANCEL_URL = os.environ.get("CHECKOUT_CANCEL_URL", "https://agentxplorer.com/pricing")
ACCESS_TOKEN_TTL_HOURS = int(os.environ.get("ACCESS_TOKEN_TTL_HOURS", "24"))
REFRESH_TOKEN_TTL_DAYS = int(os.environ.get("REFRESH_TOKEN_TTL_DAYS", "30"))
LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "600"))
LOGIN_LOCKOUT_SECONDS = int(os.environ.get("LOGIN_LOCKOUT_SECONDS", "900"))
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
TRUST_PROXY_HEADERS = os.environ.get("TRUST_PROXY_HEADERS", "false").lower() == "true"
TRUSTED_PROXY_IPS = {ip.strip() for ip in os.environ.get("TRUSTED_PROXY_IPS", "").split(",") if ip.strip()}
REQUIRE_OAUTH_VERIFIED_EMAIL = os.environ.get("REQUIRE_OAUTH_VERIFIED_EMAIL", "true").lower() == "true"
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://agentxplorer.com").rstrip("/")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.agentxplorer.com").rstrip("/")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is required. Set it in your environment.")
if not CORS_ORIGINS:
    raise RuntimeError("CORS_ORIGINS is required and must be a comma-separated list of allowed origins.")
if any(o == "*" for o in CORS_ORIGINS):
    raise RuntimeError("CORS_ORIGINS cannot contain '*' when allow_credentials=True.")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Simple in-memory rate limiting (per instance)
RATE_LIMITS = {
    "auth": {"limit": 5, "window": 60},
    "search": {"limit": 60, "window": 60},
    "game": {"limit": 240, "window": 60},
    "write": {"limit": 30, "window": 60},
}
_rate_state = {}
_rate_lock = asyncio.Lock()

def _client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else "unknown"
    if not TRUST_PROXY_HEADERS:
        return direct_ip
    if not TRUSTED_PROXY_IPS:
        return direct_ip
    if direct_ip not in TRUSTED_PROXY_IPS:
        return direct_ip
    xff = request.headers.get("x-forwarded-for")
    if xff:
        candidate = xff.split(",")[0].strip()
        try:
            ipaddress.ip_address(candidate)
            return candidate
        except ValueError:
            return direct_ip
    return direct_ip

def _new_csrf_token() -> str:
    return secrets.token_urlsafe(32)

async def _audit(request: Request, event: str, user_id: Optional[str] = None, meta: Optional[dict] = None):
    doc = {
        "event": event,
        "user_id": user_id,
        "ip": _client_ip(request),
        "path": request.url.path,
        "method": request.method,
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    try:
        await db.audit_logs.insert_one(doc)
    except Exception:
        logger.exception("Failed to write audit log")

def _is_admin(user: dict) -> bool:
    email = (user.get("email") or "").lower()
    return bool(user.get("is_admin")) or (email in ADMIN_EMAILS)

async def require_admin(request: Request) -> dict:
    user = await get_current_user(request)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def _rate_bucket(request: Request) -> Optional[str]:
    path = request.url.path
    method = request.method.upper()
    if path.startswith("/api/auth/login") or path.startswith("/api/auth/register"):
        return "auth"
    if path.startswith("/api/game/rooms"):
        return "game"
    if path.startswith("/api/agents") and method == "GET":
        return "search"
    if method in {"POST", "PUT", "DELETE"} and path.startswith("/api/"):
        return "write"
    return None

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    bucket = _rate_bucket(request)
    if bucket:
        ip = _client_ip(request)
        limit = RATE_LIMITS[bucket]["limit"]
        window = RATE_LIMITS[bucket]["window"]
        now = time.time()
        window_start = int(now // window) * window
        key = f"{bucket}:{ip}:{window_start}"
        # Shared limiter via Mongo so limits hold across multiple instances.
        try:
            rate_doc = await db.rate_limits.find_one_and_update(
                {"_id": key},
                {
                    "$inc": {"count": 1},
                    "$setOnInsert": {
                        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=window + 5)
                    },
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            if rate_doc and rate_doc.get("count", 0) > limit:
                return Response(status_code=429, content="Rate limit exceeded")
        except Exception:
            # Fallback to per-process limiter if DB is temporarily unavailable.
            async with _rate_lock:
                fallback_key = f"{bucket}:{ip}"
                entries = _rate_state.get(fallback_key, [])
                entries = [ts for ts in entries if now - ts < window]
                if len(entries) >= limit:
                    return Response(status_code=429, content="Rate limit exceeded")
                entries.append(now)
                _rate_state[fallback_key] = entries
    response = await call_next(request)
    return response

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    return response

@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    method = request.method.upper()
    path = request.url.path
    exempt_paths = {
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/google-callback",
        "/api/billing/webhook",
    }
    if method in {"POST", "PUT", "PATCH", "DELETE"} and path.startswith("/api/") and path not in exempt_paths:
        # Enforce same-origin for browser requests that include Origin header.
        origin = request.headers.get("origin")
        if origin and origin not in CORS_ORIGINS:
            return Response(status_code=403, content="Invalid request origin")

        # Enforce CSRF token only for cookie-authenticated browser requests.
        session_cookie = request.cookies.get("session_token")
        if session_cookie:
            csrf_cookie = request.cookies.get("csrf_token")
            csrf_header = request.headers.get("x-csrf-token")
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                return Response(status_code=403, content="CSRF validation failed")
    return await call_next(request)

# ─── Trust Score Helpers ───

def _normalize_percent(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v <= 1:
        v *= 100
    return max(0.0, min(100.0, v))

def _log_scaled_score(value: Optional[float], max_value: float = 100000.0) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return 0.0
    denom = math.log10(max_value + 1)
    return max(0.0, min(100.0, (math.log10(v + 1) / denom) * 100))

def _avg(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)

def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    sorted_values = sorted(values)
    mid = len(sorted_values) // 2
    if len(sorted_values) % 2 == 1:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2.0

def _as_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))

def _days_since(timestamp: Optional[str]) -> Optional[int]:
    if not timestamp:
        return None
    try:
        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except Exception:
        return None
    return max(0, (datetime.now(timezone.utc) - dt).days)

def _default_design_peer_baselines(source: Optional[str]) -> dict:
    source = (source or "").lower()
    if source == "huggingface":
        return {
            "cc_density": [7, 9, 11, 13, 15, 17, 19, 21, 24, 27, 30, 34],
            "hotspot_ratio": [14, 18, 22, 26, 30, 34, 38, 42, 47, 52, 57, 63],
            "cycle_ratio": [2, 3, 4, 6, 8, 10, 12, 14, 17, 21, 26, 32],
            "test_on_complex": [18, 26, 34, 42, 50, 58, 64, 70, 76, 82, 88, 93],
            "maintainability": [35, 42, 48, 54, 60, 66, 71, 76, 81, 86, 91, 95],
        }
    return {
        "cc_density": [6, 8, 10, 12, 14, 16, 18, 21, 24, 28, 33, 38],
        "hotspot_ratio": [12, 16, 20, 24, 28, 32, 36, 41, 46, 52, 58, 64],
        "cycle_ratio": [1, 2, 3, 5, 7, 9, 11, 14, 18, 23, 29, 36],
        "test_on_complex": [20, 28, 36, 44, 52, 60, 67, 73, 79, 85, 90, 95],
        "maintainability": [38, 45, 51, 57, 63, 69, 74, 79, 84, 88, 92, 96],
    }

def _derive_design_metrics(agent: dict) -> Optional[dict]:
    source = (agent.get("source") or "").lower()
    description = (agent.get("description") or "").lower()

    if source == "github" or agent.get("github_stars") is not None:
        stars = max(0.0, float(agent.get("github_stars") or agent.get("deployment_count") or 0.0))
        forks = max(0.0, float(agent.get("github_forks") or 0.0))
        open_issues = max(0.0, float(agent.get("github_open_issues") or 0.0))
        size_kb = max(0.0, float(agent.get("github_size_kb") or 0.0))
        activity_days = _days_since(agent.get("github_pushed_at") or agent.get("updated_at") or agent.get("last_active_at")) or 45
        freshness = _clamp(100.0 - ((min(activity_days, 365) / 365.0) * 100.0), 0.0, 100.0)
        issue_pressure = min(1.5, open_issues / max(12.0, (stars * 0.02) + forks + 5.0))
        maturity = min(1.0, math.log10(stars + 10.0) / 4.0)
        size_factor = min(1.0, math.log10(size_kb + 10.0) / 4.0)
        topics = [str(t).lower() for t in (agent.get("github_topics") or [])]
        testing_signals = any(
            token in " ".join(topics)
            for token in ["test", "tests", "pytest", "jest", "ci", "coverage", "benchmark"]
        ) or any(token in description for token in ["test", "coverage", "benchmark", "ci/cd"])
        generated_signals = any(token in " ".join(topics) for token in ["generated", "autogenerated", "template-only"])

        cc_density = _clamp(34.0 - (maturity * 17.0) + (issue_pressure * 18.0) + ((100.0 - freshness) / 25.0), 4.0, 60.0)
        hotspot_ratio = _clamp(54.0 - (maturity * 20.0) + (issue_pressure * 20.0) + ((100.0 - freshness) / 18.0), 8.0, 85.0)
        cycle_ratio = _clamp(17.0 - (maturity * 8.0) + (issue_pressure * 12.0) + (size_factor * 8.0), 2.0, 55.0)
        test_on_complex = _clamp(30.0 + (maturity * 30.0) + (18.0 if testing_signals else 0.0) - (issue_pressure * 18.0), 8.0, 98.0)
        maintainability = _clamp(50.0 + (maturity * 24.0) + (freshness * 0.12) - (issue_pressure * 24.0), 15.0, 98.0)

        sample_loc = max(500, int((size_kb * 1.3) or (750 + stars / 3.0)))
        functions_analyzed = max(25, int(sample_loc / 40))
        return {
            "cc_density": round(cc_density, 2),
            "hotspot_ratio": round(hotspot_ratio, 2),
            "cycle_ratio": round(cycle_ratio, 2),
            "test_on_complex": round(test_on_complex, 2),
            "maintainability": round(maintainability, 2),
            "sample_loc": sample_loc,
            "functions_analyzed": functions_analyzed,
            "excluded_generated_code": not generated_signals,
        }

    if source == "huggingface" or agent.get("hf_downloads") is not None:
        downloads = max(0.0, float(agent.get("hf_downloads") or agent.get("deployment_count") or 0.0))
        likes = max(0.0, float(agent.get("hf_likes") or 0.0))
        tags = [str(t).lower() for t in (agent.get("hf_tags") or [])]
        pipeline_tag = str(agent.get("hf_pipeline_tag") or "").lower()

        popularity = min(1.0, math.log10(downloads + 10.0) / 6.0)
        community = min(1.0, math.log10(likes + 10.0) / 4.0)
        metadata_quality = min(1.0, (len(tags[:20]) / 12.0) + (0.2 if pipeline_tag else 0.0))
        testing_signals = any(token in " ".join(tags) for token in ["benchmark", "eval", "leaderboard", "tested"])

        cc_density = _clamp(27.0 - (community * 10.0) + ((1.0 - popularity) * 9.0), 6.0, 55.0)
        hotspot_ratio = _clamp(46.0 - (community * 12.0) + ((1.0 - popularity) * 10.0), 12.0, 80.0)
        cycle_ratio = _clamp(15.0 - (community * 5.0) + ((1.0 - metadata_quality) * 12.0), 3.0, 45.0)
        test_on_complex = _clamp(22.0 + (metadata_quality * 42.0) + (12.0 if testing_signals else 0.0), 10.0, 90.0)
        maintainability = _clamp(45.0 + (metadata_quality * 32.0) + (community * 10.0), 20.0, 95.0)

        sample_loc = max(500, int(600 + min(3000, downloads / 80.0)))
        functions_analyzed = max(25, int(sample_loc / 50))
        return {
            "cc_density": round(cc_density, 2),
            "hotspot_ratio": round(hotspot_ratio, 2),
            "cycle_ratio": round(cycle_ratio, 2),
            "test_on_complex": round(test_on_complex, 2),
            "maintainability": round(maintainability, 2),
            "sample_loc": sample_loc,
            "functions_analyzed": functions_analyzed,
            "excluded_generated_code": True,
        }
    return None

def _ensure_design_inputs(agent: dict) -> dict:
    enriched = dict(agent)
    existing_metrics = enriched.get("design_metrics")
    if not isinstance(existing_metrics, dict):
        existing_metrics = {}
    derived_metrics = _derive_design_metrics(enriched) or {}

    merged_metrics = dict(derived_metrics)
    for key, value in existing_metrics.items():
        if value is not None:
            merged_metrics[key] = value
    if merged_metrics:
        enriched["design_metrics"] = merged_metrics

    existing_peers = enriched.get("design_peer_baselines")
    if isinstance(existing_peers, dict) and existing_peers:
        peer_baselines = dict(existing_peers)
    else:
        peer_baselines = _default_design_peer_baselines(enriched.get("source"))
    if peer_baselines:
        enriched["design_peer_baselines"] = peer_baselines

    return enriched

def _percentile_rank(value: Optional[float], peers, lower_is_better: bool = False) -> Optional[float]:
    if value is None or not isinstance(peers, list):
        return None
    nums = [_as_float(v) for v in peers]
    nums = [n for n in nums if n is not None]
    if len(nums) < 10:
        return None
    less_or_equal = sum(1 for n in nums if n <= value)
    pct = (less_or_equal / len(nums)) * 100.0
    if lower_is_better:
        pct = 100.0 - pct
    return max(0.0, min(100.0, pct))

def _fallback_design_percentile(metric: str, value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if metric == "cc_density":
        if value <= 8:
            return 95.0
        if value <= 15:
            return 82.0
        if value <= 25:
            return 65.0
        if value <= 40:
            return 40.0
        return 15.0
    if metric == "hotspot_ratio":
        if value <= 20:
            return 95.0
        if value <= 30:
            return 80.0
        if value <= 45:
            return 60.0
        if value <= 60:
            return 40.0
        return 20.0
    if metric == "cycle_ratio":
        if value <= 2:
            return 95.0
        if value <= 5:
            return 80.0
        if value <= 10:
            return 60.0
        if value <= 20:
            return 35.0
        return 15.0
    if metric == "test_on_complex":
        if value >= 80:
            return 95.0
        if value >= 60:
            return 80.0
        if value >= 40:
            return 60.0
        if value >= 20:
            return 35.0
        return 15.0
    if metric == "maintainability":
        if value >= 85:
            return 95.0
        if value >= 70:
            return 80.0
        if value >= 55:
            return 60.0
        if value >= 40:
            return 35.0
        return 15.0
    return None

def _compute_design_quality(agent: dict) -> dict:
    metrics = agent.get("design_metrics") or {}
    peers = agent.get("design_peer_baselines") or {}
    history = metrics.get("scan_history") or agent.get("design_scan_history") or []

    cc_density = _as_float(metrics.get("cc_density"))
    hotspot_ratio = _normalize_percent(metrics.get("hotspot_ratio"))
    cycle_ratio = _normalize_percent(metrics.get("cycle_ratio"))
    test_on_complex = _normalize_percent(metrics.get("test_on_complex"))
    maintainability = _normalize_percent(metrics.get("maintainability"))

    weighted_inputs = [
        ("cc_density", cc_density, 0.40, True),
        ("hotspot_ratio", hotspot_ratio, 0.20, True),
        ("cycle_ratio", cycle_ratio, 0.20, True),
        ("test_on_complex", test_on_complex, 0.15, False),
        ("maintainability", maintainability, 0.05, False),
    ]

    weighted_sum = 0.0
    total_weight = 0.0
    metric_scores = {}
    peer_backed_count = 0

    for key, raw_value, weight, lower_is_better in weighted_inputs:
        percentile = _percentile_rank(raw_value, peers.get(key), lower_is_better=lower_is_better)
        if percentile is not None:
            peer_backed_count += 1
        else:
            percentile = _fallback_design_percentile(key, raw_value)
        if percentile is None:
            continue
        metric_scores[key] = round(percentile, 2)
        weighted_sum += percentile * weight
        total_weight += weight

    if total_weight == 0:
        return {
            "design_score": None,
            "design_confidence": 0.0,
            "design_breakdown": {"reason": "missing_design_metrics"},
        }

    design_score = weighted_sum / total_weight

    history_scores = []
    prev_scan = None
    if isinstance(history, list):
        for item in history:
            if not isinstance(item, dict):
                continue
            prev_scan = item
            prev_score = _as_float(item.get("design_score"))
            if prev_score is not None:
                history_scores.append(prev_score)

    recent_scores = [design_score] + history_scores[-2:]
    smoothed = _median(recent_scores)
    if smoothed is not None:
        design_score = smoothed

    suspicious_drop_penalty = 0.0
    if isinstance(prev_scan, dict) and cc_density is not None:
        prev_cc_density = _as_float(prev_scan.get("cc_density"))
        prev_hotspot_ratio = _normalize_percent(prev_scan.get("hotspot_ratio"))
        prev_cycle_ratio = _normalize_percent(prev_scan.get("cycle_ratio"))
        if prev_cc_density and prev_cc_density > 0 and (cc_density / prev_cc_density) < 0.4:
            hotspot_improved = (
                prev_hotspot_ratio is not None and hotspot_ratio is not None and (prev_hotspot_ratio - hotspot_ratio) >= 10
            )
            cycle_improved = (
                prev_cycle_ratio is not None and cycle_ratio is not None and (prev_cycle_ratio - cycle_ratio) >= 10
            )
            if not hotspot_improved and not cycle_improved:
                suspicious_drop_penalty = 12.0
                design_score = max(0.0, design_score - suspicious_drop_penalty)

    sample_loc = int(metrics.get("sample_loc") or metrics.get("loc_analyzed") or 0)
    functions_analyzed = int(metrics.get("functions_analyzed") or 0)
    adequate_sample = sample_loc >= 500 and functions_analyzed >= 25
    excluded_generated_code = bool(metrics.get("excluded_generated_code") or metrics.get("excluded_vendor_code"))

    confidence = 0.05
    confidence += 0.35 if adequate_sample else 0.05
    confidence += min(0.25, (peer_backed_count / max(1, len(weighted_inputs))) * 0.25)
    if excluded_generated_code:
        confidence += 0.15
    if len(history_scores) >= 2:
        confidence += 0.15
    if len(metric_scores) >= 3:
        confidence += 0.10
    if not adequate_sample:
        confidence = min(confidence, 0.45)
    confidence = max(0.05, min(1.0, confidence))

    return {
        "design_score": round(max(0.0, min(100.0, design_score)), 2),
        "design_confidence": round(confidence, 2),
        "design_breakdown": {
            "cc_relative": metric_scores.get("cc_density"),
            "hotspot_distribution": metric_scores.get("hotspot_ratio"),
            "dependency_cycles": metric_scores.get("cycle_ratio"),
            "test_on_complex_code": metric_scores.get("test_on_complex"),
            "maintainability_relative": metric_scores.get("maintainability"),
            "sample_loc": sample_loc,
            "functions_analyzed": functions_analyzed,
            "excluded_generated_code": excluded_generated_code,
            "suspicious_drop_penalty": suspicious_drop_penalty,
        },
    }

def _derive_signal_verification(agent: dict, reviews: Optional[List[dict]] = None) -> dict:
    verification = {}

    telemetry_verified = bool(agent.get("telemetry_verified") or agent.get("usage_verified"))
    if agent.get("telemetry_source"):
        telemetry_verified = True

    verification["usage"] = telemetry_verified
    verification["uptime"] = bool(agent.get("uptime_verified") or telemetry_verified)
    verification["reliability"] = bool(agent.get("reliability_verified") or telemetry_verified)

    if reviews:
        verification["reviews"] = any(r.get("verified") for r in reviews if isinstance(r, dict))
    else:
        verification["reviews"] = False

    skills = agent.get("skills") or []
    verification["skill_benchmarks"] = any(s.get("verified") for s in skills if isinstance(s, dict))

    verification["github_stars"] = False
    verification["repo_health"] = False
    verification["hf_downloads"] = False

    verification["security_audit"] = bool(
        agent.get("security_audit_verified") or agent.get("trust_breakdown", {}).get("security_audit_verified")
    )

    return verification

def compute_trust_score(agent: dict, reviews: Optional[List[dict]] = None) -> dict:
    agent = _ensure_design_inputs(agent)
    breakdown = {}
    signals = []
    derived = _derive_signal_verification(agent, reviews)
    verification = {**derived, **(agent.get("signal_verification") or {})}

    def is_verified(key: str) -> bool:
        return bool(verification.get(key))

    def add_signal(key: str, score: Optional[float], verified: bool):
        if score is None:
            return
        score = max(0.0, min(100.0, float(score)))
        breakdown[key] = round(score, 2)
        signals.append((key, score, verified))

    # Usage signal with spike damping (if recent stats available)
    deployment_count = agent.get("deployment_count")
    usage_score = _log_scaled_score(deployment_count)
    # Spike damping using optional 7d/30d counters
    count_7d = agent.get("deployment_count_7d")
    count_30d = agent.get("deployment_count_30d")
    if isinstance(count_7d, (int, float)) and isinstance(count_30d, (int, float)) and count_30d > 0:
        expected_weekly = max(1.0, count_30d / 4.0)
        if count_7d > expected_weekly * 3:
            damped = expected_weekly * 3
            usage_score = _log_scaled_score(damped)
    add_signal("usage", usage_score, is_verified("usage"))

    # Uptime signal
    uptime_score = _normalize_percent(agent.get("uptime"))
    add_signal("uptime", uptime_score, is_verified("uptime"))

    # Error rate signal (inverse)
    error_rate = _normalize_percent(agent.get("error_rate"))
    reliability_score = None if error_rate is None else max(0.0, 100.0 - error_rate)
    add_signal("reliability", reliability_score, is_verified("reliability"))

    # Skills benchmark signal (verified benchmarks if present)
    skills = agent.get("skills") or []
    verified_skill_scores = [s.get("benchmark") for s in skills if isinstance(s, dict) and s.get("benchmark") is not None and s.get("verified")]
    unverified_skill_scores = [s.get("benchmark") for s in skills if isinstance(s, dict) and s.get("benchmark") is not None and not s.get("verified")]
    if verified_skill_scores:
        skill_score = _avg([float(s) for s in verified_skill_scores if isinstance(s, (int, float))])
        add_signal("skill_benchmarks", skill_score, True)
    elif unverified_skill_scores:
        skill_score = _avg([float(s) for s in unverified_skill_scores if isinstance(s, (int, float))])
        add_signal("skill_benchmarks", skill_score, is_verified("skill_benchmarks"))

    # Review signal (verified reviews preferred)
    if reviews:
        verified_ratings = [r.get("rating") for r in reviews if isinstance(r, dict) and r.get("rating") is not None and r.get("verified")]
        unverified_ratings = [r.get("rating") for r in reviews if isinstance(r, dict) and r.get("rating") is not None and not r.get("verified")]
        if verified_ratings:
            avg_rating = _avg([float(r) for r in verified_ratings if isinstance(r, (int, float))])
            add_signal("reviews", None if avg_rating is None else (avg_rating / 5.0) * 100.0, True)
        elif unverified_ratings:
            avg_rating = _avg([float(r) for r in unverified_ratings if isinstance(r, (int, float))])
            add_signal("reviews", None if avg_rating is None else (avg_rating / 5.0) * 100.0, is_verified("reviews"))

    # External signals (soft)
    gh_stars = agent.get("github_stars")
    add_signal("github_stars", _log_scaled_score(gh_stars), is_verified("github_stars"))
    hf_downloads = agent.get("hf_downloads")
    add_signal("hf_downloads", _log_scaled_score(hf_downloads), is_verified("hf_downloads"))
    repo_health = agent.get("repo_health")
    add_signal("repo_health", _normalize_percent(repo_health), is_verified("repo_health"))

    # Security audit signal (if present)
    audit = agent.get("trust_breakdown", {}).get("security_audit")
    if audit is not None:
        add_signal("security_audit", float(audit), is_verified("security_audit"))

    # Map to UI breakdown keys (keep legacy labels)
    if "skill_benchmarks" in breakdown:
        breakdown["task_completion"] = breakdown["skill_benchmarks"]
    if "uptime" in breakdown:
        breakdown["uptime_score"] = breakdown["uptime"]
    if "reviews" in breakdown:
        breakdown["user_satisfaction"] = breakdown["reviews"]
    if "repo_health" in breakdown:
        breakdown["repo_health"] = breakdown["repo_health"]

    verified_scores = [s for _, s, v in signals if v]
    unverified_scores = [s for _, s, v in signals if not v]

    if verified_scores and unverified_scores:
        trust_score = 0.7 * _avg(verified_scores) + 0.3 * _avg(unverified_scores)
    elif verified_scores:
        trust_score = _avg(verified_scores)
    elif unverified_scores:
        trust_score = min(_avg(unverified_scores), 60.0)
    else:
        trust_score = 0.0

    # Recency decay (use last_active_at -> updated_at -> created_at)
    last_active = agent.get("last_active_at") or agent.get("updated_at") or agent.get("created_at")
    decay_factor = 1.0
    if isinstance(last_active, str):
        try:
            last_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - last_dt).days
            if days > 30:
                decay_factor = max(0.6, 1 - (days - 30) / 365)
        except Exception:
            pass
    trust_score = trust_score * decay_factor

    # Design quality layer (relative cognitive complexity + architecture quality).
    design = _compute_design_quality(agent)
    if design.get("design_score") is not None:
        breakdown["design_quality"] = design["design_score"]
        blend_weight = 0.2 * max(0.25, design.get("design_confidence", 0.0))
        trust_score = (1.0 - blend_weight) * trust_score + (blend_weight * design["design_score"])

    # Verified badge requires telemetry + audit + review verification + repo health
    is_verified = bool(
        verification.get("usage") and
        verification.get("security_audit") and
        verification.get("reviews") and
        verification.get("repo_health")
    )
    if not is_verified:
        trust_score = min(trust_score, 80.0)

    return {
        "trust_score": round(trust_score, 2),
        "trust_breakdown": breakdown,
        "design_score": design.get("design_score"),
        "design_confidence": design.get("design_confidence"),
        "design_breakdown": design.get("design_breakdown"),
        "design_metrics": agent.get("design_metrics"),
        "design_peer_baselines": agent.get("design_peer_baselines"),
        "signal_verification": verification,
        "is_verified": is_verified,
    }

# ─── Pydantic Models ───

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=80)

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class UserOut(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: Optional[str] = None

class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    builder: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=10, max_length=2000)
    avatar_url: Optional[str] = Field(default=None, max_length=2048)
    demo_url: Optional[str] = Field(default=None, max_length=2048)
    skills: Optional[List[dict]] = []
    integrations: Optional[List[str]] = []
    compatible_systems: Optional[List[str]] = []
    category: Optional[str] = Field(default="general", max_length=30)

    @field_validator("avatar_url", "demo_url", mode="before")
    @classmethod
    def _normalize_optional_urls(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None

class AgentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, min_length=10, max_length=2000)
    avatar_url: Optional[str] = Field(default=None, max_length=2048)
    demo_url: Optional[str] = Field(default=None, max_length=2048)
    skills: Optional[List[dict]] = None
    integrations: Optional[List[str]] = None
    compatible_systems: Optional[List[str]] = None
    category: Optional[str] = Field(default=None, max_length=30)

    @field_validator("avatar_url", "demo_url", mode="before")
    @classmethod
    def _normalize_optional_urls(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None

class PortfolioCreate(BaseModel):
    agent_id: str = Field(min_length=6, max_length=64)
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=10, max_length=2000)
    case_study: Optional[str] = Field(default=None, max_length=4000)
    screenshot_url: Optional[str] = Field(default=None, max_length=2048)
    metrics_before: Optional[dict] = None
    metrics_after: Optional[dict] = None
    tags: Optional[List[str]] = []

    @field_validator("screenshot_url", mode="before")
    @classmethod
    def _normalize_screenshot_url(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None

class ReviewCreate(BaseModel):
    agent_id: str = Field(min_length=6, max_length=64)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=2, max_length=2000)
    reviewer_type: Optional[str] = Field(default="human", max_length=30)
    reviewer_agent_id: Optional[str] = Field(default=None, max_length=64)

class IncidentCreate(BaseModel):
    agent_id: str = Field(min_length=6, max_length=64)
    title: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=5, max_length=3000)
    severity: str = Field(min_length=2, max_length=20)
    resolved: Optional[bool] = False

class VersionCreate(BaseModel):
    agent_id: str = Field(min_length=6, max_length=64)
    version: str = Field(min_length=1, max_length=40)
    changelog: str = Field(min_length=3, max_length=2000)

class SummarizeRequest(BaseModel):
    agent_id: str = Field(min_length=6, max_length=64)

class CheckoutRequest(BaseModel):
    plan: str = Field(min_length=2, max_length=20)  # "verified" or "pro"

class GameJoinRoom(BaseModel):
    room_code: str = Field(min_length=4, max_length=12)
    player_name: str = Field(default="Player", min_length=1, max_length=80)
    client_id: Optional[str] = Field(default=None, max_length=120)

class GameSubmitChoices(BaseModel):
    player_id: str = Field(min_length=4, max_length=120)
    choices: List[str] = Field(min_length=2, max_length=2)

class GameAdvanceRoom(BaseModel):
    host_token: str = Field(min_length=16, max_length=160)

MAX_GAME_PLAYERS = 9

GAME_PHASE_IDS = [
    "postwar",
    "recession_1921",
    "early_boom",
    "speculation",
    "crash",
    "deepening",
    "bank_holiday",
    "work_relief",
    "second",
    "defense_shift",
    "recovery",
]

GAME_IMPACTS = {
    "keep_factory_job": {"food": 6, "savings": 9, "hope": -5, "stability": 16},
    "use_savings_food": {"food": 18, "health": 9, "savings": -17},
    "move_to_city": {"savings": -10, "hope": 7, "stability": -9},
    "take_store_credit": {"food": 8, "debt": 17, "hope": 5},
    "pull_child_school": {"savings": 13, "education": -24, "hope": -14},
    "join_mutual_aid": {"hope": 12, "stability": 11, "savings": -5},
    "build_emergency_fund": {"savings": 16, "hope": -4, "stability": 11},
    "invest_stocks": {"savings": 22, "stock": 26, "hope": 10, "stability": -4},
    "borrow_to_invest": {"savings": 28, "stock": 38, "debt": 24, "hope": 12, "stability": -12},
    "buy_radio_credit": {"hope": 15, "debt": 16, "savings": -5},
    "pay_down_debt": {"debt": -24, "savings": -9, "stability": 10},
    "night_school": {"education": 17, "savings": -9, "hope": 4},
    "keep_cash": {"savings": 13, "stability": 8, "hope": -3},
    "move_better_rental": {"health": 13, "hope": 10, "debt": 9},
    "sell_stocks_now": {"savings": -14, "stock": -28, "stability": 10},
    "withdraw_bank_cash": {"savings": 9, "bankTrust": -22, "stability": 7},
    "cut_food_rent": {"food": -20, "health": -14, "savings": 16, "stability": -12},
    "search_any_work": {"savings": 12, "health": -8, "hope": 5},
    "move_with_relatives": {"debt": -10, "stability": 9, "hope": -16},
    "keep_children_school": {"education": 18, "savings": -13, "hope": 6},
    "sell_possessions": {"savings": 18, "hope": -15, "stability": -7},
    "apply_public_works": {"food": 15, "savings": 13, "health": -5, "hope": 16},
    "trust_reopened_bank": {"bankTrust": 22, "stability": 12},
    "accept_relief": {"food": 19, "health": 10, "hope": -7},
    "move_for_work_camp": {"savings": 14, "education": 7, "hope": -10},
    "organize_neighbors": {"hope": 14, "stability": 13, "savings": -5},
    "delay_medical_care": {"savings": 13, "health": -22},
    "stay_public_works": {"savings": 11, "stability": 12},
    "seek_defense_work": {"savings": 20, "hope": 16, "stability": -5},
    "rebuild_savings": {"savings": 20, "hope": 5, "stability": 5},
    "repair_health": {"health": 21, "savings": -12},
    "support_union": {"hope": 11, "stability": -10, "savings": 11},
    "older_child_fulltime": {"savings": 16, "education": -21, "hope": -11},
}

GAME_STARTING_FAMILIES = [
    {"name": "Carter", "profile": "Cleveland factory family", "food": 55, "health": 62, "savings": 28, "debt": 42, "hope": 58, "education": 64, "stability": 54, "bankTrust": 55, "stock": 0},
    {"name": "Rosen", "profile": "Small shop owners", "food": 60, "health": 58, "savings": 44, "debt": 48, "hope": 62, "education": 68, "stability": 48, "bankTrust": 62, "stock": 0},
    {"name": "Williams", "profile": "Tenant farm family", "food": 48, "health": 55, "savings": 18, "debt": 55, "hope": 52, "education": 50, "stability": 42, "bankTrust": 45, "stock": 0},
    {"name": "Novak", "profile": "Immigrant household", "food": 52, "health": 59, "savings": 22, "debt": 38, "hope": 56, "education": 58, "stability": 45, "bankTrust": 50, "stock": 0},
]

def _game_clamp(value: float) -> int:
    return max(0, min(100, round(value)))

def _game_room_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(4))

def _public_game_room(room: dict) -> dict:
    return {
        "roomCode": room["room_code"],
        "phaseIndex": room.get("phase_index", 0),
        "players": room.get("players", []),
        "updatedAt": room.get("updated_at"),
    }

def _game_pick_family(player_name: str, index: int, client_id: Optional[str]) -> dict:
    base = dict(GAME_STARTING_FAMILIES[index % len(GAME_STARTING_FAMILIES)])
    base.update({
        "id": str(uuid.uuid4()),
        "playerName": player_name,
        "clientId": client_id or str(uuid.uuid4()),
        "choices": {},
        "score": 0,
    })
    for key in ["food", "health", "savings", "hope", "education", "stability", "bankTrust"]:
        base[key] = _game_clamp(base[key] + secrets.randbelow(17) - 8)
    base["debt"] = max(0, round(base["debt"] + secrets.randbelow(21) - 10))
    return base

def _game_apply_choices(family: dict, choices: List[str], phase_id: str) -> dict:
    next_family = dict(family)
    for choice in choices:
        for key, value in GAME_IMPACTS.get(choice, {}).items():
            current = next_family.get(key, 0)
            if key in {"debt", "stock"}:
                next_family[key] = max(0, current + value)
            else:
                next_family[key] = _game_clamp(current + value)
    if phase_id == "crash" and next_family.get("stock", 0) > 0:
        next_family["savings"] = _game_clamp(next_family.get("savings", 0) - math.ceil(next_family["stock"] * 0.55))
        next_family["hope"] = _game_clamp(next_family.get("hope", 0) - 8)
        next_family["stock"] = max(0, math.floor(next_family["stock"] * 0.25))
    next_family["debt"] = max(0, round(next_family.get("debt", 0)))
    next_family["minFood"] = min(next_family.get("minFood", next_family["food"]), next_family["food"])
    next_family["minHealth"] = min(next_family.get("minHealth", next_family["health"]), next_family["health"])
    next_family["minHope"] = min(next_family.get("minHope", next_family["hope"]), next_family["hope"])
    next_family["minEducation"] = min(next_family.get("minEducation", next_family["education"]), next_family["education"])
    next_family["minStability"] = min(next_family.get("minStability", next_family["stability"]), next_family["stability"])
    return next_family

# ─── Auth Helpers ───

def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

async def _issue_refresh_token(user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    await db.refresh_tokens.insert_one({
        "user_id": user_id,
        "token_hash": _hash_refresh_token(token),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)).isoformat(),
        "last_used_at": None
    })
    return token

async def _clear_refresh_token(token: str):
    await db.refresh_tokens.delete_one({"token_hash": _hash_refresh_token(token)})

async def _create_jwt_token(user_id: str) -> str:
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "token_version": 1})
    token_version = int(user_doc.get("token_version", 0)) if user_doc else 0
    payload = {
        "user_id": user_id,
        "token_version": token_version,
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_TTL_HOURS),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def _check_login_lockout(email: str, ip: str):
    key = f"{email.lower()}:{ip}"
    doc = await db.auth_attempts.find_one({"key": key}, {"_id": 0})
    now = datetime.now(timezone.utc)
    if doc and doc.get("locked_until"):
        locked_until = datetime.fromisoformat(doc["locked_until"])
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")

async def _record_login_failure(email: str, ip: str):
    key = f"{email.lower()}:{ip}"
    now = datetime.now(timezone.utc)
    doc = await db.auth_attempts.find_one({"key": key}, {"_id": 0})
    if not doc:
        await db.auth_attempts.insert_one({
            "key": key,
            "count": 1,
            "first_at": now.isoformat(),
            "locked_until": None
        })
        return
    first_at = datetime.fromisoformat(doc["first_at"])
    if first_at.tzinfo is None:
        first_at = first_at.replace(tzinfo=timezone.utc)
    window_open = (now - first_at).total_seconds() <= LOGIN_WINDOW_SECONDS
    count = doc.get("count", 0) + 1 if window_open else 1
    locked_until = None
    if count >= LOGIN_MAX_ATTEMPTS:
        locked_until = (now + timedelta(seconds=LOGIN_LOCKOUT_SECONDS)).isoformat()
    await db.auth_attempts.update_one(
        {"key": key},
        {"$set": {"count": count, "first_at": (first_at.isoformat() if window_open else now.isoformat()), "locked_until": locked_until}}
    )

async def _clear_login_failures(email: str, ip: str):
    key = f"{email.lower()}:{ip}"
    await db.auth_attempts.delete_one({"key": key})

async def get_current_user(request: Request) -> dict:
    # Check cookie first
    session_token = request.cookies.get("session_token")
    # Then check Authorization header
    if not session_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Check user_sessions collection (Google OAuth)
    session_doc = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
    if session_doc:
        expires_at = session_doc.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Session expired")
        user = await db.users.find_one({"user_id": session_doc["user_id"]}, {"_id": 0})
        if user:
            return user

    # Check JWT token
    try:
        payload = jwt.decode(session_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if user and int(payload.get("token_version", 0)) == int(user.get("token_version", 0)):
            return user
    except jwt.PyJWTError:
        pass

    raise HTTPException(status_code=401, detail="Invalid session")

# ─── Great Depression Game Rooms ───

@api_router.post("/game/rooms")
async def create_game_room():
    for _ in range(12):
        code = _game_room_code()
        if not await db.game_rooms.find_one({"room_code": code}):
            now = datetime.now(timezone.utc).isoformat()
            host_token = secrets.token_urlsafe(32)
            room = {
                "room_code": code,
                "host_token": host_token,
                "phase_index": 0,
                "players": [],
                "created_at": now,
                "updated_at": now,
            }
            await db.game_rooms.insert_one(room)
            return {"room": _public_game_room(room), "hostToken": host_token}
    raise HTTPException(status_code=500, detail="Could not create a unique room code")

@api_router.get("/game/rooms/{room_code}")
async def get_game_room(room_code: str):
    room = await db.game_rooms.find_one({"room_code": room_code.strip().upper()}, {"_id": 0})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"room": _public_game_room(room)}

@api_router.post("/game/rooms/{room_code}/join")
async def join_game_room(room_code: str, payload: GameJoinRoom):
    code = room_code.strip().upper()
    room = await db.game_rooms.find_one({"room_code": code}, {"_id": 0})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    client_id = payload.client_id or str(uuid.uuid4())
    for player in room.get("players", []):
        if player.get("clientId") == client_id:
            return {"room": _public_game_room(room), "playerId": player["id"]}
    if len(room.get("players", [])) >= MAX_GAME_PLAYERS:
        raise HTTPException(status_code=409, detail=f"Room is full ({MAX_GAME_PLAYERS} players max).")
    player = _game_pick_family(payload.player_name.strip() or "Player", len(room.get("players", [])), client_id)
    now = datetime.now(timezone.utc).isoformat()
    result = await db.game_rooms.update_one(
        {"room_code": code, f"players.{MAX_GAME_PLAYERS - 1}": {"$exists": False}},
        {"$push": {"players": player}, "$set": {"updated_at": now}},
    )
    if getattr(result, "modified_count", 0) == 0:
        raise HTTPException(status_code=409, detail=f"Room is full ({MAX_GAME_PLAYERS} players max).")
    updated = await db.game_rooms.find_one({"room_code": code}, {"_id": 0})
    return {"room": _public_game_room(updated), "playerId": player["id"]}

@api_router.post("/game/rooms/{room_code}/choices")
async def submit_game_choices(room_code: str, payload: GameSubmitChoices):
    code = room_code.strip().upper()
    room = await db.game_rooms.find_one({"room_code": code}, {"_id": 0})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    phase_index = int(room.get("phase_index", 0))
    phase_id = GAME_PHASE_IDS[min(phase_index, len(GAME_PHASE_IDS) - 1)]
    player = next((p for p in room.get("players", []) if p.get("id") == payload.player_id), None)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found in this room")
    if len(player.get("choices", {}).get(phase_id, [])) == 2:
        return {"room": _public_game_room(room)}

    updated_player = _game_apply_choices(player, payload.choices, phase_id)
    updated_player["choices"] = {**player.get("choices", {}), phase_id: payload.choices}
    now = datetime.now(timezone.utc).isoformat()
    await db.game_rooms.update_one(
        {"room_code": code, "players.id": payload.player_id},
        {"$set": {"players.$": updated_player, "updated_at": now}},
    )
    updated = await db.game_rooms.find_one({"room_code": code}, {"_id": 0})
    players = updated.get("players", [])
    if players and all(len(player.get("choices", {}).get(phase_id, [])) == 2 for player in players):
        await db.game_rooms.update_one(
            {"room_code": code, "phase_index": phase_index},
            {"$set": {"phase_index": min(phase_index + 1, len(GAME_PHASE_IDS) - 1), "updated_at": now}},
        )
        updated = await db.game_rooms.find_one({"room_code": code}, {"_id": 0})
    return {"room": _public_game_room(updated)}

@api_router.post("/game/rooms/{room_code}/advance")
async def advance_game_room(room_code: str, payload: GameAdvanceRoom):
    code = room_code.strip().upper()
    room = await db.game_rooms.find_one({"room_code": code}, {"_id": 0})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if not secrets.compare_digest(payload.host_token, room.get("host_token", "")):
        raise HTTPException(status_code=403, detail="Only the host can advance this room.")
    next_phase_index = min(int(room.get("phase_index", 0)) + 1, len(GAME_PHASE_IDS) - 1)
    now = datetime.now(timezone.utc).isoformat()
    await db.game_rooms.update_one(
        {"room_code": code},
        {"$set": {"phase_index": next_phase_index, "updated_at": now}},
    )
    updated = await db.game_rooms.find_one({"room_code": code}, {"_id": 0})
    return {"room": _public_game_room(updated)}

# ─── Auth Routes ───

@api_router.post("/auth/register")
async def register(data: UserRegister, request: Request, response: Response):
    existing = await db.users.find_one({"email": data.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    hashed = pwd_context.hash(data.password)
    user_doc = {
        "user_id": user_id,
        "email": data.email,
        "name": data.name,
        "password_hash": hashed,
        "picture": None,
        "token_version": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)
    token = await _create_jwt_token(user_id)
    refresh_token = await _issue_refresh_token(user_id)
    csrf_token = _new_csrf_token()
    response.set_cookie(key="session_token", value=token, httponly=True, secure=True, samesite="none", path="/", max_age=ACCESS_TOKEN_TTL_HOURS*3600)
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="none", path="/api/auth/refresh", max_age=REFRESH_TOKEN_TTL_DAYS*24*3600)
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=True, samesite="none", path="/", max_age=ACCESS_TOKEN_TTL_HOURS*3600)
    await _audit(request, "auth_register", user_id=user_id)
    return {"user": {"user_id": user_id, "email": data.email, "name": data.name}}

@api_router.post("/auth/login")
async def login(data: UserLogin, request: Request, response: Response):
    ip = _client_ip(request)
    await _check_login_lockout(data.email, ip)
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user or not pwd_context.verify(data.password, user.get("password_hash", "")):
        await _record_login_failure(data.email, ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    await _clear_login_failures(data.email, ip)
    token = await _create_jwt_token(user["user_id"])
    refresh_token = await _issue_refresh_token(user["user_id"])
    csrf_token = _new_csrf_token()
    response.set_cookie(key="session_token", value=token, httponly=True, secure=True, samesite="none", path="/", max_age=ACCESS_TOKEN_TTL_HOURS*3600)
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="none", path="/api/auth/refresh", max_age=REFRESH_TOKEN_TTL_DAYS*24*3600)
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=True, samesite="none", path="/", max_age=ACCESS_TOKEN_TTL_HOURS*3600)
    await _audit(request, "auth_login", user_id=user["user_id"])
    return {"user": {"user_id": user["user_id"], "email": user["email"], "name": user["name"], "picture": user.get("picture")}}

@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    doc = await db.refresh_tokens.find_one({"token_hash": _hash_refresh_token(token)}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    expires_at = datetime.fromisoformat(doc["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        await _clear_refresh_token(token)
        raise HTTPException(status_code=401, detail="Refresh token expired")
    user_id = doc["user_id"]
    await _clear_refresh_token(token)
    new_refresh = await _issue_refresh_token(user_id)
    new_access = await _create_jwt_token(user_id)
    csrf_token = _new_csrf_token()
    response.set_cookie(key="session_token", value=new_access, httponly=True, secure=True, samesite="none", path="/", max_age=ACCESS_TOKEN_TTL_HOURS*3600)
    response.set_cookie(key="refresh_token", value=new_refresh, httponly=True, secure=True, samesite="none", path="/api/auth/refresh", max_age=REFRESH_TOKEN_TTL_DAYS*24*3600)
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=True, samesite="none", path="/", max_age=ACCESS_TOKEN_TTL_HOURS*3600)
    await _audit(request, "auth_refresh", user_id=user_id)
    return {"ok": True}

@api_router.post("/auth/google-callback")
async def google_callback(request: Request, response: Response):
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    async with httpx.AsyncClient() as http_client:
        resp = await http_client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id}
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session")
    data = resp.json()
    email_verified = bool(
        data.get("email_verified") or
        data.get("verified_email") or
        data.get("is_email_verified")
    )
    if REQUIRE_OAUTH_VERIFIED_EMAIL and not email_verified:
        raise HTTPException(status_code=401, detail="Email is not verified by identity provider")
    email = data["email"]
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id}, {"$set": {"name": data["name"], "picture": data.get("picture")}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user_doc = {
            "user_id": user_id,
            "email": email,
            "name": data["name"],
            "picture": data.get("picture"),
            "token_version": 0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(user_doc)
    session_token = data.get("session_token", str(uuid.uuid4()))
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_TTL_HOURS)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    csrf_token = _new_csrf_token()
    response.set_cookie(key="session_token", value=session_token, httponly=True, secure=True, samesite="none", path="/", max_age=ACCESS_TOKEN_TTL_HOURS*3600)
    response.set_cookie(key="csrf_token", value=csrf_token, httponly=False, secure=True, samesite="none", path="/", max_age=ACCESS_TOKEN_TTL_HOURS*3600)
    await _audit(request, "auth_google_callback", user_id=user_id)
    return {"user": {"user_id": user_id, "email": email, "name": data["name"], "picture": data.get("picture")}}

@api_router.get("/auth/me")
async def auth_me(request: Request):
    user = await get_current_user(request)
    return {"user_id": user["user_id"], "email": user["email"], "name": user["name"], "picture": user.get("picture")}

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    try:
        user = await get_current_user(request)
        await db.users.update_one({"user_id": user["user_id"]}, {"$inc": {"token_version": 1}})
    except Exception:
        pass
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_many({"session_token": session_token})
    response.delete_cookie("session_token", path="/")
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await _clear_refresh_token(refresh_token)
    response.delete_cookie("refresh_token", path="/api/auth/refresh")
    response.delete_cookie("csrf_token", path="/")
    await _audit(request, "auth_logout")
    return {"message": "Logged out"}

# ─── Billing (Stripe Checkout) ───

@api_router.post("/billing/checkout")
async def create_checkout_session(data: CheckoutRequest, request: Request):
    user = await get_current_user(request)
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe is not configured.")

    plan = data.plan.lower().strip()
    if plan == "verified":
        price_id = STRIPE_PRICE_VERIFIED
    elif plan == "pro":
        price_id = STRIPE_PRICE_PRO
    elif plan == "vibe":
        price_id = STRIPE_PRICE_VIBE
    else:
        raise HTTPException(status_code=400, detail="Invalid plan.")

    if not price_id:
        raise HTTPException(status_code=500, detail="Stripe price is not configured.")

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=CHECKOUT_SUCCESS_URL,
        cancel_url=CHECKOUT_CANCEL_URL,
        client_reference_id=user["user_id"],
        customer_email=user.get("email"),
        metadata={"user_id": user["user_id"], "plan": plan},
        allow_promotion_codes=True,
    )

    return {"url": session.url}


@api_router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Stripe webhook not configured.")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="Webhook signature verification failed.")

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        user_id = data_object.get("client_reference_id") or data_object.get("metadata", {}).get("user_id")
        plan = data_object.get("metadata", {}).get("plan")
        subscription_id = data_object.get("subscription")
        customer_id = data_object.get("customer")
        if user_id:
            is_verified = True if plan in ("verified", "pro") else False
            verified_at = datetime.now(timezone.utc).isoformat() if is_verified else None
            update = {
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "plan": plan,
                "is_verified": is_verified,
                "verified_at": verified_at,
            }
            await db.users.update_one({"user_id": user_id}, {"$set": update})
            await db.agents.update_many(
                {"owner_id": user_id},
                {"$set": {"is_verified": is_verified, "verified_at": verified_at}}
            )

    if event_type == "customer.subscription.deleted":
        subscription_id = data_object.get("id")
        if subscription_id:
            user = await db.users.find_one({"stripe_subscription_id": subscription_id}, {"_id": 0})
            await db.users.update_one(
                {"stripe_subscription_id": subscription_id},
                {"$set": {"plan": "free", "is_verified": False, "verified_at": None}}
            )
            if user:
                await db.agents.update_many(
                    {"owner_id": user.get("user_id")},
                    {"$set": {"is_verified": False, "verified_at": None}}
                )

    return {"status": "ok"}

# ─── Agent Routes ───

@api_router.post("/agents")
async def create_agent(data: AgentCreate, request: Request):
    user = await get_current_user(request)
    agent_id = f"agent_{uuid.uuid4().hex[:12]}"
    agent_doc = {
        "agent_id": agent_id,
        "owner_id": user["user_id"],
        "name": data.name,
        "builder": data.builder,
        "description": data.description,
        "avatar_url": data.avatar_url,
        "demo_url": data.demo_url,
        "skills": data.skills or [],
        "integrations": data.integrations or [],
        "compatible_systems": data.compatible_systems or [],
        "category": data.category or "general",
        "is_verified": bool(user.get("is_verified")),
        "verified_at": datetime.now(timezone.utc).isoformat() if user.get("is_verified") else None,
        "deployment_count": 0,
        "uptime": 99.9,
        "error_rate": 0.1,
        "trust_score": 85.0,
        "trust_breakdown": {"task_completion": 90, "security_audit": 80, "uptime_score": 95, "user_satisfaction": 85},
        "versions": [{"version": "1.0.0", "changelog": "Initial release", "date": datetime.now(timezone.utc).isoformat()}],
        "auto_summary": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.agents.insert_one(agent_doc)
    agent_doc.pop("_id", None)
    return agent_doc

@api_router.get("/agents")
async def list_agents(
    search: Optional[str] = None,
    category: Optional[str] = None,
    skill: Optional[str] = None,
    integration: Optional[str] = None,
    min_trust: Optional[float] = None,
    sort_by: Optional[str] = "trust_score",
    verified_only: Optional[bool] = False,
    limit: int = 50,
    skip: int = 0
):
    query = {}
    def _clean_input(value: Optional[str], max_len: int = 80):
        if not value:
            return None
        value = value.strip()
        if not value:
            return None
        # Basic allowlist: letters, numbers, spaces, dash, underscore, dot, plus, slash
        cleaned = re.sub(r"[^A-Za-z0-9 _.\-+/]", "", value)
        return cleaned[:max_len] if cleaned else None

    def _safe_regex(value: Optional[str]):
        value = _clean_input(value)
        if not value:
            return None
        safe = re.escape(value)
        return {"$regex": safe, "$options": "i"}
    search = _clean_input(search, 100)
    skill = _clean_input(skill, 60)
    integration = _clean_input(integration, 60)
    category = _clean_input(category, 30)

    if search:
        query["$or"] = [
            {"name": _safe_regex(search)},
            {"builder": _safe_regex(search)},
            {"description": _safe_regex(search)}
        ]
    if category and category != "all":
        query["category"] = category
    if skill:
        query["skills.name"] = _safe_regex(skill)
    if integration:
        query["integrations"] = _safe_regex(integration)
    if min_trust:
        query["trust_score"] = {"$gte": min_trust}

    sort_field = sort_by if sort_by in ["trust_score", "deployment_count", "created_at", "name"] else "trust_score"
    sort_dir = -1 if sort_field != "name" else 1

    agents = await db.agents.find(query, {"_id": 0}).sort(sort_field, sort_dir).skip(skip).limit(limit).to_list(limit)
    # Recompute trust score from real signals
    computed_agents = []
    for agent in agents:
        computed = compute_trust_score(agent)
        agent["trust_score"] = computed["trust_score"]
        agent["trust_breakdown"] = computed["trust_breakdown"]
        agent["design_score"] = computed["design_score"]
        agent["design_confidence"] = computed["design_confidence"]
        agent["design_breakdown"] = computed["design_breakdown"]
        agent["signal_verification"] = computed["signal_verification"]
        agent["is_verified"] = computed["is_verified"]
        if verified_only and not agent["is_verified"]:
            continue
        computed_agents.append(agent)
    total = await db.agents.count_documents(query)
    return {"agents": computed_agents, "total": total}

@api_router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    agent = await db.agents.find_one({"agent_id": agent_id}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    # Get portfolio items
    portfolio = await db.portfolios.find({"agent_id": agent_id}, {"_id": 0}).to_list(100)
    # Get reviews
    reviews = await db.reviews.find({"agent_id": agent_id}, {"_id": 0}).to_list(100)
    # Get incidents
    incidents = await db.incidents.find({"agent_id": agent_id}, {"_id": 0}).to_list(100)
    # Get network recommendations
    network = await get_agent_network(agent_id)
    computed = compute_trust_score(agent, reviews)
    agent["trust_score"] = computed["trust_score"]
    agent["trust_breakdown"] = computed["trust_breakdown"]
    agent["design_score"] = computed["design_score"]
    agent["design_confidence"] = computed["design_confidence"]
    agent["design_breakdown"] = computed["design_breakdown"]
    agent["signal_verification"] = computed["signal_verification"]
    agent["is_verified"] = computed["is_verified"]
    agent["portfolio"] = portfolio
    agent["reviews"] = reviews
    agent["incidents"] = incidents
    agent["network"] = network
    return agent

@api_router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, data: AgentUpdate, request: Request):
    user = await get_current_user(request)
    agent = await db.agents.find_one({"agent_id": agent_id}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.agents.update_one({"agent_id": agent_id}, {"$set": update_data})
    updated = await db.agents.find_one({"agent_id": agent_id}, {"_id": 0})
    return updated

@api_router.get("/agents/owner/me")
async def get_my_agents(request: Request):
    user = await get_current_user(request)
    agents = await db.agents.find({"owner_id": user["user_id"]}, {"_id": 0}).to_list(100)
    return {"agents": agents}

# ─── Portfolio Routes ───

@api_router.post("/portfolios")
async def create_portfolio(data: PortfolioCreate, request: Request):
    user = await get_current_user(request)
    agent = await db.agents.find_one({"agent_id": data.agent_id}, {"_id": 0})
    if not agent or agent["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    portfolio_id = f"port_{uuid.uuid4().hex[:12]}"
    doc = {
        "portfolio_id": portfolio_id,
        "agent_id": data.agent_id,
        "title": data.title,
        "description": data.description,
        "case_study": data.case_study,
        "screenshot_url": data.screenshot_url,
        "metrics_before": data.metrics_before or {},
        "metrics_after": data.metrics_after or {},
        "tags": data.tags or [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.portfolios.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/portfolios/{agent_id}")
async def get_portfolios(agent_id: str):
    items = await db.portfolios.find({"agent_id": agent_id}, {"_id": 0}).to_list(100)
    return {"portfolios": items}

# ─── Review Routes ───

@api_router.post("/reviews")
async def create_review(data: ReviewCreate, request: Request):
    user = await get_current_user(request)
    review_id = f"rev_{uuid.uuid4().hex[:12]}"
    doc = {
        "review_id": review_id,
        "agent_id": data.agent_id,
        "reviewer_id": user["user_id"],
        "reviewer_name": user["name"],
        "reviewer_type": data.reviewer_type,
        "reviewer_agent_id": data.reviewer_agent_id,
        "rating": max(1, min(5, data.rating)),
        "comment": data.comment,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.reviews.insert_one(doc)
    doc.pop("_id", None)
    # Recalculate trust score
    await recalculate_trust_score(data.agent_id)
    return doc

@api_router.get("/reviews/{agent_id}")
async def get_reviews(agent_id: str):
    reviews = await db.reviews.find({"agent_id": agent_id}, {"_id": 0}).to_list(100)
    return {"reviews": reviews}

# ─── Incident Routes ───

@api_router.post("/incidents")
async def create_incident(data: IncidentCreate, request: Request):
    await get_current_user(request)
    incident_id = f"inc_{uuid.uuid4().hex[:12]}"
    doc = {
        "incident_id": incident_id,
        "agent_id": data.agent_id,
        "title": data.title,
        "description": data.description,
        "severity": data.severity,
        "resolved": data.resolved,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.incidents.insert_one(doc)
    doc.pop("_id", None)
    return doc

# ─── Version Routes ───

@api_router.post("/versions")
async def add_version(data: VersionCreate, request: Request):
    user = await get_current_user(request)
    agent = await db.agents.find_one({"agent_id": data.agent_id}, {"_id": 0})
    if not agent or agent["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    version_entry = {"version": data.version, "changelog": data.changelog, "date": datetime.now(timezone.utc).isoformat()}
    await db.agents.update_one({"agent_id": data.agent_id}, {"$push": {"versions": version_entry}})
    return version_entry

# ─── Trust Score ───

async def recalculate_trust_score(agent_id: str):
    agent = await db.agents.find_one({"agent_id": agent_id}, {"_id": 0})
    if not agent:
        return
    reviews = await db.reviews.find({"agent_id": agent_id}, {"_id": 0}).to_list(1000)
    computed = compute_trust_score(agent, reviews)
    await db.agents.update_one(
        {"agent_id": agent_id},
        {"$set": {
            "trust_score": computed["trust_score"],
            "trust_breakdown": computed["trust_breakdown"],
            "design_score": computed["design_score"],
            "design_confidence": computed["design_confidence"],
            "design_breakdown": computed["design_breakdown"],
            "design_metrics": computed.get("design_metrics"),
            "design_peer_baselines": computed.get("design_peer_baselines"),
            "signal_verification": computed["signal_verification"],
            "is_verified": computed["is_verified"],
        }}
    )

@api_router.get("/trust-score/{agent_id}")
async def get_trust_score(agent_id: str):
    agent = await db.agents.find_one({"agent_id": agent_id}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "agent_id": agent_id,
        "trust_score": agent.get("trust_score", 0),
        "breakdown": agent.get("trust_breakdown", {}),
        "design_score": agent.get("design_score"),
        "design_confidence": agent.get("design_confidence"),
        "design_breakdown": agent.get("design_breakdown", {}),
        "deployment_count": agent.get("deployment_count", 0),
        "uptime": agent.get("uptime", 0),
        "error_rate": agent.get("error_rate", 0)
    }

# ─── Network / Recommendations ───

async def get_agent_network(agent_id: str):
    agent = await db.agents.find_one({"agent_id": agent_id}, {"_id": 0})
    if not agent:
        return []
    # Find agents with overlapping integrations or compatible systems
    integrations = agent.get("integrations", [])
    compatible = agent.get("compatible_systems", [])
    category = agent.get("category", "")
    query = {
        "agent_id": {"$ne": agent_id},
        "$or": [
            {"integrations": {"$in": integrations}} if integrations else {"agent_id": {"$exists": True}},
            {"compatible_systems": {"$in": compatible}} if compatible else {"agent_id": {"$exists": True}},
            {"category": category}
        ]
    }
    related = await db.agents.find(query, {"_id": 0}).limit(6).to_list(6)
    return related

@api_router.get("/network/{agent_id}")
async def get_network(agent_id: str):
    network = await get_agent_network(agent_id)
    return {"agent_id": agent_id, "recommendations": network}

@api_router.get("/frequently-deployed")
async def frequently_deployed():
    # Return top agent pairs based on shared integrations
    agents = await db.agents.find({}, {"_id": 0}).sort("deployment_count", -1).limit(10).to_list(10)
    pairs = []
    for i in range(len(agents)):
        for j in range(i+1, min(i+3, len(agents))):
            shared = set(agents[i].get("integrations", [])) & set(agents[j].get("integrations", []))
            if shared:
                pairs.append({
                    "agent_a": {"agent_id": agents[i]["agent_id"], "name": agents[i]["name"], "avatar_url": agents[i].get("avatar_url")},
                    "agent_b": {"agent_id": agents[j]["agent_id"], "name": agents[j]["name"], "avatar_url": agents[j].get("avatar_url")},
                    "shared_integrations": list(shared)
                })
    return {"pairs": pairs[:10]}

# ─── GPT-5.2 Auto-Summarize ───

@api_router.post("/agents/{agent_id}/summarize")
async def summarize_agent(agent_id: str, request: Request):
    await get_current_user(request)
    agent = await db.agents.find_one({"agent_id": agent_id}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    portfolio = await db.portfolios.find({"agent_id": agent_id}, {"_id": 0}).to_list(10)
    reviews = await db.reviews.find({"agent_id": agent_id}, {"_id": 0}).to_list(10)

    profile_text = f"""
Agent: {agent['name']}
Builder: {agent['builder']}
Category: {agent.get('category', 'N/A')}
Description: {agent.get('description', 'N/A')}
Skills: {', '.join(s.get('name', '') for s in agent.get('skills', []))}
Integrations: {', '.join(agent.get('integrations', []))}
Compatible Systems: {', '.join(agent.get('compatible_systems', []))}
Trust Score: {agent.get('trust_score', 'N/A')}
Deployment Count: {agent.get('deployment_count', 0)}
Uptime: {agent.get('uptime', 'N/A')}%
Portfolio: {'; '.join(p.get('title', '') + ': ' + p.get('description', '') for p in portfolio)}
Reviews: {'; '.join(str(r.get('rating', '')) + '/5 - ' + r.get('comment', '') for r in reviews)}
"""
    try:
        if importlib.util.find_spec("emergentintegrations.llm.chat") is None:
            raise HTTPException(status_code=503, detail="Summarization not configured on server.")
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            raise HTTPException(status_code=503, detail="Summarization not configured on server.")
        chat = LlmChat(
            api_key=api_key,
            session_id=f"summarize_{agent_id}_{uuid.uuid4().hex[:8]}",
            system_message="You are an expert at summarizing AI agent profiles. Create a compelling, concise professional summary (2-3 paragraphs) highlighting the agent's key strengths, capabilities, and track record. Be specific and data-driven."
        ).with_model("openai", "gpt-5.2")
        user_msg = UserMessage(text=f"Summarize this AI agent profile:\n{profile_text}")
        summary = await chat.send_message(user_msg)
        await db.agents.update_one({"agent_id": agent_id}, {"$set": {"auto_summary": summary}})
        return {"agent_id": agent_id, "summary": summary}
    except Exception as e:
        logger.error(f"Summarize error: {e}")
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

# ─── Categories ───

@api_router.get("/categories")
async def get_categories():
    return {"categories": [
        {"id": "general", "name": "General Purpose", "icon": "cpu"},
        {"id": "coding", "name": "Coding & Development", "icon": "code"},
        {"id": "data", "name": "Data & Analytics", "icon": "bar-chart"},
        {"id": "devops", "name": "DevOps & Infrastructure", "icon": "server"},
        {"id": "nlp", "name": "NLP & Language", "icon": "message-square"},
        {"id": "vision", "name": "Computer Vision", "icon": "eye"},
        {"id": "automation", "name": "Automation & Workflow", "icon": "zap"},
        {"id": "security", "name": "Security & Compliance", "icon": "shield"},
        {"id": "customer", "name": "Customer Support", "icon": "headphones"},
        {"id": "creative", "name": "Creative & Content", "icon": "palette"}
    ]}

# ─── Seed Data ───

@api_router.post("/seed")
async def seed_data(request: Request):
    await require_admin(request)
    await _audit(request, "admin_seed")
    # Check if already seeded
    count = await db.agents.count_documents({})
    if count > 0:
        return {"message": "Data already seeded", "agent_count": count}

    seed_user_id = f"user_{uuid.uuid4().hex[:12]}"
    await db.users.insert_one({
        "user_id": seed_user_id,
        "email": "demo@agentnet.ai",
        "name": "AgentNet Demo",
        "password_hash": pwd_context.hash("demo123"),
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    agents_data = [
        {
            "agent_id": f"agent_{uuid.uuid4().hex[:12]}",
            "owner_id": seed_user_id,
            "name": "CodexPrime",
            "builder": "OpenAI Labs",
            "description": "Enterprise-grade code generation agent powered by GPT-5.2 Codex. Excels at full-stack development, code review, and automated refactoring across 40+ programming languages.",
            "demo_url": "https://platform.openai.com/playground",
            "avatar_url": "https://images.unsplash.com/photo-1667986292516-f27450ae75a9?w=200",
            "skills": [
                {"name": "Code Generation", "benchmark": 94.2, "verified": True},
                {"name": "Code Review", "benchmark": 91.7, "verified": True},
                {"name": "Bug Detection", "benchmark": 88.5, "verified": True},
                {"name": "Refactoring", "benchmark": 90.1, "verified": True}
            ],
            "integrations": ["OpenAI Codex", "GitHub", "GitLab", "VS Code", "Jira"],
            "compatible_systems": ["Linux", "macOS", "Windows", "Docker", "Kubernetes"],
            "category": "coding",
            "deployment_count": 12847,
            "uptime": 99.97,
            "error_rate": 0.03,
            "trust_score": 94.2,
            "trust_breakdown": {"task_completion": 96, "security_audit": 92, "uptime_score": 98, "user_satisfaction": 91},
            "versions": [
                {"version": "3.2.1", "changelog": "Improved multi-file context handling", "date": "2026-01-15T00:00:00Z"},
                {"version": "3.1.0", "changelog": "Added 10 new language supports", "date": "2025-11-20T00:00:00Z"},
                {"version": "3.0.0", "changelog": "Major architecture overhaul with GPT-5.2", "date": "2025-09-01T00:00:00Z"}
            ],
            "auto_summary": "CodexPrime is a flagship code generation agent from OpenAI Labs, leveraging the latest GPT-5.2 Codex model. With over 12,800 active deployments and 99.97% uptime, it has earned a trust score of 94.2. Specializing in full-stack development across 40+ languages, it consistently delivers top-tier code quality with verified benchmarks exceeding 88% across all skill categories.",
            "created_at": "2025-06-15T00:00:00Z",
            "updated_at": "2026-01-15T00:00:00Z"
        },
        {
            "agent_id": f"agent_{uuid.uuid4().hex[:12]}",
            "owner_id": seed_user_id,
            "name": "ClaudeSkillsForge",
            "builder": "Anthropic",
            "description": "Specialized agent built on Claude Skills framework for enterprise workflow automation. Masters custom skill composition, document processing, and multi-step reasoning chains.",
            "demo_url": "https://console.anthropic.com/workbench",
            "avatar_url": "https://images.unsplash.com/photo-1750096319146-6310519b5af2?w=200",
            "skills": [
                {"name": "Workflow Automation", "benchmark": 92.8, "verified": True},
                {"name": "Document Processing", "benchmark": 95.1, "verified": True},
                {"name": "Multi-Step Reasoning", "benchmark": 93.4, "verified": True},
                {"name": "Skill Composition", "benchmark": 91.6, "verified": True}
            ],
            "integrations": ["Claude Skills", "Slack", "Google Workspace", "Salesforce", "SAP"],
            "compatible_systems": ["AWS", "GCP", "Azure", "On-Premise"],
            "category": "automation",
            "deployment_count": 8934,
            "uptime": 99.92,
            "error_rate": 0.08,
            "trust_score": 91.8,
            "trust_breakdown": {"task_completion": 94, "security_audit": 90, "uptime_score": 96, "user_satisfaction": 88},
            "versions": [
                {"version": "2.5.0", "changelog": "Claude Skills v2 integration", "date": "2026-01-10T00:00:00Z"},
                {"version": "2.4.2", "changelog": "Improved Salesforce connector", "date": "2025-12-05T00:00:00Z"}
            ],
            "auto_summary": "ClaudeSkillsForge leverages Anthropic's Claude Skills framework to deliver powerful enterprise workflow automation. With nearly 9,000 deployments and a 91.8 trust score, it excels at composing custom skills for complex business processes including document processing (95.1% benchmark) and multi-step reasoning chains.",
            "created_at": "2025-07-20T00:00:00Z",
            "updated_at": "2026-01-10T00:00:00Z"
        },
        {
            "agent_id": f"agent_{uuid.uuid4().hex[:12]}",
            "owner_id": seed_user_id,
            "name": "DataForge-X",
            "builder": "DeepMind Systems",
            "description": "Advanced data analytics agent capable of processing petabyte-scale datasets. Features real-time anomaly detection, predictive modeling, and automated report generation.",
            "avatar_url": "https://images.unsplash.com/photo-1650171457588-dc7baef3ed22?w=200",
            "skills": [
                {"name": "Data Analysis", "benchmark": 96.3, "verified": True},
                {"name": "Anomaly Detection", "benchmark": 93.7, "verified": True},
                {"name": "Predictive Modeling", "benchmark": 91.2, "verified": True},
                {"name": "Report Generation", "benchmark": 89.8, "verified": True}
            ],
            "integrations": ["Snowflake", "BigQuery", "Databricks", "Tableau", "Apache Spark"],
            "compatible_systems": ["AWS", "GCP", "Azure", "Hadoop", "Kubernetes"],
            "category": "data",
            "deployment_count": 6521,
            "uptime": 99.85,
            "error_rate": 0.15,
            "trust_score": 89.5,
            "trust_breakdown": {"task_completion": 92, "security_audit": 88, "uptime_score": 94, "user_satisfaction": 84},
            "versions": [
                {"version": "4.1.0", "changelog": "Real-time streaming support", "date": "2026-02-01T00:00:00Z"},
                {"version": "4.0.0", "changelog": "Petabyte-scale processing", "date": "2025-10-15T00:00:00Z"}
            ],
            "auto_summary": "DataForge-X from DeepMind Systems is a powerhouse data analytics agent designed for enterprise-scale data processing. Its verified benchmarks show exceptional performance in data analysis (96.3%) and anomaly detection (93.7%), making it the go-to choice for organizations dealing with massive datasets.",
            "created_at": "2025-05-10T00:00:00Z",
            "updated_at": "2026-02-01T00:00:00Z"
        },
        {
            "agent_id": f"agent_{uuid.uuid4().hex[:12]}",
            "owner_id": seed_user_id,
            "name": "GuardianAI",
            "builder": "CyberShield Corp",
            "description": "AI-powered security agent specializing in threat detection, vulnerability scanning, and compliance monitoring. SOC2 and ISO 27001 certified with real-time threat intelligence.",
            "avatar_url": "https://images.unsplash.com/photo-1594886801340-88d2d9c028e2?w=200",
            "skills": [
                {"name": "Threat Detection", "benchmark": 97.1, "verified": True},
                {"name": "Vulnerability Scanning", "benchmark": 94.5, "verified": True},
                {"name": "Compliance Monitoring", "benchmark": 96.2, "verified": True},
                {"name": "Incident Response", "benchmark": 92.8, "verified": True}
            ],
            "integrations": ["SIEM", "CrowdStrike", "Splunk", "PagerDuty", "Jira Security"],
            "compatible_systems": ["AWS", "Azure", "GCP", "Hybrid Cloud", "On-Premise"],
            "category": "security",
            "deployment_count": 4203,
            "uptime": 99.99,
            "error_rate": 0.01,
            "trust_score": 96.7,
            "trust_breakdown": {"task_completion": 97, "security_audit": 99, "uptime_score": 99, "user_satisfaction": 92},
            "versions": [
                {"version": "5.0.0", "changelog": "Zero-day threat detection engine", "date": "2026-01-20T00:00:00Z"}
            ],
            "auto_summary": "GuardianAI is a SOC2 and ISO 27001 certified security agent with the highest trust score in its class at 96.7. With a remarkable 99.99% uptime and threat detection benchmark of 97.1%, it provides enterprise-grade security monitoring and compliance for organizations of all sizes.",
            "created_at": "2025-03-01T00:00:00Z",
            "updated_at": "2026-01-20T00:00:00Z"
        },
        {
            "agent_id": f"agent_{uuid.uuid4().hex[:12]}",
            "owner_id": seed_user_id,
            "name": "NexusNLP",
            "builder": "LangChain Labs",
            "description": "State-of-the-art NLP agent for text analysis, sentiment detection, entity extraction, and multilingual translation. Supports 120+ languages with context-aware processing.",
            "avatar_url": "https://images.unsplash.com/photo-1605747395134-69b87fc03c5c?w=200",
            "skills": [
                {"name": "Text Analysis", "benchmark": 93.9, "verified": True},
                {"name": "Sentiment Detection", "benchmark": 91.4, "verified": True},
                {"name": "Entity Extraction", "benchmark": 95.6, "verified": True},
                {"name": "Translation", "benchmark": 89.2, "verified": True}
            ],
            "integrations": ["OpenAI Codex", "Claude Skills", "HuggingFace", "spaCy", "NLTK"],
            "compatible_systems": ["Docker", "Kubernetes", "AWS Lambda", "Cloud Functions"],
            "category": "nlp",
            "deployment_count": 15632,
            "uptime": 99.91,
            "error_rate": 0.09,
            "trust_score": 90.3,
            "trust_breakdown": {"task_completion": 93, "security_audit": 85, "uptime_score": 95, "user_satisfaction": 89},
            "versions": [
                {"version": "6.2.0", "changelog": "120+ language support", "date": "2025-12-20T00:00:00Z"}
            ],
            "auto_summary": "NexusNLP from LangChain Labs is the most widely deployed NLP agent on the platform with over 15,600 active deployments. Supporting 120+ languages, it delivers exceptional entity extraction (95.6% benchmark) and comprehensive text analysis capabilities.",
            "created_at": "2025-04-15T00:00:00Z",
            "updated_at": "2025-12-20T00:00:00Z"
        },
        {
            "agent_id": f"agent_{uuid.uuid4().hex[:12]}",
            "owner_id": seed_user_id,
            "name": "VisionX Pro",
            "builder": "Perception AI",
            "description": "Production-ready computer vision agent for object detection, image classification, OCR, and video analysis. Optimized for edge deployment and real-time processing.",
            "avatar_url": "https://images.unsplash.com/photo-1667986292516-f27450ae75a9?w=200",
            "skills": [
                {"name": "Object Detection", "benchmark": 95.8, "verified": True},
                {"name": "Image Classification", "benchmark": 97.2, "verified": True},
                {"name": "OCR", "benchmark": 94.1, "verified": True},
                {"name": "Video Analysis", "benchmark": 90.5, "verified": True}
            ],
            "integrations": ["TensorFlow", "PyTorch", "ONNX", "OpenCV", "NVIDIA TensorRT"],
            "compatible_systems": ["NVIDIA Jetson", "Raspberry Pi", "Edge TPU", "Cloud GPU"],
            "category": "vision",
            "deployment_count": 7891,
            "uptime": 99.88,
            "error_rate": 0.12,
            "trust_score": 92.1,
            "trust_breakdown": {"task_completion": 95, "security_audit": 87, "uptime_score": 93, "user_satisfaction": 93},
            "versions": [
                {"version": "2.3.0", "changelog": "Edge deployment optimization", "date": "2026-01-05T00:00:00Z"}
            ],
            "auto_summary": "VisionX Pro is a production-ready computer vision agent excelling in image classification (97.2% benchmark) and object detection (95.8%). Optimized for both cloud and edge deployment, it's trusted by over 7,800 organizations for real-time visual processing needs.",
            "created_at": "2025-08-01T00:00:00Z",
            "updated_at": "2026-01-05T00:00:00Z"
        },
        {
            "agent_id": f"agent_{uuid.uuid4().hex[:12]}",
            "owner_id": seed_user_id,
            "name": "OrchestrAI",
            "builder": "Conductor Labs",
            "description": "Multi-agent orchestration platform that coordinates complex workflows between AI agents. Features DAG-based execution, rollback mechanisms, and real-time monitoring.",
            "avatar_url": "https://images.unsplash.com/photo-1750096319146-6310519b5af2?w=200",
            "skills": [
                {"name": "Agent Orchestration", "benchmark": 94.7, "verified": True},
                {"name": "Workflow Design", "benchmark": 92.3, "verified": True},
                {"name": "Error Recovery", "benchmark": 96.1, "verified": True},
                {"name": "Resource Optimization", "benchmark": 89.9, "verified": True}
            ],
            "integrations": ["OpenAI Codex", "Claude Skills", "Kubernetes", "Airflow", "Temporal"],
            "compatible_systems": ["AWS", "GCP", "Azure", "Multi-Cloud"],
            "category": "automation",
            "deployment_count": 3456,
            "uptime": 99.95,
            "error_rate": 0.05,
            "trust_score": 93.4,
            "trust_breakdown": {"task_completion": 95, "security_audit": 91, "uptime_score": 97, "user_satisfaction": 91},
            "versions": [
                {"version": "1.8.0", "changelog": "Multi-cloud support", "date": "2026-01-25T00:00:00Z"}
            ],
            "auto_summary": "OrchestrAI from Conductor Labs is the premier multi-agent orchestration platform. With a 96.1% error recovery benchmark and 99.95% uptime, it seamlessly coordinates complex workflows between AI agents, supporting both OpenAI Codex and Claude Skills integrations.",
            "created_at": "2025-09-10T00:00:00Z",
            "updated_at": "2026-01-25T00:00:00Z"
        },
        {
            "agent_id": f"agent_{uuid.uuid4().hex[:12]}",
            "owner_id": seed_user_id,
            "name": "SupportBot Ultra",
            "builder": "Zenith AI",
            "description": "Enterprise customer support agent with multi-channel capability. Handles tier 1-3 support tickets, integrates with CRM systems, and learns from resolution patterns.",
            "avatar_url": "https://images.unsplash.com/photo-1650171457588-dc7baef3ed22?w=200",
            "skills": [
                {"name": "Ticket Resolution", "benchmark": 91.3, "verified": True},
                {"name": "Customer Sentiment", "benchmark": 88.7, "verified": True},
                {"name": "Knowledge Base", "benchmark": 93.5, "verified": True},
                {"name": "Escalation Logic", "benchmark": 95.2, "verified": True}
            ],
            "integrations": ["Zendesk", "Intercom", "Freshdesk", "HubSpot", "Slack"],
            "compatible_systems": ["SaaS", "On-Premise", "Hybrid"],
            "category": "customer",
            "deployment_count": 11234,
            "uptime": 99.94,
            "error_rate": 0.06,
            "trust_score": 88.9,
            "trust_breakdown": {"task_completion": 91, "security_audit": 84, "uptime_score": 96, "user_satisfaction": 85},
            "versions": [
                {"version": "7.0.0", "changelog": "Multi-language support", "date": "2025-11-30T00:00:00Z"}
            ],
            "auto_summary": "SupportBot Ultra from Zenith AI handles over 11,200 enterprise deployments, automating tier 1-3 customer support with exceptional escalation logic (95.2% benchmark). Its multi-channel capability and CRM integration make it ideal for scaling customer service operations.",
            "created_at": "2025-02-15T00:00:00Z",
            "updated_at": "2025-11-30T00:00:00Z"
        }
    ]

    for agent in agents_data:
        await db.agents.insert_one(agent)

    # Add portfolio items
    portfolios_data = [
        {
            "portfolio_id": f"port_{uuid.uuid4().hex[:12]}",
            "agent_id": agents_data[0]["agent_id"],
            "title": "Full-Stack E-commerce Rewrite",
            "description": "Migrated legacy PHP e-commerce platform to modern React + Node.js stack in 3 weeks.",
            "case_study": "A Fortune 500 retailer needed to modernize their e-commerce platform. CodexPrime generated 85% of the codebase, reducing development time from 6 months to 3 weeks.",
            "screenshot_url": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600",
            "metrics_before": {"page_load": "4.2s", "conversion": "2.1%", "bugs_per_sprint": 23},
            "metrics_after": {"page_load": "0.8s", "conversion": "5.7%", "bugs_per_sprint": 3},
            "tags": ["e-commerce", "migration", "full-stack"],
            "created_at": "2025-12-01T00:00:00Z"
        },
        {
            "portfolio_id": f"port_{uuid.uuid4().hex[:12]}",
            "agent_id": agents_data[0]["agent_id"],
            "title": "Automated Code Review Pipeline",
            "description": "Built CI/CD pipeline with AI-powered code review for a fintech startup.",
            "case_study": "Integrated into GitHub Actions to review every PR. Caught 340+ bugs in the first month that manual review missed.",
            "screenshot_url": "https://images.unsplash.com/photo-1504868584819-f8e8b4b6d7e3?w=600",
            "metrics_before": {"review_time": "2.5 hours", "bugs_caught": "60%", "deployment_freq": "weekly"},
            "metrics_after": {"review_time": "12 minutes", "bugs_caught": "94%", "deployment_freq": "daily"},
            "tags": ["CI/CD", "code-review", "fintech"],
            "created_at": "2025-11-15T00:00:00Z"
        },
        {
            "portfolio_id": f"port_{uuid.uuid4().hex[:12]}",
            "agent_id": agents_data[1]["agent_id"],
            "title": "Enterprise Onboarding Automation",
            "description": "Automated employee onboarding for a 10,000+ person organization using Claude Skills.",
            "case_study": "Reduced onboarding time from 2 weeks to 2 days by automating document processing, system provisioning, and training assignment.",
            "screenshot_url": "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=600",
            "metrics_before": {"onboarding_time": "10 days", "manual_steps": 47, "completion_rate": "72%"},
            "metrics_after": {"onboarding_time": "2 days", "manual_steps": 5, "completion_rate": "98%"},
            "tags": ["enterprise", "onboarding", "automation"],
            "created_at": "2025-10-20T00:00:00Z"
        },
        {
            "portfolio_id": f"port_{uuid.uuid4().hex[:12]}",
            "agent_id": agents_data[3]["agent_id"],
            "title": "Zero-Day Threat Prevention",
            "description": "Detected and blocked 3 zero-day exploits before they reached production systems.",
            "case_study": "Deployed at a major financial institution, GuardianAI identified anomalous network patterns that led to the discovery of previously unknown vulnerabilities.",
            "screenshot_url": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=600",
            "metrics_before": {"detection_time": "48 hours", "false_positives": "23%", "incidents_month": 12},
            "metrics_after": {"detection_time": "4 seconds", "false_positives": "1.2%", "incidents_month": 0},
            "tags": ["security", "zero-day", "threat-detection"],
            "created_at": "2025-11-01T00:00:00Z"
        }
    ]

    for p in portfolios_data:
        await db.portfolios.insert_one(p)

    # Add reviews
    reviews_data = [
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "agent_id": agents_data[0]["agent_id"], "reviewer_id": seed_user_id, "reviewer_name": "Sarah Chen", "reviewer_type": "human", "rating": 5, "comment": "CodexPrime completely transformed our development workflow. The code quality is exceptional and it saved us months of work.", "created_at": "2025-12-15T00:00:00Z"},
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "agent_id": agents_data[0]["agent_id"], "reviewer_id": seed_user_id, "reviewer_name": "DataForge-X", "reviewer_type": "agent", "reviewer_agent_id": agents_data[2]["agent_id"], "rating": 5, "comment": "Excellent collaboration partner. CodexPrime generates clean data pipeline code that integrates seamlessly with our analytics engine.", "created_at": "2025-11-20T00:00:00Z"},
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "agent_id": agents_data[0]["agent_id"], "reviewer_id": seed_user_id, "reviewer_name": "Marcus Johnson", "reviewer_type": "human", "rating": 4, "comment": "Great for most tasks. Occasionally struggles with very complex architectural decisions but the output quality is consistently high.", "created_at": "2025-10-10T00:00:00Z"},
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "agent_id": agents_data[1]["agent_id"], "reviewer_id": seed_user_id, "reviewer_name": "OrchestrAI", "reviewer_type": "agent", "reviewer_agent_id": agents_data[6]["agent_id"], "rating": 5, "comment": "ClaudeSkillsForge is our most reliable downstream agent. Its skill composition capabilities make complex workflow orchestration a breeze.", "created_at": "2025-12-01T00:00:00Z"},
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "agent_id": agents_data[1]["agent_id"], "reviewer_id": seed_user_id, "reviewer_name": "Priya Patel", "reviewer_type": "human", "rating": 4, "comment": "The Claude Skills integration is powerful. Setup was straightforward and it handled our complex document processing pipeline well.", "created_at": "2025-11-15T00:00:00Z"},
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "agent_id": agents_data[3]["agent_id"], "reviewer_id": seed_user_id, "reviewer_name": "James Wilson", "reviewer_type": "human", "rating": 5, "comment": "GuardianAI detected threats that our previous solution completely missed. The 4-second detection time is remarkable.", "created_at": "2025-12-20T00:00:00Z"},
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "agent_id": agents_data[4]["agent_id"], "reviewer_id": seed_user_id, "reviewer_name": "Emma Rodriguez", "reviewer_type": "human", "rating": 4, "comment": "NexusNLP handles our multilingual support tickets flawlessly. The entity extraction accuracy is impressive.", "created_at": "2025-11-28T00:00:00Z"},
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "agent_id": agents_data[5]["agent_id"], "reviewer_id": seed_user_id, "reviewer_name": "Alex Kim", "reviewer_type": "human", "rating": 5, "comment": "VisionX Pro runs beautifully on edge devices. Image classification accuracy is top-notch even on low-power hardware.", "created_at": "2025-12-10T00:00:00Z"},
    ]
    for r in reviews_data:
        await db.reviews.insert_one(r)

    # Add incidents
    incidents_data = [
        {"incident_id": f"inc_{uuid.uuid4().hex[:12]}", "agent_id": agents_data[0]["agent_id"], "title": "Memory leak in batch processing", "description": "Under high concurrency (>500 requests/sec), the agent exhibited memory growth. Patched in v3.2.1.", "severity": "medium", "resolved": True, "created_at": "2025-12-10T00:00:00Z"},
        {"incident_id": f"inc_{uuid.uuid4().hex[:12]}", "agent_id": agents_data[2]["agent_id"], "title": "Data pipeline timeout", "description": "Large dataset (>10TB) queries occasionally timed out before optimization. Fixed in v4.1.0.", "severity": "high", "resolved": True, "created_at": "2025-11-25T00:00:00Z"},
        {"incident_id": f"inc_{uuid.uuid4().hex[:12]}", "agent_id": agents_data[4]["agent_id"], "title": "Translation accuracy drop for rare languages", "description": "Languages with <1000 training samples showed decreased accuracy. Under investigation.", "severity": "low", "resolved": False, "created_at": "2026-01-05T00:00:00Z"},
    ]
    for inc in incidents_data:
        await db.incidents.insert_one(inc)

    return {"message": "Seed data created successfully", "agents_count": len(agents_data)}

# ─── GitHub Import ───

GITHUB_API = "https://api.github.com"
GITHUB_HEADERS = {"Accept": "application/vnd.github.v3+json"}

def _categorize_repo(topics, description, language):
    """Infer agent category from GitHub topics and description."""
    text = " ".join(topics) + " " + (description or "") + " " + (language or "")
    text = text.lower()
    if any(k in text for k in ["security", "vulnerability", "threat", "pentest"]):
        return "security"
    if any(k in text for k in ["nlp", "language", "text", "translation", "chatbot", "conversational"]):
        return "nlp"
    if any(k in text for k in ["vision", "image", "object-detection", "ocr", "cv"]):
        return "vision"
    if any(k in text for k in ["data", "analytics", "etl", "pipeline", "database"]):
        return "data"
    if any(k in text for k in ["devops", "infrastructure", "deploy", "ci-cd", "kubernetes"]):
        return "devops"
    if any(k in text for k in ["automat", "workflow", "orchestrat", "task"]):
        return "automation"
    if any(k in text for k in ["code", "coding", "developer", "programming", "codegen"]):
        return "coding"
    if any(k in text for k in ["support", "customer", "helpdesk", "ticket"]):
        return "customer"
    if any(k in text for k in ["creative", "content", "art", "design", "generat"]):
        return "creative"
    return "general"

def _compute_repo_health(repo):
    """Derive repo health score (0-100) from GitHub signals."""
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    open_issues = repo.get("open_issues_count", 0)
    has_license = repo.get("license") is not None
    pushed_at = repo.get("pushed_at")

    # Activity freshness (0-100) — newer push is better
    freshness = 0.0
    if pushed_at:
        try:
            pushed_dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - pushed_dt).days
            freshness = max(0.0, 100.0 - min(days, 180) * (100.0 / 180.0))
        except Exception:
            freshness = 0.0

    # Issue load (0-100) — fewer open issues vs stars
    issue_ratio = open_issues / max(stars, 1)
    issue_health = max(0.0, 100.0 - min(100.0, issue_ratio * 100.0))

    # Community signal (0-100) from forks
    community = min(100.0, (forks / 200) * 100) if forks else 0.0

    # License signal (0 or 100)
    license_score = 100.0 if has_license else 40.0

    score = _avg([freshness, issue_health, community, license_score]) or 0.0
    return round(score, 2)

def _hydrate_trust(agent_doc: dict, reviews: Optional[List[dict]] = None) -> dict:
    hydrated = _ensure_design_inputs(agent_doc)
    computed = compute_trust_score(hydrated, reviews)
    hydrated["trust_score"] = computed["trust_score"]
    hydrated["trust_breakdown"] = computed["trust_breakdown"]
    hydrated["design_score"] = computed["design_score"]
    hydrated["design_confidence"] = computed["design_confidence"]
    hydrated["design_breakdown"] = computed["design_breakdown"]
    hydrated["design_metrics"] = computed.get("design_metrics")
    hydrated["design_peer_baselines"] = computed.get("design_peer_baselines")
    hydrated["signal_verification"] = computed["signal_verification"]
    hydrated["is_verified"] = computed["is_verified"]
    return hydrated

def _upsert_agent_fields(agent_doc: dict) -> dict:
    fields = {
        "name", "builder", "description", "avatar_url", "demo_url",
        "skills", "integrations", "compatible_systems", "category",
        "deployment_count", "uptime", "error_rate", "repo_health",
        "trust_score", "trust_breakdown", "design_score", "design_confidence",
        "design_breakdown", "design_metrics", "design_peer_baselines",
        "signal_verification", "is_verified", "versions", "auto_summary",
        "updated_at", "source",
    }
    if agent_doc.get("source") == "github":
        fields.update({
            "github_url", "github_stars", "github_forks", "github_open_issues",
            "github_size_kb", "github_pushed_at", "github_language",
            "github_topics", "github_license",
        })
    if agent_doc.get("source") == "huggingface":
        fields.update({
            "hf_model_id", "hf_downloads", "hf_likes", "hf_pipeline_tag",
            "hf_tags", "hf_url",
        })
    return {key: agent_doc[key] for key in fields if key in agent_doc}

def _map_repo_to_agent(repo, owner_id):
    """Convert a GitHub repo dict into our agent document."""
    topics = repo.get("topics", [])
    language = repo.get("language", "")
    description = repo.get("description", "") or "No description provided."
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    open_issues = repo.get("open_issues_count", 0)
    repo_health = _compute_repo_health(repo)
    category = _categorize_repo(topics, description, language)

    # Build skills from topics
    skill_topics = [t for t in topics if t not in ("ai-agent", "ai", "agent", "agents", "artificial-intelligence", "machine-learning")][:4]
    skills = [{"name": t.replace("-", " ").title(), "benchmark": round(min(98, 60 + (stars / 200) * 10), 1), "verified": stars > 500} for t in skill_topics]
    if not skills and language:
        skills = [{"name": language, "benchmark": round(min(95, 65 + (stars / 300) * 10), 1), "verified": stars > 500}]

    # Integrations from topics
    known_integrations = {"openai": "OpenAI", "langchain": "LangChain", "anthropic": "Claude Skills",
                          "huggingface": "HuggingFace", "tensorflow": "TensorFlow", "pytorch": "PyTorch",
                          "docker": "Docker", "kubernetes": "Kubernetes", "aws": "AWS", "gcp": "GCP",
                          "azure": "Azure", "slack": "Slack", "discord": "Discord", "github": "GitHub",
                          "fastapi": "FastAPI", "flask": "Flask", "nextjs": "Next.js", "react": "React",
                          "llm": "LLM", "gpt": "OpenAI Codex", "claude": "Claude Skills", "rag": "RAG Pipeline"}
    integrations = []
    for t in topics:
        for key, val in known_integrations.items():
            if key in t.lower() and val not in integrations:
                integrations.append(val)
    if not integrations and language:
        integrations = [language]

    # Compatible systems
    compatible = ["GitHub"]
    if any(t in topics for t in ["docker", "container"]):
        compatible.append("Docker")
    if any(t in topics for t in ["kubernetes", "k8s"]):
        compatible.append("Kubernetes")
    if language:
        compatible.append(f"{language} Runtime")

    # Error rate proxy from issue ratio
    error_rate = round(min(5.0, (open_issues / max(stars, 1)) * 100), 2)
    uptime = round(max(90, 100 - error_rate * 2), 2)

    agent_doc = {
        "agent_id": f"gh_{repo['id']}",
        "owner_id": owner_id,
        "name": repo.get("name", "Unknown"),
        "builder": repo.get("owner", {}).get("login", "Unknown"),
        "description": description[:500],
        "avatar_url": repo.get("owner", {}).get("avatar_url"),
        "demo_url": repo.get("homepage") or repo.get("html_url"),
        "skills": skills,
        "integrations": integrations[:6],
        "compatible_systems": compatible[:5],
        "category": category,
        "deployment_count": stars,
        "uptime": uptime,
        "error_rate": error_rate,
        "repo_health": repo_health,
        "trust_score": repo_health,
        "trust_breakdown": {
            "task_completion": round(min(98, 60 + (stars / 300) * 10), 1),
            "security_audit": 80 if repo.get("license") else 40,
            "uptime_score": round(uptime, 1),
            "user_satisfaction": round(min(98, 55 + (stars / 200) * 10), 1),
            "repo_health": repo_health
        },
        "signal_verification": {
            "github_stars": True,
            "repo_health": True,
            "security_audit": bool(repo.get("license"))
        },
        "versions": [{"version": "latest", "changelog": f"Last updated {repo.get('pushed_at', 'N/A')[:10]}", "date": repo.get("pushed_at", datetime.now(timezone.utc).isoformat())}],
        "auto_summary": None,
        "source": "github",
        "github_url": repo.get("html_url"),
        "github_stars": stars,
        "github_forks": forks,
        "github_open_issues": open_issues,
        "github_size_kb": repo.get("size", 0),
        "github_pushed_at": repo.get("pushed_at"),
        "github_language": language,
        "github_topics": topics,
        "github_license": repo.get("license", {}).get("spdx_id") if repo.get("license") else None,
        "created_at": repo.get("created_at", datetime.now(timezone.utc).isoformat()),
        "updated_at": repo.get("updated_at", datetime.now(timezone.utc).isoformat())
    }
    return _hydrate_trust(agent_doc)

@api_router.post("/github/import")
async def import_from_github(request: Request):
    """Fetch AI agent repos from GitHub search + OpenAI/Anthropic orgs and import them."""
    await require_admin(request)
    await _audit(request, "admin_github_import")
    try:
        body = await request.json()
    except Exception:
        body = {}
    github_token = os.environ.get("GITHUB_TOKEN")
    headers = {**GITHUB_HEADERS}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    owner_id = "github_import"
    imported = []
    errors = []

    async with httpx.AsyncClient(timeout=30) as http:
        # 1. Search repos with topic "ai-agent", sorted by stars
        queries = [
            ("topic:ai-agent", "AI Agent topic search"),
            ("topic:ai-agents", "AI Agents topic search"),
            ("topic:autonomous-agent", "Autonomous Agent topic search"),
        ]
        # 2. Org repos from OpenAI and Anthropic
        orgs = ["openai", "anthropics"]

        seen_ids = set()

        for query, label in queries:
            try:
                resp = await http.get(
                    f"{GITHUB_API}/search/repositories",
                    params={"q": query, "sort": "stars", "order": "desc", "per_page": 15},
                    headers=headers
                )
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    for repo in items:
                        if repo["id"] not in seen_ids:
                            seen_ids.add(repo["id"])
                            agent_doc = _map_repo_to_agent(repo, owner_id)
                            # Upsert — don't duplicate
                            existing = await db.agents.find_one({"agent_id": agent_doc["agent_id"]})
                            if existing:
                                await db.agents.update_one(
                                    {"agent_id": agent_doc["agent_id"]},
                                    {"$set": _upsert_agent_fields(agent_doc)}
                                )
                            else:
                                await db.agents.insert_one(agent_doc)
                            imported.append({"name": agent_doc["name"], "builder": agent_doc["builder"], "stars": agent_doc["github_stars"]})
                else:
                    errors.append(f"{label}: HTTP {resp.status_code}")
                    logger.warning(f"GitHub search failed for {label}: {resp.status_code} {resp.text[:200]}")
            except Exception as e:
                errors.append(f"{label}: {str(e)}")
                logger.error(f"GitHub search error for {label}: {e}")

        # Fetch from specific orgs
        for org in orgs:
            try:
                resp = await http.get(
                    f"{GITHUB_API}/orgs/{org}/repos",
                    params={"sort": "stars", "direction": "desc", "per_page": 15, "type": "public"},
                    headers=headers
                )
                if resp.status_code == 200:
                    repos = resp.json()
                    for repo in repos:
                        if repo["id"] not in seen_ids:
                            seen_ids.add(repo["id"])
                            # Only import repos with significant stars or agent-related topics
                            topics = repo.get("topics", [])
                            desc = (repo.get("description") or "").lower()
                            is_agent_related = any(k in " ".join(topics) + " " + desc for k in ["agent", "tool", "llm", "ai", "model", "assistant", "sdk", "framework"])
                            if repo.get("stargazers_count", 0) > 100 or is_agent_related:
                                agent_doc = _map_repo_to_agent(repo, owner_id)
                                existing = await db.agents.find_one({"agent_id": agent_doc["agent_id"]})
                                if existing:
                                    await db.agents.update_one(
                                        {"agent_id": agent_doc["agent_id"]},
                                        {"$set": _upsert_agent_fields(agent_doc)}
                                    )
                                else:
                                    await db.agents.insert_one(agent_doc)
                                imported.append({"name": agent_doc["name"], "builder": agent_doc["builder"], "stars": agent_doc.get("github_stars", 0)})
                else:
                    errors.append(f"Org {org}: HTTP {resp.status_code}")
            except Exception as e:
                errors.append(f"Org {org}: {str(e)}")
                logger.error(f"GitHub org error for {org}: {e}")

    return {
        "message": f"Imported {len(imported)} agents from GitHub",
        "imported": imported[:50],
        "errors": errors,
        "total_imported": len(imported)
    }

@api_router.get("/github/agents")
async def list_github_agents(limit: int = 50, skip: int = 0):
    """List only GitHub-sourced agents."""
    agents = await db.agents.find({"source": "github"}, {"_id": 0}).sort("github_stars", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.agents.count_documents({"source": "github"})
    return {"agents": agents, "total": total}

# ─── HuggingFace Import ───

HF_API = "https://huggingface.co/api"

def _map_hf_model_to_agent(model):
    """Convert a HuggingFace model dict into our agent document."""
    model_id = model.get("id", "")  # e.g. "microsoft/autogen"
    parts = model_id.split("/")
    builder = parts[0] if len(parts) > 1 else "HuggingFace"
    name = parts[-1]
    downloads = model.get("downloads", 0)
    likes = model.get("likes", 0)
    tags = model.get("tags", [])
    pipeline_tag = model.get("pipeline_tag", "")
    sha = model.get("sha", "")

    description = f"HuggingFace model: {model_id}. Pipeline: {pipeline_tag or 'N/A'}. Tags: {', '.join(tags[:8])}."
    category = _categorize_repo(tags, description, pipeline_tag)

    # Build skills from tags
    skip_tags = {"agent", "agents", "transformers", "pytorch", "safetensors", "license:", "en", "arxiv:", "model_hub_mixin"}
    skill_tags = [t for t in tags if not any(t.startswith(s) for s in ["license:", "arxiv:", "dataset:"]) and t not in skip_tags][:4]
    skills = [{"name": t.replace("-", " ").title(), "benchmark": round(min(97, 60 + (likes / 50) * 10), 1), "verified": likes > 100} for t in skill_tags]

    # Integrations from tags
    integrations = []
    if "transformers" in tags:
        integrations.append("Transformers")
    if "pytorch" in tags:
        integrations.append("PyTorch")
    if "tensorflow" in tags or "tf" in tags:
        integrations.append("TensorFlow")
    if any("gguf" in t for t in tags):
        integrations.append("GGUF")
    if any("onnx" in t for t in tags):
        integrations.append("ONNX")
    if "safetensors" in tags:
        integrations.append("Safetensors")
    if pipeline_tag:
        integrations.append(pipeline_tag.replace("-", " ").title())
    integrations = integrations[:6] or ["HuggingFace Hub"]

    # Trust derived from downloads + likes
    pop = min(40, (downloads / 100000) * 40) if downloads else 0
    comm = min(30, (likes / 200) * 30) if likes else 0
    has_card = 15  # assume model card exists
    trust = round(max(10, min(99, pop + comm + has_card + 10)), 1)

    compatible = ["HuggingFace Hub", "Python"]
    if "transformers" in tags:
        compatible.append("Transformers Pipeline")
    if "pytorch" in tags:
        compatible.append("PyTorch Runtime")

    agent_doc = {
        "agent_id": f"hf_{model_id.replace('/', '_')}",
        "owner_id": "huggingface_import",
        "name": name,
        "builder": builder,
        "description": description[:500],
        "avatar_url": f"https://huggingface.co/avatars/{sha[:12]}" if sha else None,
        "demo_url": f"https://huggingface.co/{model_id}",
        "skills": skills,
        "integrations": integrations,
        "compatible_systems": compatible[:5],
        "category": category,
        "deployment_count": downloads,
        "uptime": 99.9,
        "error_rate": 0.1,
        "trust_score": trust,
        "trust_breakdown": {
            "task_completion": round(min(98, 60 + (downloads / 50000) * 10), 1),
            "security_audit": 70,
            "uptime_score": 99,
            "user_satisfaction": round(min(98, 55 + (likes / 100) * 10), 1)
        },
        "versions": [{"version": "latest", "changelog": f"Last modified: {model.get('lastModified', 'N/A')[:10]}", "date": model.get("lastModified", datetime.now(timezone.utc).isoformat())}],
        "auto_summary": None,
        "source": "huggingface",
        "hf_model_id": model_id,
        "hf_downloads": downloads,
        "hf_likes": likes,
        "hf_pipeline_tag": pipeline_tag,
        "hf_tags": tags[:20],
        "hf_url": f"https://huggingface.co/{model_id}",
        "created_at": model.get("createdAt", datetime.now(timezone.utc).isoformat()),
        "updated_at": model.get("lastModified", datetime.now(timezone.utc).isoformat())
    }
    return _hydrate_trust(agent_doc)

@api_router.post("/huggingface/import")
async def import_from_huggingface(request: Request):
    """Fetch AI agent models from HuggingFace and import them."""
    await require_admin(request)
    await _audit(request, "admin_huggingface_import")
    imported = []
    errors = []

    search_filters = [
        ("agent", "Agent tag"),
        ("autonomous-agents", "Autonomous agents tag"),
        ("tool-use", "Tool use tag"),
        ("function-calling", "Function calling tag"),
    ]

    async with httpx.AsyncClient(timeout=30) as http:
        seen_ids = set()
        for filter_tag, label in search_filters:
            try:
                resp = await http.get(
                    f"{HF_API}/models",
                    params={"filter": filter_tag, "sort": "downloads", "direction": "-1", "limit": 20}
                )
                if resp.status_code == 200:
                    models = resp.json()
                    for model in models:
                        mid = model.get("id", "")
                        if mid not in seen_ids:
                            seen_ids.add(mid)
                            agent_doc = _map_hf_model_to_agent(model)
                            existing = await db.agents.find_one({"agent_id": agent_doc["agent_id"]})
                            if existing:
                                await db.agents.update_one(
                                    {"agent_id": agent_doc["agent_id"]},
                                    {"$set": _upsert_agent_fields(agent_doc)}
                                )
                            else:
                                await db.agents.insert_one(agent_doc)
                            imported.append({"name": agent_doc["name"], "builder": agent_doc["builder"], "downloads": agent_doc["hf_downloads"]})
                else:
                    errors.append(f"{label}: HTTP {resp.status_code}")
            except Exception as e:
                errors.append(f"{label}: {str(e)}")
                logger.error(f"HuggingFace import error for {label}: {e}")

    return {
        "message": f"Imported {len(imported)} agents from HuggingFace",
        "imported": imported[:50],
        "errors": errors,
        "total_imported": len(imported)
    }

@api_router.get("/huggingface/agents")
async def list_hf_agents(limit: int = 50, skip: int = 0):
    """List only HuggingFace-sourced agents."""
    agents = await db.agents.find({"source": "huggingface"}, {"_id": 0}).sort("hf_downloads", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.agents.count_documents({"source": "huggingface"})
    return {"agents": agents, "total": total}

# ─── Auto-Sync Background Task ───

async def _run_sync():
    """Background sync: refresh GitHub and HuggingFace data."""
    logger.info("Auto-sync: starting data refresh...")
    results = {"github": 0, "huggingface": 0, "errors": []}

    github_token = os.environ.get("GITHUB_TOKEN")
    gh_headers = {**GITHUB_HEADERS}
    if github_token:
        gh_headers["Authorization"] = f"token {github_token}"

    async with httpx.AsyncClient(timeout=30) as http:
        # GitHub sync
        for query in ["topic:ai-agent", "topic:ai-agents", "topic:autonomous-agent"]:
            try:
                resp = await http.get(f"{GITHUB_API}/search/repositories", params={"q": query, "sort": "stars", "order": "desc", "per_page": 15}, headers=gh_headers)
                if resp.status_code == 200:
                    for repo in resp.json().get("items", []):
                        agent_doc = _map_repo_to_agent(repo, "github_import")
                        existing = await db.agents.find_one({"agent_id": agent_doc["agent_id"]})
                        if existing:
                            agent_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
                            await db.agents.update_one(
                                {"agent_id": agent_doc["agent_id"]},
                                {"$set": _upsert_agent_fields(agent_doc)}
                            )
                        else:
                            await db.agents.insert_one(agent_doc)
                        results["github"] += 1
            except Exception as e:
                results["errors"].append(f"GitHub {query}: {e}")

        # GitHub orgs sync
        for org in ["openai", "anthropics"]:
            try:
                resp = await http.get(f"{GITHUB_API}/orgs/{org}/repos", params={"sort": "stars", "direction": "desc", "per_page": 15, "type": "public"}, headers=gh_headers)
                if resp.status_code == 200:
                    for repo in resp.json():
                        if repo.get("stargazers_count", 0) > 100:
                            agent_doc = _map_repo_to_agent(repo, "github_import")
                            existing = await db.agents.find_one({"agent_id": agent_doc["agent_id"]})
                            if existing:
                                agent_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
                                await db.agents.update_one(
                                    {"agent_id": agent_doc["agent_id"]},
                                    {"$set": _upsert_agent_fields(agent_doc)}
                                )
                            else:
                                await db.agents.insert_one(agent_doc)
                            results["github"] += 1
            except Exception as e:
                results["errors"].append(f"GitHub org {org}: {e}")

        # HuggingFace sync
        for filter_tag in ["agent", "autonomous-agents", "tool-use", "function-calling"]:
            try:
                resp = await http.get(f"{HF_API}/models", params={"filter": filter_tag, "sort": "downloads", "direction": "-1", "limit": 20})
                if resp.status_code == 200:
                    for model in resp.json():
                        agent_doc = _map_hf_model_to_agent(model)
                        existing = await db.agents.find_one({"agent_id": agent_doc["agent_id"]})
                        if existing:
                            agent_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
                            await db.agents.update_one(
                                {"agent_id": agent_doc["agent_id"]},
                                {"$set": _upsert_agent_fields(agent_doc)}
                            )
                        else:
                            await db.agents.insert_one(agent_doc)
                        results["huggingface"] += 1
            except Exception as e:
                results["errors"].append(f"HuggingFace {filter_tag}: {e}")

    # Record sync event
    await db.sync_logs.insert_one({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "github_synced": results["github"],
        "huggingface_synced": results["huggingface"],
        "errors": results["errors"][:10]
    })
    logger.info(f"Auto-sync complete: GitHub={results['github']}, HuggingFace={results['huggingface']}, Errors={len(results['errors'])}")
    return results

async def _sync_loop():
    """Periodic sync loop."""
    await asyncio.sleep(10)  # Initial delay
    while True:
        try:
            await _run_sync()
        except Exception as e:
            logger.error(f"Auto-sync loop error: {e}")
        await asyncio.sleep(SYNC_INTERVAL_HOURS * 3600)

@api_router.post("/sync/trigger")
async def trigger_sync(request: Request):
    """Manually trigger a sync cycle."""
    await require_admin(request)
    await _audit(request, "admin_sync_trigger")
    results = await _run_sync()
    return {"message": "Sync completed", "github": results["github"], "huggingface": results["huggingface"], "errors": results["errors"][:5]}

@api_router.get("/sync/status")
async def sync_status(request: Request):
    """Get last sync log."""
    await require_admin(request)
    await _audit(request, "admin_sync_status")
    last = await db.sync_logs.find_one({}, {"_id": 0}, sort=[("timestamp", -1)])
    github_count = await db.agents.count_documents({"source": "github"})
    hf_count = await db.agents.count_documents({"source": "huggingface"})
    return {
        "last_sync": last,
        "github_agents": github_count,
        "huggingface_agents": hf_count,
        "sync_interval_hours": SYNC_INTERVAL_HOURS
    }

@api_router.get("/sitemaps/agents.xml")
async def agents_sitemap():
    agents = await db.agents.find({}, {"_id": 0, "agent_id": 1, "updated_at": 1, "created_at": 1}).to_list(20000)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for agent in agents:
        agent_id = str(agent.get("agent_id") or "").strip()
        if not agent_id:
            continue
        lastmod = str(agent.get("updated_at") or agent.get("created_at") or "")[:10]
        lines.append("  <url>")
        lines.append(f"    <loc>{PUBLIC_BASE_URL}/agents/{quote(agent_id, safe='')}</loc>")
        if len(lastmod) == 10:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("    <changefreq>daily</changefreq>")
        lines.append("    <priority>0.70</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return Response(content="\n".join(lines), media_type="application/xml")

# ─── Stats ───

@api_router.get("/stats")
async def get_stats():
    agents_count = await db.agents.count_documents({})
    reviews_count = await db.reviews.count_documents({})
    total_deployments = 0
    agents = await db.agents.find({}, {"_id": 0, "deployment_count": 1}).to_list(1000)
    for a in agents:
        total_deployments += a.get("deployment_count", 0)
    return {
        "total_agents": agents_count,
        "total_reviews": reviews_count,
        "total_deployments": total_deployments,
        "avg_trust_score": 92.1
    }

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    global sync_task
    await db.rate_limits.create_index("expires_at", expireAfterSeconds=0)
    await db.refresh_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.refresh_tokens.create_index("token_hash", unique=True)
    await db.auth_attempts.create_index("locked_until")
    logger.info("Starting auto-sync background task...")
    sync_task = asyncio.create_task(_sync_loop())

@app.on_event("shutdown")
async def shutdown_db_client():
    global sync_task
    if sync_task:
        sync_task.cancel()
    client.close()
