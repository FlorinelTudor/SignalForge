# Autoresearch Trading Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a strategy-only autoresearch sandbox that evaluates candidate strategy logic on the current live symbol basket and safely promotes approved parameters into TradeFlow.

**Architecture:** A new `autoresearch_trading` package will contain the single editable candidate strategy, a fixed evaluator, and `program.md`. Production code in `tradeflow_bot` will expose CLI actions to evaluate and promote results while continuing to own execution and safety behavior.

**Tech Stack:** Python, pandas, existing TradeFlow backtest/data modules, pytest, JSON artifacts

---

### Task 1: Add failing tests for autoresearch evaluation and promotion

**Files:**
- Create: `tests/test_autoresearch.py`
- Test: `tests/test_autoresearch.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- evaluating baseline and candidate metrics over synthetic symbol data
- rejecting promotion when candidate does not beat baseline
- persisting a best-candidate artifact on success

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_autoresearch.py -q`
Expected: FAIL with import or missing symbol errors for `autoresearch_trading`

- [ ] **Step 3: Write minimal implementation**

Create:
- `autoresearch_trading/__init__.py`
- `autoresearch_trading/candidate_strategy.py`
- `autoresearch_trading/evaluator.py`

Implement the smallest evaluator API needed by the tests.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_autoresearch.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_autoresearch.py autoresearch_trading
git commit -m "feat: add autoresearch evaluator sandbox"
```

### Task 2: Wire new CLI actions into TradeFlow

**Files:**
- Modify: `tradeflow_bot/main.py`
- Test: `tests/test_autoresearch.py`

- [ ] **Step 1: Write the failing test**

Add a test for the new workflow entry points:
- `autoresearch-eval`
- `autoresearch-promote`

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_autoresearch.py -q`
Expected: FAIL because CLI actions do not exist yet

- [ ] **Step 3: Write minimal implementation**

Update `tradeflow_bot/main.py` to:
- parse new actions
- invoke the evaluator
- print JSON summaries

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_autoresearch.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tradeflow_bot/main.py tests/test_autoresearch.py
git commit -m "feat: add autoresearch CLI actions"
```

### Task 3: Add documentation and journaling

**Files:**
- Create: `autoresearch_trading/program.md`
- Modify: `README.md`
- Modify: `Strategy.md`

- [ ] **Step 1: Write the failing test**

Add coverage for promotion artifact metadata or journaling hook if practical. If not practical, document expected manual verification for `Strategy.md`.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_autoresearch.py -q`
Expected: FAIL for missing metadata or journaling behavior

- [ ] **Step 3: Write minimal implementation**

Add:
- `autoresearch_trading/program.md`
- README usage docs
- promotion journal append in `Strategy.md`

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_autoresearch.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add autoresearch_trading/program.md README.md Strategy.md tests/test_autoresearch.py
git commit -m "docs: add autoresearch workflow"
```

### Task 4: Run full verification

**Files:**
- Test: `tests/test_autoresearch.py`
- Test: `tests/test_adaptive.py`
- Test: `tests/test_strategy.py`

- [ ] **Step 1: Run focused tests**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_autoresearch.py tests/test_adaptive.py tests/test_strategy.py -q`
Expected: PASS

- [ ] **Step 2: Run full test suite**

Run: `PYTHONPATH=. .venv/bin/pytest -q`
Expected: PASS

- [ ] **Step 3: Record outcomes**

Capture:
- number of tests passed
- new files added
- commands for future use

- [ ] **Step 4: Commit**

```bash
git add README.md Strategy.md tradeflow_bot/main.py autoresearch_trading tests/test_autoresearch.py
git commit -m "feat: add strategy-only autoresearch harness"
```
