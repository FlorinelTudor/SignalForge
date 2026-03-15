# Hackathon Idea Kit

This workspace now includes a reproducible shortlist and implementation-brief generator for the Bucharest Hackathon ideas.

## Commands

```bash
python -m tradeflow_bot.hackathon scorecard
python -m tradeflow_bot.hackathon compare
python -m tradeflow_bot.hackathon brief milestonepay
python -m tradeflow_bot.hackathon brief policy-wallet
python -m tradeflow_bot.hackathon json
```

If you want a shell command after installation, the package also exposes:

```bash
hackathon-kit scorecard
```

## What It Gives You

- The full six-track shortlist with complexity, innovation, and confidence ratings.
- Decision-ready comparison between the two finalists: `MilestonePay` and `Policy Wallet`.
- Implementation briefs with:
  - default scope
  - recommended stack
  - MVP features
  - API endpoints
  - core entities
  - AI outputs
  - 90-second demo flow
  - build order
  - acceptance criteria
- JSON output for feeding directly into another coding agent or a prompt pack.

## Defaults Chosen

- Solo or AI-heavy builder profile.
- Best chance to win over maximum novelty.
- Single-chain demos with deterministic fallback mode.
- `MilestonePay` is the safest primary build.
- `Policy Wallet` is the stronger high-upside alternative.
- `Exit Liquidity Radar` is the lower-risk fallback.
