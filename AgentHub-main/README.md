# AgentXplorer

AgentXplorer is a curated discovery layer for AI agents. It helps builders and teams find trustworthy agents fast, understand quality signals at a glance, and act on them without digging through scattered repos, model cards, or social threads.

## Problem

The agent ecosystem is fragmented. Builders publish agents across GitHub, Hugging Face, and private demos with inconsistent metadata and unclear quality signals. Users waste time sifting, and bad or outdated agents look the same as reliable ones.

## Value

AgentXplorer consolidates the ecosystem into one searchable hub with transparent trust scoring, verification signals, and fast comparisons so builders can ship and teams can choose with confidence.

## Key Features

- Unified discovery across GitHub and Hugging Face agents.
- Trust Score with explainable components (repo health, reviews, uptime, audits, etc.).
- Verified badge based on telemetry + audits + review verification + repo health.
- Category, trust, and verified-only filters with fast search.
- Agent profiles with metrics, versions, reviews, and external links.
- Vibe Pro quick-start packs for builders.
- Stripe Checkout for paid plans (Verified, Pro, Vibe Pro).

## Trust Score Formula

One-line formula:

`Trust = Cap80IfUnverified( ((1 - w_design) * (BaseSignals * RecencyDecay)) + (w_design * DesignScore) )`

Where:

- `BaseSignals = 0.7 * Avg(verified_signals) + 0.3 * Avg(unverified_signals)` (or only one side if the other is missing).
- `RecencyDecay` reduces stale agents after 30 days of inactivity (floor at `0.6`).
- `w_design = 0.2 * max(0.25, design_confidence)`.
- If badge requirements are not met, `Trust = min(Trust, 80)`.

### Signal Inputs (0-100 each)

- `usage`: log-scaled deployment signal (`deployment_count` with anti-spike damping using 7d/30d counters).
- `uptime`: normalized uptime percent.
- `reliability`: `100 - error_rate`.
- `skill_benchmarks`: average benchmark from skills (verified skills preferred).
- `reviews`: normalized average review rating (verified reviews preferred).
- `github_stars`: log-scaled social proof.
- `hf_downloads`: log-scaled model adoption.
- `repo_health`: repository health score (freshness, issue pressure, community, license).
- `security_audit`: security audit component when present.

### Design Quality Layer (Relative Cognitive Complexity)

The design layer is computed automatically and blended into trust:

- `cc_density` (lower is better): concentration of complexity in analyzed code.
- `hotspot_ratio` (lower is better): complexity concentrated in frequently changing areas.
- `cycle_ratio` (lower is better): dependency cycle pressure.
- `test_on_complex` (higher is better): testing depth on complex code paths.
- `maintainability` (higher is better): maintainability proxy from project hygiene signals.

Design score weighting:

- `40% cc_density`
- `20% hotspot_ratio`
- `20% cycle_ratio`
- `15% test_on_complex`
- `5% maintainability`

Design confidence increases with:

- adequate sample size (`sample_loc >= 500`, `functions_analyzed >= 25`)
- peer-baseline coverage
- generated/vendor code exclusion
- historical scan continuity

### Verified Badge Requirements

An agent is `Verified` only if all are true:

- telemetry/usage verification
- security audit verification
- review verification
- repo health verification

## Roadmap

- Public API for agent search, trust score, and verification status.
- Org workspaces and team collaboration features.
- Agent telemetry ingestion and security audit uploads.
- Verified-only discovery mode with enterprise controls.
- Agent benchmarking and standardized evaluation suites.
- One-click deploy templates for popular stacks.
