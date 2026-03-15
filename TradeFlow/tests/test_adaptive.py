from pathlib import Path

from tradeflow_bot.adaptive import AdaptiveStrategyManager


def test_neighbors_respects_minimum(tmp_path: Path):
    manager = AdaptiveStrategyManager(
        state_path=tmp_path / "state.json",
        strategy_doc_path=tmp_path / "Strategy.md",
    )

    vals = manager._neighbors(base=0.001, factors=[0.5, 1.0, 2.0], minimum=0.01)
    assert min(vals) >= 0.01
