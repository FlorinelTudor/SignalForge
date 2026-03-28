# TradeFlow Autoresearch Program

You are improving TradeFlow using a strategy-only autoresearch loop.

## Editable Surface

Only edit:

- `autoresearch_trading/candidate_strategy.py`

Do not edit:

- broker code
- execution code
- evaluator logic
- promotion logic

## Goal

Improve holdout performance on the current `SYMBOLS` basket.

Primary objective:

- higher holdout objective than baseline

Subject to:

- no unacceptable drawdown increase
- no degenerate no-trade solution

## What To Change

You may change:

- momentum threshold behavior
- z-score threshold behavior
- momentum vs mean-reversion weights

Keep changes small and reviewable.
