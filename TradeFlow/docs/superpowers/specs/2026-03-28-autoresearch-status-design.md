# Autoresearch Status Tracking Design

**Date:** 2026-03-28

**Goal:** Add an automatic timer and milestone tracker for the running autoresearch loop, with both machine-readable and human-readable outputs.

## Summary

TradeFlow will gain a sidecar status writer for the active autoresearch loop. The loop will update:

- `logs/autoresearch_status.json`
- `logs/autoresearch_status.md`

These files will represent the current run status and a short milestone history. The tracker is status-only and will not modify search logic, evaluation rules, or promotion criteria.

## Scope

### In Scope

- Automatic status updates written by the autoresearch loop
- A wall-clock timer for the active run
- Progress percentage against the configured run duration
- Milestone tracking and milestone history
- Best aggregate candidate summary
- Best fully promotable candidate summary
- Promotion status

### Out of Scope

- Changing evaluation rules
- Changing candidate generation
- Changing promotion criteria
- Adding a separate monitoring daemon

## Architecture

### Approach

Use a sidecar writer integrated directly into the autoresearch loop.

This keeps the implementation simple and accurate because the loop already knows:

- when it started
- how many iterations have completed
- how many candidates have been evaluated
- whether promotion has happened

### Files

#### New File

- `autoresearch_trading/status.py`
  - Owns status state shape
  - Renders JSON and Markdown outputs
  - Computes wall-clock progress and milestone state

#### Modified File

- `autoresearch_trading/loop.py`
  - Calls the status writer at startup, after each batch, and at completion

## Output Files

### JSON Source Of Truth

- `logs/autoresearch_status.json`

Contains the current run state, including:

- start time
- current timestamp
- elapsed seconds
- target duration hours
- estimated percent complete
- iterations completed
- candidates evaluated
- best aggregate candidate
- best promotable candidate
- promotion happened flag
- current state (`running`, `completed`, `stopped`)
- milestone history

### Human-Readable Status

- `logs/autoresearch_status.md`

Contains:

- run summary
- elapsed time
- percent complete
- latest best candidate summaries
- milestone checklist
- recent milestone history

## Milestones

The tracker will support these milestones:

- `Started`
- `First batch completed`
- `25% time elapsed`
- `50% time elapsed`
- `75% time elapsed`
- `Promoted winner`
- `Finished`

Each milestone event will be recorded in history with a timestamp.

## Update Rules

The loop will update status:

- once at startup
- after every candidate batch
- whenever a milestone threshold is crossed
- once at completion

If the loop exits early or fails, the status file should reflect that the run stopped before planned completion.

## Safety

This is a status-only feature:

- no effect on evaluation objective
- no effect on candidate generation
- no effect on promotion logic

The tracker must never become a dependency that can block research execution.

## Success Criteria

- The running loop continuously writes `logs/autoresearch_status.json`
- The running loop continuously writes `logs/autoresearch_status.md`
- Timer and percent complete reflect real wall-clock progress
- Milestones and milestone history update automatically
- Best aggregate and best promotable summaries are visible without reading raw experiment logs
