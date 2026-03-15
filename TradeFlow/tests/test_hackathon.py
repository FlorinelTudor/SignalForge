import pytest

from tradeflow_bot.hackathon import render_brief, render_compare, render_scorecard, shortlist_payload


def test_scorecard_includes_top_two_and_fallback():
    out = render_scorecard()

    assert "MilestonePay" in out
    assert "Policy Wallet" in out
    assert "Exit Liquidity Radar" in out
    assert "Top two overall: MilestonePay, Policy Wallet." in out


def test_milestonepay_brief_contains_api_and_demo_mode():
    out = render_brief("milestonepay")

    assert "POST /projects/from-chat" in out
    assert "POST /milestones/:id/release" in out
    assert "deterministic demo mode" in out.lower()
    assert "Base Sepolia" in out


def test_compare_recommends_when_to_pick_each_finalist():
    out = render_compare()

    assert "Choose MilestonePay" in out
    assert "Choose Policy Wallet" in out
    assert "Finalist Comparison" in out


def test_shortlist_payload_marks_finalists_and_fallback():
    payload = shortlist_payload()
    finalists = [idea["name"] for idea in payload["ideas"] if idea["finalist_rank"]]
    fallback = next(idea["name"] for idea in payload["ideas"] if idea["fallback"])

    assert finalists == ["MilestonePay", "Policy Wallet"]
    assert fallback == "Exit Liquidity Radar"


def test_unknown_brief_raises_key_error():
    with pytest.raises(KeyError):
        render_brief("unknown")
