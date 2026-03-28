from __future__ import annotations

import time
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import pandas as pd

from autoresearch_trading.evaluator import (
    AutoresearchEvaluation,
    AutoresearchEvaluator,
    append_experiment_log,
    persist_best_candidate,
    promote_best_candidate,
)
from tradeflow_bot.config import Settings
from tradeflow_bot.strategy import StrategyParams


@dataclass
class AutoresearchLoopResult:
    iterations: int
    candidates_evaluated: int
    promoted: bool
    best_artifact_path: Path
    experiment_log_path: Path
    best_objective: float


def generate_candidate_params(settings: Settings, limit: int = 12) -> list[StrategyParams]:
    momentum_factors = [0.70, 0.85, 1.00, 1.15]
    zscore_factors = [0.80, 0.90, 1.00, 1.10]
    momentum_weights = [0.55, 0.65, 0.75, 0.85]
    momentum_windows = sorted(
        {
            max(int(settings.momentum_window * 0.75), 5),
            settings.momentum_window,
            int(settings.momentum_window * 1.25),
        }
    )
    mean_reversion_windows = sorted(
        {
            max(int(settings.mean_reversion_window * 0.75), 5),
            settings.mean_reversion_window,
            int(settings.mean_reversion_window * 1.25),
        }
    )

    out: list[StrategyParams] = []
    for mw, rw, mt_factor, zt_factor, mom_weight in product(
        momentum_windows,
        mean_reversion_windows,
        momentum_factors,
        zscore_factors,
        momentum_weights,
    ):
        out.append(
            StrategyParams(
                momentum_window=mw,
                mean_reversion_window=rw,
                volatility_window=settings.volatility_window,
                momentum_threshold=max(settings.momentum_threshold * mt_factor, 0.002),
                zscore_threshold=max(settings.zscore_threshold * zt_factor, 0.40),
                momentum_signal_weight=mom_weight,
                mean_reversion_signal_weight=round(1.0 - mom_weight, 2),
            )
        )

    # Keep the loop bounded and deterministic.
    return out[:limit]


def run_autoresearch_loop(
    settings: Settings,
    frame_provider,
    env_file: Path,
    duration_hours: float = 6.0,
    candidates_per_iteration: int = 12,
    max_iterations: int | None = None,
    sleep_seconds: float = 60.0,
    auto_promote: bool = False,
) -> AutoresearchLoopResult:
    evaluator = AutoresearchEvaluator()
    baseline = StrategyParams(
        momentum_window=settings.momentum_window,
        mean_reversion_window=settings.mean_reversion_window,
        volatility_window=settings.volatility_window,
        momentum_threshold=settings.momentum_threshold,
        zscore_threshold=settings.zscore_threshold,
        momentum_signal_weight=settings.momentum_signal_weight,
        mean_reversion_signal_weight=settings.mean_reversion_signal_weight,
    )

    deadline = time.time() + max(duration_hours, 0.0) * 3600.0
    iterations = 0
    candidates_evaluated = 0
    best_result: AutoresearchEvaluation | None = None
    best_objective = float("-inf")
    log_path = settings.report_dir / "autoresearch_experiments.jsonl"

    while time.time() < deadline:
        if max_iterations is not None and iterations >= max_iterations:
            break

        frames: dict[str, pd.DataFrame] = frame_provider()
        for candidate_idx, candidate in enumerate(generate_candidate_params(settings, limit=candidates_per_iteration)):
            result = evaluator.evaluate_walkforward_basket(
                frames=frames,
                baseline=baseline,
                candidate=candidate,
                interval=settings.interval,
                transaction_cost_bps=settings.transaction_cost_bps,
                windows=3,
            )
            append_experiment_log(result, settings.report_dir, label=f"iter-{iterations}-cand-{candidate_idx}")
            candidates_evaluated += 1
            objective = result.candidate_holdout.objective
            if objective > best_objective:
                best_result = result
                best_objective = objective
                persist_best_candidate(result, settings.report_dir)

        iterations += 1
        if sleep_seconds > 0 and time.time() < deadline:
            time.sleep(sleep_seconds)

    if best_result is None:
        raise RuntimeError("Autoresearch loop did not evaluate any candidates.")

    best_artifact_path = persist_best_candidate(best_result, settings.report_dir)
    promoted = False
    if auto_promote and best_result.promotable:
        promote_best_candidate(settings=settings, env_file=env_file, artifact_path=best_artifact_path)
        promoted = True

    return AutoresearchLoopResult(
        iterations=iterations,
        candidates_evaluated=candidates_evaluated,
        promoted=promoted,
        best_artifact_path=best_artifact_path,
        experiment_log_path=log_path,
        best_objective=best_objective,
    )
