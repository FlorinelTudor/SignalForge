from fastapi import FastAPI, APIRouter, HTTPException, Response, Request, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import httpx
import asyncio
import importlib.util
from contextlib import asynccontextmanager
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
import jwt

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
JWT_SECRET = os.environ.get("JWT_SECRET", "agentnet-jwt-secret-key-2026")
JWT_ALGORITHM = "HS256"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─── Pydantic Models ───

class UserRegister(BaseModel):
    email: str
    password: str
    name: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: Optional[str] = None

class AgentCreate(BaseModel):
    name: str
    builder: str
    description: str
    avatar_url: Optional[str] = None
    skills: Optional[List[dict]] = []
    integrations: Optional[List[str]] = []
    compatible_systems: Optional[List[str]] = []
    category: Optional[str] = "general"

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    skills: Optional[List[dict]] = None
    integrations: Optional[List[str]] = None
    compatible_systems: Optional[List[str]] = None
    category: Optional[str] = None

class PortfolioCreate(BaseModel):
    agent_id: str
    title: str
    description: str
    case_study: Optional[str] = None
    screenshot_url: Optional[str] = None
    metrics_before: Optional[dict] = None
    metrics_after: Optional[dict] = None
    tags: Optional[List[str]] = []

class ReviewCreate(BaseModel):
    agent_id: str
    rating: int
    comment: str
    reviewer_type: Optional[str] = "human"
    reviewer_agent_id: Optional[str] = None

class IncidentCreate(BaseModel):
    agent_id: str
    title: str
    description: str
    severity: str
    resolved: Optional[bool] = False

class VersionCreate(BaseModel):
    agent_id: str
    version: str
    changelog: str

class SummarizeRequest(BaseModel):
    agent_id: str

# ─── Auth Helpers ───

def create_jwt_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

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
        if user:
            return user
    except jwt.PyJWTError:
        pass

    raise HTTPException(status_code=401, detail="Invalid session")

# ─── Auth Routes ───

@api_router.post("/auth/register")
async def register(data: UserRegister, response: Response):
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
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)
    token = create_jwt_token(user_id)
    response.set_cookie(key="session_token", value=token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*3600)
    return {"token": token, "user": {"user_id": user_id, "email": data.email, "name": data.name}}

@api_router.post("/auth/login")
async def login(data: UserLogin, response: Response):
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user or not pwd_context.verify(data.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_jwt_token(user["user_id"])
    response.set_cookie(key="session_token", value=token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*3600)
    return {"token": token, "user": {"user_id": user["user_id"], "email": user["email"], "name": user["name"], "picture": user.get("picture")}}

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
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(user_doc)
    session_token = data.get("session_token", str(uuid.uuid4()))
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    response.set_cookie(key="session_token", value=session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*3600)
    return {"token": session_token, "user": {"user_id": user_id, "email": email, "name": data["name"], "picture": data.get("picture")}}

@api_router.get("/auth/me")
async def auth_me(request: Request):
    user = await get_current_user(request)
    return {"user_id": user["user_id"], "email": user["email"], "name": user["name"], "picture": user.get("picture")}

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_many({"session_token": session_token})
    response.delete_cookie("session_token", path="/")
    return {"message": "Logged out"}

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
        "skills": data.skills or [],
        "integrations": data.integrations or [],
        "compatible_systems": data.compatible_systems or [],
        "category": data.category or "general",
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
    limit: int = 50,
    skip: int = 0
):
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"builder": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    if category and category != "all":
        query["category"] = category
    if skill:
        query["skills.name"] = {"$regex": skill, "$options": "i"}
    if integration:
        query["integrations"] = {"$regex": integration, "$options": "i"}
    if min_trust:
        query["trust_score"] = {"$gte": min_trust}

    sort_field = sort_by if sort_by in ["trust_score", "deployment_count", "created_at", "name"] else "trust_score"
    sort_dir = -1 if sort_field != "name" else 1

    agents = await db.agents.find(query, {"_id": 0}).sort(sort_field, sort_dir).skip(skip).limit(limit).to_list(limit)
    total = await db.agents.count_documents(query)
    return {"agents": agents, "total": total}

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
    avg_rating = sum(r["rating"] for r in reviews) / len(reviews) if reviews else 4.0
    user_satisfaction = (avg_rating / 5.0) * 100
    breakdown = agent.get("trust_breakdown", {})
    breakdown["user_satisfaction"] = round(user_satisfaction, 1)
    trust_score = (breakdown.get("task_completion", 85) * 0.3 + breakdown.get("security_audit", 80) * 0.2 + breakdown.get("uptime_score", 95) * 0.25 + breakdown["user_satisfaction"] * 0.25)
    await db.agents.update_one({"agent_id": agent_id}, {"$set": {"trust_score": round(trust_score, 1), "trust_breakdown": breakdown}})

@api_router.get("/trust-score/{agent_id}")
async def get_trust_score(agent_id: str):
    agent = await db.agents.find_one({"agent_id": agent_id}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "agent_id": agent_id,
        "trust_score": agent.get("trust_score", 0),
        "breakdown": agent.get("trust_breakdown", {}),
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
async def seed_data():
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

def _compute_trust(repo):
    """Derive a trust-like score from GitHub signals."""
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    open_issues = repo.get("open_issues_count", 0)
    watchers = repo.get("watchers_count", 0)
    has_license = repo.get("license") is not None

    # Popularity component (max 40)
    pop = min(40, (stars / 500) * 40) if stars else 0
    # Community component (max 25)
    comm = min(25, (forks / 100) * 25) if forks else 0
    # Maintenance component (max 20) — fewer open issues = better
    issue_ratio = open_issues / max(stars, 1)
    maint = max(0, 20 - issue_ratio * 100)
    # License component (15)
    lic = 15 if has_license else 5
    score = round(pop + comm + maint + lic, 1)
    return max(10, min(99, score))

def _map_repo_to_agent(repo, owner_id):
    """Convert a GitHub repo dict into our agent document."""
    topics = repo.get("topics", [])
    language = repo.get("language", "")
    description = repo.get("description", "") or "No description provided."
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    open_issues = repo.get("open_issues_count", 0)
    trust = _compute_trust(repo)
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

    return {
        "agent_id": f"gh_{repo['id']}",
        "owner_id": owner_id,
        "name": repo.get("name", "Unknown"),
        "builder": repo.get("owner", {}).get("login", "Unknown"),
        "description": description[:500],
        "avatar_url": repo.get("owner", {}).get("avatar_url"),
        "skills": skills,
        "integrations": integrations[:6],
        "compatible_systems": compatible[:5],
        "category": category,
        "deployment_count": stars,
        "uptime": uptime,
        "error_rate": error_rate,
        "trust_score": trust,
        "trust_breakdown": {
            "task_completion": round(min(98, 60 + (stars / 300) * 10), 1),
            "security_audit": 80 if repo.get("license") else 40,
            "uptime_score": round(uptime, 1),
            "user_satisfaction": round(min(98, 55 + (stars / 200) * 10), 1)
        },
        "versions": [{"version": "latest", "changelog": f"Last updated {repo.get('pushed_at', 'N/A')[:10]}", "date": repo.get("pushed_at", datetime.now(timezone.utc).isoformat())}],
        "auto_summary": None,
        "source": "github",
        "github_url": repo.get("html_url"),
        "github_stars": stars,
        "github_forks": forks,
        "github_language": language,
        "github_topics": topics,
        "github_license": repo.get("license", {}).get("spdx_id") if repo.get("license") else None,
        "created_at": repo.get("created_at", datetime.now(timezone.utc).isoformat()),
        "updated_at": repo.get("updated_at", datetime.now(timezone.utc).isoformat())
    }

@api_router.post("/github/import")
async def import_from_github(request: Request):
    """Fetch AI agent repos from GitHub search + OpenAI/Anthropic orgs and import them."""
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
                                await db.agents.update_one({"agent_id": agent_doc["agent_id"]}, {"$set": {
                                    "github_stars": agent_doc["github_stars"],
                                    "github_forks": agent_doc["github_forks"],
                                    "deployment_count": agent_doc["deployment_count"],
                                    "trust_score": agent_doc["trust_score"],
                                    "trust_breakdown": agent_doc["trust_breakdown"],
                                    "updated_at": agent_doc["updated_at"]
                                }})
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
                                    await db.agents.update_one({"agent_id": agent_doc["agent_id"]}, {"$set": {
                                        "github_stars": agent_doc["github_stars"],
                                        "github_forks": agent_doc["github_forks"],
                                        "deployment_count": agent_doc["deployment_count"],
                                        "trust_score": agent_doc["trust_score"],
                                        "trust_breakdown": agent_doc["trust_breakdown"],
                                        "updated_at": agent_doc["updated_at"]
                                    }})
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

    return {
        "agent_id": f"hf_{model_id.replace('/', '_')}",
        "owner_id": "huggingface_import",
        "name": name,
        "builder": builder,
        "description": description[:500],
        "avatar_url": f"https://huggingface.co/avatars/{sha[:12]}" if sha else None,
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

@api_router.post("/huggingface/import")
async def import_from_huggingface():
    """Fetch AI agent models from HuggingFace and import them."""
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
                                await db.agents.update_one({"agent_id": agent_doc["agent_id"]}, {"$set": {
                                    "hf_downloads": agent_doc["hf_downloads"],
                                    "hf_likes": agent_doc["hf_likes"],
                                    "deployment_count": agent_doc["deployment_count"],
                                    "trust_score": agent_doc["trust_score"],
                                    "trust_breakdown": agent_doc["trust_breakdown"],
                                    "updated_at": agent_doc["updated_at"]
                                }})
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
                            await db.agents.update_one({"agent_id": agent_doc["agent_id"]}, {"$set": {
                                "github_stars": agent_doc["github_stars"], "github_forks": agent_doc["github_forks"],
                                "deployment_count": agent_doc["deployment_count"], "trust_score": agent_doc["trust_score"],
                                "trust_breakdown": agent_doc["trust_breakdown"], "updated_at": datetime.now(timezone.utc).isoformat()
                            }})
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
                                await db.agents.update_one({"agent_id": agent_doc["agent_id"]}, {"$set": {
                                    "github_stars": agent_doc["github_stars"], "github_forks": agent_doc["github_forks"],
                                    "deployment_count": agent_doc["deployment_count"], "trust_score": agent_doc["trust_score"],
                                    "trust_breakdown": agent_doc["trust_breakdown"], "updated_at": datetime.now(timezone.utc).isoformat()
                                }})
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
                            await db.agents.update_one({"agent_id": agent_doc["agent_id"]}, {"$set": {
                                "hf_downloads": agent_doc["hf_downloads"], "hf_likes": agent_doc["hf_likes"],
                                "deployment_count": agent_doc["deployment_count"], "trust_score": agent_doc["trust_score"],
                                "trust_breakdown": agent_doc["trust_breakdown"], "updated_at": datetime.now(timezone.utc).isoformat()
                            }})
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
async def trigger_sync():
    """Manually trigger a sync cycle."""
    results = await _run_sync()
    return {"message": "Sync completed", "github": results["github"], "huggingface": results["huggingface"], "errors": results["errors"][:5]}

@api_router.get("/sync/status")
async def sync_status():
    """Get last sync log."""
    last = await db.sync_logs.find_one({}, {"_id": 0}, sort=[("timestamp", -1)])
    github_count = await db.agents.count_documents({"source": "github"})
    hf_count = await db.agents.count_documents({"source": "huggingface"})
    return {
        "last_sync": last,
        "github_agents": github_count,
        "huggingface_agents": hf_count,
        "sync_interval_hours": SYNC_INTERVAL_HOURS
    }

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
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    global sync_task
    logger.info("Starting auto-sync background task...")
    sync_task = asyncio.create_task(_sync_loop())

@app.on_event("shutdown")
async def shutdown_db_client():
    global sync_task
    if sync_task:
        sync_task.cancel()
    client.close()
