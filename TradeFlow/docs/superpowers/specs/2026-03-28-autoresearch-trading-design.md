# Autoresearch Trading Design

**Date:** 2026-03-28

**Goal:** Add a Karpathy-style `autoresearch` sandbox to TradeFlow so the bot can iteratively improve trading strategy logic on the current live symbol basket, while keeping live execution code fixed and safe.

## Summary

TradeFlow will gain a dedicated research sandbox that mirrors the core `karpathy/autoresearch` pattern:

- a fixed evaluator
- a single editable strategy surface
- a human-authored `program.md`
- a promotion gate before live settings change

The research loop will optimize strategy-only behavior for the symbols currently configured in `SYMBOLS`. It will not modify broker, execution, or portfolio safety code.

## Scope

### In Scope

- Add a new `autoresearch_trading/` package inside the repo
- Define a single editable candidate strategy module
- Define a fixed evaluator that scores candidate strategies on the current live symbol basket
- Add CLI entry points to evaluate and promote the best candidate
- Persist approved candidate outputs as constrained artifacts
- Append research outcomes to `Strategy.md`

### Out of Scope

- Agent-driven modification of broker integrations
- Agent-driven modification of order execution logic
- Agent-driven modification of live portfolio guardrails
- Full ML architecture search

## Architecture

### New Research Sandbox

Create a new folder:

- `autoresearch_trading/`

This folder isolates research-time artifacts from production execution code.

### Fixed Files

- `autoresearch_trading/evaluator.py`
  - Loads historical data for the configured live symbol basket
  - Computes baseline and candidate performance
  - Applies a fixed objective and promotion guardrails
- `autoresearch_trading/program.md`
  - Human-authored instructions that describe what the candidate is allowed to change
- `autoresearch_trading/__init__.py`
  - Package boundary only

### Single Editable File

- `autoresearch_trading/candidate_strategy.py`
  - Contains only strategy logic the research loop is allowed to change
  - Exposes a stable interface that the evaluator calls

### Production Integration

TradeFlow production code will remain the source of truth for:

- data fetching
- backtest execution
- order placement
- safety checks

The only thing promoted from research is a constrained artifact describing approved strategy parameters and metadata.

## Data Flow

1. The evaluator loads the configured `SYMBOLS`.
2. It fetches historical bars through the existing data client.
3. It computes a baseline result using the current production strategy parameters.
4. It computes candidate results using the sandbox candidate strategy.
5. It scores both on a fixed objective.
6. If the candidate clears promotion rules, it writes an artifact in `reports/`.
7. A promotion command can apply the approved parameters into `.env` and journal the result in `Strategy.md`.

## Evaluation Rules

### Target Universe

Use the current live symbol basket from `SYMBOLS` so research is aligned with the bot’s actual trading universe.

### Time Splits

Use a holdout-aware evaluation:

- training window: where candidate iteration is measured
- holdout window: where promotion approval is decided

The candidate must outperform the baseline on holdout, not only on the full sample.

### Objective

The evaluator will use a fixed objective designed to reward usable performance:

`objective = sharpe + 0.2 * total_return - 0.3 * abs(max_drawdown) - turnover_penalty`

Turnover penalty will be derived from trade count or signal changes so the candidate cannot win by churning excessively.

### Promotion Guardrails

A candidate can only be promoted if:

- holdout objective is better than baseline
- holdout max drawdown does not worsen beyond a configured limit
- the strategy trades at least a minimum number of times

## Promotion Model

Promotion writes a constrained artifact, for example:

- `reports/autoresearch_best.json`

This artifact will contain:

- selected thresholds
- rule weights
- metadata about baseline vs candidate results
- timestamps and symbol basket used

Live code will only read approved parameter fields from this artifact. It will not import arbitrary research code into execution.

## Files To Add Or Modify

### New Files

- `autoresearch_trading/__init__.py`
- `autoresearch_trading/candidate_strategy.py`
- `autoresearch_trading/evaluator.py`
- `autoresearch_trading/program.md`
- `tests/test_autoresearch.py`

### Modified Files

- `tradeflow_bot/main.py`
- `README.md`
- `Strategy.md`

## Testing Strategy

- Unit tests for candidate-vs-baseline evaluation
- Unit tests for promotion success/failure rules
- Unit tests for artifact persistence and loading
- CLI-level tests for new actions where practical

## Risks And Mitigations

### Overfitting

Mitigation:

- use holdout window
- fixed objective
- promotion gate

### Unsafe Live Changes

Mitigation:

- sandbox research code away from execution code
- only promote constrained parameters

### Silent No-Trade Winners

Mitigation:

- require minimum trade count
- penalize trivial/degenerate strategies

## Success Criteria

- We can run a fixed research evaluation over the current live symbol basket
- The candidate strategy is isolated in one file
- Promotion only updates approved parameters
- The outcome is logged in `Strategy.md`
- Existing live execution behavior remains unchanged unless a candidate is explicitly promoted
