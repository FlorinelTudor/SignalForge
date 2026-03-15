from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path

from tradeflow_bot.brokers.factory import build_broker
from tradeflow_bot.config import load_settings
from tradeflow_bot.data import DataClient
from tradeflow_bot.execution import TradingEngine, setup_complete_message
from tradeflow_bot.history import AlpacaHistoryImprover
from tradeflow_bot.ml import ModelManager
from tradeflow_bot.notifier import Notifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TradeFlow self-learning trading bot")
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    parser.add_argument(
        "--action",
        choices=["setup", "backtest", "run-once", "run-loop", "improve-history", "backtest-improve"],
        default="setup",
        help="Action to execute",
    )
    parser.add_argument(
        "--data-source",
        choices=["yfinance", "alpaca", "synthetic"],
        default="yfinance",
        help="Market data source",
    )
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def to_jsonable(obj):
    if is_dataclass(obj):
        return asdict(obj)
    return obj


def apply_env_suggestions(env_file: str, suggestions) -> list[str]:
    env_path = Path(env_file)
    if not env_path.exists():
        env_path.write_text("", encoding="utf-8")

    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated = []

    for s in suggestions:
        key = s.key
        val = s.new
        replaced = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={val}"
                replaced = True
                break
        if not replaced:
            lines.append(f"{key}={val}")
        updated.append(f"{key}={val}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated


def improve_from_history(settings, env_file: str):
    improver = AlpacaHistoryImprover(settings)
    fills = improver.fetch_history_records()
    summary, closed = improver.analyze(fills)
    suggestions = improver.suggest(summary)
    report_path = improver.persist_report(summary, suggestions, closed, settings.report_dir)

    updated = []
    if suggestions:
        updated = apply_env_suggestions(env_file, suggestions)

    return summary, suggestions, updated, report_path


def main() -> None:
    configure_logging()
    args = parse_args()
    settings = load_settings(args.env_file)

    data_client = DataClient(
        source=args.data_source,
        alpaca_api_key=settings.alpaca_api_key,
        alpaca_secret_key=settings.alpaca_secret_key,
        alpaca_data_url=settings.alpaca_data_url,
    )
    broker = build_broker(settings)
    model_manager = ModelManager(model_path=settings.model_path)
    notifier = Notifier(settings)
    engine = TradingEngine(settings, data_client, broker, model_manager, notifier)

    if args.action == "backtest":
        report, csv_path, json_path = engine.run_backtest()
        print(json.dumps(report.__dict__, indent=2))
        print(f"Saved backtest CSV: {csv_path}")
        print(f"Saved backtest JSON: {json_path}")
        return

    if args.action == "improve-history":
        summary, suggestions, updated, report_path = improve_from_history(settings, args.env_file)
        print(json.dumps(summary.__dict__, indent=2))
        print(f"Saved improvement report: {report_path}")
        print(f"Suggestions applied: {len(suggestions)}")
        if updated:
            print("Updated .env keys:")
            for line in updated:
                print(f"- {line}")
        return

    if args.action == "backtest-improve":
        report, csv_path, json_path = engine.run_backtest()
        summary, suggestions, updated, report_path = improve_from_history(settings, args.env_file)
        print(json.dumps(report.__dict__, indent=2))
        print(f"Saved backtest CSV: {csv_path}")
        print(f"Saved backtest JSON: {json_path}")
        print(json.dumps(summary.__dict__, indent=2))
        print(f"Saved improvement report: {report_path}")
        print(f"Suggestions applied: {len(suggestions)}")
        if updated:
            print("Updated .env keys:")
            for line in updated:
                print(f"- {line}")
        return

    if args.action == "run-once":
        decision = engine.run_cycle()
        print(json.dumps(to_jsonable(decision), default=str, indent=2))
        return

    if args.action == "run-loop":
        engine.run_loop()
        return

    # setup (default): train + backtest + run one cycle + notify
    report, csv_path, json_path = engine.run_backtest()
    decision = engine.run_cycle()
    message = setup_complete_message(report, decision)
    notifier.send("TradeFlow setup complete", message)

    print("TradeFlow is set up and ready.")
    print(json.dumps(report.__dict__, indent=2))
    print(f"Backtest artifacts: {csv_path}, {json_path}")
    print(json.dumps(to_jsonable(decision), default=str, indent=2))


if __name__ == "__main__":
    main()
