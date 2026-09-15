# -*- coding: utf-8 -*-
"""Unit tests for RebalanceEngine - ranking, signal generation, rotation logic."""
import pytest
from src.services.rebalance_engine import (
    RebalanceEngine, RebalanceResult, RebalanceSignal, SignalType, PositionRank,
)


def _make_position(code, name, sector, cost, price, ret=0):
    return {"code": code, "name": name, "sector": sector, "cost_price": cost, "current_price": price, "return_pct": ret}


def test_rank_positions():
    engine = RebalanceEngine()
    positions = [
        _make_position("A", "领涨", "科技", 100, 120, 20),
        _make_position("B", "跟风", "科技", 100, 105, 5),
        _make_position("C", "亏损", "科技", 100, 90, -10),
    ]
    sector_returns = {"科技": 10.0}
    rankings = engine.rank_positions(positions, sector_returns)
    assert len(rankings) == 3
    assert rankings[0].rs_ratio == pytest.approx(2.0, abs=0.1)
    assert rankings[0].rank == 1


def test_signal_weak_exit():
    engine = RebalanceEngine(weak_threshold_pct=0.34)
    r = PositionRank(stock_code="X", pnl_pct=-15, rs_ratio=0.3, rank=3, total_positions=3, percentile=10.0)
    signals = engine.generate_signals([r])
    exit_signals = [s for s in signals if s.signal_type == SignalType.EXIT]
    assert len(exit_signals) >= 1


def test_signal_weak_reduce():
    engine = RebalanceEngine(weak_threshold_pct=0.34)
    r = PositionRank(stock_code="Y", pnl_pct=-3, rs_ratio=0.5, rank=3, total_positions=3, percentile=10.0)
    signals = engine.generate_signals([r])
    reduce_signals = [s for s in signals if s.signal_type == SignalType.REDUCE]
    assert len(reduce_signals) >= 1


def test_signal_leader_add():
    engine = RebalanceEngine()
    r = PositionRank(stock_code="Z", stock_name="龙头", pnl_pct=12, rs_ratio=1.5, rank=1, total_positions=3, percentile=95.0)
    signals = engine.generate_signals([r])
    add_signals = [s for s in signals if s.signal_type == SignalType.ADD]
    assert len(add_signals) >= 1


def test_signal_hold_middle():
    engine = RebalanceEngine()
    r = PositionRank(stock_code="M", pnl_pct=3, rs_ratio=1.0, rank=2, total_positions=3, percentile=50.0)
    signals = engine.generate_signals([r])
    hold = [s for s in signals if s.signal_type == SignalType.HOLD]
    assert len(hold) == 1


def test_rotate_signal_on_exit():
    engine = RebalanceEngine(weak_threshold_pct=0.34)
    rankings = [
        PositionRank(stock_code="STRONG", stock_name="强势", pnl_pct=15, rs_ratio=1.8, rank=1, total_positions=3, percentile=95.0),
        PositionRank(stock_code="WEAK", pnl_pct=-20, rs_ratio=0.2, rank=3, total_positions=3, percentile=10.0),
    ]
    signals = engine.generate_signals(rankings, account_cash_pct=30)
    rotate = [s for s in signals if s.signal_type == SignalType.ROTATE]
    assert len(rotate) >= 1


def test_format_result():
    engine = RebalanceEngine()
    positions = [
        _make_position("600519", "茅台", "白酒", 1700, 1800, 5.9),
        _make_position("000858", "五粮液", "白酒", 150, 145, -3.3),
    ]
    sector_returns = {"白酒": 4.0}
    result = engine.analyze(positions, sector_returns)
    formatted = RebalanceEngine.format_result(result)
    assert "茅台" in formatted
    assert "五粮液" in formatted
    assert "排名" in formatted
