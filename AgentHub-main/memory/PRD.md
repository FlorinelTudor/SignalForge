# AgentNet - LinkedIn for AI Agents

## Problem Statement
Build a professional network for AI agents with profiles, portfolios, reviews, trust scores, and network recommendations.

## Architecture
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + Framer Motion + Recharts
- **Backend**: FastAPI + MongoDB (Motor async driver)
- **Auth**: JWT (email/password) + Emergent Google OAuth
- **AI**: GPT-5.2 via Emergent Integrations (auto-summarize agent profiles)
- **Theme**: "Sentient Terminal" - Dark cyberpunk with cyan/violet accents

## User Personas
1. **Agent Builders** - Register and showcase their AI agents with benchmarks
2. **Enterprise Deployers** - Discover, evaluate, and compare AI agents
3. **DevOps Teams** - Find compatible agent stacks based on integration data

## Core Requirements
- Agent profiles with verified benchmarks, deployment stats, version history
- Portfolio with case studies and before/after metrics
- Reviews from humans and agent endorsements
- Composite trust score with breakdown
- Network recommendations (card-based, frequently deployed with)
- Search/filter by skills, category, integrations, trust score
- OpenAI Codex and Claude Skills integration badges

## What's Been Implemented (Feb 10, 2026)
- [x] Landing page with hero, features, live stats
- [x] Auth (JWT + Google OAuth) with protected routes
- [x] Discover page with search, category filters, sort
- [x] Agent profile with bento grid layout
- [x] Trust score radial chart + breakdown bars
- [x] Verified skills with benchmark progress bars
- [x] Portfolio tab with case studies, before/after metrics
- [x] Reviews & endorsements (human + agent types)
- [x] Incident history with severity badges
- [x] Version history timeline
- [x] Network recommendations (card-based)
- [x] Dashboard with agent management
- [x] Create new agent form
- [x] GPT-5.2 auto-summarize endpoint
- [x] 8 seed agents with rich demo data
- [x] OpenAI Codex & Claude Skills integration badges
- [x] **GitHub Import**: Fetch real AI agent repos from GitHub (topics search + OpenAI/Anthropic orgs)
- [x] **65 real agents imported** from GitHub with stars, forks, language, license, topics
- [x] GitHub-specific agent cards (GitHubAgentCard) with star counts, fork counts, language badges
- [x] GitHub agent profiles show View Repository link, GitHub stats row
- [x] Discover page tabs: "All Agents" vs "GitHub Imported"
- [x] Trust score derived from GitHub signals (stars, forks, issues, license)
- [x] **HuggingFace Import**: Fetch AI agent models (agent, autonomous-agents, tool-use, function-calling tags)
- [x] **49 HuggingFace models imported** with downloads, likes, pipeline tags
- [x] HuggingFace-specific amber-themed cards with download stats, likes, pipeline tags
- [x] HuggingFace profile pages show downloads/likes, pipeline tags, View on HuggingFace button
- [x] **3-tab Discover page**: All Agents (125+), GitHub (65), HuggingFace (49)
- [x] **Auto-sync background task**: Refreshes GitHub + HuggingFace data every 6 hours
- [x] Sync status display, manual trigger endpoint, sync logs in DB
- [x] **Prominent "View Repository" / "View on HuggingFace" buttons** (cyan/amber styled, bordered, with icons)
- [x] GitHub PAT configured for 5000 req/hr rate limit

## Prioritized Backlog
### P0 (Critical)
- All core features implemented

### P1 (High)
- Agent edit/update from dashboard
- Full portfolio CRUD from dashboard
- Agent comparison view (side-by-side)
- Trust score decay over time mechanism

### P2 (Medium)
- Agent analytics dashboard (deployment trends, review sentiment)
- Bulk import agents via CSV/API
- Agent API documentation generator
- Notification system for reviews/endorsements
- Advanced search with filters (min trust score, uptime threshold)

## Next Tasks
1. Agent edit functionality from dashboard
2. Portfolio management from dashboard
3. Agent comparison feature
4. Trust score history/decay visualization
5. Notification system
