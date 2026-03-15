from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Idea:
    slug: str
    track: str
    name: str
    why_fit: str
    complexity: int
    innovation: int
    confidence: int
    finalist_rank: int | None = None
    fallback: bool = False


@dataclass(frozen=True)
class Brief:
    slug: str
    name: str
    pitch: str
    best_for: str
    default_scope: tuple[str, ...]
    recommended_stack: tuple[str, ...]
    mvp_features: tuple[str, ...]
    api_endpoints: tuple[str, ...]
    core_entities: tuple[str, ...]
    ai_outputs: tuple[str, ...]
    demo_flow: tuple[str, ...]
    build_order: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]


SHORTLIST: tuple[Idea, ...] = (
    Idea(
        slug="gasscope-copilot",
        track="Protocol Experiments",
        name="GasScope Copilot",
        why_fit=(
            "Paste a contract or tx hash and get gas hotspots, failing call patterns, "
            "and AI-generated optimization suggestions from recent traces."
        ),
        complexity=3,
        innovation=3,
        confidence=3,
    ),
    Idea(
        slug="milestonepay",
        track="DeFi & Payments",
        name="MilestonePay",
        why_fit=(
            "Turn a plain-English freelance agreement into USDC milestone escrow, "
            "release logic, and payout splits."
        ),
        complexity=3,
        innovation=4,
        confidence=5,
        finalist_rank=1,
    ),
    Idea(
        slug="policy-wallet",
        track="Agentic AI On Chain",
        name="Policy Wallet",
        why_fit=(
            "A guardrailed wallet agent that can pay invoices, rebalance stablecoins, "
            "or revoke risky approvals inside user-defined limits."
        ),
        complexity=4,
        innovation=5,
        confidence=4,
        finalist_rank=2,
    ),
    Idea(
        slug="exit-liquidity-radar",
        track="AI for On-Chain Intelligence",
        name="Exit Liquidity Radar",
        why_fit=(
            "Explainable risk engine for wallets or tokens that flags rug-like behavior, "
            "suspicious outflows, and scam patterns in plain English."
        ),
        complexity=3,
        innovation=4,
        confidence=4,
        fallback=True,
    ),
    Idea(
        slug="treasuryops-autopilot",
        track="AI Business Automation",
        name="TreasuryOps Autopilot",
        why_fit=(
            "Reconcile stablecoin inflows and outflows to invoices and produce a "
            "founder-friendly finance summary with anomaly flags."
        ),
        complexity=2,
        innovation=3,
        confidence=4,
    ),
    Idea(
        slug="agent-passport",
        track="Wildcard",
        name="Agent Passport",
        why_fit=(
            "On-chain identity, permissions, signed action receipts, and reputation "
            "for AI agents."
        ),
        complexity=4,
        innovation=5,
        confidence=4,
    ),
)


BRIEFS: dict[str, Brief] = {
    "milestonepay": Brief(
        slug="milestonepay",
        name="MilestonePay",
        pitch=(
            "Convert a client chat or freelance agreement into a milestone-based "
            "USDC escrow flow with clear release events and a judge-friendly demo."
        ),
        best_for=(
            "Highest probability of shipping a polished 24-hour prototype with clear "
            "business value and stablecoin relevance."
        ),
        default_scope=(
            "Use Base Sepolia as the single demo chain.",
            "Use one mock USDC token for deterministic demo flows.",
            "Support one client, one freelancer, and up to three milestones.",
            "Keep one funding flow and one release flow; do not build disputes or arbitration.",
            "Require human approval for every on-chain action.",
        ),
        recommended_stack=(
            "Frontend: Next.js + TypeScript + Tailwind.",
            "Wallet and execution: Alchemy smart wallet or Account Kit.",
            "AI extraction: OpenAI structured output for milestone parsing and summary generation.",
            "Persistence: SQLite or Supabase for projects, milestones, escrows, and release logs.",
            "Fallback mode: seeded demo project that behaves identically without live wallet funding.",
        ),
        mvp_features=(
            "Paste agreement text or chat transcript and extract project title, parties, milestones, due dates, and split rules.",
            "Review and edit AI-generated milestone plan before creation.",
            "Create an escrow record with funding state and milestone schedule.",
            "Release one milestone and append an immutable payout log entry.",
            "Show a status page with funded amount, released amount, and next pending milestone.",
        ),
        api_endpoints=(
            "POST /projects/from-chat",
            "POST /escrows",
            "POST /milestones/:id/release",
            "GET /projects/:id/status",
        ),
        core_entities=(
            "Project",
            "Milestone",
            "Escrow",
            "PayoutSplit",
            "ReleaseEvent",
            "AgreementSummary",
        ),
        ai_outputs=(
            "Structured milestone extraction with amount, due date, and release condition.",
            "One-screen agreement summary with missing-field warnings.",
            "Judge-facing explanation of how the escrow reduces payment friction and mistrust.",
        ),
        demo_flow=(
            "Paste a short freelance agreement into the intake form.",
            "Show AI-generated milestones and edit one field to prove human control.",
            "Create the escrow and display funded mock USDC balance.",
            "Release the first milestone with one click.",
            "Finish on the project status screen with the line: turned a messy agreement into a release-ready payment plan in under 90 seconds.",
        ),
        build_order=(
            "Implement the idea data model and seeded sample project.",
            "Build agreement intake and structured extraction.",
            "Build milestone review UI and escrow creation handler.",
            "Add release action plus project status timeline.",
            "Add deterministic demo mode and one-click sample data reset.",
        ),
        acceptance_criteria=(
            "Happy-path demo completes in under 90 seconds.",
            "Every AI output is editable before any money movement.",
            "The final screen shows paid, pending, and next release values.",
            "The app still works in demo mode with no chain connectivity.",
        ),
    ),
    "policy-wallet": Brief(
        slug="policy-wallet",
        name="Policy Wallet",
        pitch=(
            "A human-in-the-loop wallet copilot that interprets natural-language requests, "
            "checks them against user-defined policies, and executes only safe actions."
        ),
        best_for=(
            "Most memorable judge story if you want a stronger AI x on-chain identity and "
            "agent narrative."
        ),
        default_scope=(
            "Use Base Sepolia as the single demo chain.",
            "Use one mock USDC token and a single connected smart wallet.",
            "Support exactly three actions: pay invoice, revoke approval, rebalance to stablecoin.",
            "Run policy checks before execution and require explicit user confirmation.",
            "Do not implement autonomous trading, cross-chain logic, or background agents.",
        ),
        recommended_stack=(
            "Frontend: Next.js + TypeScript + Tailwind.",
            "Wallet and simulation: Alchemy smart wallets with transaction simulation.",
            "AI planner: OpenAI structured output that maps natural language into a proposed wallet action.",
            "Persistence: SQLite or Supabase for policy definitions, action plans, and audit logs.",
            "Fallback mode: pre-seeded wallet state plus mocked simulation results.",
        ),
        mvp_features=(
            "Create a policy with limits like max payment amount, approved recipients, and blocked action types.",
            "Translate a natural-language instruction into a proposed wallet action plus rationale.",
            "Simulate the action and show which policy rules passed or failed.",
            "Execute approved actions and append a tamper-evident audit log entry.",
            "Display a wallet timeline of requested, simulated, approved, and executed actions.",
        ),
        api_endpoints=(
            "POST /policies",
            "POST /agent/simulate",
            "POST /agent/execute",
            "GET /wallet/:address/audit-log",
        ),
        core_entities=(
            "WalletPolicy",
            "PolicyRule",
            "ActionRequest",
            "SimulatedAction",
            "ExecutionReceipt",
            "AuditLogEntry",
        ),
        ai_outputs=(
            "Structured action plan with recipient, token, amount, and action type.",
            "Policy explanation that cites the exact rule that allowed or blocked the action.",
            "One-line risk summary for the final demo screen.",
        ),
        demo_flow=(
            "Create a policy that allows invoice payments under a fixed amount and blocks unknown recipients.",
            "Ask the wallet copilot to pay a known contractor invoice.",
            "Show the simulated action and the policy checks that passed.",
            "Approve and execute the payment.",
            "Finish on the audit log screen with the line: your wallet now explains and constrains every AI action before funds move.",
        ),
        build_order=(
            "Implement policy, action request, and audit-log models.",
            "Build policy creation UI with one sensible default policy template.",
            "Build structured action planning and policy evaluation.",
            "Add simulation result screen and execution flow.",
            "Add deterministic demo mode with seeded wallet state and receipts.",
        ),
        acceptance_criteria=(
            "The app supports one full natural-language request to execution flow in under 90 seconds.",
            "Blocked actions always explain why they failed.",
            "The audit log captures requested, simulated, and executed states.",
            "The demo works without live chain connectivity.",
        ),
    ),
    "exit-liquidity-radar": Brief(
        slug="exit-liquidity-radar",
        name="Exit Liquidity Radar",
        pitch=(
            "Surface wallet and token risk signals in plain English so a founder or trader "
            "can understand why something looks dangerous without reading raw on-chain data."
        ),
        best_for=(
            "Best fallback if you want lower build risk than Policy Wallet while keeping a "
            "strong AI + on-chain story."
        ),
        default_scope=(
            "Score either a wallet or token, not both in the same flow.",
            "Use a fixed handful of explainable signals such as concentration, outflow spikes, and approval risk.",
            "Keep the output descriptive and explainable; do not claim perfect fraud detection.",
        ),
        recommended_stack=(
            "Frontend: Next.js + TypeScript + Tailwind.",
            "Data: Dune or indexed sample datasets for wallet and token activity.",
            "AI explanation: OpenAI structured output that converts raw signals into a concise risk memo.",
        ),
        mvp_features=(
            "Paste address or token and compute a risk score with contributing factors.",
            "Explain the top three reasons behind the score in plain English.",
            "Compare current risk to a safe-looking baseline example.",
        ),
        api_endpoints=(
            "POST /risk/analyze",
            "GET /risk/:id",
        ),
        core_entities=(
            "RiskScan",
            "RiskSignal",
            "ExplainabilityNote",
        ),
        ai_outputs=(
            "Plain-English explanation of why the asset looks normal or dangerous.",
        ),
        demo_flow=(
            "Analyze one seeded risky example and one safe example back to back.",
        ),
        build_order=(
            "Implement fixed-signal scoring first, then explanation generation, then the side-by-side UI.",
        ),
        acceptance_criteria=(
            "The explanation names the exact signals that drove the score.",
        ),
    ),
}


RESEARCH_BASIS = (
    "Hackathon format assumption: April 25-26, 2026, 24-hour, in-person build with six sponsor-aligned tracks.",
    "Stablecoin timing basis: Stripe announced AI and stablecoin launches on May 7, 2025, including stablecoin-powered accounts in 101 countries.",
    "On-chain intelligence basis: Dune positions its platform around 100+ chains and 1.5M+ datasets.",
    "Fraud urgency basis: Chainalysis reported on January 13, 2026 that 2025 scam activity was at least $14B on-chain, with the estimate likely to rise as attribution expands.",
)


def shortlist_payload() -> dict[str, object]:
    return {
        "summary": {
            "optimization_goal": "best chance to win",
            "team_profile": "solo or AI-heavy builder",
            "top_two_overall": ["MilestonePay", "Policy Wallet"],
            "lower_risk_fallback": "Exit Liquidity Radar",
        },
        "ideas": [asdict(idea) for idea in SHORTLIST],
        "briefs": {slug: asdict(brief) for slug, brief in BRIEFS.items()},
        "research_basis": list(RESEARCH_BASIS),
    }


def get_idea(slug: str) -> Idea:
    for idea in SHORTLIST:
        if idea.slug == slug:
            return idea
    raise KeyError(f"Unknown idea slug: {slug}")


def get_brief(slug: str) -> Brief:
    try:
        return BRIEFS[slug]
    except KeyError as exc:
        raise KeyError(f"No implementation brief available for: {slug}") from exc


def render_scorecard() -> str:
    lines = [
        "# Bucharest Hackathon Idea Shortlist",
        "",
        "- Optimize for: best chance to win with a solo or AI-heavy builder.",
        "- Rating scale: Complexity 1 = easiest, 5 = hardest. Innovation 1 = expected, 5 = standout. Confidence = strength as a hackathon bet.",
        "- Top two overall: MilestonePay, Policy Wallet.",
        "- Lower-risk fallback: Exit Liquidity Radar.",
        "",
        "| Track | Idea | Why it fits | Complexity | Innovation | Confidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for idea in SHORTLIST:
        lines.append(
            f"| {idea.track} | {idea.name} | {idea.why_fit} | "
            f"{idea.complexity} | {idea.innovation} | {idea.confidence} |"
        )
    lines.append("")
    lines.append("## Research Basis")
    for item in RESEARCH_BASIS:
        lines.append(f"- {item}")
    return "\n".join(lines)


def render_compare(slugs: tuple[str, ...] | None = None) -> str:
    finalists = slugs or ("milestonepay", "policy-wallet")
    briefs = [get_brief(slug) for slug in finalists]
    lines = [
        "# Finalist Comparison",
        "",
        "## Recommendation",
        "- Choose MilestonePay if you want the best chance of a polished, low-drama demo with obvious business value.",
        "- Choose Policy Wallet if you want the most memorable AI x wallet story and can handle a bit more execution risk.",
        "",
    ]
    for brief in briefs:
        lines.extend(
            [
                f"## {brief.name}",
                f"- Pitch: {brief.pitch}",
                f"- Best for: {brief.best_for}",
                f"- Scope: {brief.default_scope[0]} {brief.default_scope[1]}",
                f"- Demo close: {brief.demo_flow[-1]}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def render_brief(slug: str) -> str:
    idea = get_idea(slug)
    brief = get_brief(slug)
    lines = [
        f"# {brief.name}",
        "",
        f"- Track: {idea.track}",
        f"- Complexity: {idea.complexity}/5",
        f"- Innovation: {idea.innovation}/5",
        f"- Confidence: {idea.confidence}/5",
        f"- Best for: {brief.best_for}",
        "",
        "## Pitch",
        brief.pitch,
        "",
        "## Default Scope",
    ]
    for item in brief.default_scope:
        lines.append(f"- {item}")
    lines.extend(["", "## Recommended Stack"])
    for item in brief.recommended_stack:
        lines.append(f"- {item}")
    lines.extend(["", "## MVP Features"])
    for item in brief.mvp_features:
        lines.append(f"- {item}")
    lines.extend(["", "## API Endpoints"])
    for item in brief.api_endpoints:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Core Entities"])
    for item in brief.core_entities:
        lines.append(f"- `{item}`")
    lines.extend(["", "## AI Outputs"])
    for item in brief.ai_outputs:
        lines.append(f"- {item}")
    lines.extend(["", "## Demo Flow"])
    for idx, item in enumerate(brief.demo_flow, start=1):
        lines.append(f"{idx}. {item}")
    lines.extend(["", "## Build Order"])
    for idx, item in enumerate(brief.build_order, start=1):
        lines.append(f"{idx}. {item}")
    lines.extend(["", "## Acceptance Criteria"])
    for item in brief.acceptance_criteria:
        lines.append(f"- {item}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hackathon shortlist and implementation brief generator")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("scorecard", help="Print the full shortlist with ratings")
    subparsers.add_parser("compare", help="Compare the two recommended finalists")

    brief_parser = subparsers.add_parser("brief", help="Print the implementation brief for one idea")
    brief_parser.add_argument("slug", choices=sorted(BRIEFS), help="Idea slug")

    json_parser = subparsers.add_parser("json", help="Print machine-readable shortlist data")
    json_parser.add_argument("--slug", choices=sorted(BRIEFS), help="Idea slug to filter to one brief")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "scorecard"):
        print(render_scorecard())
        return 0

    if args.command == "compare":
        print(render_compare())
        return 0

    if args.command == "brief":
        print(render_brief(args.slug))
        return 0

    if args.command == "json":
        payload = shortlist_payload()
        if args.slug:
            payload["briefs"] = {args.slug: payload["briefs"][args.slug]}
        print(json.dumps(payload, indent=2))
        return 0

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
